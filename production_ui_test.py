"""Truck dashboard layout, live data bindings and control access without hardware."""
from test_resources import DatabaseTemporaryDirectory
import os,sys,types
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication,QPushButton
import TyreTrack_Production_Monitor as m
from truck_dashboard import sync
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *a:True
app=QApplication([])
with DatabaseTemporaryDirectory() as folder:
 m.DB=Path(folder)/'test.db';m.init_db();w=m.Main();w.clock.stop();w.show()
 assert w.truck_dashboard_ready and not w.foreign_switch.isChecked()
 assert not w.controls_tabs.isVisible()
 assert w.line_mode.currentData()=='zigzag'
 assert len(w.dashboard_hour_blocks)==13
 for width,height in ((1450,850),(1366,768),(1280,720)):
  w.resize(width,height)
  for _ in range(5):app.processEvents()
  w.hour_lbl.setText(m.tyre_total_text(527));w.session_lbl.setText(m.tyre_total_text(671))
  w.day_lbl.setText(m.tyre_total_text(6026));w.best_daily_lbl.setText('6,026 tyres')
  w.passenger_lbl.setText('5181');w.suv_lbl.setText('845');w.flow_lbl.setText('8.8')
  w.record_progress.setText("145 tyres to beat today's best hour");sync(w)
  assert w.width()==width and w.height()==height,(w.size(),width,height)
  assert w.flow_instrument.rate==8.8 and w.best_instrument.best==671 and w.best_instrument.current==527
  assert w.hour_target_bar.value()==round(527/671*1000)
  assert w.video.width()>=220 and w.video.height()>=112,(w.video.size())
  assert w.current_hour_card.width()>w.flow_instrument.width()
  assert w.hourly_strip.mapTo(w,w.hourly_strip.rect().bottomRight()).y()<height
  for control in w.findChildren(QPushButton):
   if control.isVisible() and control.window() is w:
    at=control.mapTo(w,control.rect().topLeft());assert at.x()>=0 and at.x()+control.width()<=width,(control.text(),at,width)
  w.grab().save(str(Path(__file__).with_name(f'truck_dashboard_{width}.png')))
 before=w.flow_instrument.static_renders
 for i in range(20):w.flow_instrument.set_values(i/10,527,671)
 app.processEvents();assert w.flow_instrument.static_renders==before
 w._truck_show_admin();app.processEvents();assert w.controls_tabs.isVisible()
 for index in range(w.controls_tabs.count()):
  w.controls_tabs.setCurrentIndex(index);app.processEvents()
  scroll=w.controls_tabs.widget(index);assert scroll.widget().width()<=scroll.viewport().width()
 w.truck_admin_dialog.reject();w._truck_show_admin();app.processEvents();assert w.controls_tabs.isVisible()
 w.truck_admin_dialog.hide()
 w.edit_bounds_btn.setChecked(True);app.processEvents()
 assert w.truck_line_dialog.isVisible() and w.video.window() is w.truck_line_dialog
 w.edit_bounds_btn.setChecked(False);app.processEvents()
 assert w.video.parent() is w.camera_panel
 w.close()
print('PASS: three responsive truck dashboard sizes, numeric bindings, cached gauge faces, admin reopen, line editor and all hourly blocks')
