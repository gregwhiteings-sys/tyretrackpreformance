"""Read-only Monday-Friday production totals for the current Brisbane week."""
from datetime import datetime, timedelta
from hourly_dashboard import BRISBANE, brisbane_now

def weekday_snapshot(connection, source, now=None):
    now = (now or brisbane_now()).astimezone(BRISBANE)
    monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    saturday = monday + timedelta(days=5)
    days = []
    for index in range(5):
        day = monday + timedelta(days=index)
        begin = day.replace(hour=5)
        end = day.replace(hour=17, minute=5)
        days.append(dict(date=day.date(), start=begin, end=end, count=0,
                         current=day.date() == now.date(), completed=now >= end,
                         future=day.date() > now.date()))
    rows = connection.execute(
        'SELECT ts,metric_utc FROM counts WHERE source=? AND '
        '((metric_utc>=? AND metric_utc<?) OR '
        '(metric_utc IS NULL AND ts>=? AND ts<?))',
        (source, monday.timestamp(), saturday.timestamp(),
         monday.date().isoformat(), saturday.date().isoformat()))
    for ts, epoch in rows:
        try:
            stamp = datetime.fromtimestamp(epoch, BRISBANE) if epoch is not None else datetime.fromisoformat(ts)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=BRISBANE)
            stamp = stamp.astimezone(BRISBANE)
            index = (stamp.date() - monday.date()).days
            if 0 <= index < 5 and days[index]['start'] <= stamp < days[index]['end'] and stamp <= now:
                days[index]['count'] += 1
        except (TypeError, ValueError, OverflowError, OSError):
            continue
    return days
