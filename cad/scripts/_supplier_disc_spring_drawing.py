"""Native nominal supplier dimension diagrams, never physical spring replicas."""

from __future__ import annotations

from collections.abc import Callable
import math
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

from _com import _early_bound
from _drawing_hidden_sketches import _show_hidden_owners, curate_view_dimensions
from _drawing_layout_check import DEFAULT_BOUNDARY_ALLOWANCE_M
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from vn_disc_spring_supplier_stock import (
    SUPPLIER_DIMENSION_NAMES,
    SUPPLIER_DIMENSIONS_BY_FEATURE,
    supplier_diagram_extents,
)


def prepare_supplier_disc_diagram(
    adapter: Any, views: dict[str, Any], *, spec: Any
) -> tuple[Callable[[], None], ...]:
    """Show only each dimensioned diagram owner before the native view fit."""
    application = set(spec.SUPPLIER_APPLICATION_DIMENSIONS)
    features = {
        "free_front": ("DiscSupplierHeight", "DiscSupplierStrip"),
        "free_top": ("DiscSupplierPlan",)
        + (("DiscSupplierShaft",) if "SHAFT_DIA" in application else ()),
    }
    if application.intersection(("WORKING_HEIGHT", "WORKING_DEFLECTION")):
        features["free_right"] = ("DiscSupplierApplication",)
    expected_extents = supplier_diagram_extents(spec)
    if set(features) != set(expected_extents) or set(views) != {
        *features, "installed_iso"
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
            outline = tuple(float(value) for value in views[key].GetOutline())
            if (
                len(outline) != 4
                or not all(math.isfinite(value) for value in outline)
                or outline[2] <= outline[0]
                or outline[3] <= outline[1]
            ):
                raise RuntimeError(f"{spec.SKU} {key}: empty/invalid diagram outline")
            actual_m = (outline[2] - outline[0], outline[3] - outline[1])
            # Native outlines include calibrated whitespace, not exact ink bounds.
            if not all(
                expected / 1000.0 - 1e-7
                <= actual
                <= expected / 1000.0 + 2.0 * DEFAULT_BOUNDARY_ALLOWANCE_M
                for actual, expected in zip(actual_m, expected_mm, strict=True)
            ):
                raise RuntimeError(
                    f"{spec.SKU} {key}: diagram outline {actual_m} m "
                    f"is outside nominal {expected_mm} mm plus native outline padding"
                )

    return (check_rebuilt_diagram_extents,)


def supplier_disc_spring_dimensions(
    adapter: Any,
    views: dict[str, Any],
    *,
    spec: Any,
    settled_checks: list[Callable[[], None]] | None = None,
) -> None:
    """Import native nominal sizes from explicitly nonphysical diagrams.

    ID/OD, free-height envelope and flat nominal strip are source-owned diagram
    dimensions, not a wave/bow reconstruction or the installed annulus/cone.
    Working-height/deflection planes and nominal mating-shaft circles are
    separate application gauges, not an invented loaded spring or bore.
    """
    references = []
    placements = {}
    for key, left_size, right_size in (
        ("free_top", "ID", "OD"),
        ("free_front", "THICKNESS", "FREE_HEIGHT"),
    ):
        view = _early_bound(views[key], "IView")
        x0, y0, x1, y1 = (float(value) for value in view.GetOutline())
        placements[key] = {
            left_size: (x0 - 0.018, (y0 + y1) / 2.0),
            right_size: (x1 + 0.018, (y0 + y1) / 2.0),
        }

    application = set(spec.SUPPLIER_APPLICATION_DIMENSIONS)
    if "SHAFT_DIA" in application:
        x0, _y0, x1, y1 = (
            float(value) for value in views["free_top"].GetOutline()
        )
        placements["free_top"]["SHAFT_DIA"] = ((x0 + x1) / 2.0, y1 + 0.010)
    height_sizes = [
        semantic
        for semantic in ("WORKING_HEIGHT", "WORKING_DEFLECTION")
        if semantic in application
    ]
    if height_sizes:
        x0, y0, x1, y1 = (
            float(value) for value in views["free_right"].GetOutline()
        )
        placements["free_right"] = {
            semantic: (
                x0 - 0.014 if index == 0 else x1 + 0.014,
                (y0 + y1) / 2.0,
            )
            for index, semantic in enumerate(height_sizes)
        }
    application_labels = {
        "WORKING_HEIGHT": "COMPRESSED HEIGHT",
        "WORKING_DEFLECTION": "DEFLECTION",
        "SHAFT_DIA": "FOR SHAFT",
    }

    for key, positions in placements.items():
        keep = {
            SUPPLIER_DIMENSION_NAMES[semantic]: xy
            for semantic, xy in positions.items()
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
                "precision": spec.SUPPLIER_DRAWING_PRECISION[semantic],
                "presentation": (
                    "diameter" if semantic in ("ID", "OD", "SHAFT_DIA") else "length"
                ),
            }
            if semantic in application_labels:
                arguments["callout"] = application_labels[semantic]
            supplier_reference_dimension(adapter, display, **arguments)
            references.append((display, arguments, semantic))

    def check_settled_references() -> None:
        if len(references) != 4 + len(application):
            raise RuntimeError(f"{spec.SKU}: supplier stock/application sizes missing")
        census = {
            "free_front": 2,
            "free_top": 2 + int("SHAFT_DIA" in application),
            **({"free_right": len(height_sizes)} if height_sizes else {}),
            "installed_iso": 0,
        }
        if set(views) != set(census):
            raise RuntimeError(f"{spec.SKU}: native diagram view set changed")
        for key, expected_count in census.items():
            count = int(_early_bound(views[key], "IView").GetDisplayDimensionCount())
            if count != expected_count:
                raise RuntimeError(
                    f"{spec.SKU} {key}: {count} native dimensions, "
                    f"expected {expected_count}"
                )
        for display, arguments, semantic in references:
            assert_supplier_reference_dimension(adapter, display, **arguments)
            band = getattr(spec, f"{semantic}_BAND", None)
            if band is None:
                continue
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            upper, lower = band
            expected_type = 4 if math.isclose(upper, -lower, abs_tol=1e-12) else 2
            if int(tolerance.Type) != expected_type or not all(
                math.isclose(actual, expected / 1000.0, rel_tol=0.0, abs_tol=1e-9)
                for actual, expected in (
                    (float(tolerance.GetMinValue()), lower),
                    (float(tolerance.GetMaxValue()), upper),
                )
            ):
                raise RuntimeError(
                    f"{spec.SKU} supplier {semantic}: native source band changed"
                )
            if int(display.GetPrimaryTolPrecision2()) != 3:
                raise RuntimeError(
                    f"{spec.SKU} supplier {semantic}: source band needs three places"
                )

    if settled_checks is not None:
        settled_checks.append(check_settled_references)
