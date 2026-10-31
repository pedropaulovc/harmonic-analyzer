"""Create the purchased reference drawing for the cone pivot screw."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _com import _early_bound
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _mcmaster_91829a560 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_FORMATS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_TOLERANCES_IN,
)


SPEC = DRAWINGS_BY_NAME["dt_vn_cone_pivot_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "SHOULDER SCREW, Ø1/4 x 1/4 SHOULDER, #10-24 x 3/8 THREAD"


def _assert_supplier_bands(displays: dict[str, Any]) -> None:
    for name, (lower, upper) in SUPPLIER_REFERENCE_TOLERANCES_IN.items():
        display = _early_bound(displays[name], "IDisplayDimension")
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
        if int(display.GetPrimaryTolPrecision2()) != 3:
            raise RuntimeError(f"{name}: source supplier tolerance precision changed")


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []
    callback_count = 0

    def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> None:
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("91829A560: repeated supplier dimension callback")
        displays = annotate_supplier_screw(
            adapter,
            views,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            formats=SUPPLIER_REFERENCE_FORMATS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
        )
        _assert_supplier_bands(displays)

        def assert_bands() -> None:
            from _supplier_screw_dimensions import assert_supplier_screw

            fresh = assert_supplier_screw(
                adapter,
                views,
                dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
                formats=SUPPLIER_REFERENCE_FORMATS,
                planes=SUPPLIER_REFERENCE_PLANES,
            )
            _assert_supplier_bands(fresh)

        proofs.append(assert_bands)

    def assert_settled() -> None:
        if callback_count != 1 or len(proofs) != 1:
            raise RuntimeError("91829A560: supplier dimension proof was omitted/repeated")
        for proof in proofs:
            proof()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=supplier_screw_margins(
            SUPPLIER_REFERENCE_DIMENSIONS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
        ),
        settled_checks=(assert_settled,),
        unit=part_drawing_unit("dt-vn-cone-pivot-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
