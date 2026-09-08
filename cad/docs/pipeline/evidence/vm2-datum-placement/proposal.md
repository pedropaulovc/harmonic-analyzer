# Proposed native datum placement contract

VM1 coordination request; not production implementation or acceptance. The
[unapplied patch](native-placement-proposal.patch) targets correction head
`6976b79e4bcf3bf158cf4a688813e01967177299` (main baseline `55056d49`, adapter
`2269009ed56712867826516f4406afc98a0c2814`). `git apply --check` passes against
the current production files. No production source was changed for this proposal.

## Requested change

- Keep requested-position behavior and defaults for every existing caller.
- Add an explicit `placement="native"` opt-in requiring one semantic model edge
  and its expected origin-Z cylinder radius. Reject coordinate/annotation picks,
  requested XY, missing/nonfinite geometry or tolerance, wrong circle/axis,
  missing/ambiguous adjacent cylinder, and selected-object mismatch.
- Let SolidWorks choose the symbol position without calling `SetPosition2`.
  Require one non-null edge attachment, `IsSame == 1`, non-dangling state,
  retained label/shoulder, successful rebuild and finite stable XY readbacks.
- Preserve rod **20 um** and rack **100 um** numeric limits. In the opt-in mode
  these bound movement from SolidWorks' initial native position across rebuild;
  they no longer assert distance from a hand-requested sheet point. This is an
  explicit contract change requiring approval, not an increased tolerance.
- Move rack `BoreDia` text above-left to `(0.158, 0.213)` so its leader approaches
  opposite native datum A below-left. Preserve fit, precision, notes, FCF and
  surface-finish manufacturing requirements.

Shared edits requested: `_drawing_common.py` and the rack branch of
`test_gear_drawing_batch_contract.py`. The patch also changes the two owned
recipes and their owned selector/layout assertions. No adapter, part, template,
build-graph or parent-stack changes are proposed. The rod's selected crown/rim
boundary establishes the adjacent cylindrical bearing axis; it is not the flat
front-end datum. Semantic checks explicitly verify that cylinder's axis.

## Native evidence available

Copied native-edge partial drawings have passed cold open, translation, scale,
restore and second cold open with verified circular/cylindrical geometry and
edge identity. Rod and rack position translation/restore/reopen errors were
zero in those runs. These are partial drawings, not complete print acceptance.

The first rack ink experiment exposed stale `IDatumTag` primitives after moving
or scaling: dimension lines updated but datum lines did not. Its moved/scaled
clearance numbers are invalid and must not be used as passing evidence.

The follow-up `cad/out/reports/datum-placement/rack-native-lifecycle-cold-ink/receipt.json`
saved and cold-reopened each moved/scaled/restored stage before measuring ink.
It passed in **70.3926 s** with current-annotation/ink and projected-rim guards.
Datum-to-diameter ink separation was **1.947243456304 mm** at original, moved,
restored and second-cold-open stages, and **2.521455399822 mm** when scaled.
Translation, restore and second-reopen position errors were zero; source SHA-256
remained `612fda6a2db58670dce187b1e59016f721067a9f89c4a374b06bee035407bc15`.
Receipt SHA-256:
`90271464f0154eeba94da796fae1a7babee973a34a3b04ceaa529a4b969b6a72`.
This positive control supersedes the pending cold-ink experiment, not the need
for complete corrected manufacturing drawings and readable full-sheet prints.

## Before freezing the correction

Add behavioral regressions for unchanged requested-position failures, no native
`SetPosition2` call, wrong/missing/ambiguous geometry and association, dangling
state, nonfinite values, tolerance-boundary drift, label/shoulder/rebuild failure,
stale ink and the old rack leader collision. The patch's source assertions alone
are not those behavioral regressions. Run complete corrected drawings and their
cold-reopen/move/scale/print proofs, explain the separate source-hash change, and
obtain a clean review of the full correction diff.

Wait for VM1's combined integration SHA before the expensive full build covering
the complete retained stack including #686/#687. Then capture the closed native
snapshot and exact-head zero-COM repeat. Preserve #682/#685 and #686/#687;
integration and merging remain with VM1.
