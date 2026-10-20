import unittest
from three_line import ThreeLineCounter,line_segments
class SpanTest(unittest.TestCase):
 def test_connected_short_segments(self):
  for mode in ('horizontal','zigzag','zigzag_reverse'):
   for segment in line_segments(101,101,.5,mode=mode,left_ratio=.2,right_ratio=.8):
    self.assertEqual(segment[0],20);self.assertEqual(segment[2],80)
 def test_outside_not_counted(self):
  c=ThreeLineCounter(mode='zigzag');c.set_span(.2,.8)
  for i,y in enumerate((90,70,55,40,15),1):c.observe(1,10,y,101,101,.5,i)
  self.assertEqual(c.total,0)
 def test_inside_counted_once(self):
  c=ThreeLineCounter(mode='zigzag');c.set_span(.2,.8)
  for i,y in enumerate((90,70,55,40,15),1):c.observe(1,50,y,101,101,.5,i)
  self.assertEqual(c.total,1);self.assertEqual(c.crossings,[1,1,1])
 def test_intersection_location_used(self):
  c=ThreeLineCounter();c.set_span(.2,.8)
  c.observe(1,0,90,101,101,.5,1)
  c.observe(1,100,70,101,101,.5,2)
  self.assertEqual(c.total,1)
 def test_adjustment_no_phantom(self):
  c=ThreeLineCounter(mode='zigzag');c.observe(1,25,60,101,101,.5,1)
  c.set_span(.2,.8);c.observe(1,25,59,101,101,.5,2)
  self.assertEqual(c.total,0)
 def test_invalid(self):
  c=ThreeLineCounter()
  for left,right in ((-.1,1),(.8,.2),(.4,.45),(0,1.1)):
   with self.assertRaises(ValueError):c.set_span(left,right)
if __name__=='__main__':unittest.main()
