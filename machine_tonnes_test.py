"""Verify weighted monthly throughput, weight coverage and production isolation."""
import hashlib,sqlite3,tempfile
from pathlib import Path
from contextlib import closing
from datetime import datetime
from hourly_dashboard import BRISBANE
from machine_hours import HoursStore,latest,performance

now=datetime(2026,11,26,18,tzinfo=BRISBANE)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);db=root/'counts.db';store=HoursStore(root/'hours')
    with closing(sqlite3.connect(db)) as c:
        c.execute('CREATE TABLE counts(ts TEXT,source TEXT,metric_utc REAL,tyre_type TEXT)')
        for day,kind,n,source in [('2026-11-25','passenger',100,'oak'),('2026-11-26','SUV',50,'oak'),('2026-11-26','truck',10,'oak'),('2026-11-26','unknown',2,'oak'),('2026-11-26','truck',100,'replay'),('2026-10-30','truck',100,'oak'),('2026-11-27','truck',100,'oak')]:
            stamp=day+'T08:00:00+10:00'
            c.executemany('INSERT INTO counts VALUES(?,?,?,?)',[(stamp,source,datetime.fromisoformat(stamp).timestamp(),kind)]*n)
        # Legacy timestamp path must use the same weight aliases and shift window.
        c.execute("INSERT INTO counts VALUES('2026-11-26T09:00:00','oak',NULL,'car')")
        c.execute("INSERT INTO counts VALUES('2026-11-26T04:00:00','oak',NULL,'truck')");c.commit()
    before=hashlib.sha256(db.read_bytes()).hexdigest()
    for day,meter in [('2026-11-24',100),('2026-11-25',102),('2026-11-26',110)]:store.save(day,meter,now=now)
    r=latest(store.root,db,'oak',now)
    assert r['tyres']==63 and r['unknown_weight']==2,r
    assert abs(r['tonnes_rate']-1.274/8)<1e-10,r
    assert abs(r['month_tonnes_rate']-2.074/10)<1e-10,r
    assert r['month_shifts']==2 and r['month_hours']==10 and r['month_unknown_weight']==2
    assert abs(r['month_tonnes_rate']-(.8/2+1.274/8)/2)>.01,'Unweighted mean used'
    # Unknown additions count as tyres, but never receive an invented weight.
    with closing(sqlite3.connect(db)) as c:
        assert hashlib.sha256(db.read_bytes()).hexdigest()==before
        c.execute("UPDATE counts SET tyre_type='unknown' WHERE source='oak'");c.commit()
    r=latest(store.root,db,'oak',now)
    assert abs(r['tonnes_rate']-(63*8/1000/8))<1e-10 and abs(r['month_tonnes_rate']-(163*8/1000/10))<1e-10
    store.save('2026-11-26',102,now=now)
    r=latest(store.root,db,'oak',now)
    assert r.get('tonnes_rate') is None and r['month_shifts']==1
    # A new calendar month never inherits last month's average.
    r=latest(store.root,db,'oak',datetime(2026,12,1,18,tzinfo=BRISBANE))
    assert r['month_shifts']==0 and r['month_tonnes_rate'] is None
print('PASS shift tonnes, weighted calendar-month average, aliases/legacy dates, unknown weights, zero hours, month rollover and read-only production queries')
