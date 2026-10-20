"""Dedicated video test works without a camera, suspends reconnects and isolates results."""
import os,sys,types,tempfile,json
from pathlib import Path
from unittest.mock import patch,Mock
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *args:True
app=QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);m.DB=root/'production.db';m.REPORTS=root/'reports';m.REPORTS.mkdir();m.init_db()
 w=m.Main();w.clock.stop();w.open_video_test();app.processEvents()
 assert w.video_test_dialog.isVisible()
 video=root/'recording.mp4';video.write_bytes(b'fixture placeholder; subprocess is mocked')
 w.video_test_file.setText(str(video));w.video_test_hand.setText('12')
 process=Mock();process.pid=42;process.poll.return_value=None
 with patch('subprocess.Popen',return_value=process) as launch:
  w.start_video_test()
  assert w.offline_testing and not w.video_test_pending
  command=launch.call_args.args[0]
  assert '--replay-test' in command and '--compare-modes' in command and '--stop-file' in command
  assert command[command.index('--hand-count')+1]=='12'
  assert command[command.index('--video')+1]==str(video)
 w.start=Mock();w.schedule_tick();w.start.assert_not_called()
 w.stop_video_test();assert (w._replay_output/'stop.request').exists()
 process.poll.return_value=0;process.returncode=0
 (w._replay_output/'mode_comparison.json').write_text(json.dumps({'results':{'zigzag':{'final_unique_total':12,'difference':0}}}))
 w.refresh_logic_test();assert 'Diagonal: 12' in w.video_test_status.text()
 assert 'Stopped early' in w.video_test_status.text()
 assert m.production_snapshot()['all_time']==0
 w.return_live_mode();assert not w.offline_testing;w.start.assert_called_once_with(automatic=True)
 w.video_test_dialog.close();w.close()
print('PASS: camera-free video selection, start/stop, all-mode comparison, reconnect suppression, result display and zero production writes')
