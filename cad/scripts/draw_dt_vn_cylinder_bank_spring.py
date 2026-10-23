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
near-side arrow with their text a text height clear of the OD rim.

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
    dimension_segments,
    distance_to_box,
    distance_to_line,
    set_near_side_diameter,
)
from _layout_audit import (
    annotation_geometry,
    calibrate_sheet_advance,
    display_box,
    find_lines_through_own_text,
)
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_disc_spring_drawing import (
    prepare_supplier_disc_diagram,
    supplier_disc_reference_features,
    supplier_disc_spring_dimensions,
)
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
_STATION_FIELDS = ("tips", "witnesses", "physical_lines")
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
    text: Any, plan: tuple[float, float, float, float], side: int
) -> float:
    """Sheet x move that leaves ``diameter_air`` between text and plan ink."""
    air = diameter_air(text) + PLACE_SETTLE_M
    if side < 0:
        return plan[0] - air - text.xmax
    return plan[2] + air - text.xmin


def assert_diameter_text_clear(
    text: Any, plan: tuple[float, float, float, float], side: int, *, label: str
) -> None:
    gap = plan[0] - text.xmax if side < 0 else text.xmin - plan[2]
    if not gap >= diameter_air(text):
        raise RuntimeError(
            f"{label}: text is {gap * 1000:.2f} mm from the OD rim, under a text height"
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


def stations_match(prior: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    return all(
        len(prior[field]) == len(current[field])
        and all(
            len(before) == len(after)
            and all(abs(a - b) <= 1e-5 for a, b in zip(before, after, strict=True))
            for before, after in zip(prior[field], current[field], strict=True)
        )
        for field in _STATION_FIELDS
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
        or not all(float(row.get("w") or 0.0) > 0.0 for row in texts)
    ):
        raise RuntimeError(f"{label}: no measured native text/position: {errors!r}")
    return record


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
    return {
        name: _text_record(adapter, displays[name], label=name)
        for sides in TEXT_SIDES.values()
        for name in sides
    }


def _segments(record: Mapping[str, Any]) -> list[tuple[tuple[float, float], ...]]:
    return [
        ((float(line[4]), float(line[5])), (float(line[7]), float(line[8])))
        for line in record["display"].get("lines") or ()
    ]


def leader_chain(record: Mapping[str, Any]) -> tuple[list, list]:
    """A one-arrow diameter's lines as (longest simple path from the arrow tip, rest)."""
    arrows = record["display"].get("arrows") or ()
    if len(arrows) != 1:
        raise RuntimeError(
            f"{record.get('name')}: near-side diameter has {len(arrows)} arrows"
        )
    segments = _segments(record)
    best: list[int] = []

    def walk(point: tuple[float, float], used: list[int]) -> None:
        nonlocal best
        if len(used) > len(best):
            best = list(used)
        for index, (a, b) in enumerate(segments):
            if index in used:
                continue
            if math.dist(a, point) <= _JOIN_M:
                walk(b, [*used, index])
            elif math.dist(b, point) <= _JOIN_M:
                walk(a, [*used, index])

    walk((float(arrows[0][0]), float(arrows[0][1])), [])
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
    """The y of a diameter's horizontal shoulder: the longest level chain stroke."""
    chain, _rest = leader_chain(record)
    level = [stroke for stroke in chain if abs(stroke[0][1] - stroke[1][1]) <= 1e-7]
    if not level:
        raise RuntimeError(f"{record.get('name')}: leader has no horizontal shoulder")
    return max(level, key=lambda stroke: math.dist(*stroke))[0][1]


def diameter_seat_move(
    record: Mapping[str, Any],
    plan: tuple[float, float, float, float],
    side: int,
    *,
    level: bool,
) -> tuple[float, float]:
    """(dx, dy) seating a diameter's text a text height beside the plan, either
    at its native station height or with its shoulder on the centre height."""
    text = display_box({"texts": record["display"]["texts"]})
    centre_y = (plan[1] + plan[3]) / 2.0
    current = shoulder_y(record) if level else float(record["pos"][1])
    return diameter_text_shift(text, plan, side), centre_y - current


def assert_diameter_ink(
    record: Mapping[str, Any],
    plan: tuple[float, float, float, float],
    side: int,
    *,
    label: str,
) -> None:
    """Text clear of the rim, every line on the leader, leader to text, in cell."""
    text = display_box({"texts": record["display"]["texts"]})
    assert_diameter_text_clear(text, plan, side, label=label)
    stray = stray_leader_lines(record)
    if stray:
        raise RuntimeError(f"{label}: lines off its leader chain {stray!r}")
    chain, _rest = leader_chain(record)
    box = (text.xmin, text.ymin, text.xmax, text.ymax)
    if (
        not chain
        or min(distance_to_box(stroke, box) for stroke in chain) > _SHOULDER_REACH_M
    ):
        raise RuntimeError(f"{label}: leader does not reach its text")
    ink = display_box(record["display"])
    x0, y0, x1, y1 = FREE_TOP_CELL
    if not (x0 <= ink.xmin and ink.xmax <= x1 and y0 <= ink.ymin and ink.ymax <= y1):
        raise RuntimeError(
            f"{label}: ink {ink!r} leaves the TOP cell {FREE_TOP_CELL!r}"
        )


def _assert_heights(
    adapter: Any,
    displays: Mapping[str, Any],
    stations: Mapping[str, Mapping[str, Any]],
) -> None:
    records = _size_records(adapter, displays)
    for name, side in TEXT_SIDES["free_front"].items():
        geometry = supplier_top_text_geometry(records[name], horizontal=False)
        if displays[name].OffsetText is not True or not stations_match(
            stations[name], geometry
        ):
            raise RuntimeError(f"{name}: offset text moved its native lines")
        assert_height_text_clear(geometry, side, label=f"{supplier_spec.SKU} {name}")
    struck = lines_through_own_text(records, TEXT_SIDES["free_front"])
    if struck:
        raise RuntimeError(
            f"{supplier_spec.SKU}: size text struck by its own line: {struck}"
        )


def _assert_diameters(
    adapter: Any,
    displays: Mapping[str, Any],
    plan: tuple[float, float, float, float],
    placement: PlanPlacement,
) -> None:
    records = _size_records(adapter, displays)
    for name, side in placement.sides.items():
        assert_diameter_ink(
            records[name], plan, side, label=f"{supplier_spec.SKU} {name}"
        )
    assert_plan_leaders(
        {
            name: dimension_segments(displays[name].GetAnnotation())
            for name in placement.sides
        },
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
) -> None:
    """Move both texts to the placement, re-reading after each rebuild."""
    for _ in range(_SEAT_PASSES):
        moves = {}
        for name, side in placement.sides.items():
            record = _text_record(adapter, displays[name], label=name)
            moves[name] = (
                record,
                diameter_seat_move(record, plan, side, level=name in placement.level),
            )
        if all(
            abs(dx) <= _SEATED_M and abs(dy) <= _SEATED_M
            for _record, (dx, dy) in moves.values()
        ):
            return
        for name, (record, (dx, dy)) in moves.items():
            _move_text(displays[name], record, dx, dy, label=name)
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
            _seat_diameters(adapter, displays, plan, placement)
            _assert_diameters(adapter, displays, plan, placement)
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


def place_size_texts(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> Callable[[], None]:
    """Move the four size texts off their lines; return their settled check."""
    displays = _size_displays(adapter, views)
    for name in TEXT_SIDES["free_top"]:
        set_near_side_diameter(
            displays[name].GetAnnotation(), f"{supplier_spec.SKU} {name}"
        )
    # Pin each height's dimension line at its own station before offset mode;
    # from then on SetPosition2 moves only the text (R48 washer sequence).
    anchors = {}
    for name in TEXT_SIDES["free_front"]:
        record = _text_record(adapter, displays[name], label=name)
        tips = supplier_top_text_geometry(record, horizontal=False)["tips"]
        anchors[name] = (sum(tip[0] for tip in tips) / 2.0, float(record["pos"][1]))
        annotation = _early_bound(displays[name].GetAnnotation(), "IAnnotation")
        if not annotation.SetPosition2(*anchors[name], 0.0):
            raise RuntimeError(f"{name}: dimension line station was rejected")
    rebuild_drawing(adapter, label="cylinder bank spring height stations")
    for name, anchor in anchors.items():
        display = displays[name]
        display.OffsetText = True
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if display.OffsetText is not True or not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: native offset text was rejected")
    rebuild_drawing(adapter, label="cylinder bank spring offset height text")
    plan = reference_bounds("free_top")
    shifts = {}
    for name, side in TEXT_SIDES["free_front"].items():
        record = _text_record(adapter, displays[name], label=name)
        geometry = supplier_top_text_geometry(record, horizontal=False)
        shifts[name] = height_text_shift(geometry, side)
        _move_text(displays[name], record, shifts[name], label=name)
    rebuild_drawing(adapter, label="cylinder bank spring height text shelves")
    stations = {
        name: supplier_top_text_geometry(
            _text_record(adapter, displays[name], label=name), horizontal=False
        )
        for name in TEXT_SIDES["free_front"]
    }
    _telemetry.info(
        f"{supplier_spec.SKU}: height texts moved "
        + ", ".join(f"{name} {dx * 1000:+.2f} mm" for name, dx in shifts.items())
    )
    _assert_heights(adapter, displays, stations)
    placement = choose_plan_placement(adapter, displays, plan)

    def settled() -> None:
        current = _size_displays(adapter, views)
        _assert_heights(adapter, current, stations)
        _assert_diameters(adapter, current, plan, placement)

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
