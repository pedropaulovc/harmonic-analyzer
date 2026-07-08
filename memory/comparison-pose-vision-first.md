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

**tune_align output is UNVERIFIED until you eyeball the blend it produced.**
On dense macro refs (bright close-up content on a dark background — the ch11/
ch12/ch17-style book close-ups) silhouette IoU rewards zooming the render into
the ref's content mass: the optimizer rails toward its scale bound (1.85) and
reports an *improved* IoU (0.35→0.75) for a visually absurd fit. The 2026-07
book-pairs round shipped scales 1.6–1.84 on 9 pairs this way — caught only by
a human opening the gallery. Red flags: fitted scale near the search bound, or
any scale ≫1.2 when the render was already framed to match the ref. After
`--write`, ALWAYS re-view `composite/<id>_blend.jpg` (the sbs sheets do NOT use
the align, so they can't catch this); when the render framing was eye-matched
to the ref, neutral `{scale 1, dx 0, dy 0}` beats a railed optimizer fit.
