import sqlite3,tempfile,zipfile,io,hashlib
from pathlib import Path
from datetime import datetime
from contextlib import closing
from machine_hours import HoursStore,latest,performance,recorded_tyres,previous_shift
from hourly_dashboard import BRISBANE
now=datetime(2026,11,26,18,tzinfo=BRISBANE)
with tempfile.TemporaryDirectory() as t:
 root=Path(t);store=HoursStore(root/'hours');db=root/'counts.db'
 with closing(sqlite3.connect(db)) as c:
  c.execute('CREATE TABLE counts(ts TEXT,source TEXT,metric_utc REAL,track_id INTEGER)')
  for stamp,source,epoch,ident in [('2026-11-26T05:00:00+10:00','oak',True,1),('2026-11-26T08:00:00+10:00','oak',True,-1),('2026-11-26T09:00:00','oak',False,2),('2026-11-25T08:00:00+10:00','oak',True,3),('2026-11-26T04:59:59+10:00','oak',True,4),('2026-11-26T17:05:00+10:00','oak',True,5),('2026-11-26T08:00:00+10:00','replay',True,6),('2026-11-27T08:00:00+10:00','oak',True,7)]:
   d=datetime.fromisoformat(stamp);c.execute('INSERT INTO counts VALUES(?,?,?,?)',(stamp,source,d.timestamp() if epoch else None,ident))
  c.commit()
 before=hashlib.sha256(db.read_bytes()).hexdigest()
 store.save('2026-11-25',1000.0,now=now);assert latest(store.root,db,'oak',now)['hours'] is None
 store.save('2026-11-26',1009.7,now=now);r=latest(store.root,db,'oak',now)
 assert r['hours']==9.7 and r['tyres']==3 and abs(r['rate']-3/9.7)<1e-9,r
 assert recorded_tyres(db,'oak','2026-11-26',now.replace(hour=7))==1
 assert recorded_tyres(db,'oak','2026-11-27',now) is None
 assert previous_shift('2026-11-23')=='2026-11-20'
 assert recorded_tyres(db,'oak','2026-11-21',now) is None
 for day,value in [('2026-11-26',996),('2026-11-26',1040),('2026-11-27',1010),('2026-11-21',6650),('2026-11-26',float('nan'))]:
  try:store.save(day,value,now=now)
  except ValueError:pass
  else:raise AssertionError((day,value))
 assert latest(store.root,db,'oak',now)['meter']==1009.7
 store.save('2026-11-26',10,'Meter replaced; opening confirmed from reset sheet',opening=0,now=now)
 assert latest(store.root,db,'oak',now)['hours']==10
 with store.connect() as c:assert c.execute('SELECT count(*) FROM history').fetchone()[0]==3
 gap=HoursStore(root/'gap');gap.save('2026-11-23',6600,now=now);gap.save('2026-11-26',6620,now=now)
 assert latest(gap.root,db,'oak',now)['hours'] is None
 zpath=root/'photos.zip'
 with zipfile.ZipFile(zpath,'w') as z:
  z.writestr('../IMG-20261126-WA0103.jpg',b'test-photo-bytes')
  z.writestr('meter_readings.csv','day,meter\n2026-11-26,1009.7\n')
 imported=HoursStore(root/'imported');assert imported.import_zip(zpath)==(1,1)
 assert imported.rows()[0]['checked']==0 and imported.rows()[0]['meter']==1009.7
 imported.save('2026-11-26',1010,now=now);imported.import_zip(zpath)
 assert imported.rows()[0]['meter']==1010 and len(imported.documents('2026-11-26'))==1
 assert all((imported.root/d['path']).resolve().is_relative_to(imported.root.resolve()) for d in imported.documents('2026-11-26'))
 assert hashlib.sha256(db.read_bytes()).hexdigest()==before,'Production counts modified'
print('PASS actual running-hour delta, matching Brisbane production counts including +1, test/future/shift exclusion, missing-day/zero/reset validation, audit, local photo import and unchanged production database')
