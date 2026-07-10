---
name: cwm-free-dof-by-design
description: CopyWithMates2 not preserving a copied component's free-DOF pose is EXPECTED SW behavior, not a bug; the real open symptom is Transform2-put-reverts-at-scale
metadata:
  type: project
---

The CopyWithMates2 "wander" chased in #227/#231/#232/#233 is **by design, not a
bug** (concluded 2026-07-10 with Pedro, SW 2024 SP3 + SW 2026 SP2, via raw
pywin32 + an early-bound C# Interop port; diagnostic lives at
`cad/scripts/diagnostics/diag_cwm_min.py`).

**Why it is not a bug.** When a copied component is UNDER-CONSTRAINED, its free
DOF has no mate-defined value, so CopyWithMates2 has nothing to preserve there —
it re-solves and the free DOF lands wherever the solver puts it (deterministic,
but not the seed's value). Fully-constrain the copy (`--pin`: a 3rd Right-plane
coincident mate that removes the free slide) and it lands EXACTLY on pose. An
undefined position was never defined, so moving it is within spec.

**Facts established (all measured, not assumed):**
- The minimal case: 1 zero-feature part, 2 root-plane mates (coincident Top +
  distance Front) leave exactly ONE free DOF — the in-plane slide along the
  planes' intersection line; all rotations incl. spin are constrained (proven by
  `--pin` fully defining the part with a single translational mate).
- Correct API usage does NOT change it: `Repeat=false` + `NewEntityToMateTo` =
  the root planes authors the copy's mates correctly (err=0) and it still lands
  off-pose. So it is the free DOF, not misuse. (Re-valuing a distance mate DOES
  require passing NewEntityToMateTo even for the same plane — a real usage rule.)
- `CopyWithMates2` returns **False** unreliably: False on the off-pose copy, on
  the on-pose `--pin` copy, AND on SW's own `Copy_Component_With_Profile_Center_
  Mate` example recreated on SW 2026 SP2. Its bool return is not a signal on this
  build — only the resulting Transform2 / DOF status is.
- Separate CONFOUND (off by default): the first component is auto-fixed; a
  distance mate on a fixed component conflicts with the fix → spurious "mates
  over-defined/corrupted" errors unrelated to CopyWithMates2. Float the seed
  (`UnfixComponent`) to remove it (`--fixed-seed` demonstrates it).

**Build lesson:** a component copied with a free DOF will NOT inherit the seed's
pose along that DOF — fully-mate it, or place it explicitly with a Transform2 put
(what the pipeline does). Relates to [[default-free-dof-park-drivers]] (the build
deliberately ships free operational DOF, placed by insertion transform).

**STILL OPEN — the actual symptom to chase:** the original report was a
Transform2 put **REVERTING after EditRebuild3 on the large multi-loop assembly**.
The minimal case shows the put HOLDS, so it does not capture that. If there is a
real defect, it is the revert at scale, not this expected free-DOF placement.
Extends [[negative-result-positive-control]] and [[no-untested-failure-assumptions]];
verify empirically per [[verify-assumptions-live-sw]].
