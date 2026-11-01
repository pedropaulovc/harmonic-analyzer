"""Purchased reference sheet for the oblique-trammel pivot shim."""
from __future__ import annotations

import argparse
import math
import sys

import _telemetry
import ch_rocker_arm_tl_vn_oblique_pivot_shim_spec as part
from _com import _early_bound
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _session import run_build
from _supplier_limits import LIMIT
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_shim"]
ITEM = 'LOW-CARBON STEEL SHIM, 3/8 X 5/8, .008 THICK'
# Every text shelves past its own outer witness, clear of the lines: the bore
# on the Top's top lane, the OD on its bottom lane, both left of the thin
# strip so the thickness text beside it on the right stays clear of them.
# Front and Top reserve the same left/right space so the fit centres them on
# one projection line; the unannotated Front's equal top/bottom keeps it
# level with the Right. The 5/8 part fits at 2:1.
SHELVES = {
    "SupplierBoreDiameter": (True, "left"),
    "SupplierOuterDiameter": (True, "left"),
    "SupplierThickness": (False, "right"),
}
SUPPLIER_MARGINS = {
    "*Front": (0.060, 0.010, 0.060, 0.010),
    "*Top": (0.060, 0.018, 0.060, 0.018),
}


def _assert_supplier_bands(displays):
    for name, display in displays.items():
        display = _early_bound(display, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        lower, upper = part.SUPPLIER_REFERENCE_TOLERANCES_MM[name]
        if int(tolerance.Type) != LIMIT or not all(
            math.isclose(actual, expected / 1000.0, rel_tol=0.0, abs_tol=1e-12)
            for actual, expected in ((float(tolerance.GetMinValue()), lower),
                                     (float(tolerance.GetMaxValue()), upper))
        ):
            raise RuntimeError(name + ": supplier limits changed")
        if int(display.GetPrimaryTolPrecision2()) != part.SUPPLIER_REFERENCE_FORMATS[name][0]:
            raise RuntimeError(name + ": supplier tolerance precision changed")


async def build(adapter) -> dict[str, str]:
    proofs = []

    def supplier_dimensions(adapter, views):
        if proofs:
            raise RuntimeError("supplier reference callback repeated")
        displays = annotate_supplier_screw(
            adapter, views, dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=part.SUPPLIER_REFERENCE_FORMATS,
            starts=part.SUPPLIER_REFERENCE_STARTS,
            planes=part.SUPPLIER_REFERENCE_PLANES,
            sides=part.SUPPLIER_REFERENCE_SIDES,
            units=part.SUPPLIER_REFERENCE_UNITS,
        )
        _assert_supplier_bands(displays)
        stations = shelve_supplier_text(adapter, displays, SHELVES)

        def assert_references():
            fresh = assert_supplier_screw(
                adapter, views, dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=part.SUPPLIER_REFERENCE_FORMATS,
                planes=part.SUPPLIER_REFERENCE_PLANES,
                units=part.SUPPLIER_REFERENCE_UNITS,
            )
            _assert_supplier_bands(fresh)
            assert_supplier_shelves(adapter, fresh, SHELVES, stations)

        proofs.append(assert_references)

    def assert_supplier_dimensions():
        if len(proofs) != 1:
            raise RuntimeError("supplier references omitted or repeated")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=False, number_fit=NumberFit.SHRINK_TO_CELL,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,), supplier_data=part.SUPPLIER_DATA,
        unit=part_drawing_unit(part.PART_NAME),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
