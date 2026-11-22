TYRETRACK BELT-WIDTH SIZE ASSIST — EXPERIMENTAL SOURCE BUILD

Based on TyreTrack_Rubber_Ring_FOD_On_Updated_Build.zip (20 Nov 2026).
All original .pt/.blob files retained byte-for-byte. Foreign detection stays on by its existing default.

COUNTING tab: Belt size assist. Initially enabled, assumed inside width 1100 mm.
This is a guess, not a site measurement. Measure between the usable inside belt edges.
The four edge controls define straight lines at the top/bottom of the full camera image.
Initial geometry is estimated for OAK_RGB_20261119_131314_292944.mp4, 640x360.
It scales with image dimensions, but not with camera movement, a crop, or lens/FOV changes.
Observe only displays estimates without changing the visual class result.
Uncheck Use belt-width size support to revert entirely to visual classification.
Settings persist and apply while connected; changing them clears previous size samples.
Show Tyre Labels displays size~XXXmm TRIAL and assisted when a label changed.

METHOD
Tyre box width divided by interpolated inside belt width at the tyre box centre,
multiplied by the assumed physical belt width. At least five unique observations,
within 35-75 percent image height; shape, clipping, intersection and stability checks.
Overlapping/nested boxes are rejected conservatively. Bbox shape cannot establish true
flatness, and tyre height, lens distortion and perspective still bias estimates.
Not all actual overlaps/tilts are detectable from bounding boxes.
450-680mm: passenger size candidate. 680-730mm: visual fallback.
730-900mm: SUV/4x4 size candidate. Other sizes: visual fallback, not truck assignment.
Only passenger/4x4 visual vote scores below 80 percent can change. Unknown/truck and
strong visual votes are retained. Original visual confidence is retained; size is not
presented as an independently calibrated class probability.
No extra counts, separate foreign events, or changes to line crossings are introduced.

VALIDATION HERE
Six new automated tests passed: scale sensitivity, decisions/fallback, stable-frame
and freshness gates, occlusion/shape guards, invalid geometry, and execution of actual
worker event/UI configuration code. Syntax compilation passed. Original model hashes
and compatibility audit passed. Three-line, span and forecast pure-Python checks passed.
The GUI parts of adjustable_bounds_test.py and tyre_weight_test.py could not run here:
PyQt5 is not installed. Full CI and Windows freeze were NOT run in this environment.
No live OAK camera, measured calibration, labelled accuracy evaluation or onsite test.

BUILD
This ZIP is complete SOURCE, not a precompiled Windows executable. Extract into your
GitHub repository root, retaining the .github folder. Run the included TyreTrack Windows
Portable Build workflow manually (Actions -> Run workflow). It runs the regression
suite before creating TyreTrack-Windows-x64-Portable.zip. Keep the last working build.
Compare passenger/SUV results with known physical tyres before relying on this trial.
