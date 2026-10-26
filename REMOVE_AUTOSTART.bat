@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0startup_shortcut.ps1" -Action Remove
if errorlevel 1 echo Removal failed. Read the message above.
pause
