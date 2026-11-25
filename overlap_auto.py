"""V8 background inference and event-level, auditable +1 production corrections.
Never infer an exact group size: the authorized policy assumes two tyres.
"""
import hashlib,json,sqlite3,threading,time,uuid
from pathlib import Path
from queue import Queue,Empty,Full
from datetime import datetime
from contextlib import closing
SHA='ac858b5e077a1099f13f441642285c652015ed20674e2beb67a12ba375a35c59'

def schema(c):
    c.execute('CREATE TABLE IF NOT EXISTS overlap_auto_counts (event_id TEXT PRIMARY KEY,count_id INTEGER UNIQUE,stamp TEXT,payload TEXT,reversed INTEGER NOT NULL DEFAULT 0,reason TEXT)')

def write_correction(db,event):
    """Atomic retry-safe insert; original OAK rows stay intact."""
    if event.get('scope')!='production' or not event.get('eligible') or len(event.get('counted_ids',[]))!=1:return False
    with closing(sqlite3.connect(db,timeout=5)) as c:
        schema(c);c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM overlap_auto_counts WHERE event_id=?',(event['event_id'],)).fetchone():return False
        stamp=datetime.fromisoformat(event['timestamp'])
        cur=c.execute('INSERT INTO counts(ts,source,track_id,confidence,tyre_type,class_confidence,metric_utc) VALUES(?,?,?,?,?,?,?)',
            (stamp.isoformat(),event['source'],-1,event['confidence'],'unknown',0,stamp.timestamp()))
        c.execute('INSERT INTO overlap_auto_counts(event_id,count_id,stamp,payload) VALUES(?,?,?,?)',
            (event['event_id'],cur.lastrowid,event['timestamp'],json.dumps(event)))
        c.commit();return True

def corrections(db,day=None):
    if not Path(db).exists():return []
    with closing(sqlite3.connect(db,timeout=5)) as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='overlap_auto_counts'").fetchone():return []
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('SELECT * FROM overlap_auto_counts'+(' WHERE substr(stamp,1,10)=?' if day else '')+' ORDER BY stamp DESC',([day] if day else []))]

def reverse(db,key,reason):
    if not reason.strip():raise ValueError('Enter a reason for reversing the automatic correction')
    with closing(sqlite3.connect(db,timeout=5)) as c:
        schema(c);c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT count_id,reversed FROM overlap_auto_counts WHERE event_id=?',(key,)).fetchone()
        if not r:raise ValueError('Automatic correction not found')
        if not r[1]:
            c.execute('DELETE FROM counts WHERE id=? AND track_id=-1',(r[0],))
            c.execute('UPDATE overlap_auto_counts SET reversed=1,reason=? WHERE event_id=?',(reason,key))
        c.commit()

class Events:
    """Associate group boxes with OAK tracks; finish only after all tracks retire.
    Require 3 model observations, one committed OAK count and no second count.
    Ambiguous assignment, tracker recovery, pause, shutdown or long events cancel.
    """
    def __init__(self,emit,session=None):
        self.emit=emit;self.session=session or uuid.uuid4().hex;self.active=[];self.used=set();self.counts={};self.seen={};self.seq=0
    def counted(self,ident,stamp,frame):self.counts[int(ident)]=(stamp,frame)
    def tick(self,tracks,frame,enabled):
        for d in tracks:self.seen[int(d[4])]=frame
        if not enabled:self.cancel();return
        for e in list(self.active):
            if frame-e['first']>900:
                self.used.update(e['ids']);self.active.remove(e);continue
            if all(frame-self.seen.get(i,frame)>90 for i in e['ids']):
                ids=[i for i in e['ids'] if i in self.counts]
                # Count must belong to this event, including a short lead-in.
                ids=[i for i in ids if self.counts[i][1]>=e['first']-30]
                p=dict(event_id=e['key'],timestamp=self.counts[ids[0]][0] if len(ids)==1 else e['stamp'],observation_timestamp=e['stamp'],source=e['source'],scope='production',
                    eligible=e['hits']>=3 and len(ids)==1 and len(e['ids'])<=2,
                    counted_ids=sorted(ids),track_ids=sorted(e['ids']),counted_tracks=len(ids),observed_tracks=len(e['ids']),confidence=e['peak'],
                    model_sha256=SHA,assumed_tyres=2,added_tyres=1,tyre_type='unknown',
                    recording_reference=e.get('recording'),group_bbox=e.get('bbox'),frame_sequence=e.get('sequence'),
                    detection_method='V8 overlap model; assumed two; one linked OAK count')
                self.emit(p,e['image']);self.used.update(e['ids']);self.active.remove(e)
        live=set().union(*(e['ids'] for e in self.active)) if self.active else set()
        keep={i for i,n in self.seen.items() if frame-n<=120 or i in live}
        self.seen={i:n for i,n in self.seen.items() if i in keep};self.counts={i:n for i,n in self.counts.items() if i in keep}
        # used IDs retained for entire camera session: IDs must be namespaced on recovery.
    def observe(self,boxes,meta):
        if not meta['enabled']:return
        for bb,score in boxes:
            if score<.65:continue
            ids={int(d[4]) for d in meta['tracks'] if bb[0]<= (d[0]+d[2])/2 <=bb[2] and bb[1]<=(d[1]+d[3])/2<=bb[3]}
            if not ids or len(ids)>2 or ids&self.used:continue
            matches=[e for e in self.active if e['ids']&ids]
            if len(matches)>1:
                for e in matches:self.used.update(e['ids']);self.active.remove(e)
                continue
            if matches:
                e=matches[0];e['ids']|=ids
                if meta['frame']-e['last']>60:e['hits']=0
                e['hits']+=1;e['last']=meta['frame'];e['peak']=max(score,e['peak'])
            else:
                self.seq+=1
                self.active.append(dict(ids=ids,first=meta['frame'],last=meta['frame'],hits=1,peak=score,
                    stamp=meta['stamp'],source=meta['source'],image=meta['image'],bbox=list(map(float,bb)),recording=meta.get('recording'),
                    sequence=meta.get('sequence'),key=f'{self.session}-v8-{self.seq}'))
    def cancel(self):
        for e in self.active:self.used.update(e['ids'])
        self.active.clear()

class Detector:
    def __init__(self,path):
        import onnxruntime as ort
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=SHA:raise ValueError('V8 model hash mismatch')
        opts=ort.SessionOptions();opts.intra_op_num_threads=1;opts.inter_op_num_threads=1
        self.net=ort.InferenceSession(str(path),sess_options=opts,providers=['CPUExecutionProvider'])
        self.name=self.net.get_inputs()[0].name
    def __call__(self,im):
        import cv2,numpy as np
        h,w=im.shape[:2];scale=min(416/w,416/h);nw,nh=round(w*scale),round(h*scale);left=(416-nw)//2;top=(416-nh)//2
        a=np.full((416,416,3),114,np.uint8);a[top:top+nh,left:left+nw]=cv2.resize(im,(nw,nh))
        x=np.ascontiguousarray(a[:,:,::-1].transpose(2,0,1)[None],dtype=np.float32)/255
        raw=self.net.run(None,{self.name:x})[0][0].T;raw=raw[raw[:,4]>=.65]
        if not len(raw):return []
        boxes=np.column_stack((raw[:,0]-raw[:,2]/2,raw[:,1]-raw[:,3]/2,raw[:,2:4]))
        result=[]
        for j in np.asarray(cv2.dnn.NMSBoxes(boxes.tolist(),raw[:,4].tolist(),.65,.5)).reshape(-1):
            xx,yy,bw,bh=boxes[j];result.append(([max(0,(xx-left)/scale),max(0,(yy-top)/scale),min(w,(xx+bw-left)/scale),min(h,(yy+bh-top)/scale)],float(raw[j,4])))
        return result

class Background:
    def __init__(self,path,on_error):
        self.path=path;self.on_error=on_error;self.pending=Queue(1);self.results=Queue(1);self.stop=threading.Event();self.last=0
        self.thread=threading.Thread(target=self.run,name='overlap-v8',daemon=True);self.thread.start()
    def submit(self,meta):
        if time.monotonic()-self.last<.5:return
        self.last=time.monotonic()
        try:self.pending.put_nowait(meta)
        except Full:pass
    def run(self):
        try:
            detector=Detector(self.path)
            self.on_error('OVERLAP V8 ACTIVE · 65% · automatic +1 enabled')
            while not self.stop.is_set():
                try:m=self.pending.get(timeout=.2)
                except Empty:continue
                boxes=detector(m['image'])
                try:self.results.put_nowait((boxes,m))
                except Full:pass
        except Exception as e:self.on_error('OVERLAP V8 OFF: '+str(e))
    def poll(self):
        try:return self.results.get_nowait()
        except Empty:return None
    def close(self):self.stop.set();self.thread.join(10)
