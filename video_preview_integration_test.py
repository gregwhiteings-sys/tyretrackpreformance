"""Run the real video-test subprocess and observe its frames in the real Qt window."""
import os,sys,types,time,tempfile,json
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *args:True
app=QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory() as folder:
 root=Path(folder);m.DB=root/'production.db';m.REPORTS=root/'reports';m.REPORTS.mkdir();m.init_db()
 w=m.Main();w.clock.stop();w.show();w.open_video_test()
 w.video_test_file.setText(str(Path(__file__).with_name('test_data')/'oak_h264_sample.h264'))
 w.top_line_slider.setValue(10);w.bottom_line_slider.setValue(90)
 w.start_video_test();w.top_line_slider.setValue(15);w.left_span_slider.setValue(20);w.right_span_slider.setValue(80);seen=False;deadline=time.monotonic()+60
 while time.monotonic()<deadline:
  app.processEvents();w.poll_video_test_preview();w.refresh_logic_test()
  seen=seen or w.video._pix is not None
  if w._replay_process is None:break
  time.sleep(.015)
 else:
  w.stop_video_test();raise AssertionError('Real replay did not finish within 60 seconds')
 assert seen,'No video frame reached the dashboard'
 assert 'COMPLETE' in w.test_transport.text(),w.video_test_status.text()
 assert w.test_progress.value()==1000
 summary=json.loads((w._replay_output/'test_summary.json').read_text())
 assert summary['frames']==45 and not summary['production_totals_modified'],summary
 assert len(json.loads((w._replay_output/'mode_comparison.json').read_text())['results'])==3
 assert summary['top']==.15 and summary['bottom']==.9 and len(summary['geometry_changes'])>=2,summary
 assert summary['left']==.2 and summary['right']==.8,summary
 assert m.production_snapshot()['all_time']==0
 w.close()
print('PASS: actual child inference, 45-frame video, dashboard preview, 100% completion, three-mode results, zero production writes')
