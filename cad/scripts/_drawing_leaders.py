"""Leader geometry read back off a drawing sheet, and a near-side diameter style.

A leader that runs through a hole's centre, or across another annotation's
leader, is a clarity defect a render shows but no dimension gate catches
(eye pass of w15-301f4bf4e: MHA-020's hub-seat leader crossed R12.7 at the
bore centre; on MHA-021 the tip diameter, bore diameter and bore finish
leaders met at the bore). This module reads each annotation's ink as sheet
segments so a drawing can fail its build on such a crossing.

Opt-in, like ``_drawing_hidden_sketches``: only the drawings that import it
re-key when it changes; ``_drawing_common`` is in every drawing's key. It is
the fleet's one leader and dimension-line reader; extend it rather than
growing another.

What a seat has shown, and what it has not yet:

- Farm run w15-3d3a9d762 (20260925T193429474Z-35f59b07): drawing:crank_arm
  (15d4e3b95dbf, seat pid 12100, "done in 22.0s") and
  drawing:crank_drive_gear (d48669b89a14) built and passed
  ``assert_leaders_clear``. So ``GetLineAtIndex2`` and
  ``GetLeaderPointsAtIndex`` returned ink for every named annotation (the
  no-ink branch fails loud).
- That pass did NOT prove the COORDINATE SPACE: segments in view space would
  miss every keep-out and crossing vacuously. ``lands_within`` closes that
  gap (each named annotation must end at its feature, in sheet metres), and
  the ``leaders clear`` info line puts the segment counts and landing
  distances in the leaf log. The first leaf that passes it is the proof; add
  its line here.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import _telemetry
from solidworks_mcp.adapters import sw_type_info as _sw_type_info

Point = tuple[float, float]
Segment = tuple[Point, Point]
Box = tuple[float, float, float, float]  # (x0, y0, x1, y1), x0 <= x1, y0 <= y1

# An arrowhead or its tail nearer foreign text than this reads as part of
# that text: keep 2 mm of ink between them.
ARROW_TEXT_CLEARANCE = 0.002

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


def parse_section_line_info(values: Sequence[float]) -> list[Segment]:
    """Section-line strokes from ``IView.GetSectionLineInfo2``'s flat array.

    Layout: [count, layer, then per line: nSegments, nSegments x (lineType,
    start[3], end[3]), arrow1 (start[3], end[3], width, height, style), arrow2
    (same), text1[3], text2[3], textHeight]. The chain-line segments and both
    arrow shafts come back; the labels' text points do not.
    """
    values = [float(v) for v in values]
    if not values:
        return []
    count, index, segments = int(values[0]), 2, []
    for _ in range(count):
        n = int(values[index])
        index += 1
        for _ in range(n):
            start, end = values[index + 1 : index + 3], values[index + 4 : index + 6]
            segments.append(((start[0], start[1]), (end[0], end[1])))
            index += 7
        for _ in range(2):
            start, end = values[index : index + 2], values[index + 3 : index + 5]
            segments.append(((start[0], start[1]), (end[0], end[1])))
            index += 9
        index += 7
    if index != len(values):
        raise RuntimeError(f"section-line info has {len(values)} values, parsed {index}")
    return segments


def section_line_segments(view: Any) -> list[Segment]:
    """The cutting-plane strokes (chain line and arrow shafts) a view carries."""
    view = _sw_type_info.early_bound_or_flag(view, "IView", "GetSectionLineInfo2")
    return parse_section_line_info(tuple(view.GetSectionLineInfo2() or ()))


def dimension_text_points(annotation: Any) -> list[Point]:
    """A display dimension's text positions in sheet metres (same space as its lines)."""
    annotation = _sw_type_info.early_bound_or_flag(
        annotation, "IAnnotation", "GetSpecificAnnotation"
    )
    display = _sw_type_info.early_bound_or_flag(
        annotation.GetSpecificAnnotation(), "IDisplayDimension", "GetDisplayData"
    )
    data = _sw_type_info.early_bound_or_flag(
        display.GetDisplayData(), "IDisplayData", "GetTextPositionAtIndex", "GetTextCount"
    )
    return [
        tuple(float(v) for v in tuple(data.GetTextPositionAtIndex(index))[:2])
        for index in range(int(data.GetTextCount()))
    ]


def points_inside(points: Sequence[Point], box: tuple[float, float, float, float]) -> list[Point]:
    """The points strictly inside ``box`` = (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = box
    return [p for p in points if x0 < p[0] < x1 and y0 < p[1] < y1]


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


# Two lines closer than this, and sharing more than this of their length,
# read as one stroke on a printed sheet (sheet metres: 0.1 mm).
COLLINEAR_TOLERANCE = 1e-4


def _collinear_overlap(first: Segment, second: Segment, tolerance: float) -> bool:
    """True when ``second`` lies along ``first`` for more than ``tolerance``."""
    (a, b), (c, d) = first, second
    length = math.dist(a, b)
    if length <= tolerance:
        return False
    if max(distance_to_line(first, c), distance_to_line(first, d)) > tolerance:
        return False
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    tc = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy
    td = (d[0] - a[0]) * ux + (d[1] - a[1]) * uy
    return min(length, max(tc, td)) - max(0.0, min(tc, td)) > tolerance


def segments_cross(
    first: Segment, second: Segment, tolerance: float = COLLINEAR_TOLERANCE
) -> bool:
    """True when the segments properly intersect or one lies along the other.

    A shared endpoint is not a crossing; a leader laid along another line for
    more than ``tolerance`` is, since the two strokes print as one.
    """
    (a, b), (c, d) = first, second
    d1, d2 = _orientation(c, d, a), _orientation(c, d, b)
    d3, d4 = _orientation(a, b, c), _orientation(a, b, d)
    if d1 * d2 < 0.0 and d3 * d4 < 0.0:
        return True
    return _collinear_overlap(first, second, tolerance) or _collinear_overlap(
        second, first, tolerance
    )


def distance_to_line(segment: Segment, point: Point) -> float:
    """Distance from ``point`` to the infinite line through the segment."""
    (x0, y0), (x1, y1) = segment
    length = math.dist((x0, y0), (x1, y1))
    if length == 0.0:
        return math.dist((x0, y0), point)
    return abs((x1 - x0) * (y0 - point[1]) - (x0 - point[0]) * (y1 - y0)) / length


def distance_to_point(segment: Segment, point: Point) -> float:
    """Shortest distance from ``point`` to the segment."""
    (x0, y0), (x1, y1) = segment
    dx, dy = x1 - x0, y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.dist((x0, y0), point)
    t = max(0.0, min(1.0, ((point[0] - x0) * dx + (point[1] - y0) * dy) / length_sq))
    return math.dist((x0 + t * dx, y0 + t * dy), point)


def distance_to_box(segment: Segment, box: Box) -> float:
    """Shortest distance from the segment to an axis-aligned box.

    0 when it touches or enters the box, or runs along an edge within
    ``COLLINEAR_TOLERANCE`` (``segments_cross``).
    """
    x0, y0, x1, y1 = box
    if any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in segment):
        return 0.0
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    edges = tuple(zip(corners, corners[1:] + corners[:1]))
    if any(segments_cross(segment, edge) for edge in edges):
        return 0.0
    return min(
        *(distance_to_point(segment, corner) for corner in corners),
        *(distance_to_point(edge, end) for edge in edges for end in segment),
    )


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


def landing_distance(segments: Sequence[Segment], centre: Point) -> float:
    """How close the annotation's nearest segment END comes to ``centre``."""
    return min(math.dist(end, centre) for segment in segments for end in segment)


def arrows_near_text(
    arrows: Mapping[str, Sequence[Segment]],
    texts: Mapping[str, Box],
    *,
    clearance: float = ARROW_TEXT_CLEARANCE,
    half_width: float = 0.0,
) -> list[tuple[str, str, float]]:
    """Every (owner, text, gap) where an owner's arrowhead stands nearer than
    ``clearance`` to another annotation's text box.

    ``arrows`` gives each annotation's arrowheads (and any outside arrow's
    tail) as segments along their axis; ``half_width`` is half an arrowhead's
    breadth, taken off the axis distance.  A text keyed like the owner is its
    own and is skipped.  The gap is the nearest arrow's, floored at 0.
    """
    near = []
    for owner, segments in arrows.items():
        if not segments:
            continue
        for name, box in texts.items():
            if name == owner:
                continue
            nearest = min(distance_to_box(segment, box) for segment in segments)
            gap = nearest - half_width
            if gap < clearance:
                near.append((owner, name, max(gap, 0.0)))
    return near


def assert_leaders_clear(
    groups: Mapping[str, Sequence[Segment]],
    *,
    centre: Point,
    keep_out: Mapping[str, float],
    lands_within: Mapping[str, tuple[float, float]],
    label: str,
) -> None:
    """Fail unless every named annotation lands at its feature and none cross.

    ``lands_within[name] = (low, high)``: the annotation's nearest segment end
    lies that far from ``centre`` (its rim, or the centre itself). Every
    annotation must have a band, which proves the segments are sheet metres
    before the crossing and keep-out checks can pass. ``keep_out[name]``: no
    segment of it comes closer to ``centre`` than that.
    """
    missing = sorted(set(groups) - set(lands_within))
    if missing:
        raise ValueError(f"{label}: no landing band for {missing}")
    empty = [name for name, segments in groups.items() if not segments]
    landings = {
        name: landing_distance(segments, centre)
        for name, segments in groups.items()
        if segments
    }
    astray = {
        name: distance
        for name, distance in landings.items()
        if not lands_within[name][0] <= distance <= lands_within[name][1]
    }
    crossings = leader_crossings(groups)
    intrusions = {
        name: min(distance_to_point(segment, centre) for segment in groups[name])
        for name, radius in keep_out.items()
        if groups[name] and min(distance_to_point(s, centre) for s in groups[name]) < radius
    }
    summary = {
        name: f"{len(segments)} seg, lands {landings.get(name, float('nan')) * 1000:.2f} mm"
        for name, segments in groups.items()
    }
    _telemetry.event(
        "drawing.leaders_clear",
        label=label,
        segments=str(summary),
        crossings=str(crossings),
        intrusions=str(intrusions),
        astray=str(astray),
    )
    if empty or astray or crossings or intrusions:
        raise RuntimeError(
            f"{label}: leaders not clear -- no ink read for {empty}, landing off its "
            f"feature {astray}, crossings {crossings}, inside the keep-out of {centre}: "
            f"{intrusions}; segments {dict(groups)}"
        )
    _telemetry.info(f"{label}: leaders clear {summary}")
