# Master V8 overlap update

Replaces the active V7 ONNX model with Master V8. Original OAK detection,
classification, counting and recording remain in place. The separate bounded
CPU overlap worker uses the new hash-verified model; no OAK blob conversion is
needed for this existing CPU worker.

At Greg's explicit request, retain the existing automatic +1 policy and saved
enabled/off preference: 65% confidence, three stable model observations,
exactly one linked OAK count, then one unclassified addition after tracks leave.
Two linked counts, zero counts, pauses and incomplete events add nothing.
Corrections remain recorded, deduplicated and reversible. This assumes two
physical tyres; a model prediction cannot prove the hidden tyre total.

Master V8's validation-selected benchmark threshold was 15%. The live build
retains the previous 65% threshold for +1, rather than silently lowering it.
This sacrifices sensitivity: the small repeated benchmark matched 7/12 groups
at 65% versus 11/12 at 15%. Independent site accuracy remains unaccepted;
the training metadata's production_ready=false is preserved. Owner authorization
to use the model is recorded separately from validation evidence.

The 15m01s November 17 replay ran both models on all 13,515 frames. At 65%,
V7 produced boxes on 132 frames in 9 temporal intervals; V8 produced none.
At 15%, V8 produced boxes on 26 frames in 4 intervals, visually consistent
with partial/folded single tyres. Temporal intervals are not unique tyre groups.
No definite pair was established in the sampled source frames, so this replay
primarily checks false-alert rejection and does not establish overlap recall.

The comparison footer now shows Recorded OAK and Observe-only class totals,
plus the number measured and classification disagreements. Extra possible,
size-only and duplicate production lines are removed. Observe-only does not
change production totals. Review/reversal wording is model-neutral so older V7
records can still be reversed without being relabelled as V8 evidence.
