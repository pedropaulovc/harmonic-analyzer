---
name: default-free-dof-park-drivers
description: Default build saves a working kinematic model (operational DOF FREE); PARK_* mates + build_lock flag + closure DOF gate
metadata:
  type: project
---

**Inverted the always-0-DOF design (2026-06, drive-train first, PR stacked on #110
`drive-train-unlock`).** The default build now saves a WORKING kinematic model: the
predetermined operational DOF are left FREE. Today that is drive-train's **crank
spin** only (1 DOF — drag the crank, the whole geared train turns). Cone-post swing
and the 20 channel amplitude bars stay park-driven at their engaged pose (setup /
disengage motions; covered by motion + mobility suites).

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
- verify `_expected_free_dof(name)` returns 1 only when drive-train was built `free`
  (it re-reads `build_lock.yaml`; the freshness guard guarantees the saved model
  matches). The gate then routes to `report.agate(...)` (async) for the closure, else
  the sync `report.gate(...)`.
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
