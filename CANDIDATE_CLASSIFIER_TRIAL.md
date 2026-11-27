# Automatic classifier comparison in Admin

Open **Admin Settings → AI REVIEWS**. **New crop classifier: observe only** is
enabled by default, and a later Off choice persists. The existing belt-size
observe-only panel is labelled separately. The operator dashboard has no new
classifier readings or diagnostics.

Keep normal production running. After an individual tyre is counted by OAK, the
trial receives the same review crop, or the later isolated measurement crop if
one becomes available. There is one comparison per original session/track ID,
not per video frame. A bounded queue of eight crops feeds one background CPU
thread. No extra OAK network or full-frame inference is added. A full queue skips
trial records and reports it in Admin; production counts continue unaffected.
Trial/manual/offline sources are excluded. An originally disabled count is not
retroactively enrolled when the checkbox is later enabled.

The new model uses RGB 224-square padding and a fixed 80% candidate score cutoff.
Small, truncated, overlapping, low-contrast or otherwise unusable crops stay
Unknown. Model/file errors stay inside the trial. This is a passenger/SUV model;
truck has no trained candidate class. The score is not a calibrated guarantee
of real tyre-class accuracy.

Today's panel compares the recorded class and the new candidate for **the same
saved individual OAK counts**. This is a comparison cohort, not another set of
production totals. Automatic overlap +1 additions have no independent crop and
are excluded. The +1 rule, current detector/classifier, existing belt settings,
alarms and main dashboard totals are unchanged. The new model cannot be selected
as the production classifier in this build.

Use **Review new classifier / export comparison CSV** to choose a date, inspect
the crop, export results and optionally record a known actual class with reviewer
name and supporting evidence. Agreement alone is not accuracy; actual-class
reviews allow recorded/candidate correctness to be compared over several shifts.
These reviews never edit production counts or the existing review database.

Trial rows and review history live in **data/candidate_trial/trial.sqlite3**.
One local JPEG crop per comparison is retained when possible, with a 200 MB photo
cap and a 1 GB free-space reserve. Reaching the photo cap stops new photo writes,
not classification or production counting. No evidence is automatically deleted.
Keep the existing data folder when updating. This feature does not upload data,
send emails or automatically retrain the model.

Software checks cover the actual worker count hook, unique comparisons, original
class preservation, unknown filters, human review/CSV, bounded nonblocking work,
model failure isolation, shutdown, Admin visibility and packaged ONNX inference.
The yard PC's live CPU load and physical tyre classification still need checking
during the observe-only trial.
