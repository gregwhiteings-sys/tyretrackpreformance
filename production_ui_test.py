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
for label,value in ((w.day_lbl,6026),(w.hour_lbl,227),(w.session_lbl,671)):
 label.setText(m.tyre_total_text(value))
 assert 'tyres' in label.text()
w.passenger_lbl.setText('5181');w.suv_lbl.setText('845')
w.record_progress.setText("445 tyres to beat today's best hour")
assert '36px' in w.passenger_lbl.styleSheet() and '36px' in w.suv_lbl.styleSheet()
assert w.line_angle.value()==0 and w.line_length.value()==100
for width,height in ((1450,850),(1366,768),(1280,720)):
 w.resize(width,height)
 for _ in range(5):app.processEvents()
 for label,value in ((w.day_lbl,6026),(w.hour_lbl,227),(w.session_lbl,671)):
  label.setText(m.tyre_total_text(value))
 w.passenger_lbl.setText('5181');w.suv_lbl.setText('845')
 w.record_progress.setText("445 tyres to beat today's best hour")
 assert w.width()==width,(w.width(),width)
 assert len(w.dashboard_hour_blocks)==13 and w.hourly_strip.isVisible()
 assert w.hourly_strip.mapTo(w,w.hourly_strip.rect().bottomRight()).y()<w.height()
 assert "18px" in w.current_hour_card.findChild(m.QLabel,"metricName").styleSheet()
 assert w.counters_panel.width()>w.video.width(),(w.counters_panel.width(),w.video.width())
 assert w.video.width()>=320 and w.video.height()>=360
 for control in w.findChildren(QPushButton):
  if control.isVisible():
   at=control.mapTo(w,control.rect().topLeft());assert at.x()>=0 and at.x()+control.width()<=w.width()
 w.grab().save(str(root/f'experiment_dashboard_{width}.png'))
assert not hasattr(w.record_progress, '_motion')
w.record_progress.setText("Fixed message")
assert w.record_progress.toolTip()=="Fixed message"
w.set_flow_rate(4.9);assert '#FF5C68' in w.flow_lbl.styleSheet()
w.set_flow_rate(5);assert not w.flow_lbl.styleSheet()
assert not hasattr(w, 'flow_flash_timer')
assert w.oak_view_combo.currentText() == 'Smooth'
assert not w.show_tyre_labels.isChecked()
assert not hasattr(w, 'target_button')
assert len(w.projection_labels)==3
assert 'PROJECTED THIS MONTH' in w.forecast_label.text()
assert '900 20px' in w.forecast_label.styleSheet()
print('PASS: stationary accessible message, steady low-flow threshold, monthly projection and smooth unlabelled defaults')
print('PASS: actual Qt operator dashboard at 1450,1366,1280; OAK only, foreign off, hidden fixed lines')
next(button for button in w.findChildren(QPushButton) if button.text()=="Admin Settings").click();app.processEvents()
assert w.controls_tabs.isVisible() and not w.stats_scroll.isVisible()
for index in range(w.controls_tabs.count()):
 w.controls_tabs.setCurrentIndex(index)
 for _ in range(3):app.processEvents()
 scroll=w.controls_tabs.widget(index);host=scroll.widget()
 assert host.width()==scroll.viewport().width()
print('PASS: administration pages fit scroll viewport')

# Exercise actual health label wiring without camera, files or background requests.
from types import SimpleNamespace
import time
class SupportFixture:
 def request(self,*args,**kwargs):pass
 def snapshot(self):return dict(app_cpu=12,free_gb=5,processing_fps=8,backup='Saved fixture',last_backup='2026-11-02',error='')
w._support=SupportFixture()
saved_worker=w.worker
w.worker=SimpleNamespace(source_kind='oak',manual_test=False,processing_frame=20,isRunning=lambda:True,oak_source=SimpleNamespace(live_frame_at=time.monotonic(),latest_frame_at=time.monotonic(),recorder=SimpleNamespace(is_alive=lambda:True)))
w.update_system_support()
assert 'CAMERA ONLINE' in w.system_health_label.text() and 'LOW SPACE' in w.system_health_label.text()
assert 'Processing 8.0 FPS' in w.system_health_label.text()
assert 'Last successful' in w.backup_status.text()
w.worker=saved_worker
print('PASS actual system-health CPU/FPS/disk and backup status labels')

del w._support
w.close();shutil.rmtree(folder,ignore_errors=True)
