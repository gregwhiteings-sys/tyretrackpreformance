"""Real Qt layout and operator controls; camera and inference are not started."""
import os,sys,types,tempfile,shutil
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication,QPushButton
root=Path(__file__).resolve().parent
folder=Path(tempfile.mkdtemp(prefix='oak_experiment_ui_'))
for path in root.glob('*.py'):shutil.copy2(path,folder/path.name)
sys.path.insert(0,str(folder))
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None
m.Main._confirm_admin_pin=lambda self,action:True
app=QApplication([]);w=m.Main();w.show()
assert not w.controls_tabs.isVisible()
assert not w.foreign_switch.isChecked()
assert w.source_combo.count()==1 and w.selected_source()==('oak','')
assert not w.browse_btn.isVisible() and not w.manual_oak_test.isVisible()
assert not w.show_fixed_lines.isChecked()
assert w.line_mode.currentData()=='zigzag' and not w.middle_control.isEnabled()
w.line_mode.setCurrentIndex(w.line_mode.findData('horizontal'))
assert w.middle_control.isEnabled()
w.line_mode.setCurrentIndex(w.line_mode.findData('zigzag'))
assert w.line_angle.value()==0 and w.line_length.value()==100
for width,height in ((1450,850),(1366,768),(1280,720)):
 w.resize(width,height)
 for _ in range(5):app.processEvents()
 assert w.width()==width,(w.width(),width)
 assert w.counters_panel.width()>w.video.width(),(w.counters_panel.width(),w.video.width())
 for control in w.findChildren(QPushButton):
  if control.isVisible():
   at=control.mapTo(w,control.rect().topLeft());assert at.x()>=0 and at.x()+control.width()<=w.width()
 w.grab().save(str(root/f'experiment_dashboard_{width}.png'))
print('PASS: actual Qt operator dashboard at 1450,1366,1280; OAK only, foreign off, hidden fixed lines')
w.controls_tabs.show();app.processEvents()
for index in range(w.controls_tabs.count()):
 w.controls_tabs.setCurrentIndex(index)
 for _ in range(3):app.processEvents()
 scroll=w.controls_tabs.widget(index);host=scroll.widget()
 assert host.width()==scroll.viewport().width()
print('PASS: administration pages fit scroll viewport')
w.close();shutil.rmtree(folder,ignore_errors=True)
