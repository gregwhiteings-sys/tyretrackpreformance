import os,sys,types,tempfile,shutil
from pathlib import Path
from test_resources import DatabaseTemporaryDirectory
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication,QLabel
root=Path(__file__).resolve().parent
with DatabaseTemporaryDirectory() as tmp:
 folder=Path(tmp)
 for p in root.glob('*.py'):shutil.copy2(p,folder/p.name)
 shutil.copy2(root/'tyrecycle_logo.png',folder/'tyrecycle_logo.png')
 sys.path.insert(0,str(folder))
 import TyreTrack_Production_Monitor as m
 m.Main.tick=lambda self:None
 m.Main._confirm_admin_pin=lambda *args:True
 app=QApplication([]);w=m.Main();w.clock.stop();w.show()
 for width,height in ((1280,720),(1366,768)):
  w.resize(width,height)
  for _ in range(5):app.processEvents()
  logo=w.findChild(QLabel,'tyrecycleLogo');assert logo is not None
  assert not logo.pixmap().isNull() and logo.pixmap().width()>=220
  assert w.width()==width and w.height()==height,(w.width(),w.height())
  assert w.hourly_strip.mapTo(w,w.hourly_strip.rect().bottomRight()).y()<height
  w.grab().save(str(root/f'logo_dashboard_{width}.png'))
 w.close()
print('PASS supplied logo displays at 1280x720 and 1366x768; hourly totals remain visible')
