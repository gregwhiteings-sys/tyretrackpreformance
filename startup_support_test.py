"""Check install script contract and real Qt single-instance locks without Windows changes."""
import ast,tempfile
from pathlib import Path
from PyQt5.QtCore import QLockFile,QCoreApplication
root=Path(__file__).resolve().parent
qt=QCoreApplication.instance() or QCoreApplication([])
with tempfile.TemporaryDirectory() as tmp:
 path=str(Path(tmp)/'instance.lock')
 first=QLockFile(path);second=QLockFile(path)
 first.setStaleLockTime(0);second.setStaleLockTime(0)
 assert first.tryLock(0)
 assert not second.tryLock(0)
 first.unlock();assert second.tryLock(0);second.unlock()
s=(root/'startup_shortcut.ps1').read_text()
for token in ["GetFolderPath('Startup')","TyreTrack Production.lnk",'$shortcut.TargetPath = $exePath','$shortcut.WorkingDirectory = $PSScriptRoot',"$Action -eq 'Remove'",'Test-Path -LiteralPath $exePath']:
 assert token in s,token
for name,action in [('INSTALL_AUTOSTART.bat','Install'),('REMOVE_AUTOSTART.bat','Remove')]:
 assert '%~dp0startup_shortcut.ps1' in (root/name).read_text()
 assert '-Action '+action in (root/name).read_text()
code=(root/'TyreTrack_Production_Monitor.py').read_text();ast.parse(code)
assert code.index('if "--build-smoke-test"') < code.index('instance_lock = QLockFile') < code.index('    window = Main()')
assert 'instance_lock.tryLock(0)' in code
print('PASS: current-user sign-in shortcut contract, removal, executable path, build/test bypass, real Qt duplicate launch exclusion and lock release; actual Windows sign-in pending')
