"""Actual JPEG transport and Qt screen preview; no production counts or camera."""
import os,sys,types,tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
import numpy as np,cv2
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
from offline_replay import PreviewWriter
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *args:True
app=QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);m.DB=root/'production.db';m.init_db()
 w=m.Main();w.clock.stop();w.resize(1280,720);w.show()
 app.processEvents()
 assert w.video.height()>=480 and w.video.width()>=970,(w.video.width(),w.video.height())
 w.offline_testing=True;w._replay_output=root;w.test_progress.show()
 frame=np.zeros((270,480,3),dtype=np.uint8);frame[:]=(40,60,80)
 cv2.line(frame,(0,210),(479,60),(0,255,255),2)
 state=dict(frame=40,geometry='zigzag',percent=50,total=7,crossings=[7,6,4],recoveries=[0,1,0],processing_fps=12.5)
 writer=PreviewWriter(root);writer.publish(frame,state,force=True)
 w.poll_video_test_preview();app.processEvents()
 assert w.video._pix.width()==480 and w.video._pix.height()==270
 assert 'UNIQUE 7' in w.test_transport.text() and w.test_progress.value()==500
 assert 'production totals unchanged' in w.status_lbl.text()
 assert m.production_snapshot()['all_time']==0
 previous=w.video._pix.cacheKey();w.poll_video_test_preview()
 assert w.video._pix.cacheKey()==previous,'duplicate frame must not repaint'
 state['frame']=41;state['percent']=51;writer.publish(frame,state,force=True)
 w.poll_video_test_preview();assert w.test_progress.value()==510
 w.close()
print('PASS: 1280px large viewport, atomic JPEG/meta preview, actual on-screen frames/progress/count, duplicate-frame suppression, zero production writes')
