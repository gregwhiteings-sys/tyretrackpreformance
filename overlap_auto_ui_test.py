"""Real Qt reversal button removes only the automatic count row."""
import os,time,sqlite3,json
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication,QDialog,QTableWidget,QPushButton,QSpinBox,QLineEdit
from classification_review import ReviewStore
from classification_review_ui import open_review
from overlap_auto import write_correction,corrections
app=QApplication.instance() or QApplication([])
with TemporaryDirectory() as tmp:
 root=Path(tmp);db=root/'tyretrack.db'
 with closing(sqlite3.connect(db)) as c:
  c.execute('CREATE TABLE counts(id INTEGER PRIMARY KEY,ts TEXT,source TEXT,track_id INTEGER,confidence REAL,tyre_type TEXT,class_confidence REAL,metric_utc REAL)')
  c.execute("INSERT INTO counts(id,track_id) VALUES(1,7)");c.commit()
 event=dict(event_id='auto-ui',timestamp='2026-11-24T08:00:00+10:00',source='oak',scope='production',eligible=True,counted_ids=[7],confidence=.8,automatic_correction=True,added_tyres=1)
 assert write_correction(db,event)
 store=ReviewStore(root/'classification_review');store.submit('overlap',event,key='auto-ui');assert store.flush()
 state={'phase':0,'error':None};deadline=time.monotonic()+10
 def step():
  dialog=app.activeModalWidget()
  try:
   assert time.monotonic()<deadline,('UI timed out',state['phase'],[w.text() for w in dialog.findChildren(__import__('PyQt5.QtWidgets',fromlist=['QLabel']).QLabel)] if isinstance(dialog,QDialog) else '')
   if not isinstance(dialog,QDialog):QTimer.singleShot(30,step);return
   table=dialog.findChild(QTableWidget)
   if not table.rowCount():QTimer.singleShot(30,step);return
   if not state['phase']:
    table.selectRow(0);assert not dialog.findChild(QSpinBox).isEnabled()
    next(w for w in dialog.findChildren(QLineEdit) if w.placeholderText().startswith('What was actually')).setText('Greg reviewed: only one tyre')
    next(b for b in dialog.findChildren(QPushButton) if b.text()=='Reverse selected overlap +1 correction').click();state['phase']=1
   elif corrections(db)[0]['reversed']:
    with closing(sqlite3.connect(db)) as c:assert c.execute('SELECT track_id FROM counts').fetchall()==[(7,)]
    state['phase']=2;dialog.accept();return
   QTimer.singleShot(30,step)
  except Exception as e:
   state['error']=e
   if isinstance(dialog,QDialog):dialog.reject()
 QTimer.singleShot(30,step);open_review(None,store,'2026-11-24')
 assert not state['error'],state['error'];assert state['phase']==2;assert store.close()
print('PASS real Qt overlap reversal, original count retained, manual double-add controls disabled')
