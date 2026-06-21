---
name: channel-amplitude-state
description: Final channel-count + amplitude-preset state — full 20 channels, neutral preset — lives on similarity-tuning branch (63dd47e), NOT for main
metadata:
  type: project
---

**Current state (2026-06-20, supersedes the earlier temporary 3-channel cut):** the
machine is built with **all 20 channels active** and **all amplitude bars at rest**
(neutral preset, a_j = 0). This is the **chosen final** state for the
similarity-tuning exercise — NOT a temporary perf cut, and there is no longer any
"recover to square" plan. Neutral matches the reference photos: every channel return
spring sits at the same rest length, so one shared spring geometry covers all 20
channels. The `square` preset (a_j = 80/harmonic_n on ODD harmonics, 0 on even — the
textbook square-wave partial sum) is documented in the YAML as the alternative.

**⚠️ Branch hygiene:** this config lives as a single commit `63dd47e` on
`claude/similarity-tuning` and is **NOT meant to be merged to `main`** (per user,
2026-06-20). It is the experimental neutral/20-channel baseline for tuning CAD-vs-photo
similarity. Keep it on the branch; do not open a PR to main for it.

**Config knobs (post-#47 split — `machine.yaml` is gone, replaced by `machine/*.yaml`):**
- `cad/config/machine/channels.yaml` → `active_count: 20`, read via
  `_config.active_count()` / `_config.active_channels()` (first N rows).
- `cad/config/machine/amplitude.yaml` → `preset: neutral`; `channels.yaml` all
  `amplitude_mm: 0.0`.

**active_count semantics:** caps the per-channel mechanism the build instantiates —
cylinder gear + cam follower (connecting-rod) in `build_drive_train_assembly.py`, and
rocker-arm / amplitude-bar / channel-lever (top lever) / return spring + bushings in
`build_channel_assembly.py`. At the full count (20) every channel is built. The 20
**cone gears** are always KEPT (cone stack derived from the full count;
`build_drive_train_assembly.py` reads all 20 rows), as are all 20 rows of
`channels.yaml` (gear law, ratios, synthesis truth model). With neutral amplitudes the
pen trace is flat, so the motion gate passes trivially.

**verify.py wiring:** `CHANNELS = _config.active_count()`, `_expected_channel_ratios()`
uses `active_channels()`; channel/drive-train `_COMPONENT_BAND` are formulas
(channel = 7N+4±6, drive-train = 32+N±4) reproducing the measured N=20 bands (144, 52).
`verify_amplitude_preset._law` handles `neutral` (asserts all zeros); gate is
`amplitude:preset-law`. `output`/`frame` bands unchanged (the 20-hole summing plate just
leaves holes empty at reduced counts).

**Drive-train crank-driver over-define (fixed, general):** at REDUCED channel counts the
gear solve converges with the crank exactly on its design pose, so the spin-driver
distance target equals the handle's current position — a degenerate zero-motion mate SW
rejects as "over-defines the assembly". Proven a healthy 1-DOF mechanism (off-design
target adds with 0 What's Wrong, crank rotates full 15 mm), NOT a real over-constraint.
Fix in `build_drive_train_assembly.py`: PERTURB the crank ~15° about its spin axis (local
+Y, transform cols 3..5) before `spin_driver`; the closing ForceRebuild3 snaps it back.
At full 20 channels this path isn't hit, but the perturb is harmless and stays. See
[[sw-assembly-mate-diagnostics-api]] for the GetWhatsWrong APIs used to diagnose it.

**DIMENSIONS.md:** the generated `cad/DIMENSIONS.md` was retired entirely (PR #50, on
main) — `cad/config/dimensions.yaml` is the single source of truth; the `.md` is now an
untracked on-demand render (gitignored). The old stale-vs-yaml drift gate is gone.

Related: [[harmonic-analyzer-project]], [[assembly-single-config]], [[parametric-springs]],
[[incremental-builds-validation]], [[od-62mm-reanchor]], [[sw-assembly-mate-diagnostics-api]].
