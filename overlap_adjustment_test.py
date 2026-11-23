"""Absolute/reversible corrections, concurrency, report reconciliation and no production mutations."""
import json,sqlite3,tempfile
from pathlib import Path
from datetime import datetime
from contextlib import closing
from classification_review import ReviewStore
from management_reports import build_briefing
from hourly_dashboard import BRISBANE
from pypdf import PdfReader
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);db=root/'counts.db'
 with closing(sqlite3.connect(db)) as c:
  c.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT,tyre_type TEXT)')
  stamp=datetime(2026,11,23,8,tzinfo=BRISBANE)
  c.execute('INSERT INTO counts VALUES(?,?,?,?)',(stamp.isoformat(),stamp.timestamp(),'oak','passenger'));c.commit()
 store=ReviewStore(root/'classification_review')
 for key,scope in [('event','production'),('test','test')]:
  store.submit('overlap',dict(timestamp=stamp.isoformat(),scope=scope,track_ids=[1,2],counted_track_ids=[1],not_counted_track_ids=[2]),key=key)
 assert store.flush()
 def reject(fn):
  try:fn()
  except ValueError:return
  raise AssertionError('Invalid correction accepted')
 reject(lambda:store.adjust_overlap('event',1,'unknown','Greg','Clip reviewed'))
 store.review('event','confirmed_overlap');store.review('test','confirmed_overlap')
 reject(lambda:store.adjust_overlap('test',1,'unknown','Greg','Clip reviewed'))
 reject(lambda:store.adjust_overlap('event',1,'unknown','','Clip reviewed'))
 assert store.adjust_overlap('event',1,'passenger','Greg','One tyre missed in clip')==1
 assert store.adjust_overlap('event',1,'passenger','Greg','One tyre missed in clip',0)==1
 reject(lambda:store.adjust_overlap('event',2,'passenger','Greg','Two tyres',0))
 reject(lambda:store.review('event','not_overlap'))
 for weekly in (False,True):
  r,p=build_briefing(db,'oak',root/'reports',stamp.replace(hour=10),weekly)
  assert r['total']==1 and r['confirmed_missed']==1 and r['reviewed_total']==2
  text=''.join(page.extract_text() for page in PdfReader(p['pdf']).pages)
  assert 'reviewed total: 2' in text and 'One tyre missed in clip' in text
 assert store.adjust_overlap('event',0,'unknown','Greg','Reversed after checking another angle',1)==2
 r,_=build_briefing(db,'oak',root/'reports',stamp.replace(hour=10));assert r['reviewed_total']==1
 with store.connect() as c:assert c.execute('SELECT COUNT(*) FROM overlap_adjustment_history').fetchone()[0]==2
 with closing(sqlite3.connect(db)) as c:assert c.execute('SELECT COUNT(*) FROM counts').fetchone()[0]==1
 assert store.close()
print('PASS corrections require confirmed production review, atomic revision/idempotent save, reversal history, daily/weekly reviewed totals and unchanged original count DB')
