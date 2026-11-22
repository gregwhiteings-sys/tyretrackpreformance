"""Review-only UI; disk reads, writes and exports run outside the GUI thread."""
import threading
from PyQt5.QtCore import Qt,QObject,pyqtSignal,QUrl
from PyQt5.QtGui import QPixmap,QDesktopServices
from PyQt5.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QLineEdit,
    QPushButton,QTableWidget,QTableWidgetItem,QFileDialog,QCheckBox,QHeaderView)
from classification_review import summary

class Bridge(QObject):
    result=pyqtSignal(object)

def open_review(parent,store,today,scope_default="production"):
    dialog=QDialog(parent);dialog.setWindowTitle('Tyre comparison and foreign-alert review');dialog.resize(1120,790)
    layout=QVBoxLayout(dialog);filters=QHBoxLayout();layout.addLayout(filters)
    day=QLineEdit(today);day.setPlaceholderText('YYYY-MM-DD');filters.addWidget(QLabel('Brisbane date'));filters.addWidget(day)
    kind=QComboBox();kind.addItem('All records','');kind.addItem('Tyre comparison','tyre');kind.addItem('Foreign alerts','foreign');filters.addWidget(kind)
    scope=QComboBox();scope.addItem('Production','production');scope.addItem('Live test','test');scope.addItem('Video replay','replay');filters.addWidget(scope);scope.setCurrentIndex(max(0,scope.findData(scope_default)))
    disagreements=QCheckBox('Tyre disagreements only');filters.addWidget(disagreements)
    refresh=QPushButton('Refresh');filters.addWidget(refresh)
    stats=QLabel();stats.setWordWrap(True);layout.addWidget(stats)
    table=QTableWidget(0,9);table.setHorizontalHeaderLabels(['Time','Type','Original prediction','Diameter ~mm','Size suggestion','Assisted proposal','Used for count','Review','Reason'])
    table.setSelectionBehavior(QTableWidget.SelectRows);table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents);layout.addWidget(table)
    image=QLabel('Select a record to see its evidence');image.setMinimumHeight(200);image.setAlignment(Qt.AlignCenter);layout.addWidget(image)
    detail=QLabel();detail.setWordWrap(True);layout.addWidget(detail)
    controls=QHBoxLayout();layout.addLayout(controls);status=QComboBox();reason=QComboBox()
    for title,value in [('Choose false-alert reason',''),('Normal tyre mistaken for metal/rim','normal_tyre'),('Belt join','belt_join'),('Shadow','shadow'),('Other (explain in notes)','other')]:reason.addItem(title,value)
    notes=QLineEdit();notes.setPlaceholderText('What was actually there? E.g. exposed tyre bead wire; loose metal rim; reviewer name')
    save=QPushButton('Save human review');controls.addWidget(status);controls.addWidget(reason);controls.addWidget(notes);controls.addWidget(save)
    actions=QHBoxLayout();layout.addLayout(actions)
    export_csv=QPushButton('Export comparison CSV');export_zip=QPushButton('Export reviewed evidence ZIP');recording=QPushButton('Open recording folder')
    for b in [export_csv,export_zip,recording]:actions.addWidget(b)
    notice=QLabel('Human reviews do not reset alarms, change weights or rewrite production totals. Unreviewed/unsure cases are never treated as negatives. Size is estimated, not an exact sidewall code.');notice.setWordWrap(True);layout.addWidget(notice)
    bridge=Bridge(dialog);state={'rows':[],'busy':False,'closed':False,'threads':[]}
    def busy(value):
        state['busy']=value
        for b in [refresh,save,export_csv,export_zip]:b.setEnabled(not value)
    def task(fn):
        if state['busy']:return
        busy(True)
        def run():
            try:value=fn()
            except Exception as e:value=('error',str(e))
            if not state['closed']:bridge.result.emit(value)
        state['threads']=[t for t in state['threads'] if t.is_alive()]
        thread=threading.Thread(target=run,name='review-screen-io',daemon=True)
        state['threads'].append(thread);thread.start()
    def selected():
        i=table.currentRow();return state['rows'][i] if 0<=i<len(state['rows']) else None
    def load():
        date=day.text().strip();category=kind.currentData();area=scope.currentData();only=disagreements.isChecked()
        def read():
            allrows=store.rows(date,category or None,area,limit=1000000);s=summary(allrows)
            if only:allrows=[r for r in allrows if r['kind']=='tyre' and (r['payload'].get('disagreement') or r['payload'].get('size_disagreement'))]
            return ('rows',allrows[:500],s,len(allrows))
        task(read)
    def receive(value):
        busy(False)
        if value[0]=='error':notice.setText('Review operation failed: '+value[1]);return
        if value[0]=='rows':
            _,rows,s,total=value;state['rows']=rows;table.setRowCount(len(rows))
            counts=lambda c:f"Passenger {c.get('passenger',0)}, SUV/4x4 {c.get('4x4',0)}, unclassified {c.get('unknown',0)}"
            stats.setText(f"Date totals: tyres {s['tyres']} · measured {s['measured']} · disagreements {s['disagreements']} · foreign alerts {s['foreign']} · human-marked false alerts {s['false_alerts']} · unreviewed {s['unreviewed']}. Showing latest {len(rows)} of {total} matching records. Original: {counts(s['original_counts'])} · Size-assisted proposal: {counts(s['assisted_counts'])}. Agreement is not accuracy.")
            for i,r in enumerate(rows):
                p=r['payload'];mm=p.get('diameter_mm');values=[r['stamp'],r['kind'],p.get('original_class',p.get('predicted_class','')),f'{mm:.0f}' if mm is not None else 'Not measurable',p.get('size_candidate') or 'Uncertain',p.get('assisted_class',''),p.get('final_class',''),r['status'],r['reason']]
                for j,v in enumerate(values):table.setItem(i,j,QTableWidgetItem(str(v)))
            if rows:table.selectRow(0)
            else:image.clear();detail.setText('No records for this date/filter. New records begin with this build. Press Refresh after counting starts.')
        else:notice.setText(value[1]);load()
    bridge.result.connect(receive)
    def choose():
        r=selected();status.clear()
        if not r:return
        options=[('Not reviewed','unreviewed'),('Passenger','passenger'),('SUV / 4x4','4x4'),('Truck','truck'),('Unsure','unsure')] if r['kind']=='tyre' else [('Not reviewed','unreviewed'),('Confirmed foreign object','confirmed_foreign'),('False alert','false_alert'),('Unsure','unsure')]
        for title,val in options:status.addItem(title,val)
        status.setCurrentIndex(max(0,status.findData(r['status'])));reason.setCurrentIndex(max(0,reason.findData(r['reason'])));notes.setText(r['notes'])
        path=store.image_path(r)
        if path:image.setPixmap(QPixmap(str(path)).scaled(850,240,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:image.clear();image.setText('Evidence image unavailable')
        p=r['payload'];detail.setText('ID: '+r['id']+' | '+json_text(p))
    table.itemSelectionChanged.connect(choose)
    def write_review():
        r=selected()
        if not r:return
        key=r['id'];val=status.currentData();why=reason.currentData() if r['kind']=='foreign' else '';comment=notes.text()
        task(lambda:(store.review(key,val,why,comment) or ('saved','Human review saved; original prediction preserved.')))
    def export(extension):
        path,_=QFileDialog.getSaveFileName(dialog,'Export review records','TyreTrack_review.'+extension,'ZIP (*.zip)' if extension=='zip' else 'CSV (*.csv)')
        if not path:return
        date=day.text().strip();category=kind.currentData();area=scope.currentData()
        task(lambda:('export',f'Export saved: {path} ({store.export(path,date,category or None,area)} source records). ZIP contains only human-reviewed cases.'))
    def open_recording():
        r=selected();path=r['payload'].get('recording_reference') if r else None
        if path:QDesktopServices.openUrl(QUrl.fromLocalFile(str(__import__('pathlib').Path(path).parent)))
        else:notice.setText('No recording reference was captured for this record. Recording may have been off; use the evidence image and timestamp.')
    save.clicked.connect(write_review);refresh.clicked.connect(load);export_csv.clicked.connect(lambda:export('csv'));export_zip.clicked.connect(lambda:export('zip'));recording.clicked.connect(open_recording)
    def closed():state['closed']=True
    dialog.finished.connect(closed);load();dialog.exec_()
    for thread in state['threads']:
        thread.join(6)
        if thread.is_alive():raise RuntimeError('Review screen I/O worker did not finish on close')

def json_text(p):
    modes={'compare':'Compare only','assist':'Size assistance','off':'Original only'}
    parts=[]
    if 'mode' in p:parts.append('Mode: '+modes.get(p['mode'],str(p['mode'])))
    if 'visual_vote' in p:parts.append(f"Original class vote: {p['visual_vote']:.0%}")
    if 'confidence' in p:parts.append(f"Detector confidence: {p['confidence']:.0%}")
    if p.get('calibration'):parts.append(f"Assumed belt width: {p['calibration'].get('width_mm')} mm")
    if p.get('recording_reference'):parts.append('Recording: '+__import__('pathlib').Path(p['recording_reference']).name)
    if p.get('frame_sequence') is not None:parts.append('Frame: '+str(p['frame_sequence']))
    return ' | '.join(parts)
