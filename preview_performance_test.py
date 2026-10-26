"""Real OAK graphs and nonblocking PNG writes, without an attached camera."""
import json,hashlib,threading,tempfile,time
from pathlib import Path
import depthai as dai
from PyQt5.QtCore import QCoreApplication,QTimer
from PyQt5.QtGui import QImage,QColor
from preview_output import SnapshotWriter
from oak_rvc2 import build_pipeline
root=Path(__file__).resolve().parent
for foreign in (False,True):
 for recording in (False,True):
  nodes=build_pipeline(dai,root/'rvc2_models',recording,foreign).getAllNodes()
  camera=next(n for n in nodes if isinstance(n,dai.node.ColorCamera))
  assert camera.getPreviewSize()==(480,270) and camera.getVideoSize()==(640,360)
  sizes=[(n.initialConfig.get().resizeConfig.width,n.initialConfig.get().resizeConfig.height) for n in nodes if isinstance(n,dai.node.ImageManip)]
  assert (320,180) not in sizes and sizes.count((384,384))==1
  assert len(sizes)==(2 if foreign else 1)
  if foreign:assert (416,416) in sizes
  assert len([n for n in nodes if isinstance(n,dai.node.NeuralNetwork)])==(2 if foreign else 1)
source=(root/'oak_rvc2.py').read_text().replace('\r\n','\n')
change=json.loads((root/'preview_pipeline_change.json').read_text())
assert source.count(change['new'])==1
original=source.replace(change['new'],change['old']).encode()
assert hashlib.sha256(original).hexdigest()==json.loads((root/'compatibility_baseline.json').read_text())['unchanged_files']['oak_rvc2.py']
# Real graph links for high-quality and original fallback, in all combinations.
import os,numpy as np,cv2
from unittest.mock import patch
from oak_preview import live_size
for safe in ('','1'):
 with patch.dict(os.environ,{'TYRETRACK_SAFE_PREVIEW':safe}):
  assert live_size()==((480,270) if safe else (640,360))
  for foreign in (False,True):
   for recording in (False,True):
    p=build_pipeline(dai,root/'rvc2_models',recording,foreign)
    nodes=p.getAllNodes();camera=next(n for n in nodes if isinstance(n,dai.node.ColorCamera))
    live=next(n for n in nodes if isinstance(n,dai.node.XLinkOut) and n.getStreamName()=='live')
    links=[c for cs in p.getConnectionMap().values() for c in cs]
    link=next(c for c in links if c.inputId==live.id)
    assert link.outputId==camera.id and link.outputName==('preview' if safe else 'video')
    assert not live.input.getBlocking() and live.input.getQueueSize()==1
    manips=[n for n in nodes if isinstance(n,dai.node.ImageManip)]
    assert len(manips)==(2 if foreign else 1)
    assert all(next(c for c in links if c.inputId==n.id).outputName=='preview' for n in manips)
    encs=[n for n in nodes if isinstance(n,dai.node.VideoEncoder)]
    if recording:assert next(c for c in links if c.inputId==encs[0].id).outputName=='video'
# Actual DepthAI NV12 conversion, including BGR channel order.
h,w=360,640
image=np.zeros((h,w,3),np.uint8);image[:,:w//2]=(0,0,255);image[:,w//2:]=(255,0,0)
yuv=cv2.cvtColor(image,cv2.COLOR_BGR2YUV_I420).reshape(-1)
y=yuv[:h*w];u=yuv[h*w:h*w+h*w//4];v=yuv[h*w+h*w//4:]
uv=np.empty(h*w//2,np.uint8);uv[0::2]=u;uv[1::2]=v
packet=dai.ImgFrame();packet.setWidth(w);packet.setHeight(h);packet.setType(dai.ImgFrame.Type.NV12);packet.setData(np.concatenate((y,uv)))
bgr=packet.getCvFrame();assert bgr.shape==(h,w,3)
assert bgr[100,100,2]>240 and bgr[100,500,0]>240
assert w*h*3//2 < 480*270*3 # Raw NV12 live bytes, not total network traffic.
qt=QCoreApplication.instance() or QCoreApplication([])
entered=threading.Event();release=threading.Event();threads=[]
class SlowImage:
 def __init__(self,image,slow=False):self.image=image;self.slow=slow
 def copy(self):return SlowImage(self.image.copy(),self.slow)
 def save(self,path,fmt):
  threads.append(threading.get_ident())
  if self.slow:entered.set();assert release.wait(3)
  return self.image.save(path,fmt)
with tempfile.TemporaryDirectory() as tmp:
 path=Path(tmp)/'dashboard.png';errors=[];writer=SnapshotWriter(path,errors.append)
 im=QImage(320,180,QImage.Format_RGB32);im.fill(QColor('red'))
 start=time.monotonic();writer.request(SlowImage(im,True));assert time.monotonic()-start<.2
 assert entered.wait(2);fired=[];QTimer.singleShot(0,lambda:fired.append(True));qt.processEvents();assert fired
 assert not path.exists()
 im.fill(QColor('green'))
 for _ in range(20):writer.request(SlowImage(im))
 release.set();assert writer.wait(3)
 assert not errors and len(threads)==2 and all(t!=threading.get_ident() for t in threads)
 assert QImage(str(path)).pixelColor(0,0).green()>100
 assert not path.with_name(path.name+'.tmp').exists()
main=(root/'TyreTrack_Production_Monitor.py').read_text()
assert 'OAK_PREVIEW_INTERVAL_MS = 67' in main and 'setTimerType(Qt.PreciseTimer)' in main
assert 'self.grab().save(' not in main
print('PASS: four real OAK graphs; eight real direct-video/fallback graphs; real NV12 colour conversion; AI and recording preserved; reverse-patch baseline hash; responsive Qt timer during blocked PNG encoding; coalesced atomic output')
