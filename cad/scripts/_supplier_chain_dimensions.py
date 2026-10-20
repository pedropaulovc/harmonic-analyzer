"""Exact native supplier references on source-derived stock, not stand-ins.

Installed links retain their original clearance geometry and no dimensions.
All supplier numeric features belong to the separately sourced stock state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Literal

from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from _com import _early_bound
from _drawing_dimensions import set_arc_endpoints_to_center
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_points_in_view
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)

# 6261K171's configurable 6261K401 engineering drawing spells pitch .25 in;
# 6261K108's own engineering drawing spells the same exact pitch .250 in.
SUPPLIER_PITCH_MM = 0.25 * 25.4
CHAIN_PITCH_PRECISION = 2
CONNECTING_LINK_PITCH_PRECISION = 3


def annotate_chain_pitch(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    kind: Literal["inner", "outer", "connecting"],
    precision: int,
) -> Callable[[], None]:
    """Dimension the two real station circles, explicitly centre to centre."""
    import _supplier_chain_stock as stock

    if kind not in ("inner", "outer", "connecting"):
        raise ValueError(f"unknown roller-chain source {kind!r}")
    radius = stock.PIN_DIAMETER / 2
    z = (
        stock.CONNECTING_PIN_END
        if kind == "connecting"
        else stock.CHAIN_PIN_HALF_LENGTH
    )
    stations = (
        (-SUPPLIER_PITCH_MM / 2, SUPPLIER_PITCH_MM / 2)
        if kind == "connecting"
        else (
            SUPPLIER_PITCH_MM,
            2 * SUPPLIER_PITCH_MM,
        )
    )
    label = f"{kind} chain link supplier pitch"
    view = _early_bound(views["free_front"], "IView")
    outline = tuple(float(value) for value in view.GetOutline())
    scan = scan_view_edges(view, label=label)
    # Source physical pin circles, never plate-end arcs or nearby hole rims.
    circles = tuple(
        scan.circle_at(
            (x, 0.0, z),
            radius,
            axis=(0.0, 0.0, 1.0),
            label=f"{label} station {index}",
            center_tol_mm=1e-5,
            radius_tol_mm=1e-5,
        )
        for index, x in enumerate(stations)
    )
    centers = model_points_in_view(
        adapter,
        view,
        [(x / 1000.0, 0.0, z / 1000.0) for x in stations],
        label=f"{label} centres",
    )
    entities = tuple(circle.edge for circle in circles)
    display = add_edge_dimension(
        adapter,
        view,
        p0=centers[0],
        p1=centers[1],
        text_xy=((centers[0][0] + centers[1][0]) / 2.0, outline[3] + 0.006),
        label=label,
        orientation="horizontal",
        entities=entities,
    )
    set_arc_endpoints_to_center(adapter, display, label=label)
    native = _early_bound(
        _early_bound(display, "IDisplayDimension").GetDimension2(0), "IDimension"
    )
    if any(int(native.GetArcEndCondition(index)) != 1 for index in (1, 2)):
        raise RuntimeError(
            f"{label}: both circular endpoints must measure their centres"
        )
    assert_dimension_measures(
        adapter, display, expected_mm=SUPPLIER_PITCH_MM, label=label, entities=entities
    )
    presentation = {
        "label": label,
        "units": "in",
        "precision": precision,
        "expected_mm": SUPPLIER_PITCH_MM,
        "callout": "PITCH",
    }
    supplier_reference_dimension(adapter, display, **presentation)

    def settled() -> None:
        # Final drawing rebuilds may regenerate edges: resolve the physical
        # circles again instead of trusting the pre-rebuild edge handles.
        final_scan = scan_view_edges(view, label=f"{label} settled")
        final_entities = tuple(
            final_scan.circle_at(
                (x, 0.0, z),
                radius,
                axis=(0.0, 0.0, 1.0),
                label=f"{label} settled station {index}",
                center_tol_mm=1e-5,
                radius_tol_mm=1e-5,
            ).edge
            for index, x in enumerate(stations)
        )
        final_native = _early_bound(
            _early_bound(display, "IDisplayDimension").GetDimension2(0), "IDimension"
        )
        if any(int(final_native.GetArcEndCondition(index)) != 1 for index in (1, 2)):
            raise RuntimeError(
                f"{label}: settled circular endpoints lost their centres"
            )
        if int(_early_bound(final_native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(f"{label}: unprovided supplier tolerance appeared")
        assert_dimension_measures(
            adapter,
            display,
            expected_mm=SUPPLIER_PITCH_MM,
            label=label,
            entities=final_entities,
        )
        assert_supplier_reference_dimension(adapter, display, **presentation)

    return settled


def annotate_chain_stock(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    kind: Literal["inner", "outer", "connecting"],
) -> tuple[Callable[[], None], ...]:
    """Supplier-source sections and physical centre pitch; no installed sizes."""
    import _supplier_chain_stock as stock

    connecting = kind == "connecting"
    rows_by_view = {
        "free_front": (
            (stock.PIN_DIMENSION, stock.PIN_DIAMETER, 3, "diameter", "PIN"),
            (
                stock.ROLLER_DIMENSION,
                stock.ROLLER_DIAMETER,
                3 if connecting else 2,
                "diameter",
                "FOR ROLLER" if connecting else "ROLLER",
            ),
        ),
        "free_top": (
            (
                stock.WIDTH_DIMENSION,
                stock.ROLLER_WIDTH,
                3,
                "length",
                "FOR ROLLER WIDTH" if connecting else "ROLLER WIDTH",
            ),
        ),
    }
    if connecting:
        rows_by_view["free_top"] += (
            (stock.PLATE_DIMENSION, stock.PLATE_THICKNESS, 3, "length", "PLATE"),
            (
                stock.LENGTH_DIMENSION,
                stock.CONNECTING_PIN_LENGTH,
                3,
                "length",
                "OVERALL PIN",
            ),
        )
    checks = []
    for key, rows in rows_by_view.items():
        view = _early_bound(views[key], "IView")
        xmin, ymin, xmax, ymax = (float(value) for value in view.GetOutline())
        if key == "free_front":
            positions = {
                stock.PIN_DIMENSION: (xmax + 0.006, ymin - 0.009),
                stock.ROLLER_DIMENSION: (xmin - 0.006, ymin - 0.009),
            }
        else:
            positions = {stock.WIDTH_DIMENSION: (xmin - 0.007, (ymin + ymax) / 2)}
            if connecting:
                positions.update(
                    {
                        stock.PLATE_DIMENSION: (xmax + 0.007, ymax + 0.008),
                        stock.LENGTH_DIMENSION: (xmax + 0.013, (ymin + ymax) / 2),
                    }
                )
        annotations = curate_view_dimensions(
            adapter,
            view,
            keep=positions,
            view_label=f"{kind} supplier {key}",
            dimensions_by_feature=stock.DIMENSIONS_BY_FEATURE,
        )
        by_name = {
            dimension_name(adapter, annotation): annotation
            for annotation in annotations
        }
        if len(annotations) != len(rows) or set(by_name) != set(positions):
            raise RuntimeError(
                f"{kind} {key}: supplier source dimension inventory differs"
            )
        for name, expected, precision, presentation, callout in rows:
            display = _early_bound(
                by_name[name].GetSpecificAnnotation(), "IDisplayDimension"
            )
            owner = (
                stock.FRONT_FEATURE if key == "free_front" else stock.SECTION_FEATURE
            )
            options = {
                "label": f"{name}@{owner}",
                "units": "in",
                "precision": precision,
                "expected_mm": expected,
                "presentation": presentation,
                "callout": callout,
            }
            supplier_reference_dimension(adapter, display, **options)

            def settled(
                display=display, name=name, owner=owner, options=options
            ) -> None:
                native = _early_bound(display.GetDimension2(0), "IDimension")
                if str(native.FullName).split("@")[:2] != [name, owner]:
                    raise RuntimeError(
                        f"{name}: supplier dimension lost its source section"
                    )
                if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
                    raise RuntimeError(
                        f"{name}: unprovided supplier tolerance appeared"
                    )
                assert_supplier_reference_dimension(adapter, display, **options)

            checks.append(settled)
    # Import first: curating source dimensions must not delete a drawing-owned
    # centre-to-centre pitch that was authored before an import/rebuild.
    checks.append(
        annotate_chain_pitch(
            adapter,
            views,
            kind=kind,
            precision=CONNECTING_LINK_PITCH_PRECISION
            if connecting
            else CHAIN_PITCH_PRECISION,
        )
    )

    def inventory() -> None:
        expected = {
            "free_front": 3,
            "free_top": 3 if connecting else 1,
            "free_right": 0,
            "installed_iso": 0,
        }
        for key, count in expected.items():
            if (
                int(_early_bound(views[key], "IView").GetDisplayDimensionCount())
                != count
            ):
                raise RuntimeError(f"{kind} {key}: supplier reference count changed")

    checks.append(inventory)
    return tuple(checks)


def annotate_keeper_bead(adapter: Any, views: Mapping[str, Any]) -> Callable[[], None]:
    """Import the diameter that actually drives the seed bead's revolved arc.

    A bead/rod intersection circle is smaller than the sphere, so it cannot
    carry the catalogue diameter. The original SeedProfile's semicircle is
    the native geometric source instead; no independent numeric carrier or
    value/text override stands in for the bead.
    """
    import vn_keeper_chain_spec as chain

    view = _early_bound(views["*Front"], "IView")
    outline = tuple(float(value) for value in view.GetOutline())
    name = chain.CATALOGUE_BEAD_DIMENSION
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep={name: (outline[2] + 0.006, outline[3] + 0.006)},
        view_label="keeper catalogue bead diameter",
        dimensions_by_feature=chain.DRAWING_DIMENSIONS,
    )
    if len(annotations) != 1:
        raise RuntimeError(
            "keeper catalogue bead diameter: expected one native source dimension"
        )
    display = _early_bound(
        _early_bound(annotations[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    # The source sketch owns a true diameter, not a radial value with a typed
    # diameter prefix; supplier_reference_dimension checks its exact SI value.
    if int(display.Type2) != 6:  # swDimensionType_e.swDiameterDimension
        raise RuntimeError("keeper catalogue bead size is not a native diameter")
    presentation = {
        "label": f"{name}@SeedProfile",
        "units": "in",
        "precision": chain.DRAWING_REFERENCE_PRECISION[name],
        "expected_mm": chain.BEAD_DIA,
        "presentation": "diameter",
        "fraction_denominator": 32,
        "callout": "CATALOGUE BEAD SIZE",
    }
    supplier_reference_dimension(adapter, display, **presentation)

    def settled() -> None:
        final_display = _early_bound(
            _early_bound(annotations[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        native = _early_bound(final_display.GetDimension2(0), "IDimension")
        if (
            int(final_display.Type2) != 6
            or str(native.Name) != name
            or str(native.FullName).split("@")[1:2] != ["SeedProfile"]
        ):
            raise RuntimeError(
                "keeper catalogue bead size lost its native source diameter"
            )
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(
                "keeper catalogue bead size acquired an unprovided tolerance"
            )
        for orientation, item in views.items():
            count = int(_early_bound(item, "IView").GetDisplayDimensionCount())
            if count != (1 if orientation == "*Front" else 0):
                raise RuntimeError(
                    "keeper catalogue bead reference count changed after final rebuild"
                )
        assert_supplier_reference_dimension(adapter, final_display, **presentation)

    return settled
