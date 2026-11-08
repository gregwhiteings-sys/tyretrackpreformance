TYRETRACK DASHBOARD PATCH

IMPORTANT: Extract this ZIP directly into the TyreTrack project root, the same folder as run_ci_tests.py. When asked, replace the existing TyreTrack_Production_Monitor.py.

The Python file is at the top level of this ZIP. Do not extract it into a subfolder.

Then run: python -u run_ci_tests.py

The hourly tiles use the average of completed hours: red is below the rounded average, orange is on it, and green is above it. The current hour compares with completed hours so far. This patch adds no camera processing or polling.
