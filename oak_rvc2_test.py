"""Detection-only blob/pipeline/geometry/decoder/tracker and alarm tests."""
from pathlib import Path
import numpy as np,depthai as dai
from oak_rvc2 import validate_models,build_pipeline,decode,unletterbox,OakTracker,read_layers
ROOT=Path(__file__).parent/'rvc2_models'
assert validate_models(dai,ROOT)
for foreign in (False,True):
 for recording in (False,True):
  p=build_pipeline(dai,ROOT,recording,foreign)
  camera=next(n for n in p.getAllNodes() if isinstance(n,dai.node.ColorCamera))
  assert camera.getIspSize()==camera.getVideoSize()==(640,360)
  assert camera.getPreviewSize()==(480,270)
  networks=[n for n in p.getAllNodes() if isinstance(n,dai.node.NeuralNetwork)]
  assert len(networks)==(2 if foreign else 1)
def foreign_raw(cx=208,cy=208,w=80,h=80,score=.95):
 out=np.zeros((1,8,3549),np.float32)
 out[0,:,0]=[cx,cy,w,h,score,0,0,0]
 return {'output0':out}
rows,masks=decode(foreign_raw())
assert rows.shape==(1,6) and masks is None and int(rows[0,5])==0
np.testing.assert_allclose(rows[0,:4],[168*480/416,(168-91)*270/234,248*480/416,(248-91)*270/234],rtol=1e-5)
raw=foreign_raw();raw['output0'][0,:,1]=[210,208,80,80,.8,0,0,0]
assert len(decode(raw)[0])==1
assert len(decode(raw,agnostic=True)[0])==1
other=foreign_raw();other['output0'][0,4:,0]=[0,0,.96,0]
assert int(decode(other)[0][0,5])==2
normal=foreign_raw()
normal['output0'][0,4:,0]=[.90,0,0,.99]
assert len(decode(normal,.70)[0])==0
normal['output0'][0,:,1]=[208,208,80,80,0,0,.85,0]
assert int(decode(normal,.70)[0][0,5])==2
assert len(decode(foreign_raw(cy=20))[0])==0
bad={'output0':np.zeros(17,np.float32)}
try:decode(bad);raise AssertionError('Bad YOLOv8 head accepted')
except ValueError:pass
from foreign_alarm import ForeignPresence
presence=ForeignPresence(hits=3,clear_after=3.0)
det=dict(class_id=0,class_name='foreign_object',box=rows[0,:4].tolist(),confidence=.95)
events=[]
for t in (0,.2,.4):
 new,active=presence.update([det],t);events.extend(new)
assert len(events)==1 and events[0]['class_name']=='foreign_object' and len(active)==1
new,active=presence.update([],4.0)
assert not active
# Distinct channel colors check RGB tyre and RGB foreign preprocessing.
a=np.zeros((384,384,3),np.uint8);a[84:300,:,0]=255
frame=unletterbox(a);assert frame.shape==(270,480,3) and np.all(frame[:,:,2]==255) and not frame[:,:,0].any()
b=np.zeros((416,416,3),np.uint8);b[91:325,:,0]=255
f=unletterbox(b,'foreign');assert np.all(f[:,:,2]==255) and not f[:,:,0].any()
tracker=OakTracker();ids=[]
for y in range(250,110,-10):
 r=np.zeros((6,3024),np.float32);r[:,0]=[192,y,80,60,.95,.01]
 result=tracker.track_oak(frame,r.ravel(),.35,.5,False)
 assert result.boxes.id is not None and result.masks is None
 ids.append(int(result.boxes.id[0]))
assert len(set(ids))==1
from foreign_alarm import CLASSES
assert CLASSES==('wheel_rim','person')
print('PASS: detection-only compiled contracts; four pipeline combinations; 384 RGB tyre/416 RGB foreign; YOLOv8 4-class decoding, NMS, no masks, ByteTrack continuity and auto-clear presence tracking')
