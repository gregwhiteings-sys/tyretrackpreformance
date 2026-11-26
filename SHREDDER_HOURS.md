# Shredder shift-end readings

The dashboard shows the latest checked completed shift: actual running hours,
recorded production tyres, and recorded tyres per actual running hour. The
hour meter was confirmed by the owner to advance only while the shredder runs.
It is separate from scheduled-hours and existing pace calculations.

Open **Shredder hours**, select the shift date, enter the cumulative TOTAL HOURS
reading, optionally attach the meter photo and supervisor sheets, check that
the shift is complete and the reading verified, then save. The previous checked
weekday shift-end reading supplies the opening value. A first reading is a
baseline; missing prior shifts leave the rate pending. A known opening/reset
can be entered with an explanation. Negative, future, weekend and over-24-hour
shift deltas are rejected or flagged. All reading edits retain a history.

**Import daily photo ZIP** groups photos by filename date. An optional
`meter_readings.csv` with `day,meter` columns supplies proposed values only.
Imported values require operator checking and saving. Existing checked readings
and duplicate images are preserved. Double-click an attached photo to open it.
No OCR or automatic WhatsApp connection is enabled by this feature.

Rates use primary OAK counts from the same Brisbane weekday 05:00–17:05 window,
including automatic additions already committed to those totals. Test/replay
sources and out-of-window/future counts are excluded. No recorded counts is
shown as unavailable, not proof of zero production. Camera gaps can still make
recorded throughput lower than physical throughput. Missing data and zero
running hours never yield a fabricated rate.

Readings, history and evidence stay in `data/machine_hours`. They are separate
from the production database; this feature does not change tyre counts, model
settings, overlap rules, alerts or earlier reporting. Photos are imported locally
by the operator, never published to the source repository. Dashboard reads use
the existing background review reader and are joined during app shutdown.
