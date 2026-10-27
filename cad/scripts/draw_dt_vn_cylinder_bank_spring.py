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
moves only presentation, each text by one native position write at a fixed
place computed from the spec sizes, the view scale and the diagram centre
(``size_text_positions``): the heights take native offset text shelved beyond
their own lines (the R48 washer pattern), and the diameters take one
near-side arrow with their text clear of the OD rim and 2 mm
(``ARROW_TEXT_CLEARANCE_M``) beyond the outer reach of their own arrowhead.
The shared finaliser's checks and the layout audit judge the settled sheet.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from functools import partial
from types import SimpleNamespace
import sys
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_leaders import set_near_side_diameter
from _layout_geometry import ARROW_TEXT_CLEARANCE_M
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_disc_spring_drawing import (
    prepare_supplier_disc_diagram,
    supplier_disc_reference_features,
    supplier_disc_spring_dimensions,
)
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
THICKNESS_NAME = SUPPLIER_DIMENSION_NAMES["THICKNESS"]
FREE_HEIGHT_NAME = SUPPLIER_DIMENSION_NAMES["FREE_HEIGHT"]
# Each size keeps the side of its diagram the shared placement gave it:
# -1 left, +1 right.
TEXT_SIDES = {
    "free_front": {THICKNESS_NAME: -1, FREE_HEIGHT_NAME: 1},
    "free_top": {ID_NAME: -1, OD_NAME: 1},
}
# Native geometry of this sheet's size dimensions, identical on runs
# fa43a1a5 (ec339f3d) and ae121732 (d179e35b):
# the shared disc placement's height station, 18 mm beyond the diagram;
HEIGHT_STATION_M = 0.018
# the witnesses run 1 mm past that station, away from the diagram;
WITNESS_OVERSHOOT_M = 0.001
# every arrowhead is 3.556 mm long and 0.762 mm wide (GetArrowHeadAtIndex2);
ARROW_LENGTH_M = 0.003556
ARROW_WIDTH_M = 0.000762
# cap height, and the printed width of "(0.005 in)" / "(0.050 in)" and of
# "(Ø0.385 ±0.010 in)" / "(Ø0.500 ±0.010 in)" (their runs' native widths).
TEXT_HEIGHT_M = 0.0035
HEIGHT_TEXT_WIDTH_M = 0.0227354
DIAMETER_TEXT_WIDTH_M = 0.0030139 + 0.0052784 + 0.0352139


def _centre(bounds: tuple[float, float, float, float]) -> tuple[float, float]:
    x0, y0, x1, y1 = bounds
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def height_text_gap() -> float:
    """Station to the near edge of a height's shelved text: past its own
    witnesses by the shelf's clear gap."""
    return WITNESS_OVERSHOOT_M + CLEAR_GAP_M + PLACE_SETTLE_M


def diameter_text_gap(name: str, scale: float) -> float:
    """Plan centre to the near edge of a diameter's text: a text height clear
    of the OD rim, and ``ARROW_TEXT_CLEARANCE_M`` beyond the outer reach of its
    own arrowhead, whichever is farther. The arrowhead sits outside its rim,
    so it reaches at most its length plus half its width past the rim,
    whatever angle its leader takes."""
    radius = {ID_NAME: supplier_spec.ID, OD_NAME: supplier_spec.OD}[name] / 2000.0
    od_rim = supplier_spec.OD / 2000.0 * scale
    return max(
        od_rim + TEXT_HEIGHT_M + PLACE_SETTLE_M,
        arrow_reach(radius * scale) + ARROW_TEXT_CLEARANCE_M + PLACE_SETTLE_M,
    )


def arrow_reach(rim: float) -> float:
    """Farthest an outside arrowhead on a rim at ``rim`` reaches from centre."""
    return rim + ARROW_LENGTH_M + ARROW_WIDTH_M / 2.0


def size_text_positions(
    bounds: Mapping[str, tuple[float, float, float, float]],
    scales: Mapping[str, float],
) -> dict[str, tuple[float, float]]:
    """Each size text's native position (its centre), from the spec sizes,
    the view scale and each diagram's native centre (``bounds``)."""
    positions = {}
    cx, cy = _centre(bounds["free_front"])
    half_od = supplier_spec.OD / 2000.0 * scales["free_front"]
    for name, side in TEXT_SIDES["free_front"].items():
        station = cx + side * (half_od + HEIGHT_STATION_M)
        near = station + side * height_text_gap()
        positions[name] = (near + side * HEIGHT_TEXT_WIDTH_M / 2.0, cy)
    cx, cy = _centre(bounds["free_top"])
    for name, side in TEXT_SIDES["free_top"].items():
        near = cx + side * diameter_text_gap(name, scales["free_top"])
        positions[name] = (near + side * DIAMETER_TEXT_WIDTH_M / 2.0, cy)
    return positions


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


def _view_scale(view: Any) -> float:
    numerator, denominator = (
        float(value) for value in _early_bound(view, "IView").ScaleRatio
    )
    return numerator / denominator


@_telemetry.traced("drawing.cylinder_bank_spring.size_texts")
def place_size_texts(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> None:
    """Move the four size texts off their lines, one position write each.

    The heights' annotation still sits at its shared station, which offset
    mode keeps as the dimension line's; the write then moves only the text.
    The shared finaliser's rebuild settles all four.
    """
    displays = _size_displays(adapter, views)
    positions = size_text_positions(
        {key: reference_bounds(key) for key in TEXT_SIDES},
        {key: _view_scale(views[key]) for key in TEXT_SIDES},
    )
    for name in TEXT_SIDES["free_front"]:
        displays[name].OffsetText = True
    for name in TEXT_SIDES["free_top"]:
        set_near_side_diameter(
            displays[name].GetAnnotation(), f"{supplier_spec.SKU} {name}"
        )
    for name, (x, y) in positions.items():
        annotation = _early_bound(displays[name].GetAnnotation(), "IAnnotation")
        if not annotation.SetPosition2(x, y, 0.0):
            raise RuntimeError(
                f"{supplier_spec.SKU} {name}: text placement was rejected"
            )
    _telemetry.info(
        f"{supplier_spec.SKU}: size texts placed "
        + ", ".join(
            f"{name} ({x * 1000:.2f}, {y * 1000:.2f}) mm"
            for name, (x, y) in positions.items()
        )
    )


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
    place_size_texts(adapter, views, reference_bounds=reference_bounds)


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
