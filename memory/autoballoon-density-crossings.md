---
name: autoballoon-density-crossings
description: AutoBalloon5 crosses leaders at ~32 balloons/view under BOTH of the two layouts tried (its native circular layout, 5 crossings, and our _spread_balloons re-ring, 6) — untested: multiple rings, routed leaders; per-view component isolation is what keeps a balloon sheet clean today
metadata:
  type: project
---

Measured 2026-07-28 on drive-train, same commit, same cached assembly, ~32
balloons on one un-isolated full-assembly view:

| balloon placement | leader crossings |
|---|---|
| `AutoBalloon5` square layout + our `_spread_balloons` re-ring | **6** |
| `AutoBalloon5` native circular (`swDetailingBalloonLayout_Circle` = 2) | **5** |

Both cross at this density, and switching between them did not rescue it (6 → 5
is not a fix). That is evidence that **density is a variable neither of these two
placements handles** — NOT proof that no placement could. Untested: multiple
concentric rings, jogged/routed leaders, splitting one view's balloons across
several views, and AutoBalloon's four edge layouts (top/bottom/left/right). If
you try one, record the count here.

The crossed pairs were checked against `_spread_balloons`'s own
non-crossing argument ("balloons placed in their attachments' angular order
cannot cross") and were in the CORRECT order. The argument cannot hold at this
density: 32 balloons do not fit on the ring at the minimum gap, so
`_push_apart_on_ring` falls back to even spacing, which its own docstring
records as the placement that hauls leaders across the model.

`draw_channel_assembly.py` records a DIFFERENT native-layout defect
(that `f375557a` replaced hand-pinned balloons with `layout=2` on the premise
that "their order follows the view ring", and it does not). This run does NOT
reproduce that one: the observation above is that the crossed pairs WERE in the
correct attachment order, which is evidence that order-preserving placement
still crosses at this density — it says nothing about whether `layout=2`
followed ring order here, because ring order was never read back. What both
assemblies now share is only the outcome: the native layout crossed.

Two related facts measured at the same time:

- **A hidden-line edge is not a shown entity.** `AutoBalloon5` balloons what a
  view SHOWS. With sheet 4's two views in hidden-lines-visible and nothing
  isolated, its AutoBalloon calls returned NO new items — coverage stuck at
  26/32, six buried families unreachable. Do not expect hidden lines to reach a
  concealed component; isolate it.
- **`AutoBalloon5` is nondeterministic about WHICH view balloons a given item**
  (observed: an item moved between views across two runs of an identical
  assembly; also recorded independently in `draw_channel_assembly.py`). So a
  drawing built on un-isolated AutoBalloon views cannot be made fully
  deterministic from the recipe side.

**Why:** #442 tried to replace ~200 s of hand-placed drive-train balloons with
AutoBalloon on un-isolated views. It could not pass `check_drawing_layout`, and
that structural failure — not any timing — is why it was parked.

The run also showed 277 s against 188 s, but do NOT read that as a speedup from
deleting isolation. It is a single A/B pair, which
[[drawing-fleet-timings-drift]] says proves no performance effect without
repeated counterbalanced runs, and it does not even survive internal
consistency: [[drawing-isolation-cost]] measures isolation ALONE at ~315 s,
already more than the 277 s "before". One of the two numbers is measuring
something other than what its label says, and neither has been re-run.

**How to apply:** keep each identification view isolated to a handful of
families — that is what makes a balloon sheet clean, and it is a code-write-time
view configuration, not a runtime placement tweak. Budget for it:
[[drawing-isolation-cost]]. Related: [[drawing-recipe-com-pitfalls]],
[[drawing-text-leader-style]].
