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

Native run 86053b8e then printed a stray SupplierOD line: from the OD rim at
the text's height, parallel to its leader and through its own "(". The same
line is in the main renders of the sibling 9714K24 and 9715K43 ODs, so it is
not the text move. [INFERENCE: SolidWorks's arc extension of the circle's
closed arc.] The diameters turn ``ArcExtensionLineOrOppositeSide`` off, and
the settled check refuses any size line through its own text (the layout
audit's ``find_lines_through_own_text``) and any diameter line that is not
on its one leader chain from the arrow.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
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
    assert_leaders_clear,
    dimension_segments,
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
        lands_within={name: (0.8 * radius, 1.2 * radius) for name, radius in radii.items()},
        label=label,
    )


def stations_match(prior: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    return all(
        len(prior[field]) == len(current[field])
        and all(
            len(before) == len(after)
            and all(
                abs(a - b) <= 1e-5 for a, b in zip(before, after, strict=True)
            )
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
        errors or record is None or int(record.get("type", 0)) != 4
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


def _move_text(display: Any, record: Mapping[str, Any], dx: float, *, label: str) -> None:
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    x, y = (float(value) for value in record["pos"][:2])
    if not annotation.SetPosition2(x + dx, y, 0.0):
        raise RuntimeError(f"{label}: text placement was rejected")


def lines_through_own_text(records: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """The layout audit's own-text finder over these dimensions' native ink."""
    advance = calibrate_sheet_advance(tuple(records.values()))
    sheet = SimpleNamespace(
        name=supplier_spec.SKU,
        annotations=[
            annotation_geometry(record, owner="view", advance=advance)
            for record in records.values()
        ],
    )
    return [finding.detail for finding in find_lines_through_own_text(sheet)]


def stray_leader_lines(record: Mapping[str, Any]) -> list[tuple[float, ...]]:
    """A one-arrow diameter's lines that are not its chain from the arrow tip."""
    data = record["display"]
    arrows = data.get("arrows") or ()
    if len(arrows) != 1:
        raise RuntimeError(f"{record.get('name')}: near-side diameter has {len(arrows)} arrows")
    lines = [
        (float(line[4]), float(line[5]), float(line[7]), float(line[8]))
        for line in data.get("lines") or ()
    ]
    reached = [(float(arrows[0][0]), float(arrows[0][1]))]
    chained = True
    while chained:
        chained = False
        for line in list(lines):
            ends = ((line[0], line[1]), (line[2], line[3]))
            if any(math.dist(end, point) <= 1e-5 for end in ends for point in reached):
                lines.remove(line)
                reached.extend(ends)
                chained = True
    return lines


def _assert_size_texts(
    adapter: Any,
    displays: Mapping[str, Any],
    plan: tuple[float, float, float, float],
    stations: Mapping[str, Mapping[str, Any]],
) -> None:
    records = {
        name: _text_record(adapter, displays[name], label=name)
        for sides in TEXT_SIDES.values()
        for name in sides
    }
    for name, side in TEXT_SIDES["free_front"].items():
        display = displays[name]
        geometry = supplier_top_text_geometry(records[name], horizontal=False)
        if display.OffsetText is not True or not stations_match(stations[name], geometry):
            raise RuntimeError(f"{name}: offset text moved its native lines")
        assert_height_text_clear(geometry, side, label=f"{supplier_spec.SKU} {name}")
    groups = {}
    for name, side in TEXT_SIDES["free_top"].items():
        text = display_box({"texts": records[name]["display"]["texts"]})
        assert_diameter_text_clear(text, plan, side, label=f"{supplier_spec.SKU} {name}")
        if displays[name].ArcExtensionLineOrOppositeSide is not False:
            raise RuntimeError(f"{name}: arc extension line came back")
        stray = stray_leader_lines(records[name])
        if stray:
            raise RuntimeError(f"{name}: lines off its leader chain {stray!r}")
        groups[name] = dimension_segments(displays[name].GetAnnotation())
    assert_plan_leaders(groups, plan, label=f"{supplier_spec.SKU} plan diameters")
    struck = lines_through_own_text(records)
    if struck:
        raise RuntimeError(f"{supplier_spec.SKU}: size text struck by its own line: {struck}")


def place_size_texts(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> Callable[[], None]:
    """Move the four size texts off their lines; return their settled check."""
    displays = _size_displays(adapter, views)
    for name in TEXT_SIDES["free_top"]:
        set_near_side_diameter(displays[name].GetAnnotation(), f"{supplier_spec.SKU} {name}")
        displays[name].ArcExtensionLineOrOppositeSide = False
        if displays[name].ArcExtensionLineOrOppositeSide is not False:
            raise RuntimeError(f"{name}: arc extension line was not turned off")
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
    for name, side in TEXT_SIDES["free_top"].items():
        record = _text_record(adapter, displays[name], label=name)
        text = display_box({"texts": record["display"]["texts"]})
        shifts[name] = diameter_text_shift(text, plan, side)
        _move_text(displays[name], record, shifts[name], label=name)
    rebuild_drawing(adapter, label="cylinder bank spring size text shelves")
    stations = {
        name: supplier_top_text_geometry(
            _text_record(adapter, displays[name], label=name), horizontal=False
        )
        for name in TEXT_SIDES["free_front"]
    }
    _telemetry.info(
        f"{supplier_spec.SKU}: size texts moved "
        + ", ".join(f"{name} {dx * 1000:+.2f} mm" for name, dx in shifts.items())
    )

    def settled() -> None:
        _assert_size_texts(adapter, _size_displays(adapter, views), plan, stations)

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
        adapter, views, spec=SHEET_SPEC, reference_bounds=reference_bounds,
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
