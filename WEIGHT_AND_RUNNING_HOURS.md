# Production weight and running-hour reporting

Hourly, daily and weekly dashboard cards include estimated weight beside the
existing tyre totals. The hourly cards use kg or compact tonnes; their tooltip
shows both. Daily/weekly cards show kg and tonnes together. Future cards remain
pending. Brisbane production windows, source isolation and calendar boundaries
are unchanged. No production count records are rewritten.

Owner-supplied estimates: passenger 8 kg / 1 EPU, SUV/4x4 16 kg / 2 EPU,
truck 45 kg / 5 EPU. Any unclassified source record defaults to passenger for
production display, weight, EPU, reports and projections; the original database
label is retained. No extra unclassified dashboard category is added. An asterisk
on a period weight means that the passenger default was used.

Daily and weekly management PDF/CSV/JSON and email summaries include actual
shredder running hours from checked shift-end meter readings, tyres per running
hour and estimated tonnes per running hour. PDFs also show daily production
weights and per-shift running-hour detail. Existing foreign-alert snapshots,
count audit and review sections remain.

Running rates use only completed shifts with valid checked opening/closing (or
previous working-shift closing) meter values. Weekly rates divide the combined
output by the combined running hours for those same shifts, never an unweighted
mean of daily rates. Coverage such as 2/5 matched shifts is shown. In-progress
shifts and missing readings remain pending; no-count gaps are never used to infer
runtime. Zero hours with positive counts require review and do not produce a rate.

Keep entering and checking the shift-end meter in the existing Shredder hours
screen. A report produced before that reading is available shows pending values;
export a fresh report after saving the reading. Previously sent reports are not
silently changed or resent. The existing scheduled-window pace is labelled
separately from actual running-hour throughput.

CSV appends estimated_tonnes, running_hours, tyres_per_running_hour and
estimated_tonnes_per_running_hour columns and SHREDDER_SHIFT/SHREDDER_PERIOD
records. Existing count rows and original headers remain available. All weights
are classification-based estimates, not weighbridge measurements.
