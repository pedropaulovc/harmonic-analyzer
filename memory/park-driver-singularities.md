---
name: park-driver-singularities
description: Park/driver mates can be satisfied yet pin NOTHING (singular) or fail IN PLACE (error-state far side) — how each class presents and the proven fixes
metadata:
  type: project
---

Two silent-failure classes in park/driver mates, both caught by the v0.15.0
release preflight park closure (2026-07-05) and fixed in PR #186.

**1. Singular drivers — satisfied, pinning nothing.** A plane-plane ANGLE to a
fixed plane defines a CONE of orientations: parked near the 0/180 apex
(magnifier wire swing, 0.74 deg) the constraint has no first-order authority
and the body can precess with the mate green. Subtler: the angle can sit far
from the apex (wire spin, 13.4 deg) yet its GRADIENT be perpendicular to the
DOF it's meant to pin (the wire's Right normal was built horizontal; spin about
the near-vertical axis tips it out-of-plane first-order, in-plane angle
stationary). Presents as: mate authors/replays "OK", component reads
under-constrained (status 2) at the closure. Fix: choose the constraint whose
gradient ALIGNS with the DOF — a point DISTANCE with a long lever arm for a
swing (hub depth, arm = whole wire), an angle whose plane normal makes the
gradient run along the spin axis (Front@wire vs RIGHT plane, 89.8 deg). Do the
row-rank check on the hook rotations before trusting a formulation. NB every
point-based constraint is spin-blind on an axisymmetric part.

**2. Error-state far side — the mate fails IN PLACE.** An unsigned distance
added on the wrong side can be CREATED by SW in hard error state 47 ("cannot
be solved -- dimension flipped") WITHOUT moving the component, so `_mate`'s
motion-based readback (moved <= tol) declares it healthy and the corpse
surfaces gates later as status-6 (swInvalidSolution) components. Since #186,
`_mate` reads the created mate's `GetErrorCode2` (FeatureByName, warnings
tolerated) and routes a hard error into the same delete-and-re-add-flipped
recovery as a wrong-side move.

Debugging kit: `cad/scripts/diagnostics/probe_magnifier_closure.py` — replays
the park sidecar, dumps GetWhatsWrong (byref-VARIANT trap!) + per-component
GetConstrainedStatus, measures actual pose values vs recorded scalars, and
isolates the offender by suppressing one driver at a time. Status enum:
2=under, 3=fully, 4=over, 5=no-solution, 6=INVALID-SOLUTION.

Related: [[sw-assembly-mate-diagnostics-api]] (the BDC distance-driver
singularity + GetWhatsWrong recipes), [[default-free-dof-park-drivers]],
[[solidworks-modeling-pitfalls]].
