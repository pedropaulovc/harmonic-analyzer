---
name: rocker-arms-fan-in-plan
description: "Photos show the 20 rocker arms RADIATING in plan from the pedestal pivot (tight stack at the pivot, 140 mm spread at the tips); the model stacks them parallel at the 7.0565 drum pitch -- the top residual geometry delta after the 2026-09 photo pass, deferred because it re-architects the channel's mate contracts"
metadata:
  type: project
---

Evidence (2026-09-01 photo-fidelity pass, PR #650): ch14 p.26 (`ch14_images/page001_img01`,
the "140 mm" callout across the arm tips) and p.27 (`page002_img01`, the bank from the side)
plus the ch30 rear-quarter plates p005/p007 all show the rocker arms converging to a
~50-70 mm stack at the pivot block and spreading to ~140 mm (7.06 pitch) at the rod-pin
tips. The model places every arm parallel at the drum pitch on the common Z pivot shaft
(`build_channel_assembly`: "rocker/lever concentric on the shaft OD"), so from any
rear/side/top view the bank reads as one grey slab instead of a fan.

**Why deferred:** a per-arm plan yaw of ~1-1.6 deg/arm breaks the concentric-on-shaft
pivot mate (a yawed arm needs an axis-to-point + angle pair), moves the amplitude bar's
Z anchor off the rocker mid-plane, twists the rod pin joint, and changes the pinned
9-mate CopyWithMates2 slice contract (`_cwm.py`) for 19 copies, with verify:kinematics
and the interference contracts re-derived on top. Multi-day, high gate risk.

**How to apply:** if the fan is ever authored, define theta_j so the rod-pin holes at
r = ROD_HOLE_X (127.37) land on the cylinder-gear pitch 7.0565 while the pivot stack
sits at the bushing pitch; fix the amplitude bars' Z to the lever row; keep the rods
plumb. Expect to rewrite the seed-channel mates and the copy contract together.
