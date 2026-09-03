"""Topology helpers shared by the curated gear drawings.

Gear end views contain many closely spaced tooth edges.  A sheet-coordinate
pick at the bore's 12 o'clock point can therefore select a tooth silhouette
instead of the bore itself.  Resolve the circular model edge by its exact
radius and pass that entity to the drawing annotation helpers.
"""

from __future__ import annotations

import math
import time
from typing import Any

import _telemetry
from _common import _early_bound
from _drawing_common import visible_view_entities
from solidworks_mcp.adapters import sw_type_info as _sw_type_info


def _span_attrs(**attributes: float) -> None:
    """Attach aggregate scan counts to the CURRENT span.

    ``@traced`` owns the span, so there is no handle to set attributes on --
    reach for the active one. A no-op when nothing is recording, so callers
    never guard.
    """
    span = _telemetry.trace.get_current_span()
    for key, value in attributes.items():
        span.set_attribute(key, value)


@_telemetry.traced("drawing.pick_circle_edge")
def visible_circle_edge(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible circular model edge matching ``diameter_mm``.

    The most expensive step in a gear drawing, and it splits three ways, not
    one. Measured on cone_gear (481 visible edges, 121 of them circles), 27.7 s,
    every timer bracketing exactly one operation:

    ===================== ======== ==============
    phase                     time      per edge
    ===================== ======== ==============
    sweep (child span)       7.5 s  one COM call
    ``GetCurve()``           8.8 s       18.2 ms
    ``_early_bound`` (x2)    7.0 s   7.3 ms each
    ``IsCircle()``           2.0 s        4.2 ms
    ``CircleParams``         0.4 s   3.4 ms x121
    ===================== ======== ==============

    An earlier version of this table said ``GetCurve`` cost 24.6 ms and was "the
    entire bill". It was not: that timer also enclosed the ``_early_bound`` of
    the returned curve, inflating the call it was supposed to isolate by ~35%
    (Codex P2) -- the same paired-measurement error this table exists to warn
    about, made one layer down. The corrected split is three near-equal thirds:
    sweep 7.5 s, COM reads 11.2 s, wrapper binding 7.0 s.

    **``_early_bound`` is the interesting one.** It is 7.0 s of a 27.7 s pick and
    it is NOT a COM round trip -- it is local wrapper resolution, run twice per
    edge (once for the IEdge, once for the returned ICurve). Unlike the sweep and
    unlike ``GetCurve``, it is ordinary Python and therefore the only third of
    this cost that can be attacked without a different SolidWorks API. Nothing
    here has tried yet; measure a memoised wrapper lookup before assuming it.

    The COM calls themselves resisted two removals, both measured, so do not
    re-walk them:

    * **Pre-filter on ``IEdge::GetCurveParams2``** (2.6 ms, 10x cheaper) and pay
      ``GetCurve`` only for closed edges. Refuted: a full circle does NOT report
      coincident endpoints -- the probe flagged ``closed=1`` out of 121 circles.
    * **Drop ``IsCircle()``** and read ``CircleParams`` defensively. Worth 1.8 s
      of 25.3 s; not worth losing the explicit type check.

    A start-point-radius pre-filter (the trick
    :func:`visible_tooth_tip_silhouette` uses) is NOT available here: that one
    is sound only because a gear's tooth tips are coaxial with the view origin,
    and this helper is also called for OFF-AXIS holes (adjuster passages, flange
    hold-downs) whose start points sit nowhere near their own radius.

    The counts go on the SPAN's own attributes, not just a span event: the
    profiling workflow reads span lines, where an event's attributes do not
    appear. The per-edge work stays inside ONE span rather than flooding the
    trace with leaves.

    Ties break on the circle's CENTRE, never on enumeration order --
    ``GetVisibleEntities2`` documents no ordering, and a part with coaxial or
    mirrored circles of one radius (every through-bore has two, one per face)
    would otherwise return a different edge run to run. See
    :func:`_drawing_common._spread_balloons` for what that non-determinism cost.
    The centre comes out of ``CircleParams`` this loop already reads, so the
    guarantee is free.
    """
    candidates: list[tuple[float, tuple[float, float, float], Any]] = []
    raw_edges = visible_view_entities(view, 1, label=f"circle dia {diameter_mm:g}")
    bind_s = 0.0
    curve_s = 0.0
    classify_s = 0.0
    params_s = 0.0
    for edge in raw_edges:
        # Each timer brackets ONE thing. _early_bound is wrapper resolution, not
        # a COM round trip, and folding it into the call it precedes is how a
        # per-call price gets overstated -- the exact mistake this file's table
        # was written to stop people making.
        bind_started = time.perf_counter()
        edge = _early_bound(edge, "IEdge")
        edge_bound = time.perf_counter()
        raw_curve = edge.GetCurve()
        got_curve = time.perf_counter()
        curve = _early_bound(raw_curve, "ICurve")
        curve_bound = time.perf_counter()
        is_circle = curve.IsCircle()
        classified = time.perf_counter()
        bind_s += (edge_bound - bind_started) + (curve_bound - got_curve)
        curve_s += got_curve - edge_bound
        classify_s += classified - curve_bound
        if not is_circle:
            continue
        # CircleParams = (centre xyz, axis xyz, radius).
        params = curve.CircleParams
        params_s += time.perf_counter() - classified
        radius_mm = float(params[6]) * 1000.0
        centre = (float(params[0]), float(params[1]), float(params[2]))
        candidates.append((radius_mm, centre, edge))

    # Three COM round trips per edge, priced SEPARATELY. The sweep that produced
    # these edges is its own child span, so without this split the remainder is
    # one opaque number and any optimisation here would be guesswork about which
    # of the three calls to attack.
    _span_attrs(edges=len(raw_edges), circles=len(candidates),
                diameter_mm=diameter_mm, curve_s=round(curve_s, 3),
                classify_s=round(classify_s, 3), params_s=round(params_s, 3),
                bind_s=round(bind_s, 3))
    target_radius = diameter_mm / 2.0
    if not candidates:
        raise RuntimeError("drawing view has no visible circular model edge")
    radius_mm, _centre, edge = min(
        candidates, key=lambda item: (abs(item[0] - target_radius), item[1])
    )
    if abs(radius_mm - target_radius) > 0.01:
        raise RuntimeError(
            f"no visible circle matches radius {target_radius:.4f} mm; "
            f"nearest is {radius_mm:.4f} mm"
        )
    return edge


@_telemetry.traced("drawing.pick_tooth_silhouette")
def visible_tooth_tip_silhouette(
    adapter: Any, view: Any, outside_diameter_mm: float
) -> Any:
    """Return the upper side-view silhouette at the specified tooth-tip radius.

    Costed the OPPOSITE way round from its circle-edge sibling: here the loop is
    nearly free and the single sweep is the bill. Measured on crank_drive_gear,
    35.2 s total = **26.7 s inside one ``GetVisibleEntities2(..., 4)`` call**
    that returned NINE silhouettes, plus 8.5 s of endpoint reads. Silhouette
    kind makes SolidWorks derive the view's outline geometry, and the price is
    flat in the result count -- spring_hook pays 20.6 s for SIX.

    That call is not warm-up, and cannot be amortised: a second identical sweep
    on the same view in the same session measured 21.2 s against the first
    sweep's 20.8 s. There is nothing to reorder behind and nothing to cache --
    it recomputes every time. The only lever left is calling it FEWER times,
    which is a drawing-design question (does this print need a tooth-tip
    silhouette at all?), not something this helper can decide.

    Like its circle-edge sibling, the aggregate scan counts go on the span's own
    attributes so the cost is attributable from the span line alone, and ties
    break on geometry rather than on ``GetVisibleEntities2``'s undocumented
    order: a gear's tooth tips are periodic, so several silhouettes share one
    ``mean_y`` by construction and picking among them by enumeration index makes
    the drawing irreproducible.
    """
    target_radius_m = outside_diameter_mm / 2000.0
    candidates: list[tuple[tuple[float, ...], Any]] = []
    raw_silhouettes = visible_view_entities(
        view, 4, label=f"tooth tip od {outside_diameter_mm:g}"
    )
    for raw_silhouette in raw_silhouettes:
        silhouette = _early_bound(raw_silhouette, "ISilhouetteEdge")
        start = adapter._attempt(lambda s=silhouette: s.GetStartPoint())
        end = adapter._attempt(lambda s=silhouette: s.GetEndPoint())
        if start is None or end is None:
            continue
        start_xyz = adapter._get_attr_or_call(start, "ArrayData")
        end_xyz = adapter._get_attr_or_call(end, "ArrayData")
        if not start_xyz or not end_xyz:
            continue
        start_radius = math.hypot(float(start_xyz[0]), float(start_xyz[1]))
        end_radius = math.hypot(float(end_xyz[0]), float(end_xyz[1]))
        if abs(start_radius - target_radius_m) > 0.00001:
            continue
        if abs(end_radius - target_radius_m) > 0.00001:
            continue
        mean_y = (float(start_xyz[1]) + float(end_xyz[1])) / 2.0
        # mean_y first (the actual selection criterion), then the endpoints
        # verbatim so equal-height silhouettes order by geometry.
        key = (mean_y,) + tuple(float(v) for v in start_xyz[:3]) + tuple(
            float(v) for v in end_xyz[:3]
        )
        candidates.append((key, silhouette))

    # scanned, not just matched: the COM cost is per silhouette PROCESSED (each
    # costs an early-bind plus two endpoint reads), so two views with the same
    # match count but wildly different scan counts must not look alike.
    _span_attrs(silhouettes=len(raw_silhouettes), matched=len(candidates),
                outside_diameter_mm=outside_diameter_mm)
    if not candidates:
        raise RuntimeError(
            "no visible tooth-tip silhouette matches radius "
            f"{target_radius_m * 1000.0:.4f} mm"
        )
    return max(candidates, key=lambda candidate: candidate[0])[1]


@_telemetry.traced("drawing.section_cut_face_only", label_param="label")
def show_only_cut_face(adapter: Any, section: Any, *, label: str) -> None:
    """Make a section view display ONLY the face the cutting plane cuts.

    A gear's projected side view is a black band: every tooth edge lands
    within the OD, ~480 lines over 62 mm on the 120T gears, so the bore's
    hidden lines and the face width are unreadable (machinist review,
    2026-09-02, five sheets).  A section through the axis is the conventional
    gear side view, but SolidWorks still projects the half of the tooth ring
    BEHIND the cutting plane into it -- the same band.  ``IDrSection::
    SetDisplayOnlySurfaceCut`` leaves just the hatched cut face: the blank's
    width, the bore channel and (cylinder gear) the cam step, which is what a
    machinist dimensions.  First fleet use of that flag; the setter returns
    nothing, so the state is read back and a refusal fails loud.
    """
    view = _sw_type_info.early_bound_or_flag(section, "IView", "GetSection")
    dr_section = view.GetSection()
    if dr_section is None:
        raise RuntimeError(f"section view has no section definition ({label})")
    dr_section = _sw_type_info.early_bound_or_flag(
        dr_section,
        "IDrSection",
        "SetDisplayOnlySurfaceCut",
        "GetDisplayOnlySurfaceCut",
    )
    dr_section.SetDisplayOnlySurfaceCut(True)
    adapter.currentModel.EditRebuild3()
    if not bool(dr_section.GetDisplayOnlySurfaceCut()):
        raise RuntimeError(
            f"section view did not accept display-only-cut-face ({label})"
        )
