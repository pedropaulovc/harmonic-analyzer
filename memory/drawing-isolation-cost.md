---
name: drawing-isolation-cost
description: Component isolation is the dominant cost of an assembly drawing (~35s/view, 9 views = 54% of drive-train's 585s) and the obvious cross-view identity cache does NOT work — Name carries the view
metadata:
  type: project
---

Measured 2026-07-28 on the drive-train assembly drawing (585 s total, hand-placed
balloon path), via the `resolve_s`/`visible_s` attributes now on the
`drawing.isolate_balloon_components` span:

| span | count | each | total |
|---|---|---|---|
| `isolate_balloon_components` | 9 | 30–41 s | **~315 s (54%)** |
| `grouped_component_balloons` | 2 | 41–86 s | ~127 s |
| `finalize` | 1 | 58 s | 58 s |

Per view: ~80 leaves, **~20 s resolving identities** (`.Component` +
`GetPathName`, ~250 ms a pair) and **~15 s writing `Visible`** (~190 ms each).
So a COM property read on this seat is ~200–250 ms — assume that, not 1–5 ms,
when costing any per-component loop.

**The obvious cache does not work.** Nine views walk the SAME component tree, so
memoising the path-derived identity looks free. It is not:
`IDrawingComponent::Name` **carries the view**, so the same component is a
different key in every view. Keyed on `Name`, the cache filled to 569 entries
across 9 × 80 lookups instead of saturating at ~80, and the drawing went
586 s → 580 s. A working version needs a view-stripped key
(`name.rsplit("@", 1)[0]`) — UNVERIFIED, since the exact `Name` format was never
captured, and a wrong strip mis-resolves a component's identity and silently
draws the wrong picture. Capture a real `Name` first.

What DOES hold: #440's lazy path — a component whose NAME already matched must
never pay the `.Component` + `GetPathName` round trips — is the one structural
saving actually available, and is pinned by a test.

**Why:** the standing rule is that a drawing over 1 min signals something wrong.
For every assembly drawing the answer is isolation, not the recipe, and the
per-COM-call cost above is what makes it so. Ceiling on optimising isolation
without changing approach is ~96 s of 580 s; `visible_s` is not cacheable at all.

**How to apply:** read the span attributes before optimising
(`rg isolate_balloon_components <log>`); they name which half to attack. Related:
[[drawing-fleet-cost-profile]], [[autoballoon-density-crossings]],
[[drawing-recipe-com-pitfalls]].
