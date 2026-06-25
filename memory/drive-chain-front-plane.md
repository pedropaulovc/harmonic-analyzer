---
name: drive-chain-front-plane
description: the crank<->knob roller chain rides the FRONT plane (machine z -146); both sprockets + crank arm laid out south of the cone and the stub disc
metadata:
  type: project
---

The roller chain coupling the crank (drive-train) to the paper-drive knob shaft
runs on a flat loop on the machine's FRONT face — book ch30 p005/p002 show it in
front of the cone/gear stack, NOT beside it. It was originally at z ~-81 (north
of the crank pedestal, in the cone-post's z-band -75..-103) and collided with
the cone once the drum/gears moved out to book line-2. Fix = drop the whole
chain plane to **machine z -146** (`CHAIN_MID_Z`, both `REMOVABLE_Z0`s set so
T12/T24 mids = -146), which clears:
- the **cone-post** (z -75..-103) by ~43 mm in z;
- the paper-drive **stub disc** (z -134.5..-137.5) by ~6.5 mm — the knob T24's
  tips overlap the disc rim by ~1.4 mm in XY (c2c 66.05 < r26+r41.49), harmless
  ONLY because they no longer share z. Chain plane must stay <= ~-141 or T24
  fouls the disc.

Three coupled moves make z -146 work (all on this branch / PR 82):
1. **Crank T12 sprocket** (`build_drive_train_assembly.REMOVABLE_Z0 = -148.5`,
   band -148.5..-143.5): between the pedestal south face (-131.6) and the arm.
2. **Knob T24 + knob shaft reversed**: `build_paper_drive_assembly` places
   `transgear-knob-shaft` with `ROT_X_POS90` at z -149 (was ROT_X_NEG90 at
   -76.5) so the grab-knob tucks NORTH (-91..-84.5) and the plain south shaft
   hosts T24 (`REMOVABLE_Z0=-148.5`) clear of the disc + fine pinion (-128..-134,
   parked, unchanged). No knob-shaft PART change — the 58 mm shaft already spans
   the range when reversed.
3. **Crank arm in FRONT (south) of the sprocket** — user: "crank arm should be
   in front of chain sprocket otherwise it will interfere when turning." The
   handle grip extends machine -Z from the arm, so an arm NORTH of the chain
   sweeps the grip back THROUGH the chain plane. Fix = lengthen the crankshaft
   +10 (`build_crankshaft.SHAFT_LENGTH 120->130`, drive-train `CRANKSHAFT_Z0
   -150->-160`, `CRANKSHAFT_LENGTH 130`, north end stays -30) and seat the arm
   at the new south end (`CRANK_ARM_Z0 = CRANKSHAFT_Z0`, -160..-152). The arm
   then rotates entirely in its own z-band south of the chain (-146) at EVERY
   angle, so turning clearance is guaranteed by z-separation, not just the rest
   pose. Pinion z is absolute (64T seat) + the keyed chain locks to the shaft
   AXIS, so the length change doesn't disturb the gear mesh.

`_chain.py` computes only the chain XY (from `CRANK_CENTRE` imported live as
drive-train `X_CRANK,Y_DRIVE`, and `KNOB_CENTRE`); the z plane is paper-drive's
`CHAIN_MID_Z`. Verified: drive-train, paper-drive, and the full
harmonic-analyzer all build interference-free + healthy. Related:
[[harmonic-analyzer-project-decisions]], [[rocker-support-window-faces-x]].
