"""The supplied recording is the sole bundled alert and is used for best hours only."""
from test_resources import DatabaseTemporaryDirectory
import os,sys,types,wave,array
from pathlib import Path,PureWindowsPath
from unittest.mock import Mock
os.environ['QT_QPA_PLATFORM']='offscreen'
stub=types.ModuleType('ultralytics');stub.YOLO=object;sys.modules['ultralytics']=stub
from PyQt5.QtWidgets import QApplication
import TyreTrack_Production_Monitor as m
qt=QApplication.instance() or QApplication([])
m.Main.tick=lambda self:None;m.Main._confirm_admin_pin=lambda *args:True
assert len(m.CELEBRATION_SOUNDS)==21
for key,(_label,name) in m.CELEBRATION_SOUNDS.items():
 path=m.resource_path(name)
 with wave.open(str(path),'rb') as audio:
  assert audio.getcomptype()=='NONE' and audio.getsampwidth()==2 and audio.getnchannels()==1
  duration=audio.getnframes()/audio.getframerate()
  samples=array.array('h',audio.readframes(audio.getnframes()))
  assert 0<duration<60 and max(abs(x) for x in samples)>0,(key,duration)
print('PASS: all 21 supplied clips are valid, non-silent PCM WAVs under 60 seconds')
with DatabaseTemporaryDirectory() as folder:
 m.DB=Path(folder)/'test.db';m.DATA=Path(folder);m.init_db()
 w=m.Main();w.clock.stop();w.alarm_state={'active':False}
 assert w.celebration_sound_combo.count()==22
 assert w.celebration_sound_combo.currentData()=='random'
 backend=types.SimpleNamespace(SND_FILENAME=1,SND_ASYNC=2,SND_NODEFAULT=4,PlaySound=Mock())
 assert w.play_celebration_sound(preview=True,backend=backend)
 assert Path(backend.PlaySound.call_args.args[0]).resolve()==m.resource_path(m.CELEBRATION_SOUNDS[w._last_celebration_sound][1]).resolve()
 assert backend.PlaySound.call_args.args[1]==7
 w.celebration_sound_combo.setCurrentIndex(w.celebration_sound_combo.findData('voicy_01'))
 assert w.play_celebration_sound(preview=True,backend=backend)
 assert Path(backend.PlaySound.call_args.args[0]).resolve()==m.resource_path(m.CELEBRATION_SOUNDS['voicy_01'][1]).resolve()
 w.celebration_sound_combo.setCurrentIndex(w.celebration_sound_combo.findData('random'))
 w.celebration_mute.setChecked(True);backend.PlaySound.reset_mock()
 assert not w.play_celebration_sound(backend=backend);backend.PlaySound.assert_not_called()
 assert w.play_celebration_sound(preview=True,backend=backend)
 assert w.stop_celebration_preview(backend=backend)
 w.alarm_state={'active':True};backend.PlaySound.reset_mock()
 assert not w.play_celebration_sound(preview=True,backend=backend);backend.PlaySound.assert_not_called()
 assert not w.stop_celebration_preview(backend=backend)
 assert PureWindowsPath(r'C:\\pack\\celebration_sounds\\voicy_01.wav')==PureWindowsPath('C:/pack/celebration_sounds/voicy_01.wav')
 w.close()
print('PASS: shuffled and selected playback, Windows flags, mute, preview, stop and operational-alarm priority')
