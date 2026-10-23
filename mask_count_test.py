import unittest
import numpy as np
from mask_count import mask_centroid
from three_line import ThreeLineCounter
class Tests(unittest.TestCase):
 def test_asymmetric_polygon(self):
  p=np.array([[0,0],[12,0],[0,12]],np.float32)
  self.assertEqual(mask_centroid(p,480,270),(4.,4.))
  self.assertEqual(mask_centroid(p[::-1],480,270),(4.,4.))
 def test_invalid_masks(self):
  for p in ([],[[1,1],[2,2]],[[0,0],[1,1],[2,2]],[[0,0],[1,float('nan')],[2,2]]):self.assertIsNone(mask_centroid(p,480,270))
 def test_one_mask_three_lines_one_count(self):
  c=ThreeLineCounter(mode='horizontal')
  for f,y in enumerate(range(250,20,-2),1):
   p=np.array([[90,y-5],[110,y-5],[110,y+5],[90,y+5]])
   x,y=mask_centroid(p,480,270);c.begin_frame([7]);c.observe(7,x,y,480,270,.59,f,True,(20,10))
  self.assertEqual(c.total,1);self.assertEqual(c.crossings,[1,1,1])
 def test_distinct_overlapping_instances(self):
  c=ThreeLineCounter(mode='horizontal')
  for f,y in enumerate(range(250,20,-2),1):
   c.begin_frame([1,2])
   for ident,dx in ((1,0),(2,10)):
    point=mask_centroid([[90+dx,y-15],[120+dx,y-15],[120+dx,y+15],[90+dx,y+15]],480,270)
    c.observe(ident,*point,480,270,.59,f,True,(30,30))
  self.assertEqual(c.total,2)
if __name__=='__main__':unittest.main()
