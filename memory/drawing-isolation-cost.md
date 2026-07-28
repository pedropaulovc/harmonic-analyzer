---
name: drawing-isolation-cost
description: Component isolation is the dominant cost of an assembly drawing (~35s/view, 9 views = 54% of drive-train's 585s); a cross-view identity cache keyed on the RAW IDrawingComponent::Name does NOT work (Name carries the view) — a view-stripped key is untested, not ruled out
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

Per view: ~80 leaves, **~20 s resolving identities** (the `.Component` +
`GetPathName` PAIR, ~250 ms together) and **~15 s writing `Visible`** (~190 ms
per write). Both figures also exclude the separate `Name` read, which the timed
region does not cover.

**Do not turn those into a per-call price.** They are a pair and a write, not
two samples of one number. Individually-instrumented calls, measured
2026-07-28 on the same seat (see [[drawing-sweep-cost-anatomy]]), span an order
of magnitude: `IEdge::GetCurve` 24.6 ms, `GetCurveParams2` 2.6 ms,
`ICurve::IsCircle` 3.8 ms, `CircleParams` 3.6 ms. So "a COM read costs ~250 ms"
is wrong by 10–70x; what IS true is that the isolation pair costs ~250 ms and a
`Visible` write ~190 ms. Price a per-component loop from a call actually
instrumented, never from a paired total.

**The obvious cache does not work.** Nine views walk the SAME component tree, so
memoising the path-derived identity looks free. It is not:
`IDrawingComponent::Name` **carries the view**, so the same component is a
different key in every view. Keyed on `Name`, the cache filled to 569 entries
across 9 × 80 lookups instead of saturating at ~80, and the drawing went
586 s → 580 s. A working version needs a view-stripped key
(`name.rsplit("@", 1)[0]`) — UNVERIFIED, since the exact `Name` format was never
captured, and a wrong strip mis-resolves a component's identity and silently
draws the wrong picture. Capture a real `Name` first.

What DOES hold: #440's lazy path — a component whose NAME already matched skips
the `.Component` + `GetPathName` round trips — is the one structural saving
actually landed, and is pinned by a test.

**What is still on the table, with the arithmetic.** Per drawing:
~180 s resolving (9 × ~20 s) + ~135 s writing visibility (9 × ~15 s). A working
cross-view cache leaves only the FIRST view's resolution, so it removes ~160 s —
isolation ~315 s → ~155 s, or ~27% off a 585 s drawing. `visible_s` is not
cacheable at all, so ~135 s is the floor for this approach. (An earlier version
of this file said "~96 s"; that was simply wrong arithmetic.)

**Why:** the standing rule is that a drawing over 1 min signals something worth
investigating. On THIS drawing the answer was isolation, not the recipe. Do not
read that as a universal — [[drawing-fleet-timings-drift]] makes the opposite
point, that a large assembly-drawing total can be legitimate (drive-train has
seven sheets), and one drawing is not a rule. The transferable part is that per-component
COM loops are where assembly-drawing time goes — but cost them from an
instrumented call, not from the paired figures above.

**How to apply:** read the span attributes before optimising
(`rg isolate_balloon_components <log>`); they name which half to attack. The
`resolve_s` / `visible_s` attributes arrive with #446 — a build from before it
has only the bare `drawing.isolate_balloon_components` duration. Related:
[[drawing-fleet-cost-profile]], [[drawing-fleet-timings-drift]],
[[autoballoon-density-crossings]], [[drawing-recipe-com-pitfalls]].
