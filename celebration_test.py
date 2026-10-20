"""Daily record celebration fires once per hour; later hours and days can win."""
from test_resources import DatabaseTemporaryDirectory
import os,sys,types,tempfile,shutil
from pathlib import Path
from datetime import datetime,timedelta,timezone
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
qt=QApplication.instance() or QApplication([])
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *a:True
with DatabaseTemporaryDirectory() as folder:
 m.DB=Path(folder)/'test.db';m.init_db()
 w=m.Main();w.clock.stop();w.celebration_mute.setChecked(True)
 now=datetime(2026,10,19,7,10,tzinfo=timezone(timedelta(hours=10)))
 m.brisbane_now=lambda:now
 def populate(values):
  slots=[]
  for i in range(13):
   start=now.replace(hour=5,minute=0,second=0)+timedelta(hours=i)
   end=start+timedelta(minutes=5 if i==12 else 60)
   slots.append(dict(number=i+1,start=start,end=end,count=values.get(i,0),completed=end<=now))
  complete=[x for x in slots if x['completed']]
  w._dashboard_cache=dict(hourly=(slots,max(complete,key=lambda x:x['count']),min(complete,key=lambda x:x['count'])))
 populate({0:10,1:20,2:21});w.refresh_production_hours()
 assert len(w._celebrated_hours)==1 and 'NEW BEST HOUR' in w.celebration_banner.text()
 w.celebration_banner.clear();w.refresh_production_hours();assert not w.celebration_banner.text()
 now+=timedelta(hours=1);populate({0:10,1:20,2:21,3:22});w.refresh_production_hours()
 assert len(w._celebrated_hours)==2
 now+=timedelta(days=1);populate({0:5,1:8,2:9,3:10});w.refresh_production_hours()
 assert len(w._celebrated_hours)==3
 assert not w.claim_daily_record(20,20,"2026-10-20")
 assert not w.claim_daily_record(50,0,"2026-10-20")
 assert w.claim_daily_record(21,20,"2026-10-20")
 assert not w.claim_daily_record(22,20,"2026-10-20")
 # A fresh window sees the persisted marker, and a later day can celebrate.
 other=m.Main();other.clock.stop()
 assert not other.claim_daily_record(30,20,"2026-10-20")
 assert other.claim_daily_record(31,30,"2026-10-21")
 other.close()
 from unittest.mock import Mock
 now=now.replace(day=22,hour=7,minute=10)
 populate({0:10,1:20,2:21})
 w._dashboard_cache.update(metrics={'daily':21},prior_best=('2026-10-21',20))
 w.play_celebration_sound=Mock()
 w.refresh_production_hours()
 assert 'NEW BEST DAILY TOTAL' in w.celebration_banner.text()
 assert 'NEW BEST HOUR' in w.celebration_banner.text()
 w.play_celebration_sound.assert_called_once_with()
 w.celebration_banner.clear();w.refresh_production_hours()
 assert not w.celebration_banner.text()
 w.play_celebration_sound.assert_called_once_with()
 w.close()
print('PASS: daily records require a prior day, beat ties, persist across restart, and reset next day')
print('PASS: once per qualifying hour, no repeated banner per tyre, later-hour records and next-day reset')
