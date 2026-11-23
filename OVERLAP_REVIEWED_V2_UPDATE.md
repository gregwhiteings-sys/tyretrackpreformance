# Reviewed overlap V2 candidate — 23 November 2026

Replaced the packaged experimental overlap PT/ONNX/blob with the newly trained Reviewed V2 candidate. Main tyre detector and foreign-object models are unchanged. The existing confirmed 1180 mm default and later operator edits are preserved.

The candidate remains OFF: independent CPU replay reproduces 4 matched groups, 8 misses and 0 false detections at validation-selected confidence 0.25 (34 test frames; 22 normal). Test recall is 33.3%. Dense frames are correlated and the two held-out sequences are from the same day. This is not a pass and cannot justify live overlap inference or automatic missed-count additions.

Blob compilation: OpenVINO 2022.1, RVC2, 6 SHAVEs, RGB planar U8 416x416 with /255 scaling. DepthAI blob parser confirms input [416,416,3,1], output [3549,5,1]. PT/ONNX positive frame both detect one group; maximum box difference 0.88 pixels. No OAK hardware inference performed.

Dashboard trial panel shows the new 4/12 and 0/22 evidence; original production counting, geometric overlap review and count links continue unchanged. Review corrections remain explicit and auditable. All model hashes are in overlap_model/trial_status.json. Full Colab threshold sweep and per-frame CPU verification are packaged alongside the model.

To improve: collect more independent overlap arrangements on fresh days; label every visible tyre for the individual detector, and connected groups separately; include tilted single tyres, folded material and belt joins as carefully reviewed difficult examples; keep whole sequences in one split. Evaluate event detection and count linkage separately. Lowering confidence or converting to a blob cannot recover missing learned examples.
