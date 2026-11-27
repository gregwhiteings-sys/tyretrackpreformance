"""Weight periods and meter-matched reports use consistent production records."""
import csv,hashlib,sqlite3,tempfile
from pathlib import Path
from contextlib import closing
from datetime import datetime,timedelta
from hourly_dashboard import BRISBANE,hourly_snapshot
from weekly_dashboard import weekday_snapshot,month_week_snapshot
from machine_hours import HoursStore,report_running_hours
from management_reports import collect,build_briefing,make_email
from pypdf import PdfReader
now=datetime(2026,11,27,18,tzinfo=BRISBANE)
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);db=root/'counts.db';hours=HoursStore(root/'machine_hours')
 with closing(sqlite3.connect(db)) as c:
  c.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT,tyre_type TEXT)')
  def add(day,kind,n=1,hour=6,source='oak',legacy=False):
   t=now.replace(day=day,hour=hour,minute=0)
   c.executemany('INSERT INTO counts VALUES(?,?,?,?)',[(t.isoformat(),None if legacy else t.timestamp(),source,kind)]*n)
  add(26,'car',100);add(27,'SUV',50,legacy=True);add(27,'truck',10);add(27,'unknown',2)
  add(27,'truck',20,source='video');add(27,'truck',20,hour=4);add(28,'truck',20);add(27,'truck',20,hour=19)
  c.commit()
  slots,_,_=hourly_snapshot(c,'oak',now);days=weekday_snapshot(c,'oak',now);weeks=month_week_snapshot(c,'oak',now)
  assert sum(x['count'] for x in slots)==62
  assert sum(x['estimated_kg'] for x in slots)==1266
  assert sum(x['unknown_weight'] for x in slots)==2
  assert sum(x['estimated_kg'] for x in days)==2066==sum(x['estimated_kg'] for x in weeks)
 for day,meter in [(25,100),(26,102),(27,110)]:hours.save(f'2026-11-{day}',meter,now=now)
 original=hashlib.sha256(db.read_bytes()).hexdigest();meter_hash=hashlib.sha256(hours.db.read_bytes()).hexdigest()
 daily=collect(db,'oak',now);weekly=collect(db,'oak',now,True)
 run=daily['running_hours'];assert run['running_hours']==8 and run['matched_tyres']==62
 assert abs(run['tonnes_per_running_hour']-1.266/8)<1e-10
 run=weekly['running_hours'];assert run['running_hours']==10 and run['matched_tyres']==162
 assert abs(run['tonnes_per_running_hour']-2.066/10)<1e-10 and run['matched_shifts']==2
 assert run['expected_shifts']==5 and not run['coverage_complete']
 # Live counts never divide by a completed-shift meter value entered early.
 live=collect(db,'oak',now.replace(hour=12));assert live['running_hours']['running_hours'] is None
 r,paths=build_briefing(db,'oak',root/'reports',now,True)
 with paths['csv'].open(encoding='utf-8-sig',newline='') as f:
  rows=list(csv.DictReader(f));assert all(None not in row for row in rows),'CSV row/header mismatch'
 sr=next(x for x in rows if x['record_type']=='SHREDDER_PERIOD')
 assert float(sr['running_hours'])==10 and float(sr['estimated_tonnes'])==2.066
 assert abs(float(sr['estimated_tonnes_per_running_hour'])-.2066)<1e-10
 text=' '.join(p.extract_text() for p in PdfReader(paths['pdf']).pages)
 assert 'Shredder running hours and averages' in text and '2/5 shifts matched' in text and 'Daily production weight' in text
 msg=make_email(('sender@example.org','TEST','manager@example.org'),r,paths)
 assert '10.00 h' in msg.get_body(preferencelist=('plain',)).get_content()
 assert '10.00 h' in msg.get_body(preferencelist=('html',)).get_content()
 assert hashlib.sha256(db.read_bytes()).hexdigest()==original
 assert hashlib.sha256(hours.db.read_bytes()).hexdigest()==meter_hash
 # No readings must not create a new hours database.
 missing=report_running_hours(root/'missing',[],now.replace(hour=5),now,now)
 assert missing['running_hours'] is None and not (root/'missing').exists()
 print('PASS exact period kg/tonnes, aliases, unknown/test/off-shift/future isolation, weighted matched shifts, incomplete coverage, live pending, CSV/PDF/email and no DB writes')
