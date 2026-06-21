---
name: ch30-similarity-metric-saturated
description: Why ch30 render-vs-photo part-param tuning is metric-saturated — IoU is align-invariant to size, RMS is flat-gray noise; geometry already matches
metadata:
  type: project
---

The ch30 render-vs-photo similarity loop (`comparisons/tools/{measure,search_camera,
tune_align,render_offline}.py`) is **metric-saturated for part-geometry changes** as of
2026-06-21. After the gooseneck slide-down (the one clearly-wrong-vs-photo feature),
every diagnostic shows the model already matches the ch30 plates, and neither score can
register a geometry refinement.

**Why the metrics can't see geometry:**
- `measure.py` IoU is computed **after a per-pair 2D align (scale + dx + dy)** — so it is
  blind to any *global size* change. A height-only edit (the 320mm gooseneck) scored
  neutral *by construction* (IoU 0.495→0.497). Only SHAPE/proportion/feature-presence
  changes can move it.
- The render is a **single flat-gray monolithic STL** (`render_offline.model_paths` → mono
  `cad/out/stl/harmonic-analyzer.STL`; user chose this for speed over per-part STL+boxes).
  So RMS (`composite.score_pair`) is dominated by uniform-color mismatch, not geometry — it
  even *rose* (71.3→74.6) when geometry got more correct.
- `search_camera` compensates residual proportion error with **focal length (converged
  74–165mm vs the true ~100mm lens)** — a sign remaining residuals are perspective/metric,
  not part errors.

**Evidence geometry already matches:** vertical bright-mass centroids ref-vs-render within
±0.05 across all 8 views; aspect ratio front 2.5% off, **sides near-perfect (0.98–0.99)**;
the only "too wide" reads are oblique views (7–13%) = camera-azimuth artifact, geometrically
inconsistent with a single part-dim error. (Quick re-check tools: `/tmp/aspect.py`,
`/tmp/centroid.py` patterns — bbox aspect + bright-mass quartiles.)

**Decision (user, 2026-06-21): accept current state, stop the loop.** The gooseneck was the
main faithful-geometry win; scores are at the metric's practical floor. To make part tuning
score-meaningful again would require **upgrading the metric to a colored/per-part render**
(reverses the monolith speed choice) so RMS becomes a real geometry+appearance signal — NOT
done, offered and declined. Branch: `claude/similarity-part-tuning` (no PR/automerge).

Lean loop established this session: bypass verify; `doit build_bare`; `export_models.py
--stl-only` (~27s, mono STL only); `render_offline.py`; `measure.py`. Any bbox-changing
geometry edit REQUIRES re-running `tune_align` (stale align tanks both scores). See
[[oblique-views-break-on-axis-occlusion]], [[comparison-camera-refinement]],
[[harmonic-analyzer-project]].
