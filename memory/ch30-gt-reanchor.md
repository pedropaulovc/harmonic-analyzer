---
name: ch30-gt-reanchor
description: 2026-07-02 drive-train reposition off the ch30 GT triangulation — what moved, the traps hit, and the deferred north-region/top-frame follow-ups
metadata:
  type: project
---

**2026-07-02 (branch `drive-train/ch30-gt-reposition`):** the whole drive train was
re-anchored on the bundle-adjusted ch30 GT
(`cad/scripts/diagnostics/triangulate_ch30_gt.py`, ground truth in
`research/1-research-documentation/039-ch30-annotation-benchmark/ground_truth/`).
Headlines: drive plane y 126.8 → **104.8**; crank at **(122.8, 144.96)** — ABOVE the
64T, near-vertical 16T mesh (this dissolved the old "+122 pedestal photo vs 62.2 OD
anchor" contradiction: the wrong assumption was the HORIZONTAL mesh azimuth, not
either measurement); alignment pinion RESTORED level-inboard at x ±10.38 (the
2026-06-18 "impossible channel" argument located it in the wrong place); chain plane
z −146 → −155; connecting rod re-solved 163.18 → 180.83 (rocker rest tilt −6.92°
preserved bit-exact, downstream chain untouched).

**Why (traps worth remembering):**
- `PEN16_MID` in `build_drive_train_assembly.py` is **NEGATIVE** (−0.272); a stale
  comment claimed +0.275 and propagating it gave a wrong mesh c2c (39.90 vs the true
  40.446) that tripped the module's own assert. Recompute from live `_config`, never
  from comments.
- `build_channel_assembly.py` authors the ring at **+54.78** and the rocker pivot at
  **−72.9 in the SAME frame** — the rod is genuinely oblique ACROSS the machine
  (dx 102.5). A "both on the drive side" planar sketch gives a wrong-sign x and a
  bogus rod length (149.17); the old-value consistency check (does the code's own
  d=182.3 comment reproduce?) is what caught it.
- Commit e2062b5 (PR #132) shipped an unescaped apostrophe in a single-quoted
  dimensions.yaml scalar — `check:config` was broken at HEAD and nobody noticed
  because the doit stamp was already green. Fixed on this branch (`sketch''s`).
- **A part restored from git history re-inherits its era's defaults**: ch25's
  `build_alignment_pinion.py` called `build_fixed_gear` without `dp=`, silently
  taking the DP 30 default from BEFORE the OD-62.2 rescale (train is DP 49.82
  now) — teeth ~66% oversized, drum buried 5.4 mm into all 20 cylinder gears,
  caught only by the assembly interference gate (config + assembly math already
  said 49.82). When resurrecting a script, diff its numeric anchors against the
  CURRENT config-derived values, not just its own asserts.
- The teammate-authored `build_pinion_bracket.py` hit the arc-centre
  equation-rejection pitfall (bisect + fix: see
  [[solidworks-modeling-pitfalls]], last entry) — SolidWorks-free gates all
  passed; only a live build exposed it.
- **`_arc_geometry` ignored the rocker's intrinsic lever angle**: the tapered
  rocker strap puts its rod-pin bore at mid-depth(25.4) = 8.399, i.e. 0.4 ABOVE
  the pivot bore (mid-depth(0) = 8.0), so the pivot→pin lever leans β = 0.9007°
  above the arm's +X. The solve set arm_tilt = pin azimuth (β = 0), the placed
  pin landed R(tilt)·(0, 0.399) ≈ 0.4 mm high, the J2 rod revolute dragged the
  ring 0.363 above the cam centre, and the Ø30.6 cam dug 0.26 into the Ø30.8
  ring bore — 20 × 20.27 mm³ visible ONLY at the top-level interference gate
  (rod in `channel`, gear in `drive-train`; cross-sub blind spot, see
  [[flexible-subassemblies]] — whose Phase B "0.39 mm" incident was almost
  certainly this same β, mis-fixed then by re-pinning to datums). Diagnosed by
  dumping `IInterference.GetInterferenceBody().GetBodyBox()` (the crescent
  bbox decodes both circle centres) and reading `Transform2` off the saved
  channel.SLDASM. Fix: import `_mid_y`/`ROD_HOLE_X` from `build_rocker_arm`
  (imported-not-copied, the CAM_ECC precedent), lever = hypot = 25.4031,
  `arm_tilt = azimuth − β` → pin lands exactly on P; pin point preserved to
  3 µm so downstream held (lever_tilt 0.2004→0.2308 nudged the spring's
  neutral gap → `LEVER_EYE_Y` 1063.15→1063.25, per the math gate's own
  instruction). Latent at HEAD since the taper commit; masked because no
  from-scratch top rebuild ran since (same gate-rot as the YAML apostrophe).

**How to apply (deferred follow-ups, all GT-located but blocked on the
portal/back-frame re-layout):** arbor north bearing at z +91.5 (arbor north end held
at +78), cone tip post at (−81.03, 104.60, +101.83) (shaft tip ends 4.4 short at
97.4), the helical arbor end gears, and the top-frame/column stretch (GT corners
(±221.5, 1074.6, ±137.4), columns (±203.8, ±117.5) vs modeled ±208/1040.7/±123 and
±197/±112 — a ~3–7% global upper-frame stretch, flag-only in dimensions.yaml). GT
crank_sprocket z −189.1 vs modeled T12 plane −155 is the one un-adopted GT z (the
annotation likely reads the crank arm/handle, which the model puts at −167..−190).
Related: [[default-free-dof-park-drivers]], [[od-62mm-reanchor]].
