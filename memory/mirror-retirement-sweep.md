---
name: mirror-retirement-sweep
description: How #151 retired the M6.8 chirality mirror — golden-pose gate, transformation rulebook, accepted deltas
metadata:
  type: project
---

# Mirror retirement (#151/#153/#154/#156) — the sweep, 2026-07-08

**Governing invariant: world geometry is FROZEN.** Every component's final
world pose after the sweep must exactly match the pre-sweep build; part
geometry stays byte-identical. The authoritative targets are the golden pose
dumps in `cad/out/reports/pose-golden/` (captured 2026-07-08 pre-sweep with
`diagnostics/probe_pose_dump.py dump`; scratchpad backup `pose-golden-backup`).

**Why:** the mirror (M∘T∘S) was valid only under per-part symmetry claims
(#153) and re-keyed assemblies on placement yamls (#156); flip-ambiguous mates
could silently solve the wrong branch (#154). Re-authoring machine-handed
(crank at −X, east=−x, west=+x, output −Z) deletes the whole layer.

**How to apply (the transformation rulebook, verified against golden):**
- x anchors negate; y/z/gap/angle magnitudes stay positive; handedness lives
  in coordinate chain operators and placement rotations.
- 'x'-plane parts keep their rows; rot_z(θ) → rot_z(−θ) (tooth seeds negate).
- 'z'-plane parts pick up an explicit extra Ry(180)
  (`compose_rows(rot_z_rows(θ), ROT_Y_180)` etc.) and their origin shifts 2c
  along z (part thickness when c = T/2) — pinion brackets +5, pivot blocks
  +12, crank-arm origin at the plate's NORTH face.
- ROT_Y_POS90 / ROT_X_±90 are conjugation-invariant; Ry(−I) → Ry(+I).
- Plane-local ↔ machine maps conjugate: `(px + x·C + z·S, pz − x·S + z·C)`.
- verify=(comp, readback) mates need NO sign edits (values physically
  unchanged); `_FLIP_INVERT` stays valid and self-audits loud at build.
- Azimuth chains must keep BOTH legs as plane-local magnitudes (ALPHA16 bug:
  `X_CRANK − GEAR64_SEAT[0]` flipped sign and shifted PINION_SEED_DEG 21.8 →
  13.4; fix: `GEAR64_SEAT[0] − X_CRANK`).
- Instance ORDER is part of the frozen world: generators that used to emit
  (east, west) must keep emitting the same machine order or -1/-2 suffixes
  swap (clamp screws, block screws, paper-drive clamps west-first).

**Offline gate:** `cad/scripts/diagnostics/check_mirror_retirement.py`
recomputes all 408 placements from the modules SolidWorks-free and diffs
against golden. Accepted deltas (documented inline): magnifier lever-wire
0.015 mm / 4e-5 rows (the old mirror's bbox-z-centre 2c artifact — the new
values are the authored intent), crank family ~1.2 µm (golden-side mate-solver
noise), chain links ≤0.51 mm (the pattern's own fill drift, build gates at
2.0 mm).

**Left as-is:** `_chain.py` still models the chain loop in its own +X frame
with `mirror_x=True` reflecting to machine (pre-existing internal convention);
`_assert_chain_layout` pins its anchors to −KNOB_SHAFT_XY / −X_CRANK. Older
comments in frame/base use east=+x labels from an earlier era — geometry
verified correct, labels not globally reconciled.

Related: [[default-free-dof-park-drivers]], [[mate-flip-determinism]].
