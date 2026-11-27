from tyre_weight import add_weight
"""Read-only Monday-Friday production totals for the current Brisbane week."""
from datetime import datetime, timedelta
from hourly_dashboard import BRISBANE, brisbane_now

def weekday_snapshot(connection, source, now=None):
    now = (now or brisbane_now()).astimezone(BRISBANE)
    kind_column='tyre_type' if any(r[1]=='tyre_type' for r in connection.execute('PRAGMA table_info(counts)')) else 'NULL'
    monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    saturday = monday + timedelta(days=5)
    days = []
    for index in range(5):
        day = monday + timedelta(days=index)
        begin = day.replace(hour=5)
        end = day.replace(hour=17, minute=5)
        days.append(dict(date=day.date(), start=begin, end=end, count=0,estimated_kg=0,unknown_weight=0,
                         current=day.date() == now.date(), completed=now >= end,
                         future=day.date() > now.date()))
    rows = connection.execute(
        f'SELECT ts,metric_utc,{kind_column} FROM counts WHERE source=? AND '
        '((metric_utc>=? AND metric_utc<?) OR '
        '(metric_utc IS NULL AND ts>=? AND ts<?))',
        (source, monday.timestamp(), saturday.timestamp(),
         monday.date().isoformat(), saturday.date().isoformat()))
    for ts, epoch,kind in rows:
        try:
            stamp = datetime.fromtimestamp(epoch, BRISBANE) if epoch is not None else datetime.fromisoformat(ts)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=BRISBANE)
            stamp = stamp.astimezone(BRISBANE)
            index = (stamp.date() - monday.date()).days
            if 0 <= index < 5 and days[index]['start'] <= stamp < days[index]['end'] and stamp <= now:
                days[index]['count'] += 1
                add_weight(days[index],kind)
        except (TypeError, ValueError, OverflowError, OSError):
            continue
    return days


def month_week_snapshot(connection, source, now=None):
    """Calendar weeks clipped to this month; original weekday shift counts only."""
    now=(now or brisbane_now()).astimezone(BRISBANE)
    kind_column='tyre_type' if any(r[1]=='tyre_type' for r in connection.execute('PRAGMA table_info(counts)')) else 'NULL'
    first=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    end=(first.replace(day=28)+timedelta(days=4)).replace(day=1)
    monday=first-timedelta(days=first.weekday());weeks=[]
    while monday<end:
        start=max(first,monday);stop=min(end,monday+timedelta(days=7))
        # Do not allocate a production-week card for a weekend-only fragment.
        if any((start+timedelta(days=i)).weekday()<5 for i in range((stop-start).days)):
            weeks.append(dict(start=start,end=stop,count=0,estimated_kg=0,unknown_weight=0,current=start<=now<stop,
                              completed=now>=stop,future=now<start))
        monday+=timedelta(days=7)
    rows=connection.execute(f'SELECT ts,metric_utc,{kind_column} FROM counts WHERE source=? AND '
        '((metric_utc>=? AND metric_utc<?) OR (metric_utc IS NULL AND ts>=? AND ts<?))',
        (source,first.timestamp(),end.timestamp(),(first-timedelta(days=1)).date().isoformat(),
         (end+timedelta(days=1)).date().isoformat()))
    for ts,epoch,kind in rows:
        try:
            stamp=datetime.fromtimestamp(epoch,BRISBANE) if epoch is not None else datetime.fromisoformat(ts)
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=BRISBANE)
            stamp=stamp.astimezone(BRISBANE)
            if not first<=stamp<end or stamp>now or stamp.weekday()>=5:continue
            if not stamp.replace(hour=5,minute=0,second=0,microsecond=0)<=stamp<stamp.replace(hour=17,minute=5,second=0,microsecond=0):continue
            for week in weeks:
                if week['start']<=stamp<week['end']:
                    week['count']+=1;add_weight(week,kind);break
        except (TypeError,ValueError,OverflowError,OSError):continue
    return weeks
