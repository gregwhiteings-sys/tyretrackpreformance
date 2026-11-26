"""Real Qt dashboard/review interactions; CPU model stub, isolated state, no camera/network."""
import os,sys,types,time,threading
from test_resources import DatabaseTemporaryDirectory
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication,QDialog,QComboBox,QPushButton
from PyQt5.QtCore import QTimer
import TyreTrack_Production_Monitor as m
from classification_review import ReviewStore
from classification_review_ui import open_review
app=QApplication.instance() or QApplication([]);m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *a:True
with DatabaseTemporaryDirectory() as tmp:
 p=Path(tmp);m.DATA=p/'data';m.DATA.mkdir();m.DB=m.DATA/'counts.db';m.REPORTS=p/'reports';m.REPORTS.mkdir();m.init_db()
 w=m.Main();w.clock.stop();assert w.belt_mode.currentData()=='compare'
 w.belt_mode.setCurrentIndex(w.belt_mode.findData('assist'));assert not w.belt_observe.isChecked()
 w.belt_mode.setCurrentIndex(w.belt_mode.findData('compare'));assert w.belt_observe.isChecked()
 def close_advanced():
  for d in app.topLevelWidgets():
   if isinstance(d,QDialog) and d.windowTitle()=='Advanced belt-edge setup':d.accept()
 QTimer.singleShot(100,close_advanced);w.open_belt_edge_setup()
 assert all(control.parent() is w for _,control in w.belt_edges)
 w.show_comparison_dashboard({'original_counts':{'passenger':7,'4x4':3},'assisted_counts':{'passenger':6,'4x4':4},'final_counts':{'passenger':7,'4x4':3},'measured':8,'tyres':10,'disagreements':1})
 assert w.review_cards.values['passenger'].text()=='6'
 assert w.review_cards.values['4x4'].text()=='4'
 assert w.review_cards.additions.text()=='+0'
 assert not hasattr(w,'classification_comparison_label')
 store=w.get_review_store();store.submit('foreign',{'timestamp':'2026-11-23T08:00:00+10:00','predicted_class':'metal_object'},key='one');assert store.flush(), 'Review writer failed to drain'
 assert store.rows(), store.last_error
 errors=[]
 deadline=time.monotonic()+10
 def check():
  try:
   d=next(d for d in app.topLevelWidgets() if isinstance(d,QDialog) and d.windowTitle().startswith('Tyre comparison'))
   combos=d.findChildren(QComboBox)
   available=[c for c in combos if c.findData('false_alert')>=0]
   if not available:
    if time.monotonic()<deadline:QTimer.singleShot(30,check);return
    from PyQt5.QtWidgets import QLabel
    raise AssertionError('Review record did not load: '+ ' | '.join(l.text() for l in d.findChildren(QLabel)))
   status=available[0];status.setCurrentIndex(status.findData('false_alert'))
   reason=next(c for c in combos if c.findData('normal_tyre')>=0);reason.setCurrentIndex(reason.findData('normal_tyre'))
   save=next(b for b in d.findChildren(QPushButton) if b.text()=='Save human review')
   save.click()
   def saved():
    if store.rows()[0]['status']=='false_alert':d.accept()
    elif time.monotonic()<deadline:QTimer.singleShot(30,saved)
    else:errors.append(AssertionError('Review was not saved before timeout'));d.reject()
   QTimer.singleShot(30,saved)
  except Exception as exc:
   errors.append(exc)
   for d in app.topLevelWidgets():
    if isinstance(d,QDialog):d.reject()
 QTimer.singleShot(350,check);open_review(w,store,'2026-11-23')
 assert not errors,errors
 assert store.rows()[0]['status']=='false_alert';assert m.production_snapshot()['all_time']==0
 import numpy as np,cv2
 m.send_message=lambda *args,**kwargs:False
 w.request_conveyor_stop=lambda event:None
 original=np.zeros((80,100,3),dtype=np.uint8);original[:]=(20,140,20)
 w.on_foreign_alarm(dict(frame=original,box=[10,10,50,50],class_name='metal_object',confidence=.9,
     timestamp='2026-11-23T09:00:00+10:00',source_kind='oak',source='fixture',track_id=7,model_sha256='fixture-model'))
 assert store.flush()
 saved=next(r for r in store.rows() if r['payload'].get('clean_inference_image'))
 raw=cv2.imread(str(store.image_path(saved)));assert not ((raw[:,:,2]>180)&(raw[:,:,1]<60)).any()
 annotated=cv2.imread(saved['payload']['snapshot']);assert ((annotated[:,:,2]>180)&(annotated[:,:,1]<60)).any()
 assert saved['status']=='unreviewed' and saved['payload']['model_sha256']=='fixture-model'
 assert m.production_snapshot()['all_time']==0
 # Reproduce the Windows cleanup race deterministically: a dashboard reader
 # is still opening the review DB when the main window begins closing.
 previous=getattr(w,'_review_dashboard_thread',None)
 if previous is not None:previous.join(6)
 app.processEvents();w._review_dashboard_busy=False
 entered=threading.Event();release=threading.Event();completed=threading.Event()
 real_rows=store.rows
 def delayed_rows(*args,**kwargs):
  if threading.current_thread().name=='review-dashboard-read':
   entered.set();assert release.wait(5), 'Test reader release timed out'
   try:return real_rows(*args,**kwargs)
   finally:completed.set()
  return real_rows(*args,**kwargs)
 store.rows=delayed_rows
 w.refresh_comparison_dashboard();assert entered.wait(2)
 reader=w._review_dashboard_thread
 join_started=threading.Event();real_join=reader.join
 def joining_reader(timeout=None):
  join_started.set();return real_join(timeout)
 reader.join=joining_reader
 def release_on_shutdown():
  deadline=time.monotonic()+3
  while not w.closing and time.monotonic()<deadline:time.sleep(.005)
  assert w.closing, 'Window never began shutdown'
  join_started.wait(3)
  release.set()
 releaser=threading.Thread(target=release_on_shutdown);releaser.start()
 w.close();releaser.join(5)
 assert join_started.is_set(), 'Window close did not join its dashboard reader'
 assert completed.is_set() and not reader.is_alive(), 'Dashboard reader outlived window close'
 assert not w.review_dashboard_timer.isActive()
 w._review_dashboard_busy=False
 w.refresh_comparison_dashboard()
 assert w._review_dashboard_thread is reader, 'A new reader started during shutdown'
 app.processEvents()
 assert not reader.is_alive()
 assert store.close(), "Review writer did not stop before fixture cleanup"
assert not p.exists(), 'Temporary database directory was not removed'
print('PASS delayed dashboard reader joined before close; refresh disabled during shutdown; no cleanup-error suppression')
print('PASS fixture explicitly closes UI SQLite handles and rejects leaked worker handles before Windows cleanup')
print('PASS real dashboard comparison, simple mode selection, review dialog false-alert save and zero production counts; model stub/no camera')
