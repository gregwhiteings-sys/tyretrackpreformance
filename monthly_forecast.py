"""Read-only monthly estimate; Brisbane weekday 05:00–17:05 schedule.
Observed pace includes downtime from the first recorded production day this month.
"""
from datetime import datetime, timedelta
from hourly_dashboard import BRISBANE
from tyre_weight import totals

def snapshot(con, source, now, period="month"):
    now=now.astimezone(BRISBANE)
    begin=now.replace(hour=0,minute=0,second=0,microsecond=0)
    if period=='day':
        end=begin+timedelta(days=1)
    elif period=='week':
        begin-=timedelta(days=begin.weekday());end=begin+timedelta(days=7)
    elif period=='month':
        begin=begin.replace(day=1)
        end=(begin.replace(day=28)+timedelta(days=4)).replace(day=1)
    else:raise ValueError('Unknown projection period')
    # Aggregate indexed timestamps in SQLite; legacy timestamps retain Python parsing.
    rows=con.execute("SELECT strftime('%Y-%m-%d',metric_utc,'unixepoch','+10 hours'),tyre_type,COUNT(*) FROM counts WHERE source=? AND metric_utc>=? AND metric_utc<=? AND CAST(strftime('%w',metric_utc,'unixepoch','+10 hours') AS INTEGER) BETWEEN 1 AND 5 AND strftime('%H:%M:%S',metric_utc,'unixepoch','+10 hours')>='05:00:00' AND strftime('%H:%M:%S',metric_utc,'unixepoch','+10 hours')<'17:05:00' GROUP BY 1,2",(source,begin.timestamp(),min(now,end).timestamp())).fetchall()
    rows=list(rows)
    for ts,kind in con.execute('SELECT ts,tyre_type FROM counts WHERE source=? AND metric_utc IS NULL AND ts>=? AND ts<?',(source,(begin-timedelta(days=1)).date().isoformat(),(end+timedelta(days=1)).date().isoformat())):
        try:
            stamp=datetime.fromisoformat(ts)
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=BRISBANE)
            stamp=stamp.astimezone(BRISBANE)
            if begin<=stamp<end and stamp<=now and stamp.weekday()<5 and (5,0)<=(stamp.hour,stamp.minute)<(17,5):rows.append((stamp.date().isoformat(),kind,1))
        except (ValueError,TypeError,OverflowError,OSError):continue
    types={};first=None
    for day,kind,n in rows:
        if not day:continue
        first=min(first,day) if first else day
        types[kind]=types.get(kind,0)+n
    actual=totals(types)
    elapsed=remaining=0.0
    day=begin
    while day<end:
        if day.weekday()<5:
            start=day.replace(hour=5);stop=day.replace(hour=17,minute=5)
            remaining+=max(0,(stop-max(now,start)).total_seconds())/3600
            if first and day.date().isoformat()>=first:
                elapsed+=max(0,(min(now,stop)-start).total_seconds())/3600
        day+=timedelta(days=1)
    count=sum(types.values());kg=actual['total_kg']
    ready=bool(first and elapsed>=1)
    return dict(period=period,label={'day':'TODAY','week':'THIS WEEK','month':begin.strftime('%B %Y').upper()}[period],as_of=now.isoformat(),month=begin.strftime('%B %Y'),actual_tyres=count,actual_kg=kg,unknown=actual['unknown'],observed_hours=elapsed,remaining_hours=remaining,first_day=first,ready=ready,projected_tyres=round(count+count/elapsed*remaining) if ready else None,projected_tonnes=(kg+kg/elapsed*remaining)/1000 if ready else None)

def all_snapshots(con,source,now):
    return {period:snapshot(con,source,now,period) for period in ('day','week','month')}

def forecast_text(data,test_mode=False):
    if test_mode:return 'Production projections paused during video/manual tests'
    if not data or not data.get('ready'):return 'PROJECTION · Waiting for at least one observed production hour in this period'
    warning=' · Unclassified tyres excluded from weight' if data['unknown'] else ''
    return (f"PROJECTED {data['label']} · {data['projected_tyres']:,} tyres · {data['projected_tonnes']:,.1f} tonnes\n"
            f"Estimated from {data['observed_hours']:,.1f} scheduled hours since {data['first_day']}; includes stops. Class-based weight estimate.{warning}")

def report_text(report):
    data=report.get('production_projections') or {'month':report.get('monthly_forecast')}
    return '\n\n'.join(forecast_text(data.get(period)) for period in ('day','week','month') if period in data)
