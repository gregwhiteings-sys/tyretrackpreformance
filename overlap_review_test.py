"""Real persistence and late count links, isolated from production counts."""
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
from overlap_review import OverlapReview
from classification_review import ReviewStore,summary
D=[(10,10,110,110,1,.9,'passenger'),(60,40,160,140,2,.9,'4x4')]
image=np.zeros((200,200,3),dtype=np.uint8)
with TemporaryDirectory() as tmp:
 store=ReviewStore(Path(tmp)/'review');engine=OverlapReview(store,'session',retire_frames=3)
 for f in range(1,4):engine.observe(D,f,'2026-11-23T08:00:00+10:00',image,f,'recording.mp4')
 assert len(engine.active)==1
 engine.counted(1,'2026-11-23T08:00:01+10:00','passenger')
 engine.observe([],4,'2026-11-23T08:00:02+10:00')
 engine.counted(2,'2026-11-23T08:00:03+10:00','4x4')
 for f in range(5,8):engine.observe([],f,'2026-11-23T08:00:04+10:00')
 assert store.flush();rows=store.rows('2026-11-23',kind='overlap');assert len(rows)==1
 p=rows[0]['payload'];assert p['counted_track_ids']==[1,2] and not p['not_counted_track_ids']
 assert p['association_status']=='all_observed_tracks_counted' and len(p['count_events'])==2
 assert store.image_path(rows[0]).is_file()
 engine.finish();engine.finish();assert store.flush();assert len(store.rows(kind='overlap'))==1
 store.review(rows[0]['id'],'confirmed_overlap');assert store.rows(kind='overlap')[0]['status']=='confirmed_overlap'
 other=OverlapReview(store,'other',scope='test',stable_frames=2)
 for f in range(2):other.observe(D,f,'2026-11-23T09:00:00+10:00',image,counting_active=False)
 other.counted(1,'2026-11-23T09:00:01+10:00','passenger');other.finish()
 assert store.flush();p=store.rows(scope='test')[0]['payload']
 assert p['not_counted_track_ids']==[2] and p['association_status']=='needs_review' and p['counting_active_at_start'] is False
 assert summary(store.rows())['tyres']==0 and summary(store.rows())['overlap_events']==1
 transient=OverlapReview(store,'short');transient.observe(D,0,'2026-11-23T10:00:00+10:00');transient.observe([],1,'2026-11-23T10:00:01+10:00');transient.finish()
 assert store.close();assert len(store.rows(kind='overlap'))==1
print('PASS stable candidates, late real count links, missing-count uncertainty, production/test isolation, images, no duplicate records')
