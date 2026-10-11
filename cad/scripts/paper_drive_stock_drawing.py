"""Model-linked toothspace callout on a stock-form flank.

The flank is named by its model geometry, never by a sheet hit test: farm
run 11 (efe149f9f) hit-tested the projected gauge contact on all three
stock gears and took a neighbouring edge every time -- the rack pinion's
(0.86 mm away), the feed pinion's (0.23 mm) and the knob shaft's (a line or
circle). On a 1:1 or 3:1 tooth the flank, the next flank, the root and the
tip all lie within a hit-test's reach of the contact. So, as main's
assembly drawing names the collar's rear rim (``_collar_rim_candidates``):
list the edges the view draws, keep the one formed edge (neither a line nor
a circle) whose closest point lies within ``CONTACT_TOLERANCE_MM`` of the
contact at the inspected end face, select it by entity with the leader's
landing at the projected contact, and read the landing back.
"""

from __future__ import annotations

import math
from typing import Any, NamedTuple

import _telemetry
from _com import _com_invoke, _early_bound
from _drawing_common import (
    _VIEW_ENTITY_EDGE,
    _assert_leader_lands,
    _select_view_entity,
    model_point_in_view,
    property_link,
    rebuild_drawing,
    visible_view_entities,
)
from paper_drive_stock_inspection import toothspace_gauge_contact_mm
from stock_form_cutter import StockFormProfile


def require_source_control(source: str, expected: str, *, label: str) -> None:
    """Raise unless the part's saved control text is the spec's, line for line.

    SolidWorks stores a custom property's line breaks as CRLF on save (the
    run 20261010T001620278Z rack-pinion SLDPRT's properties stream holds
    ``\\r\\n``), so a reopened source reads back CRLF where the build wrote
    LF. The line break is not the control; every line must still match.
    """
    if source.splitlines() != expected.splitlines():
        raise RuntimeError(
            f"{label}: source control {source!r} differs from the current "
            f"specification {expected!r}"
        )


def _rotate(point: tuple[float, float], angle: float) -> tuple[float, float]:
    c, s = math.cos(angle), math.sin(angle)
    return c * point[0] - s * point[1], s * point[0] + c * point[1]


# How far the flank edge may pass from the contact point. SolidWorks holds
# an equation curve as a fitted spline (paper_drive_stock_native.author_span),
# so this budgets the fit, not the part: a micrometre-class fit is far inside
# 0.01 mm, and each flank end lies over 20x farther from the contact (tested),
# so neither a root-fillet nor a tip edge can qualify.
CONTACT_TOLERANCE_MM = 0.01


class EdgeReading(NamedTuple):
    """One edge the view draws: its closest point to the contact (model mm)
    and whether its curve is a line or a circle."""

    edge: Any
    closest_mm: tuple[float, float, float]
    straight_or_round: bool


def flank_at_contact(
    readings: list[EdgeReading], contact_mm: tuple[float, float, float]
) -> EdgeReading:
    """The one formed edge through the contact; none or several raise,
    naming the nearest edges the view draws."""
    matches = [
        reading
        for reading in readings
        if not reading.straight_or_round
        and math.dist(reading.closest_mm, contact_mm) <= CONTACT_TOLERANCE_MM
    ]
    if len(matches) != 1:
        nearest = sorted(readings, key=lambda r: math.dist(r.closest_mm, contact_mm))[:4]
        listed = "; ".join(
            f"{'line/circle' if r.straight_or_round else 'formed'} "
            f"{math.dist(r.closest_mm, contact_mm):.4f} mm at "
            f"({r.closest_mm[0]:.4f}, {r.closest_mm[1]:.4f}, {r.closest_mm[2]:.4f})"
            for r in nearest
        )
        raise RuntimeError(
            "toothspace callout: expected one formed flank edge within "
            f"{CONTACT_TOLERANCE_MM} mm of the gauge contact "
            f"({contact_mm[0]:.4f}, {contact_mm[1]:.4f}, {contact_mm[2]:.4f}) mm, "
            f"matched {len(matches)} of {len(readings)} drawn edges; nearest: "
            f"{listed or 'none'}"
        )
    return matches[0]


def _drawn_edges(view: Any, contact_mm: tuple[float, float, float]) -> list[EdgeReading]:
    contact_m = tuple(value / 1000.0 for value in contact_mm)
    readings = []
    for edge in visible_view_entities(view, _VIEW_ENTITY_EDGE, label="toothspace flank"):
        closest = tuple(
            float(value)
            for value in (_com_invoke(edge, "IEdge", "GetClosestPointOn", *contact_m) or ())
        )
        curve = _com_invoke(edge, "IEdge", "GetCurve")
        if len(closest) < 3 or curve is None:
            raise RuntimeError(
                f"toothspace callout: a drawn edge read closest point {closest}, curve {curve}"
            )
        readings.append(
            EdgeReading(
                edge=edge,
                closest_mm=(closest[0] * 1e3, closest[1] * 1e3, closest[2] * 1e3),
                straight_or_round=bool(_com_invoke(curve, "ICurve", "IsLine"))
                or bool(_com_invoke(curve, "ICurve", "IsCircle")),
            )
        )
    return readings


def add_toothspace_callout(
    adapter: Any, view: Any, *, profile: StockFormProfile,
    actual_pin_diameter_mm: float, rotate_rad: float, axial_station_mm: float,
    property_name: str, note_xy: tuple[float, float],
) -> Any:
    """One model-linked arrow on the flank at the gauge pin's contact point."""
    label = "toothspace callout"
    contact = toothspace_gauge_contact_mm(profile, actual_pin_diameter_mm)
    x, y = _rotate(contact.flank_point_mm, rotate_rad)
    contact_mm = (x, y, axial_station_mm)
    flank = flank_at_contact(_drawn_edges(view, contact_mm), contact_mm)
    landing = model_point_in_view(
        adapter, view, tuple(value / 1000.0 for value in contact_mm),
        label="toothspace gauge contact",
    )
    _telemetry.info(
        f"{label}: contact ({x:.4f}, {y:.4f}, {axial_station_mm:.4f}) mm -> sheet "
        f"({landing[0]:.5f}, {landing[1]:.5f}); flank edge closest point "
        f"({flank.closest_mm[0]:.4f}, {flank.closest_mm[1]:.4f}, {flank.closest_mm[2]:.4f}) mm"
    )
    draw = adapter.currentModel
    _select_view_entity(adapter, view, "EDGE", None, label=label, entity=flank.edge)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    if selection_manager.SetSelectionPoint2(1, -1, landing[0], landing[1], 0.0) is not True:
        raise RuntimeError(f"{label}: failed to set the flank landing {landing}")
    note = draw.InsertNote(property_link(property_name))
    if note is None:
        raise RuntimeError(f"{label}: failed to insert linked callout {property_name!r}")
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
        raise RuntimeError(f"{label}: failed to create the leader")
    if not annotation.SetPosition2(note_xy[0], note_xy[1], 0.0):
        raise RuntimeError(f"{label}: failed to position the note")
    rebuild_drawing(adapter, label=label)
    if int(annotation.GetAttachedEntityCount3()) != 1 or tuple(
        annotation.GetAttachedEntityTypes() or ()
    ) != (1,):
        raise RuntimeError(f"{label}: expected exactly one EDGE attachment")
    _assert_leader_lands(annotation, landing, what="toothspace callout", label=label)
    draw.ClearSelection2(True)
    return note
