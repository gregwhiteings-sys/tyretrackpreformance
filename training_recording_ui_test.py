"""Real automatic-capture checkbox: new default, persisted off, no count changes."""
from test_resources import DatabaseTemporaryDirectory
from pathlib import Path
import os,sys,types,sqlite3
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None
m.Main._confirm_admin_pin=lambda self,action:True
app=QApplication.instance() or QApplication([])
with DatabaseTemporaryDirectory() as folder:
 m.DATA=Path(folder);m.DB=Path(folder)/'counts.db';m.init_db()
 ui=m.Main();ui.clock.stop()
 assert ui.auto_training_checkbox.isChecked() and m.AUTO_TRAINING_RECORDING
 assert not ui.record_oak_checkbox.isChecked()
 ui.auto_training_checkbox.setChecked(False);app.processEvents()
 assert not m.AUTO_TRAINING_RECORDING and m.get_state('auto_training_recording')=='0'
 ui.close();app.processEvents()
 ui=m.Main();ui.clock.stop()
 assert not ui.auto_training_checkbox.isChecked() and not m.AUTO_TRAINING_RECORDING
 ui.auto_training_checkbox.setChecked(True);app.processEvents()
 assert m.AUTO_TRAINING_RECORDING and m.get_state('auto_training_recording')=='1'
 ui.close();app.processEvents()
 with sqlite3.connect(m.DB) as c:assert c.execute('select count(*) from counts').fetchone()[0]==0
print('PASS real Qt auto recording defaults ON, manual stays OFF, later choice persists; no production counts')
