"""Isolated, bounded CPU classifier trial. Never opens the production count DB."""
import ast,csv,hashlib,json,queue,shutil,sqlite3,threading,time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps

MODEL_SHA='a8e9faa4b42141343152c057b99e779b915eebb481f502753b1f5a335a454274'
NAMES={0:'passenger',1:'suv_4x4'}
MIN_CONFIDENCE=.80

def category(value):
    key=str(value).lower().strip()
    return '4x4' if key in ('4x4','suv','suv_4x4','suv/4x4') else key if key in ('passenger','truck') else 'unknown'

def record_id(payload):
    return hashlib.sha256((MODEL_SHA+'|'+str(payload['session_id'])+'|'+str(payload['track_id'])).encode()).hexdigest()

def crop_context(box,boxes,width,height,index,frame_sequence=None):
    x1,y1,x2,y2=map(float,box);area=max(1,(x2-x1)*(y2-y1));reason=''
    if x1<=1 or y1<=1 or x2>=width-1 or y2>=height-1:reason='edge_truncated'
    else:
        for j,other in enumerate(boxes):
            if j==index:continue
            a,b,c,d=map(float,other);inter=max(0,min(x2,c)-max(x1,a))*max(0,min(y2,d)-max(y1,b))
            if inter/min(area,max(1,(c-a)*(d-b)))>.20:reason='overlap';break
    return dict(reason=reason,box=[x1,y1,x2,y2],frame_size=[width,height],image_frame_sequence=frame_sequence)

class Predictor:
    def __init__(self,path):
        raw=Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=MODEL_SHA:raise ValueError('Candidate model checksum mismatch')
        import onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(raw,options,providers=['CPUExecutionProvider'])
        if self.session.get_inputs()[0].shape!=[1,3,224,224]:raise ValueError('Candidate input must be batch-1 RGB 224')
        names=ast.literal_eval(self.session.get_modelmeta().custom_metadata_map.get('names','{}'))
        if names!=NAMES:raise ValueError('Candidate class map mismatch')
        self.input=self.session.get_inputs()[0].name
    def predict(self,bgr):
        image=Image.fromarray(np.ascontiguousarray(bgr[:,:,::-1])).convert('RGB')
        padded=ImageOps.pad(image,(224,224),color=(30,30,30))
        tensor=np.asarray(padded,dtype=np.float32).transpose(2,0,1)[None]/255.
        p=np.asarray(self.session.run(None,{self.input:tensor})[0]).reshape(-1)
        if p.shape!=(2,) or not np.isfinite(p).all() or abs(float(p.sum())-1)>.001:raise ValueError('Invalid candidate probabilities')
        cls=int(p.argmax());return category(NAMES[cls]),float(p[cls])

class Store:
    def __init__(self,root):self.root=Path(root);self.db=self.root/'trial.sqlite3';self.image_bytes=None
    @contextmanager
    def connect(self,write=False):
        if write:
            self.root.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(self.db,timeout=.25)
        else:c=sqlite3.connect(self.db.resolve().as_uri()+'?mode=ro',uri=True,timeout=.25)
        c.row_factory=sqlite3.Row
        try:
            if write:
                c.execute('CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,day TEXT,stamp TEXT,session_id TEXT,track_id TEXT,source TEXT,original_class TEXT,production_class TEXT,candidate_class TEXT,raw_class TEXT,confidence REAL,reason TEXT,model_sha TEXT,image TEXT,payload TEXT,human_label TEXT NOT NULL DEFAULT "",reviewer TEXT NOT NULL DEFAULT "",notes TEXT NOT NULL DEFAULT "",reviewed_at TEXT)')
                c.execute('CREATE INDEX IF NOT EXISTS candidate_day ON records(day,model_sha)')
                c.execute('CREATE TABLE IF NOT EXISTS human_reviews(id TEXT,stamp TEXT,label TEXT,reviewer TEXT,notes TEXT)')
            yield c
            if write:c.commit()
        except Exception:
            if write:c.rollback()
            raise
        finally:c.close()
    def rows(self,day):
        if not self.db.exists():return []
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM records WHERE day=? AND model_sha=? ORDER BY stamp DESC',(day,MODEL_SHA))]
    def save(self,payload,prediction,image=None):
        key=record_id(payload);stamp=str(payload['timestamp']);image_name=''
        if image is not None:
            folder=self.root/'images';folder.mkdir(parents=True,exist_ok=True)
            if self.image_bytes is None:self.image_bytes=sum(p.stat().st_size for p in folder.rglob('*.jpg'))
            if self.image_bytes<200*1024*1024 and shutil.disk_usage(self.root).free>1024**3:
                path=folder/stamp[:10]/(key+'.jpg');path.parent.mkdir(exist_ok=True)
                if not path.exists():
                    Image.fromarray(np.ascontiguousarray(image[:,:,::-1])).save(path,quality=90)
                    self.image_bytes+=path.stat().st_size
                image_name=str(path.relative_to(self.root))
        values=(key,stamp[:10],stamp,str(payload['session_id']),str(payload['track_id']),str(payload.get('source','')),
            category(payload.get('original_class')),category(payload.get('final_class')),prediction['candidate_class'],
            prediction.get('raw_class',''),prediction.get('confidence'),prediction['reason'],MODEL_SHA,image_name,json.dumps(payload,default=str))
        with self.connect(True) as c:
            c.execute('INSERT OR IGNORE INTO records(id,day,stamp,session_id,track_id,source,original_class,production_class,candidate_class,raw_class,confidence,reason,model_sha,image,payload) VALUES('+','.join('?'*15)+')',values)
    def review(self,key,label,reviewer,notes):
        if label not in ('passenger','4x4','truck','unsure') or not reviewer.strip() or not notes.strip():raise ValueError('Choose an actual class and enter reviewer name and evidence/notes')
        stamp=datetime.now(timezone.utc).isoformat()
        with self.connect(True) as c:
            result=c.execute('UPDATE records SET human_label=?,reviewer=?,notes=?,reviewed_at=? WHERE id=? AND model_sha=?',(label,reviewer[:80],notes[:2000],stamp,key,MODEL_SHA))
            if result.rowcount!=1:raise ValueError('Comparison record not found')
            c.execute('INSERT INTO human_reviews VALUES(?,?,?,?,?)',(key,stamp,label,reviewer[:80],notes[:2000]))
    def export(self,path,day):
        fields=['id','stamp','track_id','original_class','production_class','candidate_class','raw_class','confidence','reason','model_sha','human_label','reviewer','notes','image']
        with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fields);writer.writeheader()
            for r in self.rows(day):writer.writerow({k:("'"+r[k] if isinstance(r[k],str) and r[k].lstrip().startswith(('=','+','-','@')) else r[k]) for k in fields})
    def summary(self,day):
        rows=self.rows(day);accepted=[r for r in rows if r['candidate_class']!='unknown']
        verified=[r for r in rows if r['human_label'] in ('passenger','4x4','truck')]
        return dict(records=len(rows),production_counts=dict(Counter(r['production_class'] for r in rows)),
            original_counts=dict(Counter(r['original_class'] for r in rows)),candidate_counts=dict(Counter(r['candidate_class'] for r in rows)),
            accepted=len(accepted),disagreements=sum(r['candidate_class']!=r['production_class'] for r in accepted),
            unknown=len(rows)-len(accepted),verified=len(verified),
            original_verified_correct=sum(r['production_class']==r['human_label'] for r in verified),
            candidate_verified_correct=sum(r['candidate_class']==r['human_label'] for r in verified))

class Trial:
    """One queued crop per actual OAK count; no per-frame inference."""
    def __init__(self,root,model,on_status=None,predictor_factory=Predictor):
        self.store=Store(root);self.model=Path(model);self.on_status=on_status or (lambda s:None);self.factory=predictor_factory
        self.queue=queue.Queue(maxsize=8);self.stop_event=threading.Event();self.abort=threading.Event();self.lock=threading.Lock()
        self.seen=set();self.thread=None;self.predictor=None;self.model_error='';self.error='';self.dropped=0;self.completed=0
    def notify(self,text):
        try:self.on_status('CANDIDATE OBSERVE-ONLY: '+text)
        except Exception:pass
    def submit(self,payload,image=None):
        if payload.get('scope')!='production':return False
        key=record_id(payload)
        with self.lock:
            if self.stop_event.is_set() or key in self.seen:return False
            item=(dict(payload),image.copy() if image is not None else None)
            try:self.queue.put_nowait(item)
            except queue.Full:self.dropped+=1;self.notify('comparison queue full; production counts unaffected');return False
            self.seen.add(key)
            if self.thread is None:
                self.thread=threading.Thread(target=self.run,name='candidate-observe-only',daemon=True);self.thread.start()
        return True
    def classify(self,payload,image):
        reason=payload.get('candidate_context',{}).get('reason','')
        if category(payload.get('final_class'))=='truck':reason='truck_not_trained'
        if image is None or image.size==0:reason=reason or 'no_crop'
        elif min(image.shape[:2])<48 or image.shape[1]<64:reason=reason or 'small_crop'
        elif not .85<=image.shape[1]/image.shape[0]<=2.8:reason=reason or 'crop_aspect'
        elif float(np.asarray(Image.fromarray(np.ascontiguousarray(image[:,:,::-1])).convert('L')).std())<12:reason=reason or 'low_contrast'
        if reason:return dict(candidate_class='unknown',reason=reason)
        if self.model_error:return dict(candidate_class='unknown',reason='model_unavailable')
        try:
            if self.predictor is None:self.predictor=self.factory(self.model);self.notify('model ready; 80% threshold; no production class changes')
            cls,confidence=self.predictor.predict(image)
            if cls not in ('passenger','4x4') or not np.isfinite(confidence) or not 0<=confidence<=1:raise ValueError('Invalid candidate result')
            return dict(candidate_class=cls if confidence>=MIN_CONFIDENCE else 'unknown',raw_class=cls,confidence=confidence,reason='' if confidence>=MIN_CONFIDENCE else 'low_confidence')
        except Exception as exc:
            self.model_error=str(exc);self.notify('model unavailable: '+self.model_error)
            return dict(candidate_class='unknown',reason='model_unavailable')
    def run(self):
        while not self.stop_event.is_set() or not self.queue.empty():
            try:payload,image=self.queue.get(timeout=.1)
            except queue.Empty:continue
            try:
                if self.abort.is_set():continue
                prediction=self.classify(payload,image)
                if not self.abort.is_set():
                    self.store.save(payload,prediction,image if image is not None and min(image.shape[:2])>=16 else None)
                    self.completed+=1
            except Exception as exc:self.error=str(exc);self.notify('record could not be saved: '+self.error)
            finally:self.queue.task_done()
    def snapshot(self):return dict(completed=self.completed,dropped=self.dropped,error=self.error or self.model_error,queued=self.queue.unfinished_tasks)
    def close(self,timeout=5):
        self.stop_event.set()
        if self.thread is not None:self.thread.join(timeout)
        if self.thread is not None and self.thread.is_alive():
            self.abort.set();self.notify('background stop timed out; late results discarded');return False
        return True
