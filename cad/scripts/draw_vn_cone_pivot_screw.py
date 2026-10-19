"""Create the purchased reference drawing for the cone pivot screw."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from functools import partial
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _com import _early_bound
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _mcmaster_91829a560 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_FORMATS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_TOLERANCES_IN,
)


SPEC = DRAWINGS_BY_NAME["vn_cone_pivot_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "SHOULDER SCREW, Ø1/4 x 1/4 SHOULDER, #10-24 x 3/8 THREAD"


def _assert_supplier_bands(
    displays: dict[str, Any], *, check_precision: bool
) -> None:
    for name, (lower, upper) in SUPPLIER_REFERENCE_TOLERANCES_IN.items():
        display = displays[name]
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 2 or not all(
            math.isclose(actual, expected * 0.0254, rel_tol=0.0, abs_tol=1e-10)
            for actual, expected in (
                (float(tolerance.GetMinValue()), lower),
                (float(tolerance.GetMaxValue()), upper),
            )
        ):
            raise RuntimeError(f"{name}: native supplier shoulder band changed")
        if check_precision and int(display.GetPrimaryTolPrecision2()) != 3:
            raise RuntimeError(f"{name}: supplier tolerance precision did not persist")


def _supplier_dimensions(
    adapter: Any,
    views: dict[str, Any],
    *,
    settled_checks: list[Callable[[], None]],
) -> None:
    displays = annotate_supplier_screw(
        adapter,
        views,
        dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
        formats=SUPPLIER_REFERENCE_FORMATS,
        starts=SUPPLIER_REFERENCE_STARTS,
        planes=SUPPLIER_REFERENCE_PLANES,
    )
    _assert_supplier_bands(displays, check_precision=False)
    for name in SUPPLIER_REFERENCE_TOLERANCES_IN:
        # The native SI deviations are unchanged; only the inch spelling differs.
        displays[name].SetPrecision3(-1, -1, 3, -1)

    def settled_check() -> None:
        fresh = assert_supplier_screw(
            adapter,
            views,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            formats=SUPPLIER_REFERENCE_FORMATS,
            planes=SUPPLIER_REFERENCE_PLANES,
        )
        _assert_supplier_bands(fresh, check_precision=True)

    settled_checks.append(settled_check)


async def build(adapter: Any) -> dict[str, str]:
    settled_checks = []
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=partial(
            _supplier_dimensions, settled_checks=settled_checks
        ),
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
