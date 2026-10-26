"""PCM resource checks and Windows audio-call behavior; does not claim speaker testing."""
from test_resources import DatabaseTemporaryDirectory
import os,sys,types,tempfile,wave,array
from pathlib import Path, PureWindowsPath
from unittest.mock import Mock
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *args:True
qt=QApplication.instance() or QApplication([])
for key,(label,name) in m.CELEBRATION_SOUNDS.items():
 with wave.open(str(m.resource_path(name)),'rb') as source:
  assert source.getcomptype()=='NONE' and source.getsampwidth()==2
  duration=source.getnframes()/source.getframerate();samples=array.array('h',source.readframes(source.getnframes()))
  assert 1<duration<=60.1 and max(abs(x) for x in samples)>1000
 print('PASS: valid non-silent PCM audio',name,round(duration,2),'seconds')
def close_test_windows(windows):
 for window in reversed(windows):
  window.clock.stop()
  window.close()
  for name in ("_dashboard_loader","_snapshot_writer","_csv_exporter"):
   worker=getattr(window,name,None)
   if worker is not None:assert worker.wait(5),name+" did not stop"
 qt.processEvents()

# The old string suffix assertion fails for native Windows backslashes.
assert PureWindowsPath(r"C:\pack\celebration_sounds\ao_theme.wav")==PureWindowsPath("C:/pack/celebration_sounds/ao_theme.wav")
with DatabaseTemporaryDirectory() as folder:
 m.DATA=Path(folder);m.DB=Path(folder)/'test.db';m.init_db();
 windows=[]
 try:
  w=m.Main();windows.append(w);w.clock.stop();w.alarm_state={'latched':False}
  backend=types.SimpleNamespace(SND_FILENAME=1,SND_ASYNC=2,SND_NODEFAULT=4,PlaySound=Mock())
  for key in m.CELEBRATION_SOUNDS:
   w.celebration_sound_combo.setCurrentIndex(w.celebration_sound_combo.findData(key))
   assert m.get_state('celebration_sound','cheer')==key
   assert w.play_celebration_sound(preview=True,backend=backend)
   actual=Path(backend.PlaySound.call_args.args[0]).resolve()
   expected=m.resource_path(m.CELEBRATION_SOUNDS[key][1]).resolve()
   assert actual==expected,(actual,expected)
   assert backend.PlaySound.call_args.args[1]==7
  w.celebration_sound_combo.setCurrentIndex(w.celebration_sound_combo.findData("random"))
  m.set_state('celebration_shuffle','{}')
  previous=None;seen=set()
  for cycle in range(3):
   cycle_files=[]
   for _ in range(len(m.CELEBRATION_SOUNDS)):
    assert w.play_celebration_sound(preview=(cycle!=1),backend=backend)
    filename=backend.PlaySound.call_args.args[0]
    assert filename!=previous
    cycle_files.append(filename);seen.add(filename);previous=filename
   assert len(set(cycle_files))==len(m.CELEBRATION_SOUNDS)
  assert len(seen)==len(m.CELEBRATION_SOUNDS)
  # A failed Windows start must not consume the next item in the persisted bag.
  before=m.get_state('celebration_shuffle')
  backend.PlaySound.side_effect=RuntimeError('speaker unavailable')
  assert not w.play_celebration_sound(preview=True,backend=backend)
  assert m.get_state('celebration_shuffle')==before
  backend.PlaySound.side_effect=None
  # Import through the real dialog handler, select Random, then rediscover after restart.
  from unittest.mock import patch
  with patch.object(m.QFileDialog,'getOpenFileName',return_value=(str(m.resource_path(next(iter(m.CELEBRATION_SOUNDS.values()))[1])),'')):
   w.add_celebration_sound()
  assert w.celebration_sound_combo.currentData()=='random'
  assert 'shuffle all sounds' in w.celebration_indicator.text()
  custom=[k for k in w.celebration_sounds if k.startswith('custom_')]
  assert custom
  w.celebration_sound_combo.setCurrentIndex(w.celebration_sound_combo.findData('ao_theme'))
  assert 'AO theme' in w.celebration_indicator.text()
  w.celebration_sound_combo.setCurrentIndex(0)
  w.celebration_mute.setChecked(True);backend.PlaySound.reset_mock()
  assert not w.play_celebration_sound(backend=backend);backend.PlaySound.assert_not_called()
  assert w.play_celebration_sound(preview=True,backend=backend)
  assert w.stop_celebration_preview(backend=backend);assert backend.PlaySound.call_args.args==(None,0)
  w.alarm_state={'latched':True};backend.PlaySound.reset_mock()
  assert not w.play_celebration_sound(preview=True,backend=backend)
  assert not w.stop_celebration_preview(backend=backend);backend.PlaySound.assert_not_called()
  w.alarm_state={'latched':False}
  saved=w.play_celebration_sound;w.play_celebration_sound=Mock();w.test_sound_btn.click()
  w.play_celebration_sound.assert_called_once_with(preview=True);w.play_celebration_sound=saved
  w.close()
  w=m.Main();windows.append(w);w.clock.stop();assert any(k.startswith("custom_") for k in w.celebration_sounds);w.close()
 finally:
  close_test_windows(windows)

# Reproduce an early assertion failure while a real dashboard reader may be active.
# Cleanup must stop that reader and release the database before directory deletion.
failed_folder=None
try:
 with DatabaseTemporaryDirectory() as folder:
  failed_folder=Path(folder);m.DATA=Path(folder);m.DB=Path(folder)/'test.db';m.init_db()
  windows=[]
  try:
   w=m.Main();windows.append(w);w.clock.stop()
   raise AssertionError('intentional cleanup probe')
  finally:close_test_windows(windows)
except AssertionError as exc:
 assert str(exc)=='intentional cleanup probe',str(exc)
assert not failed_folder.exists()
print('PASS: Windows path equivalence and exception-path window/reader shutdown before SQLite temp cleanup')
print('PASS: selector persistence, selected file/async flags, automatic mute, explicit test, stop, alarm priority and button wiring; physical speaker playback pending')
