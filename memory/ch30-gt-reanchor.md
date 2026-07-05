---
name: ch30-gt-reanchor
description: 2026-07-02 drive-train reposition off the ch30 GT triangulation — what moved, the traps hit, and the deferred north-region/top-frame follow-ups
metadata:
  type: project
---

**2026-07-02 (merged to main; work branch `drive-train/ch30-gt-reposition`, since deleted):** the whole drive train was
re-anchored on the bundle-adjusted ch30 GT
(`cad/scripts/diagnostics/triangulate_ch30_gt.py`, ground truth in
`research/1-research-documentation/039-ch30-annotation-benchmark/ground_truth/`).
Headlines: drive plane y 126.8 → **104.8**; crank at **(122.8, 144.96)** — ABOVE the
64T, near-vertical 16T mesh (this dissolved the old "+122 pedestal photo vs 62.2 OD
anchor" contradiction: the wrong assumption was the HORIZONTAL mesh azimuth, not
either measurement); alignment pinion RESTORED level-inboard at x ±10.38 (the
2026-06-18 "impossible channel" argument located it in the wrong place); chain plane
z −146 → −155; connecting rod re-solved 163.18 → 180.83 (rocker rest pose preserved
bit-exact — the −6.92° is the pin AZIMUTH, arm tilt is −7.82°; downstream chain untouched).

**Why (traps worth remembering):**
- ~~"in the side views the green casting is a SLAB, not a round column"~~ **REFUTED
  same day** (user caught it visually): the crank pedestal is a **cylinder**. The
  slab read came from the true side views (page004/008), where the column hides
  behind a frame column and the crank arm; the **quarter views** (page003/009) show
  one round green column — elliptical top with a two-screw split bearing cap, domed
  boss (the cone-shaft front stub end) on the flank. Worse, the slab band −145..−125
  hung past the base bottom-plate corner (−139.7) — the very anchors the GT
  triangulation was pinned to — and NO gate checked "a base-bolted mount stands on
  the base" (added: `footprint:drive-train-mounts-on-base` in the math suite).
  Corridor math then forced the real anatomy: stub boss (−123) → 64T south face is
  ~49 deep and a Ø46.2 column fills it with ~2 air each side, with the swing journal
  **nested inside** (Ø26 bottom-entry cavity + Ø24 cylindrical block + straight wall
  windows for the 12.52° shaft — a slab + side-by-side block never fit, which is
  what pushed the slab off the base). Lessons: (1) a shape read from an occluded
  view must be cross-checked against the views that actually see the part; (2) when
  a placement only "fits" by leaving the base, treat that as a wrong-anatomy signal,
  not a coordinate.
- **Adding an off-axis feature to a previously symmetric part breaks the M6.8
  mirror silently.** The whole assembly is x-mirrored at placement
  (`mirror_placement`, machine crank at −X while the scripts derive at +X);
  the default `MIRROR_PLANE "x"` is only valid while the part IS x-symmetric.
  Nesting the swing journal made the crank pedestal chiral, its cavity/windows
  landed un-mirrored (+2.03 where −2.03 was needed) and only the assembly
  interference gate caught it (3975 + 675 + 173 mm³, pedestal vs post/shaft).
  Diagnosis that worked: attach to the live failed Assem via COM and dump
  `Transform2` of the clashing components (`diagnostics/probe_pedestal_clash.py`, since deleted 2026-07-03)
  — the −x translations exposed the frame flip in one read. Fix idiom = the
  existing `x0` pattern (summing-lever): author the part script itself
  mirrored (negate its x literals), declare `"crank-pedestal": "x0"`, and
  negate the part-frame x in the assembly's import-time asserts. Lesson: any
  new x-asymmetric feature on a mirror-placed part must switch the part to
  the authored-mirrored idiom — grep `MIRROR_PLANE` before hardcoding
  part-frame x offsets. Also same-day: cut-extrudes default to the −sketch-
  normal side (bosses default +normal — the nameplate exemplar misleads);
  the front/rear window cuts needed swapped `reverse_direction`, caught by
  the part volume gate missing by exactly the cavity-overlap delta.
- `PEN16_MID` in `build_drive_train_assembly.py` is **NEGATIVE** (−0.272); a stale
  comment claimed +0.275 and propagating it gave a wrong mesh c2c (39.90 vs the true
  40.446) that tripped the module's own assert. Recompute from live `_config`, never
  from comments.
- ~~the rod is genuinely oblique ACROSS the machine~~ **REFUTED same day** (see
  the vertical-rod bullet below): the rods hang PLUMB. The "old-value consistency
  check" that anchored the oblique reading (does the code's own d=182.3 comment
  reproduce?) was **circular** — the d=182.3 comment was WRITTEN BY the same
  "line-2 photogrammetry" commit that introduced the oblique read, so reproducing
  it only proved self-consistency, not truth. A consistency check against a value
  is worthless if the value and the hypothesis share an author-commit; check
  against evidence from a DIFFERENT provenance (here: the ch30 photos + GT
  rocker-corner triangulation).
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

- **Vertical rods (same-day follow-up, second PR):** *(numbers below superseded
  same day by the ch14 ROM re-derive — ROD_HOLE_X 127.37, ROD_C2C 147.67, level
  rest pose, ecc 8.64 lobe-up; the plumb topology stands. See
  [[ch14-rom-rederive]].)* the ch30 photos show every
  connecting rod hanging PLUMB from the rocker arm's rod-side tip onto its cam;
  the GT rocker-corner triangulation (solved cameras from
  `triangulate_ch30_gt.py`, ray-intersected `rocker_arm_corner_*` clusters) lands
  the arm's rod-side end at machine (−60.0, 252.8) — directly over the drum —
  and the far end at (+216.1, 246.8), midpoint +72.5 ≈ the frame's +72.9 pivot
  (seesaw confirmed). Fix: `ROD_HOLE_X` 25.4 → **127.49** (hole solved so the pin
  sits exactly above the phased cam centre at the PRESERVED −7.8158° rest tilt;
  5.3 inboard of the bottom-arc end, which predicts the GT corner at −58.6),
  `ROD_C2C`/`CENTER_DISTANCE` 180.83 → **144.75**, rod tilt +34.51° → −0.001°.
  Downstream chain untouched (lever_tilt 0.23077, spring gate delta −0.004,
  `LEVER_EYE_Y` 1063.25 stays). M6.3's "1-inch lever" closed the same
  vertical-rod argument against the OLD arbor x 47.5; the GT drum move broke
  that closure silently — the lesson is that a **derived** value's derivation
  chain must be re-run when any anchor moves, or the value quietly becomes a
  fossil (grep the codebase for the anchor when adopting a GT move).

**How to apply (deferred follow-ups, all GT-located but blocked on the
portal/back-frame re-layout):** arbor north bearing at z +91.5 (arbor north end held
at +78), cone tip post at (−81.03, 104.60, +101.83) (shaft tip ends 4.4 short at
97.4), the helical arbor end gears, and the top-frame/column stretch (GT corners
(±221.5, 1074.6, ±137.4), columns (±203.8, ±117.5) vs modeled ±208/1040.7/±123 and
±197/±112 — a ~3–7% global upper-frame stretch, flag-only in dimensions.yaml). GT
crank_sprocket z −189.1 vs modeled T12 plane −155 is the one un-adopted GT z (the
annotation likely reads the crank arm/handle, which the model puts at −167..−190).
Related: [[default-free-dof-park-drivers]], [[od-62mm-reanchor]].
