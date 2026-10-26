@echo off
setlocal
cd /d "%~dp0"
if not exist "TyreTrack.exe" (
 echo Run this launcher beside the compiled TyreTrack.exe.
 pause
 exit /b 1
)
echo Close any running TyreTrack instance before continuing.
echo Starting with the original direct 480x270 preview.
set "TYRETRACK_SAFE_PREVIEW=1"
start "" /D "%~dp0" "%~dp0TyreTrack.exe"
endlocal
