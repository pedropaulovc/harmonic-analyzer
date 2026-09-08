# VM1 assembly and datum closeout

The combined runtime at `2d8618ca17fdcae69c32a67b9aa0f2f23e1ecee2` passed the
full pipeline, cold drawing lifecycles, visual inspection, closed snapshot and
zero-COM repeat. The adapter is `2269009ed56712867826516f4406afc98a0c2814`.
These are historical, pinned results; current merge and release status is in
[PR #717](https://github.com/pedropaulovc/harmonic-analyzer/pull/717) and the
[project board](https://github.com/users/pedropaulovc/projects/1).

The runtime integrates the reviewed assembly dependency/parser changes and
shared title-block correction with [VM2's datum correction at
748cf37c](../vm2-datum-placement/correction-f9c8bddf.md). Manufacturing dimensions,
datum stability limits and strict native attachment checks remain unchanged.

## Acceptance evidence

- [Full normal pipeline](full-build.json): `uv run python -m doit -n 4`, exit 0
  in 80.189 seconds; [complete log](full-build.log) records 1,523 recipe tests
  passing and the corrected rack drawing rebuilt. The remaining tasks were
  current from the earlier successful full run at `64c3dab4`, whose eight
  assemblies and saved-model gates were built and inspected. This is ordinary
  incremental pipeline coverage, not a claim that every task rebuilt twice.
- [Rack](rack/receipt.json) and [rod](rod/receipt.json): first cold open,
  movement, scaling, restoration and second cold open all passed on VM1 using
  the combined template. Original source and production drawing bytes were
  preserved. Cold/moved/scaled/second-cold PNGs are retained beside each receipt.
- All eight assembly isometrics and all 92 drawing sheets were inspected.
  The original visual reports and manifests are retained here; the corrected
  rack and both lifecycle series were subsequently inspected on this runtime.
  Reports retain their original local artifact paths and hashes.
- [Empty native seat](empty-seat.json) was observed before the
  [closed snapshot](closed-snapshot.json). The local snapshot ZIP was reread
  and every member verified. The large ZIP remains preserved in the recorded
  local path; this publication contains its exact manifest and hash.
- [Full repeat](zero-com-repeat.json): exit 0 with automatic SolidWorks startup
  and remote cache disabled. No task execution, new telemetry, runtime-input or
  native/export change occurred; the genuine build ledger stayed byte-identical.
  Its [complete log](zero-com-repeat.log) is retained.
- Independent full-diff reviews are clean for [#702](codex-702-review.md) and
  [#717](codex-717-review.md), with exact reviewed head/base commits and limits.

The raw receipts and reports were copied without editing. This evidence-only
publication does not itself change runtime code or native outputs. Its final
PR head receives the normal full-repeat gate before merge; that head and result
are recorded in the PR acceptance comment.

## Deferred work

Existing title/material/finish fitting remains under
[#709](https://github.com/pedropaulovc/harmonic-analyzer/issues/709); body layout
and the blocked drawing stack remain under
[#712](https://github.com/pedropaulovc/harmonic-analyzer/issues/712) and
[#718](https://github.com/pedropaulovc/harmonic-analyzer/issues/718).
The translated rack Gear Data heading touches the upper border. The rod's
scaled diagnostic sheet retains its static scale note; the restored production
sheet has the stated 2:1 end view. These stress sheets are attachment evidence.

The comparison against the preserved VM2 main baseline found all 108 leaf input
maps/cache keys and six authored DOF manifests equal, but five of eight stored
geometry fingerprints differ. Seven VM1 cold readbacks reproduce their own
stored hashes; paper-drive differs. A bounded signed-zero check did not explain
the differences. This does not certify geometry equivalence or establish a
specific geometry regression. The remaining investigation, exact hashes and
reproducer are preserved in
[#719](https://github.com/pedropaulovc/harmonic-analyzer/issues/719).
