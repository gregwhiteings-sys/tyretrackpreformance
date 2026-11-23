"""Actual encoded footage, clean event evidence, storage isolation and bounded capture."""
import tempfile,json,types,threading,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
import av,numpy as np
from training_recording import TrainingRecorder
with av.open('test_data/oak_h264_sample.h264',format='h264') as f:
 packets=[bytes(p) for p in f.demux(video=0) if p.size]
now=datetime(2026,11,23,5,tzinfo=timezone(timedelta(hours=10)))
disk=lambda _:types.SimpleNamespace(free=50*1024**3)
with tempfile.TemporaryDirectory() as tmp:
 r=TrainingRecorder(tmp,lambda x:None,disk_usage=disk,segment_seconds=1)
 for i,p in enumerate(packets):
  r.feed(p,now+timedelta(seconds=i/15),i,i>=15)
  if i==20:
   image=np.zeros((360,640,3),np.uint8)
   assert r.submit(dict(kind='overlap_start',event_id='one',scope='production',timestamp=now.isoformat(),track_ids=[1,2],recording_reference=r.path),image)
   image[:]=255 # saved evidence must own a clean copy
 r.feed(packets[-1],now+timedelta(seconds=4),46,False)
 assert r.submit(dict(kind='overlap_complete',event_id='one',scope='production',timestamp=now.isoformat(),track_ids=[1,2],counted_track_ids=[1],not_counted_track_ids=[2],recording_reference='original.mp4'))
 assert not r.submit(dict(kind='scheduled_baseline',scope='test',timestamp=now.isoformat()))
 assert not r.submit(dict(kind='scheduled_baseline',scope='production',timestamp=now.isoformat()))
 r.close()
 videos=sorted(Path(tmp).rglob('*.mp4'));assert len(videos)==2,videos
 for p in videos:
  with av.open(str(p)) as f:assert len(list(f.decode(video=0)))==15
  s=json.loads(p.with_suffix('.json').read_text());assert s['frames']==15 and s['fps']==15 and s['clean_video']
 records=[json.loads(line) for p in Path(tmp).rglob('*.jsonl') for line in p.read_text().splitlines()]
 start=next(x for x in records if x['kind']=='overlap_start');end=next(x for x in records if x['kind']=='overlap_complete')
 import cv2
 assert not cv2.imread(str(Path(tmp)/start['clean_snapshot'])).any()
 assert end['counted_track_ids']==[1] and end['not_counted_track_ids']==[2]
 assert start['label_status']=='unreviewed' and start['confirmed_belt_width_mm']==1180
 assert len([x for x in records if x['kind']=='segment'])==2
print('PASS actual 15fps MP4 decode, production gate, keyframe rotation, clean copied evidence, late count links after recording stops')
for mode in ['low','quota','error']:
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);keep=root/'retained.bin';keep.write_bytes(b'keep')
  def storage(_):
   if mode=='error':raise OSError('unavailable')
   return types.SimpleNamespace(free=0 if mode=='low' else 50*1024**3)
  r=TrainingRecorder(root,lambda x:None,disk_usage=storage,quota_gb=0 if mode=='quota' else 25)
  for i,p in enumerate(packets):r.feed(p,now,i,True)
  r.close();assert not list(root.rglob('*.mp4'));assert keep.read_bytes()==b'keep';assert 'paused' in r.state
print('PASS low-space/quota/I/O error pause recording, retain existing files and do not propagate into counting')
with tempfile.TemporaryDirectory() as tmp:
 r=TrainingRecorder(tmp,lambda x:None,disk_usage=disk);r.state='recording'
 p=dict(kind='scheduled_baseline',scope='production',timestamp=now.isoformat())
 for i in range(32):assert r.submit(p)
 assert not r.submit(p) and r.dropped==1
 r.close()
print('PASS evidence queue bounded, no waiting or unbounded image accumulation')
# An evidence-image failure on shutdown must still finalise the primary video.
with tempfile.TemporaryDirectory() as tmp:
 r=TrainingRecorder(tmp,lambda x:None,disk_usage=disk)
 for i,p in enumerate(packets[:15]):r.feed(p,now,i,True)
 assert r.submit(dict(kind='overlap_start',event_id='failure',scope='production',timestamp=now.isoformat()),np.zeros((360,640,3),np.uint8))
 original=cv2.imwrite
 try:
  cv2.imwrite=lambda *a,**k:False
  r.close()
 finally:cv2.imwrite=original
 assert r.recorder.writer is None
 video=next(Path(tmp).rglob('*.mp4'))
 with av.open(str(video)) as f:assert sum(1 for _ in f.decode(video=0))==15
print('PASS shutdown evidence error still closes handles and finalises the playable primary video')

# Exercise the real OAK recorder loop with simulated encoded packets; no camera.
import os,sys
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
import TyreTrack_Production_Monitor as m
import training_recording
original_capture=training_recording.TrainingRecorder
training_recording.TrainingRecorder=lambda *a,**k:original_capture(*a,**k,disk_usage=disk)
with tempfile.TemporaryDirectory() as tmp:
 m.DATA=Path(tmp);m.OAK_RECORDINGS=Path(tmp)/'manual';m.RECORD_OAK_VIDEO=False;m.AUTO_TRAINING_RECORDING=True;m.log=lambda x:None
 src=m.OakSource.__new__(m.OakSource);src.stop_event=threading.Event();src.capture_fps=15;src.training_active=True
 class PacketQueue:
  index=0
  def tryGet(self):
   if self.index>=len(packets):src.stop_event.set();return None
   n=self.index;self.index+=1
   return types.SimpleNamespace(getData=lambda:packets[n],getSequenceNum=lambda:n)
 src.encoded_queue=PacketQueue();src._record_loop()
 files=list((Path(tmp)/'oak_training').rglob('*.mp4'));assert len(files)==1
 with av.open(str(files[0])) as f:assert sum(1 for _ in f.decode(video=0))==45
 assert not (Path(tmp)/'manual').exists() and src.training_capture is None
training_recording.TrainingRecorder=original_capture
print('PASS actual OAK recorder loop saves auto footage with manual Record unticked and closes all handles')
# Actual production worker supplies the gate and event/count linkage; tests excluded.
import overlap_worker_link_test as fixture
original_source=fixture.Source
for manual,operating in [(False,True),(True,True),(False,False)]:
 captured=[];gates=[]
 class Source(original_source):
  def __init__(self,*a,**k):
   super().__init__(*a,**k)
   def submit(p,image=None):
    if getattr(self,'training_active',False):captured.append((p,image.copy() if image is not None else None))
   self.training_capture=types.SimpleNamespace(submit=submit)
  def read(self):gates.append(self.training_active);return super().read()
 fixture.m.OakSource=Source;fixture.m.oak_in_operating_hours=lambda:operating
 with tempfile.TemporaryDirectory() as tmp:
  fixture.m.DATA=Path(tmp);fixture.counts.clear()
  fixture.worker=fixture.m.CounterWorker('oak','','Bottom to Top',.35,.5);fixture.worker.manual_test=manual
  fixture.worker.run()
  assert all(g==bool(operating and not manual) for g in gates)
  if manual or not operating:assert not captured
  else:
   kinds={p['kind'] for p,image in captured};assert {'overlap_start','overlap_complete','scheduled_baseline'}<=kinds
   complete=next(p for p,image in captured if p['kind']=='overlap_complete')
   assert complete['counted_track_ids']==[1] and complete['not_counted_track_ids']==[2]
   assert len(fixture.counts)==1
print('PASS actual worker production gate, clean sampling and late count linkage; manual and off-hours excluded')
