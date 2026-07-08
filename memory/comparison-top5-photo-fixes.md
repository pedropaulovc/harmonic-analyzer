---
name: comparison-top5-photo-fixes
description: "2026-07-08 gallery vision pass: top-5 model-vs-photo fixes (green resample, paper z-fight, painted summing lever/wheel/pen) + the traps found on the way"
metadata:
  type: project
---

2026-07-08 vision pass over all 18 regenerated comparison pairs (PR #209,
branch `photo-match-top5`). The five fixes and the reusable lessons:

1. **`casting_green` was pastel teal.** The palette claimed "sampled from the
   ch30 plates" but carried R=0.13; median patch-sampling the actual plates
   (ch30 p002/p009 frame+base, ch17/ch18 lever) gives R≈0.05·G, B≈0.85·G →
   `(0.03, 0.45, 0.38)`. **How to apply:** when a palette entry claims
   "photo-sampled", re-derive it with PIL median patches before trusting it.
2. **Coplanar faces z-fight in the offline renders.** The platen paper's back
   face landed exactly on the platen front face → every ch30 front view drew
   the paper as torn black/white triangle shards (worse at far/ortho zoom,
   clean in close-ups, so it looks like a "corrupt mesh" but isn't).
   **How to apply:** keep the repo's 0.25 margin rule for FACE-ON-FACE decals
   too (paper, plates, labels) — a 0.25 air gap behind the decal kills it;
   verify by re-render, not by interference gates (0-volume contact passes
   them). See [[solidworks-modeling-pitfalls]].
3. **Summing lever + pen v-block are green-painted, magnifying wheel is
   black-painted** (ch17/ch18/ch24/p.51). Parts relying on bare
   `apply_material` appearance (Gray Cast Iron / Brass) read wrong in the
   gallery; the painted machine parts need explicit `apply_color`.
   `materials.yaml casting_green_parts` is the (doc-only) list — keep it in
   sync.
4. **Pen marker**: blunt 5 mm nose + nickel colour (was 12 mm needle cone,
   brass). Still VERTICAL — the tilt/paper-contact stays a documented
   Appendix C simplification; a real fix means angled v-block bores and a
   pen-frame window rework.
5. **Wheel "8 spokes" was a miscount.** The magnifying wheel HAS 6 spokes
   (verified by point-in-solid parity probing of the STL at r=25..38); the
   wheel-bar + column behind it read as 2 extra spokes in renders. **How to
   apply:** before "fixing" a pattern count seen in a render, probe the STL —
   vertex-angle histograms DON'T work (box spokes have no mid-span vertices).

**Trap: `_common.py` is in every part's recipe digest.** Editing the palette
constants there invalidates the whole fleet (~100 parts) → full rebuild. If
palette tweaks become frequent, move the palette source of truth into
`cad/config/materials.yaml` behind a `_config` accessor (+ `_buildgraph`
mapping) so a colour edit rebuilds only the parts that read it.

Remaining known visual deltas (NOT fixed, next candidates): crank handle is
black with a brass ferrule in ch11 (model: plain dark-oak teardrop);
connecting rods read near-black in plates vs 0.267 gray; nameplate sits flat
on the base deck vs the plinth front bevel in ch26 (+ an unidentified silver
gear rendered on the deck near it — investigate `transgear-removable` spares);
wheel-axle's 35 mm silver flange reads bigger/brighter than the photo hub;
summing lever webbed-casting shape ([[summing-lever-true-geometry]]).
