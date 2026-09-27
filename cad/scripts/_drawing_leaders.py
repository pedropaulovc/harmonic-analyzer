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
  distances in the leaf log.
- Farm run w15-8c4af0b9f (20260925T194809956Z-4929302b) is the proof. Every
  landing reads the feature's exact sheet radius, so the segments are sheet
  metres:
  - drawing:crank_arm dffdcac16414, seat pid 7484: "crank arm hub seat:
    leaders clear {'HubSeatDia': '2 seg, lands 19.50 mm', 'BossRadius':
    '3 seg, lands 0.00 mm'}". Ø19.5 at 2:1 is a 19.50 mm sheet radius, and
    R12.7 ends at the bore centre.
  - drawing:crank_drive_gear 1b05750e1716, seat pid 11608: "crank drive gear
    bore: leaders clear {'OutsideDia': '2 seg, lands 48.86 mm', 'BoreDia':
    '3 seg, lands 7.14 mm', 'BoreFinish': '2 seg, lands 7.14 mm'}". These are
    HALF_OD and the bore's sheet radius at 3:2.
- ``section_line_segments`` (GetSectionLineInfo2) is not seat-proven yet.
  Its first leaf (drawing:crank_pinion 20260925T210727Z) showed the chain
  comes back in MODEL space and the arrows on the sheet. Until the chain was
  mapped through the view's model-to-view transform, every section chain
  was tested in model metres near the sheet origin, far from every leader,
  so any earlier section-line crossing result was VACUOUS. That includes
  8c4af0b9f's pass: it proves the leaders' space, not the section line's.
  The mapped version's first leaf is the proof.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Collection, Mapping, Sequence

import _telemetry
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array

Point = tuple[float, float]
Point3 = tuple[float, float, float]
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


def parse_section_line_info(
    values: Sequence[float],
    chain_to_sheet: Callable[[Point3], Point] | None = None,
) -> list[Segment]:
    """Section-line strokes from ``IView.GetSectionLineInfo2``'s flat array.

    Layout: [count, layer, then per line: nSegments, nSegments x (lineType,
    start[3], end[3]), arrow1 (start[3], end[3], width, height, style), arrow2
    (same), text1[3], text2[3], textHeight]. The chain-line segments, both
    arrow shafts and both arrowheads' outlines come back; the labels' text
    points do not.

    The array mixes spaces: the chain points are MODEL coordinates and the
    arrows are sheet coordinates (seat, drawing:crank_pinion leaf
    20260925T210727Z: chain x 0, y +/-0.0106 against arrows at y 0.120 on a
    3:1 view at (0.110, 0.150)). ``chain_to_sheet`` maps a chain point onto
    the sheet (``section_line_segments`` passes the view's model-to-view
    transform); without it the chain is read as already on the sheet.

    Each head is tipped at the shaft end AWAY from the chain: the tail is the
    end within ``COLLINEAR_TOLERANCE`` of a chain segment's line and inside
    its span, give or take ``SECTION_CHAIN_OVERRUN``. That doubles as the
    transform's proof -- a shaft with neither or both ends on the mapped
    chain raises with the raw and mapped values, never guesses.
    """
    values = [float(v) for v in values]
    if not values:
        return []
    count, index, segments = int(values[0]), 2, []
    for _ in range(count):
        n = int(values[index])
        index += 1
        chain: list[Segment] = []
        for _ in range(n):
            start = (values[index + 1], values[index + 2], values[index + 3])
            end = (values[index + 4], values[index + 5], values[index + 6])
            if chain_to_sheet is None:
                stroke = ((start[0], start[1]), (end[0], end[1]))
            else:
                stroke = (chain_to_sheet(start), chain_to_sheet(end))
            chain.append(stroke)
            index += 7
        segments.extend(chain)
        for arrow in (1, 2):
            raw = values[index : index + 9]
            start, end = (raw[0], raw[1]), (raw[3], raw[4])
            width, height = raw[6], raw[7]
            segments.append((start, end))
            segments.extend(
                arrowhead_outline(_tail_first(start, end, chain, arrow, raw), width, height)
            )
            index += 9
        index += 7
    if index != len(values):
        raise RuntimeError(f"section-line info has {len(values)} values, parsed {index}")
    return segments


# How far past a chain segment's end an arrow's tail may sit and still read as
# on the chain (sheet metres). The seat's chain runs PAST its arrows instead:
# drawing:crank_pinion leaf 20260925T210727Z mapped the chain end to y
# 0.118347 and drew arrow 1's tail at 0.120347, 2.00 mm inside. The mirror
# case is allowed the same 2 mm until a seat shows one; every arrow logs its
# measured inset so the next run can tighten this with evidence.
SECTION_CHAIN_OVERRUN = 0.002


def _chain_inset(stroke: Segment, point: Point) -> float | None:
    """How far inside the stroke's span ``point`` sits along its line.

    Negative past an end; None when ``point`` is off the stroke's infinite
    line by more than ``COLLINEAR_TOLERANCE``.
    """
    (x0, y0), (x1, y1) = stroke
    length = math.dist((x0, y0), (x1, y1))
    if length == 0.0:
        return None
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    dx, dy = point[0] - x0, point[1] - y0
    if abs(dx * uy - dy * ux) > COLLINEAR_TOLERANCE:
        return None
    along = dx * ux + dy * uy
    return min(along, length - along)


def _tail_first(
    start: Point, end: Point, chain: Sequence[Segment], arrow: int, raw: Sequence[float]
) -> Segment:
    """The arrow shaft ordered tail (on the chain) to tip."""
    insets = [
        max(
            (inset for stroke in chain if (inset := _chain_inset(stroke, point)) is not None),
            default=None,
        )
        for point in (start, end)
    ]
    on_chain = [inset is not None and inset >= -SECTION_CHAIN_OVERRUN for inset in insets]
    if on_chain == [True, False]:
        orientation, shaft, inset = "start on chain, tip at end", (start, end), insets[0]
    elif on_chain == [False, True]:
        orientation, shaft, inset = "end on chain, tip at start", (end, start), insets[1]
    else:
        raise RuntimeError(
            f"section arrow {arrow}: cannot tell its tip -- start on chain "
            f"{on_chain[0]}, end on chain {on_chain[1]} (insets {insets}); raw "
            f"{list(raw)}, chain on the sheet {list(chain)}"
        )
    _telemetry.info(
        f"section arrow {arrow}: {orientation}; tail inset {inset * 1000:.2f} mm from "
        f"the chain end (negative past it; allowance {SECTION_CHAIN_OVERRUN * 1000:.1f} mm)"
    )
    return shaft


def arrowhead_outline(shaft: Segment, width: float, height: float) -> list[Segment]:
    """The outline of an arrowhead whose tip is the shaft's end.

    The API names the head's two sizes but not which one runs along the
    shaft, so both readings are returned -- a head ``width`` long and
    ``height`` across, and ``height`` long and ``width`` across -- and a
    crossing with either counts.  Each reading is three strokes: the two
    wings from the tip back to the base corners, and the base across the
    shaft between them.
    """
    (x0, y0), (x1, y1) = shaft
    length = math.dist((x0, y0), (x1, y1))
    if length == 0.0:
        return []
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    wings = []
    for along, across in ((width, height), (height, width)):
        bx, by = x1 - ux * along, y1 - uy * along
        half = across / 2.0
        left = (bx - uy * half, by + ux * half)
        right = (bx + uy * half, by - ux * half)
        wings.extend((((x1, y1), left), ((x1, y1), right), (left, right)))
    return wings


def section_line_segments(adapter: Any, view: Any) -> list[Segment]:
    """The cutting-plane strokes a view carries, all in sheet metres.

    The chain points are mapped through ``IView.ModelToViewTransform`` (the
    same model-to-sheet projection ``_drawing_common.model_point_in_view``
    uses, with SolidWorks doing the matrix product); the arrows already come
    back on the sheet. ``view`` is the view that CARRIES the section line
    (the parent), whose model space the chain is in.

    The layout audit dropped ModelToViewTransform (drawing-layout-audit.md:
    GetPolylines7 edges and IVertex points, mapped by a hand-rolled
    ArrayData product, missed their strokes by 86-460 mm). Neither of those
    inputs is used here. A crop hides geometry without moving it. A break
    DOES move it -- the transform does not know the gap -- so a broken view
    raises. Any other mismatch leaves the arrows' tails off the mapped chain,
    which raises in ``parse_section_line_info``.
    """
    view = _sw_type_info.early_bound_or_flag(
        view, "IView", "GetSectionLineInfo2", "ModelToViewTransform", "IsBroken", "GetName2"
    )
    name = str(view.GetName2())
    if view.IsBroken():
        raise RuntimeError(
            f"section line on broken view {name!r}: its model-to-view transform "
            "does not carry the break gap"
        )
    utility = _sw_type_info.early_bound_or_flag(
        adapter.swApp.GetMathUtility(), "IMathUtility", "CreatePoint"
    )
    transform = _sw_type_info.early_bound_or_flag(
        view.ModelToViewTransform, "IMathTransform", "ArrayData"
    )
    _telemetry.info(
        f"section view {name!r} model-to-view transform {list(transform.ArrayData)}"
    )

    def to_sheet(point: Point3) -> Point:
        # A bare list marshals as VT_ARRAY | VT_VARIANT, which CreatePoint
        # silently reads as the origin (seat, drawing:crank_pinion leaf
        # 20260925T215656Z: both chain ends landed on the view's translation).
        model = utility.CreatePoint(double_array(list(point)))
        if model is None:
            raise RuntimeError(f"section line: could not create model point {point}")
        model = _sw_type_info.early_bound_or_flag(
            model, "IMathPoint", "MultiplyTransform", "ArrayData"
        )
        created = tuple(float(v) for v in tuple(model.ArrayData)[:3])
        if not all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(created, point)):
            raise RuntimeError(
                f"section line: CreatePoint({point}) made {created}; the array did not marshal"
            )
        mapped = model.MultiplyTransform(transform)
        if mapped is None:
            raise RuntimeError(f"section line: could not map model point {point}")
        mapped = _sw_type_info.early_bound_or_flag(mapped, "IMathPoint", "ArrayData")
        x, y = (float(v) for v in tuple(mapped.ArrayData)[:2])
        _telemetry.debug(f"section chain point {point} -> sheet ({x:.6f}, {y:.6f})")
        return (x, y)

    return parse_section_line_info(tuple(view.GetSectionLineInfo2() or ()), to_sheet)


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


def _ends_on_interior(segment: Segment, other: Segment, tolerance: float) -> bool:
    """True when an end of ``segment`` lands on ``other`` away from its ends."""
    for end in segment:
        if min(math.dist(end, other[0]), math.dist(end, other[1])) <= tolerance:
            continue
        if distance_to_point(other, end) <= tolerance:
            return True
    return False


def segments_cross(
    first: Segment,
    second: Segment,
    tolerance: float = COLLINEAR_TOLERANCE,
    *,
    touching: str = "crossing",
) -> bool:
    """True when the segments intersect, meet in a T or one lies along the other.

    Only a shared endpoint (within ``tolerance``) is exempt.  A stroke that
    ends on another's interior -- a T-junction -- is a crossing unless the
    caller declares the pair ``touching="allowed"`` (a leader tip landed on
    its own feature line); a proper crossing and a collinear overlap longer
    than ``tolerance`` always count, since the strokes print as one.
    """
    if touching not in ("crossing", "allowed"):
        raise ValueError(f"touching must be 'crossing' or 'allowed', not {touching!r}")
    (a, b), (c, d) = first, second
    d1, d2 = _orientation(c, d, a), _orientation(c, d, b)
    d3, d4 = _orientation(a, b, c), _orientation(a, b, d)
    if d1 * d2 < 0.0 and d3 * d4 < 0.0:
        return True
    if _collinear_overlap(first, second, tolerance) or _collinear_overlap(
        second, first, tolerance
    ):
        return True
    if touching == "allowed":
        return False
    return _ends_on_interior(first, second, tolerance) or _ends_on_interior(
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


def leader_crossings(
    groups: Mapping[str, Sequence[Segment]],
    touching: Collection[frozenset[str]] = (),
) -> list[tuple[str, str]]:
    """Every pair of named annotations whose ink crosses.

    ``touching`` lists the pairs (as frozensets of two names) declared to meet
    in a T -- one's tip landed on the other's line; they still may not cross.
    """
    names = list(groups)
    crossings = []
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            mode = "allowed" if frozenset((first, second)) in touching else "crossing"
            if any(
                segments_cross(a, b, touching=mode)
                for a in groups[first]
                for b in groups[second]
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
    touching: Collection[frozenset[str]] = (),
) -> None:
    """Fail unless every named annotation lands at its feature and none cross.

    ``lands_within[name] = (low, high)``: the annotation's nearest segment end
    lies that far from ``centre`` (its rim, or the centre itself). Every
    annotation must have a band, which proves the segments are sheet metres
    before the crossing and keep-out checks can pass. ``keep_out[name]``: no
    segment of it comes closer to ``centre`` than that. ``touching``: pairs
    declared to meet in a T (``leader_crossings``); every other T is a
    crossing.
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
    crossings = leader_crossings(groups, touching)
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
