"""No production DB or network: summary privacy, isolation, throttling, failures."""
from pathlib import Path
from datetime import datetime,timedelta
import tempfile,threading,time,json
from unittest.mock import MagicMock
from hourly_dashboard import BRISBANE
from web_dashboard import Publisher,build_snapshot,validate_config,URL
now=datetime(2026,10,30,10,tzinfo=BRISBANE)
start=now.replace(hour=5)
live=dict(day=now.date().isoformat(),hour=10,daily=4,current_hour=2,all_time=99,types={'passenger':2,'SUV':1,'truck':1})
cache=dict(metrics=dict(day_start=start,flow_per_minute=1.2,no_count_status='RUNNING'),hourly=([dict(start=start,end=start+timedelta(hours=1),completed=True,count=2)],dict(count=2),None),best=('2026-10-29',100),weekdays=[dict(date=now.date(),count=4,current=True)],private_email='not shared',comments='not shared')
payload=build_snapshot(live,cache,now,True,100)
assert payload['estimated_kg']==77 and payload['epu']==9
assert payload['passenger']==2 and payload['suv']==1 and payload['truck']==1
assert 'private_email' not in payload and 'comments' not in payload
assert build_snapshot(live,cache,now,test_mode=True) is None
assert build_snapshot(live,cache,now+timedelta(days=1)) is None
with tempfile.TemporaryDirectory() as tmp:
 path=Path(tmp)/'connection.json';cfg=Path(tmp)/'import.json';cfg.write_text(json.dumps(dict(schema=1,url=URL,token='x'*48)))
 clock=[0];entered=threading.Event();release=threading.Event()
 response=MagicMock();response.__enter__.return_value.status=200
 def slow(req,timeout):
  assert req.get_header('User-agent')=='TyreTrack-Publisher/1.0'
  entered.set();assert release.wait(2);return response
 p=Publisher(path,opener=slow,clock=lambda:clock[0]);p.import_file(cfg)
 assert not p.request(payload);p.enable(True);assert p.request(payload);assert entered.wait(1)
 assert not p.request(payload),'No overlapping jobs'
 release.set();p.thread.join(2);assert p.status=='Last update sent successfully'
 assert not p.request(payload),'Ten-second limit'
 clock[0]=11;p.opener=MagicMock(side_effect=OSError('secret detail'))
 assert p.request(payload);p.thread.join(2);assert 'secret' not in p.status
 p.enable(False);clock[0]=30;assert not p.request(payload)
 restored=Publisher(path);assert not restored.config['enabled']
 for invalid in ({'schema':1,'url':'http://evil.test','token':'x'*48},{'schema':1,'url':URL,'token':'short'}):
  try:validate_config(invalid)
  except ValueError:pass
  else:raise AssertionError('Unsafe config accepted')
print('PASS: kg/EPU summary, private-field exclusion, date/test isolation, opt-in persistence, nonblocking uploads, no overlap, ten-second limit, network failure isolation and connection-file validation')
