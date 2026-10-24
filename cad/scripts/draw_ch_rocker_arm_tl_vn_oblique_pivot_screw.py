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
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_lane import move_supplier_lane
from _supplier_screw_layout import supplier_screw_margins

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_screw"]
ITEM = '18-8 SS PRECISION SHOULDER SCREW, 10 MM X 35 MM, M8 X 1.25'
# The shoulder length's three-line text is ~62 mm wide, centred on its dimension
# line; the helper's 6 mm lane would print it across the 4 mm wide 1:4 screw.
# Its line moves 26 mm further out, and the Top cell reserves that lane plus
# half the text before the scale fit.
SHOULDER_LANE_SHIFT = 0.026
SUPPLIER_MARGINS = supplier_screw_margins(
    part.SUPPLIER_REFERENCE_DIMENSIONS,
    planes=part.SUPPLIER_REFERENCE_PLANES,
    sides=part.SUPPLIER_REFERENCE_SIDES,
) | {"*Top": (0.006 + SHOULDER_LANE_SHIFT + 0.033, 0.020, 0.020, 0.020)}


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
        if int(tolerance.Type) != 2 or not all(
            math.isclose(actual, expected / 1000.0, rel_tol=0.0, abs_tol=1e-12)
            for actual, expected in ((float(tolerance.GetMinValue()), lower),
                                     (float(tolerance.GetMaxValue()), upper))
        ):
            raise RuntimeError(name + ": supplier band changed")
        if int(display.GetPrimaryTolPrecision2()) != part.SUPPLIER_REFERENCE_FORMATS[name][0]:
            raise RuntimeError(name + ": supplier tolerance precision changed")


async def build(adapter) -> dict[str, str]:
    # supplier_top's 70 mm Top cell holds the 52.5 mm screw at 1:4 (standard: 1:8).
    view_layout = "supplier_top"
    proofs = []
    stations = {}

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
            layout=view_layout,
            shelf_stations=stations,
        )
        move_supplier_lane(adapter, displays["SupplierShoulderLength"], -SHOULDER_LANE_SHIFT,
                           label="SupplierShoulderLength")
        _assert_supplier_bands(displays)

        def assert_references():
            fresh = assert_supplier_screw(
                adapter, views, dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=part.SUPPLIER_REFERENCE_FORMATS,
                planes=part.SUPPLIER_REFERENCE_PLANES,
                units=part.SUPPLIER_REFERENCE_UNITS,
                layout=view_layout,
                shelf_stations=stations,
            )
            _assert_supplier_bands(fresh)

        proofs.append(assert_references)

    def assert_supplier_dimensions():
        if len(proofs) != 1:
            raise RuntimeError("supplier references omitted or repeated")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=False, view_layout=view_layout,
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
