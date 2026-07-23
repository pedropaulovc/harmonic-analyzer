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

**The revert-at-scale is NOT an open bug — it is the documented "solver-state
attractor," same free-DOF root, already characterized AND mitigated.** A copy of
a slice with FREED operational DOF: the solver returns the copied chain to one
deterministic wrong pose on the free manifold from ANY start, even though every
copied mate is value/flip/alignment-identical to the seed's and satisfied at the
design pose. A raw Transform2 put lands exactly and is REVERTED by the next
solve; `SetTransformAndSolve3` reverts the same way. This is expected
constraint-solver branch-selection on an under-determined system (the same free
DOF as the wander); the minimal case shows the put HOLDS only because minimal
scale can't summon a strong non-design attractor (mirrored/rotated transforms,
coincident PLANE axial mates, 4-part multi-loop, ~100 components — proven by
`diag_cwm_attractor.py` #227, put held in all nine minimal cells).

MITIGATION (shipping in `build_channel_assembly` via `_cwm.copy_with_mates`): put
the chain at the design pose (makes the design branch the nearest) → author
transient driver mates pinning each free DOF (a real DRIVEN solve rewrites the
copied mates' stored state) → delete the drivers. Put-alone reverts;
driver-alone solves to the wrong nearest branch; the two-step lands it.

**2026-07-23 scale fix:** keep each copied channel's three transient drivers
alive until the complete bank is committed. Previously every one of the 18
channels re-put the complete 18×4-component copied bank before each of its three
drivers: 3,888 `Transform2` puts, 367.398 s of `cwm.pose_drive`. Now only the
current 4-part chain is re-put before each driver (12 puts/channel); already
settled predecessors stay pinned and unprocessed successors are overwritten on
their turn. Release all 54 drivers together with
`IModelDocExtension.MultiSelect2` + one `DeleteSelection2`. The pywin32 call MUST
marshal a `VARIANT(VT_ARRAY | VT_DISPATCH, [feature._oleobj_, ...])`; plain
lists, tuples, and `VT_ARRAY | VT_VARIANT` all returned 0/2 in a live positive
control, while the dispatch SAFEARRAY returned 2/2. Live full-channel result:
`assembly.build` 595.817 → 366.710 s (-229.107 s, -38.45%);
`cwm.pose_release` 74.233 → 2.292 s. All 60 free DOF, exact 128-component pose
ledger, health, zero-interference, mate-count and under-constraint gates passed.

Remaining perf question, not correctness: whether `IDragOperator` absolute Drag
(minimal attractor repro measured ~0.2 s/part vs ~0.8 s/authored-driver) can
replace transient drivers on the real slice. The pinned-bank formulation already
removes the prior O(N²) put cost, so any Drag experiment must beat the measured
366.710 s whole assembly and preserve the same closing gates.

Extends [[negative-result-positive-control]] and [[no-untested-failure-assumptions]];
verify empirically per [[verify-assumptions-live-sw]]; relates to
[[default-free-dof-park-drivers]].
