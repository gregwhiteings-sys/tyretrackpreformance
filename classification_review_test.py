import ast,json,tempfile,unittest,zipfile,csv,time,threading,os
from pathlib import Path
import numpy as np
from belt_width_assist import BeltSettings,BeltWidthAssist
from classification_review import ReviewStore,comparison,summary

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=ReviewStore(self.root/'review')
    def tearDown(self):self.store.close();self.temp.cleanup()
    def payload(self,scope='production'):
        return dict(timestamp='2026-11-23T08:00:00+10:00',scope=scope,original_class='passenger',assisted_class='4x4',final_class='passenger',size_candidate='4x4',diameter_mm=780,disagreement=True,mode='compare')
    def test_compare_only_counterfactual(self):
        a=BeltWidthAssist(BeltSettings(observe_only=True));l,r=a.edges(200,640,360);bw=(r-l)*.76;cx=(l+r)/2;b=(cx-bw/2,200-bw*.35,cx+bw/2,200+bw*.35)
        for f in range(7):a.observe(1,b,[(1,b)],640,360,f)
        p=comparison(a,1,6,'passenger',.6,'passenger','compare',{'width_mm':1100})
        self.assertEqual(p['assisted_class'],'4x4');self.assertEqual(p['final_class'],'passenger');self.assertTrue(p['disagreement'])
        self.assertEqual(a.resolve(1,6,'passenger',.6)[0],'passenger')
    def test_scope_dedup_and_original_evidence(self):
        image=np.zeros((20,30,3),dtype=np.uint8);image[:,:,1]=120
        self.store.submit('tyre',self.payload(),image,key='same')
        self.store.submit('tyre',self.payload('test'),None,key='test')
        self.store.submit('tyre',self.payload('replay'),None,key='replay')
        self.assertTrue(self.store.flush());r=self.store.rows()[0];data=self.store.image_path(r).read_bytes()
        changed=self.payload();changed['original_class']='4x4'
        self.store.submit('tyre',changed,np.ones_like(image)*255,key='same');self.store.flush()
        rows=self.store.rows();self.assertEqual(len(rows),1);self.assertEqual(rows[0]['payload']['original_class'],'passenger');self.assertEqual(self.store.image_path(rows[0]).read_bytes(),data)
        self.assertEqual(len(self.store.rows(scope='test')),1);self.assertEqual(len(self.store.rows(scope='replay')),1)
        self.store.review('same','4x4',notes='Verified physically')
        self.assertEqual(self.store.rows()[0]['payload']['original_class'],'passenger')
    def test_review_labels_and_export(self):
        for key,status in [('false','false_alert'),('true','confirmed_foreign'),('unsure','unsure'),('pending','unreviewed')]:
            p={'timestamp':'2026-11-23T10:00:00+10:00','predicted_class':'metal_object','box':[0,0,10,10],'clean_inference_image':True}
            self.store.submit('foreign',p,np.zeros((30,40,3),dtype=np.uint8),key=key)
        self.store.flush();self.store.review('false','false_alert','normal_tyre','Rubber-only tyre, no metal')
        self.store.review('true','confirmed_foreign',notes='Loose metal rim');self.store.review('unsure','unsure')
        with self.assertRaises(ValueError):self.store.review('false','false_alert','')
        out=self.root/'reviewed.zip';self.store.export(out)
        with zipfile.ZipFile(out) as z:
            entries=json.loads(z.read('review_manifest.json'));self.assertEqual({r['id'] for r in entries},{'false','true'})
            self.assertEqual(len([n for n in z.namelist() if n.startswith('images/')]),2)
            self.assertIn('NOT A READY-TO-TRAIN',z.read('README.txt').decode());self.assertFalse(any(n.endswith('.txt') and n.startswith('labels/') for n in z.namelist()))
        self.assertEqual(summary(self.store.rows())['false_alerts'],1)
        self.store.review('false','unsure');self.assertEqual(summary(self.store.rows())['false_alerts'],0)
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM review_history WHERE record_id="false"').fetchone()[0],2)
    def test_daily_summary_counts_same_tyres(self):
        self.store.submit('tyre',self.payload(),key='one');self.store.submit('tyre',self.payload('test'),key='test')
        self.assertTrue(self.store.close())
        data=json.loads((self.store.root/'daily/2026-11-23_summary.json').read_text())
        self.assertEqual(data['tyres'],1);self.assertEqual(data['original_counts'],{'passenger':1});self.assertEqual(data['assisted_counts'],{'4x4':1});self.assertEqual(data['final_counts'],{'passenger':1})
        self.assertTrue((self.store.root/'daily/2026-11-23_summary.csv').exists())
    def test_gui_heartbeat_with_blocked_writer(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QTimer,QEventLoop
        app=QApplication.instance() or QApplication([]);entered=threading.Event();release=threading.Event();real=self.store._write
        def blocked(*args):entered.set();release.wait(2);real(*args)
        self.store._write=blocked
        self.store.submit('tyre',self.payload(),key='async');self.assertTrue(entered.wait(1))
        beats=[];timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:beats.append(1));timer.start()
        loop=QEventLoop();QTimer.singleShot(100,loop.quit);loop.exec_();timer.stop();release.set();self.assertTrue(self.store.flush());self.assertGreaterEqual(len(beats),3)
    def test_actual_ui_and_worker_wiring(self):
        tree=ast.parse(Path('TyreTrack_Production_Monitor.py').read_text())
        worker=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CounterWorker');run=next(n for n in worker.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        event=next(n for n in ast.walk(run) if isinstance(n,ast.If) and ast.unparse(n.test).startswith('event and'))
        body=ast.unparse(event)
        self.assertLess(body.index('log_count('),body.index('self.pending_comparisons['));self.assertEqual(body.count('log_count('),1)
        self.assertIn("scope='test' if self.manual_test else 'production'",body)
        main=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Main');alarm=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='on_foreign_alarm')
        body=ast.unparse(alarm);self.assertIn("event['frame'].copy()",body);self.assertIn("clean_inference_image=True",body)
        ui=Path('classification_review_ui.py').read_text();self.assertIn('threading.Thread',ui);self.assertIn('false_alert',ui)

if __name__=='__main__':unittest.main()
