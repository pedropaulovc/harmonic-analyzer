---
name: submodule-pointer-drift
description: A drifted SolidworksMCP-python checkout silently drops newer adapter kwargs (pydantic ignores unknown fields) — check `git submodule status` for a `+` prefix before debugging geometry failures
metadata:
  type: project
---

2026-07-04, PR7: `part:cone_pivot_post` failed its crank-bore volume check
(+1314 mm³ — the revolve ran as a BOSS, not a cut). Root cause: the
`SolidworksMCP-python` submodule working tree sat on a local `personal`
branch two commits BEHIND `origin/personal` (left there by the DXF-import
session, see [[dxf-import-makers-seat]]), predating
`d84537a "RevolveParameters.is_cut"`. The build script's
`RevolveParameters(angle=360.0, is_cut=True)` lost the kwarg SILENTLY —
pydantic BaseModel ignores unknown fields by default — so the only symptom
was a wrong volume downstream.

**Why:** the superproject records the pointer (`git ls-tree HEAD <sub>`),
but nothing forces the working tree to match it; a `+` prefix in
`git submodule status` means checkout ≠ recorded pointer.

**How to apply:** when a part that "was green before" fails a geometry
gate after no relevant repo change, check `git submodule status` FIRST.
Fix = `git -C SolidworksMCP-python merge --ff-only origin/personal` (after
`git cherry origin/personal personal` confirms no unique local commits).
The volume gates are the safety net that surfaces this class loudly — one
more reason never to widen their tolerances.
