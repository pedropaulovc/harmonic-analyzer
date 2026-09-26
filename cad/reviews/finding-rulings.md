# Machinist-review finding rulings

A gating finding of a machinist review (blocker, over-specification or clarity)
that the project deliberately keeps is answered here, one row per ruling.
`machinist_ledger.py ingest --rebuttals` (and `machinist_review.py
--rebuttals`) cites a row by its id and this file's path and line, and the
ledger then records the verdict as `accepted_with_rulings`.

A ruling is either the user's or Main's adjudication, made under the user's
standing delegation. An adjudication counts only when it is recorded here with
its evidence. `ruled_by` is `user` or `Main`.

| id | drawing | finding | decision | evidence | ruled_by | date |
|---|---|---|---|---|---|---|
| MR-037-1 | knife_mount (MHA-037) | over-specification: the 19.82 cross-bore location should be one place, ±0.8 | REJECTED. BoreFromTop feeds the crown web and the fitted-stud gap 1:1: at ±0.8 the web is 1.762 mm (< 2.0 target) and the gap 0.15 mm (< 0.25), and restoring them needs a 6.5 boss that moves the stud seat. The .XX general band (±0.51) is kept: web 2.052, gap 0.44. | commit 184d5dbf2 body; the PR #822 adjudication table; Codex FIX 2026-09-26T00:31:55Z (knife) and the cc-17/cc-18 rounds | Main | 2026-09-26 |
| U40 | cone_gear (MHA-013-T006) | blocker: the bore-to-gap-floor ligament is 0.62 mm radial ((2.880 floor min − 1.638 bore max)/2), below the 1.5 mm floor | ACCEPTED as a named exception on book-fidelity grounds. No separate T006 reaches 1.5 mm at any bore, because drum-tip clearance caps the floor, and an integral pinion blocks the tip-loaded set. Kept off the sheet (rule 6). | cone_gear_spec.WEB_EXCEPTIONS_MM = {6: 0.621}, pinned by test_cone_gear_drawing's root-to-bore web test; confirmed by Main 2026-09-26 after the geometry analysis (#834) | user | 2026-09-23 |
| U42 | cone_gear (MHA-013-T006 to T042) | contact ratio below 1.1 at the worst case of the printed bands | ACCEPTED as a named exception on book-fidelity grounds. The cost is wear on the tooth-tip corners, not position error: rigid transmission error is at most 0.023 mm at the drum pitch line on T006 and at most 0.004 mm on the rest. Kept off the sheet (rule 6). | cone_gear_spec.CONTACT_RATIO_EXCEPTION_TEETH = (6, 12, 18, 24, 30, 36, 42), pinned as an exact set by test_cone_gear_mesh_design (#834) | user | 2026-09-23 |
| MR-013-1 | cone_gear (MHA-013, all 20 configurations) | over-specification: the 6.00 ±0.1 face width controls an overall width with no stated axial fit or stack requirement | KEPT at ±0.10. An asserted axial stack sets the upper side: 0.529 mm of neighbour air, in-service margins 1.05 mm north and 1.10 mm south; a .X band collides. | the user's ruling "MHA-013 face ±0.10" on #914 (Main-cc line 1479); test_face_width_band_holds_both_axial_stacks at 75c6faa37 (#834); recorded by Main 2026-09-26 | user | 2026-09-25 |
