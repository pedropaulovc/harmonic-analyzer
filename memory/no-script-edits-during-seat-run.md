---
name: no-script-edits-during-seat-run
description: "Editing a build script or spec while a doit seat run is in flight turns every downstream verify gate into a fresh-inputs STALE failure and can make an assembly mate against a part built from the old script (9 mm crank miss) -- queue edits until the run ends, then one more `doit --continue build`"
metadata:
  type: feedback
---

Seen 2026-09-02 (PR #650): while `doit -n 4 build_bare`/`build` was running on the seat,
editing `crank_arm_spec.py` (66 -> 75) and later `build_harmonic_base.py` produced two
distinct failure shapes:

1. doit evaluates a task's freshness when it is scheduled, so a part built EARLIER in the
   same run stays "current" and the assembly built LATER mates against the OLD part while
   the script says otherwise -- drive-train's "flip-seed MISS ... off by 9.00 mm" was
   exactly the arm-length delta, not a flip bug. `_FLIP_INVERT` toggling would have been
   the wrong fix.
2. The verify gates' fresh-inputs guard reads script digests at gate time, so every
   assembly carrying the edited part fails "STALE artefact, NOT verified" even though
   the geometry is fine.

**How to apply:** batch script/spec edits; when the seat is busy, commit them and wait for
the run to finish, then run `uv run python -m doit -n 4 --continue build` once. Also
`build` does NOT include `export` -- run `doit export` explicitly for STL/GLB/boxes. And
never run two doit invocations on the same `.doit.db` at once.
