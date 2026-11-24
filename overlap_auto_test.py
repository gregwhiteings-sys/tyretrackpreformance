from overlap_auto import Events,write_correction,corrections,reverse,Detector,SHA
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
import sqlite3,hashlib,numpy as np
STAMP='2026-11-24T08:00:00+10:00';d=(10,10,90,90,7,.9,'passenger')
def make(two=False,paused=False):
 out=[];e=Events(lambda p,im:out.append(p),'test')
 for f in [1,5,9]:
  tracks=[d]+([(95,10,140,90,8,.9,'passenger')] if two else [])
  e.tick(tracks,f,True);e.observe([([0,0,150,100],.8)],dict(enabled=True,tracks=tracks,frame=f,stamp=STAMP,source='oak',image=None))
 e.counted(7,STAMP,10)
 if two:e.counted(8,STAMP,30)
 if paused:e.tick([],50,False)
 e.tick([],110,True)
 return out,e
out,e=make();assert len(out)==1 and out[0]['eligible'];e.tick([],200,True);assert len(out)==1
assert not make(True)[0][0]['eligible'];assert not make(paused=True)[0]
for hits in [2,3]:
 out2=[];ev=Events(lambda p,im:out2.append(p))
 for f in range(hits):
  ev.tick([d],f,True);ev.observe([([0,0,100,100],.9)],dict(enabled=True,tracks=[d],frame=f,stamp=STAMP,source='oak',image=None))
 ev.tick([],100,True);assert not out2[0]['eligible']
with TemporaryDirectory() as t:
 db=Path(t)/'counts.db'
 with closing(sqlite3.connect(db)) as c:
  c.execute('CREATE TABLE counts(id INTEGER PRIMARY KEY,ts TEXT,source TEXT,track_id INTEGER,confidence REAL,tyre_type TEXT,class_confidence REAL,metric_utc REAL)')
  c.execute('INSERT INTO counts VALUES(1,?,?,?,?,?,?,?)',(STAMP,'oak',7,.9,'passenger',.9,__import__('datetime').datetime.fromisoformat(STAMP).timestamp()));c.commit()
 assert write_correction(db,out[0]);assert not write_correction(db,out[0]);assert len(corrections(db))==1
 with closing(sqlite3.connect(db)) as c:assert c.execute('SELECT count(*) FROM counts').fetchone()[0]==2
 from management_reports import build_briefing
 for weekly in (False,True):
  report,_=build_briefing(db,'oak',Path(t)/'reports',__import__('datetime').datetime.fromisoformat(STAMP).replace(hour=9),weekly)
  assert report['total']==2 and report['automatic_overlap_added']==1 and report['reviewed_total']==2,report
 reverse(db,out[0]['event_id'],'False overlap reviewed by Greg');reverse(db,out[0]['event_id'],'Retry')
 assert not write_correction(db,out[0])
 with closing(sqlite3.connect(db)) as c:assert c.execute('SELECT track_id FROM counts').fetchall()==[(7,)]
 assert corrections(db)[0]['reversed']==1
 for scope in ['test','replay']:assert not write_correction(db,dict(out[0],scope=scope,event_id=scope))
model=Path(__file__).parent/'overlap_v7/best.onnx';assert hashlib.sha256(model.read_bytes()).hexdigest()==SHA
net=Detector(model);assert net.net.get_inputs()[0].shape==[1,3,416,416];assert isinstance(net(np.zeros((360,640,3),np.uint8)),list)
print('PASS V7 inference; stable +1 once, two-count/zero-count/pause suppression, atomic retry/reversal and test isolation')
