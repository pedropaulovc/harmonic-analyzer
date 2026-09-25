"""Leader geometry read back off a drawing sheet, and a near-side diameter style.

A leader that runs through a hole's centre, or across another annotation's
leader, is a clarity defect a render shows but no dimension gate catches
(eye pass of w15-301f4bf4e: MHA-020's hub-seat leader crossed R12.7 at the
bore centre; on MHA-021 the tip diameter, bore diameter and bore finish
leaders met at the bore). This module reads each annotation's ink as sheet
segments so a drawing can fail its build on such a crossing.

Opt-in, like ``_drawing_hidden_sketches``: only the drawings that import it
re-key when it changes; ``_drawing_common`` is in every drawing's key.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import _telemetry
from solidworks_mcp.adapters import sw_type_info as _sw_type_info

Point = tuple[float, float]
Segment = tuple[Point, Point]

_ARROWS_OUTSIDE = 1  # swDimensionArrowsSide_e.swDimArrowsOutside
_BROKEN_LEADER_HORIZONTAL = 2  # SetBrokenLeader2 style: horizontal text


def set_near_side_diameter(annotation: Any, label: str) -> None:
    """One arrow on the rim nearest the text; no line through the centre.

    The same native style ``draw_alignment_pinion`` gives its OD: diametric,
    arrow outside, no second arrow, a broken leader with horizontal text.
    """
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetSpecificAnnotation"
    )
    display = _sw_type_info.early_bound_or_flag(
        annotation.GetSpecificAnnotation(),
        "IDisplayDimension",
        "SetSecondArrow",
        "GetUseDocSecondArrow",
        "GetSecondArrow",
        "SetBrokenLeader2",
        "GetUseDocBrokenLeader",
        "GetBrokenLeader2",
    )
    display.Diametric = True
    display.ArrowSide = _ARROWS_OUTSIDE
    display.SetSecondArrow(False, False)
    display.SolidLeader = False
    if display.SetBrokenLeader2(False, _BROKEN_LEADER_HORIZONTAL) != 0:
        raise RuntimeError(f"{label}: failed to apply the broken horizontal leader")
    if (
        int(display.ArrowSide) != _ARROWS_OUTSIDE
        or bool(display.SolidLeader)
        or bool(display.GetUseDocBrokenLeader())
        or int(display.GetBrokenLeader2()) != _BROKEN_LEADER_HORIZONTAL
        or bool(display.GetUseDocSecondArrow())
        or bool(display.GetSecondArrow())
    ):
        raise RuntimeError(f"{label}: near-side single-arrow style did not persist")


def dimension_segments(annotation: Any) -> list[Segment]:
    """A display dimension's lines (dimension, extension, leader) in sheet metres."""
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetSpecificAnnotation"
    )
    display = _sw_type_info.early_bound_or_flag(
        annotation.GetSpecificAnnotation(), "IDisplayDimension", "GetDisplayData"
    )
    data = _sw_type_info.early_bound_or_flag(
        display.GetDisplayData(), "IDisplayData", "GetLineAtIndex2", "GetLineCount"
    )
    segments = []
    for index in range(int(data.GetLineCount())):
        line = tuple(float(value) for value in data.GetLineAtIndex2(index))
        if len(line) < 10:
            raise RuntimeError(f"display line {index} is incomplete: {line}")
        segments.append(((line[4], line[5]), (line[7], line[8])))
    return segments


def leader_segments(annotation: Any) -> list[Segment]:
    """An annotation's leader polylines (straight or bent) in sheet metres."""
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetLeaderCount", "GetLeaderPointsAtIndex"
    )
    segments = []
    for index in range(int(annotation.GetLeaderCount())):
        flat = tuple(float(value) for value in (annotation.GetLeaderPointsAtIndex(index) or ()))
        points = [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 2, 3)]
        segments.extend(zip(points, points[1:]))
    return segments


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_cross(first: Segment, second: Segment) -> bool:
    """True when the two segments properly intersect (a shared endpoint is not a crossing)."""
    (a, b), (c, d) = first, second
    d1, d2 = _orientation(c, d, a), _orientation(c, d, b)
    d3, d4 = _orientation(a, b, c), _orientation(a, b, d)
    return d1 * d2 < 0.0 and d3 * d4 < 0.0


def distance_to_point(segment: Segment, point: Point) -> float:
    """Shortest distance from ``point`` to the segment."""
    (x0, y0), (x1, y1) = segment
    dx, dy = x1 - x0, y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.dist((x0, y0), point)
    t = max(0.0, min(1.0, ((point[0] - x0) * dx + (point[1] - y0) * dy) / length_sq))
    return math.dist((x0 + t * dx, y0 + t * dy), point)


def leader_crossings(groups: Mapping[str, Sequence[Segment]]) -> list[tuple[str, str]]:
    """Every pair of named annotations whose ink crosses."""
    names = list(groups)
    crossings = []
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            if any(
                segments_cross(a, b) for a in groups[first] for b in groups[second]
            ):
                crossings.append((first, second))
    return crossings


def assert_leaders_clear(
    groups: Mapping[str, Sequence[Segment]],
    *,
    centre: Point,
    keep_out: Mapping[str, float],
    label: str,
) -> None:
    """Fail when named annotations cross, or one runs inside its keep-out of ``centre``."""
    crossings = leader_crossings(groups)
    intrusions = {
        name: min(distance_to_point(segment, centre) for segment in groups[name])
        for name, radius in keep_out.items()
        if groups[name] and min(distance_to_point(s, centre) for s in groups[name]) < radius
    }
    _telemetry.event(
        "drawing.leaders_clear",
        label=label,
        segments=str({name: len(segments) for name, segments in groups.items()}),
        crossings=str(crossings),
        intrusions=str(intrusions),
    )
    empty = [name for name, segments in groups.items() if not segments]
    if empty or crossings or intrusions:
        raise RuntimeError(
            f"{label}: leaders not clear -- no ink read for {empty}, crossings {crossings}, "
            f"inside the keep-out of {centre}: {intrusions}; segments {dict(groups)}"
        )
