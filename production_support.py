"""Local health history and recoverable SQLite backups. Never writes production DB."""
from contextlib import closing
from datetime import datetime,timedelta
from pathlib import Path
import json,os,re,shutil,sqlite3,tempfile,threading,time,zipfile


def activity_bins(events, start, end, observations=(),minutes=60):
    """Count activity is not conveyor availability. Missing telemetry stays unknown."""
    result=[];a=start
    while a<end:
        b=min(a+timedelta(minutes=minutes),end)
        n=sum(a<=t<b for t,*_ in events)
        seen=[r for r in observations if a<=datetime.fromisoformat(r['at'])<b]
        state='activity / camera issue' if n and any(r.get('camera')=='stale' for r in seen) else 'activity' if n else ('camera issue' if any(r.get('camera')=='stale' for r in seen) else 'no counts observed' if seen else 'unobserved')
        result.append(dict(start=a.isoformat(),end=b.isoformat(),count=n,state=state))
        a=b
    return result


def read_observations(folder,start,end):
    rows=[];day=start.date()
    while day<=end.date():
        try:
            data=json.loads((Path(folder)/(day.isoformat()+'.json')).read_text())
            if not isinstance(data,list):data=[]
            for item in data:
                try:
                    stamp=datetime.fromisoformat(item['at'])
                    if start<=stamp<=end:rows.append(item)
                except (AttributeError,KeyError,TypeError,ValueError):continue
        except (OSError,ValueError,TypeError):pass
        day+=timedelta(days=1)
    return rows


def write_observation(folder,sample):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(sample['at'][:10]+'.json')
    try:rows=json.loads(path.read_text())
    except (OSError,ValueError):rows=[]
    # One observation per minute. Historical health is separate from count history.
    if not isinstance(rows,list):rows=[]
    rows=[r for r in rows if isinstance(r,dict) and r.get('at','')[:16]!=sample['at'][:16]]+[sample]
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(rows[-1440:]),encoding='utf-8');os.replace(tmp,path)


def create_backup(db,private_config,destination,day):
    db=Path(db);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    target=destination/('TyreTrack_'+day+'.zip')
    if target.exists():return target
    if not db.is_file():raise FileNotFoundError('Production database missing')
    with tempfile.TemporaryDirectory(prefix='tyretrack-backup-') as temp:
        copy=Path(temp)/'tyretrack.db'
        with closing(sqlite3.connect(db,timeout=3)) as source,closing(sqlite3.connect(copy)) as out:
            source.backup(out,pages=128,sleep=.01)
            if out.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity failed')
        tmp=destination/(target.name+'.tmp')
        try:
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as archive:
                archive.write(copy,'data/tyretrack.db')
                config=Path(private_config)
                if config.exists():
                    for path in config.iterdir():
                        if path.is_file() and not path.is_symlink():archive.write(path,'data/private_config/'+path.name)
                archive.writestr('RESTORE_README.txt','Close TyreTrack. Keep a copy of current data. Restore data/tyretrack.db and private_config into the app data folder. This archive contains private settings: do not share publicly. Video recordings are not included.\n')
            with zipfile.ZipFile(tmp) as archive:
                if archive.testzip():raise RuntimeError('Backup ZIP validation failed')
            os.chmod(tmp,0o600);os.replace(tmp,target)
        finally:
            if tmp.exists():tmp.unlink()
    return target


class SupportService:
    def __init__(self,db,private_config,data):
        self.db=Path(db);self.private_config=Path(private_config);self.data=Path(data)
        self.lock=threading.Lock();self.thread=None;self.status={};self.last_request=-1e9
        self.last_cpu=(time.monotonic(),time.process_time())
        self.last_disk_check=-1e9;self.free_gb=None;self.backup_retry=-1e9;self.last_frames=None;self.last_success=None;self.checked_backups=set()
        self.history=self.data/'system_health';self.backups=self.data/'backups'
    def request(self,sample,force_backup=False):
        now=time.monotonic()
        with self.lock:
            if self.thread and self.thread.is_alive():return
            if not force_backup and now-self.last_request<10:return
            self.last_request=now
            self.thread=threading.Thread(target=self._run,args=(dict(sample),force_backup),daemon=True,name='TyreTrack health and backup')
            self.thread.start()
    def _record_success(self,day):
        if self.last_success==day:return
        path=self.backups/'last_success.json';tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'day':day}),encoding='utf-8');os.replace(tmp,path)
        self.last_success=day
    def _run(self,sample,force):
        status={}
        try:
            if self.last_success is None:
                try:
                    previous=json.loads((self.backups/'last_success.json').read_text())['day']
                    if re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:_close)?',previous) and (self.backups/('TyreTrack_'+previous+'.zip')).is_file():self.last_success=previous
                except (OSError,KeyError,TypeError,ValueError):pass
            now=time.monotonic();wall,cpu=self.last_cpu
            status['app_cpu']=max(0,min(100,(time.process_time()-cpu)/max(.001,now-wall)*100/max(1,os.cpu_count() or 1)))
            self.last_cpu=(now,time.process_time())
            if now-self.last_disk_check>=60 or self.free_gb is None:
                self.free_gb=shutil.disk_usage(self.data).free/1024**3;self.last_disk_check=now
            status['free_gb']=self.free_gb
            frames=sample.get('frames',0)
            if self.last_frames and frames>=self.last_frames[1]:status['processing_fps']=(frames-self.last_frames[1])/max(.001,now-self.last_frames[0])
            self.last_frames=(now,frames)
            if not sample.get('testing'):
                sample.update(app_cpu=status['app_cpu'],free_gb=status['free_gb'],processing_fps=status.get('processing_fps'))
                write_observation(self.history,sample)
                day=sample['at'][:10]+('_close' if sample['at'][11:16]>='17:05' else '')
                target=self.backups/('TyreTrack_'+day+'.zip')
                if target.exists():
                    if target not in self.checked_backups:
                        with zipfile.ZipFile(target) as archive:
                            if archive.testzip() or 'data/tyretrack.db' not in archive.namelist():raise RuntimeError('Existing backup integrity failed')
                        self.checked_backups.add(target)
                    self._record_success(day);status['backup']='Saved '+day
                elif force or now-self.backup_retry>=300:
                    self.backup_retry=now
                    if self.free_gb<2:raise RuntimeError('Backup postponed: less than 2 GB free')
                    create_backup(self.db,self.private_config,self.backups,day)
                    self._record_success(day);self.checked_backups.add(target)
                    status['backup']='Saved '+day
                else:status['backup']='Pending retry'
            else:status['backup']='Paused during test'
            status['error']=''
        except Exception as exc:status['error']=type(exc).__name__+': '+str(exc)
        status['last_backup']=self.last_success
        with self.lock:self.status=status
    def snapshot(self):
        with self.lock:return dict(self.status)
    def wait(self,timeout=3):
        thread=self.thread
        if thread:thread.join(timeout)
        return not thread or not thread.is_alive()
