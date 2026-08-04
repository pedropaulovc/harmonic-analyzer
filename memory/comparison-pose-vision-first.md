---
name: comparison-pose-vision-first
description: Pose-fit comparison pairs by eye — the 3D camera IS the fit; the 2D align optimizer is gone (camera_frame ignores align)
metadata:
  type: feedback
---

When matching CAD renders to book/photo references (cad/comparisons/), iterate the
3D camera (az/el/roll/target_mm/zoom) **by vision**: render, read the
`_blend.jpg` overlay, correct the manifest numbers, re-render. There is no
second, numeric stage any more — RMS scoring in `scores.json` is a guide to
read, never a thing to optimize against.

**Why:** the IoU/RMS surface is full of wrong-but-locally-optimal alignments
while the orientation is still off — an optimizer happily fits a mis-posed
silhouette, and the score stops being a trustworthy signal. Vision reads the
*direction* of the error (which way to move az/el/target), which the scalar
score cannot.

**How to apply:** blend overlay → adjust az (lateral part order), el
(vertical convergence/foreshortening), roll (horizon tilt), target_mm/zoom
(framing) → re-render `--only <id>`; repeat until the blend reads right, then
stop. See [[comparison-camera-refinement]],
[[oblique-views-break-on-axis-occlusion]].

**The 2D align is DEAD and `tune_align.py` is DELETED (2026-07-24, PR #411).**
Every pair now registers as `camera_frame` (`composite.blender_registration`
returns it whenever the camera carries a concrete `target_mm`), and
`_fitted_render` returns BEFORE reading `align` on that path — so
scale/dx/dy change nothing at render time. `test_pose_manifest.py` pins both
directions: every shipped pair must resolve to `camera_frame`, and a
`camera_frame` pair must carry a neutral align. Four pairs were found holding
tuned aligns from their pre-re-fit lives; recompositing after zeroing
reproduced their scores exactly, proving the values dead.

*Why the tool went, as a caution about optimizers here:* on dense macro refs
(bright close-up content on a dark background — the ch11/ch12/ch17-style book
close-ups) silhouette IoU rewarded zooming the render into the ref's content
mass. The optimizer railed toward its scale bound (1.85) and reported an
*improved* IoU (0.35→0.75) for a visually absurd fit; the 2026-07 book-pairs
round shipped scales 1.6–1.84 on 9 pairs that way, caught only by a human
opening the gallery. If a numeric 2D fit is ever reintroduced, its output is
UNVERIFIED until someone eyeballs the blend it produced.
