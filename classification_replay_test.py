"""Run real video replay pipeline with simulated model outputs; no production DB."""
import sys,types,tempfile,json
from pathlib import Path
import numpy as np,cv2
from belt_width_assist import BeltWidthAssist
class Tensor:
 def __init__(self,v):self.v=np.asarray(v)
 def cpu(self):return self
 def int(self):return self
 def numpy(self):return self.v
 def tolist(self):return self.v.tolist()
class Model:
 names={0:'passenger',1:'4x4'}
 def __init__(self,*a):self.index=0
 def track(self,*a,**kw):
  cy=232-self.index*3;assist=BeltWidthAssist();l,r=assist.edges(cy,480,270);bw=(r-l)*.76;cx=(l+r)/2
  cls=0 if self.index%5 in [0,1,3] else 1;self.index+=1
  b=types.SimpleNamespace(xyxy=Tensor([[cx-bw/2,cy-bw*.35,cx+bw/2,cy+bw*.35]]),id=Tensor([1]),conf=Tensor([.9]),cls=Tensor([cls]))
  return [types.SimpleNamespace(boxes=b)]
m=types.ModuleType('ultralytics');m.YOLO=Model;sys.modules['ultralytics']=m
import offline_replay
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);video=root/'fixture.mp4';writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),15,(480,270));assert writer.isOpened()
 for i in range(50):writer.write(np.zeros((270,480,3),np.uint8))
 writer.release();out=root/'out'
 assert offline_replay.main(['--video',str(video),'--output',str(out),'--mode','horizontal'])==0
 report=json.loads((out/'test_summary.json').read_text());s=report['classification_comparison']
 assert report['final_unique_total']==1 and not report['production_totals_modified'],report
 assert s['tyres']==1 and s['measured']==1 and s['disagreements']==1,s
 assert s['original_counts']=={'passenger':1} and s['assisted_counts']=={'4x4':1},s
 assert (out/'classification_comparison.csv').exists()
 print('PASS real replay pipeline with simulated inference produces isolated comparison CSV and original/SUV proposal totals, including post-count measurement')
