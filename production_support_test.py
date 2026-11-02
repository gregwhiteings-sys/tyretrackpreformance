"""Real SQLite/WAL restore, health privacy/isolation, timeline and Qt heartbeat."""
from contextlib import closing
from datetime import datetime,timedelta
from pathlib import Path
import json,os,sqlite3,tempfile,time,zipfile,threading
from unittest.mock import patch
from production_support import create_backup,activity_bins,read_observations,write_observation,SupportService
from hourly_dashboard import BRISBANE
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
os.environ['QT_QPA_PLATFORM']='offscreen'
now=datetime(2026,11,2,7,tzinfo=BRISBANE)
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);db=root/'tyretrack.db';config=root/'private_config';config.mkdir()
 (config/'settings.json').write_text('{"test":"private fixture"}')
 with closing(sqlite3.connect(db)) as con:
  con.execute('PRAGMA journal_mode=WAL');con.execute('CREATE TABLE sample(id INTEGER,value TEXT)')
  con.execute("INSERT INTO sample VALUES(1,'preserved')");con.commit()
  backup=create_backup(db,config,root/'backups','2026-11-02')
  assert con.execute('SELECT * FROM sample').fetchall()==[(1,'preserved')]
 with zipfile.ZipFile(backup) as archive:
  assert archive.testzip() is None and set(archive.namelist())=={'data/tyretrack.db','data/private_config/settings.json','RESTORE_README.txt'}
  archive.extract('data/tyretrack.db',root/'restore')
 with closing(sqlite3.connect(root/'restore/data/tyretrack.db')) as restored:
  assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  assert restored.execute('SELECT * FROM sample').fetchall()==[(1,'preserved')]
 assert create_backup(db,config,root/'backups','2026-11-02')==backup
 history=root/'system_health'
 sample=dict(at=now.isoformat(),camera='online',testing=False,frames=10)
 write_observation(history,sample);write_observation(history,sample)
 rows=read_observations(history,now-timedelta(hours=1),now+timedelta(hours=1));assert len(rows)==1
 slots=activity_bins([(now,'passenger')],now-timedelta(hours=1),now+timedelta(hours=2),rows)
 assert [s['state'] for s in slots]==['unobserved','activity','unobserved']
 assert activity_bins([],now,now+timedelta(hours=1),rows)[0]['state']=='no counts observed'
 assert activity_bins([],now,now+timedelta(hours=1),[{**sample,'camera':'stale'}])[0]['state']=='camera issue'
 assert activity_bins([(now,'x')],now,now+timedelta(hours=1),[{**sample,'camera':'stale'}])[0]['state']=='activity / camera issue'
 service=SupportService(db,config,root)
 service.request({**sample,'testing':True},force_backup=True);assert service.wait()
 assert service.snapshot()['backup']=='Paused during test'
 service.request({**sample,'at':now.replace(hour=18).isoformat()},True);assert service.wait()
 assert (root/'backups/TyreTrack_2026-11-02_close.zip').is_file()
 assert service.snapshot()['last_backup']=='2026-11-02_close'
 service=SupportService(db,config,root)  # Last successful backup survives restart.
 service.free_gb=.5;service.last_disk_check=time.monotonic()
 service.request({**sample,'at':(now+timedelta(days=1)).isoformat()},True);assert service.wait()
 assert 'less than 2 GB' in service.snapshot()['error']
 assert service.snapshot()['last_backup']=='2026-11-02_close'
 assert not (root/'backups/TyreTrack_2026-11-03.zip').exists()

 # Blocked backup does not stop Qt; duplicate requests do not overlap.
 gate=threading.Event();entered=threading.Event();calls=[]
 def blocked(*args):entered.set();calls.append(1);gate.wait(5);raise OSError("simulated backup failure")
 app=QApplication.instance() or QApplication([]);beats=[]
 timer=QTimer();timer.timeout.connect(lambda:beats.append(1));timer.start(5)
 with patch('production_support.create_backup',blocked):
  service=SupportService(db,config,root/'service');service.data.mkdir()
  service.request(sample,True);assert entered.wait(1)
  service.request(sample,True)
  end=time.monotonic()+.1
  while time.monotonic()<end:app.processEvents();time.sleep(.001)
  assert len(beats)>3 and len(calls)==1
  gate.set();assert service.wait()
 timer.stop()
 assert 'error' in service.snapshot()
print('PASS WAL backup/restore and ZIP integrity, private config scope, idempotent daily backup, health minute coalescing, timeline distinctions, test isolation, no overlap and Qt heartbeat during blocked backup')
