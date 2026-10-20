import unittest,math
from three_line import ThreeLineCounter,line_segments,simulation_checks
class ZigzagTest(unittest.TestCase):
 def test_connecting_endpoints(self):
  for direction in ('Bottom to Top','Top to Bottom'):
   for mode in ('zigzag','zigzag_reverse'):
    start,middle,end=line_segments(101,101,.59,direction,mode)
    self.assertEqual(set((middle[1],middle[3])),set((start[1],end[1])))
 def test_recovery(self):
  for mode in ('zigzag','zigzag_reverse'):
   c=ThreeLineCounter(mode=mode)
   for frame,y in enumerate((65,55,45,30,15),1):c.observe(1,50,y,101,101,.59,frame)
   self.assertEqual(c.total,1);self.assertEqual(c.recoveries[1],1)
 def test_lateral_motion_not_a_count(self):
  c=ThreeLineCounter(mode='zigzag')
  c.observe(1,100,50,101,101,.59,1)
  self.assertIsNone(c.observe(1,0,50,101,101,.59,2));self.assertEqual(c.total,0)
 def test_backward_not_a_count(self):
  c=ThreeLineCounter(mode='zigzag')
  c.observe(1,50,40,101,101,.59,1)
  self.assertIsNone(c.observe(1,50,60,101,101,.59,2));self.assertEqual(c.total,0)
 def test_outside_segment(self):
  c=ThreeLineCounter(mode='zigzag')
  c.observe(1,-100,200,101,101,.59,1)
  c.observe(1,-100,-50,101,101,.59,2);self.assertEqual(c.total,0)
 def test_two_side_by_side_separated_events(self):
  for mode in ('zigzag','zigzag_reverse'):
   c=ThreeLineCounter(mode=mode);times={}
   for frame,y in enumerate(range(90,9,-2),1):
    c.begin_frame([1,2])
    for ident,x in ((1,10),(2,90)):
     c.observe(ident,x,y,101,101,.59,frame)
     if (ident,1) in c.crossed:times.setdefault(ident,frame)
   self.assertEqual(c.total,2);self.assertEqual(c.crossings,[2,2,2])
   self.assertNotEqual(times[1],times[2])
   self.assertEqual(times[1]<times[2],mode=='zigzag')
 def test_geometry_switch_no_phantom(self):
  c=ThreeLineCounter();c.observe(1,50,70,101,101,.59,1)
  c.set_mode('zigzag');self.assertIsNone(c.observe(1,50,45,101,101,.59,2))
 def test_count_survives_geometry_switch(self):
  c=ThreeLineCounter();c.observe(1,50,90,101,101,.59,1);c.observe(1,50,70,101,101,.59,2)
  c.set_mode('zigzag');c.observe(1,50,60,101,101,.59,3);c.observe(1,50,40,101,101,.59,4)
  self.assertEqual(c.total,1)
 def test_perpendicular_jitter(self):
  c=ThreeLineCounter(mode='zigzag')
  for i,y in enumerate((51,49,51,49),1):c.observe(1,50,y,101,101,.59,i)
  self.assertEqual(c.total,0)
 def test_reverse_belt(self):
  c=ThreeLineCounter('Top to Bottom',mode='zigzag')
  for i,y in enumerate(range(10,91,2),1):c.observe(1,50,y,101,101,.59,i)
  self.assertEqual(c.total,1);self.assertEqual(c.crossings,[1,1,1])
 def test_simulation_modes(self):
  for mode in ('horizontal','zigzag','zigzag_reverse'):
   self.assertTrue(all(ok for _,ok in simulation_checks(mode)),(mode,simulation_checks(mode)))
if __name__=='__main__':unittest.main()
