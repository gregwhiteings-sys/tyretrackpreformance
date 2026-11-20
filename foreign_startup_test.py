"""Requested FOD default-on migration, persistence and actual UI wiring."""
from test_resources import DatabaseTemporaryDirectory
from pathlib import Path
import os,sqlite3,sys,types
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
from foreign_startup import foreign_enabled_at_startup,MIGRATION_KEY
m.Main.tick=lambda self:None
m.Main._confirm_admin_pin=lambda self,action:True
app=QApplication.instance() or QApplication([])
with DatabaseTemporaryDirectory() as directory:
    m.DB=Path(directory)/'settings.db';m.init_db()
    # Simulate an existing installation which had saved FOD off.
    m.set_state('foreign_enabled','0');m.set_state('foreign_confidence','70')
    with sqlite3.connect(m.DB) as con:
        con.execute("INSERT INTO counts(ts,source,track_id,confidence) VALUES('2026-11-20T06:00:00','fixture',1,.9)")
    ui=m.Main();ui.clock.stop()
    assert 'FOD: ON' in ui.fod_badge.text()
    assert ui.foreign_switch.isChecked(), 'Update must enable existing installations once'
    assert ui.foreign_conf.value()==70, 'Retain the operator confidence setting'
    assert m.get_state(MIGRATION_KEY)=='1' and m.get_state('foreign_enabled')=='1'
    ui.foreign_switch.setChecked(False);app.processEvents()
    assert m.get_state('foreign_enabled')=='0'
    ui.close();app.processEvents()
    ui=m.Main();ui.clock.stop()
    assert 'FOD: OFF' in ui.fod_badge.text()
    assert not ui.foreign_switch.isChecked(), 'Later explicit off must persist'
    ui.close();app.processEvents()
    with sqlite3.connect(m.DB) as con:
        assert con.execute('SELECT COUNT(*) FROM counts').fetchone()[0]==1
    # A fresh installation also defaults on, with the model comparison threshold.
    m.DB=Path(directory)/'fresh.db';m.init_db()
    ui=m.Main();ui.clock.stop()
    assert ui.foreign_switch.isChecked() and ui.foreign_conf.value()==55
    ui.close();app.processEvents()
print('PASS: new install and existing-off upgrade enable FOD; later off persists; confidence/counts preserved; actual Qt checkbox wiring')
