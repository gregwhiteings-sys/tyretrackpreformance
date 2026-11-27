"""Real model contract, bounded async work, private review state and count isolation."""
import csv,hashlib,json,sqlite3,tempfile,threading,time
from pathlib import Path
from contextlib import closing
import numpy as np
from candidate_trial import Predictor,Trial,Store,MODEL_SHA,crop_context

image=np.zeros((80,120,3),np.uint8);image[::2]=230
def payload(track=1,**kwargs):
    return dict(timestamp='2026-11-27T09:00:00+10:00',scope='production',session_id='fixture',track_id=track,
                original_class='passenger',final_class='passenger',candidate_context={},**kwargs)
class Fake:
    def __init__(self,path):pass
    def predict(self,image):return '4x4',.95

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);production=root/'counts.db'
    with closing(sqlite3.connect(production)) as c:c.execute('CREATE TABLE counts(n INTEGER)');c.execute('INSERT INTO counts VALUES(7)');c.commit()
    before=hashlib.sha256(production.read_bytes()).hexdigest()
    trial=Trial(root/'trial','unused',predictor_factory=Fake)
    p=payload();assert trial.submit(p,image);assert not trial.submit(p,image)
    assert not trial.submit(dict(payload(99),scope='test'),image)
    for track,im,context in [(2,image,{'reason':'overlap'}),(3,image[:20],{}),(4,None,{}),(5,np.zeros_like(image),{})]:
        q=payload(track);q['candidate_context']=context;assert trial.submit(q,im)
    assert trial.close();rows=trial.store.rows('2026-11-27');assert len(rows)==5,rows
    row=next(r for r in rows if r['track_id']=='1');assert row['production_class']=='passenger' and row['candidate_class']=='4x4'
    assert row['model_sha']==MODEL_SHA and row['image']
    assert {r['reason'] for r in rows}>={'overlap','small_crop','no_crop','low_contrast'}
    s=trial.store.summary('2026-11-27');assert s['records']==5 and s['accepted']==1 and s['disagreements']==1 and s['unknown']==4
    trial.store.review(row['id'],'passenger','Greg','Known vehicle origin')
    s=trial.store.summary('2026-11-27');assert (s['verified'],s['original_verified_correct'],s['candidate_verified_correct'])==(1,1,0)
    trial.store.save(p,dict(candidate_class='passenger',raw_class='passenger',confidence=.99,reason=''))
    saved=next(r for r in trial.store.rows('2026-11-27') if r['track_id']=='1')
    assert saved['candidate_class']=='4x4' and saved['human_label']=='passenger','Duplicate overwrite changed evidence'
    trial.store.export(root/'export.csv','2026-11-27');assert len(list(csv.DictReader((root/'export.csv').open(encoding='utf-8-sig'))))==5
    assert not trial.store.rows('2026-11-26')
    assert hashlib.sha256(production.read_bytes()).hexdigest()==before
    bad=root/'bad.onnx';bad.write_bytes(b'not-the-candidate')
    failed=Trial(root/'failed',bad);assert failed.submit(payload(),image);assert failed.close()
    assert failed.store.rows('2026-11-27')[0]['reason']=='model_unavailable'
    assert failed.snapshot()['error'] and hashlib.sha256(production.read_bytes()).hexdigest()==before

with tempfile.TemporaryDirectory() as tmp:
    started=threading.Event();release=threading.Event()
    class Blocked:
        def __init__(self,path):pass
        def predict(self,image):started.set();assert release.wait(5);return 'passenger',.95
    t=Trial(Path(tmp)/'queue','unused',predictor_factory=Blocked);assert t.submit(payload(),image);assert started.wait(2)
    start=time.monotonic();accepted=[t.submit(payload(n),image) for n in range(2,25)]
    assert time.monotonic()-start<.5,'Submitting blocked the count thread'
    assert t.dropped>0 and sum(accepted)<=8
    assert not t.close(.01);release.set();t.thread.join(3)
    assert not t.thread.is_alive() and not t.store.db.exists(),'Late inference wrote after aborted shutdown'

box=[100,100,220,180];boxes=[box,[180,110,250,190]]
assert crop_context(box,boxes,480,270,0)['reason']=='overlap'
assert crop_context(box,[box],480,270,0)['reason']==''
assert crop_context([0,100,120,180],[[0,100,120,180]],480,270,0)['reason']=='edge_truncated'

# Test the actual packaged model and exact RGB/padding contract.
path=Path(__file__).parent/'candidate_classifier/best.onnx';model=Predictor(path)
name,score=model.predict(image);assert name in ('passenger','4x4') and 0<=score<=1
class Session:
    def run(self,outputs,feed):
        tensor=feed['images'];assert tensor.shape==(1,3,224,224) and tensor.dtype==np.float32
        assert tensor[0,0,112,112]==1 and tensor[0,1,112,112]==0 and tensor[0,2,112,112]==0
        assert abs(float(tensor[0,0,0,0])-30/255)<1e-6
        return [np.asarray([[.1,.9]],np.float32)]
probe=Predictor.__new__(Predictor);probe.session=Session();probe.input='images'
red=np.zeros((80,120,3),np.uint8);red[:,:,2]=255
assert probe.predict(red)[0]=='4x4'
print('PASS real batch-1 classifier/hash and RGB padding, unique counted comparisons, unknown gates, human review/CSV, nonblocking bounded queue, shutdown isolation, corrupt model and unchanged production DB')
