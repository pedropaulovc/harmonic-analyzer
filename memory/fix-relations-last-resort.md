---
name: fix-relations-last-resort
description: "Pedro's CAD directive — never anchor sketches with \"fix\" relations; use semantic relations + driving dims; fix only for justified reference geometry"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

Pedro directed (2026-06-12) that ALL `fix` sketch relations in CAD build scripts be replaced with semantic relations (coincident, collinear, merge, distance dims tied to the origin/features), not just the circle pattern.

**Why:** A fix relation nails an entity in absolute space — it hides why geometry is positioned where it is, breaks parametric intent (upstream dimension changes don't propagate), masks under-defined sketches (sketch turns black without real relationships), and makes models harder to edit predictably.

**How to apply:** When authoring or migrating sketches in [[harmonic-analyzer-project]], fully define via real relations + dimensions tied to the origin or other features. `fix` is acceptable only for: locking reference geometry / base features that genuinely shouldn't move (e.g. equation-driven curves with no dimension scheme), throwaway layout sketches, or temporary scaffolding while sorting other constraints — and any surviving `fix` in production scripts needs an inline justification comment. Migration plan: point-addressability in SolidworksMCP-python (suffix refs like `Circle_1.center`, reserved `origin`) + `_common.py` semantic rewrite.
