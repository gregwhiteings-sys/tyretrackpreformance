"""PCM resource checks and Windows audio-call behavior; does not claim speaker testing."""
import os,sys,types,tempfile,wave,array
from pathlib import Path
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
  assert 1<duration<=8.1 and max(abs(x) for x in samples)>1000
 print('PASS: valid non-silent PCM audio',name,round(duration,2),'seconds')
with tempfile.TemporaryDirectory() as folder:
 m.DB=Path(folder)/'test.db';m.init_db();w=m.Main();w.clock.stop();w.alarm_state={'latched':False}
 backend=types.SimpleNamespace(SND_FILENAME=1,SND_ASYNC=2,SND_NODEFAULT=4,PlaySound=Mock())
 for key in m.CELEBRATION_SOUNDS:
  w.celebration_sound_combo.setCurrentIndex(w.celebration_sound_combo.findData(key))
  assert m.get_state('celebration_sound','cheer')==key
  assert w.play_celebration_sound(preview=True,backend=backend)
  assert backend.PlaySound.call_args.args[0].endswith(m.CELEBRATION_SOUNDS[key][1])
  assert backend.PlaySound.call_args.args[1]==7
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
print('PASS: selector persistence, selected file/async flags, automatic mute, explicit test, stop, alarm priority and button wiring; physical speaker playback pending')
