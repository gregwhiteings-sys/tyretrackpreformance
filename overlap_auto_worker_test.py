"""Exercise real count worker; simulated OAK result tensors, real review persistence."""
import os,sys,types,tempfile,time
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
import numpy as np
from PyQt5.QtCore import QCoreApplication
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
import TyreTrack_Production_Monitor as m
import oak_rvc2
from belt_width_assist import BeltSettings,BeltWidthAssist
app=QCoreApplication.instance() or QCoreApplication([])
class Tensor:
 def __init__(self,value):self.value=np.asarray(value)
 def cpu(self):return self
 def numpy(self):return self.value
 def int(self):return self
 def tolist(self):return self.value.tolist()
class Tracker:
 names={0:'passenger',1:'4x4'}
 def track_oak(self,frame,raw,*args):
  if raw is None:return types.SimpleNamespace(boxes=None)
  box,cls=raw;b=types.SimpleNamespace(xyxy=Tensor([box]),id=Tensor([1]),conf=Tensor([.9]),cls=Tensor([cls]))
  return types.SimpleNamespace(boxes=b)
oak_rvc2.OakTracker=Tracker
ys=list(range(310,110,-4))+[0]*110;statuses=[];counts=[]
class Source:
 def __init__(self,*a,**k):self.index=0;self.last_read_frame_at=time.monotonic();self.recording_path='sample_recording.mp4'
 def read(self):
  if self.index==len(ys):worker.running=False;return False,None,None
  if self.index>=50:
   self.last_read_neural_output=None;self.index+=1;return True,np.zeros((360,640,3),np.uint8),self.index
  cy=ys[self.index];left,right=worker.belt_assist.edges(cy,640,360);bw=(right-left)*.76;cx=(left+right)/2
  self.last_read_neural_output=((cx-bw/2,cy-bw*.35,cx+bw/2,cy+bw*.35),0 if self.index%5 in [0,1,3] else 1)
  self.index+=1;return True,np.zeros((360,640,3),np.uint8),self.index
 def release(self):pass
m.OakSource=Source;m.oak_in_operating_hours=lambda:True;m.log_count=m.log_count

import overlap_auto
class FakeBackground:
 def __init__(self,*a):self.result=None
 def submit(self,meta):self.result=([([0,0,640,360],.9)] if meta['tracks'] else [],meta)
 def poll(self):r=self.result;self.result=None;return r
 def close(self):pass
overlap_auto.Background=FakeBackground

with tempfile.TemporaryDirectory() as tmp:
 m.DATA=Path(tmp);m.DB=Path(tmp)/'tyretrack.db';m.init_db();worker=m.CounterWorker('oak','','Bottom to Top',.35,.5)
 worker.belt_assist=BeltWidthAssist(BeltSettings(observe_only=True));worker.status.connect(statuses.append);worker.run()
 assert not any(s.startswith('ERROR') for s in statuses),statuses
 from overlap_auto import corrections
 auto=corrections(m.DB);assert len(auto)==1,auto
 assert worker.session_count==2,worker.session_count
 with __import__('contextlib').closing(__import__('sqlite3').connect(m.DB)) as c:
  assert c.execute('SELECT COUNT(*) FROM counts').fetchone()[0]==2
 rows=worker.audit.rows(kind='overlap');assert len(rows)==1 and rows[0]['payload']['added_tyres']==1,rows
 print('PASS real OAK worker: one real crossing plus exactly one V7 correction; real DB and evidence record')
