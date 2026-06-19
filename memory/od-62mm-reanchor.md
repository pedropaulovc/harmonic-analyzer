---
name: od-62mm-reanchor
description: gear train re-anchored OD 103.3->62.2mm (low conf); alignment pinion removed; SW rebuild DONE+green & landed on main (PR#12 Fix#8 reverted to land it, must re-apply)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3dfc247c-5caa-477e-bc6b-0e5deca6f310
---

2026-06-18: user re-anchored the cylinder/cone gear OD from 103.3 to **62.2 mm**
(LOW confidence — eyeballed by scaling gear brackets in the p.25 bottom-left photo
vs the back-view), directive: "i am positive stick to 62.2 and fix everything downstream."

What changed (committed to main, NOT YET SolidWorks-validated):
- machine.yaml: diametral_pitch 30->49.82, cone incline 21.10->12.52°, radius_step
  2.54->1.5295, drum_seat 7.5->7.22 (Z_PITCH held at 7.0565 so the channel grid +
  ~100 downstream parts DON'T move — only gears/cam/cone shift). crank_drive DP
  16->26.57 (= DP_TRAIN*64/120) so the 64T radius again equals the cone T120 (the
  book's "64T OD ≈ cone 120T OD" check is RESTORED; R64/R16/ADD16 de-hardcoded).
- cam OD 50.8->30.6, ecc 5.08->3.06 (scaled 0.6022, rocker stroke shrinks, accepted);
  rod ring bore 51->30.8; cone-shaft re-stepped 3/8-1/4-1/8-1/32" (T006 tip journal
  now 0.79mm = mechanically marginal). materials.yaml: muntz_yellow for the 4 yellow
  tip gears [[harmonic-analyzer-project]].

**The 62.2 reading forces SIX geometric impossibilities** (engineering signal it's too
small): (1) cam lobe through tooth roots, (2) 0.79mm T006 tip journal, (3) crank
pedestal derived +55 vs photo +122 (~67mm inboard), (4) alignment-pinion disengage
pose impossible (negative sqrt), (5) pivot-block straddle, (6) pinion Ø22.4 drum can't
thread the 12.56mm gap between rocker-support frustum (x-28.45) and rescaled 64T
(x-15.89). Each "fix" got more fictional. I recommended revisiting 62.2; user instead
chose **"remove pinion completely will be reworked after."**

So the **alignment pinion is REMOVED** from build_drive_train_assembly.py (drum, 2
straps, 2 blocks, torque shaft, lift rod, lever, handle + all its self-checks +
p2 swing joints). Module imports clean; verify --suite config 14/14. Part scripts
(build_alignment_pinion/pinion_bracket/etc.) stay on disk for the rework.

2026-06-19: **Phase 3 DONE + GREEN + LANDED on main** (HEAD fde40f2). Full doit
rebuild of all 20 cone configs + cylinder gear + cam/rod + drive-train (no pinion)
+ output/frame/top; muntz_yellow applied; verify all suites pass (static/truth/
config + isolation/motion/engagement live, 88 gates). Render diff vs v0.2.0 shown
(9 changed parts, all drive-train + dependents: cone-gear stack, cylinder-gear,
connecting-rod, crank-drive-gear, crank-pinion, cone-gear-shaft, transgear-removable,
channel-spring-installed, measuring-stick; frame/platen/pen/summing UNCHANGED).
NO release cut (user asked only to run the diff + show renders).

Throw-scaling fork resolved: the channel was still built for cam throw 5.08 while
the re-anchor scaled it to 3.06 — user chose "scale throw to 3.06". The only
fallout was build_channel_assembly._assert_plate_threading using a RIGID-spring
model (bottom eye hung off the moving top eye) that only matched at the design
pose; fixed by anchoring bottom_eye_y = PLATE_EYE_Y (the real parametric spring is
hooked at the fixed plate hole — see [[parametric-springs]]), restoring pose-
independent design margins + a real stretch guard. No plate/pen recalibration, no
baseline shift — the "substantial re-tune" collapsed to a one-function fix.

**Of the 6 forced impossibilities, only the pinion ones (4,6) drove a real change
(pinion removed); the rest did NOT block the green build** — cam/rod cleared once
the channel used the 3.06 throw, and the marginal journals/pedestal passed the
gates. So the 62.2 reading, while LOW-conf, is buildable.

LANDING NOTE: while this work was local, **PR #12 "Fix #8" (sketch-inference
suppression — replaced the channel bushing/spring seed+LocalLinearPattern with
explicit per-channel placement because the pattern flipped the bushing bank to +Z
at 20 channels) merged to origin/main** and conflicted with the re-anchor in
build_channel_assembly.py / _common.py / build_measuring_stick.py. User chose
**"Revert main"**: reverted PR#12 (revert commit, kept in history), then replayed
the 18 re-anchor commits on top → tree byte-for-byte == validated green build, no
rebuild needed. **Fix #8 is therefore UNDONE on main and must be re-applied on top
of the re-anchored channel script** (revert the revert + re-resolve, or redo the
explicit-bushing-placement change against the 3.06 channel). The seed+pattern
bushing determinism bug it fixed is back until then.

If 62.2 is ever revised, the whole cascade re-propagates from machine.yaml
(config-driven, build scripts auto-rescale).
