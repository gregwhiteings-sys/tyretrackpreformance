import unittest
from three_line import ThreeLineCounter
class CountTest(unittest.TestCase):
    def drive(self, c, ident, ys, first=1):
        return [event for i,y in enumerate(ys,first) if (event:=c.observe(ident,50,y,100,101,.5,i))]
    def test_all_lines_once(self):
        c=ThreeLineCounter(); self.assertEqual(len(self.drive(c,1,[90,80,70,60,50,40,30,20,10])),1)
        self.assertEqual(c.crossings,[1,1,1]);self.assertEqual(c.recoveries,[0,0,0])
    def test_middle_recovery(self):
        c=ThreeLineCounter();self.assertEqual(self.drive(c,1,[65,55,45,30,15]),[(1,1)])
        self.assertEqual(c.recoveries,[0,1,0])
    def test_end_recovery(self):
        c=ThreeLineCounter();self.assertEqual(self.drive(c,1,[35,28,18]),[(1,2)])
    def test_jitter(self):
        c=ThreeLineCounter();self.assertFalse(self.drive(c,1,[51,49,51,49,50]))
    def test_stale(self):
        c=ThreeLineCounter();self.drive(c,1,[90]);self.assertFalse(self.drive(c,1,[70],30))
    def test_pause(self):
        c=ThreeLineCounter();self.drive(c,1,[90]);c.reset_positions();self.assertFalse(self.drive(c,1,[70]))
    def test_reverse(self):
        c=ThreeLineCounter('Top to Bottom');self.assertEqual(len(self.drive(c,1,[10,20,30,40,60,70,90])),1)
        self.assertEqual(c.crossings,[1,1,1])
    def test_two_close_tyres(self):
        c=ThreeLineCounter();self.drive(c,1,[90,70]);self.drive(c,2,[90,70]);self.assertEqual(len(c.counted),2)
    def test_unconfirmed(self):
        c=ThreeLineCounter();self.assertIsNone(c.observe(1,50,90,100,101,.5,1,False))
        self.assertIsNone(c.observe(1,50,70,100,101,.5,2))
    def test_slow_crossing(self):
        c=ThreeLineCounter();self.assertEqual(len(self.drive(c,1,[90]+[79]*30+[77])),1)
    def test_id_recovery(self):
        c=ThreeLineCounter()
        for frame,y in enumerate((90,80,70),1):
            c.begin_frame([1]);c.observe(1,50,y,100,101,.5,frame,True,(30,30))
        self.assertIn(1,c.counted)
        c.begin_frame([2]);self.assertIsNone(c.observe(2,50,60,100,101,.5,4,True,(30,30)))
        self.assertIn(2,c.counted)
        self.assertFalse(self.drive(c,2,[40,15],5))
    def test_visible_neighbour_not_merged(self):
        c=ThreeLineCounter();c.begin_frame([1]);c.observe(1,50,90,100,101,.5,1,True,(30,30))
        c.begin_frame([1,2]);c.observe(2,50,90,100,101,.5,2,True,(30,30))
        self.assertIn(1,c.records);self.assertIn(2,c.records)
if __name__=='__main__':unittest.main()

