@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0startup_shortcut.ps1" -Action Install
if errorlevel 1 echo Installation failed. Read the message above.
pause
