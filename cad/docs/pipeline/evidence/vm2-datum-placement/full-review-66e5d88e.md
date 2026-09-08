# Full committed-diff review: 66e5d88e

Verdict: **findings outstanding; not clean and not native acceptance**.

Reviewed base `55056d4990d38ebb461f343d3002fc90731b9e73` against head
`66e5d88ef6efced5f402a2631dd51eee2489eeda` for PR #702. Source inspection used
Git blobs, not the active working-tree version of the finish probe. No COM,
production edits, merge, or full-build validation was performed for this review.

## Findings

### P1: Rack finish reattachment does not retain the clear leader route

Location: `cad/scripts/draw_rack_pinion.py:113` (the rebuild and postcondition at
lines 116-123); also the unsupported persistence claim at lines 82-87.

The helper succeeds when exactly one intended bore edge remains attached and
the annotation is non-dangling, but never checks the saved leader route. The
committed production-372acd6e normal build passed, yet
`probes/rack-production-lifecycle-372acd6e/receipt.json` fails at first cold
open with zero finish-to-datum clearance. The finish endpoint is
`(0.21804349740134313, 0.17344369111470476, 0.0015)` m, at the crowded datum
location, instead of the requested right-rim XY. The subsequent committed
`finish-persistent-trial.json` preserves the same failure through rebuild and
cold reopen. This is a native counterexample, not a hypothetical API concern.

Fix the rack-only routing using a persistent, natively proven call sequence;
retain semantic edge identity, Ra 1.6, and all manufacturing/stability limits.
Keep the current strict attachment checks, add an actual post-rebuild routing
postcondition where appropriate, and require the complete cold/move/scale/
restore/cold lifecycle and readable prints. The mocked selection/reattachment
tests prove API order and rejection behavior, not persistence of native ink.
Do not claim all native placement methods fail based on these variants.

### P2: Production lifecycle does not enforce datum-to-diameter clearance

Location: `cad/scripts/diagnostics/probe_vm2_datum_lifecycle.py:398` (through
line 406). The runner records the dimension primitives and checks that they
exist, but does not call `assert_clearance(row)` for datum versus diameter.
Only the separate finish-versus-datum comparison calls that gate. Likewise,
`analyze_vm2_datum_clearance.py:125` only prints distances; its CLI is not a
threshold-enforcing exit-status gate.

Reproduction without COM: evaluating the pinned analyzer against the pinned
`probes/rack-native-lifecycle-original/receipt.json` gives cold-open clearance
`0.0`, although that historical receipt's lifecycle status is `passed`. This
is legitimate historical observation, but demonstrates why lifecycle success
alone does not establish the requested diameter-clearance gate. The missing
call remains present in the reviewed production-mode control flow.

Minimal correction: after collecting all current datum/dimension primitives,
checkpoint the raw row, and, for `inputs["mode"] == "production"`, assign
`row["datum_diameter_line_triangle_clearance_m"] = assert_clearance(row)`.
Do this at every observed cold stage, before finish-specific comparison. Keep
the existing 1 mm ink limit and ten-nanometre freshness guard; neither is a
manufacturing or 20/100 micrometre placement tolerance. Add a bounded pure
stage-gate function if needed to exercise the production call path directly.
Tests must feed the recorded original-overlap and above-clearance primitives
through that function: production overlap must raise; current separated ink
must return its measured value; missing/stale primitives must fail; partial
mode must retain its historical observation behavior. Keep every archived
status/receipt byte unchanged. Publish new receipts for the corrected runner.

### P3: Earlier investigation summaries need explicit supersession notices

Locations: `cad/docs/pipeline/evidence/vm2-datum-placement/probe-results.md:3`
and `finish-attachment-control.md:24`.

The earlier report describes unchanged recipes/a draft PR, while this head
changes both recipes. The immediate-only attachment summary can also be read
without encountering the subsequent persistence failure. Add short historical
notices and links to `rack-finish-failure-372acd6e.md`; preserve the historical
measurements and raw files. The latest failure summary itself accurately says
that the head is not accepted. This is provenance clarity, not a new native
geometry finding.

## Scope and verification

The diff contains 341 files, 64,040 inserted lines and 40 deleted lines:
20 changed Python source/test files under `cad/scripts/`, and 321 files under
the evidence directory. All 20 Python files (5,485 head lines) were statically
reviewed, including diagnostics, closure ownership, lifecycle, geometry
comparison and tests. The archived 201-line finish-probe source was also read
as historical evidence, not treated as executable production code.

The 341-file inventory comprises 11 Markdown summaries, one proposal patch,
two gitattributes files, 60 JSON files, ten logs, two XML files, one text file,
21 SLDDRW files, 42 PDFs, 38 PNGs, eight SLDPRT files, 21 Python files
(including the historical evidence copy), 116 execution tokens and eight SHA
sidecars. Evidence review covered all 321 blobs and all 11 Markdown summaries.

The delegated evidence audit found zero mismatches in 454 explicitly mapped
SHA-256 comparisons: 132 manifest source hashes, 132 copy hashes, 130 semantic
identity-sidecar hashes/payloads, 57 unique receipt/output/supersession links,
and three original-raw Markdown hash links. All 132 manifest member sizes
matched. The baseline inventory contains 108 parts and eight assemblies;
130 published identity inputs plus two closure receipts match its accounting.
Both archived JUnit totals agree with their summaries (98 tests/95 failures/
three passes, and 142 tests/zero failures). Historical failure is not mistaken
for current acceptance. No full-stack acceptance or source-identity waiver
was found in the latest summaries.

Ruff was run on each of the 20 exact Git blobs via stdin: all passed.
`git diff --check` passed for the committed source diff. Nine relevant offline
test files ran: **430 passed in 6.72 s**. Before and after this test run, the
only tracked source difference from the reviewed head was the active
`diagnostics/probe_vm2_rack_finish_attachment.py`, which these nine test files
do not import. Its committed version was separately inspected and linted.
The active probe edits and its new uncommitted tests are outside this verdict.

Test receipts, under `probes/` beside this report:

- `full-review-66e5d88e-tests.log`: SHA-256
  `2b5d52543faab5ea92676d4093c9cc1a0506ea0c7858196b9c7263456f919caf`.
- `full-review-66e5d88e-tests.xml`: SHA-256
  `31a61b0e68832a15c7f07c782186759b879b5b59cc17b0242f978d59647687cc`.

Both complete production-372acd6e drawing PNGs were visually inspected after
confirming no working-tree difference from the reviewed blobs. The rod datum
and manufacturing callouts are readable. The rack diameter approaches above
the datum, but its finish leader visibly converges at the datum triangle;
the numeric zero-clearance finding comes from native receipts, not pixels.
Both sheets retain visibly crowded Number/Revision fields. That shared-template
issue is already documented and belongs to VM1; it was not introduced by this
PR and is not a request for VM2 to edit the template.

## Limitations and handoff

This is a full-diff code/evidence review, not a clean external CodeRabbit
result. The parent retained the CLI `payload_too_large` failure separately and
requested GitHub full review. The reviewer authored portions of this change;
the separate evidence audit corroborates bytes but is not an independent
external manufacturing review.

Native binaries were checked for recorded byte identity, not reopened here.
The 38 historical PNGs were not all visually reinspected; the current complete
pair received the visual pass. Unpublished historical native artifacts and
ZIP contents were not verified. Offline tests cannot establish actual COM
side effects, persistent annotation placement or complete print acceptance.

Fix and re-review a frozen correction head. Preserve historical raw evidence,
protected parent stacks and tolerances. Full retained-stack build, closed
snapshot and exact-head zero-COM validation require VM1's combined integration
head; this review does not replace them or authorize merging.
