TYRETRACK DASHBOARD UPDATE PATCH

This small patch contains the updated main application source file.

To apply it to the full TyreTrack source package:
1. Extract your TyreTrack source ZIP into a folder.
2. Copy TyreTrack_Production_Monitor.py from this patch over the existing file with the same name.
3. Upload the updated source folder to the TyreTrack GitHub repository and run the existing Windows Portable workflow.

The hourly tiles use the average of completed hours: red is below the rounded average, orange is on it, and green is above it. The current hour is compared with completed hours so far. The layout reuses the existing dashboard refresh; it adds no camera processing or polling.

This is a source patch, not a compiled Windows EXE.
