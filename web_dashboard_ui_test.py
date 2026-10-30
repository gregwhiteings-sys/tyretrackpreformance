"""Real admin connection-file controls; no network/camera/production writes."""
import os,sys,types,json
from pathlib import Path
from unittest.mock import patch,MagicMock
os.environ['QT_QPA_PLATFORM']='offscreen';stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication,QFileDialog
from test_resources import DatabaseTemporaryDirectory
import TyreTrack_Production_Monitor as m
from web_dashboard import URL
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *a:True
qt=QApplication.instance() or QApplication([])
with DatabaseTemporaryDirectory() as folder:
 m.DATA=Path(folder);m.DB=m.DATA/'test.db';m.PRIVATE_CONFIG_DIR=m.DATA/'private';m.init_db();w=m.Main();w.clock.stop()
 opener=MagicMock();w._web_publisher.opener=opener
 connection=m.DATA/'input.json';connection.write_text(json.dumps(dict(schema=1,url=URL,token='test-only-'+'x'*40)))
 try:
  assert not w.web_enabled.isChecked()
  with patch.object(QFileDialog,'getOpenFileName',return_value=(str(connection),'')):w.web_connect_btn.click()
  assert w._web_publisher.config and not w._web_publisher.config['enabled'];assert not opener.called
  w.web_enabled.setChecked(True);assert w._web_publisher.config['enabled']
  w.web_enabled.setChecked(False);assert not w._web_publisher.config['enabled'];assert not opener.called
  assert m.production_snapshot()['all_time']==0
 finally:w.close();qt.processEvents()
print('PASS: real connection-file import, opt-in controls, disabled default, private persistence and zero production writes/network requests')
