"""Production-only clean training evidence; called on the existing recorder thread.

Stream-copy H264 already encoded on OAK. No inference, PC encoding, count writes
or automatic deletion. UI/inference threads only enqueue bounded event evidence.
"""
import json,queue,shutil,time
from pathlib import Path
from oak_recording import EncodedRecorder

class TrainingRecorder:
    def __init__(self,folder,log,fps=15,quota_gb=25,min_free_gb=10,
                 disk_usage=shutil.disk_usage,clock=time.monotonic,segment_seconds=900):
        self.folder=Path(folder);self.log=log;self.quota=int(quota_gb*1024**3)
        self.min_free=int(min_free_gb*1024**3);self.disk_usage=disk_usage;self.clock=clock
        self.events=queue.Queue(maxsize=32);self.dropped=0;self.state='waiting for production'
        self.last_check=-float('inf');self.storage_ok=False;self.last_baseline=-float('inf')
        self.recorder=EncodedRecorder(self.folder,log,fps,segment_seconds,self._finalized)
        self.failed=False
        self.recorded_events=set()

    @property
    def path(self):
        return str(self.recorder.path.with_suffix('.mp4')) if self.recorder.path else None

    def submit(self,payload,image=None):
        # No filesystem work or blocking on the processing thread. A bounded queue
        # prevents a stalled disk from exhausting memory.
        event_id=payload.get('event_id')
        completion=payload.get('kind')=='overlap_complete' and event_id in self.recorded_events
        if payload.get('scope')!='production' or (self.state!='recording' and not completion):return False
        try:
            self.events.put_nowait((dict(payload),image.copy() if image is not None else None))
            if payload.get('kind')=='overlap_start':
                if len(self.recorded_events)>2048:self.recorded_events.clear()
                self.recorded_events.add(event_id)
            if completion:self.recorded_events.discard(event_id)
            return True
        except queue.Full:self.dropped+=1;return False

    def _storage(self,force=False):
        now=self.clock()
        if not force and now-self.last_check<15:return self.storage_ok
        self.last_check=now
        try:
            self.folder.mkdir(parents=True,exist_ok=True)
            free=self.disk_usage(self.folder).free
            used=sum(p.stat().st_size for p in self.folder.rglob('*') if p.is_file())
            self.storage_ok=free>=self.min_free and used<self.quota
            if not self.storage_ok:self.state='paused: low space' if free<self.min_free else 'paused: 25 GB training quota'
        except OSError as exc:
            self.storage_ok=False;self.state='paused: storage error';self.log(f'Automatic training recording storage check: {exc}')
        return self.storage_ok

    def feed(self,data,stamp,sequence,production_active,enabled=True):
        try:
            if not enabled or not production_active:
                self.recorder.feed(data,stamp,sequence,enabled=False)
                self.state='off' if not enabled else 'waiting for production'
            elif self.failed:
                self.state='paused: recording error'
            elif self._storage():
                self.recorder.feed(data,stamp,sequence)
                self.state='recording' if self.path else 'waiting for keyframe'
            else:self.recorder.feed(data,stamp,sequence,enabled=False)
            self._drain()
        except Exception as exc:
            self.failed=True;self.state='paused: recording error'
            self.log(f'Automatic training recording paused; counting continues: {exc}')
            try:self.recorder.close()
            except Exception:pass

    def _append(self,stamp,record):
        day=str(stamp)[:10];folder=self.folder/day;folder.mkdir(parents=True,exist_ok=True)
        with (folder/'training_events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(record,allow_nan=False)+'\n')

    def _drain(self):
        # Bound each pass so camera packets continue draining during event bursts.
        for _ in range(4):
            try:payload,image=self.events.get_nowait()
            except queue.Empty:break
            try:
                stamp=payload['timestamp'];payload['label_status']='unreviewed'
                payload['clean_image']=image is not None;payload['confirmed_belt_width_mm']=1180
                payload['recording_reference']=payload.get('recording_reference') or self.path
                if image is not None:
                    import cv2,uuid
                    day=self.folder/str(stamp)[:10];day.mkdir(parents=True,exist_ok=True)
                    p=day/('clean_'+uuid.uuid4().hex+'.jpg')
                    if not cv2.imwrite(str(p),image,[cv2.IMWRITE_JPEG_QUALITY,95]):raise OSError('Clean snapshot write failed')
                    payload['clean_snapshot']=str(p.relative_to(self.folder))
                self._append(stamp,payload)
            finally:self.events.task_done()

    def _finalized(self,path,started,frames,fps,gaps):
        record=dict(kind='segment',recording_reference=str(path),timestamp=started.isoformat(),
                    frames=frames,fps=fps,duration_seconds=frames/fps,packet_gap_count=gaps,
                    clean_video=True,scope='production',confirmed_belt_width_mm=1180,
                    timing='Brisbane host packet-receipt time; offset approximate, not frame-synchronised count proof')
        path.with_suffix('.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        self._append(started.isoformat(),record)

    def close(self):
        try:
            while not self.events.empty():self._drain()
            self.recorder.close()
        except Exception as exc:self.log(f'Automatic training recording close: {exc}')
