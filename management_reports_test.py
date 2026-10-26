"""Read-only briefing math/PDF/CSV, mocked MIME transport, scheduler and Qt export."""
import ast,csv,json,os,sqlite3,sys,tempfile,threading,time,types
from pathlib import Path
from datetime import datetime,timedelta,timezone
from contextlib import closing
from unittest.mock import Mock
from management_reports import collect,build_briefing,make_email,send_briefing
from hourly_dashboard import BRISBANE
from pypdf import PdfReader
from test_resources import DatabaseTemporaryDirectory
root=Path(__file__).resolve().parent
now=datetime(2026,10,30,17,5,tzinfo=BRISBANE)
with DatabaseTemporaryDirectory() as folder:
 folder=Path(folder);db=folder/'counts.db';incident=folder/'incidents';incident.mkdir();recordings=folder/'recordings'/'2026-10-30';recordings.mkdir(parents=True)
 (recordings/'OAK_RGB_20261030_060000.mp4').write_bytes(b'fixture filename only')
 with closing(sqlite3.connect(db)) as con:
  con.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT,tyre_type TEXT)')
  def add(day,hour,kind='passenger',source='oak',legacy=False):
   t=now.replace(day=day,hour=hour,minute=0)
   con.execute('INSERT INTO counts VALUES(?,?,?,?)',(t.replace(tzinfo=None).isoformat(sep=' '),None if legacy else t.timestamp(),source,kind))
  for kind in ('passenger','passenger','SUV','truck','unknown'):add(30,6,kind,legacy=kind=='SUV')
  for _ in range(4):add(29,6)
  add(30,4);add(30,18);add(30,6,source='video');add(31,6);add(26,6);add(23,6)
  con.execute("CREATE TABLE supervisor_no_count(incident_id TEXT,started_brisbane TEXT,ended_brisbane TEXT,status TEXT,reason TEXT,supervisor TEXT,comments TEXT)")
  con.execute('INSERT INTO supervisor_no_count VALUES(?,?,?,?,?,?,?)',('NC-20261030-081000','2026-10-30 08:00:00',None,'AWAITING RESPONSE','=unsafe formula','Operator <review>','Long comment '+('details '*60)))
  con.commit();before=con.total_changes
 for name,kind in [('live','oak'),('test','oak_test'),('video','video')]:
  (incident/(name+'.json')).write_text(json.dumps(dict(timestamp=now.replace(hour=8).isoformat(),source_kind=kind,object='wheel_rim',confidence=.9,snapshot='rim.jpg')))
 (incident/'broken.json').write_text('{')
 r,paths=build_briefing(db,'oak',folder/'reports',now,incidents_dir=incident,recordings_dir=recordings.parent)
 assert r['total']==5 and r['weight']['total_kg']==77 and r['weight']['total_epu']==9
 assert r['weight']['unknown']==1 and sum(s['count'] for s in r['slots'])==5
 assert r['previous_total']==4 and r['delta_percent']==25
 assert len(r['alarms'])==1 and r['unreadable_incidents']==1 and len(r['recordings'])==1
 assert r['supervisors'][0]['status']=='AWAITING RESPONSE'
 assert len(PdfReader(paths['pdf']).pages)>=2
 text=''.join(p.extract_text() for p in PdfReader(paths['pdf']).pages)
 assert all(x in text for x in ['TYRECYCLE / OZCOM','No-count review','Truck','25.0%','Recorded footage'])
 with paths['csv'].open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
 assert sum(int(x['tyres']) for x in rows if x['record_type']=='HOURLY')==5
 assert sum(int(x['estimated_kg']) for x in rows if x['record_type']=='HOURLY')==77
 assert next(x for x in rows if x['record_type']=='WEEKDAY' and x['date']=='2026-10-30')['estimated_kg']=='77'
 assert sum(x['record_type']=='FOREIGN_ALERT' for x in rows)==1
 from PIL import Image
 snapshot=folder/'snapshot.png';Image.new('RGB',(16,9),'navy').save(snapshot)
 settings=('sender@example.org','TEST_ONLY','manager@example.org')
 email=make_email(settings,r,paths)
 assert email.get_body(preferencelist=('html',)) is not None
 assert sorted(p.get_content_type() for p in email.iter_attachments())==['application/pdf','text/csv']
 rich=make_email(settings,r,paths,snapshot)
 assert any(p.get('Content-ID')=='<dashboard_snapshot>' for p in rich.walk())
 assert 'cid:dashboard_snapshot' in rich.get_body(preferencelist=('html',)).get_content()
 smtp=Mock();smtp.__enter__=Mock(return_value=smtp);smtp.__exit__=Mock(return_value=False);factory=Mock(return_value=smtp)
 assert send_briefing(settings,r,paths,smtp_factory=factory)
 assert smtp.login.call_args.args==settings[:2] and smtp.send_message.call_count==1
 assert not send_briefing(settings,r,paths,smtp_factory=Mock(side_effect=OSError('test failure')))
 assert not send_briefing(None,r,paths,smtp_factory=Mock(side_effect=AssertionError('must not send')))
 partial=collect(db,'oak',now.replace(hour=10),False);assert not partial['complete'] and partial['delta_percent'] is None
 week,wp=build_briefing(db,'oak',folder/'weekly',now,True)
 assert week['total']==10 and sum(d['count'] for d in week['weekdays'])==10 and sum(s['count'] for s in week['slots'])==10
 assert all(p.exists() and p.stat().st_size for p in wp.values())
 with closing(sqlite3.connect(db)) as con:assert con.execute('SELECT COUNT(*) FROM counts').fetchone()[0]==15
 print('PASS: production-only PDF/CSV/JSON reconciliation, kg/EPU/legacy counts, gaps/replies/trial alerts/footage, weekly and provisional reports; MIME attachments and SMTP failures mocked')
# Exercise actual scheduler function with isolated state and mocked outbound calls.
code=ast.parse((root/'TyreTrack_Production_Monitor.py').read_text());node=next(n for n in code.body if isinstance(n,ast.FunctionDef) and n.name=='process_scheduled_emails')
state={};daily=Mock(return_value=False);weekly=Mock(return_value=False)
ns=dict(datetime=datetime,timedelta=timedelta,timezone=timezone,time=time,threading=threading,
 _EMAIL_LOCK=threading.Lock(),_LAST_REPLY_CHECK=time.monotonic(),get_state=lambda k,d='':state.get(k,d),set_state=lambda k,v:state.__setitem__(k,v),
 oak_no_count_alert_tick=lambda:None,send_daily_production_email=daily,send_management_briefing=weekly,send_hourly_email=Mock(return_value=True),log=lambda s:None)
exec(compile(ast.Module(body=[node],type_ignores=[]),'<scheduler>','exec'),ns)
ns['process_scheduled_emails'](now)
assert not any(k.startswith(('daily_sent','weekly_sent')) for k in state)
daily.return_value=True;weekly.return_value=True
ns['process_scheduled_emails'](now);assert state['daily_sent_20261030']=='1' and state['weekly_sent_20261030']=='1'
assert weekly.call_args.kwargs['weekly'] is True
calls=daily.call_count,weekly.call_count;ns['process_scheduled_emails'](now);assert calls==(daily.call_count,weekly.call_count)
ns['process_scheduled_emails'](now+timedelta(days=1));assert calls==(daily.call_count,weekly.call_count)
print('PASS: after-close daily + Friday weekly, failed-send retry, persisted success deduplication and weekend gate; no emails sent')
# Real admin button export on a background thread; no camera or SMTP.
os.environ['QT_QPA_PLATFORM']='offscreen';stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *a:True
if sys.platform=='win32':m.os.startfile=lambda path:None
qt=QApplication.instance() or QApplication([])
with DatabaseTemporaryDirectory() as folder:
 m.DATA=Path(folder);m.DB=m.DATA/'ui.db';m.REPORTS=m.DATA/'reports';m.init_db();w=m.Main();w.clock.stop()
 try:
  w.management_daily_btn.click();fired=[];QTimer.singleShot(0,lambda:fired.append(True));qt.processEvents();assert fired
  deadline=time.monotonic()+5
  while w._management_thread.is_alive() and time.monotonic()<deadline:qt.processEvents();time.sleep(.01)
  qt.processEvents()
  assert 'PDF + CSV saved:' in w.management_report_status.text(),w.management_report_status.text()
  assert list((m.REPORTS/'management').glob('*.pdf')) and w.management_daily_btn.isEnabled()
 finally:
  w.close();qt.processEvents()
  if hasattr(w,'_management_thread'):w._management_thread.join(5)
print('PASS: real report export button, responsive GUI, saved PDF/CSV and completion signal')
