"""Daily/weekly embedded evidence, event-time conversion and missing-image isolation."""
import json,sqlite3,tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from hourly_dashboard import BRISBANE
from management_reports import build_briefing,make_email,alert_snapshot

with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);inc=root/'incidents';inc.mkdir();db=root/'counts.db'
 with closing(sqlite3.connect(db)) as con:
  con.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT,tyre_type TEXT)')
 for name in ('today','earlier'):
  Image.new('RGB',(1920,1080),'#456789').save(inc/(name+'.jpg'))
 (inc/'corrupt.jpg').write_bytes(b'broken image')
 def event(name,ts,kind='oak',snapshot=None):
  (inc/(name+'.json')).write_text(json.dumps(dict(timestamp=ts,source_kind=kind,object='metal_object',confidence=.91,snapshot=snapshot or name+'.jpg')))
 event('today','2026-10-30T00:12:34+00:00',snapshot=r'C:\old\foreign_incidents\today.jpg')
 event('earlier','2026-10-29T10:11:12+10:00')
 event('missing','2026-10-30T11:00:00+10:00')
 event('corrupt','2026-10-30T12:00:00+10:00')
 event('test','2026-10-30T12:00:00+10:00','oak_test',snapshot='earlier.jpg')
 event('video','2026-10-30T12:00:00+10:00','video',snapshot='earlier.jpg')
 event('future','2026-10-31T12:00:00+10:00')
 event('previousweek','2026-10-23T12:00:00+10:00')
 now=datetime(2026,10,30,17,5,tzinfo=BRISBANE)
 for weekly,expected_alerts,expected_images in ((False,3,1),(True,4,2)):
  report,paths=build_briefing(db,'oak',root/'reports',now,weekly,inc)
  assert len(report['alarms'])==expected_alerts
  pdf=PdfReader(paths['pdf']);text=''.join(page.extract_text() for page in pdf.pages)
  assert '30 Oct 2026 10:12:34' in text and 'Brisbane (UTC+10)' in text
  assert text.count('Snapshot unavailable')==2
  assert sum(len(page.images) for page in pdf.pages)==expected_images
  assert ('29 Oct 2026 10:11:12' in text)==weekly
  msg=make_email(('sender@example.com','test','manager@example.com'),report,paths)
  assert 'timestamped foreign-alert snapshots' in msg.get_body(preferencelist=('html',)).get_content()
  attachment=next(p for p in msg.iter_attachments() if p.get_content_type()=='application/pdf')
  assert attachment.get_payload(decode=True)==paths['pdf'].read_bytes()
  assert report['total']==0
 assert alert_snapshot(report,dict(snapshot='../outside.jpg')) is None
 print('PASS daily/weekly embedded alert images, Brisbane event timestamps, Windows filenames, missing/corrupt fallback, test/date exclusions and PDF email attachment; no SMTP')
