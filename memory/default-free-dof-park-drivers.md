---
name: default-free-dof-park-drivers
description: Operational DOF are genuinely FREE — park machinery KILLED 2026-07-09 (no PARK_* mates, no locked mode, no closure proof); kinematic DOF manifest (.dof.json) + exact-set soundness gate replace it
metadata:
  type: project
---

**2026-07-09 — the park machinery is KILLED (Pedro: "does not seem useful").**
Everything below the divider is history of the removed system. What remains:

- Every part is inserted on its exact Python-solved transform and the real
  contact mates hold it, so **the build is deterministic without fully
  defining the assembly** (Pedro's argument for the kill). Freed operational
  DOF (drive-train 4, channel 3/channel, magnifier 3, paper-drive/summing/pen
  1 each) simply get NO driver mate.
- **Kinematic DOF manifest** (the kept half): `free_dof_key=` on the
  `*_driver` helpers ALWAYS records the drive spec (entities + rest value +
  mate side) into `_assembly._DOF_SPECS` → `write_dof_manifest(stem)` →
  `.<stem>.dof.json` sidecar (rides the remote cache). `_assembly_postbuild.
  load_dof_manifest` / `author_dof_drives` author entries TRANSIENTLY (mates
  named `DRIVE_<key>`) for verify:kinematics (pen Fourier sweep targets
  `D1@DRIVE_pen_travel`, magnifier `lever_rock` chain sweep, paper-drive crank
  instance lookup) and the mobility/motion diagnostics; callers discard the
  model unsaved.
- **Exact-set soundness gate** replaces the release closure proof:
  `assert_free_dof_necessity(..., allowed_stems=...)` — necessity (≥ N
  under-constrained, required families present) AND no under-constrained
  component outside `verify._ALLOWED_FREE_STEMS[name]` (the freed families
  plus everything coupled). Catches the one real thing the closure caught
  (an unintended freedom) in every soundness pass instead of only at release.
  The allowed lists were pinned from a live status dump; the gate names any
  stray, so extending after a deliberate coupling change is a one-line fix.
  drive-train/magnifier/paper-drive lists span the coupled trains.
- **Deleted**: `PARK_PREFIX`, `mark_park_driver`, `find_park_drivers`,
  `set_park_defer`/`park_deferred`, `assert_expected_free_dof`,
  `assert_park_closure`, `is_locked_build`, `build_lock.yaml` (no locked
  mode at all), the preflight closure stage (preflight = gear-ratios only),
  `.park.json` sidecars (now `.dof.json`).
- **Trap preserved**: mate `label=` strings that mention "PARK driver" (e.g.
  drive-train's crank/cone/pinion/lift-rod drivers, pen's travel driver) were
  deliberately NOT renamed — `_seed_flip` derives the recorded mate side from
  the label signature and several are in `_FLIP_INVERT`; renaming would flip
  replay sides. Labels are log strings, not machinery.

**Why:** the closure re-proved what insertion already fixed; locked mode was
never used; the defer/replay path was a recurring bug source (replay flips,
corpse mates, singularities — see [[park-driver-singularities]],
[[paper-drive-park-closure-gate]], now historical).

**How to apply:** freeing a new operational DOF = call the `*_driver` helper
with `free_dof_key="<key>"` (records, never authors), bump
`verify._expected_free_dof`, add the family to `_REQUIRED_FREE_STEMS` and its
coupled families to `_ALLOWED_FREE_STEMS`. To drive a freed DOF in a gate or
diagnostic: `author_dof_drives(adapter, [spec])` transiently, discard unsaved.

---

HISTORY (removed system, for archaeology): the original inversion authored a
`PARK_<key>` mate per freed DOF, suppressed in `free` builds / engaged in
`locked` builds (`build_lock.yaml`), gate = `assert_expected_free_dof`
suppress/re-engage closure cycling. 2026-07 it became defer-and-replay:
specs recorded to `.<stem>.park.json`, release preflight replayed them and
proved 0-DOF closure (`assert_park_closure`), soundness kept necessity only.
Freed-DOF growth: drive-train crank (2026-06) + cone swing (2026-07-03,
PR2r3) + pinion swing + lift-rod/cam (PR8 → 4); channel 3/channel with the
lever COUPLED via J5 foot-on-arc (2026-07-07, PR #201); paper-drive crank
spin over the Belt/Chain + rack-pinion couplings (2026-07-05); summing lever
rock + pen carriage travel (2026-07-07). Full-scale validation once read
`park_drivers=60 expected_free_dof=60 free_dof=60` on channel.

Related: [[fix-relations-last-resort]], [[channel-amplitude-state]],
[[single-assembly-fast-verify]].
