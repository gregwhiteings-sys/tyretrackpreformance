"""Real supervisor dialog displays recovery status, imported reply and full comments."""
import os,sys,types
from pathlib import Path
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication,QDialog,QTableWidget,QLabel
from PyQt5.QtGui import QPalette
from test_resources import DatabaseTemporaryDirectory
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *a:True
qt=QApplication.instance() or QApplication([])
with DatabaseTemporaryDirectory() as folder:
 m.DATA=Path(folder);m.DB=m.DATA/'test.db';m.init_db();w=m.Main();w.clock.stop()
 now=m.brisbane_now();ident='NC-'+now.strftime('%Y%m%d')+'-050000'
 m.no_count_replies.create_incident(m.DB,ident,now.strftime('%Y-%m-%d')+' 05:00:00',now.strftime('%Y-%m-%d')+' 05:14:24')
 with m.no_count_replies.db_connection(m.DB) as con:
  con.execute("UPDATE supervisor_no_count SET status='COMPLETED',reason='[Waiting for tyres / Scheduled break / Conveyor stopped]',supervisor='[Your name]',comments='[Optional details]'")
 def pending(dialog):
  table=dialog.findChild(QTableWidget);assert table.rowCount()==1
  assert table.item(0,3).text()=='AWAITING RESPONSE'
  assert table.item(0,4).text()=='Awaiting reply'
  return 0
 def received(dialog):
  dialog.show();qt.processEvents()
  table=dialog.findChild(QTableWidget);assert table.item(0,3).text()=='COMPLETED'
  assert table.item(0,5).text()=='Greg';table.selectRow(0);qt.processEvents()
  assert any('TEST ONLY' in label.text() for label in dialog.findChildren(QLabel))
  assert table.palette().color(QPalette.AlternateBase).name()=='#183149'
  dialog.hide();return 0
 try:
  with patch.object(QDialog,'exec_',pending):w.open_supervisor_reports()
  assert m.no_count_replies.record_reply(m.DB,ident,'Other','Greg','TEST ONLY - checking dashboard reception.','<test-ui>')
  with patch.object(QDialog,'exec_',received):w.open_supervisor_reports()
 finally:w.close();qt.processEvents()
print('PASS: real report dialog reopens template record, shows Greg/Other/test comment, selection detail and readable alternate row palette')
