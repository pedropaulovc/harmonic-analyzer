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
| U40 | cone_gear (MHA-013-T006) | blocker: the bore-to-gap-floor ligament is 0.606 mm radial ((2.849 floor min − 1.6375 bore max)/2), below the 1.5 mm floor | ACCEPTED as a named exception on book-fidelity grounds. No separate T006 reaches 1.5 mm at any bore, because drum-tip clearance caps the floor, and an integral pinion blocks the tip-loaded set. Kept off the sheet (rule 6). First ruled 2026-09-23 at 0.62 mm (floor 2.880 MIN); amended by the user's #917 C2 ruling, option (1): keep a 0.04 floor window under the #917 fit-up residual, so the T006 floor is 2.849 MIN / 2.889 MAX and the web 0.606 (0.60575 at the +0.050 bore upper, printed 0.60 MIN). | cone_gear_spec.WEB_EXCEPTIONS_MM = {6: 0.6055} (half a thousandth under 0.60575, so the family bore band keeps +0.050), pinned by test_cone_gear_drawing's root-to-bore web test (the first 0.621 exception was confirmed by Main 2026-09-26 after the geometry analysis); FLOOR_LIMITS_MM[6] = (2.849, 2.889), an exact 0.04 window asserted by test_cone_gear_mesh_design (#834; amended on #917, branch conegear/917-c2) | user | 2026-09-26 |
| U42 | cone_gear (MHA-013-T006 to T048) | contact ratio below 1.1 at the worst case of the printed bands | ACCEPTED as a named exception on book-fidelity grounds. The cost is wear on the tooth-tip corners, not position error: rigid transmission error is at most 0.023 mm at the drum pitch line on T006 and at most 0.004 mm on the rest. Kept off the sheet (rule 6). First ruled 2026-09-23 for T006 to T042; the user's #917 R3 ruling adds T048. Worst-case contact ratios with the #917 fit-up residual, T006 to T048: 0.13 / 0.38 / 0.55 / 0.69 / 0.81 / 0.90 / 0.99 / 1.06. | cone_gear_spec.CONTACT_RATIO_EXCEPTION_TEETH = (6, 12, 18, 24, 30, 36, 42, 48), pinned as an exact set by test_cone_gear_mesh_design (#834; amended on #917) | user | 2026-09-26 |
| MR-013-1 | cone_gear (MHA-013, all 20 configurations) | over-specification: the 6.00 ±0.1 face width controls an overall width with no stated axial fit or stack requirement | KEPT at ±0.10. An asserted axial stack sets the upper side: 0.529 mm of neighbour air, in-service margins 1.05 mm north and 1.10 mm south; a .X band collides. | the user's ruling "MHA-013 face ±0.10" on #914 (Main-cc line 1479); test_face_width_band_holds_both_axial_stacks at 75c6faa37 (#834); recorded by Main 2026-09-26 | user | 2026-09-25 |
