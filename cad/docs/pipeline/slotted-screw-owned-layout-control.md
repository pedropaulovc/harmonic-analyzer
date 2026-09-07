# Slotted-screw owned layout control

This diagnostic work extends the existing owned datum-policy pilot for the
[slotted-screw layout candidate](slotted-screw-native-layout.md). The first slice
contains pure-data witness tests only. The target is not enrolled, and no native
run or source equivalence has been established by this branch.

The witness requires the recipe's three model-dimension roles and three views at
6:1. It uses the existing native annotation measurement bank, including displayed
dimension strokes, to record signed clearances to the sheet's measured zone
border. A baseline overflow remains a recorded negative layout result. The
candidate must fit. Neither outcome replaces the pilot's source, attachment,
saved/cold drawing, or printed-content checks.

Enrollment requires a genuine local source build on the frozen producer branch,
its exact output SHA, execution token, producer trace, and native dimension-role
readback. The current 17 source pins and coverage contracts remain unchanged.
No synthetic test value is an enrollment value.

The existing pilot requires rocker, lever, and the selected target under both
source and guard roots. A declared diagnostic-only bundle may contain byte copies
of the pinned rocker/lever sources and the genuinely built slotted source, with
that same bundle supplied as both roots. The pilot protects the bundle and opens
only its uniquely named owned trial copies. Separate outer guards must retain the
upstream originals' paths, producer revisions, hashes, and provenance before and
after the trial. Staging is not a producer output restore or a token restamp.

The remaining slice adds an explicit observation arm to the existing pilot and
retains uncropped full-sheet rendering and literal printed text after the normal
save and cold reopen. These checks run outside the recipe timer. Correctness of
the baseline/candidate pair comes first; one timing pair cannot establish a
performance benefit.

## Offline reproduction

```powershell
$env:PYTHONPATH = 'cad/scripts;cad/comparisons/tools;SolidworksMCP-python/src'
uv run --frozen python -m pytest -q --tb=short cad/scripts/test_slotted_screw_layout_pilot_drawing.py
```

The initial synthetic suite passed 12 tests. It covers missing, hidden,
dangling, excluded and extra dimension data; numeric visibility, view and scale
changes; non-finite coordinates; absent strokes; and candidate border overflow.
Native dimension identities and printed output remain untested.
