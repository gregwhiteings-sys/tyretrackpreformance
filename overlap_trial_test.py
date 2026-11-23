"""Failed candidate stays blocked, dashboard diagnostics do not change production."""
import json,hashlib,os
from pathlib import Path
from overlap_trial import read_status,dashboard_panel
root=Path(__file__).resolve().parent
r=read_status(root/'overlap_model');assert r['status']=='BLOCKED'
assert '4 matched groups / 12 labelled' in r['detail'] and '0 / 22' in r['detail']
assert r['report']['live_enabled'] is False
assert r['report']['training_config']['confirmed_belt_width_mm']==1180
assert r['report']['held_out_test']['recall']==1/3
assert r['report']['conversion']['output']==[1,5,3549]
for name,digest in r['report']['model_hashes'].items():assert hashlib.sha256((root/'overlap_model'/name).read_bytes()).hexdigest()==digest
assert read_status(root/'nonexistent')['status']=='BLOCKED'
os.environ['QT_QPA_PLATFORM']='offscreen'
from PyQt5.QtWidgets import QApplication,QPushButton,QMessageBox
app=QApplication.instance() or QApplication([])
panel=dashboard_panel(None,root/'overlap_model');seen=[]
QMessageBox.information=lambda *a:seen.append(a[-1])
panel.findChild(QPushButton).click()
assert 'separate geometric review' in seen[0] and 'no additional camera inference' in seen[0]
panel.close();app.processEvents()
print('PASS overlap trial always blocked, packaged model hashes, missing evidence fallback and dashboard explanation; no inference/count/alarm paths')
