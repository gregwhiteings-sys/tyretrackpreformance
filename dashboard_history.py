"""Aggregate modern count history inside SQLite; parse only legacy rows in Python."""
from contextlib import closing
from collections import defaultdict
from datetime import datetime
import sqlite3

def best_daily(db,source,now):
    totals=defaultdict(int)
    with closing(sqlite3.connect(db,timeout=15)) as con:
        con.execute('BEGIN')
        rows=con.execute("""SELECT date(metric_utc,'unixepoch','+10 hours'),COUNT(*)
            FROM counts WHERE source=? AND metric_utc<=?
            AND (CAST(metric_utc+36000 AS INTEGER)%86400)>=18000
            AND (CAST(metric_utc+36000 AS INTEGER)%86400)<61500
            GROUP BY date(metric_utc,'unixepoch','+10 hours')""",(source,now.timestamp()))
        for day,count in rows:
            if day is not None:totals[day]+=count
        for (ts,) in con.execute('SELECT ts FROM counts WHERE source=? AND metric_utc IS NULL',(source,)):
            try:
                stamp=datetime.fromisoformat(ts)
                if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=now.tzinfo)
                stamp=stamp.astimezone(now.tzinfo)
                begin=stamp.replace(hour=5,minute=0,second=0,microsecond=0)
                if begin<=stamp<begin.replace(hour=17,minute=5) and stamp<=now:
                    totals[stamp.date().isoformat()]+=1
            except (ValueError,TypeError,OverflowError):continue
    return max(totals.items(),key=lambda item:(item[1],item[0])) if totals else (None,0)
