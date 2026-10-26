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
  assert sizes.count((320,180))==1 and (384,384) in sizes
  if foreign:assert (416,416) in sizes
  assert len([n for n in nodes if isinstance(n,dai.node.NeuralNetwork)])==(2 if foreign else 1)
source=(root/'oak_rvc2.py').read_text();patch=json.loads((root/'preview_pipeline_change.json').read_text())
assert source.count(patch['new'])==1
original=source.replace(patch['new'],patch['old']).replace('\r\n','\n').encode()
assert hashlib.sha256(original).hexdigest()==json.loads((root/'compatibility_baseline.json').read_text())['unchanged_files']['oak_rvc2.py']
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
print('PASS: four real OAK graphs; only live branch 320x180; original AI and recording preserved; reverse-patch hash; responsive Qt timer during blocked PNG encoding; coalesced atomic output')
