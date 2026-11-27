"""Real admin view and field review; no camera, model stub and no count changes."""
import os,sys,types,time
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
import numpy as np
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel,QDialog,QTableWidget,QComboBox,QLineEdit,QPushButton
from candidate_trial import Store
from candidate_trial_ui import CandidatePanel,open_candidate_review
from test_resources import DatabaseTemporaryDirectory
app=QApplication.instance() or QApplication([])
host=QWidget();layout=QVBoxLayout(host);panel=CandidatePanel(lambda:None);layout.addWidget(panel);host.show()
summary=dict(records=1234,production_counts={'passenger':1000,'4x4':234},candidate_counts={'passenger':990,'4x4':230,'unknown':14},accepted=1220,unknown=14,disagreements=20)
panel.show_result(summary)
for style in ['Fusion','Windows']:
 app.setStyle(style)
 for width in [360,640,880]:
  host.resize(width,300)
  for _ in range(5):app.processEvents()
  for label in panel.findChildren(QLabel):
   at=label.mapTo(panel,label.rect().topLeft())
   assert at.x()>=0 and at.x()+label.width()<=panel.width(),(width,label.text())
   assert at.y()>=0 and at.y()+label.height()<=panel.height(),(width,label.text())
panel.show_result({'error':'database busy'});assert all(v.text()=='—' for v in panel.recorded.values())
panel.show_result(summary);assert panel.candidate['4x4'].text()=='230';host.close()

with DatabaseTemporaryDirectory() as tmp:
 root=Path(tmp);store=Store(root/'candidate_trial');day='2026-11-27'
 payload=dict(timestamp=day+'T09:00:00+10:00',scope='production',session_id='fixture',track_id=1,original_class='passenger',final_class='passenger')
 store.save(payload,dict(candidate_class='4x4',raw_class='4x4',confidence=.95,reason=''),np.zeros((80,120,3),np.uint8))
 # Date and table are selected through actual Qt controls.
 state={'done':False,'error':None};deadline=time.monotonic()+10
 def step():
  dialog=app.activeModalWidget()
  try:
   assert time.monotonic()<deadline,'Candidate review timed out'
   if not isinstance(dialog,QDialog):QTimer.singleShot(30,step);return
   from PyQt5.QtWidgets import QDateEdit
   from PyQt5.QtCore import QDate
   dialog.findChild(QDateEdit).setDate(QDate(2026,11,27))
   table=dialog.findChild(QTableWidget);assert table.rowCount()==1
   table.selectRow(0);combo=dialog.findChild(QComboBox);combo.setCurrentIndex(combo.findData('passenger'))
   fields=dialog.findChildren(QLineEdit)
   next(f for f in fields if f.placeholderText()=='Reviewer name').setText('Greg')
   next(f for f in fields if f.placeholderText().startswith('Evidence /')).setText('Known vehicle origin')
   next(b for b in dialog.findChildren(QPushButton) if b.text()=='Save actual-class review').click()
   assert store.rows(day)[0]['human_label']=='passenger';state['done']=True;dialog.accept()
  except Exception as exc:
   state['error']=exc
   if isinstance(dialog,QDialog):dialog.reject()
 QTimer.singleShot(30,step);open_candidate_review(None,store.root)
 assert state['done'] and state['error'] is None,state

stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *a:True
with DatabaseTemporaryDirectory() as tmp:
 root=Path(tmp);m.DATA=root/'data';m.DATA.mkdir();m.DB=m.DATA/'counts.db';m.REPORTS=root/'reports';m.REPORTS.mkdir();m.init_db()
 day=m.brisbane_now().date().isoformat();store=Store(m.DATA/'candidate_trial')
 store.save(dict(payload,timestamp=day+'T09:00:00+10:00'),dict(candidate_class='4x4',raw_class='4x4',confidence=.95,reason=''))
 w=m.Main();w.clock.stop();w.show()
 assert not w.candidate_panel.isVisible() and not w.counters_panel.isAncestorOf(w.candidate_panel)
 assert w.candidate_observe_checkbox.isChecked() and w.belt_mode.currentData()=='compare'
 assert w.overlap_auto_checkbox.isChecked()
 w.refresh_comparison_dashboard();deadline=time.monotonic()+5
 while w.candidate_panel.candidate['4x4'].text()!='1' and time.monotonic()<deadline:app.processEvents();time.sleep(.01)
 assert w.candidate_panel.recorded['passenger'].text()=='1' and w.candidate_panel.candidate['4x4'].text()=='1'
 next(b for b in w.findChildren(QPushButton) if b.text()=='Admin Settings').click();w.controls_tabs.setCurrentWidget(w.review_admin_page)
 for _ in range(5):app.processEvents()
 w.review_admin_page.ensureWidgetVisible(w.candidate_panel.button,0,0)
 for _ in range(5):app.processEvents()
 assert w.candidate_panel.isVisible() and not w.candidate_panel.button.visibleRegion().isEmpty()
 transport=w.test_transport.text();w.on_review_status('CANDIDATE OBSERVE-ONLY: fixture');assert w.test_transport.text()==transport
 w.candidate_observe_checkbox.setChecked(False);assert m.get_state('candidate_observe_enabled')=='0'
 assert w.overlap_auto_checkbox.isChecked() and w.belt_mode.currentData()=='compare'
 assert m.production_snapshot()['all_time']==0
 w.close();app.processEvents()
print('PASS candidate panel geometry, real actual-class review, admin-only async comparisons, persisted off, retained belt/overlap settings, unchanged production totals and clean shutdown')
