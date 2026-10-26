TYRETRACK STREAM RECOVERY — 27 OCTOBER 2026

Complete GitHub-ready source package, not a compiled Windows EXE.
Upload all files to the same repository, replacing matching files, then rerun
the Windows build workflow and download its newly built portable application.
Close the installed TyreTrack before replacing the application files.
Keep the site's existing data, reports and private email/configuration files.
Do not run the old and new application together against the camera.

FIX AND QUALITY UPGRADE:
The extra on-camera resize stage is removed. Smooth view now takes the existing
640x360 NV12 camera video directly. This is four times the pixels of the previous
320x180 live view without adding an ImageManip processing node. AI, count logic
and recording settings are preserved. The 480x270 original preview is available
by closing the app and launching RUN_SAFE_PREVIEW.bat beside TyreTrack.exe.
Normal launch uses the sharper 640x360 preview. Show Boxes stays on analysed
frames at their original resolution. Current dashboard, weights and sounds stay.
Background PNG saving stays off the GUI thread.

After installing, check the camera live image, then Show Boxes and count-line
crossings while tyres actually travel through the lines during production.
Automatic production remains Monday-Friday 05:00-17:05 Brisbane.
Outside those hours use the existing manual OAK test (isolated test totals).
The included RUN_OAK_HARDWARE_TEST.bat checks real preview/neural/recording
streams without changing production totals; it does not prove count accuracy.

No physical OAK is attached in the development environment. If it still fails,
send the latest application log, especially OAK AI STALL, capture/recording
failed, connection errors and OAK stream summary, plus a dashboard screenshot.
Do not reset the count database or delete history to troubleshoot the stream.
