---
name: fix-relations-last-resort
description: "Pedro's CAD directive — never anchor sketches with \"fix\" relations; use semantic relations + driving dims; fix only for justified reference geometry"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

Pedro directed (2026-06-12) that ALL `fix` sketch relations in CAD build scripts be replaced with semantic relations (coincident, collinear, merge, distance dims tied to the origin/features), not just the circle pattern.

**ESCALATED (2026-06-26):** Pedro then directed removing **ALL fix AND lock constraints everywhere, parts and assemblies — no carve-outs**. This OVERRIDES the equation-driven-gear-gap exception below: those gap sketches are now left intentionally under-defined (geometry is pinned by the equation curves, not the solver). Scope of that sweep, all done:
- Parts: removed the `fix` sketch-escalation path entirely (`_common.ensure_fully_defined` no longer takes `fix_entities`/`allow_fix_escalation`); gear-gap callers (`_gear.cut_tooth_gap`, `build_cone_gear`, `build_transgear_removable`) just warn + skip the assert.
- Assemblies: removed component grounding (`place_component`/`place_components_batch` no longer take `ground`; no `FixComponent`), the `lock_mate` helper + all its calls, `lock_rotation` on mates, and the direct `fix_component` calls (paper-drive chain links, harmonic top-level subassemblies).
- The SolidWorks **auto-fix of each assembly's first inserted component** remains (it's a SW default, not a script-applied constraint — would need explicit `UnfixComponent` to remove).
- Accepted consequence (Pedro confirmed): `assert_components_fully_defined` / `verify:soundness` DOF gates now fail loud on the free DOF this introduces; restoring definition would mean replacing grounded poses + lock/keying mates with explicit datum/kinematic mates (not done — not requested). The underlying SolidworksMCP-python adapter primitives (`fix_component`, `lock_rotation`, mate_type `lock`) were left intact — only the harmonic-analyzer's *use* of them was removed.

**Why:** A fix relation nails an entity in absolute space — it hides why geometry is positioned where it is, breaks parametric intent (upstream dimension changes don't propagate), masks under-defined sketches (sketch turns black without real relationships), and makes models harder to edit predictably. The same reasoning extends to assembly fixes/locks.

**How to apply:** When authoring sketches in [[harmonic-analyzer-project]], fully define via real relations + dimensions tied to the origin or other features. Do NOT add `fix` sketch relations, `ground=`/`FixComponent`, `lock_mate`, or `lock_rotation` — they're gone and should stay gone unless Pedro re-authorizes. Migration plan (parts): point-addressability in SolidworksMCP-python (suffix refs like `Circle_1.center`, reserved `origin`) + `_common.py` semantic rewrite.
