"""Owner-specified kg/EPU math and actual Qt dashboard labels, no production writes."""
import os,sys,types
from pathlib import Path
from test_resources import DatabaseTemporaryDirectory
from tyre_weight import totals
r=totals({'passenger':10,'4x4':3,'truck':2,'unknown':1})
assert r['weights']=={'passenger':80,'4x4':48,'truck':90}
assert r['total_kg']==218 and r['total_epu']==26 and r['total_count']==16 and r['unknown']==1
assert totals([('SUV',2),('suv / 4x4',3),('TRUCK',1)])['total_kg']==125
assert totals({})['total_kg']==0
assert totals({'truck':1})['total_epu']==5 and totals({'truck':1})['total_kg']==45
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *args:True
qt=QApplication.instance() or QApplication([])
with DatabaseTemporaryDirectory() as tmp:
 m.DATA=Path(tmp);m.DB=Path(tmp)/'test.db';m.init_db();w=m.Main();w.clock.stop();w.show()
 before=m.get_state('celebration_sound')
 w.refresh_weight_totals({'passenger':10,'4x4':3,'truck':2,'unknown':1})
 assert w.passenger_lbl.text()=='10' and w.suv_lbl.text()=='3' and w.truck_lbl.text()=='2'
 assert [w.weight_labels[k].text() for k in ('passenger','4x4','truck')]==['80 kg','48 kg','90 kg']
 assert '218 kg' in w.total_weight_lbl.text() and '26 EPU' in w.total_weight_lbl.text()
 assert '1 unclassified' in w.total_weight_lbl.toolTip()
 for width,height in [(1280,720),(1366,768),(1450,850)]:
  w.resize(width,height)
  for _ in range(5):qt.processEvents()
  for label in [w.total_weight_lbl,*w.weight_labels.values(),w.passenger_lbl,w.suv_lbl,w.truck_lbl]:
   pos=label.mapTo(w.stats_scroll.viewport(),label.rect().topLeft())
   assert pos.y()>=0 and pos.y()+label.height()<=w.stats_scroll.viewport().height(),(width,label.text(),pos.y(),label.height(),w.stats_scroll.viewport().height())
  assert w.video.height()>=360
 w.refresh_weight_totals({'truck':1},test_mode=True)
 assert w.total_weight_lbl.text().startswith('TEST') and '45 kg' in w.total_weight_lbl.text()
 assert m.get_state('celebration_sound')==before
 w.close();qt.processEvents()
print('PASS: passenger 8 kg/1 EPU; SUV 16 kg/2 EPU; truck 45 kg/5 EPU; sum/aliases/unknown exclusions; real count+kg labels visible at 1280,1366,1450; isolated test labels')
