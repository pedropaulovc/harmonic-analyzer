"""Native nominal supplier dimension diagrams, never physical spring replicas."""

from __future__ import annotations

from collections.abc import Callable
import math
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _drawing_hidden_sketches import _show_hidden_owners, curate_view_dimensions
from _drawing_layout_audit import _Reader, _dump_annotation
from _drawing_leaders import set_near_side_diameter
from _layout_audit import display_box
from _layout_geometry import ARROW_TEXT_CLEARANCE_M
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_screw_layout import supplier_top_text_geometry
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    reacquire_supplier_dimensions,
)
from _supplier_spring_reference import SUPPLIER_DIAGRAM_CONFIGURATION
from _supplier_wire_stock_drawing import _construction_curves_as_outline
from vn_disc_spring_supplier_stock import (
    SUPPLIER_DIMENSION_NAMES,
    SUPPLIER_DIMENSIONS_BY_FEATURE,
    supplier_diagram_extents,
)

# Which side of its diagram each size's text hangs on (-1 left, +1 right).
# The flat strip lies right of centre, so its thickness takes the right; the
# full-width envelope height takes the left. The shaft gauge hangs above the
# OD text on the right (the plan's reserved top lane), so no two plan leaders
# share a quadrant.
TEXT_SIDES = {
    "ID": -1,
    "OD": 1,
    "SHAFT_DIA": 1,
    "FREE_HEIGHT": -1,
    "THICKNESS": 1,
    "WORKING_HEIGHT": -1,
    "WORKING_DEFLECTION": 1,
}
# Template arrowhead, 3.556 mm long and 0.762 mm wide (GetArrowHeadAtIndex2,
# draw_dt_vn_cylinder_bank_spring): the farthest an outside arrow on a rim
# reaches beyond it, whatever angle its leader takes.
ARROW_REACH_M = 0.003556 + 0.000762 / 2.0
# The shaft text's bottom, this far over the plan centre: clear of the OD
# text by more than the audit's one-callout separation (4.5 mm at 6 mm).
SHAFT_TEXT_RISE_M = 0.0075
# Edge-on diagrams: the template's centre cross lies along the thin edge view
# and prints as dashes inside it, a hidden line to the reader.
EDGE_VIEWS = ("free_front", "free_right")
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym


def _delete_center_marks(adapter: Any, view: Any, *, label: str) -> None:
    """Delete every centre mark in an edge view and read none back."""
    marks = tuple(view.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if not marks:
        return
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    for index, mark in enumerate(marks):
        if not _early_bound(mark, "IAnnotation").Select2(index > 0, 0):
            raise RuntimeError(f"cannot select {label}")
    draw.EditDelete()  # VT_VOID: the re-read below is the proof
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"delete {label}")
    if view.GetAnnotationsByType(_CENTER_MARK_ANNOTATION):
        raise RuntimeError(f"{label} survived deletion")


def supplier_disc_reference_features(spec: Any) -> dict[str, tuple[str, ...]]:
    """Exact source owners shared by preparation, fitting and dimension placement."""
    application = set(spec.SUPPLIER_APPLICATION_DIMENSIONS)
    features = {
        "free_front": ("DiscSupplierHeight", "DiscSupplierStrip"),
        "free_top": ("DiscSupplierPlan",)
        + (("DiscSupplierShaft",) if "SHAFT_DIA" in application else ()),
    }
    if application.intersection(("WORKING_HEIGHT", "WORKING_DEFLECTION")):
        features["free_right"] = ("DiscSupplierApplication",)
    return features


def prepare_supplier_disc_diagram(
    adapter: Any,
    views: dict[str, Any],
    *,
    spec: Any,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> tuple[Callable[[], None], ...]:
    """Show only each dimensioned diagram owner before the native view fit.

    The diagrams are construction geometry. Drawn in the default construction
    font, the thin strip printed as short dashes inside the edge view, so this
    SLDDRW draws construction curves solid (as the cylinder-bank sheet does).
    """
    line_font = _construction_curves_as_outline(adapter)
    features = supplier_disc_reference_features(spec)
    expected_extents = supplier_diagram_extents(spec)
    if set(features) != set(expected_extents) or set(views) != {
        *features,
        "installed_iso",
    }:
        raise RuntimeError(f"{spec.SKU}: nominal diagram view/feature mismatch")
    for key, owners in features.items():
        shown = _show_hidden_owners(
            adapter, views[key], owners, view_label=f"{spec.SKU} nominal {key}"
        )
        if set(shown) != set(owners):
            raise RuntimeError(f"{spec.SKU} {key}: diagram owners are not saved hidden")

    def check_rebuilt_diagram_extents() -> None:
        for key, expected_mm in expected_extents.items():
            bounds = reference_bounds(key)
            actual_m = (bounds[2] - bounds[0], bounds[3] - bounds[1])
            if not all(
                math.isclose(actual, expected / 1000.0, rel_tol=0.0, abs_tol=1e-7)
                for actual, expected in zip(actual_m, expected_mm, strict=True)
            ):
                raise RuntimeError(
                    f"{spec.SKU} {key}: native diagram ink {actual_m} m "
                    f"differs from nominal {expected_mm} mm"
                )

    return (line_font, check_rebuilt_diagram_extents)


def _size_text_move(
    adapter: Any,
    key: str,
    semantic: str,
    display: Any,
    bounds: dict[str, tuple[float, float, float, float]],
    *,
    label: str,
) -> tuple[tuple[float, ...], float, float]:
    """Native position and the move that puts the text clear on its side.

    A plan diameter's near edge goes past the OD rim by its own outside
    arrowhead plus the arrow-to-text clearance; the shaft gauge's text sits
    over the plan centre. A height's offset text goes a clear gap beyond its
    own dimension line, witnesses and arrows (the washer thickness pattern).
    The application gauge cell has no room beside its wide planes for a
    stacked callout, so its text runs along its own dimension line to just
    over the highest plane's arrow.
    """
    reader = _Reader(adapter)
    record = _dump_annotation(reader, display.GetAnnotation())
    errors = reader.take_errors()
    position = tuple(float(value) for value in (record or {}).get("pos") or ())
    text = display_box(
        {"texts": ((record or {}).get("display") or {}).get("texts") or ()}
    )
    if errors or record is None or len(position) != 3 or text is None:
        raise RuntimeError(
            f"{label} {semantic}: unreadable native size text {errors!r}"
        )
    side = TEXT_SIDES[semantic]
    if key == "free_top":
        x0, y0, x1, y1 = bounds[key]
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        reach = (
            (x1 - x0) / 2.0 + ARROW_REACH_M + ARROW_TEXT_CLEARANCE_M + PLACE_SETTLE_M
        )
        dx = cx + side * reach - (text.xmin if side > 0 else text.xmax)
        if semantic == "SHAFT_DIA":
            dy = cy + SHAFT_TEXT_RISE_M - text.ymin
        else:
            dy = cy - (text.ymin + text.ymax) / 2.0
        return position, dx, dy
    lines = supplier_top_text_geometry(record, horizontal=False)
    gap = CLEAR_GAP_M + PLACE_SETTLE_M
    if key == "free_right":
        dx = lines["tips"][0][0] - (text.xmin + text.xmax) / 2.0
        return position, dx, bounds[key][3] + ARROW_REACH_M + gap - text.ymin
    if side > 0:
        return position, lines["right"] + gap - text.xmin, 0.0
    return position, lines["left"] - gap - text.xmax, 0.0


def place_disc_size_texts(
    adapter: Any,
    placed: list[tuple[str, str, Any]],
    bounds: dict[str, tuple[float, float, float, float]],
    *,
    label: str,
) -> None:
    """Move each size text off every line it would sit on.

    Plan diameters take one near-side arrow (no line through the shared
    centre, so concentric leaders cannot cross). Thin edge-view heights take
    native offset text, which keeps the dimension line at its station and
    lets the position write move only the text. A gauge height's text moves
    along its own line instead: an offset connector to the gap between its
    outside arrows ended in mid-air.
    """
    for key, semantic, display in placed:
        if key == "free_top":
            set_near_side_diameter(display.GetAnnotation(), f"{label} {semantic}")
        elif key != "free_right":
            display.OffsetText = True
    rebuild_drawing(adapter, label=f"{label} disc size styles")
    for key, semantic, display in placed:
        position, dx, dy = _size_text_move(
            adapter, key, semantic, display, bounds, label=label
        )
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if not annotation.SetPosition2(position[0] + dx, position[1] + dy, 0.0):
            raise RuntimeError(f"{label} {semantic}: size text placement was rejected")
    rebuild_drawing(adapter, label=f"{label} disc size texts")


def assert_disc_size_text_clear(
    adapter: Any,
    key: str,
    semantic: str,
    display: Any,
    bounds: dict[str, tuple[float, float, float, float]],
    *,
    label: str,
) -> None:
    """Settled text still clear of its lines (shaft and gauge texts over them)."""
    _position, dx, dy = _size_text_move(
        adapter, key, semantic, display, bounds, label=label
    )
    if key == "free_right":
        unclear = abs(dx) > PLACE_SETTLE_M or dy > PLACE_SETTLE_M
    else:
        unclear = TEXT_SIDES[semantic] * dx > PLACE_SETTLE_M or (
            semantic == "SHAFT_DIA" and dy > PLACE_SETTLE_M
        )
    if unclear:
        raise RuntimeError(
            f"{label} {semantic}: settled size text is not clear of its lines "
            f"(needs {dx * 1000:.2f}, {dy * 1000:.2f} mm)"
        )


def supplier_disc_spring_dimensions(
    adapter: Any,
    views: dict[str, Any],
    *,
    spec: Any,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
    settled_checks: list[Callable[[], None]] | None = None,
) -> None:
    """Import native nominal sizes from explicitly nonphysical diagrams.

    ID/OD, free-height envelope and flat nominal strip are source-owned diagram
    dimensions, not a wave/bow reconstruction or the installed annulus/cone.
    Working-height/deflection planes and nominal mating-shaft circles are
    separate application gauges, not an invented loaded spring or bore.
    """
    references = []
    placed = []
    source_bounds = {
        key: reference_bounds(key) for key in supplier_disc_reference_features(spec)
    }
    application = set(spec.SUPPLIER_APPLICATION_DIMENSIONS)
    sizes = {
        "free_top": ("ID", "OD", "SHAFT_DIA"),
        "free_front": ("FREE_HEIGHT", "THICKNESS"),
        "free_right": ("WORKING_HEIGHT", "WORKING_DEFLECTION"),
    }
    # Import stations: each dimension line (or diameter text) this far off its
    # diagram on its side; the texts then move clear of their own lines.
    stations = {"free_top": 0.018, "free_front": 0.018, "free_right": 0.014}
    placements = {}
    for key, semantics in sizes.items():
        if key not in source_bounds:
            continue
        x0, y0, x1, y1 = source_bounds[key]
        placements[key] = {
            semantic: (
                x1 + stations[key] if TEXT_SIDES[semantic] > 0 else x0 - stations[key],
                (y0 + y1) / 2.0 + (0.012 if semantic == "SHAFT_DIA" else 0.0),
            )
            for semantic in semantics
            if semantic in ("ID", "OD", "FREE_HEIGHT", "THICKNESS")
            or semantic in application
        }
    # The two edge-view heights are different supplier quantities: name them.
    callouts = {
        "FREE_HEIGHT": "FREE HEIGHT",
        "THICKNESS": "THICKNESS",
        "WORKING_HEIGHT": "COMPRESSED HEIGHT",
        "WORKING_DEFLECTION": "DEFLECTION",
        "SHAFT_DIA": "FOR SHAFT",
    }

    for key, positions in placements.items():
        keep = {
            SUPPLIER_DIMENSION_NAMES[semantic]: xy for semantic, xy in positions.items()
        }
        imported = curate_view_dimensions(
            adapter,
            views[key],
            keep=keep,
            view_label=f"{spec.SKU} supplier {key}",
            dimensions_by_feature=SUPPLIER_DIMENSIONS_BY_FEATURE,
        )
        semantics = {
            SUPPLIER_DIMENSION_NAMES[semantic]: semantic for semantic in positions
        }
        for annotation in imported:
            semantic = semantics[dimension_name(adapter, annotation)]
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            arguments = {
                "label": f"{spec.SKU} supplier {semantic.lower()}",
                "expected_mm": float(getattr(spec, semantic)),
                "units": spec.SUPPLIER_DRAWING_UNITS,
                "configuration": str(views[key].ReferencedConfiguration),
                "precision": spec.SUPPLIER_DRAWING_PRECISION[semantic],
                "presentation": (
                    "diameter" if semantic in ("ID", "OD", "SHAFT_DIA") else "length"
                ),
            }
            if semantic in callouts:
                arguments["callout"] = callouts[semantic]
            supplier_reference_dimension(adapter, display, **arguments)
            references.append(
                (key, SUPPLIER_DIMENSION_NAMES[semantic], arguments, semantic)
            )
            placed.append((key, semantic, display))
    place_disc_size_texts(adapter, placed, source_bounds, label=spec.SKU)
    edge_views = [key for key in EDGE_VIEWS if key in views]
    for key in edge_views:
        _delete_center_marks(
            adapter, views[key], label=f"{spec.SKU} {key} edge-view centre mark"
        )

    expected = {key: {} for key in views}
    configurations = {
        key: str(view.ReferencedConfiguration) for key, view in views.items()
    }
    for key, name, _arguments, _semantic in references:
        if configurations[key] != SUPPLIER_DIAGRAM_CONFIGURATION:
            raise RuntimeError(
                f"{spec.SKU} {key}: nominal diagram uses wrong configuration"
            )
        expected[key][name] = next(
            feature
            for feature, names in SUPPLIER_DIMENSIONS_BY_FEATURE.items()
            if name in names
        )

    def check_settled_references() -> None:
        if len(references) != 4 + len(application):
            raise RuntimeError(f"{spec.SKU}: supplier stock/application sizes missing")
        for key in edge_views:
            if views[key].GetAnnotationsByType(_CENTER_MARK_ANNOTATION):
                raise RuntimeError(
                    f"{spec.SKU} {key}: edge view regained a centre mark"
                )
        displays = reacquire_supplier_dimensions(
            adapter,
            views,
            expected=expected,
            configurations=configurations,
        )
        for key, name, arguments, semantic in references:
            display = displays[name]
            assert_disc_size_text_clear(
                adapter, key, semantic, display, source_bounds, label=spec.SKU
            )
            assert_supplier_reference_dimension(adapter, display, **arguments)
            assert_supplier_configuration_value(
                display,
                configurations[key],
                arguments["expected_mm"],
                label=name,
            )
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            band = getattr(spec, f"{semantic}_BAND", None)
            if band is None:
                if int(tolerance.Type) != 0:
                    raise RuntimeError(
                        f"{spec.SKU} {semantic}: unprovided source band appeared"
                    )
                continue
            upper, lower = band
            expected_type = 4 if math.isclose(upper, -lower, abs_tol=1e-12) else 2
            if int(tolerance.Type) != expected_type or not all(
                math.isclose(actual, value / 1000.0, rel_tol=0.0, abs_tol=1e-9)
                for actual, value in (
                    (float(tolerance.GetMinValue()), lower),
                    (float(tolerance.GetMaxValue()), upper),
                )
            ):
                raise RuntimeError(f"{spec.SKU} {semantic}: native source band changed")
            if int(display.GetPrimaryTolPrecision2()) != 3:
                raise RuntimeError(
                    f"{spec.SKU} {semantic}: source band needs three places"
                )

    if settled_checks is not None:
        settled_checks.append(check_settled_references)
    else:
        raise ValueError(
            "supplier disc dimensions require the finalizer's settled_checks list"
        )
