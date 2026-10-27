"""Purchased reference sheet for the oblique-trammel pivot shim."""
from __future__ import annotations

import argparse
import math
import sys

import _telemetry
import ch_rocker_arm_tl_vn_oblique_pivot_shim_spec as part
from _com import _early_bound
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_lane import move_supplier_lane
from _supplier_screw_layout import supplier_screw_margins

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_shim"]
ITEM = 'DIN 988 SPRING STEEL SHIM, 10 MM ID X 16 MM OD X 0.2 MM'
# The two Front diameters' stacked texts overprinted on one bottom lane;
# the bore takes the top lane.
SIDES = part.SUPPLIER_REFERENCE_SIDES | {'SupplierBoreDiameter': 'top'}
# The Top view's thickness text, centred on its 6 mm lane, printed across the
# part; its line moves 14 mm further out, reserved before the scale fit.
LANE_SHIFT = 0.014
SUPPLIER_MARGINS = supplier_screw_margins(
    part.SUPPLIER_REFERENCE_DIMENSIONS,
    planes=part.SUPPLIER_REFERENCE_PLANES,
    sides=SIDES,
) | {"*Top": (0.006 + LANE_SHIFT + 0.025, 0.020, 0.020, 0.020)}


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
    proofs = []

    def supplier_dimensions(adapter, views):
        if proofs:
            raise RuntimeError("supplier reference callback repeated")
        displays = annotate_supplier_screw(
            adapter, views, dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=part.SUPPLIER_REFERENCE_FORMATS,
            starts=part.SUPPLIER_REFERENCE_STARTS,
            planes=part.SUPPLIER_REFERENCE_PLANES,
            sides=SIDES,
            units=part.SUPPLIER_REFERENCE_UNITS,
        )
        move_supplier_lane(adapter, displays["SupplierThickness"], views["*Top"],
                           lane_shift=LANE_SHIFT, label="SupplierThickness")
        _assert_supplier_bands(displays)

        def assert_references():
            fresh = assert_supplier_screw(
                adapter, views, dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=part.SUPPLIER_REFERENCE_FORMATS,
                planes=part.SUPPLIER_REFERENCE_PLANES,
                units=part.SUPPLIER_REFERENCE_UNITS,
            )
            _assert_supplier_bands(fresh)

        proofs.append(assert_references)

    def assert_supplier_dimensions():
        if len(proofs) != 1:
            raise RuntimeError("supplier references omitted or repeated")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=False,
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
