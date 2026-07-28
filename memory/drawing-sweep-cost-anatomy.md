---
name: drawing-sweep-cost-anatomy
description: Entity sweeps dominate a part drawing; kind 1 splits three near-equal ways (sweep 7.5s / COM reads 11.2s / _early_bound wrapper binding 7.0s — binding is NOT COM and is the only attackable third), kind 4 is a flat ~21s call; four ways to cut them were measured and all four failed
metadata:
  type: project
---

Measured 2026-07-28 on the live seat, after routing every sweep through the
traced `visible_view_entities` chokepoint (before that, 43.8 min of 193.7 min of
drawing build time sat inside `drawing.build` covered by NO child span).

**The two sweep kinds cost in opposite ways. Do not reason about "a sweep".**

| pick | sweep call | per-entity loop | entities |
|---|---|---|---|
| cone_gear circle (kind 1) | 7.0 s | **18.4 s** | 481 edges |
| crank_drive_gear circle (kind 1) | 8.3 s | **21.1 s** | 577 edges |
| crank_drive_gear tooth (kind 4) | **26.7 s** | 8.5 s | 9 silhouettes |
| spring_hook shank (kind 4) | **20.6 s** | 3.5 s | 6 silhouettes |

Kind 1 returns hundreds of edges cheaply and the classification loop is the
bill. Kind 4 makes SolidWorks derive outline geometry: ~21 s flat, *independent
of how few entities come back*.

**Inside the kind-1 loop the cost splits three near-equal ways** (cone_gear,
481 edges, 27.7 s, each timer bracketing exactly one operation):
sweep 7.5 s, `GetCurve()` 8.8 s (**18.2 ms** each), `_early_bound` 7.0 s
(7.3 ms x2 per edge), `IsCircle()` 2.0 s (4.2 ms), `CircleParams` 0.4 s
(3.4 ms x121).

An earlier version of this note said `GetCurve` was 24.6 ms and "the entire
bill". Wrong, and wrong in the way this file warns about: that timer also
enclosed the `_early_bound` of the returned curve, inflating the call by ~35%.
**Bracket one operation per timer, including the non-COM ones.**

**`_early_bound` is the lead worth pulling.** 7.0 s of 27.7 s, twice per edge
(the IEdge, then the returned ICurve), and it is NOT a COM round trip — it is
local wrapper resolution. It is therefore the only third of this cost
attackable without a different SolidWorks API. Untested: whether the wrapper
lookup memoises per interface. Measure before assuming.

**Four optimisations measured, four refuted (and one still open).**

0. **Memoising the `_early_bound` wrapper lookup.** UNTESTED — the one idea
   below that has not been refuted, and the measurement above says it is worth
   up to 7.0 s of a 27.7 s pick.
1. **Per-view memo of the sweep.** 0% hit rate — an audit of every call site
   found no drawing that sweeps the same view twice (each gear print picks a
   circle off `front` and at most a silhouette off `right`). A cross-call cache
   would also need invalidating on any visibility change, and a stale entity
   list picks the wrong edge SILENTLY.
2. **`IEdge::GetCurveParams2` as a cheap pre-filter** (2.6 ms, 10x cheaper than
   `GetCurve`), paying `GetCurve` only for closed edges. Refuted: a full circle
   does NOT report coincident endpoints — `closed=1` out of 121 circles.
3. **Start-point-radius pre-filter** (the trick `visible_tooth_tip_silhouette`
   uses). Not available to `visible_circle_edge`: sound only for entities
   coaxial with the view origin, and that helper is also called for OFF-AXIS
   holes (adjuster passages, flange hold-downs).
4. **Warming / reordering the kind-4 sweep**, on the theory that ~21 s for 6
   entities is one-time view resolution. Refuted: a second identical sweep on
   the same view in the same session measured 21.2 s against the first's 20.8 s.
   It recomputes every call.

**What is left.** Kind 4's only lever is calling it FEWER times — a
drawing-design question (does this print need a tooth-tip silhouette at all?),
not a helper-level one. Worth raising when the GD&T callouts get cut.

**Why:** the standing rule is that a drawing over 1 min signals something worth
investigating, and for the gear/spring prints the answer is the sweep, not the
recipe. See [[drawing-isolation-cost]] for the *assembly* drawing equivalent
(component isolation, a different loop) and [[drawing-fleet-timings-drift]] for
why a large total is not automatically a defect.

**How to apply:** read `curve_s`/`classify_s`/`params_s` and the child
`drawing.visible_entity_scan` span (`components`/`entities`/`entity_kind`) off
the span line before optimising — they say which of the four costs you are
looking at. Related: [[drawing-recipe-com-pitfalls]],
[[load-bearing-claims-need-a-repro]].
