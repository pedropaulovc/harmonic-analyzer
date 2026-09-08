# VM2: repair two reproduced datum-placement failures

You are authorized to investigate and fix the pinion-lift-rod and rack-pinion
drawing failures in a separate PR. VM1 retains merging and cross-stack integration.
Continue independently on your own SolidWorks machine; do not wait for VM1's seat.

## Starting evidence and isolation

- Read the local AGENTS.md and developing-solidworks skill first; use its local API bundle.
- Preserve the existing #686/#687 code, review receipts, native artifacts, execution
  tokens and genuine ledger. Do not modify #682/#685 or their artifacts.
- Evidence head: `439f8dec448e540cf61e3153b74b216336fe3f7d`, especially
  [assembly integration evidence](https://github.com/pedropaulovc/harmonic-analyzer/blob/439f8dec448e540cf61e3153b74b216336fe3f7d/cad/docs/pipeline/assembly-granularity-integration-results.md), section
  `Native validation blocker and unchanged reproduction`.
- The tested assembly candidate was `2d10203b0d554e1d53fb5f13d84951412afb4a82`;
  its evidence-only successors do not create a new native pass.
- Use a new code worktree/branch based on main `55056d4990d38ebb461f343d3002fc90731b9e73`,
  with adapter `2269009ed56712867826516f4406afc98a0c2814`. Fetch main first;
  if it has advanced, report the delta before choosing a different experiment baseline.
  Do not pull VM1's adapter `25bc99b1` or its drawing stack into this experiment.
- The existing unsaved dirty `Draw109 - Sheet1` was not closed by the guard.
  Establish its ownership before any no-save closure; do not indiscriminately
  close documents or restart SolidWorks. Preserve saved-file hashes and record cleanup.

## Reproduction

The unchanged retry used these normal, seat-locked tasks with remote cache off:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run --frozen python -m doit -n 4 drawing:pinion_lift_rod drawing:rack_pinion
```

Datum A readback errors were 23.536 micrometres versus a 20-micrometre limit for
pinion_lift_rod, and 163.372 versus 100 micrometres for rack_pinion. Both are
symbol-position errors, not manufacturing geometry errors. The reports contain
exact requested/returned positions and hashes. Reuse those failures as evidence;
do not repeatedly rerun the same unchanged case without testing a specific delta.

## Ownership and correction

Initially own only `draw_pinion_lift_rod.py`, `draw_rack_pinion.py`, their two
`test_*_drawing.py` files, and uniquely named diagnostic/evidence files.
Coordinate with VM1 before editing `_drawing_common.py`, other shared helpers,
templates, dodo.py, the adapter or source parts. Do not duplicate a shared helper
just to avoid coordination.

Investigate the documented datum attachment/placement contract with a working
positive control and one-variable comparisons. Prefer semantic entity attachment
and letting SolidWorks choose a valid position when that produces a readable print.
Layout changes are authorized. Preserve datum meaning, controlled faces, dimensions,
units, tolerances, leaders and association. Do not increase placement tolerances,
round away residuals, ignore rejected API calls, or turn failed checks into warnings.
If native placement requires replacing an exact-XY assertion, propose and prove
the replacement identity, attachment, clearance and cold-reopen checks first.
VM1 has a separate extent/viewport experiment: quantization is only a hypothesis,
not a demonstrated explanation for these GetPosition failures.

## Acceptance and delivery

Add real-receipt fail-first regressions. Validate each correction natively through
the normal pipeline, including cold reopen, attachment identity, move/scale behavior,
and full-sheet/detail PDF/PNG inspection. Record exact code, adapter, source identities,
commands, timings and failure/success receipts. Preserve baseline evidence.

Push early and open a separate draft PR against main; mark ready at code-complete.
Use Windows-local CodeRabbit OR Codex for one clean full-diff review, plus offline
checks. Watch the PR with watch-pr; do not merge it.

After the correction is reviewed, validate its exact commit with #686/#687 in an
isolated integration branch, without changing the published assembly branches.
Finish a successful full build, same-main geometry/DOF and native identity checks,
all required visuals, closed snapshot and exact-head zero-COM full repeat. No token
restamping, cache/ledger fabrication, or transplant of another experiment's outputs.
Report the correction PR/head and complete acceptance evidence to VM1 for merging.
