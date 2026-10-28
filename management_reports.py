"""Brisbane production briefings: read-only metrics, vector PDF charts, CSV and MIME.
Report generation is called from background workers. No count/state writes or SMTP
are performed by build_briefing; sending is an explicit separate operation.
"""
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta
from email.message import EmailMessage
from html import escape
from pathlib import Path
import csv, json, math, os, sqlite3, threading
from hourly_dashboard import BRISBANE, brisbane_now
from tyre_weight import category, totals
_LOCK = threading.RLock()
KINDS=('passenger','4x4','truck','unknown')
LABELS=('Passenger','SUV / 4x4','Truck','Unclassified')
COLOURS=('#119b75','#168aca','#bd8d25','#8192a3')

def local_stamp(ts,epoch=None):
    stamp=datetime.fromtimestamp(epoch,BRISBANE) if epoch is not None else datetime.fromisoformat(ts)
    return stamp.replace(tzinfo=BRISBANE) if stamp.tzinfo is None else stamp.astimezone(BRISBANE)

def previous_workday(day):
    day-=timedelta(days=1)
    while day.weekday()>4:day-=timedelta(days=1)
    return day

def read_events(con,source,start,end):
    rows=con.execute('SELECT ts,metric_utc,tyre_type FROM counts WHERE source=? AND '
        '((metric_utc>=? AND metric_utc<?) OR (metric_utc IS NULL AND ts>=? AND ts<?))',
        (source,start.timestamp(),end.timestamp(),start.date().isoformat(),(end.date()+timedelta(days=1)).isoformat()))
    events=[]
    for ts,epoch,kind in rows:
        try:
            stamp=local_stamp(ts,epoch)
            if start<=stamp<end and stamp.weekday()<5 and (5,0)<=(stamp.hour,stamp.minute)<(17,5):
                events.append((stamp,category(kind)))
        except (TypeError,ValueError,OverflowError,OSError):pass
    return sorted(events)

def collect(db,source,now=None,weekly=False,incidents_dir=None,recordings_dir=None):
    now=local_stamp((now or brisbane_now()).isoformat())
    monday=now.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=now.weekday())
    start=(monday if weekly else now).replace(hour=5,minute=0,second=0,microsecond=0)
    close=(monday+timedelta(days=4) if weekly else now).replace(hour=17,minute=5,second=0,microsecond=0)
    end=min(now,close);end=max(start,end)
    previous_start=(monday-timedelta(days=7) if weekly else previous_workday(start)).replace(hour=5,minute=0,second=0,microsecond=0)
    previous_end=(previous_start+timedelta(days=4) if weekly else previous_start).replace(hour=17,minute=5)
    with closing(sqlite3.connect(db,timeout=15)) as con:
        con.execute('BEGIN') # One read snapshot across the metrics and incident tables.
        events=read_events(con,source,start,end)
        week_events=read_events(con,source,monday.replace(hour=5),end)
        previous=read_events(con,source,previous_start,previous_end)
        # SQLite aggregation avoids copying the entire count history into Python.
        stamp="CASE WHEN metric_utc IS NOT NULL THEN datetime(metric_utc,'unixepoch','+10 hours') WHEN substr(ts,11) LIKE '%+%' OR substr(ts,11) LIKE '%-%' OR ts LIKE '%Z' THEN datetime(ts,'+10 hours') ELSE datetime(ts) END"
        historical=con.execute(f"WITH e AS (SELECT {stamp} AS stamp FROM counts WHERE source=?) SELECT date(stamp),COUNT(*) FROM e WHERE stamp<? AND time(stamp)>='05:00:00' AND time(stamp)<'17:05:00' AND strftime('%w',stamp) BETWEEN '1' AND '5' GROUP BY date(stamp) ORDER BY COUNT(*) DESC,date(stamp) DESC LIMIT 1",(source,end.replace(tzinfo=None).isoformat(sep=' '))).fetchone()
        all_time=con.execute('SELECT COUNT(*) FROM counts WHERE source=?',(source,)).fetchone()[0]
        has_supervisor=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='supervisor_no_count'").fetchone()
        supervisors=[]
        if has_supervisor:
            con.row_factory=sqlite3.Row
            for row in con.execute('SELECT * FROM supervisor_no_count WHERE started_brisbane>=? AND started_brisbane<? ORDER BY started_brisbane',(start.date().isoformat(),(end.date()+timedelta(days=1)).isoformat())):
                supervisors.append(dict(row))
    kinds=Counter(kind for _,kind in events);weight=totals(kinds)
    weekdays=[]
    for index in range(5):
        day=monday+timedelta(days=index)
        weekdays.append(dict(date=day.date().isoformat(),label=day.strftime('%a'),count=sum(t.date()==day.date() for t,_ in week_events),types=dict(Counter(k for t,k in week_events if t.date()==day.date())),future=day.date()>now.date()))
    slots=[]
    for index in range(13):
        a=start.replace(hour=5)+timedelta(hours=index);b=min(a+timedelta(hours=1),a.replace(hour=17,minute=5))
        selected=[kind for t,kind in events if a.time()<=t.time()<b.time()]
        # Weekly columns aggregate corresponding clock hours across the weekdays.
        if weekly:
            elapsed=sum(max(0,(min(b+timedelta(days=i),end)-(a+timedelta(days=i))).total_seconds()/60) for i in range(5))
        else:elapsed=(b-a).total_seconds()/60
        slots.append(dict(start=a.strftime('%H:%M'),end=b.strftime('%H:%M'),count=len(selected),types=dict(Counter(selected)),minutes=elapsed,completed=end>=b))
    completed=[s for s in slots if s['completed']];best=max(completed,key=lambda s:s['count']) if completed else None
    # No-count periods are observed count gaps; camera/conveyor availability is unknown.
    gaps=[];minutes=0
    for index in range(5 if weekly else 1):
        begin=start+timedelta(days=index);finish=min(begin.replace(hour=17,minute=5),end)
        if finish<=begin:continue
        minutes+=(finish-begin).total_seconds()/60
        times=[t for t,_ in events if begin<=t<finish]
        for a,b in zip([begin]+times,times+[finish]):
            if (b-a).total_seconds()>=600:gaps.append(dict(start=a.isoformat(),end=b.isoformat(),minutes=(b-a).total_seconds()/60))
    alarms=[];unreadable_incidents=0
    if incidents_dir and Path(incidents_dir).is_dir():
        for path in Path(incidents_dir).glob('*.json'):
            try:
                item=json.loads(path.read_text(encoding='utf-8'));stamp=local_stamp(item.get('timestamp',''))
                if item.get('source_kind')=='oak' and start<=stamp<end:
                    alarms.append(dict(timestamp=stamp.isoformat(),object=str(item.get('object','Unknown')),confidence=float(item.get('confidence',0)),snapshot=Path(item.get('snapshot','')).name))
            except (ValueError,TypeError,OSError):unreadable_incidents+=1
    recordings=[]
    if recordings_dir and Path(recordings_dir).is_dir():
        for i in range(5 if weekly else 1):
            day=start+timedelta(days=i)
            candidates=list((Path(recordings_dir)/day.strftime('%Y-%m-%d')).glob('*.mp4'))
            candidates+=list(Path(recordings_dir).glob('OAK_RGB_'+day.strftime('%Y%m%d')+'*.mp4'))
            recordings.extend(path.name for path in candidates)
    complete=now>=close and (weekly or now.weekday()<5)
    delta=((len(events)-len(previous))/len(previous)*100) if complete and previous else None
    return dict(weekly=weekly,source=source,start=start.isoformat(),end=end.isoformat(),as_of=now.isoformat(),complete=complete,
        total=len(events),types=dict(kinds),weight=weight,slots=slots,weekdays=weekdays,best=best,
        average_hour=len(events)*60/minutes if minutes else 0,flow_minute=len(events)/minutes if minutes else 0,
        peak_flow=max((s['count']/s['minutes'] for s in completed if s['minutes']>0),default=0),
        best_day=list(historical) if historical else [None,0],all_time=all_time,
        previous_total=len(previous),previous_label=previous_start.strftime('%d %b %Y'),delta_percent=delta,
        no_count_gaps=gaps,supervisors=supervisors,alarms=sorted(alarms,key=lambda r:r['timestamp']),
        unreadable_incidents=unreadable_incidents,recordings=sorted(recordings))

def commentary(r):
    name='Week' if r['weekly'] else datetime.fromisoformat(r['start']).strftime('%A')
    text=f"{name} {'closed' if r['complete'] else 'to date'} at {r['total']:,} tyres and {r['weight']['total_kg']:,} estimated kg."
    if r['delta_percent'] is not None:
        value=r['delta_percent'];text+=f" Output was {abs(value):.1f}% {'above' if value>=0 else 'below'} the previous {'working week' if r['weekly'] else 'working day'}."
    if r['best']:
        b=r['best'];text+=f" The strongest {'clock-hour group' if r['weekly'] else 'completed slot'} was {b['start']}-{b['end']} with {b['count']:,} tyres."
    pending=sum(x['status']!='COMPLETED' for x in r['supervisors'])
    text+=f" {len(r['no_count_gaps'])} count {'gap' if len(r['no_count_gaps'])==1 else 'gaps'} of 10+ minutes; {pending} supervisor {'response' if pending==1 else 'responses'} outstanding."
    return text

def safe_csv(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
    return value

def write_csv(r,path):
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['record_type','date','start_brisbane','end_brisbane','tyres','passenger','suv_4x4','truck','unclassified','estimated_kg','epu','details'])
        def row(kind,date='',start='',end='',count='',types=None,details=''):
            types=types or {};v=totals(types)
            w.writerow([safe_csv(x) for x in [kind,date,start,end,count,*[types.get(k,0) for k in KINDS],v['total_kg'],v['total_epu'],details]])
        row('PERIOD_TOTAL',r['start'][:10],r['start'],r['end'],r['total'],r['types'],'Estimated class weights; Brisbane UTC+10. '+commentary(r))
        for s in r['slots']:row('HOURLY',r['start'][:10],s['start'],s['end'],s['count'],s['types'])
        for d in r['weekdays']:row('WEEKDAY',d['date'],count='' if d['future'] else d['count'],types=d['types'],details='Upcoming' if d['future'] else 'Production total')
        for g in r['no_count_gaps']:row('NO_COUNT_GAP',start=g['start'],end=g['end'],details=f"{g['minutes']:.1f} minutes; conveyor/camera availability not inferred")
        for s in r['supervisors']:row('SUPERVISOR',start=s['started_brisbane'],end=s.get('ended_brisbane') or '',details=' | '.join(str(s.get(k) or '') for k in ('incident_id','status','reason','supervisor','comments')))
        for a in r['alarms']:row('FOREIGN_ALERT',start=a['timestamp'],details=f"Trial model: {a['object']}; confidence {a['confidence']:.3f}; {a['snapshot']}")
        for name in r['recordings']:row('RECORDING',details=name)
        for key in ('average_hour','flow_minute','peak_flow','best_day','all_time','previous_total','delta_percent'):
            row('METRIC',details=f'{key}: {r[key]}')

def write_pdf(r,path,logo=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Flowable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    fonts=Path(reportlab.__file__).parent/'fonts'
    for name,file in [('Brief','Vera.ttf'),('BriefBold','VeraBd.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
    navy=colors.HexColor('#10283c');teal=colors.HexColor('#008b85');muted=colors.HexColor('#526779')
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='BriefBody',fontName='Brief',fontSize=8.3,leading=11,textColor=navy,spaceAfter=6))
    styles.add(ParagraphStyle(name='BriefHeading',fontName='BriefBold',fontSize=13,leading=17,textColor=navy,spaceBefore=10,spaceAfter=7))
    def p(text):return Paragraph(escape(str(text)).replace('\n','<br/>'),styles['BriefBody'])
    def heading(text):return Paragraph(escape(text),styles['BriefHeading'])
    width=A4[0]-72
    class Bars(Flowable):
        def __init__(self,labels,values,w=width,h=136):Flowable.__init__(self);self.labels=labels;self.values=values;self.width=w;self.height=h
        def draw(self):
            c=self.canv;top=max([v or 0 for v in self.values]+[1]);n=len(self.labels);step=self.width/n
            c.setStrokeColor(colors.HexColor('#d6e2e9'));c.line(0,24,self.width,24)
            for i,(label,value) in enumerate(zip(self.labels,self.values)):
                x=i*step;h=(self.height-53)*(value or 0)/top
                c.setFillColor(teal);c.roundRect(x+step*.16,24,step*.68,max(h,1),2,fill=1,stroke=0)
                c.setFillColor(navy);c.setFont('BriefBold',7.5);c.drawCentredString(x+step/2,29+h,'-' if value is None else f'{value:,}')
                c.setFont('Brief',7);c.drawCentredString(x+step/2,10,label)
    class Mix(Flowable):
        height=118
        def __init__(self,weight=False):Flowable.__init__(self);self.width=width;self.height=118;self.weight=weight
        def draw(self):
            c=self.canv;total=r['weight']['total_kg'] if self.weight else r['total'];angle=90;cx=62;cy=57;radius=43
            for i,k in enumerate(KINDS):
                val=r['weight']['weights'].get(k,0) if self.weight else r['types'].get(k,0);span=360*val/total if total else 0
                if span:c.setFillColor(colors.HexColor(COLOURS[i]));c.wedge(cx-radius,cy-radius,cx+radius,cy+radius,angle,span,fill=1,stroke=0)
                angle+=span
                y=96-i*25;c.setFillColor(colors.HexColor(COLOURS[i]));c.rect(139,y-2,8,8,fill=1,stroke=0)
                c.setFillColor(navy);c.setFont('Brief',9);c.drawString(155,y,LABELS[i]);c.setFont('BriefBold',9)
                c.drawRightString(self.width-10,y,f'{val:,}   ({val/total*100 if total else 0:.1f}%)')
            c.setFillColor(colors.white);c.circle(cx,cy,26,fill=1,stroke=0)
            c.setFillColor(navy);c.setFont('BriefBold',10);c.drawCentredString(cx,cy,f'{total:,}');c.setFont('Brief',7);c.drawCentredString(cx,cy-12,'KG' if self.weight else 'TYRES')
            if not total:c.drawString(139,3,'No assigned weight data' if self.weight else 'No counted tyres')
    def table(rows,widths=None):
        header_style=ParagraphStyle(name='TH',parent=styles['BriefBody'],textColor=colors.white,fontName='BriefBold')
        cells=[[Paragraph(escape(str(x)).replace('\n','<br/>'),header_style if i==0 else styles['BriefBody']) for x in row] for i,row in enumerate(rows)]
        t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#edf5f8')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
        return t
    def page(c,doc):
        c.saveState()
        c.setFillColor(navy);c.rect(0,A4[1]-63,A4[0],63,fill=1,stroke=0)
        c.setFillColor(colors.white);c.setFont('BriefBold',19);c.drawString(36,A4[1]-30,'TYRECYCLE / OZCOM')
        c.setFont('Brief',8);c.drawString(36,A4[1]-47,'TYRETRACK  |  '+('WEEKLY' if r['weekly'] else 'DAILY')+' PRODUCTION BRIEFING')
        if logo and Path(logo).is_file():c.drawImage(str(logo),A4[0]-112,A4[1]-56,width=74,height=43,preserveAspectRatio=True,mask='auto')
        c.setStrokeColor(colors.HexColor('#d6e2e9'));c.line(36,34,A4[0]-36,34)
        c.setFillColor(muted);c.setFont('Brief',7);c.drawString(36,23,'Brisbane UTC+10 | Class-based weight estimates | Production records only')
        c.drawRightString(A4[0]-36,23,f'{doc.page}')
        c.restoreState()
    doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=36,leftMargin=36,topMargin=76,bottomMargin=44,title='Tyrecycle / Ozcom production briefing',author='TyreTrack')
    start=datetime.fromisoformat(r['start']);end=datetime.fromisoformat(r['end'])
    story=[heading(f"{start:%A %d %B %Y}" if not r['weekly'] else f"Week of {start:%d %B %Y}"),p(f"{start:%d %b %H:%M} - {end:%d %b %H:%M} Brisbane | {'FINAL' if r['complete'] else 'PROVISIONAL - shift in progress'}")]
    if r.get('demo'):story.insert(0,p('DEMONSTRATION DATA - layout preview; not site production results.'))
    kpis=[('TOTAL TYRES',f"{r['total']:,}"),('ESTIMATED WEIGHT',f"{r['weight']['total_kg']/1000:,.2f} tonnes"),('TOTAL EPU',f"{r['weight']['total_epu']:,}"),('AVERAGE / HOUR',f"{r['average_hour']:,.1f}"),('BEST DAY',f"{r['best_day'][1]:,} tyres"),('ALL-TIME OAK COUNTS',f"{r['all_time']:,}")]
    tiles=[]
    for a in (0,3):tiles.append([Paragraph(f'<font size="7" color="#526779">{label}</font><br/><font name="BriefBold" size="17" color="#008b85">{value}</font>',ParagraphStyle(name='KPI',parent=styles['BriefBody'],leading=22)) for label,value in kpis[a:a+3]])
    t=Table(tiles,colWidths=[width/3]*3);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#edf5f8')),('BOX',(0,0),(-1,-1),.5,colors.HexColor('#d6e2e9')),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),8)]));story +=[t,Spacer(1,9),p(commentary(r)),heading('Hourly production'+(' - combined clock hours' if r['weekly'] else '')),Bars([s['start'][:2] for s in r['slots']],[s['count'] for s in r['slots']]),heading('Monday-Friday production'),Bars([d['label'] for d in r['weekdays']],[None if d['future'] else d['count'] for d in r['weekdays']],h=99),heading('Tyre classifications'),Mix(),p('Passenger: 8 kg / 1 EPU. SUV / 4x4: 16 kg / 2 EPU. Truck: 45 kg / 5 EPU. Unclassified tyres remain in the total and have no assigned weight. Truck figures require truck-labelled count data.'),PageBreak(),heading('Estimated weight by tyre class'),Mix(weight=True),p('Weight share uses kilograms, not tyre counts. Unclassified tyres have no assigned weight and are excluded. Passenger: 8 kg; SUV / 4x4: 16 kg; truck: 45 kg per tyre.'),heading('Production detail')]
    rows=[['Brisbane slot','Tyres','Passenger','SUV / 4x4','Truck','Est. kg']]
    for s in r['slots']:rows.append([s['start']+'-'+s['end'],f"{s['count']:,}",s['types'].get('passenger',0),s['types'].get('4x4',0),s['types'].get('truck',0),totals(s['types'])['total_kg']])
    story +=[table(rows,[width*.24,width*.12,width*.17,width*.17,width*.12,width*.18]),p(f"Average flow: {r['flow_minute']:.2f} tyres/min | Best completed-slot flow: {r['peak_flow']:.2f} tyres/min"),p(f"Best day: {r['best_day'][0] or 'No history'} | Previous {'week' if r['weekly'] else 'working day'} ({r['previous_label']}): {r['previous_total']:,} tyres"),heading('No-count review and supervisor responses'),p(f"{len(r['no_count_gaps'])} count {'gap' if len(r['no_count_gaps'])==1 else 'gaps'} of 10+ minutes ({sum(g['minutes'] for g in r['no_count_gaps']):.1f} minutes combined). A count gap does not establish conveyor stoppage or camera availability.")]
    if r['no_count_gaps']:
        story.append(table([['Count gap starts (Brisbane)','Ends','Minutes']]+[[datetime.fromisoformat(g['start']).strftime('%d %b %H:%M:%S'),datetime.fromisoformat(g['end']).strftime('%d %b %H:%M:%S'),f"{g['minutes']:.1f}"] for g in r['no_count_gaps']],[width*.43,width*.42,width*.15]))
    if r['supervisors']:
        rows=[['Incident / Brisbane time','Status / supervisor','Reason / comments']]
        for s in r['supervisors']:rows.append([s['incident_id']+'\n'+s['started_brisbane'],s['status']+'\n'+str(s.get('supervisor') or 'Unassigned'),str(s.get('reason') or 'Awaiting reply')+'\n'+str(s.get('comments') or '')])
        story.append(table(rows,[width*.31,width*.25,width*.44]))
    else:story.append(p('No supervisor incident records for this period.'))
    story +=[heading('Foreign-object alerts - trial model'),p(f"{len(r['alarms'])} recorded live OAK alerts. Supported trial classes: wheel rim and person. Test alerts are excluded; zero records do not establish that monitoring was enabled.")]
    if r['alarms']:story.append(table([['Brisbane time','Object','Confidence']]+[[a['timestamp'][11:19],a['object'],f"{a['confidence']:.0%}"] for a in r['alarms']],[width*.4,width*.4,width*.2]))
    if r['unreadable_incidents']:story.append(p(f"{r['unreadable_incidents']} incident files could not be read; review the local incident folder."))
    story +=[heading('Recorded footage and audit trail'),p(f"{len(r['recordings'])} matching timestamped MP4 files found in the recording folder. Use the report times to review the corresponding footage; file presence does not verify continuous coverage."),p('Recording references: '+(', '.join(r['recordings'][:8]) or 'None found.'))]
    if len(r['recordings'])>8:story.append(p('Full recording reference list is included in the CSV.'))
    story.append(p('This report uses stored production counts. Camera uptime is not measured by this report. Review labels and recorded footage to support ongoing model improvements.'))
    doc.build(story,onFirstPage=page,onLaterPages=page)

def build_briefing(db,source,output_dir,now=None,weekly=False,incidents_dir=None,recordings_dir=None,logo=None):
    with _LOCK:
        r=collect(db,source,now,weekly,incidents_dir,recordings_dir)
        out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        stem=f"TyreTrack_{'Weekly' if weekly else 'Daily'}_{r['start'][:10]}_{stamp}"
        paths={ext:out/(stem+'.'+ext) for ext in ('pdf','csv','json')}
        for ext,writer in [('pdf',lambda path:write_pdf(r,path,logo)),('csv',lambda path:write_csv(r,path)),('json',lambda path:Path(path).write_text(json.dumps(r,indent=2),encoding='utf-8'))]:
            tmp=paths[ext].with_suffix('.'+ext+'.tmp')
            try:writer(tmp);os.replace(tmp,paths[ext])
            finally:
                if tmp.exists():tmp.unlink()
        return r,paths

def make_email(settings,r,paths,snapshot=None):
    sender,password,recipient=settings
    msg=EmailMessage();msg['From']=sender;msg['To']=recipient
    msg['Subject']=f"TYRECYCLE / OZCOM | {'Weekly' if r['weekly'] else 'Daily'} production | {r['start'][:10]} | {r['total']:,} tyres"
    msg.set_content('TYRECYCLE / OZCOM - TYRETRACK\n\n'+commentary(r)+f"\n\nEstimated weight: {r['weight']['total_kg']:,} kg\nEPU: {r['weight']['total_epu']:,}\nAverage: {r['average_hour']:.1f} tyres/hour\n\nOpen the attached PDF for charts and operational review, or the CSV in Excel.\nWeights are classification estimates. Times are Brisbane UTC+10.")
    html=f'<html><body style="font-family:Arial;color:#10283c"><h1 style="color:#008b85">TYRECYCLE / OZCOM</h1><h2>{"Weekly" if r["weekly"] else "Daily"} production briefing</h2><p>{escape(commentary(r))}</p><table cellpadding="14" style="background:#edf5f8"><tr><td><b>{r["total"]:,}</b><br>TYRES</td><td><b>{r["weight"]["total_kg"]:,} kg</b><br>ESTIMATED WEIGHT</td><td><b>{r["weight"]["total_epu"]:,}</b><br>EPU</td></tr></table><p><b>Attached:</b> PDF charts and management review; CSV for Excel.</p><p>Brisbane UTC+10. Weights are class-based estimates.</p></body></html>'
    if snapshot and Path(snapshot).is_file():
        captured=datetime.fromtimestamp(Path(snapshot).stat().st_mtime,BRISBANE).strftime('%d %b %Y %H:%M:%S Brisbane')
        html=html.replace('</body>',f'<p>Dashboard captured {captured}:</p><img src="cid:dashboard_snapshot" alt="Dashboard reference" style="width:100%;max-width:900px;height:auto"></body>')
    html=html.replace('</body>', '<h3>Estimated weight by tyre class</h3><img src="cid:weight_mix" alt="Estimated weight by class in kilograms" style="width:100%;max-width:620px"><p>Passenger: 8 kg; SUV / 4x4: 16 kg; truck: 45 kg per tyre. Unclassified tyres excluded.</p></body>')
    msg.add_alternative(html,subtype='html')
    msg.get_body(preferencelist=('html',)).add_related(weight_chart_png(r),maintype='image',subtype='png',cid='<weight_mix>',disposition='inline',filename='Estimated_Weight_By_Class.png')
    for ext,mime in [('pdf',('application','pdf')),('csv',('text','csv'))]:msg.add_attachment(Path(paths[ext]).read_bytes(),maintype=mime[0],subtype=mime[1],filename=Path(paths[ext]).name)
    if snapshot and Path(snapshot).is_file():
        msg.get_body(preferencelist=('html',)).add_related(Path(snapshot).read_bytes(),maintype='image',subtype='png',cid='<dashboard_snapshot>',disposition='inline',filename='TyreTrack_Dashboard.png')
    return msg

def send_briefing(settings,r,paths,snapshot=None,logger=lambda s:None,smtp_factory=None):
    if not settings:return False
    import smtplib
    try:
        msg=make_email(settings,r,paths,snapshot)
        with (smtp_factory or smtplib.SMTP_SSL)('smtp.gmail.com',465,timeout=20) as smtp:
            smtp.login(settings[0],settings[1]);smtp.send_message(msg)
        logger('Gmail accepted management briefing: '+msg['Subject']);return True
    except Exception as exc:logger(f'Management briefing email failed: {type(exc).__name__}: {exc}');return False


def smoke_report():
    """Verify packaged PDF/font support with an isolated empty fixture, no SMTP."""
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/'smoke.db'
        with closing(sqlite3.connect(db)) as con:
            con.execute('CREATE TABLE counts(ts TEXT,metric_utc REAL,source TEXT,tyre_type TEXT)')
            con.commit()
        r,paths=build_briefing(db,'smoke',folder,datetime(2026,10,26,17,5,tzinfo=BRISBANE))
        assert weight_chart_png(r).startswith(b'\x89PNG')
        assert paths['pdf'].read_bytes().startswith(b'%PDF-')
        assert paths['csv'].stat().st_size>0


def weight_chart_png(r):
    """Small dependency-free chart for email, same kg values as PDF/CSV."""
    from PIL import Image, ImageDraw, ImageFont
    import reportlab
    font=ImageFont.truetype(str(Path(reportlab.__file__).parent/"fonts"/"Vera.ttf"),15)
    import io
    image=Image.new('RGB',(620,230),'white');d=ImageDraw.Draw(image)
    total=r['weight']['total_kg'];angle=-90
    for i,key in enumerate(KINDS[:3]):
        value=r['weight']['weights'].get(key,0);span=360*value/total if total else 0
        if span:d.pieslice((10,10,220,220),angle,angle+span,fill=COLOURS[i])
        angle+=span;y=35+i*55
        d.rectangle((245,y,258,y+13),fill=COLOURS[i])
        d.text((270,y),f"{LABELS[i]}: {value:,} kg ({value/total*100 if total else 0:.1f}%)",fill='#10283c',font=font)
    if not total:d.text((40,110),'No assigned weight',fill='#10283c',font=font)
    d.text((245,205),f'Total estimated weight: {total:,} kg',fill='#10283c',font=font)
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()
