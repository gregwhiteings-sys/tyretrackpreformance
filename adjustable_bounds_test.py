from test_resources import DatabaseTemporaryDirectory
import os,sys,types,tempfile,json,unittest
from pathlib import Path
from three_line import ThreeLineCounter,line_segments
class BoundsLogicTest(unittest.TestCase):
 def test_connected_custom_bounds(self):
  for mode in ('zigzag','zigzag_reverse'):
   for direction in ('Bottom to Top','Top to Bottom'):
    start,diagonal,end=line_segments(101,101,.5,direction,mode,.1,.9)
    self.assertEqual(set((diagonal[1],diagonal[3])),{10,90})
    self.assertEqual(set((start[1],end[1])),{10,90})
 def test_one_count_across_custom_geometry(self):
  c=ThreeLineCounter(mode='zigzag');c.set_bounds(.1,.9)
  for i,y in enumerate((95,85,65,45,20,5),1):c.observe(1,50,y,101,101,.59,i)
  self.assertEqual(c.total,1);self.assertEqual(c.crossings,[1,1,1])
 def test_motion_of_lines_does_not_count(self):
  c=ThreeLineCounter(mode='zigzag');c.observe(1,50,65,101,101,.59,1)
  c.set_bounds(.1,.6);c.observe(1,50,64,101,101,.4,2)
  self.assertEqual(c.total,0)
 def test_accepted_count_retained(self):
  c=ThreeLineCounter();c.observe(1,50,90,101,101,.59,1);c.observe(1,50,70,101,101,.59,2)
  c.set_bounds(.1,.9);c.observe(1,50,65,101,101,.5,3);c.observe(1,50,45,101,101,.5,4)
  self.assertEqual(c.total,1)
 def test_invalid_bounds_rejected(self):
  c=ThreeLineCounter()
  for top,bottom in ((.9,.1),(0,.8),(.5,.55),(.2,1)):
   with self.assertRaises(ValueError):c.set_bounds(top,bottom)

def ui_check():
 os.environ['QT_QPA_PLATFORM']='offscreen'
 stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
 import numpy as np
 from PyQt5.QtWidgets import QApplication
 from PyQt5.QtCore import Qt,QPoint,QPointF,QEvent
 from PyQt5.QtGui import QMouseEvent
 from PyQt5.QtTest import QTest
 from unittest.mock import Mock
 import TyreTrack_Production_Monitor as m
 m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *args:True
 app=QApplication.instance() or QApplication([])
 with DatabaseTemporaryDirectory() as folder:
  m.DB=Path(folder)/'db.sqlite';m.init_db();w=m.Main();w.resize(1280,720);w.show()
  w.display_frame(np.zeros((270,480,3),np.uint8));app.processEvents()
  w.top_line_slider.setValue(10);w.bottom_line_slider.setValue(90)
  assert (w.video.top_ratio,w.video.bottom_ratio)==(.1,.9)
  w.edit_bounds_btn.setChecked(True);assert w.video.bounds_editable
  w.offline_testing=True;w._replay_output=Path(folder)
  process=Mock();process.poll.return_value=None;w._replay_process=process
  ox,oy,width,height,scale=w.video.image_geometry()
  x=round(ox+width/2);y1=round(oy+.1*269*scale);y2=round(oy+.3*269*scale)
  QTest.mousePress(w.video,Qt.LeftButton,pos=QPoint(x,y1))
  assert w.video.drag_mode=='top_bound',w.video.drag_mode
  app.sendEvent(w.video,QMouseEvent(QEvent.MouseMove,QPointF(x,y2),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
  QTest.mouseRelease(w.video,Qt.LeftButton,pos=QPoint(x,y2))
  app.processEvents()
  assert abs(w.top_line_slider.value()-30)<=1,w.top_line_slider.value()
  request=json.loads((Path(folder)/'geometry.request.json').read_text())
  assert abs(request['top']-.3)<=.01 and request['bottom']==.9,request
  assert w.line_pos.minimum()<=w.line_pos.value()<=w.line_pos.maximum()
  cy=round(oy+(w.video.top_ratio+w.video.bottom_ratio)/2*269*scale)
  QTest.mousePress(w.video,Qt.LeftButton,pos=QPoint(round(ox+1),cy))
  assert w.video.drag_mode=='left_span',w.video.drag_mode
  nx=round(ox+.2*479*scale)
  app.sendEvent(w.video,QMouseEvent(QEvent.MouseMove,QPointF(nx,cy),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
  QTest.mouseRelease(w.video,Qt.LeftButton,pos=QPoint(nx,cy));app.processEvents()
  assert abs(w.left_span_slider.value()-20)<=1,w.left_span_slider.value()
  request=json.loads((Path(folder)/'geometry.request.json').read_text())
  # Integer screen pixels may round the intended 20% drag to 19% or 21%.
  # The replay must receive exactly the value displayed by the slider.
  assert request['left']==w.left_span_slider.value()/100,request
  assert abs(request['left']-.2)<=.011,request
  assert request['right']==w.right_span_slider.value()/100,request
  w._replay_process=None;w.close()
 print('PASS: real on-screen top-line drag, sliders, connected geometry and live replay control request')
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(BoundsLogicTest)
 result=unittest.TextTestRunner().run(suite)
 if not result.wasSuccessful():raise SystemExit(1)
 ui_check()
