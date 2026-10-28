"""Lightweight committed-count snapshot, independent of historical report work."""
from contextlib import closing
import sqlite3
from datetime import datetime

def snapshot(db,source,now):
    start=now.replace(hour=5,minute=0,second=0,microsecond=0)
    end=now.replace(hour=17,minute=5,second=0,microsecond=0)
    stop=min(max(now,start),end)
    hour=now.replace(minute=0,second=0,microsecond=0)
    with closing(sqlite3.connect(db,timeout=3)) as con:
        con.execute('BEGIN')
        all_time=con.execute('SELECT COUNT(*) FROM counts WHERE source=?',(source,)).fetchone()[0]
        rows=con.execute('SELECT ts,metric_utc,tyre_type FROM counts WHERE source=? AND ((metric_utc>=? AND metric_utc<?) OR (metric_utc IS NULL AND ts>=? AND ts<?))',
            (source,start.timestamp(),stop.timestamp(),start.replace(tzinfo=None).isoformat(),stop.replace(tzinfo=None).isoformat())).fetchall()
    types={};hour_count=0
    for ts,epoch,kind in rows:
        try:
            stamp=datetime.fromtimestamp(epoch,now.tzinfo) if epoch is not None else datetime.fromisoformat(ts)
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=now.tzinfo)
            if not start<=stamp<stop:continue
        except (ValueError,TypeError,OverflowError,OSError):continue
        types[kind]=types.get(kind,0)+1
        if hour<=stamp and now<end:hour_count+=1
    return dict(day=now.date().isoformat(),hour=now.hour,daily=sum(types.values()),current_hour=hour_count,all_time=all_time,types=types)
