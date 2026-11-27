"""Admin-only candidate comparison and field review. No production count edits."""
from pathlib import Path
from PyQt5.QtCore import Qt,QDate
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QFrame,QVBoxLayout,QGridLayout,QLabel,QPushButton,QDialog,QHBoxLayout,
    QDateEdit,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QLineEdit,QFileDialog,QMessageBox,QApplication)
from candidate_trial import Store
from hourly_dashboard import brisbane_now
from review_cards import FitLabel

class CandidatePanel(QFrame):
    def __init__(self,callback,parent=None):
        super().__init__(parent);self.enabled=True;self.setObjectName('candidateTrialPanel')
        self.setStyleSheet('QFrame#candidateTrialPanel {background:#17262b;border:1px solid #587078;border-radius:6px;}')
        layout=QVBoxLayout(self);layout.setContentsMargins(8,7,8,7);layout.setSpacing(4)
        title=FitLabel('TODAY · NEW CLASSIFIER OBSERVE-ONLY');title.setStyleSheet('font:700 12px "Segoe UI";color:#74caff;');layout.addWidget(title)
        note=FitLabel('Same OAK-counted tyres · original totals remain in production')
        note.setStyleSheet('font:10px "Segoe UI";color:#c9e5ef;');layout.addWidget(note)
        grid=QGridLayout();self.recorded={};self.candidate={}
        for col,(key,title) in enumerate([('passenger','Passenger'),('4x4','SUV / 4×4'),('truck','Truck'),('unknown','Unknown')],1):
            label=FitLabel(title);label.setStyleSheet('font:600 10px "Segoe UI";color:#c9e5ef;');grid.addWidget(label,0,col)
            for row,mapping in [(1,self.recorded),(2,self.candidate)]:
                value=FitLabel('0' if key!='truck' or row==1 else '—');value.setStyleSheet('font:700 17px "Segoe UI";color:#57e5ca;')
                mapping[key]=value;grid.addWidget(value,row,col)
        for row,title in [(1,'Recorded'),(2,'Candidate')]:
            label=FitLabel(title);label.setStyleSheet('font:600 11px "Segoe UI";color:#c9e5ef;');grid.addWidget(label,row,0)
        for col in range(5):grid.setColumnStretch(col,1)
        layout.addLayout(grid);self.summary=FitLabel('Waiting for new production OAK counts')
        self.summary.setStyleSheet('font:11px "Segoe UI";color:#c9e5ef;');layout.addWidget(self.summary)
        self.verified=FitLabel('No actual classes confirmed yet');self.verified.setStyleSheet('font:10px "Segoe UI";color:#c9e5ef;');layout.addWidget(self.verified)
        self.status=QLabel('On · 80% candidate confidence · passenger/SUV only');self.status.setWordWrap(True)
        self.status.setStyleSheet('font:11px "Segoe UI";color:#c9e5ef;');layout.addWidget(self.status)
        self.button=QPushButton('Review new classifier / export comparison CSV');self.button.setFixedHeight(28)
        self.button.clicked.connect(callback);layout.addWidget(self.button)
    def set_enabled(self,value):
        self.enabled=bool(value)
        self.status.setText('On · 80% candidate confidence · passenger/SUV only' if value else 'Off · saved trial records retained')
    def show_result(self,data,stats=None):
        stats=stats or {}
        if 'error' in data:
            for label in list(self.recorded.values())+list(self.candidate.values()):label.setText('—')
            self.verified.setText('Actual-class reviews unavailable')
            self.summary.setText('Candidate comparisons unavailable');self.status.setText(str(data['error']));return
        for key,label in self.recorded.items():label.setText(f"{data.get('production_counts',{}).get(key,0):,}")
        for key,label in self.candidate.items():label.setText('—' if key=='truck' else f"{data.get('candidate_counts',{}).get(key,0):,}")
        self.summary.setText(f"Compared {data.get('records',0):,} · Accepted {data.get('accepted',0):,} · Different {data.get('disagreements',0):,} · Unknown {data.get('unknown',0):,}")
        n=data.get('verified',0)
        self.verified.setText(f"Human checked {n} · Recorded correct {data.get('original_verified_correct',0)} · Candidate correct {data.get('candidate_verified_correct',0)}" if n else 'No actual classes confirmed yet · agreement is not accuracy')
        self.set_enabled(self.enabled)
        if self.enabled and stats.get('error'):self.status.setText('Candidate fault: '+str(stats['error']))
        elif self.enabled and stats.get('dropped'):self.status.setText(f"Skipped trial records: {stats['dropped']} · production counts unaffected")
        elif self.enabled and stats.get('queued'):self.status.setText(f"Observe-only · {stats['queued']} comparison(s) pending · 80% threshold")

def open_candidate_review(parent,root):
    store=Store(root);dialog=QDialog(parent);dialog.setWindowTitle('New classifier — observe-only comparison')
    screen=QApplication.primaryScreen().availableGeometry();dialog.resize(min(1050,screen.width()-40),min(740,screen.height()-50))
    layout=QVBoxLayout(dialog);note=QLabel('One comparison per individually counted production OAK tyre. Automatic overlap +1 additions have no separate crop and are excluded. Candidate classes never change counts, alarms or the recorded class. Truck is not trained. Confirm actual classes only when known; model agreement is not accuracy.')
    note.setWordWrap(True);layout.addWidget(note)
    top=QHBoxLayout();day=QDateEdit();day.setCalendarPopup(True);day.setDisplayFormat('yyyy-MM-dd')
    now=brisbane_now().date();day.setDate(QDate(now.year,now.month,now.day));top.addWidget(QLabel('Brisbane shift date'));top.addWidget(day)
    refresh_button=QPushButton('Refresh');export=QPushButton('Export this day CSV');top.addWidget(refresh_button);top.addWidget(export);top.addStretch();layout.addLayout(top)
    table=QTableWidget(0,7);table.setHorizontalHeaderLabels(['Time','Track','Recorded','Candidate','Score','Reason','Human class'])
    table.setSelectionBehavior(QTableWidget.SelectRows);table.setSelectionMode(QTableWidget.SingleSelection);table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);layout.addWidget(table,1)
    detail=QLabel('Select a record to review');detail.setWordWrap(True);layout.addWidget(detail)
    picture=QLabel();picture.setAlignment(Qt.AlignCenter);picture.setMaximumHeight(130);layout.addWidget(picture)
    edit=QHBoxLayout();actual=QComboBox();actual.addItem('Choose actual class','')
    for title,key in [('Passenger','passenger'),('SUV / 4×4','4x4'),('Truck','truck'),('Unsure','unsure')]:actual.addItem(title,key)
    reviewer=QLineEdit();reviewer.setPlaceholderText('Reviewer name');edit.addWidget(actual);edit.addWidget(reviewer);layout.addLayout(edit)
    notes=QLineEdit();notes.setPlaceholderText('Evidence / how the actual class was confirmed (required)');layout.addWidget(notes)
    buttons=QHBoxLayout();save=QPushButton('Save actual-class review');close=QPushButton('Close');buttons.addWidget(save);buttons.addWidget(close);layout.addLayout(buttons)
    rows=[]
    def selected():
        i=table.currentRow();return rows[i] if 0<=i<len(rows) else None
    def load():
        nonlocal rows
        try:rows=store.rows(day.date().toString('yyyy-MM-dd'))
        except Exception as exc:QMessageBox.warning(dialog,'Read failed',str(exc));return
        table.setRowCount(len(rows));picture.clear();detail.setText(f'{len(rows)} saved comparisons for this date')
        for i,r in enumerate(rows):
            values=[r['stamp'][11:19],r['track_id'],r['production_class'],r['candidate_class'],'' if r['confidence'] is None else f"{r['confidence']:.0%}",r['reason'],r['human_label']]
            for j,value in enumerate(values):item=QTableWidgetItem(str(value));item.setToolTip(str(value));table.setItem(i,j,item)
    def select():
        r=selected();picture.clear()
        if not r:return
        detail.setText(f"Original visual: {r['original_class']} · Recorded: {r['production_class']} · Candidate: {r['candidate_class']} · {r['reason'] or 'accepted'} · Track {r['track_id']}")
        actual.setCurrentIndex(max(0,actual.findData(r['human_label'])));reviewer.setText(r['reviewer']);notes.setText(r['notes'])
        if r['image']:
            path=(store.root/r['image']).resolve()
            if path.is_relative_to(store.root.resolve()) and path.is_file():picture.setPixmap(QPixmap(str(path)).scaled(520,130,Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def save_review():
        r=selected()
        if not r:return
        try:store.review(r['id'],actual.currentData(),reviewer.text(),notes.text());load()
        except Exception as exc:QMessageBox.warning(dialog,'Review not saved',str(exc))
    def export_csv():
        path,_=QFileDialog.getSaveFileName(dialog,'Save candidate comparison CSV',f"Candidate_Comparison_{day.date().toString('yyyy-MM-dd')}.csv",'CSV (*.csv)')
        if not path:return
        try:store.export(path,day.date().toString('yyyy-MM-dd'))
        except Exception as exc:QMessageBox.warning(dialog,'Export failed',str(exc))
    table.itemSelectionChanged.connect(select);refresh_button.clicked.connect(load);day.dateChanged.connect(load)
    save.clicked.connect(save_review);export.clicked.connect(export_csv);close.clicked.connect(dialog.accept)
    load();dialog.exec_()
