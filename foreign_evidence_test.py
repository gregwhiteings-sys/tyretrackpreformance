"""Exercise the shipped worker method with deliberately different preview/evidence frames."""
import ast,datetime,traceback
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from foreign_alarm import ForeignPresence,ClearEvidence,in_region,CLASSES,OAK_CLASSES

tree=ast.parse((Path(__file__).parent/'TyreTrack_Production_Monitor.py').read_text())
worker=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CounterWorker')
method=next(n for n in worker.body if isinstance(n,ast.FunctionDef) and n.name=='foreign_check')
scope={'time':SimpleNamespace(monotonic=lambda:10.),'traceback':traceback,'log':lambda *a:None,
       'brisbane_now':lambda:datetime.datetime(2026,11,19,tzinfo=datetime.timezone(datetime.timedelta(hours=10))),
       'in_region':in_region,'CLASSES':CLASSES,'OAK_CLASSES':OAK_CLASSES}
exec(compile(ast.Module(body=[method],type_ignores=[]),'shipped_foreign_check','exec'),scope)
check=scope['foreign_check']

class Signal:
    def __init__(self):self.values=[]
    def emit(self,value):self.values.append(value)

def fixture():
    w=SimpleNamespace(foreign_reset_pending=False,foreign_enabled=True,foreign_failed=False,
        source_kind='oak',processing_frame=1,foreign_every=1,foreign_last_seq=None,
        foreign_confidence=.70,foreign_region=(.03,.98,.18,.82),
        foreign_presence_tracker=ForeignPresence(hits=3,clear_after=3.),
        foreign_clear_evidence=ClearEvidence(),last_foreign_presence=(),
        foreign_presence=Signal(),foreign_event=Signal(),foreign_status=Signal(),
        manual_test=False,source='',foreign_model_sha256='a'*64)
    w.item=None;w.oak_source=SimpleNamespace(read_foreign=lambda:w.item)
    return w

def raw(cls=0):
    a=np.zeros((1,8,3549),np.float32);a[0,:4,0]=[208,208,80,80];a[0,4+cls,0]=.95
    return {'output0':a}

preview=np.full((7,13,3),17,np.uint8)
paired=np.full((270,480,3),93,np.uint8)
w=fixture()
for seq in [1,2,3]:w.item=(seq,paired,raw(),9.9);check(w,preview)
assert not w.foreign_failed,w.foreign_status.values
assert len(w.foreign_event.values)==1
event=w.foreign_event.values[0]
assert event['frame'].shape==paired.shape and np.all(event['frame']==93)
assert not np.shares_memory(event['frame'],paired)
assert event['frame_sequence']==3 and event['model_sha256']=='a'*64
assert event['evidence_frame_kind']=='foreign_inference'
assert abs(event['inference_age_seconds']-.1)<1e-8
hits=w.foreign_presence_tracker.tracks[0]['hits'];check(w,preview)
assert w.foreign_presence_tracker.tracks[0]['hits']==hits
w.item=(4,paired,raw(),7.);check(w,preview)
assert len(w.foreign_event.values)==1

# Class 3 is still suppressed with the real four-class decoder.
w=fixture()
for seq in [1,2,3]:w.item=(seq,paired,raw(3),9.9);check(w,preview)
assert not w.foreign_event.values and not w.foreign_failed

# PC evidence continues to use the exact frame submitted to PC inference.
class Values:
    def __init__(self,value):self.value=value
    def cpu(self):return self
    def int(self):return self
    def tolist(self):return self.value
w=fixture();w.source_kind='video';pc=np.full((270,480,3),42,np.uint8)
boxes=SimpleNamespace(xyxy=Values([[180,130,260,210]]),cls=Values([0]),conf=Values([.95]))
def predict(frame,**kwargs):
    assert frame is pc
    return [SimpleNamespace(boxes=boxes)]
w.foreign_model=SimpleNamespace(predict=predict)
for _ in range(3):check(w,pc)
assert len(w.foreign_event.values)==1
assert np.all(w.foreign_event.values[0]['frame']==42)
assert w.foreign_event.values[0]['evidence_frame_kind']=='pc_inference'
assert w.foreign_event.values[0]['frame_sequence'] is None
print('PASS: shipped worker saves matched OAK pixels and dimensions, copied evidence, sequence/hash/age provenance; stale/duplicate packets ignored; normal tyres excluded; PC evidence retained')
