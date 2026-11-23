"""Month week arithmetic and real responsive dashboard fit."""
import sqlite3,calendar
from datetime import datetime,timedelta,timezone
from contextlib import closing
from weekly_dashboard import month_week_snapshot
from hourly_dashboard import BRISBANE
now=datetime(2026,10,28,10,tzinfo=BRISBANE)
with closing(sqlite3.connect(':memory:')) as c:
 c.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT)')
 def add(t,source='oak',legacy=False,utc=False):
  ts=t.astimezone(timezone.utc).isoformat() if utc else t.replace(tzinfo=None).isoformat() if legacy else t.isoformat()
  c.execute('INSERT INTO counts VALUES(?,?,?)',(ts,None if legacy or utc else t.timestamp(),source))
 add(now.replace(day=1,hour=5),utc=True);add(now.replace(day=2,hour=17,minute=4),legacy=True)
 for day in (5,26,27,28):add(now.replace(day=day,hour=6))
 for t,src in [(now.replace(day=3),'oak'),(now.replace(day=28,hour=11),'oak'),(now.replace(day=29),'oak'),(now.replace(day=27,hour=4,minute=59),'oak'),(now.replace(day=27,hour=17,minute=5),'oak'),(now,'video'),(now.replace(month=9,day=30),'oak')]:add(t,src)
 c.execute("INSERT INTO counts VALUES('bad',NULL,'oak')")
 ws=month_week_snapshot(c,'oak',now);assert [w['count'] for w in ws]==[2,1,0,0,3],ws
 assert ws[-1]['current'] and all(w['completed'] for w in ws[:-1])
 assert month_week_snapshot(c,'oak',now.astimezone(timezone.utc))==ws
 for year in (2024,2026,2027):
  for month in range(1,13):
   ws=month_week_snapshot(c,'oak',now.replace(year=year,month=month,day=1));assert 4<=len(ws)<=5
   covered=[(w['start']+timedelta(days=i)).date() for w in ws for i in range((w['end']-w['start']).days)]
   assert len(covered)==len(set(covered)) and all(d.month==month for d in covered)
   assert all(datetime(year,month,d).date() in covered for d in range(1,calendar.monthrange(year,month)[1]+1) if datetime(year,month,d).weekday()<5)
 nov=month_week_snapshot(c,'oak',now.replace(month=11,day=1));assert nov[0]['start'].day==2 and all(w['future'] for w in nov)
print('PASS month boundaries, leap years, partial weeks, timezone rollover, production shifts/source/future exclusion')
# Reuse the established real UI fixture with added month-row assertions.
from pathlib import Path
source=Path('weekday_dashboard_test.py').read_text()
source=source.replace("[(1280,720),(1366,768),(1450,850)]","[(1280,720),(1366,768),(1450,850),(1920,1080)]")
needle="    assert w.hourly_strip.isVisible() and w.weekday_strip.isVisible()"
extra='''
    assert [x['count'] for x in w._dashboard_cache['month_weeks']]==[0,0,0,0,10]
    assert 'October 2026' in w.month_week_heading.text() and 'LIVE' in w.dashboard_week_blocks[-1].text()
    w.stats_scroll.verticalScrollBar().setValue(0);qt.processEvents()
    viewport=w.stats_scroll.viewport()
    for strip in (w.hourly_strip,w.weekday_strip,w.month_week_strip):
     pos=strip.mapTo(viewport,strip.rect().topLeft())
     assert pos.x()>=0 and pos.x()+strip.width()<=viewport.width()+1
     assert pos.y()>=0 and pos.y()+strip.height()<=viewport.height()+1,(style,width,height,pos.y(),strip.height(),viewport.height())
    blocks=[b for b in w.dashboard_week_blocks if b.isVisible()]
    assert max(b.width() for b in blocks)-min(b.width() for b in blocks)<=1
    assert all(b.height()>=48 and b.width()>=120 for b in blocks)
    from PyQt5.QtGui import QTextDocument
    for label in w.projection_labels.values():
     document=QTextDocument();document.setDefaultFont(label.font());document.setHtml(label.text());document.setTextWidth(label.width()-8)
     assert document.size().height()<=label.height(),(style,width,height,document.size().height(),label.height())
'''
assert needle in source;source=source.replace(needle,needle+extra)
source=source.replace('weekday_dashboard_preview.png','month_week_dashboard_preview.png')
exec(compile(source,'month_week_real_ui_fixture','exec'),{'__file__':str(Path('weekday_dashboard_test.py').resolve())})
print('PASS weekly cards equal width, 3 totals rows fully visible without scrolling at 4 sizes/2 styles; real async production totals')
