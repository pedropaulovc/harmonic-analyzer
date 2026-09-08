# #702 placement correction: f9c8bddf

The two datum corrections and rack finish placement pass the scoped native and
visual checks below at `f9c8bddff7c5f56d094f46723d5bd8151d541e9a`.
This is a correction handoff to VM1, not full-stack acceptance or merge approval.
The adapter remains `2269009ed56712867826516f4406afc98a0c2814`.

## What changed

The rack finish is inserted immediately after explicit view-scoped selection of
the semantic bore edge at its positive-X rim. `_rack_bore_finish.py` requires
exact selection/attachment identity, one non-dangling finish symbol, manufacturing
readbacks and the actual right-rim leader endpoint after rebuild. It does not use
endpoint setters or repair attachment afterward. The recipe owns only placement.

The final placement commit lowers the finish label 8 mm, from sheet Y 0.113 m to
0.105 m, with X unchanged at 0.278 m. Its regression test pins that position.
The native datum helper and its original 20/100 micrometre stability limits are
unchanged. Part specifications, geometry, adapter, shared `_drawing_common.py`,
templates and parent stacks are unchanged by this correction.

## Native and print results

The [normal run](probes/correction-f9c8bddf/production-f9c8bddf/receipt.json)
passed in 47.764 s. Its log records the rack drawing rebuilt; the rod drawing and
both parts were current. All five monitored runtime-file hashes and the Git head
were identical before/after. The [witnessed closure](probes/correction-f9c8bddf/production-f9c8bddf/closed.json)
closed only the owned production documents without saving or changing bytes.

Both complete production lifecycles passed: first cold open, +8/+5 mm view
translation, scale factor 1.25, restore, and second cold open. Each changed-view
stage uses save/close/reopen for fresh ink. The first cold open is the placement
baseline; these receipts do not invent a pre-save insertion witness.

| Check | Rack | Pinion lift rod |
| --- | --- | --- |
| Lifecycle elapsed | 70.738 s | 14.856 s |
| Minimum datum/diameter ink clearance | 1.947 mm | 5.903 mm |
| Minimum finish/datum ink clearance | 4.458 mm | Not the rack-finish check |
| Datum translation, restore and second-reopen error | 0 | 0 |
| Native-position stability limit | 100 micrometres | 20 micrometres |

The rack's scaled finish/datum clearance is 5.597 mm. Both lifecycles retain
source/body/edge correspondence, cylindrical geometry, strict attachment identity,
non-dangling datum and shoulder readbacks. The rack finish remains attached to
the bore edge; the production renderer requires machining-required type and
`Ra 1.6`. All manufacturing specifications remain unchanged.

I inspected the full-sheet cold, moved and scaled PNGs for both drawings. The
rack's bore dimension, datum A and finish callout are readable and separated;
`Ra 1.6` now clears the adjacent side view and lower notes in every inspected
state. The rod's datum and diameter callout remain readable and separate.
The second-cold-open PNGs are checked against their first-cold-open bytes in the
independent native evidence audit. Original PDFs accompany every exported stage.
The numeric line/filled-triangle checks do not cover text glyph outlines; the
visual pass is a separate check.

- [Rack cold print](probes/correction-f9c8bddf/rack-production-lifecycle-f9c8bddf/cold_open.png),
  [moved](probes/correction-f9c8bddf/rack-production-lifecycle-f9c8bddf/moved.png),
  [scaled](probes/correction-f9c8bddf/rack-production-lifecycle-f9c8bddf/scaled.png),
  [receipt](probes/correction-f9c8bddf/rack-production-lifecycle-f9c8bddf/receipt.json).
- [Rod cold print](probes/correction-f9c8bddf/rod-production-lifecycle-f9c8bddf/cold_open.png),
  [moved](probes/correction-f9c8bddf/rod-production-lifecycle-f9c8bddf/moved.png),
  [scaled](probes/correction-f9c8bddf/rod-production-lifecycle-f9c8bddf/scaled.png),
  [receipt](probes/correction-f9c8bddf/rod-production-lifecycle-f9c8bddf/receipt.json).

The existing Number/Rev title-block crowding and the moved rack Gear Data heading
touching the upper border are still visible. VM1 explicitly deferred shared
template fitting and existing body layout under #709/#712. This handoff does not
claim those issues are fixed or grant unqualified full-sheet acceptance.
The rod's scaled diagnostic state also retains its static `END VIEW SCALE 2:1`
note although that stress step changes the view to 2.5:1. The restored production
state is 2:1; the scaled stress sheet is attachment evidence, not a releasable
manufacturing sheet. No broader note/layout change was made.

## Identity and exact originals

Both source parts remained byte-identical through production and both lifecycles:

| Source | SHA-256 |
| --- | --- |
| Rack | `24eb4236303c758016d2340bd6cfbee63ffed63e2f5a73bfb99f889adbaac418` |
| Rod | `59f635b07d5b1edb91ea828c0f9f8f8285cbcbbe17ce188cddeafef8ae08e8db` |

| Original receipt | SHA-256 |
| --- | --- |
| Normal run | `30376bd3d36bf8baa6010ac923f6b51e152d18fd805043e10a7843e9fe4ec23e` |
| Rack lifecycle | `d7030f7dcc24b9c596d880b1a0b2666b3214cc9cc35489dc6c70103a90ece92a` |
| Rod lifecycle | `d0ed67a0c33fa223c1f3038a8c1e17673e583c33288f26f88e5df1644ee813a5` |

[The published bundle](probes/correction-f9c8bddf/) contains the original receipts,
production SLDDRW/PDF/PNG files and lifecycle copies/prints. Original Windows paths
and bytes are preserved. Explanations belong here, not inside the raw receipts.
The [source-hash cause](source-hash-cause.md) remains the imported bore callout
dirtying the source and the drawing save writing that referenced part. Its controls
and historical limits are unchanged; this run shows no additional source change.

Runtime receipts hash Windows working-file bytes. Review tables hash Git blobs.
For the rack recipe these differ only by line endings: runtime
`86a1ce874e9003f0781c6bd589cb5fffedcbf0447c6695dbf6fb0402d88ceec8`, Git
`5735c2389ffbb5c26de2d247fbabfa9958e429120783630e2fe47c6335e816ce`.
These are not CAD source-part hashes.

## Earlier failures remain evidence

The original `372acd6e` cold-reopen finish/datum collision is documented in
[the failure handoff](rack-finish-failure-372acd6e.md), published at `6a5feda0`.
The [updated-main manifests](probes/updated-main-550/README.md) were published at
`66e5d88e`; VM1 independently verified their original hashes. Neither was replaced.

The intermediate `184b6a76` run passed numeric attachment/clearance checks but
failed visual acceptance: after view movement, `Ra 1.6` overlapped the side view.
Its [moved print](probes/production-184b6a76-visual-failure/rack-production-lifecycle-184b6a76/moved.png)
and all 30 original normal/lifecycle files remain in
[a separate preserved bundle](probes/production-184b6a76-visual-failure/).
The raw lifecycle status still says `passed`, its numeric result. This paragraph
records the separate visual failure; it does not relabel or edit the receipt.

## Review and remaining integration gates

The [full baseline-to-head review](probes/correction-reviews/full-review-f9c8bddf.md)
found no actionable code/evidence findings: 368 files covered, including 22 Python
files, with unchanged prior coverage verified byte-for-byte and every later change
reviewed. The reviewer authored none of the implementation. AST, Ruff and source
diff checks passed. The [new offline log](probes/correction-reviews/correction-offline-f9c8bddf.log)
records 1,504 recipe tests passing in 62.11 s; graph/part-isolation tasks were
current and did not rerun. The original earlier review reports/logs are preserved.

This is independent agent review, not CodeRabbit approval. The local full-diff
CodeRabbit CLI failed with `payload_too_large`; GitHub's full-review command was
skipped because 251 files exceeded its 100-file limit. Neither reviewed the full
diff successfully. No reduced review is represented as full coverage.

VM1 reports its `64c3dab4` build ended successfully, but it contains the old failing
placement. VM1 must preserve that run and integrate this correction on a new head,
then complete the retained-stack validation, identity comparison, closed snapshot
and exact-head zero-COM repeat. VM2 did not rerun the full stack or change VM1's
frozen integration branch. Nothing merges from this handoff.
