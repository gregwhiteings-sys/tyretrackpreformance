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
 w.celebration_mute.setChecked(False)
 w.play_celebration_sound=Mock(return_value=True)
 w.refresh_production_hours()
 assert 'NEW BEST DAILY TOTAL' in w.celebration_banner.text()
 assert 'NEW BEST HOUR' in w.celebration_banner.text()
 w.play_celebration_sound.assert_called_once_with()
 w.celebration_banner.clear();w.refresh_production_hours()
 assert not w.celebration_banner.text()
 w.play_celebration_sound.assert_called_once_with()
 # First completed hour establishes a record, caught at the hour boundary.
 now=now.replace(day=23,hour=6,minute=0,second=0)
 populate({0:12,1:0});w.play_celebration_sound.reset_mock()
 w.refresh_production_hours();w.play_celebration_sound.assert_called_once_with()
 assert 'NEW BEST HOUR' in w.celebration_banner.text()
 w.celebration_banner.clear();w.refresh_production_hours()
 assert not w.celebration_banner.text()
 now=now.replace(hour=7);populate({0:12,1:12});w.refresh_production_hours()
 w.play_celebration_sound.assert_called_once_with()
 now=now.replace(hour=8);populate({0:12,1:12,2:13})
 w.play_celebration_sound.reset_mock();w.refresh_production_hours()
 w.play_celebration_sound.assert_called_once_with()
 # Daily total crossed on the last frame still celebrates at the cutoff.
 now=now.replace(hour=17,minute=5);populate({0:12})
 w._dashboard_cache.update(metrics={'daily':51},prior_best=('2026-10-22',50))
 w.play_celebration_sound.reset_mock();w.refresh_production_hours()
 assert 'NEW BEST DAILY TOTAL' in w.celebration_banner.text()
 w.play_celebration_sound.assert_called_once_with()
 # Failed audio is retried; success clears the pending record.
 w.play_celebration_sound=Mock(side_effect=[False,True])
 w.deliver_record_celebration(['TEST RECORD'])
 assert w._pending_record_sound['attempts']==1
 w._pending_record_sound['next_attempt']=0
 w.deliver_record_celebration()
 assert w._pending_record_sound is None and w.play_celebration_sound.call_count==2
 w.play_celebration_sound.reset_mock();w.celebration_mute.setChecked(True)
 w.deliver_record_celebration(['MUTED RECORD'])
 w.play_celebration_sound.assert_not_called()
 assert 'MUTED' in w.celebration_indicator.text()
 w.celebration_mute.setChecked(False);w.alarm_state={'latched':True}
 w.deliver_record_celebration(['DEFERRED RECORD'])
 w.play_celebration_sound.assert_not_called()
 assert w._pending_record_sound
 w.alarm_state={'latched':False};w.play_celebration_sound=Mock(return_value=True)
 w.deliver_record_celebration();w.play_celebration_sound.assert_called_once_with()
 w.close()
print('PASS: daily records require a prior day, beat ties, persist across restart, and reset next day')
print('PASS: first completed hour, late crossings at rollover, daily cutoff, no duplicate records, mute/alarm priority and failed-playback retry')
