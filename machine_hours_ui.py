"""Operator shift-end entry; photos remain local and counts are read-only."""
from pathlib import Path
from datetime import datetime
from PyQt5.QtCore import Qt,QDate,QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (QFrame,QLabel,QVBoxLayout,QHBoxLayout,QPushButton,QDialog,
    QFormLayout,QDateEdit,QDoubleSpinBox,QCheckBox,QLineEdit,QFileDialog,QMessageBox,
    QTableWidget,QTableWidgetItem,QHeaderView,QListWidget,QSizePolicy,QScrollArea,QWidget,QApplication)
from machine_hours import HoursStore,latest,performance,previous_shift
from hourly_dashboard import brisbane_now
from review_cards import FitLabel

class HoursPanel(QFrame):
    def __init__(self,callback,parent=None):
        super().__init__(parent);self.setObjectName('machineHoursPanel');self.setFixedHeight(166)
        self.setStyleSheet('QFrame#machineHoursPanel {background:#17262b;border:1px solid #587078;border-radius:6px;}')
        outer=QVBoxLayout(self);outer.setContentsMargins(8,5,8,5);outer.setSpacing(2)
        head=QHBoxLayout();self.title=FitLabel('SHREDDER PERFORMANCE · SHIFT-END READINGS')
        self.title.setStyleSheet('color:#f1c568;font:700 11px "Segoe UI";');head.addWidget(self.title,1)
        self.button=QPushButton('Shredder hours');self.button.setFixedHeight(25)
        self.button.setStyleSheet('font:600 11px "Segoe UI";padding:2px 8px;');self.button.clicked.connect(callback);head.addWidget(self.button)
        outer.addLayout(head);row=QHBoxLayout();self.values={}
        for key,name in [('hours','ACTUAL RUNNING HOURS'),('tyres','RECORDED TYRES'),('rate','TYRES / RUNNING HOUR'),('tonnes_rate','EST. TONNES / RUNNING HOUR'),('month_tonnes_rate','MONTH AVG. EST. TONNES / RUN HOUR')]:
            if key=='tonnes_rate':outer.addLayout(row);row=QHBoxLayout()
            box=QFrame();box.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Expanding);box.setMinimumWidth(0)
            layout=QVBoxLayout(box);layout.setContentsMargins(4,0,4,0);layout.setSpacing(0)
            title=FitLabel(name);title.setStyleSheet('color:#c9e5ef;font:600 10px "Segoe UI";');layout.addWidget(title)
            value=FitLabel('—');value.setStyleSheet('color:#57e5ca;font:700 24px "Segoe UI";');layout.addWidget(value);self.values[key]=value;row.addWidget(box,1)
        outer.addLayout(row);self.note=FitLabel('Add a checked shift-end meter reading')
        self.note.setStyleSheet('color:#c9e5ef;font:11px "Segoe UI";');outer.addWidget(self.note)
    def show_result(self,data):
        data=data or {};day=data.get('day')
        self.title.setText('SHREDDER · LAST COMPLETED SHIFT · '+day if day else 'SHREDDER PERFORMANCE · SHIFT-END READINGS')
        for key,value in self.values.items():
            n=data.get(key)
            value.setText('—' if n is None else f'{n:.1f} h' if key=='hours' else f'{n:,.2f} t/h' if key.endswith('tonnes_rate') else f'{n:,.1f}' if key=='rate' else f'{n:,.0f}')
        self.values['month_tonnes_rate'].setToolTip(f"This month's {data.get('month_shifts',0)} checked shifts: total estimated tonnes divided by total matching running hours. Missing readings/counts are excluded.")
        note=data.get('status','Readings unavailable')
        if data.get('tonnes_rate') is not None or data.get('month_tonnes_rate') is not None:
            note='Weight estimates: passenger 8 kg · SUV/4×4 16 kg · truck 45 kg'
            unknown=data.get('unknown_weight',0);monthly=data.get('month_unknown_weight',0)
            if unknown or monthly:note+=f' · Passenger weight default: {unknown} shift / {monthly} month tyres'
        self.note.setText(note);self.note.setToolTip(data.get('error','') or note)

def open_hours(parent,root,counts_db,source):
    store=HoursStore(root);dialog=QDialog(parent);dialog.setWindowTitle('Shredder hours — daily readings and photos')
    screen=QApplication.primaryScreen().availableGeometry()
    dialog.resize(min(940,screen.width()-40),min(660,screen.height()-60));layout=QVBoxLayout(dialog)
    info=QLabel('After each shift: select the date, enter TOTAL HOURS from the meter photo, attach photos, check and save. '
        'The previous checked shift-end reading supplies the opening reading. Rates use recorded OAK production counts '
        'for the same Brisbane weekday 05:00–17:05 window. A missing reading or missing counts leaves the rate pending. '
        'The machine meter measures actual running time; these entries never change tyre counts.')
    info.setWordWrap(True);layout.addWidget(info)
    table=QTableWidget(0,6);table.setHorizontalHeaderLabels(['Shift date','Meter hours','Status','Run hours','Tyres','Tyres / h'])
    table.setSelectionBehavior(QTableWidget.SelectRows);table.setSelectionMode(QTableWidget.SingleSelection)
    table.setEditTriggers(QTableWidget.NoEditTriggers);table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);layout.addWidget(table,1)
    editor=QWidget();editor_layout=QVBoxLayout(editor);editor_layout.setContentsMargins(0,0,0,0)
    form=QFormLayout();day=QDateEdit();day.setCalendarPopup(True);day.setDisplayFormat('yyyy-MM-dd')
    today=brisbane_now().date();day.setDate(QDate(today.year,today.month,today.day));day.setMaximumDate(day.date());form.addRow('Shift date',day)
    meter=QDoubleSpinBox();meter.setDecimals(1);meter.setRange(0,10000000);meter.setSingleStep(.1);meter.setObjectName('closingMeter');form.addRow('Closing TOTAL HOURS',meter)
    opening_label=QLabel();form.addRow('Previous checked reading',opening_label)
    override=QCheckBox('Enter a known opening reading / meter reset');form.addRow('',override)
    opening=QDoubleSpinBox();opening.setDecimals(1);opening.setRange(0,10000000);opening.setEnabled(False);override.toggled.connect(opening.setEnabled);form.addRow('Manual opening (optional)',opening)
    notes=QLineEdit();notes.setPlaceholderText('Supervisor notes; explain any opening override or meter reset');form.addRow('Notes',notes)
    checked=QCheckBox('Shift is complete and I have checked this meter reading');checked.setObjectName('checkedReading');form.addRow('',checked)
    editor_layout.addLayout(form);photos=QListWidget();photos.setMaximumHeight(85);editor_layout.addWidget(photos)
    scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(editor);layout.addWidget(scroll,2)
    actions=QHBoxLayout();attach=QPushButton('Attach meter / log photos');import_button=QPushButton('Import daily photo ZIP');save=QPushButton('Save shift reading');close=QPushButton('Close')
    for button in [attach,import_button,save,close]:actions.addWidget(button)
    layout.addLayout(actions);status=QLabel('');status.setWordWrap(True);layout.addWidget(status)
    pending=[];records=[]
    def selected_day():return day.date().toString('yyyy-MM-dd')
    def load_day():
        pending.clear();checked.setChecked(False);override.setChecked(False);photos.clear()
        by_day={r['day']:r for r in store.rows()};r=by_day.get(selected_day(),{})
        p=by_day.get(previous_shift(selected_day()),{})
        previous=p.get('meter') if p.get('checked') else None
        opening_label.setText(str(previous) if previous is not None else 'Missing — save a baseline reading first, or enter a known opening')
        meter.setValue(r.get('meter') if r.get('meter') is not None else previous or 0)
        notes.setText(r.get('notes',''))
        if r.get('opening') is not None:override.setChecked(True);opening.setValue(r['opening'])
        for doc in store.documents(selected_day()):
            photos.addItem(doc['name']);photos.item(photos.count()-1).setData(Qt.UserRole,str(store.root/doc['path']))
    def refresh():
        nonlocal records
        records=store.rows();table.setRowCount(len(records))
        for i,r in enumerate(records):
            p=performance(records,r['day'],counts_db,source)
            values=[r['day'],'' if r['meter'] is None else f"{r['meter']:.1f}",'Checked' if r['checked'] else 'Check photo',
                '—' if p['hours'] is None else f"{p['hours']:.1f}",'—' if p['tyres'] is None else f"{p['tyres']:,}",'—' if p['rate'] is None else f"{p['rate']:,.1f}"]
            for j,text in enumerate(values):table.setItem(i,j,QTableWidgetItem(text))
        load_day()
    def select_row():
        i=table.currentRow()
        if 0<=i<len(records):day.setDate(QDate.fromString(records[i]['day'],'yyyy-MM-dd'));load_day()
    def add_photos():
        paths,_=QFileDialog.getOpenFileNames(dialog,'Select meter photo and supervisor sheets','','Photos (*.jpg *.jpeg *.png *.webp)')
        for path in paths:
            pending.append(path);photos.addItem(Path(path).name);photos.item(photos.count()-1).setData(Qt.UserRole,path)
    def open_photo(item):
        path=item.data(Qt.UserRole)
        if path:QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    def import_photos():
        path,_=QFileDialog.getOpenFileName(dialog,'Import WhatsApp daily photos or reviewed readings package','','ZIP files (*.zip)')
        if not path:return
        try:
            count,proposed=store.import_zip(path);refresh()
            status.setText(f'Imported {count} photos and {proposed} proposed readings. Select a date, verify the meter against its photo, then check and save. Re-importing does not duplicate photos or overwrite checked readings.')
        except Exception as exc:QMessageBox.warning(dialog,'Import failed',str(exc))
    def save_reading():
        if not checked.isChecked():QMessageBox.warning(dialog,'Check the reading','Confirm that the shift is complete and the meter reading has been checked.');return
        try:
            # Evidence is retained locally even if a reading needs correction.
            store.attach(selected_day(),pending)
            store.save(selected_day(),meter.value(),notes.text(),opening.value() if override.isChecked() else None)
            refresh();status.setText('Saved. The dashboard will refresh; original production counts are unchanged.')
        except Exception as exc:QMessageBox.warning(dialog,'Reading not saved',str(exc))
    day.dateChanged.connect(load_day);table.itemSelectionChanged.connect(select_row);attach.clicked.connect(add_photos)
    photos.itemDoubleClicked.connect(open_photo);import_button.clicked.connect(import_photos);save.clicked.connect(save_reading);close.clicked.connect(dialog.accept)
    refresh();dialog.exec_()

