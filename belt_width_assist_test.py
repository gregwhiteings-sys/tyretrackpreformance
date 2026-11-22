"""Size-assist behavior and real worker event/UI wiring, without camera hardware."""
import ast, math, unittest
from pathlib import Path
from belt_width_assist import BeltSettings,BeltWidthAssist

class TestBelt(unittest.TestCase):
    def track(self, ratio=.57, count=7, settings=None, track=1):
        a=BeltWidthAssist(settings);w,h=640,360;cy=200
        l,r=a.edges(cy,w,h);bw=(r-l)*ratio;cx=(l+r)/2
        box=(cx-bw/2,cy-bw*.35,cx+bw/2,cy+bw*.35)
        for f in range(count):a.observe(track,box,[(track,box)],w,h,f)
        return a,box
    def test_diameter_and_sensitivity(self):
        for belt in [1000,1100,1200]:
            a,_=self.track(settings=BeltSettings(width_mm=belt))
            self.assertAlmostEqual(a.evidence(1,6)['diameter_mm'],.57*belt)
    def test_support_and_fallback(self):
        a,_=self.track();self.assertEqual(a.resolve(1,6,'4x4',.65),('passenger',.65,True))
        self.assertEqual(a.resolve(1,6,'4x4',.9),('4x4',.9,False))
        self.assertEqual(a.resolve(1,6,'unknown',0),('unknown',0,False))
        self.assertEqual(a.resolve(1,6,'truck',.6),('truck',.6,False))
        a,_=self.track(.76);self.assertEqual(a.resolve(1,6,'passenger',.6)[0],'4x4')
        for ratio in [.65,.86]:
            a,_=self.track(ratio);self.assertIsNone(a.evidence(1,6)['candidate'])
        a,_=self.track(settings=BeltSettings(observe_only=True))
        self.assertFalse(a.resolve(1,6,'4x4',.6)[2])
    def test_required_frames_duplicate_and_stale(self):
        a,box=self.track(count=4);self.assertIsNone(a.evidence(1,3))
        for _ in range(8):a.observe(1,box,[(1,box)],640,360,3)
        self.assertIsNone(a.evidence(1,3))
        a.observe(1,box,[(1,box)],640,360,4)
        self.assertIsNotNone(a.evidence(1,4));self.assertIsNone(a.evidence(1,10))
        a.forget(1);self.assertIsNone(a.evidence(1,4))
    def test_occlusion_tilt_confidence_clipping(self):
        for change in ['nested','intersect','upright','edge','confidence']:
            a,b=self.track();others=[(1,b)];box=b;conf=True
            if change=='nested':others.append((2,(b[0]+5,b[1]+5,b[2]-5,b[3]-5)))
            if change=='intersect':others.append((2,(b[0]+20,b[1],b[2]+20,b[3])))
            if change=='upright':box=(280,140,350,240)
            if change=='edge':box=(0,140,150,240)
            if change=='confidence':conf=False
            a.observe(1,box,others,640,360,7,conf)
            self.assertIsNone(a.evidence(1,7),change)
    def test_disabled_invalid_unstable(self):
        for c in [BeltSettings(enabled=False),BeltSettings(left_top=.8,right_top=.2),BeltSettings(width_mm=math.nan)]:
            a,_=self.track(settings=c);self.assertIsNone(a.evidence(1,6))
        a,b=self.track();l,r=a.edges(200,640,360);bw=(r-l)*.73;cx=(l+r)/2
        box=(cx-bw/2,200-bw*.35,cx+bw/2,200+bw*.35)
        a.observe(1,box,[(1,box)],640,360,7);self.assertIsNone(a.evidence(1,7))
    def test_worker_count_and_display_use_same_resolver(self):
        tree=ast.parse(Path('TyreTrack_Production_Monitor.py').read_text())
        worker=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CounterWorker')
        run=next(n for n in worker.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        calls=[n for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='resolve']
        self.assertEqual(len(calls),2)
        # Execute the actual event-time resolver assignment extracted from the worker.
        event=next(n for n in ast.walk(run) if isinstance(n,ast.If) and ast.unparse(n.test).startswith('event and'))
        assign=next(n for n in event.body if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='resolve')
        a,_=self.track();ns={'self':type('Worker',(),{'belt_assist':a,'processing_frame':6})(), 'track_id':1,'tyre_type':'4x4','class_conf':.65}
        exec(compile(ast.Module(body=[assign],type_ignores=[]),'<actual worker event>','exec'),ns)
        self.assertEqual(ns['tyre_type'],'passenger');self.assertTrue(ns['size_changed'])
        main=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Main')
        config=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='belt_size_settings')
        code=compile(ast.Module(body=[config],type_ignores=[]),'<actual UI settings>','exec');ns={'BeltSettings':BeltSettings};exec(code,ns)
        class Control:
            def __init__(self,v):self.v=v
            def value(self):return self.v
            def isChecked(self):return self.v
        ui=type('UI',(),{'belt_enabled':Control(True),'belt_observe':Control(False),'belt_width':Control(1200),'belt_edges':[(k,Control(v)) for k,v in [('left_top',440),('right_top',610),('left_bottom',215),('right_bottom',775)]]})()
        self.assertEqual(ns['belt_size_settings'](ui).width_mm,1200)

if __name__=='__main__':unittest.main()
