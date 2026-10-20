"""Real worker and real ByteTrack with synthetic OAK packets: isolated shadow counts."""
import os,time
os.environ['QT_QPA_PLATFORM']='offscreen'
import numpy as np
from types import SimpleNamespace
from PyQt5.QtCore import QCoreApplication
import TyreTrack_Production_Monitor as m
from three_line import ThreeLineCounter,simulation_checks
qt=QCoreApplication.instance() or QCoreApplication([])
assert all(ok for _,ok in simulation_checks())
ys=list(range(260,95,-5))
for production_enabled in (False,True):
 logged=[];statuses=[]
 m.log_count=lambda *args:logged.append(args)
 m.oak_in_operating_hours=lambda:production_enabled
 class SimulatedOak:
  def __init__(self,*args,**kwargs):self.index=0;self.last_read_frame_at=time.monotonic()
  def read(self):
   if self.index==len(ys):worker.running=False;return False,None,None
   raw=np.zeros((6,3024),dtype=np.float32);raw[:,0]=[192,ys[self.index],80,60,.95,.01]
   self.index+=1;self.last_read_neural_output=raw.ravel();self.last_read_frame_at=time.monotonic()
   return True,np.zeros((270,480,3),dtype=np.uint8),self.index
  def release(self):pass
 m.OakSource=SimulatedOak
 worker=m.CounterWorker('oak','','Bottom to Top',.35,.5)
 worker.three_line.set_mode("zigzag")
 worker.logic_test_counter=ThreeLineCounter(mode="zigzag");worker.status.connect(statuses.append)
 worker.run()
 assert not any(s.startswith('ERROR') for s in statuses),statuses
 assert worker.logic_test_counter.total==1 and worker.logic_test_counter.crossings==[1,1,1]
 assert worker.session_count==int(production_enabled) and len(logged)==int(production_enabled)
 assert all(row[0]==m.OAK_NAME for row in logged)
 print('PASS: independent shadow count; production gate',production_enabled,'production writes',len(logged))
host=SimpleNamespace(logic_test_result=worker.logic_test_counter,logic_test_started='test',logic_test_finished='end',
                     hand_count=SimpleNamespace(text=lambda:'2'),line_pos=SimpleNamespace(value=lambda:59))
report=m.Main.logic_test_report(host)
assert report['final_unique_total']==1 and report['difference']==-1 and not report['production_totals_modified_by_test']
print('PASS: exported hand-count comparison and separate test totals')
