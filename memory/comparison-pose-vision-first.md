---
name: comparison-pose-vision-first
description: Pose-fit comparison pairs by eye first; run IoU/RMS optimizers only for the final 2D polish once the 3D pose is nearly exact
metadata:
  type: feedback
---

When matching CAD renders to book/photo references (comparisons/), iterate the
3D camera (az/el/roll/target_mm/zoom) **by vision**: render, read the
`_blend.jpg` overlay, correct the manifest numbers, re-render. Only invoke the
numeric optimizers (`tune_align.py` silhouette-IoU align fit, RMS scoring as a
guide) **when the pose is within millimetres of final**.

**Why:** the IoU/RMS surface is full of wrong-but-locally-optimal alignments
while the orientation is still off — the optimizer happily fits a mis-posed
silhouette, and the score stops being a trustworthy signal. Vision reads the
*direction* of the error (which way to move az/el/target), which the scalar
score cannot.

**How to apply:** blend overlay → adjust az (lateral part order), el
(vertical convergence/foreshortening), roll (horizon tilt), target_mm/zoom
(framing) → re-render `--only <id>`; repeat. Then `tune_align.py --only <id>
--write` for scale/dx/dy, then freeze. See [[comparison-camera-refinement]],
[[oblique-views-break-on-axis-occlusion]].
