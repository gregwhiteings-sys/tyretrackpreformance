"""Upgrade an existing original-schema database twice without losing records or settings."""
from test_resources import DatabaseTemporaryDirectory
import os,sys,types,tempfile,sqlite3
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
import TyreTrack_Production_Monitor as m
with DatabaseTemporaryDirectory() as folder:
 m.DB=Path(folder)/'site.db'
 with sqlite3.connect(m.DB) as con:
  con.executescript('CREATE TABLE counts(id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT NOT NULL,source TEXT,track_id INTEGER,confidence REAL); CREATE TABLE state(key TEXT PRIMARY KEY,value TEXT);')
  con.execute('INSERT INTO counts(ts,source,track_id,confidence) VALUES(?,?,?,?)',('2026-10-19T06:10:00',m.OAK_NAME,123,.9))
  con.execute('INSERT INTO state VALUES(?,?)',('site_custom_setting','keep me'))
 m.init_db();m.init_db()
 with sqlite3.connect(m.DB) as con:
  assert con.execute('SELECT id,ts,source,track_id,confidence FROM counts').fetchall()==[(1,'2026-10-19T06:10:00',m.OAK_NAME,123,.9)]
  assert con.execute('SELECT value FROM state WHERE key=?',('site_custom_setting',)).fetchone()[0]=='keep me'
  cols={row[1] for row in con.execute('PRAGMA table_info(counts)')};assert {'metric_utc','tyre_type','class_confidence'}<=cols
  indices={row[1] for row in con.execute('PRAGMA index_list(counts)')};assert {'counts_source_metric','counts_source_ts'}<=indices
print('PASS: existing history IDs/values and site state preserved through repeat schema upgrade; additive columns/indexes only')
