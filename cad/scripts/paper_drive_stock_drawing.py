"""Model-linked toothspace callout on a stock-form flank.

Main's convention for a callout on a model edge: pick the edge at its known
sheet point (the spec's gauge-pin flank contact), then check the attached
edge is a formed curve, neither a line nor a circle (an OD, root or end-face
straight edge), that passes through that contact. A root-fillet or tip edge
is also a formed curve, but it meets the flank only at the flank's ends,
which lie far from the contact.
"""

from __future__ import annotations

import math
from typing import Any

from _common import _early_bound
from _drawing_common import add_property_linked_callout, model_point_in_view
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


# How far the attached edge may pass from the contact point. SolidWorks holds
# an equation curve as a fitted spline (paper_drive_stock_native.author_span),
# so this budgets the fit, not the part: a micrometre-class fit is far inside
# 0.01 mm, and each flank end lies over 20x farther from the contact (tested).
CONTACT_TOLERANCE_MM = 0.01


def _require_formed_flank(attached: Any, contact_xy_mm: tuple[float, float], station_mm: float) -> None:
    curve = _early_bound(_early_bound(attached, "IEdge").GetCurve(), "ICurve")
    if curve.IsLine() or curve.IsCircle():
        raise RuntimeError(
            "toothspace callout: attached edge is a line or circle, not a formed flank"
        )
    # An end-face edge is planar at constant z, so its closest point to the
    # contact at any station is its closest in x/y: compare x/y only.
    x, y = contact_xy_mm
    closest = tuple(curve.GetClosestPointOn(x / 1000.0, y / 1000.0, station_mm / 1000.0))
    miss_mm = math.hypot(closest[0] * 1000.0 - x, closest[1] * 1000.0 - y)
    if miss_mm > CONTACT_TOLERANCE_MM:
        raise RuntimeError(
            f"toothspace callout: attached edge passes {miss_mm:.4f} mm from the "
            f"gauge contact ({x:.4f}, {y:.4f}) mm (closest point "
            f"{tuple(round(v * 1000.0, 4) for v in closest[:3])} mm; limit "
            f"{CONTACT_TOLERANCE_MM} mm): not the flank"
        )


def add_toothspace_callout(
    adapter: Any, view: Any, *, profile: StockFormProfile,
    actual_pin_diameter_mm: float, rotate_rad: float, axial_station_mm: float,
    property_name: str, note_xy: tuple[float, float],
) -> Any:
    """One model-linked arrow on the flank at the gauge pin's contact point."""
    contact = toothspace_gauge_contact_mm(profile, actual_pin_diameter_mm)
    x, y = _rotate(contact.flank_point_mm, rotate_rad)
    edge_xy = model_point_in_view(
        adapter, view, (x / 1000.0, y / 1000.0, axial_station_mm / 1000.0),
        label="toothspace gauge contact",
    )
    note = add_property_linked_callout(
        adapter, view, property_name=property_name, edge_xy=edge_xy, note_xy=note_xy,
    )
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 1 or tuple(annotation.GetAttachedEntityTypes() or ()) != (1,):
        raise RuntimeError("toothspace callout: expected exactly one EDGE attachment")
    _require_formed_flank(attached[0], (x, y), axial_station_mm)
    return note
