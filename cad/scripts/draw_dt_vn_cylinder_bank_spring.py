"""Supplier nominal dimension diagrams beside the installed 9714K392 envelope.

The sheet prints only replacement sizes: ID, OD, free height and thickness.
The part keeps its catalogue load-point gauge sketch (compressed height and
deflection at 1.5 lb), which is rating data rather than a replacement size;
the 0.95 mm set gap governs the installed preload.

At 2:1 these diagrams are smaller than their text. The shared disc placement
centres each value on its own line, so machinist review of b344192 found the
thickness and free height struck by their witnesses and dimension lines, and
the two plan diameters crossing at the centre with their text on the OD rim.
``place_size_texts`` keeps every native dimension, value and station, and
moves only presentation: the heights take native offset text shelved beyond
their own lines (the R48 washer pattern), and the diameters take one
near-side arrow with their text a text height clear of the OD rim and the
fleet's 2 mm arrow-to-text clearance beyond their own arrowhead.

Native run 86053b8e then printed a stray SupplierOD line: from the OD rim's
0 deg point (centre height), parallel to its leader and through its own "(".
The same line is in the main renders of the sibling 9714K24 and 9715K43 ODs,
so the text move did not make it, and ``ArcExtensionLineOrOppositeSide``
False stuck but changed nothing (run 27c25caf). No documented display switch
names it, so the leaf resolves it by presentation: it tries the bounded
``PLAN_PLACEMENTS`` in order, re-reading native ink after each rebuild, and
keeps the first that every guard passes. A guard failure refuses the sheet.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import partial
import math
from types import SimpleNamespace
import sys
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _drawing_layout_audit import _Reader, _dump_annotation
from _drawing_leaders import (
    COLLINEAR_TOLERANCE,
    assert_leaders_clear,
    distance_to_line,
    set_near_side_diameter,
)
from _layout_audit import (
    annotation_geometry,
    arrowhead_segments,
    calibrate_sheet_advance,
    display_box,
    find_lines_through_own_text,
)
from _layout_geometry import (
    ARROW_TEXT_CLEARANCE_M,
    DEFAULT_ADVANCE_RATIO,
    segment_box_distance,
)
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_disc_spring_drawing import (
    prepare_supplier_disc_diagram,
    supplier_disc_reference_features,
    supplier_disc_spring_dimensions,
)
from _supplier_screw_dimensions import _assert_supplier_top_stations
from _supplier_screw_layout import supplier_top_text_geometry
from _supplier_spring_drawing import (
    build_supplier_spring_drawing,
    reacquire_supplier_dimensions,
    supplier_state_cells,
)
from _supplier_spring_reference import SUPPLIER_DIAGRAM_CONFIGURATION
import dt_vn_cylinder_bank_spring_spec as supplier_spec
from vn_disc_spring_supplier_stock import (
    SUPPLIER_DIMENSION_NAMES,
    SUPPLIER_DIMENSIONS_BY_FEATURE,
)


SPEC = DRAWINGS_BY_NAME["dt_vn_cylinder_bank_spring"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "WAVE DISC SPRING"
# The drawing's view of the spec: identical except for no application gauges.
SHEET_SPEC = SimpleNamespace(
    **{**vars(supplier_spec), "SUPPLIER_APPLICATION_DIMENSIONS": ()}
)
ID_NAME = SUPPLIER_DIMENSION_NAMES["ID"]
OD_NAME = SUPPLIER_DIMENSION_NAMES["OD"]
# Each size keeps the side of its diagram the shared placement gave it:
# -1 left, +1 right.
TEXT_SIDES = {
    "free_front": {
        SUPPLIER_DIMENSION_NAMES["THICKNESS"]: -1,
        SUPPLIER_DIMENSION_NAMES["FREE_HEIGHT"]: 1,
    },
    "free_top": {ID_NAME: -1, OD_NAME: 1},
}
# Line ends this close are joined; lines this close to a common line print as
# one stroke (_drawing_leaders.COLLINEAR_TOLERANCE).
_JOIN_M = 1e-5
# A diameter's text is seated when a further move would be under this.
_SEATED_M = 1e-5
_SEAT_PASSES = 3
# The shoulder sits on the text's baseline: 0.05 mm under it on run 86053.
_SHOULDER_REACH_M = 0.0005
# The outer TOP cell the shared finalizer checks the settled ink against; it
# does not depend on the caption band.
FREE_TOP_CELL = next(
    cell
    for key, _, cell in supplier_state_cells(0.0, maximum=False)
    if key == "free_top"
)


@dataclass(frozen=True)
class PlanPlacement:
    """One presentation of the two plan diameters.

    ``sides``: -1 text left of the plan, +1 right. ``level``: diameters whose
    shoulder sits at the centre height, so the leader lands on the rim's 0 or
    180 deg point and runs horizontal along the shoulder.
    """

    label: str
    sides: Mapping[str, int]
    level: frozenset[str] = frozenset()


# Tried in order; the first whose settled native ink passes every guard wins.
PLAN_PLACEMENTS = (
    PlanPlacement("as placed", TEXT_SIDES["free_top"]),
    PlanPlacement(
        "OD leader level at 0 deg", TEXT_SIDES["free_top"], frozenset({OD_NAME})
    ),
    PlanPlacement("sides swapped", {ID_NAME: 1, OD_NAME: -1}),
    PlanPlacement(
        "sides swapped, OD leader level at 180 deg",
        {ID_NAME: 1, OD_NAME: -1},
        frozenset({OD_NAME}),
    ),
)


def height_text_shift(geometry: Mapping[str, Any], side: int) -> float:
    """Sheet x move that shelves offset text wholly past its own native lines."""
    text = geometry["text"]
    air = CLEAR_GAP_M + PLACE_SETTLE_M
    if side < 0:
        return geometry["left"] - air - text.xmax
    return geometry["right"] + air - text.xmin


def assert_height_text_clear(
    geometry: Mapping[str, Any], side: int, *, label: str
) -> None:
    """No witness, dimension line or arrow of its own reaches the text."""
    text = geometry["text"]
    gap = geometry["left"] - text.xmax if side < 0 else text.xmin - geometry["right"]
    if not gap >= CLEAR_GAP_M:
        raise RuntimeError(
            f"{label}: text is {gap * 1000:.2f} mm from its own native lines"
        )


def diameter_air(text: Any) -> float:
    """A text height of air between a diameter's text and the OD rim."""
    return max(CLEAR_GAP_M, text.height)


def diameter_text_shift(
    text: Any,
    plan: tuple[float, float, float, float],
    side: int,
    *,
    arrow_reach: float,
) -> float:
    """Sheet x move that leaves ``diameter_air`` between text and plan ink and
    the arrow-to-text clearance between text and the outer extent of its own
    arrowhead (``arrow_reach``), whichever is farther out."""
    air = diameter_air(text) + PLACE_SETTLE_M
    arrow_air = ARROW_TEXT_CLEARANCE_M + PLACE_SETTLE_M
    if side < 0:
        return min(plan[0] - air, arrow_reach - arrow_air) - text.xmax
    return max(plan[2] + air, arrow_reach + arrow_air) - text.xmin


def assert_diameter_text_clear(
    text: Any, plan: tuple[float, float, float, float], side: int, *, label: str
) -> None:
    gap = plan[0] - text.xmax if side < 0 else text.xmin - plan[2]
    if not gap >= diameter_air(text):
        raise RuntimeError(
            f"{label}: text is {gap * 1000:.2f} mm from the OD rim, under a text height"
        )


def own_arrowheads(record: Mapping[str, Any]) -> list[Any]:
    """A dimension's arrowhead outlines, as the layout audit draws them."""
    heads = [
        segment
        for arrow in record["display"].get("arrows") or ()
        for segment in arrowhead_segments(arrow)
    ]
    if not heads:
        raise RuntimeError(f"{record.get('name')}: no readable native arrowhead")
    return heads


def arrow_reach(record: Mapping[str, Any], side: int) -> float:
    """The sheet x of a diameter's own arrowheads nearest its text's side."""
    xs = [x for segment in own_arrowheads(record) for x in (segment.x0, segment.x1)]
    return max(xs) if side > 0 else min(xs)


def assert_own_arrows_clear(
    record: Mapping[str, Any], text: Any, *, label: str
) -> None:
    """The fleet's arrow-to-text clearance on the dimension's OWN arrowheads,
    which ``find_arrows_near_text`` exempts (``_verify_control_ink`` rule)."""
    gap = min(segment_box_distance(head, text) for head in own_arrowheads(record))
    if not gap >= ARROW_TEXT_CLEARANCE_M:
        raise RuntimeError(
            f"{label}: own arrowhead {gap * 1000:.2f} mm from its text, under the "
            f"{ARROW_TEXT_CLEARANCE_M * 1000:g} mm arrow-to-text clearance"
        )


def assert_plan_leaders(
    groups: Mapping[str, Any], plan: tuple[float, float, float, float], *, label: str
) -> None:
    """Each diameter lands on its own rim and no line reaches the centre."""
    x0, y0, x1, y1 = plan
    radii = {OD_NAME: (x1 - x0) / 2.0}
    radii[ID_NAME] = radii[OD_NAME] * supplier_spec.ID / supplier_spec.OD
    assert_leaders_clear(
        groups,
        centre=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
        keep_out={name: 0.5 * radii[ID_NAME] for name in groups},
        lands_within={
            name: (0.8 * radius, 1.2 * radius) for name, radius in radii.items()
        },
        label=label,
    )


def _text_record(adapter: Any, display: Any, *, label: str) -> dict[str, Any]:
    reader = _Reader(adapter)
    record = _dump_annotation(reader, display.GetAnnotation())
    errors = reader.take_errors()
    position = (record or {}).get("pos") or ()
    texts = ((record or {}).get("display") or {}).get("texts") or ()
    if (
        errors
        or record is None
        or int(record.get("type", 0)) != 4
        or len(position) != 3
        or not all(math.isfinite(float(value)) for value in position)
        or not texts
    ):
        raise RuntimeError(f"{label}: no readable native text/position: {errors!r}")
    return record


def widths_measured(record: Mapping[str, Any]) -> bool:
    """SolidWorks reported a width for every text run of the record."""
    return all(float(run.get("w") or 0.0) > 0.0 for run in record["display"]["texts"])


def size_text_box(record: Mapping[str, Any]) -> Any:
    """A size text's box: SolidWorks' width for each run that reports one.

    A run with no width (``_dump_display`` omits ``w`` when the seat returns
    none) is estimated at the record's calibrated glyph advance, the sheet
    audit's estimate, floored at its 0.62 default so it never narrows the box.
    The heights' shared station geometry estimates the same way: their single
    run has no calibration sample, so it gets the default.
    """
    advance = max(calibrate_sheet_advance((record,)), DEFAULT_ADVANCE_RATIO)
    return display_box({"texts": record["display"]["texts"]}, advance=advance)


def _size_displays(adapter: Any, views: Mapping[str, Any]) -> dict[str, Any]:
    return reacquire_supplier_dimensions(
        adapter,
        {key: views[key] for key in TEXT_SIDES},
        expected={
            key: {
                name: next(
                    feature
                    for feature, names in SUPPLIER_DIMENSIONS_BY_FEATURE.items()
                    if name in names
                )
                for name in sides
            }
            for key, sides in TEXT_SIDES.items()
        },
        configurations={key: SUPPLIER_DIAGRAM_CONFIGURATION for key in TEXT_SIDES},
    )


def _move_text(
    display: Any, record: Mapping[str, Any], dx: float, dy: float = 0.0, *, label: str
) -> None:
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    x, y = (float(value) for value in record["pos"][:2])
    if not annotation.SetPosition2(x + dx, y + dy, 0.0):
        raise RuntimeError(f"{label}: text placement was rejected")


def lines_through_own_text(
    records: Mapping[str, Mapping[str, Any]], names: Iterable[str] | None = None
) -> list[str]:
    """The layout audit's own-text finder over the named dimensions' native ink.

    The glyph advance is calibrated over every record given, as the sheet audit
    calibrates over the sheet. The single-run height texts have no exact width
    sample, so alone they fall back to the 0.62 default, which boxes
    "(0.005 in)" 1.1 mm past its native width onto its own offset leg: run
    054fe692 refused the pass-1 geometry the sheet audit had passed. The two
    diameter rows supply exact samples (0.43 on run 86053b8e's records).
    """
    advance = calibrate_sheet_advance(tuple(records.values()))
    wanted = set(records if names is None else names)
    sheet = SimpleNamespace(
        name=supplier_spec.SKU,
        annotations=[
            annotation_geometry(record, owner="view", advance=advance)
            for name, record in records.items()
            if name in wanted
        ],
    )
    return [finding.detail for finding in find_lines_through_own_text(sheet)]


def _size_records(adapter: Any, displays: Mapping[str, Any]) -> dict[str, Any]:
    """One native snapshot of the four size dimensions; every check reads it."""
    return {
        name: _text_record(adapter, displays[name], label=name)
        for sides in TEXT_SIDES.values()
        for name in sides
    }


def height_stations(records: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Each height's native tips, witnesses and dimension lines, plus its text."""
    return {
        name: supplier_top_text_geometry(records[name], horizontal=False)
        for name in TEXT_SIDES["free_front"]
    }


def assert_height_stations(
    records: Mapping[str, Any], baseline: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    """The shared supplier-Top station check against the pre-mutation baseline."""
    current = height_stations(records)
    for name, geometry in current.items():
        _assert_supplier_top_stations(name, baseline[name], geometry)
    return current


def _segments(record: Mapping[str, Any]) -> list[tuple[tuple[float, float], ...]]:
    return [
        ((float(line[4]), float(line[5])), (float(line[7]), float(line[8])))
        for line in record["display"].get("lines") or ()
    ]


def _is_shoulder(stroke: tuple, text: Any, tip_x: float, *, measured: bool) -> bool:
    """A level stroke on the text's baseline under all of the text, ending at
    the text's far edge (away from the arrow), as SolidWorks draws it.

    Text left of its arrow ends at its first glyph, which the run position
    fixes. Text right of it ends at its last glyph, known only from measured
    widths; with an estimated width the shoulder need only run under the text.
    """
    (ax, ay), (bx, by) = stroke
    low, high = min(ax, bx), max(ax, bx)
    if not (
        abs(ay - by) <= 1e-7
        and abs(ay - text.ymin) <= _SHOULDER_REACH_M
        and low <= text.xmin + COLLINEAR_TOLERANCE
    ):
        return False
    if tip_x < text.xmin:
        if measured:
            return abs(high - text.xmax) <= COLLINEAR_TOLERANCE
        return high > text.xmin + COLLINEAR_TOLERANCE
    return abs(low - text.xmin) <= COLLINEAR_TOLERANCE and (
        not measured or high >= text.xmax - COLLINEAR_TOLERANCE
    )


def leader_chain(record: Mapping[str, Any]) -> tuple[list, list]:
    """A one-arrow diameter's lines as (arrow tip -> text shoulder, every other).

    The chain is anchored at both ends: it starts at the arrow tip and its last
    stroke is the shoulder under the text. A breadth-first search over joined
    endpoints, each reached once, stops at the first stroke count at which a
    shoulder is reached, so the leader is the fewest-stroke such path and
    duplicate or cyclic strokes cannot multiply the search. A stroke past the
    shoulder or any detour is left over for ``stray_leader_lines``.
    """
    arrows = record["display"].get("arrows") or ()
    if len(arrows) != 1:
        raise RuntimeError(
            f"{record.get('name')}: near-side diameter has {len(arrows)} arrows"
        )
    segments = _segments(record)
    text = size_text_box(record)
    measured = widths_measured(record)
    tip = (float(arrows[0][0]), float(arrows[0][1]))

    def far_end(index: int, point: tuple[float, float]) -> tuple[float, float] | None:
        a, b = segments[index]
        if math.dist(a, point) <= _JOIN_M:
            return b
        if math.dist(b, point) <= _JOIN_M:
            return a
        return None

    reached = [tip]
    frontier: list[tuple[tuple[float, float], list[int]]] = [(tip, [])]
    best: list[int] | None = None
    while frontier and best is None:
        following = []
        for point, path in frontier:
            for index in range(len(segments)):
                end = None if index in path else far_end(index, point)
                if end is None:
                    continue
                if _is_shoulder(segments[index], text, tip[0], measured=measured):
                    best = [*path, index]
                    break
                if all(math.dist(end, seen) > _JOIN_M for seen in reached):
                    reached.append(end)
                    following.append((end, [*path, index]))
            if best is not None:
                break
        frontier = following
    if best is None:
        raise RuntimeError(
            f"{record.get('name')}: leader does not reach its text shoulder"
        )
    chain = [segments[index] for index in best]
    rest = [segment for index, segment in enumerate(segments) if index not in best]
    return chain, rest


def within_chain(segment: tuple, chain: list) -> bool:
    """Collinear with chain strokes, and inside their extent: it prints as them."""
    along = [
        stroke
        for stroke in chain
        if math.dist(*stroke) > COLLINEAR_TOLERANCE
        and all(distance_to_line(stroke, end) <= COLLINEAR_TOLERANCE for end in segment)
    ]
    if not along:
        return False
    (x0, y0), (x1, y1) = along[0]
    length = math.dist((x0, y0), (x1, y1))
    ux, uy = (x1 - x0) / length, (y1 - y0) / length

    def at(point: tuple[float, float]) -> float:
        return (point[0] - x0) * ux + (point[1] - y0) * uy

    stations = [at(end) for stroke in along for end in stroke]
    low, high = min(stations), max(stations)
    return all(
        low - COLLINEAR_TOLERANCE <= at(end) <= high + COLLINEAR_TOLERANCE
        for end in segment
    )


def stray_leader_lines(record: Mapping[str, Any]) -> list[tuple[float, ...]]:
    """A one-arrow diameter's lines off its leader chain, as (x0, y0, x1, y1)."""
    chain, rest = leader_chain(record)
    return [
        (*segment[0], *segment[1])
        for segment in rest
        if not within_chain(segment, chain)
    ]


def shoulder_y(record: Mapping[str, Any]) -> float:
    """The y of a diameter's text shoulder, the last stroke of its leader chain."""
    chain, _rest = leader_chain(record)
    return chain[-1][0][1]


def diameter_seat_move(
    record: Mapping[str, Any],
    plan: tuple[float, float, float, float],
    side: int,
    *,
    level: bool,
) -> tuple[float, float]:
    """(dx, dy) seating a diameter's text a text height beside the plan, either
    at its native station height or with its shoulder on the centre height."""
    text = size_text_box(record)
    centre_y = (plan[1] + plan[3]) / 2.0
    current = shoulder_y(record) if level else float(record["pos"][1])
    shift = diameter_text_shift(text, plan, side, arrow_reach=arrow_reach(record, side))
    return shift, centre_y - current


def assert_diameter_ink(
    record: Mapping[str, Any],
    plan: tuple[float, float, float, float],
    side: int,
    *,
    label: str,
) -> None:
    """Text clear of the rim, every line on the leader, own arrowheads clear of
    the text, leader to text, in cell."""
    text = size_text_box(record)
    assert_diameter_text_clear(text, plan, side, label=label)
    stray = stray_leader_lines(record)
    if stray:
        raise RuntimeError(f"{label}: lines off its leader chain {stray!r}")
    assert_own_arrows_clear(record, text, label=label)
    ink = display_box(record["display"])
    x0, y0, x1, y1 = FREE_TOP_CELL
    if not (x0 <= ink.xmin and ink.xmax <= x1 and y0 <= ink.ymin and ink.ymax <= y1):
        raise RuntimeError(
            f"{label}: ink {ink!r} leaves the TOP cell {FREE_TOP_CELL!r}"
        )


def _assert_heights(
    displays: Mapping[str, Any],
    records: Mapping[str, Any],
    baseline: Mapping[str, Mapping[str, Any]],
) -> None:
    for name, geometry in assert_height_stations(records, baseline).items():
        if displays[name].OffsetText is not True:
            raise RuntimeError(f"{name}: native offset text was lost")
        assert_height_text_clear(
            geometry,
            TEXT_SIDES["free_front"][name],
            label=f"{supplier_spec.SKU} {name}",
        )
    struck = lines_through_own_text(records, TEXT_SIDES["free_front"])
    if struck:
        raise RuntimeError(
            f"{supplier_spec.SKU}: size text struck by its own line: {struck}"
        )


def _assert_diameters(
    records: Mapping[str, Any],
    plan: tuple[float, float, float, float],
    placement: PlanPlacement,
) -> None:
    for name, side in placement.sides.items():
        assert_diameter_ink(
            records[name], plan, side, label=f"{supplier_spec.SKU} {name}"
        )
    assert_plan_leaders(
        {name: _segments(records[name]) for name in placement.sides},
        plan,
        label=f"{supplier_spec.SKU} plan diameters",
    )
    struck = lines_through_own_text(records, placement.sides)
    if struck:
        raise RuntimeError(
            f"{supplier_spec.SKU}: size text struck by its own line: {struck}"
        )


def _seat_diameters(
    adapter: Any,
    displays: Mapping[str, Any],
    plan: tuple[float, float, float, float],
    placement: PlanPlacement,
) -> dict[str, Any]:
    """Move both texts to the placement; return the converged native snapshot.

    Every move is followed by a rebuild and a fresh read, the last one too, so
    a placement that settles on its final permitted move is accepted.
    """
    for moved in range(_SEAT_PASSES + 1):
        records = _size_records(adapter, displays)
        moves = {
            name: diameter_seat_move(
                records[name], plan, side, level=name in placement.level
            )
            for name, side in placement.sides.items()
        }
        if all(
            abs(dx) <= _SEATED_M and abs(dy) <= _SEATED_M for dx, dy in moves.values()
        ):
            return records
        if moved == _SEAT_PASSES:
            break
        for name, (dx, dy) in moves.items():
            _move_text(displays[name], records[name], dx, dy, label=name)
        rebuild_drawing(adapter, label=f"cylinder bank spring plan: {placement.label}")
    raise RuntimeError(f"text did not settle in {_SEAT_PASSES} moves")


def choose_plan_placement(
    adapter: Any,
    displays: Mapping[str, Any],
    plan: tuple[float, float, float, float],
) -> PlanPlacement:
    """The first ``PLAN_PLACEMENTS`` entry whose settled ink passes every guard."""
    rejected = []
    for placement in PLAN_PLACEMENTS:
        try:
            records = _seat_diameters(adapter, displays, plan, placement)
            _assert_diameters(records, plan, placement)
        except RuntimeError as error:
            rejected.append(f"{placement.label}: {error}")
            _telemetry.info(
                f"{supplier_spec.SKU}: plan placement rejected -- {rejected[-1]}"
            )
            continue
        _telemetry.info(
            f"{supplier_spec.SKU}: plan placement {placement.label!r} won "
            f"after {len(rejected)} rejected"
        )
        return placement
    raise RuntimeError(
        f"{supplier_spec.SKU}: no plan diameter placement passes its guards: {rejected}"
    )


@_telemetry.traced("drawing.cylinder_bank_spring.size_texts")
def place_size_texts(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> Callable[[], None]:
    """Move the four size texts off their lines; return their settled check."""
    displays = _size_displays(adapter, views)
    # Every height station is compared with this read, taken before any
    # position, offset or style change, after each stage below.
    records = _size_records(adapter, displays)
    baseline = height_stations(records)
    for name in TEXT_SIDES["free_top"]:
        set_near_side_diameter(
            displays[name].GetAnnotation(), f"{supplier_spec.SKU} {name}"
        )
    # Pin each height's dimension line at its own station before offset mode;
    # from then on SetPosition2 moves only the text (R48 washer sequence).
    anchors = {
        name: (
            sum(tip[0] for tip in geometry["tips"]) / 2.0,
            float(records[name]["pos"][1]),
        )
        for name, geometry in baseline.items()
    }
    for name, anchor in anchors.items():
        annotation = _early_bound(displays[name].GetAnnotation(), "IAnnotation")
        if not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: dimension line station was rejected")
    rebuild_drawing(adapter, label="cylinder bank spring height stations")
    assert_height_stations(_size_records(adapter, displays), baseline)
    for name, anchor in anchors.items():
        display = displays[name]
        display.OffsetText = True
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if display.OffsetText is not True or not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: native offset text was rejected")
    rebuild_drawing(adapter, label="cylinder bank spring offset height text")
    records = _size_records(adapter, displays)
    shifts = {}
    for name, geometry in assert_height_stations(records, baseline).items():
        shifts[name] = height_text_shift(geometry, TEXT_SIDES["free_front"][name])
        _move_text(displays[name], records[name], shifts[name], label=name)
    rebuild_drawing(adapter, label="cylinder bank spring height text shelves")
    _telemetry.info(
        f"{supplier_spec.SKU}: height texts moved "
        + ", ".join(f"{name} {dx * 1000:+.2f} mm" for name, dx in shifts.items())
    )
    _assert_heights(displays, _size_records(adapter, displays), baseline)
    plan = reference_bounds("free_top")
    placement = choose_plan_placement(adapter, displays, plan)

    def settled() -> None:
        current = _size_displays(adapter, views)
        snapshot = _size_records(adapter, current)
        _assert_heights(current, snapshot, baseline)
        _assert_diameters(snapshot, plan, placement)

    settled()
    return settled


def supplier_dimensions(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
    settled_checks: list[Callable[[], None]],
) -> None:
    supplier_disc_spring_dimensions(
        adapter,
        views,
        spec=SHEET_SPEC,
        reference_bounds=reference_bounds,
        settled_checks=settled_checks,
    )
    settled_checks.append(
        place_size_texts(adapter, views, reference_bounds=reference_bounds)
    )


async def build(adapter: Any) -> dict[str, str]:
    settled_checks = []
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM,
        stock_configuration=SUPPLIER_DIAGRAM_CONFIGURATION,
        prepare_views=partial(prepare_supplier_disc_diagram, spec=SHEET_SPEC),
        supplier_reference_features=supplier_disc_reference_features(SHEET_SPEC),
        include_right=False,
        stock_caption="SUPPLIER NOMINAL DIMENSION DIAGRAM — NOT PART SHAPE",
        supplier_margins={
            "free_front": (0.035, 0.0, 0.035, 0.0),
            "free_top": (0.040, 0.0, 0.040, 0.0),
        },
        supplier_dimensions=partial(supplier_dimensions, settled_checks=settled_checks),
        installed_caption="INSTALLED ENVELOPE",
        settled_checks=settled_checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
