> Superseded by Master V8; see OVERLAP_V8_UPDATE.md. The +1 policy and reversal ledger are retained.

# V7 automatic overlap correction

Enabled by default at Greg's request; saved setting can turn it off in camera controls.
V7 is bundled separately from the original OAK tyre detector. CPU inference runs in
one background thread, at most twice per second, batch 1, RGB/255 416 letterbox,
confidence 0.65 and NMS IoU 0.5. Both input and output queues hold one item.
Model failures show a review status; original counting continues.

Three model observations linked to the same OAK track group are required.
After all group tracks have been absent for 90 processed frames, one committed OAK
count allows one additional unclassified tyre. Two linked counts or zero linked
counts produce no addition. This assumes two physical tyres; it cannot establish
hidden group size, and cannot classify the hidden tyre as passenger/SUV/truck.
Track IDs are consumed for the entire camera session; ambiguous merges, long events,
pauses, tracker recovery and shutdown cancel pending events. Incomplete events do
not add counts. Results older than 15 processed frames are discarded.

An atomic transaction writes the extra counts row and an event-keyed ledger in the
production database. Repeated commits cannot add twice. Original OAK rows are not
edited. A snapshot must be saved before a correction can be committed. Evidence is
also submitted to the review database with the timestamp and recording reference.
Production shift/manual-test/source gates apply both at observation and commit.

Dashboard totals and hourly/daily/weekly/monthly figures include the extra row.
The comparison dashboard and daily/weekly PDF/CSV identify automatic additions as
already included; never add that subtotal again. Extra tyres remain unclassified,
so they do not contribute an invented weight/EPU. Human missed adjustments remain
a separate ledger, and cannot be saved against an automatic V7 record.

Open overlap count reviews, select an automatic event, enter a reason in Notes,
and press Reverse selected V7 +1 correction to remove only the automatic row.
The original OAK count remains. The ledger retains a reversal tombstone so retries
cannot resurrect it. Review database records retain the original model prediction.

Offline tests cover real packaged ONNX inference, real worker count/persistence,
late second counts, zero counts, pauses, repeated commits, reversals and report
reconciliation. Site accuracy and PC throughput still need checking on production
footage. Tracker ID switches, completely hidden tyres, more-than-two groups and
false positive model predictions can cause incorrect adjustments; no software rule
here proves that an overlap always represents two tyres.
