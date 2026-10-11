"""Rendered drawing balloon-circle geometry.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations

from typing import Any
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
import math


def rendered_balloon_circle(note: Any, *, label: str) -> tuple[float, float, float]:
    """Return sheet X/Y/radius from the unique rendered full-circle primitive.

    INote.GetBalloonInfo can retain its original center after a successful move,
    rebuild, redraw, and PDF export. IAnnotation.GetDisplayData reflects the ink.
    """
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: balloon has no annotation")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetDisplayData"
    )
    display = annotation.GetDisplayData()
    if display is None:
        raise RuntimeError(f"{label}: balloon has no rendered display data")
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayData", "GetArcCount", "GetArcAtIndex2"
    )
    circle = None
    for index in range(int(display.GetArcCount())):
        arc = tuple(float(value) for value in (display.GetArcAtIndex2(index) or ()))
        # Native schema: four metadata values, start XYZ, end XYZ, center XYZ,
        # normal XYZ, rotation direction. Closed start/end identifies a circle.
        if len(arc) < 17 or not all(math.isfinite(value) for value in arc[4:16]):
            raise RuntimeError(f"{label}: invalid rendered arc data: {arc!r}")
        if any(abs(arc[4 + axis] - arc[7 + axis]) > 1e-9 for axis in range(3)):
            continue
        radius = math.hypot(arc[4] - arc[10], arc[5] - arc[11])
        if (
            not math.isfinite(radius)
            or radius <= 0.0
            or abs(arc[13]) > 1e-9
            or abs(arc[14]) > 1e-9
            or abs(abs(arc[15]) - 1.0) > 1e-9
        ):
            raise RuntimeError(
                f"{label}: invalid rendered sheet-circle geometry: {arc!r}"
            )
        if circle is not None:
            raise RuntimeError(
                f"{label}: multiple rendered full-circle balloon primitives"
            )
        circle = (arc[10], arc[11], radius)
    if circle is None:
        raise RuntimeError(f"{label}: no rendered full-circle balloon primitive")
    return circle
