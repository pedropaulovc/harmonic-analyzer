---
name: paper-drive-kinematic-probe
description: Paper-drive crank→feed kinematic probe findings — belt ratio 0.538≠0.50, knob-shaft spin axis ⊥ sprockets
metadata:
  type: project
---

`cad/scripts/build_kinematic_probe.py` (added for codex #189, PR chain-component-pattern)
drives the crank +30° on the built `paper-drive.SLDASM` and reads the whole feed train
back. Two non-obvious findings that will trip up anyone reasoning about this model:

1. **The SW Belt/Chain feature does NOT couple at the exact tooth ratio.** Nominal is
   12:24 = 0.500 (and the physical chain drive IS exactly 0.5), but the live
   `insert_belt_chain` (EngageBelt, `pulley_diameters=[24,48]`) couples crank→T24 at
   **~0.538** (measured: crank 30.0° → T24 16.15°). ~8% high. Everything DOWNSTREAM of
   T24 is exact — platen = `NET_RACK_TRAVEL_PER_KNOB_REV(63.84) × 16.15/360 = −2.86 mm`,
   matches to 0.001 mm. So the rack-pinion is faithful; only the belt-feature coupling
   drifts. Left as-is (out of scope for #189); the probe REPORTS the measured ratio and
   band-checks ~1:2 rather than asserting 0.5. If you ever need an exact 12:24, the belt
   feature is the thing to fix, not the rack. See [[belt-chain-feature-com-binding]].

2. **The knob shaft's modeled spin axis is PERPENDICULAR to the sprockets'.** T24 and the
   fine pinion spin about global Z; the `transgear-knob-shaft` (placed `ROT_X_POS90`,
   `ground=False`, Lock-mated to T24) turns about global **Y** — same 16.15° magnitude,
   different axis. So any readback that projects rotation onto a shared/crank axis reads
   a FALSE ZERO for the shaft (this bit the first probe). Compare rotation by MAGNITUDE
   (axis-angle angle via `acos((trace−1)/2)`), never by axis projection. The Lock mates
   still couple all three (:592) — the cluster follows the crank; the perpendicular axis
   is a modeling-frame artifact, not a broken mate.

The probe never saves (drives + reads, then `CloseAllDocuments`). It is a NON_PART_SCRIPT
(diagnostic, like `build_mobility_probe.py`), run by hand, not on the COM spine. See
[[default-free-dof-park-drivers]] and [[chain-component-pattern]].
