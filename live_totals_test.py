"""Committed counters remain responsive while historical dashboard work is blocked."""
import os,sys,types,time,threading,sqlite3,tempfile
from pathlib import Path
from datetime import datetime,timedelta
from live_totals import snapshot
from hourly_dashboard import BRISBANE
from contextlib import closing
now=datetime(2026,10,28,10,30,tzinfo=BRISBANE)
with tempfile.TemporaryDirectory() as folder:
 db=Path(folder)/'counts.db'
 with closing(sqlite3.connect(db)) as con:
  con.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT,tyre_type TEXT)')
  for hour,kind,source,legacy in [(6,'passenger','oak',False),(10,'SUV','oak',True),(10,'truck','video',False),(4,'truck','oak',False)]:
   t=now.replace(hour=hour,minute=29);con.execute('INSERT INTO counts VALUES(?,?,?,?)',(t.replace(tzinfo=None).isoformat(),None if legacy else t.timestamp(),source,kind))
  con.commit()
 r=snapshot(db,'oak',now);assert (r['daily'],r['current_hour'],r['all_time'])==(2,1,3),r
 assert snapshot(db,'oak',now.replace(hour=4))['daily']==0
 assert snapshot(db,'oak',now.replace(hour=18))['current_hour']==0
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import TyreTrack_Production_Monitor as m
from test_resources import DatabaseTemporaryDirectory
from background_export import CoalescedExport
m.Main.tick=lambda self:None
m.Main._confirm_admin_pin=lambda *a:True
qt=QApplication.instance() or QApplication([])
with DatabaseTemporaryDirectory() as folder:
 m.DATA=Path(folder);m.DB=m.DATA/'test.db';m.init_db();w=m.Main();w.clock.stop()
 m.brisbane_now=lambda:now
 gate=threading.Event();entered=threading.Event()
 def slow():entered.set();gate.wait(5)
 w._dashboard_loader=CoalescedExport(slow,lambda e:None);w._dashboard_loader.request();assert entered.wait(1)
 try:
  m.log_count(m.OAK_NAME,1,.9,'passenger',.9)
  with closing(sqlite3.connect(m.DB)) as con:
   con.execute('UPDATE counts SET metric_utc=?',((now-timedelta(seconds=1)).timestamp(),));con.commit()
  w.request_live_totals();heartbeat=[];QTimer.singleShot(0,lambda:heartbeat.append(True))
  deadline=time.monotonic()+2
  while getattr(w,'_live_totals',{}).get('all_time')!=1 and time.monotonic()<deadline:qt.processEvents();time.sleep(.005)
  assert heartbeat and w._live_totals['all_time']==1
  assert '8 kg' in w.total_weight_lbl.text()
  # A stale historical refresh cannot replace committed headline values.
  w.day_lbl.setText('old');w.apply_live_totals();assert '1' in w.day_lbl.text()
  worker=types.SimpleNamespace(source_kind='video',manual_test=False)
  w.worker=worker;w.day_lbl.setText('TEST');w.apply_live_totals();assert w.day_lbl.text()=='TEST';w.worker=None
 finally:gate.set();w._dashboard_loader.wait();w.close();qt.processEvents()
print('PASS: fast committed totals, legacy classes, shift boundaries, GUI heartbeat during blocked historical collection, stale-cache protection and video isolation')
