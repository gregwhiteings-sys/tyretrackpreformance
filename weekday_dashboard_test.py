"""Real week boundaries, production-only history and Qt daily-strip layout."""
import os,sys,sqlite3,time,types
from datetime import datetime,timedelta,timezone
from pathlib import Path
from contextlib import closing
from weekly_dashboard import weekday_snapshot
from hourly_dashboard import BRISBANE
now=datetime(2026,10,28,10,tzinfo=BRISBANE) # Wednesday
with closing(sqlite3.connect(':memory:')) as con:
 con.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT)')
 def add(day,hour,minute=0,legacy=False,source='oak',aware=False):
  t=now.replace(day=day,hour=hour,minute=minute)
  stamp=t.astimezone(timezone.utc).isoformat() if aware else t.replace(tzinfo=None).isoformat(sep=' ' if legacy else 'T')
  con.execute('INSERT INTO counts VALUES(?,?,?)',(stamp,None if legacy or aware else t.timestamp(),source))
 add(26,5);add(26,17,4,legacy=True);add(27,6);add(27,8,aware=True);add(27,8,source='video');add(28,9)
 add(26,4,59);add(26,17,5);add(25,9);add(29,9);add(28,11);add(19,6)
 con.execute("INSERT INTO counts VALUES('broken',NULL,'oak')")
 days=weekday_snapshot(con,'oak',now)
 assert [d['count'] for d in days]==[2,2,1,0,0],days
 assert [d['date'].isoformat() for d in days]==['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30']
 assert days[2]['current'] and not days[2]['completed'] and days[3]['future']
 weekend=weekday_snapshot(con,'oak',now.replace(day=31))
 assert all(d['completed'] and not d['current'] for d in weekend)
 rollover=weekday_snapshot(con,'oak',datetime(2026,11,2,6,tzinfo=BRISBANE))
 assert rollover[0]['date'].isoformat()=='2026-11-02' and not any(d['count'] for d in rollover)
 utc=now.astimezone(timezone.utc)
 assert weekday_snapshot(con,'oak',utc)==days
 print('PASS: Brisbane Monday-Friday, week rollover/weekend, legacy timestamps, current-day cutoff, source and shift exclusion')
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
from test_resources import DatabaseTemporaryDirectory
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *args:True
m.brisbane_now=lambda:now
qt=QApplication.instance() or QApplication([])
with DatabaseTemporaryDirectory() as folder:
 m.DATA=Path(folder);m.DB=Path(folder)/'test.db';m.init_db()
 with closing(sqlite3.connect(m.DB)) as con:
  for day,count in [(26,5),(27,3),(28,2)]:
   for index in range(count):
    t=now.replace(day=day,hour=6,minute=index)
    con.execute('INSERT INTO counts(ts,metric_utc,source,tyre_type) VALUES(?,?,?,?)',(t.isoformat(),t.timestamp(),m.OAK_NAME,'passenger'))
  con.commit()
 w=m.Main();w.clock.stop();w.celebration_mute.setChecked(True);w.show()
 try:
  deadline=time.monotonic()+4
  while w._dashboard_cache is None and time.monotonic()<deadline:qt.processEvents();time.sleep(.005)
  assert w._dashboard_cache is not None
  assert [d['count'] for d in w._dashboard_cache['weekdays']]==[5,3,2,0,0]
  assert len(w.dashboard_day_blocks)==5 and '26 Oct–30 Oct' in w.weekday_heading.text()
  assert 'TODAY' in w.dashboard_day_blocks[2].text() and '—' in w.dashboard_day_blocks[3].text()
  for style in ('Fusion','Windows'):
   qt.setStyle(style)
   for width,height in [(1280,720),(1366,768),(1450,850)]:
    w.resize(width,height)
    for _ in range(6):qt.processEvents()
    assert w.height()==height and w.video.height()>=360,(style,width,w.height(),w.video.height())
    assert w.hourly_strip.isVisible() and w.weekday_strip.isVisible()
    for block in w.dashboard_day_blocks:
     pos=block.mapTo(w,block.rect().topLeft())
     assert pos.x()>=0 and pos.x()+block.width()<=w.width() and pos.y()+block.height()<=w.height()
     assert block.width()>=200 and block.height()>=42
  qt.setStyle('Fusion');w.resize(1280,720);qt.processEvents()
  w.grab().save(str(Path(__file__).parent/'weekday_dashboard_preview.png'))
  before=[b.text() for b in w.dashboard_day_blocks]
  w.test_events=[1,2,3,4,5];w.refresh_weekday_totals()
  assert [b.text() for b in w.dashboard_day_blocks]==before,'Test counts must not replace production history'
 finally:
  w.close();qt.processEvents()
  if hasattr(w,'_dashboard_loader'):w._dashboard_loader.wait(4)
print('PASS: real async history collection, dated five-day strip, today/upcoming states, six layouts and production history isolated from tests')
