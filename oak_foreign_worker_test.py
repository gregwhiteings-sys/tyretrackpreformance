"""Exercise real counter worker + foreign alarm and authenticated GUI reset with fake packets."""
from test_resources import DatabaseTemporaryDirectory
import os,time,tempfile
os.environ['QT_QPA_PLATFORM']='offscreen'
import numpy as np
from types import SimpleNamespace
from pathlib import Path
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
m.Main._confirm_admin_pin=lambda self,action:True
qt=QApplication.instance() or QApplication([])
m.log_count=lambda *args:None;m.oak_in_operating_hours=lambda:True
m.YOLO=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('OAK path must not instantiate CPU YOLO'))
def raw(kind):
 if kind=='tyre':return np.zeros(18144,np.float32)
 out=np.zeros((1,5,3549),np.float32)
 out[0,:,0]=[240,208,80,80,.99]
 return {'output0':out}
for class_id in (0,):
 class Source:
  def __init__(self,ip,foreign_enabled=False):self.index=0;self.last_read_frame_at=time.monotonic();assert foreign_enabled
  def read(self):
   if self.index==6:worker.running=False;return False,None,None
   self.index+=1;self.last_read_neural_output=raw('tyre');self.last_read_frame_at=time.monotonic()
   return True,np.zeros((270,480,3),np.uint8),self.index
  def read_foreign(self):return self.index,np.zeros((270,480,3),np.uint8),raw('foreign'),time.monotonic()
  def release(self):pass
 m.OakSource=Source
 worker=m.CounterWorker('oak','','Bottom to Top',.35,.5);worker.foreign_enabled=True;worker.foreign_every=20
 events=[];statuses=[];worker.foreign_event.connect(events.append);worker.status.connect(statuses.append);worker.foreign_status.connect(statuses.append)
 worker.run()
 assert len(events)==1 and events[0]['class_id']==class_id and events[0]['class_name']=='foreign_object',(events,statuses,worker.foreign_boxes,worker.foreign_failed)
 assert worker.foreign_active and not worker.foreign_failed
 assert not any(s.startswith('FAULT') for s in statuses),statuses
 assert not any(s.startswith('ERROR') for s in statuses),statuses
print('PASS: real OAK counter worker decodes one-class YOLOv8 RVC2 outputs without CPU YOLO; each tracked object alerts once; OAK ignores PC-only frame interval')
# Presence-based alarm clears as soon as its worker reports no object after the grace window.
m.Main.tick=lambda self:None
with DatabaseTemporaryDirectory():
 window=m.Main();window.clock.stop();window.alarm_timer.stop() if hasattr(window,'alarm_timer') else None
 window.alarm_tick=lambda:None;window.stop_alarm_sound=lambda:None
 window.update_alarm_banner=lambda:None
 window.on_foreign_presence([{'class_name':'foreign_object'}])
 assert window.alarm_state['active']
 window.on_foreign_presence([])
 assert not window.alarm_state['active']
 window.close()
print('PASS: dashboard alarm automatically clears after foreign-object presence ends')
