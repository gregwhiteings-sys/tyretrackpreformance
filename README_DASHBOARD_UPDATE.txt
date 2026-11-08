TYRETRACK DASHBOARD + MODEL INTEGRITY PATCH

Extract this ZIP directly into the TyreTrack project root, the same folder as run_ci_tests.py. Choose Replace for existing files.

Included at the ZIP root:
- TyreTrack_Production_Monitor.py: dashboard changes and responsive full-width hourly/weekday totals.
- rvc2_models/sha256.json and rvc2_models/foreign/: the matching model manifest, configuration, build metadata and blob from the supplied TyreTrack source bundle. These files restore a consistent checksum set.

After extraction, commit the replaced files to the TyreTrack GitHub repository and run:
python -u run_ci_tests.py

This is a source patch, not a compiled Windows EXE.
