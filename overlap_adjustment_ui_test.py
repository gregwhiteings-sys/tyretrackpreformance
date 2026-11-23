"""Actual review dialog: confirm overlap, save one missed tyre and display revision."""
import os,time
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from tempfile import TemporaryDirectory
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication,QDialog,QTableWidget,QComboBox,QPushButton,QSpinBox,QLineEdit
from classification_review import ReviewStore
from classification_review_ui import open_review
app=QApplication.instance() or QApplication([])
with TemporaryDirectory() as tmp:
 store=ReviewStore(Path(tmp));store.submit('overlap',dict(timestamp='2026-11-23T08:00:00+10:00',scope='production',track_ids=[1,2],counted_track_ids=[1],not_counted_track_ids=[2],counted_tracks=1,observed_tracks=2,association_status='needs_review'),key='event');assert store.flush()
 state={'phase':0,'error':None};deadline=time.monotonic()+10
 def step():
  dialog=app.activeModalWidget()
  try:
   assert time.monotonic()<deadline,'Review UI timed out'
   if not isinstance(dialog,QDialog):QTimer.singleShot(30,step);return
   table=dialog.findChild(QTableWidget)
   if not table.rowCount():QTimer.singleShot(30,step);return
   buttons={b.text():b for b in dialog.findChildren(QPushButton)}
   if state['phase']==0:
    table.selectRow(0)
    status=next(c for c in dialog.findChildren(QComboBox) if c.findData('confirmed_overlap')>=0)
    status.setCurrentIndex(status.findData('confirmed_overlap'));buttons['Save human review'].click();state['phase']=1
   elif state['phase']==1 and table.item(0,7).text()=='confirmed_overlap':
    dialog.findChild(QSpinBox).setValue(1)
    lines=dialog.findChildren(QLineEdit)
    next(w for w in lines if w.placeholderText()=='Reviewer name').setText('Greg')
    next(w for w in lines if w.placeholderText().startswith('What was actually')).setText('Reviewed clip: one additional tyre missed')
    buttons['Save missed adjustment'].click();state['phase']=2
   elif state['phase']==2:
    rows=store.rows(kind='overlap')
    if rows[0].get('adjustment',{}).get('quantity')==1:
     state['phase']=3;dialog.accept();return
   QTimer.singleShot(30,step)
  except Exception as e:
   state['error']=e
   if isinstance(dialog,QDialog):dialog.reject()
 QTimer.singleShot(30,step);open_review(None,store,'2026-11-23')
 assert not state['error'],state['error'];assert state['phase']==3
 assert store.rows(kind='overlap')[0]['adjustment']['revision']==1
 assert store.close()
print('PASS actual review UI confirms overlap and saves named, reasoned missed adjustment once')
