"""Lightweight committed-count snapshot, independent of historical report work."""
from contextlib import closing
import sqlite3,time
from datetime import datetime,timedelta

def snapshot(db,source,now):
    begun=time.monotonic()
    start=now.replace(hour=5,minute=0,second=0,microsecond=0)
    end=now.replace(hour=17,minute=5,second=0,microsecond=0)
    stop=min(max(now,start),end)
    hour=now.replace(minute=0,second=0,microsecond=0)
    types={};hour_count=0
    with closing(sqlite3.connect(db,timeout=3)) as con:
        con.execute('BEGIN')
        all_time=con.execute('SELECT COUNT(*) FROM counts WHERE source=?',(source,)).fetchone()[0]
        # Return one row per class, not every tyre in today's production history.
        rows=con.execute('SELECT tyre_type,COUNT(*),SUM(CASE WHEN metric_utc>=? THEN 1 ELSE 0 END) FROM counts WHERE source=? AND metric_utc>=? AND metric_utc<? GROUP BY tyre_type',
            (hour.timestamp(),source,start.timestamp(),stop.timestamp()))
        for kind,count,hour_n in rows:
            types[kind]=count
            if now<end:hour_count+=hour_n
        # Compatibility with old databases without epoch timestamps.
        rows=con.execute('SELECT ts,tyre_type FROM counts WHERE source=? AND metric_utc IS NULL AND ts>=? AND ts<?',
            (source,(start.date()-timedelta(days=1)).isoformat(),(end.date()+timedelta(days=2)).isoformat()))
        for ts,kind in rows:
            try:
                stamp=datetime.fromisoformat(ts)
                if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=now.tzinfo)
                if not start<=stamp<stop:continue
            except (ValueError,TypeError,OverflowError,OSError):continue
            types[kind]=types.get(kind,0)+1
            if hour<=stamp and now<end:hour_count+=1
    ready=time.monotonic()
    return dict(day=now.date().isoformat(),hour=now.hour,daily=sum(types.values()),current_hour=hour_count,all_time=all_time,types=types,read_ms=(ready-begun)*1000,ready_mono=ready)
