"""Create the purchased reference drawing for the oblique-trammel nut bracket screw."""

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
from _purchased_title_fit import fit_purchased_title_block
from _com import _early_bound
from _supplier_screw_dimensions import assert_supplier_screw
from _supplier_screw_reference_text import annotate_supplier_screw_with_shelves
from _supplier_screw_layout import supplier_screw_margins
import ch_rocker_arm_tl_vn_oblique_block_screw_spec as supplier


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_block_screw"]
# The footer's ITEM row: the fastener table's callout for the screw.
ITEM = "#8-32 X 1-7/8 SHCS"
# Keep the complete MIN label off the overall-length dimension line, using
# the existing left annotation lane without changing the source chord.
_REFERENCE_SIDES = {
    **supplier.SUPPLIER_REFERENCE_SIDES,
    "SupplierThreadLength": "left",
}


def _assert_supplier_minimums(displays: dict[str, Any]) -> None:
    for name in supplier.SUPPLIER_REFERENCE_MINIMUMS:
        display = _early_bound(displays[name], "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        if (
            int(tolerance.Type) != 5  # swTolMIN, inherited from the model.
            or not math.isclose(float(tolerance.GetMinValue()), 0.0, rel_tol=0.0, abs_tol=1e-10)
            or not math.isclose(float(tolerance.GetMaxValue()), 0.0, rel_tol=0.0, abs_tol=1e-10)
            or int(display.GetPrimaryTolPrecision2()) != 3
        ):
            raise RuntimeError(f"{name}: native supplier thread-length minimum changed")


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []
    callback_count = 0

    def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> None:
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("91251A188: repeated supplier dimension callback")
        source_and_shelf_checks: list[Callable[[], None]] = []
        displays = annotate_supplier_screw_with_shelves(
            adapter,
            views,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=_REFERENCE_SIDES,
            settled_checks=source_and_shelf_checks,
            label=SPEC.artifact_stem,
        )
        _assert_supplier_minimums(displays)

        def assert_minimums() -> None:
            for check in source_and_shelf_checks:
                check()
            fresh = assert_supplier_screw(
                adapter,
                views,
                dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=supplier.SUPPLIER_REFERENCE_FORMATS,
                planes=supplier.SUPPLIER_REFERENCE_PLANES,
            )
            _assert_supplier_minimums(fresh)

        proofs.append(assert_minimums)

    def assert_settled() -> None:
        if callback_count != 1 or len(proofs) != 1:
            raise RuntimeError("91251A188: supplier minimum proof was omitted/repeated")
        for proof in proofs:
            proof()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        view_layout="portrait_reference",
        align_orthographic=True,
        title_block_setup=partial(
            fit_purchased_title_block, spec=SPEC, material_property="Material"
        ),
        supplier_dimensions=supplier_dimensions,
        supplier_margins=supplier_screw_margins(
            supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=_REFERENCE_SIDES,
        ),
        settled_checks=(assert_settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
