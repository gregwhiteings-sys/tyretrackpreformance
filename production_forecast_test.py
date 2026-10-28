from datetime import datetime
from zoneinfo import ZoneInfo
from production_forecast import forecast_text
import time
z=ZoneInfo('Australia/Brisbane')
def f(h,m=0,total=3000,target=6000,day=29,test=False):
 n=datetime(2026,10,day,h,m,tzinfo=z)
 return forecast_text(n,target,dict(day=n.date().isoformat(),hour=h,daily=total),test)
assert '6,042' in f(11)
assert '494 tyres/hour' in f(11)
assert 'Shift starts' in f(4)
assert '15 minutes' in f(5)
assert 'Shift ended' in f(17,5)
assert 'Target achieved' in f(12,total=6000)
assert 'No scheduled' in f(12,day=31)
assert 'paused' in f(12,test=True)
assert 'Set a daily' in f(12,target=0)
n=datetime(2026,10,29,11,tzinfo=z)
assert 'Waiting' in forecast_text(n,6000,None)
t=time.perf_counter()
for _ in range(10000): f(11)
print('PASS: forecast arithmetic, shift boundaries, disabled target, weekend, tests and missing totals; 10000 calculations %.1fms'%((time.perf_counter()-t)*1000))
