"""Production-hours gate and all-hours connection; no device required."""
import ast,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock
code=ast.parse(Path(__file__).with_name('TyreTrack_Production_Monitor.py').read_text())
main=next(n for n in code.body if isinstance(n,ast.ClassDef) and n.name=='Main')
funcs=[n for n in code.body if isinstance(n,ast.FunctionDef) and n.name=='oak_in_operating_hours']
funcs += [n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='schedule_tick']
ns=dict(time=time,brisbane_now=lambda:None)
exec(compile(ast.Module(body=funcs,type_ignores=[]),'<production schedule>','exec'),ns)
zone=timezone(timedelta(hours=10))
for h,m,s,expected in ((4,59,59,False),(5,0,0,True),(17,4,59,True),(17,5,0,False),(23,0,0,False)):
 assert ns['oak_in_operating_hours'](datetime(2026,10,19,h,m,s,tzinfo=zone))==expected
for day in (17,18):assert not ns['oak_in_operating_hours'](datetime(2026,10,day,8,tzinfo=zone))
ui=SimpleNamespace(closing=False,worker=None,auto_retry_at=0,start=Mock())
ns['schedule_tick'](ui);ui.start.assert_called_once_with(automatic=True)
ns['schedule_tick'](ui);assert ui.start.call_count==1
ui.worker=SimpleNamespace(isRunning=lambda:True,operator_paused=False)
ui.show_fixed_lines=SimpleNamespace(isChecked=lambda:False)
ui.start_btn=SimpleNamespace(setEnabled=Mock());ui.stop_btn=SimpleNamespace(setEnabled=Mock())
ui.stop=Mock();ns['schedule_tick'](ui);ui.stop.assert_not_called()
print('PASS: weekday count boundaries, weekend gate, all-hours camera connection, retry throttle, no scheduled camera disconnect')
