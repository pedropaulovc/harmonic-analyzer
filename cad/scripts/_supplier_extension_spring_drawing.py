"""Drawing-only import and settled readback of native extension spring references.

The source model owns reference sketch and dimension identities in
``_supplier_extension_spring``; only this consumer imports drawing adapters.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name

from _com import _early_bound
from _drawing_hidden_sketches import curate_view_dimensions
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_extension_spring import (
    COIL_OD,
    DIMENSIONS_BY_FEATURE,
    FREE_LENGTH,
    MAX_LENGTH,
    WIRE_DIA,
)


def extension_spring_dimensions(
    adapter: Any,
    views: Mapping[str, Any],
    *,
    free_length_mm: float,
    max_length_mm: float,
    coil_od_mm: float,
    wire_dia_mm: float,
    precision: Mapping[str, int],
    od_tolerance_mm: float | None = None,
    od_tolerance_precision: int | None = None,
) -> tuple[Callable[[], None], ...]:
    """Import exact states and return read-only final-rebuild dimension checks."""
    checks = []
    for key, rows in (
        (
            "free_front",
            ((FREE_LENGTH, free_length_mm, "length", "INSIDE HOOKS / LOOPS"),),
        ),
        (
            "free_right",
            (
                (COIL_OD, coil_od_mm, "diameter", "COIL OD"),
                (WIRE_DIA, wire_dia_mm, "diameter", "NOMINAL WIRE SECTION"),
            ),
        ),
        ("max_front", ((MAX_LENGTH, max_length_mm, "length", "AT MAXIMUM EXTENSION"),)),
    ):
        view = views[key]
        xmin, ymin, xmax, ymax = (float(value) for value in view.GetOutline())
        if key == "free_right":
            positions = {
                COIL_OD: (xmax + 0.006, ymax + 0.005),
                WIRE_DIA: (xmax + 0.006, ymin - 0.009),
            }
        else:
            positions = {rows[0][0]: ((xmin + xmax) / 2, ymax + 0.010)}
        annotations = curate_view_dimensions(
            adapter,
            view,
            keep=positions,
            view_label=key,
            dimensions_by_feature=DIMENSIONS_BY_FEATURE,
        )
        by_name = {
            dimension_name(adapter, annotation): annotation
            for annotation in annotations
        }
        if set(by_name) != set(positions):
            raise RuntimeError(
                f"{key}: supplier reference inventory differs from source"
            )
        for name, expected, presentation, callout in rows:
            display = _early_bound(
                by_name[name].GetSpecificAnnotation(), "IDisplayDimension"
            )
            supplier_reference_dimension(
                adapter,
                display,
                label=name,
                units="in",
                precision=precision[name],
                expected_mm=expected,
                presentation=presentation,
                callout=callout,
            )
            owner = next(
                feature
                for feature, names in DIMENSIONS_BY_FEATURE.items()
                if name in names
            )

            def settled(
                display=display,
                name=name,
                expected=expected,
                presentation=presentation,
                callout=callout,
                owner=owner,
            ) -> None:
                assert_supplier_reference_dimension(
                    adapter,
                    display,
                    label=name,
                    units="in",
                    precision=precision[name],
                    expected_mm=expected,
                    presentation=presentation,
                    callout=callout,
                )
                native = _early_bound(display.GetDimension2(0), "IDimension")
                qualified = str(native.FullName).split("@")
                if len(qualified) < 2 or qualified[0] != name or qualified[1] != owner:
                    raise RuntimeError(
                        f"{name}: final native dimension references the wrong source sketch"
                    )
                if name == COIL_OD and od_tolerance_mm is not None:
                    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
                    if (
                        int(tolerance.Type) != 4
                        or abs(float(tolerance.GetMinValue()) + od_tolerance_mm / 1000)
                        > 1e-12
                        or abs(float(tolerance.GetMaxValue()) - od_tolerance_mm / 1000)
                        > 1e-12
                        or int(display.GetPrimaryTolPrecision2())
                        != od_tolerance_precision
                    ):
                        raise RuntimeError(
                            "source supplier OD band changed after final rebuild"
                        )
                elif (
                    int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0
                ):
                    raise RuntimeError(
                        f"{name}: unprovided supplier tolerance appeared after final rebuild"
                    )

            checks.append(settled)
            if name == COIL_OD and od_tolerance_mm is not None:
                tolerance = _early_bound(
                    _early_bound(display.GetDimension2(0), "IDimension").Tolerance,
                    "IDimensionTolerance",
                )
                if (
                    int(tolerance.Type) != 4
                    or abs(float(tolerance.GetMinValue()) + od_tolerance_mm / 1000)
                    > 1e-12
                    or abs(float(tolerance.GetMaxValue()) - od_tolerance_mm / 1000)
                    > 1e-12
                    or int(display.GetPrimaryTolPrecision2()) != od_tolerance_precision
                ):
                    raise RuntimeError(
                        "source supplier OD band changed on drawing import"
                    )
    return tuple(checks)
