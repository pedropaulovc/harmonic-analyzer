---
name: ch30-p002-refit-roadmap
description: "ch30 p002 front-view refit sequence: wheel group +10.7 done (PR #340); reducer group down 42.9 mm next (pose-studio deltas); then platen/rack lowered AND resized smaller"
metadata:
  type: project
---

Pedro is refitting the model against the ch30 p002 front photo in stages
(2026-07-18), each with meshprobe before/after renders vs the photo:

1. **DONE (PR #340):** magnifier wheel group (wheel, wheel-bar, column-clamps,
   clamp-screws) raised 565.0 → 575.7 (+10.7).
2. **NEXT — reducer group down 42.9 mm:** pose-studio deltas in
   `cad/comparisons/findings/harmonic_analyzer--ch30-p002-img01_deltas.json` move
   `support-bar` + `rack-pinion` + `transgear-knob-shaft` + `transgear-removable`
   as ONE rigid group by translate_mm [0.129, −42.891, −4.103] (machine mm; fit
   vs release v0.20.0). y −42.9 is the intended lowering (support-bar 338.5 →
   ≈295.6); z −4.1 needs a confirm (intended vs drag leakage); x is noise.
   Cascades: chain span to the crank T12 sprocket (Belt/Chain feature + link
   count, [[chain-component-pattern]]), rack-pinion ↔ platen mesh.
3. **LATER:** platen/rack lowered AND resized smaller.

**How to apply:** in the reducer PR, keep the rack-pinion↔platen mesh sound for
the gates but treat its exact re-anchoring as provisional — step 3 owns the
final platen geometry. Fit deltas predate the wheel move but the groups are
disjoint, so they stay valid.
