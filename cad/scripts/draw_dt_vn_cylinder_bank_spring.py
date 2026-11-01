"""Supplier nominal dimension diagrams beside the installed 9714K392 envelope.

The sheet prints only replacement sizes: ID, OD and free height. The strip
thickness is not one: SKU 9714K392 defines it, and its 0.127 mm strip
printed as a doubled hairline through the FRONT envelope (machinist review of
4e46b502). The part keeps its strip and catalogue load-point gauge sketches
(compressed height and deflection at 1.5 lb), which this sheet neither
shows nor dimensions; the 0.95 mm set gap governs the installed preload.

The shared disc diagram shows and dimensions all four sizes, so this sheet
shows only the envelope and plan sketches (``SHEET_FEATURES``) and imports
their three dimensions itself, under the same supplier-reference contract.
The diagrams are construction geometry, drawn solid and thick for this
SLDDRW (the music wire's ``_construction_curves_as_outline``): the default
construction font printed them as grey dash-gap lines.

At 2:1 the diagrams are smaller than their text, so ``place_size_texts``
moves only presentation, each text by one native position write at a fixed
place computed from the spec sizes, the view scale and the diagram centre
(``size_text_positions``): the free height takes native offset text
shelved beyond its own lines (the R48 washer pattern) at a station 10 mm off
the envelope, and the diameters take one near-side arrow with their text
clear of the OD rim and 2 mm (``ARROW_TEXT_CLEARANCE_M``) beyond the outer
reach of their own arrowhead. The shared finaliser's checks and the layout
audit judge the settled sheet.
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
from _drawing_hidden_sketches import _show_hidden_owners, curate_view_dimensions
from _drawing_leaders import set_near_side_diameter
from _layout_geometry import ARROW_TEXT_CLEARANCE_M
from _part_properties import part_drawing_unit
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    build_supplier_spring_drawing,
    reacquire_supplier_dimensions,
)
from _supplier_spring_reference import SUPPLIER_DIAGRAM_CONFIGURATION
from _supplier_wire_stock_drawing import _construction_curves_as_outline
import dt_vn_cylinder_bank_spring_spec as supplier_spec
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from vn_disc_spring_supplier_stock import (
    SUPPLIER_DIMENSION_NAMES,
    SUPPLIER_DIMENSIONS_BY_FEATURE,
    supplier_diagram_extents,
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
FREE_HEIGHT_NAME = SUPPLIER_DIMENSION_NAMES["FREE_HEIGHT"]
# The diagram sketches this sheet shows: the OD x free-height envelope and
# the ID/OD plan. Not the strip (``DiscSupplierStrip``).
SHEET_FEATURES = {
    "free_front": ("DiscSupplierHeight",),
    "free_top": ("DiscSupplierPlan",),
}
# The printed sizes, by view: (spec field, side of the diagram, -1 left).
PRINTED = {
    "free_front": {"FREE_HEIGHT": 1},
    "free_top": {"ID": -1, "OD": 1},
}
TEXT_SIDES = {
    key: {SUPPLIER_DIMENSION_NAMES[field]: side for field, side in sizes.items()}
    for key, sizes in PRINTED.items()
}
# The free height's dimension line, this far off the envelope; the
# diameters import this far off the plan, where the shared disc placement
# imported them, before their style and text move.
HEIGHT_STATION_M = 0.010
DIAMETER_IMPORT_M = 0.018
# Ruling (release manager, 2026-10-27, applying the owner's rule that a vn
# sheet carries only replacement-critical sizes and that simplifying beats
# adding native machinery; PR #1896): the size texts take these fixed,
# spec-derived places, and the sheet has no runtime own-ink, own-arrowhead or
# settled-clearance check. The shared finaliser and layout audit stay the
# guards. Natively measured own-arrowhead-to-text clearance at these places:
# 2.73-3.23 mm (run 20261027T155633803Z-efb1e66b, 380ee131).
# Native geometry of this sheet's size dimensions, identical on runs
# fa43a1a5 (ec339f3d) and ae121732 (d179e35b):
# the witnesses run 1 mm past the station, away from the diagram;
WITNESS_OVERSHOOT_M = 0.001
# every arrowhead is 3.556 mm long and 0.762 mm wide (GetArrowHeadAtIndex2);
ARROW_LENGTH_M = 0.003556
ARROW_WIDTH_M = 0.000762
# cap height, and the printed width of "(.050 in)" and of
# "(Ø.385 ±.010 in)" / "(Ø.500 ±.010 in)" (their runs' native widths).
TEXT_HEIGHT_M = 0.0035
HEIGHT_TEXT_WIDTH_M = 0.0201493
DIAMETER_TEXT_WIDTH_M = 0.0030139 + 0.0052784 + 0.0300417


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


def height_station(
    bounds: tuple[float, float, float, float], scale: float, side: int
) -> tuple[float, float]:
    """The free height's dimension-line station: ``HEIGHT_STATION_M`` off
    the OD-wide envelope, at its centre height."""
    cx, cy = _centre(bounds)
    return cx + side * (supplier_spec.OD / 2000.0 * scale + HEIGHT_STATION_M), cy


def size_text_positions(
    bounds: Mapping[str, tuple[float, float, float, float]],
    scales: Mapping[str, float],
) -> dict[str, tuple[float, float]]:
    """Each size text's native position (its centre), from the spec sizes,
    the view scale and each diagram's native centre (``bounds``)."""
    positions = {}
    for name, side in TEXT_SIDES["free_front"].items():
        station, cy = height_station(bounds["free_front"], scales["free_front"], side)
        near = station + side * height_text_gap()
        positions[name] = (near + side * HEIGHT_TEXT_WIDTH_M / 2.0, cy)
    cx, cy = _centre(bounds["free_top"])
    for name, side in TEXT_SIDES["free_top"].items():
        near = cx + side * diameter_text_gap(name, scales["free_top"])
        positions[name] = (near + side * DIAMETER_TEXT_WIDTH_M / 2.0, cy)
    return positions


def prepare_diagrams(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> tuple[Callable[[], None], ...]:
    """Solid construction curves; show only ``SHEET_FEATURES`` before the fit.

    The shared disc preparation's contract for the sketches this sheet
    shows: each saved hidden, and each view's ink exactly the nominal
    diagram (the strip lies inside the envelope, so the extents are the
    shared ones).
    """
    _construction_curves_as_outline(adapter)
    for key, owners in SHEET_FEATURES.items():
        shown = _show_hidden_owners(
            adapter, views[key], owners, view_label=f"{supplier_spec.SKU} nominal {key}"
        )
        if set(shown) != set(owners):
            raise RuntimeError(
                f"{supplier_spec.SKU} {key}: diagram owners are not saved hidden"
            )
    expected_extents = supplier_diagram_extents(SHEET_SPEC)

    def check_rebuilt_diagram_extents() -> None:
        for key in SHEET_FEATURES:
            x0, y0, x1, y1 = reference_bounds(key)
            if not all(
                math.isclose(actual, expected / 1000.0, rel_tol=0.0, abs_tol=1e-7)
                for actual, expected in zip(
                    (x1 - x0, y1 - y0), expected_extents[key], strict=True
                )
            ):
                raise RuntimeError(
                    f"{supplier_spec.SKU} {key}: native diagram ink differs from "
                    f"nominal {expected_extents[key]} mm"
                )

    return (check_rebuilt_diagram_extents,)


def _owners(names: Mapping[str, Any]) -> dict[str, str]:
    return {
        name: next(
            feature
            for feature, owned in SUPPLIER_DIMENSIONS_BY_FEATURE.items()
            if name in owned
        )
        for name in names
    }


def _size_displays(adapter: Any, views: Mapping[str, Any]) -> dict[str, Any]:
    return reacquire_supplier_dimensions(
        adapter,
        {key: views[key] for key in TEXT_SIDES},
        expected={key: _owners(sides) for key, sides in TEXT_SIDES.items()},
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
    """Move the three size texts off their lines, one position write each.

    The free height's annotation still sits at its station, which offset
    mode keeps as the dimension line's; the write then moves only the text.
    The shared finaliser's rebuild settles all three.
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


def _import_sizes(
    adapter: Any,
    views: Mapping[str, Any],
    stations: Mapping[str, tuple[float, float]],
) -> list[tuple[str, str, dict[str, Any], str]]:
    """The printed sizes as native supplier reference dimensions, each at
    its station: (view key, name, reference contract, spec field)."""
    references = []
    for key, sizes in PRINTED.items():
        fields = {SUPPLIER_DIMENSION_NAMES[field]: field for field in sizes}
        imported = curate_view_dimensions(
            adapter,
            views[key],
            keep={name: stations[name] for name in fields},
            view_label=f"{supplier_spec.SKU} supplier {key}",
            dimensions_by_feature=SUPPLIER_DIMENSIONS_BY_FEATURE,
        )
        configuration = str(views[key].ReferencedConfiguration)
        if configuration != SUPPLIER_DIAGRAM_CONFIGURATION:
            raise RuntimeError(
                f"{supplier_spec.SKU} {key}: nominal diagram uses wrong configuration"
            )
        for annotation in imported:
            name = dimension_name(adapter, annotation)
            field = fields[name]
            arguments = {
                "label": f"{supplier_spec.SKU} supplier {field.lower()}",
                "expected_mm": float(getattr(supplier_spec, field)),
                "units": supplier_spec.SUPPLIER_DRAWING_UNITS,
                "configuration": configuration,
                "precision": supplier_spec.SUPPLIER_DRAWING_PRECISION[field],
                "presentation": "diameter" if field in ("ID", "OD") else "length",
            }
            supplier_reference_dimension(
                adapter,
                _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension"),
                **arguments,
            )
            references.append((key, name, arguments, field))
    return references


def _assert_source_band(display: Any, field: str) -> None:
    """The source tolerance band the shared disc check reads: ID/OD carry
    the catalogue's symmetric band at three places, free height none."""
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    band = getattr(supplier_spec, f"{field}_BAND", None)
    if band is None:
        if int(tolerance.Type) != 0:
            raise RuntimeError(
                f"{supplier_spec.SKU} {field}: unprovided source band appeared"
            )
        return
    upper, lower = band
    expected_type = 4 if math.isclose(upper, -lower, abs_tol=1e-12) else 2
    if int(tolerance.Type) != expected_type or not all(
        math.isclose(actual, value / 1000.0, rel_tol=0.0, abs_tol=1e-9)
        for actual, value in (
            (float(tolerance.GetMinValue()), lower),
            (float(tolerance.GetMaxValue()), upper),
        )
    ):
        raise RuntimeError(f"{supplier_spec.SKU} {field}: native source band changed")
    if int(display.GetPrimaryTolPrecision2()) != 3:
        raise RuntimeError(
            f"{supplier_spec.SKU} {field}: source band needs three places"
        )


def supplier_dimensions(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
    settled_checks: list[Callable[[], None]],
) -> None:
    """Import the printed sizes, place their texts, and register the shared
    disc diagram's settled reference check for them, over the whole sheet:
    the installed view carries no dimension."""
    bounds = {key: reference_bounds(key) for key in PRINTED}
    x0, y0, x1, y1 = bounds["free_top"]
    cy = (y0 + y1) / 2.0
    stations = {
        FREE_HEIGHT_NAME: height_station(
            bounds["free_front"], _view_scale(views["free_front"]), 1
        ),
        ID_NAME: (x0 - DIAMETER_IMPORT_M, cy),
        OD_NAME: (x1 + DIAMETER_IMPORT_M, cy),
    }
    references = _import_sizes(adapter, views, stations)
    configurations = {
        key: str(view.ReferencedConfiguration) for key, view in views.items()
    }
    expected = {key: _owners(TEXT_SIDES.get(key, {})) for key in views}
    place_size_texts(adapter, views, reference_bounds=reference_bounds)

    def check_settled_references() -> None:
        displays = reacquire_supplier_dimensions(
            adapter, views, expected=expected, configurations=configurations
        )
        for _key, name, arguments, field in references:
            display = displays[name]
            assert_supplier_reference_dimension(adapter, display, **arguments)
            assert_supplier_configuration_value(
                display,
                arguments["configuration"],
                arguments["expected_mm"],
                label=name,
            )
            _assert_source_band(display, field)

    settled_checks.append(check_settled_references)


async def build(adapter: Any) -> dict[str, str]:
    settled_checks = []
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM,
        stock_configuration=SUPPLIER_DIAGRAM_CONFIGURATION,
        prepare_views=prepare_diagrams,
        supplier_reference_features=SHEET_FEATURES,
        include_right=False,
        stock_caption="SUPPLIER NOMINAL DIMENSION DIAGRAM — NOT PART SHAPE",
        supplier_margins={
            "free_front": (0.035, 0.0, 0.035, 0.0),
            "free_top": (0.040, 0.0, 0.040, 0.0),
        },
        supplier_dimensions=partial(supplier_dimensions, settled_checks=settled_checks),
        installed_caption="INSTALLED ENVELOPE",
        settled_checks=settled_checks,
        unit=part_drawing_unit("dt-vn-cylinder-bank-spring"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
