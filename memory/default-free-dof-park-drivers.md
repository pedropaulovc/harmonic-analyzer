---
name: default-free-dof-park-drivers
description: Default build saves a working kinematic model (operational DOF FREE); PARK_* mates + build_lock flag + closure DOF gate
metadata:
  type: project
---

> **UPDATE 2026-07 — defer-and-replay (park mates added by release, not build).**
> The freed-DOF park drivers are no longer *authored-then-suppressed* by the build.
> They are NOT authored at all in a `free` build (skipping ~61 mate solves — 1
> crank + 3×20 channel — is the build-time win); each is RECORDED as a resolved
> spec (`free_dof_key=` on the `*_driver` helpers → `_assembly._record_park_spec`)
> into a `.<stem>.park.json` sidecar beside the `.SLDASM` (a cached assembly
> output). The opt-in **release preflight** (`preflight_release.py`, doit task
> `preflight`, COM-spine, gates `release`, NOT in `build`) replays them
> (`replay_park_specs`), runs the exact-DOF closure (`assert_park_closure`), then
> DISCARDS the model unsaved — shipped `.SLDASM` stays free. Build-time `soundness`
> now proves only necessity (`assert_free_dof_necessity`, ≥ N under-constrained);
> the closure moved to preflight. ENGAGED setup drivers (`PARK_pinion_swing`, cone
> swing) are unchanged — still authored inline, never deferred. Diagnostics:
> `build_mobility_probe.py` replays specs before its baseline;
> `build_motion_setup_drives.py` treats an absent (deferred) driver as already-free;
> `build_motion_study.py` (full-device, geometry-classifier) needs a seat re-check.
> The prose below describes the ORIGINAL author-but-suppress mechanism.

**Inverted the always-0-DOF design (2026-06, drive-train first, PR stacked on #110
`drive-train-unlock`; extended to channel 2026-06).** The default build now saves a
WORKING kinematic model: the predetermined operational DOF are left FREE.
- **drive-train** frees the **crank spin** (1 DOF — drag the crank, the whole geared
  train turns). Cone-post swing stays park-driven. The alignment-pinion swing
  (`PARK_pinion_swing`, restored 2026-07-02 with the ch30 GT re-anchor) is likewise a
  park-driven SETUP DOF: the angle driver pins the FRONT strap (`pinion-bracket`
  family — the drum itself is tied to the strap by two-real mates), stays ENGAGED in
  `free` builds, and the free-DOF closure count stays 1 (crank only). p2 probe/motion
  stages target family `pinion-bracket`, `only_type=ANGLE` (the straps also carry
  single-real axial DISTANCE locators that must NOT be suppressed — the p1 cone-post
  pattern).
- **channel** frees, per active channel, **3 DOF** — rocker swing + connecting-rod
  follow + amplitude-bar slide — so a 20-channel build saves 60 free DOF. Validated
  full-scale 2026-06: `park_drivers=60 expected_free_dof=60 free_dof=60`, interference
  hits=0, deep-health 165 targets clean. The reorg that introduced this (4 mate
  changes, see below) replaced the rocker spin_driver + global-Front-Plane axial with:
  rocker spin→`PARK_rocker_angle` + axial **distance to the neighbour pivot-bushing**
  (PITCH/2, the #110 neighbour idiom — bushings pre-placed BEFORE the channel loop);
  rod→**coaxial coincident on the rocker's rod-bore axis** + Z-distance to rocker Front
  Plane + `PARK_rod_swing` (was `_pin_design_pose`'s 4 global-datum mates, now removed);
  bar foot-X→`PARK_bar_amplitude`. Channel-level validated only — the top-level
  cam-ring↔cylinder-gear-lobe interference (~0.39mm slack `_pin_design_pose` guarded) is
  deferred to a `harmonic_analyzer` build.

**Mechanism — author-but-suppress.** Every reproducibility-locking mate is still
authored, then its FEATURE renamed to `PARK_<key>` (e.g. `PARK_crank_angle`) — the
mate `label=` is only a build-log string, SW auto-names the feature `Angle1`, so the
gate would never find it without the rename. Default build SUPPRESSES the `PARK_*`
mate (pins nothing → DOF free); a `locked` build leaves it ENGAGED (the old
fully-defined, byte-reproducible snapshot — explicit opt-in for a pinned export).

**Why:** the shipped default was a frozen 0-DOF model — you couldn't drag the crank
and watch the gears turn, and the artefact didn't represent the device's kinematics.

**How to apply:**
- Mode per assembly: `cad/config/machine/build_lock.yaml`, read as a STRING-LITERAL
  `_config.machine("build_lock", "drive_train")`. Literal args tokenise it into that
  assembly's doit `file_dep` + remote-cache digest (`_buildgraph._family_tokens`), so
  flipping `free`↔`locked` rebuilds ONLY that assembly and keys the cache to a
  distinct artefact. The flag MUST be the config value (in the digest), never an env
  var — an env flag would collide free/locked under one key.
- Helpers in `cad/scripts/_assembly.py`: `PARK_PREFIX`, `mark_park_driver(adapter,
  mate, key)` (renames via the adapter's `rename_feature` → `IFeature.Name`),
  `find_park_drivers` (`list_mates` → `[(name, suppressed)]` for `PARK_*`).
- **DOF gate adapts, nothing else does.** SolidWorks has NO scalar DOF API. The build
  and verify `soundness` both call `assert_expected_free_dof(adapter, N)` — the
  **closure check**: assert exactly N `PARK_*` are suppressed → re-engage them →
  ForceRebuild → assert 0 under-constrained (proves the drivers are the SOLE freedom,
  so DOF count = N) → re-suppress → restore the free pose. `N == 0` (locked / no
  parked DOF) reduces to the strict `assert_components_fully_defined`. Every NON-DOF
  gate (over-constrained, model-healthy, interference, gear-ratios, component-count)
  runs on the as-built model UNCHANGED. `assert_components_fully_defined` itself is
  unchanged (the 8 build-script callers keep strict 0-DOF).
- verify `_expected_free_dof(name)`: drive-train→1 (if free), channel→`3 *
  _config.active_count()` (if free), else 0 (re-reads `build_lock.yaml`; freshness guard
  guarantees the saved model matches). The gate routes to `report.agate(...)` (async)
  for the closure when free, else the sync `report.gate(...)`.
- `build_mobility_probe.py` re-engages all `PARK_*` BEFORE its 0-DOF baseline (the
  default-free saved model is not 0-DOF), then suppresses each driver to show it frees
  its own part family.
- Editing `_assembly.py` flips the recipe digest of EVERY assembly (shared closure
  dep), so `doit assembly:drive_train` rebuilds the whole COM spine up to drive_train
  — a free regression check that the strict path still passes frame/channel/etc. See
  [[single-assembly-fast-verify]] to iterate on one assembly faster.

No defensive locked-pose fallbacks were added — per [[no-untested-failure-assumptions]],
all checks run on whatever mode is actually built. Full design in AGENTS.md
"Default-free DOF (operational kinematics)". Related: [[fix-relations-are-a-last-resort]],
[[channel-count-amplitude-state]].
