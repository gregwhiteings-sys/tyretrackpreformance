"""Shift-end hour-meter records and read-only production-rate calculation."""
import csv,hashlib,io,json,math,re,sqlite3,uuid,zipfile
from pathlib import Path
from contextlib import contextmanager,closing
from datetime import date,datetime,timedelta
from hourly_dashboard import BRISBANE,brisbane_now
from tyre_weight import totals as weight_totals

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

def recorded_output(db,source,day,now=None):
    """Same Brisbane weekday 05:00–17:05 production window; no test sources."""
    now=(now or brisbane_now()).astimezone(BRISBANE);d=date.fromisoformat(day)
    if d.weekday()>=5 or d>now.date() or not Path(db).exists():return None
    start=datetime.combine(d,datetime.min.time(),BRISBANE).replace(hour=5)
    end=min(start.replace(hour=17,minute=5),now)
    if end<=start:return None
    with closing(sqlite3.connect(db,timeout=3)) as c:
        grouped=dict(c.execute('SELECT tyre_type,COUNT(*) FROM counts WHERE source=? AND metric_utc>=? AND metric_utc<? GROUP BY tyre_type',(source,start.timestamp(),end.timestamp())))
        rows=c.execute('SELECT ts,tyre_type FROM counts WHERE source=? AND metric_utc IS NULL AND ts>=? AND ts<?',(source,(d-timedelta(days=1)).isoformat(),(d+timedelta(days=2)).isoformat())).fetchall()
    for ts,kind in rows:
        try:
            t=datetime.fromisoformat(ts)
            if t.tzinfo is None:t=t.replace(tzinfo=BRISBANE)
            if start<=t<end:grouped[kind]=grouped.get(kind,0)+1
        except (ValueError,TypeError):continue
    return weight_totals(grouped,default_passenger=True) if grouped else None

def recorded_tyres(db,source,day,now=None):
    output=recorded_output(db,source,day,now)
    return output['total_count'] if output else None

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
    output=recorded_output(db,source,day,now)
    if output is None:result['status']='No production counts available for this shift';return result
    n=output['total_count'];tonnes=output['total_kg']/1000
    result.update(tyres=n,rate=n/hours,tonnes=tonnes,
                  tonnes_rate=tonnes/hours if n>0 else None,
                  unknown_weight=output['unknown'],status='Recorded tyres / actual running hours')
    return result

def monthly_average(rows,db,source,now):
    """Weighted rate: known estimated tonnes / matched completed-shift run hours."""
    prefix=now.date().isoformat()[:7];hours=tonnes=0.;shifts=unknown=0
    for row in rows:
        if not row['checked'] or not row['day'].startswith(prefix) or row['day']>now.date().isoformat():continue
        p=performance(rows,row['day'],db,source,now)
        if not p.get('hours') or p.get('tyres') is None:continue
        hours+=p['hours'];tonnes+=p['tonnes'];unknown+=p['unknown_weight'];shifts+=1
    # All-unknown output has no usable weight estimate.
    rate=tonnes/hours if hours>0 and tonnes>0 else None
    return dict(month_tonnes_rate=rate,month_hours=hours,month_tonnes=tonnes,
                month_shifts=shifts,month_unknown_weight=unknown)

def latest(root,db,source,now=None):
    now=now or brisbane_now();rows=HoursStore(root).rows()
    days=[r['day'] for r in rows if r['checked'] and r['day']<=now.date().isoformat()]
    result=performance(rows,max(days),db,source,now) if days else dict(status='Add a checked shift-end meter reading',day=None,hours=None,tyres=None,rate=None)
    result.update(monthly_average(rows,db,source,now))
    return result


def report_running_hours(root,events,start,end,now):
    """Match checked, completed-shift meter deltas to report-snapshot output.

    Never create or update the meter DB and never use in-progress shifts or
    estimate running hours from elapsed time, counts or no-count gaps.
    """
    path=Path(root)/'hours.sqlite3';readings={};error=None
    if path.is_file():
        try:
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=3)) as c:
                c.row_factory=sqlite3.Row
                readings={r['day']:dict(r) for r in c.execute('SELECT * FROM readings WHERE checked=1 AND meter IS NOT NULL')}
        except (sqlite3.Error,OSError) as exc:error=str(exc)
    days=[];day=start.date()
    while day<=end.date():
        if day.weekday()<5:
            key=day.isoformat();close=datetime.combine(day,datetime.min.time(),BRISBANE).replace(hour=17,minute=5)
            output=weight_totals({k:sum(t.date()==day and kind==k for t,kind in events) for k in {kind for _,kind in events}},default_passenger=True)
            row=dict(day=key,tyres=output['total_count'],estimated_kg=output['total_kg'],unknown_weight=output['unknown'],
                     hours=None,rate=None,tonnes_rate=None,status='Meter reading missing',matched=False)
            r=readings.get(key);prior=readings.get(previous_shift(key))
            if close>now or close>end:row['status']='Shift in progress — running average pending'
            elif error:row['status']='Meter records unavailable'
            elif r:
                opening=r['opening'] if r['opening'] is not None else prior['meter'] if prior else None
                if opening is None:row['status']='Previous shift reading missing'
                else:
                    hours=round(r['meter']-opening,4)
                    if not math.isfinite(hours) or not 0<=hours<=24:row['status']='Check meter readings'
                    elif hours==0:
                        row['hours']=0.;row['status']='Check counts with zero running hours' if output['total_count'] else 'No running hours recorded'
                    else:
                        row.update(hours=hours,matched=True,rate=output['total_count']/hours,
                            tonnes_rate=output['total_kg']/1000/hours if output['total_count']>0 else None,
                            status='Checked completed shift')
            days.append(row)
        day+=timedelta(days=1)
    matched=[r for r in days if r['matched']];hours=sum(r['hours'] for r in matched)
    tyres=sum(r['tyres'] for r in matched);kg=sum(r['estimated_kg'] for r in matched);unknown=sum(r['unknown_weight'] for r in matched)
    return dict(days=days,matched_shifts=len(matched),expected_shifts=len(days),running_hours=hours if matched else None,
        matched_tyres=tyres,matched_kg=kg,unknown_weight=unknown,
        tyres_per_running_hour=tyres/hours if hours else None,
        tonnes_per_running_hour=kg/1000/hours if hours and tyres>0 else None,
        average_running_hours_per_shift=hours/len(matched) if matched else None,
        average_tyres_per_shift=tyres/len(matched) if matched else None,
        average_tonnes_per_shift=kg/1000/len(matched) if matched and tyres>0 else None,
        coverage_complete=bool(days) and all(r['matched'] or r['hours']==0 and r['tyres']==0 for r in days),error=error)

def running_hours_text(data):
    if not data:return 'Shredder running hours: readings pending.'
    n=data['matched_shifts'];total=data['expected_shifts']
    if data['running_hours'] is None:return f'Shredder running hours: readings pending (0/{total} shifts matched).'
    rate=data['tyres_per_running_hour'];tonnes=data['tonnes_per_running_hour']
    result=f"Shredder running hours: {data['running_hours']:.2f} h; {n}/{total} shifts matched. Average {rate:,.1f} tyres/running h; "
    result+=f'{tonnes:,.2f} estimated tonnes/running h.' if tonnes is not None else 'estimated tonnes/running h unavailable.'
    result+=f" Rates use only the same matched shifts ({data['matched_tyres']:,} tyres)."
    if data['unknown_weight']:result+=f" {data['unknown_weight']:,} source records use the passenger 8 kg default."
    return result
