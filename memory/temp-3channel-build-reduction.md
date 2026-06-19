---
name: temp-3channel-build-reduction
description: TEMPORARY 2026-06-19 reduction to 3 active channels + neutral amplitude bars for build performance; how/why and how to recover
metadata:
  type: project
---

TEMPORARY build-performance reduction (2026-06-19, user-requested). The machine is
driven to **3 active channels** (was 20) and **all amplitude bars reset to neutral**
(a_j = 0). Done ONLY to cut full-build/refresh time while the remaining parts of the
device are certified; **will be recovered** to 20 channels + the square preset once
certification is complete.

**Single knob:** `machine.yaml channels.active_count: 3`, read via
`_config.active_count()` / `_config.active_channels()` (first N rows).

**Reduced to active_count (3):** the per-channel mechanism — cylinder gear + cam
follower (connecting-rod) in `build_drive_train_assembly.py` (cylinder loop only),
and rocker-arm / amplitude-bar / channel-lever (top lever) / return spring + bushings
in `build_channel_assembly.py` (`CHANNELS` default = active_count).

**KEPT at full 20 (deliberate, per user):** the 20 **cone gears** (cone loop +
self-check still `range(20)`; cone gears 3..19 stay keyed to the cone shaft and mesh
nothing — fully defined, harmless), all 20 rows of `channels.yaml` (gear law, ratios),
and the synthesis math (`truth_model`, the `truth` verify suite harmonics 1..20 /
sawtooth-20, `pen_driver` S1..S20 chain) — neutral amplitudes make the pen trace flat,
so the motion gate passes trivially.

**Amplitudes:** `channels.yaml` all `amplitude_mm: 0.0`; `machine.yaml amplitude.preset:
neutral` (new preset). `verify.py verify_amplitude_preset._law` handles `neutral`
(asserts all zeros); gate renamed `amplitude:square-law` -> `amplitude:preset-law`.

**verify.py wired to active_count:** `CHANNELS = _config.active_count()`,
`_expected_channel_ratios()` uses `active_channels()`, and the channel/drive-train
`_COMPONENT_BAND` are formulas (channel = 7N+4±6, drive-train = 32+N±4) that reproduce
the measured N=20 bands (144, 52) and are correct at N=3 (25, 35). `output`/`frame`
bands unchanged (output has NO per-channel parts; the 20-hole summing plate just leaves
17 holes empty — `build_output_assembly.py`/`build_summing_lever.py` needed NO change).

**RECOVERY (one place + regen):** set `machine.yaml channels.active_count: 20`, restore
`amplitude.preset: square`, regenerate `channels.yaml amplitude_mm` by the square law
(a_j = 80/harmonic_n on ODD harmonics, 0 on even; values preserved inline as comments),
then `doit`. Everything else follows automatically.

**Drive-train crank-driver over-define (fixed):** at reduced channel counts the gear
solve converges with the crank EXACTLY on its design pose, so the spin-driver distance
target equals the handle's current position — a degenerate zero-motion mate SW rejects
as "over-defines the assembly". Proven a healthy 1-DOF mechanism (mobility probe: off-
design target adds with 0 What's Wrong, crank rotates the full 15 mm), NOT a real over-
constraint. Fix in `build_drive_train_assembly.py`: PERTURB the crank ~15° about its
spin axis (local +Y, transform cols 3..5) before `spin_driver`, mirroring the cam-lobe
perturb in `build_motion_study.py`; the closing ForceRebuild3 snaps it back. See
[[sw-assembly-mate-diagnostics-api]] for the GetWhatsWrong APIs used to diagnose it.

(Note: the earlier `DIMENSIONS.md` stale-vs-`dimensions.yaml` drift was resolved upstream
on `main`, not by this branch — no longer carried here.)

Related: [[harmonic-analyzer-project]], [[assembly-single-config]], [[parametric-springs]],
[[incremental-builds-validation]], [[od-62mm-reanchor]], [[sw-assembly-mate-diagnostics-api]].
