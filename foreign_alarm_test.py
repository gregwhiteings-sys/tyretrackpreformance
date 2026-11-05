"""Offline confirmation/region/auth tests; no model, camera, audio or SMTP."""
from test_resources import DatabaseTemporaryDirectory
import ast,json,tempfile
from pathlib import Path
from foreign_alarm import Confirmation,ForeignPresence,in_region,set_password,verify_password,write_json,read_json

def detection(box=(10,10,30,30),cls=0):return dict(box=box,class_id=cls,confidence=.9)
c=Confirmation()
assert c.update([detection()],0) is None
assert c.update([detection()],1) is None
assert c.update([detection()],2)['class_id']==0
c.clear()
assert c.update([detection()],3) is None
assert c.update([detection((100,100,130,130))],4) is None
assert c.update([],5) is None
assert c.update([detection()],6) is None
presence=ForeignPresence(hits=3,clear_after=3)
events=[]
for t in (0,.2,.4):
    new,active=presence.update([dict(detection(),class_name='foreign_object')],t)
    events.extend(new)
assert len(events)==1 and events[0]['class_name']=='foreign_object' and active
assert not presence.update([],4.0)[1]
c.clear();c.update([detection()],0)
assert c.update([detection()],10) is None
assert in_region((280,160,360,220),640,360,.03,.98,.18,.82)
assert not in_region((0,100,30,140),640,360,.03,.98,.18,.82)
assert not in_region((280,0,320,5),640,360,.03,.98,.18,.82)
with DatabaseTemporaryDirectory() as folder:
 p=Path(folder)/'admin.json';set_password(p,'testpass')
 assert verify_password(p,'testpass') and not verify_password(p,'wrongpass')
 assert 'testpass' not in p.read_text()
 state=Path(folder)/'alarm.json';write_json(state,{'latched':True})
 assert read_json(state,{})['latched']
 write_json(state,{'latched':False});assert not read_json(state,{})['latched']
print('PASS: confirmation, per-object alerting, auto-clear timeout, spatial filtering and password hashing')
