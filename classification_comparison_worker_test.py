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
  box,cls=raw;b=types.SimpleNamespace(xyxy=Tensor([box]),id=Tensor([1]),conf=Tensor([.9]),cls=Tensor([cls]))
  return types.SimpleNamespace(boxes=b)
oak_rvc2.OakTracker=Tracker
ys=list(range(310,110,-4));statuses=[];counts=[]
class Source:
 def __init__(self,*a,**k):self.index=0;self.last_read_frame_at=time.monotonic();self.recording_path='sample_recording.mp4'
 def read(self):
  if self.index==len(ys):worker.running=False;return False,None,None
  cy=ys[self.index];left,right=worker.belt_assist.edges(cy,640,360);bw=(right-left)*.76;cx=(left+right)/2
  self.last_read_neural_output=((cx-bw/2,cy-bw*.35,cx+bw/2,cy+bw*.35),0 if self.index%5 in [0,1,3] else 1)
  self.index+=1;return True,np.zeros((360,640,3),np.uint8),self.index
 def release(self):pass
m.OakSource=Source;m.oak_in_operating_hours=lambda:True;m.log_count=lambda *a:counts.append(a)
with tempfile.TemporaryDirectory() as tmp:
 m.DATA=Path(tmp);worker=m.CounterWorker('oak','','Bottom to Top',.35,.5)
 worker.belt_assist=BeltWidthAssist(BeltSettings(observe_only=True));worker.status.connect(statuses.append);worker.run()
 assert not any(s.startswith('ERROR') for s in statuses),statuses
 assert len(counts)==1 and worker.session_count==1,(counts,statuses)
 rows=worker.audit.rows();assert len(rows)==1,rows
 p=rows[0]['payload'];assert p['original_class']=='passenger' and p['final_class']=='passenger',p
 assert p['diameter_mm'] and abs(p['diameter_mm']-(.76*1180))<5,p
 assert p['size_candidate']=='4x4' and p['assisted_class']=='4x4' and p['disagreement'],p
 assert p['measurement_frame']>p['frame_sequence'],p
 print('PASS real OAK worker simulated inference: one production count, later stable measurement attached once, original preserved, SUV proposal recorded in Compare only')
