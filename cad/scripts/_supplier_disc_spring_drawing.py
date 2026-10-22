"""Native nominal supplier dimension diagrams, never physical spring replicas.

Linear dimensions keep their native dimension lines outside the source planes
and their complete source-formatted text on separate lower/upper offset shelves.
Plan diameters use near-rim single-arrow leaders in distinct sectors, never
OffsetText (which the API does not support for diameters). The shared whole-ink
cell guard remains authoritative after the final rebuild.
"""

from __future__ import annotations

from collections.abc import Callable
import math
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

from _com import _early_bound
from _drawing_common import rebuild_drawing
from _drawing_dimensions import offset_dimension_text
from _drawing_hidden_sketches import _show_hidden_owners, curate_view_dimensions
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    set_near_side_diameter,
)
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_spring_drawing import (
    assert_supplier_configuration_value,
    reacquire_supplier_dimensions,
)
from _supplier_spring_reference import SUPPLIER_DIAGRAM_CONFIGURATION
from vn_disc_spring_supplier_stock import (
    SUPPLIER_DIMENSION_NAMES,
    SUPPLIER_DIMENSIONS_BY_FEATURE,
    supplier_diagram_extents,
)


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
    """Show only each dimensioned diagram owner before the native view fit."""
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

    return (check_rebuilt_diagram_extents,)


def _assert_nominal_diameter_routes(
    displays: dict[str, Any],
    *,
    spec: Any,
    bounds: tuple[float, float, float, float],
) -> None:
    """Read final native routes, not just successful presentation setters."""
    x0, y0, x1, y1 = bounds
    radii = {}
    segments = {}
    for semantic in ("ID", "OD", "SHAFT_DIA"):
        name = SUPPLIER_DIMENSION_NAMES[semantic]
        if name not in displays:
            continue
        display = displays[name]
        if (
            not bool(display.Diametric)
            or int(display.ArrowSide) != 1  # swDimArrowsOutside
            or bool(display.SolidLeader)
            or bool(display.GetUseDocBrokenLeader())
            or int(display.GetBrokenLeader2()) != 2  # swBrokenLeaderHorizontalText
            or bool(display.GetUseDocSecondArrow())
            or bool(display.GetSecondArrow())
        ):
            raise RuntimeError(f"{spec.SKU} {semantic}: near-side diameter style changed")
        radii[name] = (x1 - x0) * float(getattr(spec, semantic)) / (2.0 * spec.OD)
        segments[name] = dimension_segments(display.GetAnnotation())
    # Native circle bounds use GetRadius plus analytic projected extrema
    # (_supplier_reference_geometry), not a rounded/nominal box. The source
    # extent's 1e-7 comparison is a refusal threshold, not projection rounding.
    # dimension_segments reads unrounded doubles; only audit JSON rounds to
    # 1e-7. Retain this fail-closed landing budget without adding that JSON
    # quantization or widening the source/cell guards.
    assert_leaders_clear(
        segments,
        centre=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
        keep_out={name: radius - 1e-7 for name, radius in radii.items()},
        lands_within={
            name: (radius - 1e-7, radius + 1e-7) for name, radius in radii.items()
        },
        label=f"{spec.SKU} nominal diameter leaders",
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
    placements = {}
    source_bounds = {
        key: reference_bounds(key) for key in supplier_disc_reference_features(spec)
    }
    x0, y0, x1, y1 = source_bounds["free_front"]
    placements["free_front"] = {
        "THICKNESS": (x0 - 0.018, (y0 + y1) / 2.0),
        "FREE_HEIGHT": (x1 + 0.018, (y0 + y1) / 2.0),
    }
    nominal_text_positions = {
        SUPPLIER_DIMENSION_NAMES["THICKNESS"]: ((x0 + x1) / 2.0, y0 - 0.014),
        SUPPLIER_DIMENSION_NAMES["FREE_HEIGHT"]: ((x0 + x1) / 2.0, y1 + 0.014),
    }
    x0, y0, x1, y1 = source_bounds["free_top"]
    # The widest source bands need their entire text outside the outer circle.
    # Upper-left ID, lower-right OD and upper-right shaft avoid the old
    # through-centre X; these are text origins, not replacement attachments.
    # Both ID/OD origins sit 4 mm inside the source's vertical extrema to
    # reserve headroom for the rocker's 4:1 asymmetric-band text. The final
    # native whole-ink guard, not that reserve, decides containment.
    placements["free_top"] = {
        "ID": (x0 - 0.026, y1 - 0.004),
        "OD": (x1 + 0.026, y0 + 0.004),
    }

    application = set(spec.SUPPLIER_APPLICATION_DIMENSIONS)
    if "SHAFT_DIA" in application:
        placements["free_top"]["SHAFT_DIA"] = (
            (x0 + x1) / 2.0 + 0.020, y1 + 0.010
        )
    diameter_text_positions = {
        SUPPLIER_DIMENSION_NAMES[semantic]: xy
        for semantic, xy in placements["free_top"].items()
    }
    height_sizes = [
        semantic
        for semantic in ("WORKING_HEIGHT", "WORKING_DEFLECTION")
        if semantic in application
    ]
    application_text_positions = {}
    if height_sizes:
        x0, y0, x1, y1 = source_bounds["free_right"]
        # Keep the dimension lines outside the application planes. Offset the
        # complete native callouts next to their own gauge bands: compressed
        # height below the baseline, deflection above the free-upper plane.
        placements["free_right"] = {
            semantic: (
                x0 - 0.014 if semantic == "WORKING_HEIGHT" else x1 + 0.014,
                (y0 + y1) / 2.0,
            )
            for semantic in height_sizes
        }
        application_text_positions = {
            SUPPLIER_DIMENSION_NAMES[semantic]: (
                (x0 + x1) / 2.0,
                y0 - 0.014 if semantic == "WORKING_HEIGHT" else y1 + 0.014,
            )
            for semantic in height_sizes
        }
    application_labels = {
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
            if semantic in application_labels:
                arguments["callout"] = application_labels[semantic]
            supplier_reference_dimension(adapter, display, **arguments)
            if key == "free_top":
                set_near_side_diameter(annotation, arguments["label"])
                # Re-pin after source formatting and leader style have settled
                # the text width; never offset a diametric dimension's text.
                if not annotation.SetPosition2(*positions[semantic], 0.0):
                    raise RuntimeError(f"{arguments['label']}: diameter placement failed")
            references.append(
                (key, SUPPLIER_DIMENSION_NAMES[semantic], arguments, semantic)
            )
        if key == "free_front":
            offset_dimension_text(adapter, imported, nominal_text_positions)
        elif key == "free_top":
            rebuild_drawing(adapter, label=f"{spec.SKU} near-side nominal diameters")
        elif key == "free_right":
            offset_dimension_text(adapter, imported, application_text_positions)

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
        displays = reacquire_supplier_dimensions(
            adapter,
            views,
            expected=expected,
            configurations=configurations,
        )
        _assert_nominal_diameter_routes(
            displays, spec=spec, bounds=source_bounds["free_top"]
        )
        for key, name, arguments, semantic in references:
            display = displays[name]
            text_positions = (
                nominal_text_positions
                if key == "free_front"
                else diameter_text_positions
                if key == "free_top"
                else application_text_positions
            )
            if name in text_positions:
                kind = (
                    "nominal" if key == "free_front"
                    else "diameter" if key == "free_top"
                    else "application"
                )
                if key != "free_top" and not bool(display.OffsetText):
                    raise RuntimeError(
                        f"{spec.SKU} {semantic}: {kind} text lost its offset shelf"
                    )
                annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
                point = tuple(float(value) for value in (annotation.GetPosition() or ()))
                if (
                    len(point) != 3
                    or not all(map(math.isfinite, point))
                    or math.dist(point[:2], text_positions[name]) > 1e-6
                ):
                    raise RuntimeError(
                        f"{spec.SKU} {semantic}: {kind} text moved from its target: "
                        f"{point!r} != {text_positions[name]!r}"
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
