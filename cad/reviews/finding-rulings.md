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
