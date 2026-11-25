"""Separate review database and bounded asynchronous evidence writer; no production writes."""
import csv,json,queue,sqlite3,threading,time,uuid,zipfile
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone

STATUSES={'overlap':{'unreviewed','confirmed_overlap','not_overlap','unsure'},'tyre':{'unreviewed','passenger','4x4','truck','unsure'},
          'foreign':{'unreviewed','confirmed_foreign','false_alert','unsure'}}
REASONS={'normal_tyre','belt_join','shadow','other',''}

def safe_csv(value):
    return "'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value

def comparison(assist,track,frame,visual,score,final,mode,settings):
    evidence=assist.evidence(track,frame)
    proposed,_,changed=assist.resolve(track,frame,visual,score,ignore_observe=True)
    return dict(original_class=visual,visual_vote=score,size_candidate=evidence['candidate'] if evidence else None,
        diameter_mm=evidence['diameter_mm'] if evidence else None,assisted_class=proposed,
        disagreement=changed,size_disagreement=bool(evidence and evidence['candidate'] and evidence['candidate']!=visual),final_class=final,mode=mode,calibration=settings,
        evidence_observations=evidence['observations'] if evidence else 0)

class ReviewStore:
    def __init__(self,root,on_error=None):
        self.root=Path(root);self.db=self.root/'reviews.sqlite3';self.on_error=on_error or (lambda s:None)
        self.q=queue.Queue(maxsize=128);self.thread=None;self.lock=threading.Lock();self.last_error='';self.dropped=0;self.dirty=set()
    @contextmanager
    def connect(self):
        self.root.mkdir(parents=True,exist_ok=True)
        c=sqlite3.connect(self.db,timeout=5)
        pragma=c.execute('PRAGMA journal_mode=WAL')
        try:pragma.fetchall()
        finally:pragma.close()
        c.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY,kind TEXT NOT NULL,stamp TEXT NOT NULL,day TEXT NOT NULL,scope TEXT NOT NULL,payload TEXT NOT NULL,image TEXT,status TEXT NOT NULL DEFAULT "unreviewed",reason TEXT NOT NULL DEFAULT "",notes TEXT NOT NULL DEFAULT "",reviewed_at TEXT)')
        c.execute('CREATE INDEX IF NOT EXISTS records_day ON records(day,kind,scope)')
        c.execute('CREATE TABLE IF NOT EXISTS overlap_adjustments (record_id TEXT PRIMARY KEY, quantity INTEGER NOT NULL, tyre_type TEXT NOT NULL, reviewer TEXT NOT NULL, notes TEXT NOT NULL, revision INTEGER NOT NULL, updated_at TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS overlap_adjustment_history (record_id TEXT, quantity INTEGER, tyre_type TEXT, reviewer TEXT, notes TEXT, revision INTEGER, updated_at TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS review_history (record_id TEXT,at TEXT,status TEXT,reason TEXT,notes TEXT)')
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback();raise
        finally:c.close()
    def fail(self,message):
        self.last_error=str(message)
        try:self.on_error('Review records: '+self.last_error)
        except Exception:pass
    def submit(self,kind,payload,image=None,key=None):
        if kind not in STATUSES:raise ValueError('Invalid record kind')
        item=(kind,dict(payload),image,key or uuid.uuid4().hex)
        with self.lock:
            if self.thread is None:
                self.thread=threading.Thread(target=self._run,name='classification-review-writer',daemon=True);self.thread.start()
        try:self.q.put_nowait(item);return True
        except queue.Full:self.dropped+=1;self.fail('queue full; evidence record dropped');return False
    def _run(self):
        while True:
            try:item=self.q.get(timeout=60)
            except queue.Empty:
                try:self.daily_reports()
                except Exception as e:self.fail(e)
                continue
            try:
                if item is None:
                    self.daily_reports();return
                self._write(*item)
                self.dirty.add(str(item[1].get("timestamp", ""))[:10])
            except Exception as e:self.fail(e)
            finally:self.q.task_done()
    def _write(self,kind,payload,image,key):
        stamp=str(payload.get('timestamp') or datetime.now(timezone.utc).isoformat());day=stamp[:10]
        scope=payload.get('scope','production');safe=uuid.uuid5(uuid.NAMESPACE_URL,key).hex
        with self.connect() as c:
            if c.execute('SELECT 1 FROM records WHERE id=?',(key,)).fetchone():return
        image_path=''
        if image is not None:
            import cv2
            folder=self.root/'images'/day;folder.mkdir(parents=True,exist_ok=True)
            path=folder/(safe+'.jpg')
            if not cv2.imwrite(str(path),image,[cv2.IMWRITE_JPEG_QUALITY,90]):raise OSError('Evidence JPEG write failed')
            image_path=str(path.relative_to(self.root))
        with self.connect() as c:
            c.execute('INSERT OR IGNORE INTO records(id,kind,stamp,day,scope,payload,image) VALUES(?,?,?,?,?,?,?)',
                (key,kind,stamp,day,scope,json.dumps(payload,allow_nan=False),image_path))
    def daily_reports(self,days=None):
        for day in list(days if days is not None else self.dirty):
            if len(day)!=10:continue
            rows=self.rows(day,scope='production',limit=1000000);data=summary(rows)
            folder=self.root/'daily';folder.mkdir(parents=True,exist_ok=True)
            target=folder/(day+'_summary.json');temp=target.with_suffix('.'+uuid.uuid4().hex+'.tmp')
            temp.write_text(json.dumps(data,indent=2));temp.replace(target)
            target=folder/(day+'_summary.csv');temp=target.with_suffix('.'+uuid.uuid4().hex+'.tmp')
            with temp.open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f);w.writerow(['Method','Passenger','SUV/4x4','Truck','Unclassified','Total'])
                for name,key in [('Original OAK visual','original_counts'),('Size-assisted proposal (includes visual fallback)','assisted_counts'),('Size-only candidates; uncertain/unmeasured separate','size_only_counts')]:
                    c=data[key];w.writerow([name,c.get('passenger',0),c.get('4x4',0),c.get('truck',0),c.get('unknown',0)+c.get('uncertain_or_unmeasured',0),sum(c.values())])
                w.writerow(['Usable size estimates',data['measured']]);w.writerow(['No size estimate',data['tyres']-data['measured']]);w.writerow(['Disagreements',data['disagreements']]);w.writerow(['Human-marked foreign false alerts',data['false_alerts']]);w.writerow(['Confirmed missed-tyre adjustments (separate ledger)',data.get('confirmed_missed',0)])
            temp.replace(target);self.dirty.discard(day)

    def flush(self,timeout=10):
        deadline=time.monotonic()+timeout
        while self.q.unfinished_tasks and time.monotonic()<deadline:time.sleep(.01)
        return not self.q.unfinished_tasks
    def close(self,timeout=10):
        if self.thread is None or not self.thread.is_alive():return True
        if not self.flush(timeout):self.fail('shutdown timed out; some queued records are unsaved');return False
        self.q.put(None);self.thread.join(timeout);return not self.thread.is_alive()
    def rows(self,day=None,kind=None,scope='production',limit=500):
        clauses=['scope=?'];args=[scope]
        if day:clauses.append('day=?');args.append(day)
        if kind:clauses.append('kind=?');args.append(kind)
        with self.connect() as c:
            c.row_factory=sqlite3.Row
            rows=c.execute('SELECT * FROM records WHERE '+' AND '.join(clauses)+' ORDER BY stamp DESC LIMIT ?',args+[limit]).fetchall()
        result=[dict(r,payload=json.loads(r['payload'])) for r in rows]
        with self.connect() as c:
            c.row_factory=sqlite3.Row
            adjustments={r['record_id']:dict(r) for r in c.execute('SELECT * FROM overlap_adjustments')}
        for row in result:row['adjustment']=adjustments.get(row['id'],{})
        return result
    def review(self,key,status,reason='',notes=''):
        with self.connect() as c:
            row=c.execute('SELECT kind,day FROM records WHERE id=?',(key,)).fetchone()
            if not row or status not in STATUSES[row[0]] or reason not in REASONS:raise ValueError('Invalid review')
            if row[0]=='overlap' and status!='confirmed_overlap':
                adjustment=c.execute('SELECT quantity FROM overlap_adjustments WHERE record_id=?',(key,)).fetchone()
                if adjustment and adjustment[0]:raise ValueError('Set the missed adjustment to zero before changing the confirmed overlap review')
            if status=='false_alert' and not reason:raise ValueError('Choose a false-alert reason')
            now=datetime.now(timezone.utc).isoformat()
            c.execute('UPDATE records SET status=?,reason=?,notes=?,reviewed_at=? WHERE id=?',(status,reason,notes,now,key))
            c.execute('INSERT INTO review_history VALUES(?,?,?,?,?)',(key,now,status,reason,notes))
        self.daily_reports([row[1]])
    def adjust_overlap(self,key,quantity,tyre_type,reviewer,notes,expected_revision=0):
        """Set an absolute reviewed correction. Never append a production count."""
        if type(quantity) is not int or not 0<=quantity<=20:raise ValueError('Missed quantity must be 0 to 20')
        if tyre_type not in ('passenger','4x4','truck','unknown'):raise ValueError('Choose a tyre class')
        reviewer=reviewer.strip();notes=notes.strip()
        if not reviewer or not notes:raise ValueError('Reviewer name and evidence/reason are required')
        if len(reviewer)>80 or len(notes)>1000:raise ValueError('Use a reviewer name up to 80 characters and a reason up to 1000 characters')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            auto=c.execute('SELECT payload FROM records WHERE id=?',(key,)).fetchone()
            if auto and json.loads(auto[0]).get('automatic_correction'):
                raise ValueError('Use Reverse overlap correction; do not add a second manual adjustment to an automatic event')
            row=c.execute('SELECT kind,status,scope,day FROM records WHERE id=?',(key,)).fetchone()
            if not row or row[:3]!=('overlap','confirmed_overlap','production'):
                raise ValueError('Confirm a production overlap review before saving a missed adjustment')
            old=c.execute('SELECT quantity,tyre_type,reviewer,notes,revision FROM overlap_adjustments WHERE record_id=?',(key,)).fetchone()
            values=(quantity,tyre_type,reviewer,notes)
            # Retried saves set the same value; they never add it again.
            if old and old[:4]==values:return old[4]
            revision=old[4] if old else 0
            if revision!=expected_revision:raise ValueError('Adjustment changed in another review; refresh before saving')
            revision+=1;stamp=datetime.now(timezone.utc).isoformat()
            args=(key,*values,revision,stamp)
            c.execute('INSERT OR REPLACE INTO overlap_adjustments VALUES(?,?,?,?,?,?,?)',args)
            c.execute('INSERT INTO overlap_adjustment_history VALUES(?,?,?,?,?,?,?)',args)
        self.daily_reports([row[3]])
        return revision

    def image_path(self,row):
        if not row.get('image'):return None
        path=(self.root/row['image']).resolve()
        return path if path.is_relative_to(self.root.resolve()) and path.is_file() else None
    def export(self,target,day=None,kind=None,scope='production'):
        # Explicitly reviewed cases only; unreviewed/unsure are never negative labels.
        rows=self.rows(day,kind,scope,limit=1000000)
        fields=['id','stamp','kind','scope','status','reason','notes','original_class','size_candidate','diameter_mm','assisted_class','final_class','predicted_class','confidence','disagreement','recording_reference','frame_sequence','track_ids','counted_track_ids','not_counted_track_ids','association_status','termination_reason','confirmed_missed','adjustment_class','adjustment_reviewer','adjustment_reason','adjustment_revision','automatic_correction','added_tyres','assumed_tyres','model_sha256','snapshot']
        target=Path(target)
        if target.suffix.lower()=='.csv':
            with target.open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
                for r in rows:
                    a=r.get('adjustment',{});extra=dict(confirmed_missed=a.get('quantity',0),adjustment_class=a.get('tyre_type',''),adjustment_reviewer=a.get('reviewer',''),adjustment_reason=a.get('notes',''),adjustment_revision=a.get('revision',0))
                    w.writerow({k:safe_csv(extra.get(k,r.get(k,r['payload'].get(k,'')))) for k in fields})
        else:
            selected=[r for r in rows if r['status'] not in ('unreviewed','unsure')]
            with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
                manifest=[]
                for r in selected:
                    image=self.image_path(r);entry=dict(r);entry['image_available']=bool(image)
                    if image:
                        name='images/'+image.name;z.write(image,name);entry['image']=name
                    manifest.append(entry)
                z.writestr('review_manifest.json',json.dumps(manifest,indent=2))
                z.writestr('README.txt','REVIEWED EVIDENCE, NOT A READY-TO-TRAIN DATASET. Original predictions and human reviews are separate. Full foreign frames may contain other objects. Box coordinates describe only the original prediction, not verified ground truth. False-alert images must NOT automatically receive empty labels; inspect and annotate every real target. No weights or production counts changed.\n')
        return len(rows)

def summary(rows):
    tyres=[r for r in rows if r['kind']=='tyre'];foreign=[r for r in rows if r['kind']=='foreign']
    original=Counter(r['payload'].get('original_class','unknown') for r in tyres)
    assisted=Counter(r['payload'].get('assisted_class','unknown') for r in tyres)
    final=Counter(r['payload'].get('final_class','unknown') for r in tyres)
    size=Counter(r['payload'].get('size_candidate') or 'uncertain_or_unmeasured' for r in tyres)
    return {'final_counts':dict(final),'original_counts':dict(original),'assisted_counts':dict(assisted),'size_only_counts':dict(size),'tyres':len(tyres),'measured':sum(r['payload'].get('diameter_mm') is not None for r in tyres),
            'disagreements':sum(bool(r['payload'].get('disagreement')) for r in tyres),
            'size_disagreements':sum(bool(r['payload'].get('size_disagreement')) for r in tyres),
            'false_alerts':sum(r['status']=='false_alert' for r in foreign),
            'confirmed_missed':sum(r.get('adjustment',{}).get('quantity',0) for r in rows if r['kind']=='overlap' and r['status']=='confirmed_overlap'),
            'overlap_events':sum(r['kind']=='overlap' for r in rows),
            'overlap_needs_review':sum(r['kind']=='overlap' and r['payload'].get('association_status')=='needs_review' for r in rows),
            'foreign':len(foreign),'unreviewed':sum(r['status']=='unreviewed' for r in rows)}
