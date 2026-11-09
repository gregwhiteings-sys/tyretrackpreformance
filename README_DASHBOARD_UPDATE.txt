TYRETRACK INDUSTRIAL CLARITY DASHBOARD PATCH

Extract this ZIP into the TyreTrack project root, the same folder as run_ci_tests.py, and choose Replace for existing files.

Included at the ZIP root:
- TyreTrack_Production_Monitor.py: the selected high-visibility dashboard layout, with camera and class totals on the left; Today, This Hour, Best Hour, Best Day, averages, projections, hourly totals, and weekday totals; charcoal panels, gold headings, and green/red/orange hourly pace indicators.
- rvc2_models/sha256.json and rvc2_models/foreign/: the matching model manifest, configuration, build metadata, and blob from the supplied TyreTrack source bundle.

Hourly colors compare each available hour with the rounded displayed hourly average: red below, orange equal, and green above. Class totals shown under the camera reuse the existing count and weight values. Camera inference, line-crossing logic, and database polling are unchanged.

After extraction, commit the replaced files to the TyreTrack GitHub repository and run:
python -u run_ci_tests.py

This is a source patch, not a compiled Windows EXE.
