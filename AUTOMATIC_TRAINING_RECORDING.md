# Automatic production training recordings

Install the updated Windows build, connect Camera 1 and leave Auto-save production training footage ticked (default ON; later choices are remembered). Keep the normal production schedule enabled. The manual Record OAK video checkbox can remain unticked. This automatic feature records only while the production worker's schedule/count gate is active; operator pause, manual OAK tests and uploaded-video tests are excluded.

Use Open automatic training recordings in camera settings. Files are saved in the app's data/oak_training/YYYY-MM-DD folder, not uploaded automatically to Google Drive.

What is saved:
- Clean camera video at native 640×360 / 15fps, split at a keyframe approximately every 15 minutes, plus the complete recording interval around events. H264 is already encoded on OAK; PC work is stream-copy/remux, not video encoding or extra AI inference.
- Each final MP4 has a JSON sidecar with Brisbane start time, frame count, duration and packet-gap information. The current segment finalises on rotation, pause, stop or normal app exit. Abrupt power loss can leave recoverable .h264 rather than a final MP4.
- training_events.jsonl contains overlap start/complete markers, event IDs, observed tracks, actual count callbacks and recording references. Starts also save clean unpainted JPEGs. Complete markers preserve later count links even after recording pauses. Rectangular overlap remains a heuristic, not a confirmed physical overlap or missed count.
- An unlabelled clean reference image every ten minutes during active production. Samples are not automatically assumed normal or accepted as training ground truth.

Keep about 20–30 GB free initially. At the configured 1.5 Mbps bitrate, 12 hours is approximately 8 GB (actual files vary). Storage checks occur on the recorder thread every 15 seconds. Automatic training capture pauses below 10 GiB free or at 25 GiB in this training folder, and resumes after space is available. Nothing is automatically deleted. The separate manual recorder is not quota-managed by this feature. Copy reviewed footage elsewhere before removing it; deleting files makes old recording links unavailable.

Status appears in the existing system-health Recording field; a paused/error state is highlighted. Video-saving failures do not add or remove counts. Evidence submission is bounded and nonblocking; a full evidence queue can drop snapshots/markers, and the queue's dropped counter is retained in memory. The continuous video is the primary context. Timestamp offsets use host packet receipt and are approximate; they do not prove frame-level count synchronisation. The review screen's existing recording button opens the containing folder, not an automatically seeked player.

At the end of a production day, stop normally or wait for the current 15-minute segment to close, then share the day's oak_training folder with its MP4, JSON, JSONL and clean JPEGs. Share the matching classification_review export as well. The footage can then be checked, de-duplicated and annotated. Auto capture does not retrain the model automatically or make predicted labels correct.

The newly packaged Reviewed V2 overlap neural candidate remains disabled (4/12 held-out groups). Original tyre counting, foreign detection and geometric overlap/count review continue. The confirmed belt default remains 1180 mm; previously saved measurements at 1100 mm are not rewritten.
