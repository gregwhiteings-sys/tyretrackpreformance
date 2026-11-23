"""Observational overlap candidates from existing tracked tyre boxes.
Overlap of rectangles is a heuristic, not proof of physical overlap or hidden count.
Only explicit post-commit count callbacks establish that a track was counted.
"""
from itertools import combinations

class OverlapReview:
    def __init__(self,store,session,scope='production',source='',stable_frames=3,retire_frames=90):
        self.store=store;self.session=session;self.scope=scope;self.source=source
        self.stable=stable_frames;self.retire=retire_frames
        self.pairs={};self.active=[];self.counts={};self.last_seen={};self.sequence=0
        self.on_evidence=None
    def evidence(self,payload,image=None):
        if self.on_evidence is not None:
            try:self.on_evidence(payload,image)
            except Exception:pass # Recording evidence must not interrupt count/review logic.
    def counted(self,track_id,timestamp,tyre_type):
        self.counts[int(track_id)]=dict(track_id=int(track_id),timestamp=timestamp,tyre_type=tyre_type)
    @staticmethod
    def overlaps(a,b):
        x=max(0,min(a[2],b[2])-max(a[0],b[0]));y=max(0,min(a[3],b[3])-max(a[1],b[1]))
        area=min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1]))
        return area>0 and x*y/area>=.20
    def observe(self,detections,frame_no,timestamp,image=None,frame_sequence=None,recording_reference=None,confidence=.35,counting_active=True):
        # The worker supplies accepted tyre boxes only. Bound the pair work.
        ds=[d for d in detections if d[5]>=confidence and d[6]!='unknown'][:24]
        for d in detections:self.last_seen[int(d[4])]=frame_no
        visible=set();components=[]
        for a,b in combinations(ds,2):
            if a[4]==b[4] or not self.overlaps(a,b):continue
            pair=tuple(sorted((int(a[4]),int(b[4]))));visible.add(pair)
            last,hits=self.pairs.get(pair,(-2,0));hits=hits+1 if last==frame_no-1 else 1
            self.pairs[pair]=(frame_no,hits)
            if hits>=self.stable:
                group=set(pair);joining=[g for g in components if g&group]
                for g in joining:group|=g;components.remove(g)
                components.append(group)
        self.pairs={k:v for k,v in self.pairs.items() if k in visible}
        for group in components:
            existing=[event for event in self.active if event['ids']&group]
            if existing:
                target=existing[0]
                for event in existing[1:]:
                    target['ids']|=event['ids'];self.active.remove(event)
                target['ids']|=group;target['last_overlap']=timestamp
            elif len(self.active)<8:
                self.sequence+=1
                self.active.append(dict(ids=group,timestamp=timestamp,last_overlap=timestamp,first_frame=frame_no,
                    counting_active_at_start=bool(counting_active),image=image.copy() if image is not None else None,
                    snapshot_track_ids=sorted(group),snapshot_boxes=[list(map(int,d[:5])) for d in ds if d[4] in group],
                    frame_sequence=frame_sequence,recording_reference=str(recording_reference) if recording_reference else None,
                    key=f'{self.session}-overlap-{self.sequence}'))
                event=self.active[-1]
                self.evidence(dict(kind='overlap_start',event_id=event['key'],timestamp=timestamp,
                    scope=self.scope,track_ids=sorted(group),frame_sequence=frame_sequence,
                    recording_reference=event['recording_reference'],counting_active=bool(counting_active)),image)
        for event in list(self.active):
            if len(event['ids'])>24 or frame_no-event['first_frame']>900:
                self._save(event,'review_window_limit');self.active.remove(event);continue
            if all(frame_no-self.last_seen.get(i,frame_no)>self.retire for i in event['ids']):
                self._save(event,'tracks_retired');self.active.remove(event)
        # IDs already counted are session history. Forget stale non-counted IDs.
        live=set().union(*(e['ids'] for e in self.active)) if self.active else set()
        self.last_seen={i:n for i,n in self.last_seen.items() if frame_no-n<=self.retire or i in live}
        self.counts={i:v for i,v in self.counts.items() if i in self.last_seen}
    def _save(self,event,reason):
        ids=sorted(event['ids']);counted=[i for i in ids if i in self.counts];missing=sorted(set(ids)-set(counted))
        payload=dict(timestamp=event['timestamp'],last_overlap=event['last_overlap'],scope=self.scope,source=self.source,
            session_id=self.session,track_ids=ids,counted_track_ids=counted,not_counted_track_ids=missing,
            count_events=[self.counts[i] for i in counted],observed_tracks=len(ids),counted_tracks=len(counted),
            association_status='all_observed_tracks_counted' if not missing else 'needs_review',
            counting_active_at_start=event['counting_active_at_start'],detection_method='tracked_box_overlap_heuristic',termination_reason=reason,
            snapshot_track_ids=event['snapshot_track_ids'],frame_sequence=event['frame_sequence'],
            recording_reference=event['recording_reference'],
            limitation='Box overlap is a candidate only. Hidden/untracked tyres and tracker ID switches are not resolved. No automatic count correction.')
        image=event['image']
        self.evidence(dict(payload,kind='overlap_complete',event_id=event['key']))
        if image is not None:
            import cv2
            for x1,y1,x2,y2,ident in event['snapshot_boxes']:
                cv2.rectangle(image,(x1,y1),(x2,y2),(0,220,255),2)
                cv2.putText(image,f'OVERLAP REVIEW ID {ident}',(max(0,x1),max(15,y1-4)),cv2.FONT_HERSHEY_SIMPLEX,.4,(0,220,255),1)
        self.store.submit('overlap',payload,image,key=event['key'])
    def finish(self,reason='session_stopped'):
        for event in self.active:self._save(event,reason)
        self.active.clear();self.pairs.clear()
