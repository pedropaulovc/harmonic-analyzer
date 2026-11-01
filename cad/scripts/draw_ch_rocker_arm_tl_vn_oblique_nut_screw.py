"""Create the purchased reference drawing for the oblique-trammel leadscrew nut screw."""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _com import _early_bound
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as supplier


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_nut_screw"]
# The footer's ITEM row: the fastener table's callout for the screw.
ITEM = "#4-40 X 1/2 BHCS"


def _assert_supplier_limits(displays: dict[str, Any]) -> None:
    nominals = {
        name: abs(value) for name, value, _ in supplier.SUPPLIER_REFERENCE_DIMENSIONS
    }
    for name, (minimum, maximum) in supplier.SUPPLIER_REFERENCE_LIMITS_IN.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 3 or not all(
            math.isclose(actual, (limit * 25.4 - nominals[name]) / 1000.0, rel_tol=0.0, abs_tol=1e-10)
            for actual, limit in (
                (float(tolerance.GetMinValue()), minimum),
                (float(tolerance.GetMaxValue()), maximum),
            )
        ):
            raise RuntimeError(f"{name}: native Olander source limits changed")
        if int(display.GetPrimaryTolPrecision2()) != 3:
            raise RuntimeError(f"{name}: Olander source limit precision changed")


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []
    callback_count = 0

    def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> None:
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("4C50BHCA: repeated supplier dimension callback")
        displays = annotate_supplier_screw(
            adapter,
            views,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
        )
        _assert_supplier_limits(displays)

        def assert_limits() -> None:
            fresh = assert_supplier_screw(
                adapter,
                views,
                dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=supplier.SUPPLIER_REFERENCE_FORMATS,
                planes=supplier.SUPPLIER_REFERENCE_PLANES,
            )
            _assert_supplier_limits(fresh)

        proofs.append(assert_limits)

    def assert_settled() -> None:
        if callback_count != 1 or len(proofs) != 1:
            raise RuntimeError("4C50BHCA: supplier limit proof was omitted/repeated")
        for proof in proofs:
            proof()

    # The 18-character registry number overruns the template's DWG. NO.
    # cell into REV; fit it there, measured.
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        number_fit=NumberFit.SHRINK_TO_CELL,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=supplier_screw_margins(
            supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
        ),
        settled_checks=(assert_settled,),
        unit=part_drawing_unit("ch-rocker-arm-tl-vn-oblique-nut-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
