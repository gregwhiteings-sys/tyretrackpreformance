"""Shift-end hour-meter records and read-only production-rate calculation."""
import csv,hashlib,io,json,math,re,sqlite3,uuid,zipfile
from pathlib import Path
from contextlib import contextmanager,closing
from datetime import date,datetime,timedelta
from hourly_dashboard import BRISBANE,brisbane_now

def previous_shift(day):
    d=date.fromisoformat(str(day))-timedelta(days=1)
    while d.weekday()>=5:d-=timedelta(days=1)
    return d.isoformat()

class HoursStore:
    def __init__(self,root):self.root=Path(root);self.db=self.root/'hours.sqlite3'
    @contextmanager
    def connect(self):
        self.root.mkdir(parents=True,exist_ok=True)
        c=sqlite3.connect(self.db,timeout=3);c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE IF NOT EXISTS readings(day TEXT PRIMARY KEY,meter REAL,checked INTEGER NOT NULL DEFAULT 0,opening REAL,notes TEXT NOT NULL DEFAULT "",updated TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS documents(day TEXT,name TEXT,path TEXT UNIQUE,sha TEXT UNIQUE)')
        c.execute('CREATE TABLE IF NOT EXISTS history(day TEXT,at TEXT,before_json TEXT,after_json TEXT)')
        try:yield c;c.commit()
        except Exception:c.rollback();raise
        finally:c.close()
    def rows(self):
        if not self.db.exists():return []
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM readings ORDER BY day DESC')]
    def documents(self,day):
        if not self.db.exists():return []
        with self.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM documents WHERE day=? ORDER BY name',(day,))]
    def attach(self,day,paths):
        date.fromisoformat(day)
        for p in paths:
            p=Path(p);self._document(day,p.name,p.read_bytes())
    def _document(self,day,name,raw):
        if len(raw)>15*1024*1024:raise ValueError('Photo exceeds 15 MB')
        if Path(name).suffix.lower() not in {'.jpg','.jpeg','.png','.webp'}:raise ValueError('Choose photo files')
        sha=hashlib.sha256(raw).hexdigest();target=self.root/'photos'/day/(sha[:16]+Path(name).suffix.lower())
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        with self.connect() as c:
            c.execute('INSERT OR IGNORE INTO documents VALUES(?,?,?,?)',(day,Path(name).name,str(target.relative_to(self.root)),sha))
            c.execute('INSERT OR IGNORE INTO readings(day) VALUES(?)',(day,))
    def import_zip(self,path):
        """Photos stay local. Proposed CSV readings always require operator checking."""
        with zipfile.ZipFile(path) as z:
            photos=[i for i in z.infolist() if Path(i.filename).suffix.lower() in {'.jpg','.jpeg','.png','.webp'}]
            if len(photos)>500 or sum(i.file_size for i in photos)>150*1024*1024:raise ValueError('Photo package exceeds import limits')
            if any(i.file_size>15*1024*1024 for i in photos):raise ValueError('A photo exceeds 15 MB')
            for item in photos:
                m=re.search(r'(20\d{2})(\d{2})(\d{2})',Path(item.filename).name)
                if not m:continue
                day=date(*map(int,m.groups())).isoformat();self._document(day,item.filename,z.read(item))
            proposed=0
            if 'meter_readings.csv' in z.namelist():
                for r in csv.DictReader(io.StringIO(z.read('meter_readings.csv').decode('utf-8-sig'))):
                    day=date.fromisoformat(r['day']).isoformat();meter=float(r['meter'])
                    if not math.isfinite(meter) or not 0<=meter<=1e7:raise ValueError('Invalid proposed meter reading')
                    with self.connect() as c:
                        c.execute('INSERT OR IGNORE INTO readings(day) VALUES(?)',(day,))
                        c.execute('UPDATE readings SET meter=? WHERE day=? AND checked=0',(meter,day))
                    proposed+=1
        return len(photos),proposed
    def save(self,day,meter,notes='',opening=None,now=None):
        d=date.fromisoformat(day);today=(now or brisbane_now()).date()
        if d>today:raise ValueError('A completed shift cannot be in the future')
        if d.weekday()>=5:raise ValueError('This production dashboard uses Monday-Friday shifts')
        meter=float(meter)
        if not math.isfinite(meter) or not 0<=meter<=1e7:raise ValueError('Enter a valid cumulative hour-meter reading')
        if opening is not None:
            opening=float(opening)
            if not notes.strip():raise ValueError('Explain the manually entered opening reading or meter reset in Notes')
            if not math.isfinite(opening) or opening<0 or opening>meter:raise ValueError('Opening meter must not exceed closing meter')
        with self.connect() as c:
            prior=c.execute('SELECT * FROM readings WHERE day=? AND checked=1',(previous_shift(day),)).fetchone()
            if opening is None and prior and meter<prior['meter']:raise ValueError('Meter went backwards; check the photo or record a reset/opening reading')
            start=opening if opening is not None else prior['meter'] if prior else None
            if start is not None and meter-start>24:raise ValueError('More than 24 running hours in one shift; check the reading')
            # Changing yesterday must not silently invalidate tomorrow's reading.
            future=c.execute('SELECT * FROM readings WHERE day>? AND checked=1 ORDER BY day LIMIT 1',(day,)).fetchone()
            if future and previous_shift(future['day'])==day and future['opening'] is None and meter>future['meter']:
                raise ValueError('Reading exceeds the following checked meter reading')
            old=c.execute('SELECT * FROM readings WHERE day=?',(day,)).fetchone();stamp=brisbane_now().isoformat()
            c.execute('INSERT OR REPLACE INTO readings VALUES(?,?,1,?,?,?)',(day,meter,opening,notes[:2000],stamp))
            new=dict(day=day,meter=meter,opening=opening,notes=notes[:2000],checked=1)
            c.execute('INSERT INTO history VALUES(?,?,?,?)',(day,stamp,json.dumps(dict(old)) if old else 'null',json.dumps(new)))

def recorded_tyres(db,source,day,now=None):
    """Same Brisbane weekday 05:00–17:05 production window; no test sources."""
    now=(now or brisbane_now()).astimezone(BRISBANE);d=date.fromisoformat(day)
    if d.weekday()>=5 or d>now.date() or not Path(db).exists():return None
    start=datetime.combine(d,datetime.min.time(),BRISBANE).replace(hour=5)
    end=min(start.replace(hour=17,minute=5),now)
    if end<=start:return None
    with closing(sqlite3.connect(db,timeout=3)) as c:
        n=c.execute('SELECT COUNT(*) FROM counts WHERE source=? AND metric_utc>=? AND metric_utc<?',(source,start.timestamp(),end.timestamp())).fetchone()[0]
        rows=c.execute('SELECT ts FROM counts WHERE source=? AND metric_utc IS NULL AND ts>=? AND ts<?',(source,(d-timedelta(days=1)).isoformat(),(d+timedelta(days=2)).isoformat())).fetchall()
    for (ts,) in rows:
        try:
            t=datetime.fromisoformat(ts)
            if t.tzinfo is None:t=t.replace(tzinfo=BRISBANE)
            if start<=t<end:n+=1
        except (ValueError,TypeError):continue
    return n if n else None # Absence of recorded counts is not proof of zero throughput.

def performance(rows,day,db,source,now=None):
    checked={r['day']:r for r in rows if r['checked'] and r['meter'] is not None}
    r=checked.get(day)
    if r is None:return dict(day=day,status='Check shift-end meter reading',hours=None,tyres=None,rate=None)
    p=checked.get(previous_shift(day));opening=r['opening'] if r['opening'] is not None else p['meter'] if p else None
    result=dict(day=day,meter=r['meter'],opening=opening,hours=None,tyres=None,rate=None,status='Previous shift reading missing')
    if opening is None:return result
    hours=round(r['meter']-opening,4)
    if not 0<=hours<=24:result['status']='Check meter readings';return result
    result['hours']=hours
    if hours==0:result['status']='No running hours recorded';return result
    n=recorded_tyres(db,source,day,now);result['tyres']=n
    if n is None:result['status']='No production counts available for this shift';return result
    result.update(rate=n/hours,status='Recorded tyres / actual running hours')
    return result

def latest(root,db,source,now=None):
    now=now or brisbane_now();rows=HoursStore(root).rows()
    days=[r['day'] for r in rows if r['checked'] and r['day']<=now.date().isoformat()]
    if not days:return dict(status='Add a checked shift-end meter reading',day=None,hours=None,tyres=None,rate=None)
    return performance(rows,max(days),db,source,now)
