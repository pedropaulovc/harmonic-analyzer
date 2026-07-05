---
name: oblique-views-break-on-axis-occlusion
description: When a part sits on a column/axis line, front+side elevations both occlude it — use a 3/4 / oblique view to measure its free end
metadata:
  type: feedback
---

A part placed **on the same line as a structural member** (e.g. the gooseneck
counter-spring post on the east column line, machine x 197, z 0) is optically
fused with that member in **both** the front and side elevations — its lower
end can't be read from either. The user's prompt "use other photos … video
keyframes, other angles" was the fix: a **three-quarter / oblique view**
separates them.

**Why:** rotating the camera about the vertical axis moves the on-axis part
off the member's silhouette, exposing its true endpoint against the
background.

**How to apply:**
- Look through the reference imagery for oblique full-machine shots
  (`ch07-p001-img17/18` ≈ az −150, el 10 was the winner). (The curation catalog
  `references/curation/batches/*.json` referenced here is not present in the repo.)
- **Vertical scale** at low elevation (~10°) is near-true: calibrate on the
  top-frame ring height (41 mm = plate top 1040.7 → underside 999.7).
- **Cross-check scale** with a vertical cylinder's silhouette width — it equals
  the true diameter regardless of azimuth (post Ø16 → 10 px confirmed
  1.58 mm/px). Horizontal extents are azimuth-foreshortened; don't trust them.
- Result: gooseneck post tip at machine y ≈ 880, ~120 below the plate (NOT the
  ~40 first guessed from the occluded front view). See [[harmonic-analyzer-project]],
  `build_gooseneck.py`, `cad/config/dimensions.yaml` (book ch. 19).
