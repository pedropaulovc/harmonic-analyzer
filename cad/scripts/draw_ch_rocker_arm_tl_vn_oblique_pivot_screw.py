"""Purchased reference sheet for the oblique-trammel pivot screw."""
from __future__ import annotations

import argparse
import math
import sys

import _telemetry
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as part
from _com import _early_bound
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_limits import LIMIT
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_screw"]
ITEM = '18-8 SS PRECISION SHOULDER SCREW, 10 MM X 35 MM, M8 X 1.25'
# tall_top's 96 mm Top cell holds the 52.5 mm screw at 1:1 (standard's 64 mm: 1:4).
VIEW_LAYOUT = "tall_top"
# Every text shelves right of its own witnesses, clear of the lines. Front and
# Top reserve the same left/right space so the fit centres them on one
# projection line; the Front's equal top/bottom keeps it level with the
# unannotated Right.
SHELVES = {
    "SupplierShoulderDiameter": (True, "right"),
    "SupplierHeadDiameter": (True, "right"),
    "SupplierShoulderLength": (False, "right"),
}
SUPPLIER_MARGINS = {
    "*Front": (0.010, 0.018, 0.060, 0.018),
    "*Top": (0.010, 0.010, 0.060, 0.010),
}


def _assert_supplier_bands(displays):
    for name, display in displays.items():
        display = _early_bound(display, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        band = part.SUPPLIER_REFERENCE_TOLERANCES_MM.get(name)
        if band is None:
            if int(tolerance.Type) != 0:
                raise RuntimeError(name + ": unsourced tolerance")
            continue
        lower, upper = band
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
        adapter, SPEC, item=ITEM, cut_to_suit=False, view_layout=VIEW_LAYOUT,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,), supplier_data=part.SUPPLIER_DATA,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
