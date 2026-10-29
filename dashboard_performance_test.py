"""History parity at production boundaries and realistic stored-history load."""
from pathlib import Path
from datetime import datetime,timedelta
from contextlib import closing
from test_resources import DatabaseTemporaryDirectory
import json,sqlite3,tempfile,time,statistics,ast
from collections import defaultdict
from hourly_dashboard import BRISBANE
from dashboard_history import best_daily
from live_totals import snapshot
root=Path(__file__).resolve().parent
old=json.loads((root/'dashboard_performance_changes.json').read_text())['functions']['best_daily_record']['old']
# The old reference function uses SQLite transaction contexts, which do not
# close connections. Own those handles explicitly before Windows deletes the DB.
with DatabaseTemporaryDirectory() as folder:
 db=Path(folder)/'history.db';now=datetime(2026,10,29,12,tzinfo=BRISBANE)
 with closing(sqlite3.connect(db)) as con:
  con.execute('CREATE TABLE counts(id INTEGER PRIMARY KEY,ts TEXT,metric_utc REAL,source TEXT,tyre_type TEXT)')
  con.execute('CREATE INDEX counts_source_metric ON counts(source,metric_utc)')
  records=[]
  for i in range(100000):
   stamp=now.replace(day=20,hour=5,minute=0)+timedelta(days=i//10000,seconds=i%10000)
   records.append((stamp.isoformat(),stamp.timestamp(),'oak','passenger' if i%2 else '4x4'))
  for stamp,source,legacy in [(now.replace(hour=4,minute=59,second=59),'oak',False),(now.replace(day=28,hour=17,minute=4,second=59,microsecond=999999),'oak',False),(now.replace(day=28,hour=17,minute=5),'oak',False),(now.replace(hour=6),'video',False),(now.replace(hour=6),'oak',True),(now.replace(hour=6).astimezone(__import__('datetime').timezone.utc),'oak',True),(now+timedelta(days=1),'oak',False)]:
   records.append((stamp.isoformat(),None if legacy else stamp.timestamp(),source,'truck'))
  con.executemany('INSERT INTO counts(ts,metric_utc,source,tyre_type) VALUES(?,?,?,?)',records);con.commit()
 ns=dict(DB=db,OAK_NAME='oak',sqlite3=sqlite3,datetime=datetime,defaultdict=defaultdict,brisbane_now=lambda:now)
 exec(old,ns);t=time.perf_counter();expected=ns['best_daily_record']();old_ms=(time.perf_counter()-t)*1000
 t=time.perf_counter();actual=best_daily(db,'oak',now);new_ms=(time.perf_counter()-t)*1000
 assert actual==expected,(actual,expected)
 fast=snapshot(db,'oak',now)
 assert fast['daily']==10002 and fast['current_hour']==0,fast
 assert fast['types']=={'passenger':5000,'4x4':5000,'truck':2},fast
 print(f'PASS: 100k history, old/new best-day parity, legacy/offset times, sub-second shift boundary, future/test exclusion. Best-day old={old_ms:.1f}ms SQL={new_ms:.1f}ms; live={fast["read_ms"]:.1f}ms')
# Verify that a continuously busy historical loader cannot accumulate new requests.
tree=ast.parse((root/'TyreTrack_Production_Monitor.py').read_text());main=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Main')
method=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='request_dashboard_data')
import threading,types
ns={'time':time};exec(compile(ast.Module(body=[method],type_ignores=[]),'<request>','exec'),ns)
requested=[];loader=types.SimpleNamespace(lock=threading.Lock(),running=True,request=lambda:requested.append(True))
w=types.SimpleNamespace(_dashboard_loader=loader)
for _ in range(100):ns['request_dashboard_data'](w)
assert not requested
loader.running=False;w._last_statistics_request=time.monotonic()
ns['request_dashboard_data'](w);assert not requested
w._last_statistics_request-=6;ns['request_dashboard_data'](w);assert len(requested)==1
print('PASS: busy-loader requests suppressed and full history refresh throttled to five seconds')
