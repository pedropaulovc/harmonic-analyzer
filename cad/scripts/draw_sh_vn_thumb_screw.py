"""Create the shared purchased reference sheet for McMaster 91882A221."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from math import dist, isfinite
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, iter_views

import _config
import _telemetry
from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import (
    assert_supplier_view_fits,
    build_purchased_fastener_drawing,
    fastener_view_cells,
    view_band_bottom,
)
from _session import run_build
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_screw_reference_names import FEATURE_BY_PLANE
import sh_vn_thumb_screw_spec as supplier


SPEC = DRAWINGS_BY_NAME["sh_vn_thumb_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4-40 x 7/16 RAISED KNURLED-HEAD THUMB SCREW"
# Keep the lane plan and pre-fit budget together. The old 14 mm bottom
# reserve left only 4 mm beyond its 10 mm thread-length lane; native ink
# crossed the 77 mm cell floor by 7.5895 mm on abe9bb7a3bd8.
_SUPPLIER_LANES = {
    "head_height": ("top", 0.009),
    "collar_height": ("top", 0.020),
    "thread_length": ("bottom", 0.010),
    "head_diameter": ("left", 0.020),
    "collar_diameter": ("right", 0.027),
    "thread_diameter": ("right", 0.012),
}
# Sheet-space text/arrow room beyond each line, independent of view scale.
_SUPPLIER_TEXT_ROOM = {"left": 0.014, "bottom": 0.014, "right": 0.018, "top": 0.014}
_POSITION_TOLERANCE_M = 1e-5  # Same 10 um as imported-dimension placement readback.
SUPPLIER_MARGINS = {
    "*Front": tuple(
        max(offset for side, offset in _SUPPLIER_LANES.values() if side == edge)
        + _SUPPLIER_TEXT_ROOM[edge]
        for edge in ("left", "bottom", "right", "top")
    )
}


def _supplier_positions(
    outline: Sequence[float], axis: Sequence[tuple[float, float]]
) -> dict[str, tuple[float, float]]:
    """Route against the actual fitted outline, not a nominal scaled radius."""
    if (
        len(outline) != 4
        or len(axis) != 4
        or not all(isfinite(value) for value in outline)
        or not all(len(point) == 2 and all(map(isfinite, point)) for point in axis)
        or outline[0] >= outline[2]
        or outline[1] >= outline[3]
    ):
        raise RuntimeError("thumb supplier layout has no finite fitted geometry")
    if max(point[1] for point in axis) - min(point[1] for point in axis) > 1e-7:
        raise RuntimeError("thumb Front view does not project its axis horizontally")
    center_y = axis[0][1]
    centers = {
        "head_height": ((axis[0][0] + axis[1][0]) / 2.0, center_y),
        "collar_height": ((axis[1][0] + axis[2][0]) / 2.0, center_y),
        "thread_length": ((axis[2][0] + axis[3][0]) / 2.0, center_y),
        "head_diameter": (0.0, center_y),
        "collar_diameter": (0.0, center_y + 0.013),
        "thread_diameter": (0.0, center_y - 0.014),
    }
    positions = {}
    for name, (side, offset) in _SUPPLIER_LANES.items():
        x, y = centers[name]
        if side == "left":
            x = outline[0] - offset
        elif side == "right":
            x = outline[2] + offset
        elif side == "bottom":
            y = outline[1] - offset
        else:
            y = outline[3] + offset
        positions[_supplier_name(name)] = (x, y)
    return positions


def _station_circle(edges: Any, station_mm: float, *, label: str) -> Any:
    """Find a physical rim at a finished axial face, including a chamfered rim.

    All fragments in the selected plane share the same axial station; the
    largest remaining circle avoids small thread/knurl cutter intersections.
    Its radius is not used as a nominal diameter.
    """
    circles = [
        item
        for item in edges.circles
        if abs(item.circle[0] - station_mm) < 1e-5
        and abs(item.circle[1]) < 1e-5
        and abs(item.circle[2]) < 1e-5
        and abs(abs(item.circle[3]) - 1.0) < 1e-6
    ]
    if not circles:
        raise RuntimeError(f"{label}: no physical circular rim at X={station_mm:g} mm")
    return max(circles, key=lambda item: item.circle[6]).edge


def _supplier_name(name: str) -> str:
    return "Supplier" + "".join(word.title() for word in name.split("_"))


def _name_supplier_dimension(display: Any, name: str) -> None:
    native = _early_bound(
        _early_bound(display, "IDisplayDimension").GetDimension2(0), "IDimension"
    )
    native.Name = _supplier_name(name)
    if str(native.FullName).split("@", 1)[0] != _supplier_name(name):
        raise RuntimeError(f"{name}: supplier dimension name did not persist")


def _assert_physical_rims(display: Any, stations: tuple[float, float]) -> None:
    """Reacquire final attachments and prove their physical finished planes."""
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 2:
        raise RuntimeError("thumb axial reference must retain two physical rims")
    actual = []
    for raw in attached:
        curve = _early_bound(raw, "IEdge").GetCurve()
        if curve is None:
            raise RuntimeError("thumb axial reference no longer attaches to a rim")
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            raise RuntimeError("thumb axial reference no longer attaches to a rim")
        values = tuple(float(value) for value in curve.CircleParams)
        if (
            abs(values[1]) > 1e-8
            or abs(values[2]) > 1e-8
            or abs(abs(values[3]) - 1.0) > 1e-6
        ):
            raise RuntimeError("thumb axial reference left its coaxial finished plane")
        actual.append(values[0] * 1000.0)
    if any(
        abs(value - expected) > 1e-5
        for value, expected in zip(sorted(actual), sorted(stations), strict=True)
    ):
        raise RuntimeError("thumb axial reference attaches to the wrong finished faces")


def _assert_reference_diameter(display: Any, name: str) -> None:
    """Prove the imported envelope still belongs to its exact model carrier."""
    native = _early_bound(display.GetDimension2(0), "IDimension")
    identity = str(native.FullName).split("@")
    if identity[:2] != [_supplier_name(name), FEATURE_BY_PLANE["Front"]]:
        raise RuntimeError(f"{name}: supplier envelope changed native source owner")


def _supplier_displays(adapter: Any) -> dict[str, Any]:
    """Reacquire the sheet's exact native display-dimension inventory."""
    views = list(iter_views(adapter))
    fronts = [view for view in views if view.GetOrientationName() == "*Front"]
    if len(fronts) != 1:
        raise RuntimeError("thumb supplier sheet must have exactly one final Front view")
    found = {}
    for raw_view in views:
        current_view = _early_bound(raw_view, "IView")
        display = current_view.GetFirstDisplayDimension6()
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            native = _early_bound(display.GetDimension2(0), "IDimension")
            name = str(native.FullName).split("@", 1)[0]
            if name in found or current_view.GetOrientationName() != "*Front":
                raise RuntimeError("thumb supplier references duplicated or changed owner")
            found[name] = display
            display = display.GetNext5()
    return found


def _assert_supplier_positions(
    found: Mapping[str, Any], positions: Mapping[str, tuple[float, float]]
) -> None:
    if set(found) != set(positions):
        raise RuntimeError("thumb sheet lost or added a supplier dimension")
    for name, display in found.items():
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        actual = tuple(float(value) for value in annotation.GetPosition())
        if (
            display.OffsetText
            or len(actual) != 3
            or not all(map(isfinite, actual))
            or dist(actual[:2], positions[name]) > _POSITION_TOLERANCE_M
        ):
            raise RuntimeError(f"{name}: settled thumb supplier dimension left its lane")


def _place_supplier_dimensions(
    adapter: Any, positions: Mapping[str, tuple[float, float]]
) -> None:
    """Place complete native lines only after all formatting/import side effects."""
    rebuild_drawing(adapter, label="thumb supplier formatting and import settled")
    found = _supplier_displays(adapter)
    if set(found) != set(positions):
        raise RuntimeError("thumb sheet lost or added a supplier dimension")
    for name, display in found.items():
        # SetPosition2 moves only the text while OffsetText is true. Turn it
        # off explicitly so the dimension line and witnesses follow the lane.
        display.OffsetText = False
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        x, y = positions[name]
        if not annotation.SetPosition2(x, y, 0.0):
            raise RuntimeError(f"{name}: failed to place thumb supplier dimension")
    rebuild_drawing(adapter, label="thumb supplier complete native lanes")
    _assert_supplier_positions(_supplier_displays(adapter), positions)


@_telemetry.traced("drawing.thumb_supplier_settled")
def _assert_supplier_dimensions(
    adapter: Any, positions: Mapping[str, tuple[float, float]]
) -> None:
    """Prove all six native references after the finalizer's last rebuild."""
    found = _supplier_displays(adapter)
    _assert_supplier_positions(found, positions)
    axial = {
        "head_height": (supplier.HEAD_H, (0.0, supplier.HEAD_H)),
        "collar_height": (
            supplier.COLLAR_H,
            (supplier.HEAD_H, supplier.HEAD_STACK_LEN),
        ),
        "thread_length": (
            supplier.SHANK_LEN,
            (supplier.HEAD_STACK_LEN, supplier.OVERALL_LEN),
        ),
    }
    diameters = {
        "head_diameter": supplier.HEAD_DIA,
        "collar_diameter": supplier.COLLAR_DIA,
        "thread_diameter": supplier.SHANK_DIA,
    }
    if set(found) != {_supplier_name(name) for name in (*axial, *diameters)}:
        raise RuntimeError("thumb sheet lost or added a supplier dimension")
    for name in (*axial, *diameters):
        display = found[_supplier_name(name)]
        value = axial[name][0] if name in axial else diameters[name]
        assert_supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=value,
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
            presentation="length" if name in axial else "diameter",
            callout=supplier.SUPPLIER_THREAD if name == "thread_diameter" else None,
        )
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(f"{name}: supplier nominal acquired a fabrication band")
        if name in axial:
            _assert_physical_rims(display, axial[name][1])
        else:
            _assert_reference_diameter(display, name)


@_telemetry.traced("drawing.thumb_supplier_dimensions")
def supplier_dimensions(
    adapter: Any, views_by_orientation: dict[str, Any]
) -> dict[str, tuple[float, float]]:
    """Three physical spans and three model-owned nominal diameter references."""
    view = _early_bound(views_by_orientation["*Front"], "IView")
    view.UpdateViewDisplayGeometry()
    stations = (0.0, supplier.HEAD_H, supplier.HEAD_STACK_LEN, supplier.OVERALL_LEN)
    axis = model_points_in_view(
        adapter,
        view,
        [(x / 1000.0, 0.0, 0.0) for x in stations],
        label="thumb supplier axial stations",
    )
    outline = tuple(float(value) for value in view.GetOutline())
    positions = _supplier_positions(outline, axis)
    # Use exactly the geometry bounds the pre-fit pass reserved, including
    # native sheet-space padding, rather than reconstructing a nominal radius.
    margin_left, margin_bottom, margin_right, margin_top = SUPPLIER_MARGINS["*Front"]
    envelope = (
        outline[0] - margin_left,
        outline[1] - margin_bottom,
        outline[2] + margin_right,
        outline[3] + margin_top,
    )
    notes = str(_config.parts(SPEC.source.stem).get("installation_notes", ""))
    cell = next(
        bounds
        for name, _, bounds in fastener_view_cells(
            view_band_bottom(notes, label=SPEC.artifact_stem)
        )
        if name == "*Front"
    )
    if (
        envelope[0] < cell[0]
        or envelope[1] < cell[1]
        or envelope[2] > cell[2]
        or envelope[3] > cell[3]
    ):
        raise RuntimeError(
            f"thumb supplier annotation lanes leave the actual Front cell: {envelope!r} vs {cell!r}"
        )
    edges = scan_view_edges(view, label="thumb supplier finished-face rims")
    rims = [
        _station_circle(edges, station, label=f"thumb station {station:g}")
        for station in stations
    ]
    for name, start, end, value in (
        ("head_height", 0, 1, supplier.HEAD_H),
        ("collar_height", 1, 2, supplier.COLLAR_H),
        ("thread_length", 2, 3, supplier.SHANK_LEN),
    ):
        entities = (rims[start], rims[end])
        display = add_edge_dimension(
            adapter,
            view,
            p0=axis[start],
            p1=axis[end],
            text_xy=positions[_supplier_name(name)],
            label=name,
            orientation="horizontal",
            entities=entities,
        )
        _name_supplier_dimension(display, name)
        assert_dimension_measures(
            adapter, display, expected_mm=value, label=name, entities=entities
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=value,
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
        )
    locations = {
        name: positions[_supplier_name(name)]
        for name in ("head_diameter", "collar_diameter", "thread_diameter")
    }
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep={_supplier_name(name): xy for name, xy in locations.items()},
        view_label="thumb supplier nominal envelope diameters",
        dimensions_by_feature={
            FEATURE_BY_PLANE["Front"]: {_supplier_name(name) for name in locations}
        },
    )
    native_to_name = {_supplier_name(name): name for name in locations}
    values = {
        "head_diameter": supplier.HEAD_DIA,
        "collar_diameter": supplier.COLLAR_DIA,
        "thread_diameter": supplier.SHANK_DIA,
    }
    for annotation in annotations:
        name = native_to_name[dimension_name(adapter, annotation)]
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=name,
            expected_mm=values[name],
            units=supplier.SUPPLIER_UNITS,
            precision=supplier.SUPPLIER_PRECISION[name],
            presentation="diameter",
            callout=supplier.SUPPLIER_THREAD if name == "thread_diameter" else None,
        )
    # Formatting and the import/delete rebuild can displace an earlier
    # AddHorizontalDimension2 drop. Re-seat all six complete native lines,
    # never the fitted view, then measure actual text/line/arrow ink.
    _place_supplier_dimensions(adapter, positions)
    view.UpdateViewDisplayGeometry()
    assert_supplier_view_fits(adapter, view, cell, label=f"{SPEC.artifact_stem} *Front")
    return positions


async def build(adapter: Any) -> dict[str, str]:
    checks = []

    def annotate(current_adapter: Any, views: dict[str, Any]) -> None:
        positions = supplier_dimensions(current_adapter, views)
        checks.append(lambda: _assert_supplier_dimensions(current_adapter, positions))

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=annotate,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
