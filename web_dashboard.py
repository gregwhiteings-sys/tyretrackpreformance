"""Outbound-only, opt-in summaries and safe dashboard stills; no remote controls."""
import json,os,threading,time,urllib.request
from pathlib import Path
from datetime import timezone
import tyre_weight
ORIGIN='https://tyretrack-production-live.astute-loom-2153.chatgpt.site'
URL=ORIGIN+'/api/snapshot'

def validate_config(value):
    if value.get('schema')!=1 or value.get('url')!=URL:raise ValueError('Choose the connection file downloaded from your TyreTrack web dashboard')
    token=value.get('token','')
    if not isinstance(token,str) or not 32<=len(token)<=256 or any(c.isspace() for c in token):raise ValueError('Invalid connection file')
    return dict(schema=1,url=URL,token=token,enabled=bool(value.get('enabled',False)),snapshot_enabled=bool(value.get('snapshot_enabled',False)))

def build_snapshot(live,cache,now,camera_connected=False,target=0,test_mode=False):
    if test_mode or not live or not cache:return None
    if live['day']!=now.date().isoformat() or live['hour']!=now.hour:return None
    if cache['metrics']['day_start'].date()!=now.date():return None
    v=tyre_weight.totals(live['types']);metrics=cache['metrics'];slots,best,_=cache['hourly']
    completed=[s for s in slots if s['completed']]
    start=now.replace(hour=5,minute=0,second=0,microsecond=0);end=now.replace(hour=17,minute=5,second=0,microsecond=0)
    elapsed=(min(now,end)-start).total_seconds();forecast=None
    if target and now.weekday()<5 and elapsed>=900:forecast=round(live['daily']/elapsed*(end-start).total_seconds()) if now<end else live['daily']
    return dict(schema=1,captured_at=now.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'),
        today=live['daily'],this_hour=live['current_hour'],best_hour=best['count'] if best else 0,best_day=cache['best'][1],all_time=live['all_time'],
        passenger=v['counts']['passenger'],suv=v['counts']['4x4'],truck=v['counts']['truck'],unclassified=v['unknown'],estimated_kg=v['total_kg'],epu=v['total_epu'],
        flow=metrics['flow_per_minute'],average_hour=sum(s['count'] for s in completed)/len(completed) if completed else 0,
        production_status=metrics['no_count_status'],camera_connected=bool(camera_connected),target=target or None,forecast=forecast,
        hours=[dict(label=s['start'].strftime('%H:%M'),count=s['count'],current=s['start']<=now<s['end']) for s in slots],
        days=[dict(label=s['date'].strftime('%a %d %b'),count=s['count'],current=s['current']) for s in cache['weekdays']])

class Publisher:
    def __init__(self,path,opener=None,clock=time.monotonic):
        self.path=Path(path);self.clock=clock;self.opener=opener or urllib.request.urlopen;self.config=None
        self.status='Sharing off';self.last_attempt=-1e9;self.lock=threading.Lock();self.thread=None
        try:self.config=validate_config(json.loads(self.path.read_text(encoding='utf-8')))
        except (OSError,ValueError,TypeError):pass
    def import_file(self,path):
        config=validate_config(json.loads(Path(path).read_text(encoding='utf-8')));config['enabled']=False
        self.config=config;self.save();self.status='Connection loaded; enable sharing'
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.config),encoding='utf-8');os.chmod(tmp,0o600);os.replace(tmp,self.path)
    def enable(self,enabled):
        if not self.config:raise ValueError('Load the web connection file first')
        self.config['enabled']=bool(enabled);self.save();self.status='Waiting for production statistics' if enabled else 'Sharing off'
    def request(self,data):
        if not data or not self.config or not self.config['enabled']:return False
        with self.lock:
            if self.thread is not None and self.thread.is_alive():return False
            if self.clock()-self.last_attempt<10:return False
            self.last_attempt=self.clock();config=dict(self.config);body=json.dumps(data,allow_nan=False).encode()
            def send():
                try:
                    req=urllib.request.Request(config['url'],data=body,headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json','Accept':'application/json','User-Agent':'TyreTrack-Publisher/1.0'},method='POST')
                    with self.opener(req,timeout=4) as response:
                        if response.status!=200:raise OSError('Upload failed')
                    self.status='Last update sent successfully'
                except Exception:self.status='Update failed; automatic retry (counting continues)'
            self.thread=threading.Thread(target=send,name='TyreTrack web statistics',daemon=True);self.thread.start();return True


def operator_image(full_image,rectangles):
    """Allow-list pixels from operator widgets; never publish admin settings."""
    from PyQt5.QtCore import QRect,QPoint
    from PyQt5.QtGui import QImage,QPainter,QColor,QFont
    result=QImage(full_image.size(),QImage.Format_RGB32)
    ratio=full_image.devicePixelRatio();result.setDevicePixelRatio(ratio);result.fill(QColor('#07111e'))
    painter=QPainter(result)
    for rect in rectangles:
        source=QRect(round(rect.x()*ratio),round(rect.y()*ratio),round(rect.width()*ratio),round(rect.height()*ratio)).intersected(full_image.rect())
        if not source.isEmpty():
            part=full_image.copy(source);part.setDevicePixelRatio(ratio)
            painter.drawImage(QPoint(rect.x(),rect.y()),part)
    painter.setPen(QColor('#6ee3d5'));painter.setFont(QFont('Segoe UI',17,QFont.Bold))
    painter.drawText(16,32,'TYRETRACK  |  OPERATOR DASHBOARD')
    painter.end();return result


class ImagePublisher:
    def __init__(self,publisher,clock=time.monotonic):
        self.publisher=publisher;self.clock=clock;self.last_attempt=-1e9;self.thread=None;self.lock=threading.Lock();self.status='Dashboard snapshot sharing off'
    def request(self,image,captured_at):
        config=self.publisher.config
        if not config or not config['enabled'] or not config.get('snapshot_enabled'):return False
        with self.lock:
            if self.thread is not None and self.thread.is_alive():return False
            if self.clock()-self.last_attempt<30:return False
            self.last_attempt=self.clock();config=dict(config);copy=image.copy()
            def send():
                try:
                    from PyQt5.QtCore import QBuffer,QIODevice,Qt
                    frame=copy.scaled(1280,960,Qt.KeepAspectRatio,Qt.SmoothTransformation)
                    buffer=QBuffer();buffer.open(QIODevice.WriteOnly)
                    if not frame.save(buffer,'JPEG',65):raise OSError('JPEG encoding failed')
                    body=bytes(buffer.data());buffer.close()
                    if len(body)>512*1024:raise OSError('Image too large')
                    # Sharing can be disabled while encoding; do not start a new upload.
                    current=self.publisher.config
                    if not current or not current['enabled'] or not current.get('snapshot_enabled'):return
                    req=urllib.request.Request(ORIGIN+'/api/dashboard-image',data=body,headers={'Authorization':'Bearer '+config['token'],'Content-Type':'image/jpeg','X-Captured-At':captured_at,'User-Agent':'TyreTrack-Publisher/1.0'},method='POST')
                    with self.publisher.opener(req,timeout=4) as response:
                        if response.status!=200:raise OSError('Upload failed')
                    self.status='Dashboard snapshot sent successfully'
                except Exception:self.status='Snapshot update failed; automatic retry (counting continues)'
            self.thread=threading.Thread(target=send,name='TyreTrack web JPEG',daemon=True);self.thread.start();return True
