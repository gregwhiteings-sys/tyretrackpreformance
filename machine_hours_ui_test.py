import os,tempfile,sqlite3,time
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from contextlib import closing
from PyQt5.QtCore import QTimer,QDate
from PyQt5.QtWidgets import QApplication,QDialog,QDateEdit,QDoubleSpinBox,QCheckBox,QPushButton,QWidget,QVBoxLayout,QLabel
from machine_hours_ui import HoursPanel,open_hours
from machine_hours import HoursStore
app=QApplication.instance() or QApplication([])
host=QWidget();layout=QVBoxLayout(host);panel=HoursPanel(lambda:None);layout.addWidget(panel);host.resize(720,111);host.show()
panel.show_result({'day':'2026-11-26','hours':9.7,'tyres':970,'rate':100,'status':'Recorded tyres / actual running hours'})
assert panel.values['hours'].text()=='9.7 h' and panel.values['rate'].text()=='100.0'
for width in [640,720,880]:
 host.resize(width,111)
 for _ in range(5):app.processEvents()
 for label in panel.findChildren(QLabel):
  at=label.mapTo(panel,label.rect().topLeft());assert at.x()>=0 and at.x()+label.width()<=panel.width()
  assert at.y()>=0 and at.y()+label.height()<=panel.height(),(width,label.text(),at.y(),label.height())
panel.show_result({'status':'Reading pending'});assert all(v.text()=='—' for v in panel.values.values())
host.close()
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);db=root/'counts.db';store=HoursStore(root/'hours')
 with closing(sqlite3.connect(db)) as c:
  c.execute('CREATE TABLE counts(ts TEXT,source TEXT,metric_utc REAL)');c.execute("INSERT INTO counts VALUES('2026-11-26T08:00:00+10:00','oak',NULL)");c.commit()
 state={'phase':0,'error':None};deadline=time.monotonic()+15
 def step():
  dialog=app.activeModalWidget()
  try:
   assert time.monotonic()<deadline,'Entry dialog timed out'
   if not isinstance(dialog,QDialog):QTimer.singleShot(30,step);return
   date=dialog.findChild(QDateEdit);value=dialog.findChild(QDoubleSpinBox,'closingMeter');check=dialog.findChild(QCheckBox,'checkedReading')
   if state['phase']==0:
    date.setDate(QDate(2026,11,25));value.setValue(1000.0);check.setChecked(True)
    next(b for b in dialog.findChildren(QPushButton) if b.text()=='Save shift reading').click();state['phase']=1
   elif state['phase']==1:
    assert store.rows()[0]['meter']==1000.0
    date.setDate(QDate(2026,11,26));value.setValue(1009.7);check.setChecked(True)
    next(b for b in dialog.findChildren(QPushButton) if b.text()=='Save shift reading').click();state['phase']=2
   else:
    assert len(store.rows())==2 and store.rows()[0]['checked']==1
    with closing(sqlite3.connect(db)) as c:assert c.execute('SELECT count(*) FROM counts').fetchone()[0]==1
    dialog.accept();return
   QTimer.singleShot(30,step)
  except Exception as exc:
   state['error']=exc
   if isinstance(dialog,QDialog):dialog.reject()
 QTimer.singleShot(30,step);open_hours(None,store.root,db,'oak');assert state['error'] is None,state['error'];assert state['phase']==2
print('PASS equal machine metrics at 3 widths, pending-state clearing, real shift-end entry for two dates and zero production writes')
import sys,types
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
import TyreTrack_Production_Monitor as m
from test_resources import DatabaseTemporaryDirectory
from hourly_dashboard import BRISBANE
from datetime import datetime
m.Main.tick=lambda self:None
m.Main._confirm_admin_pin=lambda *args:True
with DatabaseTemporaryDirectory() as tmp:
    root=Path(tmp);m.DATA=root/'data';m.DATA.mkdir();m.DB=m.DATA/'counts.db';m.REPORTS=root/'reports';m.REPORTS.mkdir();m.init_db()
    clock=datetime(2026,11,26,18,tzinfo=BRISBANE)
    m.brisbane_now=lambda:clock
    data=HoursStore(m.DATA/'machine_hours');data.save('2026-11-25',1000,now=clock);data.save('2026-11-26',1009.7,now=clock)
    # Core reader uses its own clock. All fixture dates are completed shifts.
    with closing(sqlite3.connect(m.DB)) as c:
        c.execute('INSERT INTO counts(ts,source,track_id,confidence,tyre_type,class_confidence,metric_utc) VALUES(?,?,?,?,?,?,?)',
            ('2026-11-26T05:00:00+10:00',m.OAK_NAME,1,.9,'passenger',.9,datetime(2026,11,26,5,tzinfo=BRISBANE).timestamp()));c.commit()
    w=m.Main();w.clock.stop();w.refresh_comparison_dashboard();deadline=time.monotonic()+10
    while w.machine_hours_panel.values['hours'].text()!='9.7 h' and time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
    assert w.machine_hours_panel.values['hours'].text()=='9.7 h'
    assert w.machine_hours_panel.values['tyres'].text()=='1'
    w.close();app.processEvents()
print('PASS actual dashboard async reading without classification records, matching primary production source, and clean reader shutdown')
