import sqlite3
from datetime import datetime
from monthly_forecast import snapshot,forecast_text,BRISBANE
con=sqlite3.connect(':memory:')
con.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT,tyre_type TEXT)')
def add(stamp,kind,n=1,source='OAK',legacy=False):
 t=datetime.fromisoformat(stamp).replace(tzinfo=BRISBANE)
 con.executemany('INSERT INTO counts VALUES(?,?,?,?)',[(t.isoformat(),None if legacy else t.timestamp(),source,kind)]*n)
add('2026-11-02T05:30:00','passenger',80)
add('2026-11-02T06:00:00','SUV',10,legacy=True)
add('2026-11-02T06:30:00','truck',2)
add('2026-11-02T06:30:00','unknown',1)
add('2026-11-02T04:59:00','truck',50)
add('2026-11-07T09:00:00','truck',50)
add('2026-11-02T05:30:00','truck',50,source='VIDEO')
r=snapshot(con,'OAK',datetime(2026,11,2,7,tzinfo=BRISBANE))
assert r['actual_tyres']==93 and r['actual_kg']==890 and r['observed_hours']==2
assert r['unknown']==1 and r['ready']
assert r['projected_tyres']==round(93+93/2*r['remaining_hours'])
assert abs(r['projected_tonnes']-(890+445*r['remaining_hours'])/1000)<1e-8
assert 'Unclassified' in forecast_text(r)
assert 'paused' in forecast_text(r,True)
assert not snapshot(con,'NONE',datetime(2026,11,2,7,tzinfo=BRISBANE))['ready']
r=snapshot(con,'OAK',datetime(2026,11,30,18,tzinfo=BRISBANE))
assert r['remaining_hours']==0 and r['projected_tyres']==r['actual_tyres']
assert snapshot(con,'OAK',datetime(2026,12,1,7,tzinfo=BRISBANE))['actual_tyres']==0
con.close()
print('PASS monthly schedule, pace, kg, aliases, legacy, source/shift/weekend/future exclusions, unknown weight, month rollover and test pause')
