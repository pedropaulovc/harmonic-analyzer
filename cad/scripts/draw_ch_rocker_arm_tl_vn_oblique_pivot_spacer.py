"""Purchased reference sheet for the oblique-trammel pivot spacer."""
from __future__ import annotations

import argparse
import math
import sys

import _telemetry
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as part
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _session import run_build
from _supplier_limits import LIMIT
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_spacer"]
ITEM = '6061 ALUMINUM ROUND SPACER, 3/8 SCREW, 5/8 OD X 5/8 LONG'
# How the jig uses the part is a design note, not supplier operating data: it
# rides the general line (at most the default's 74 characters), every printed
# size already being the supplier's parenthesised reference.
GENERAL_TEXT = "PURCHASED PART, USED AS SUPPLIED. LOOSE BORE: NOT A LOCATING BUSHING."
# Every text shelves right of its own witnesses, clear of the lines: the bore
# on the Top's top lane, the OD on its bottom lane, the length beside it. Only
# the Top is annotated; the projection fit centres the Front under it. The
# 5/8 x 5/8 part fits at 2:1 in tall_top's 96 mm Top cell with both diameter
# lanes (standard's 64 mm leaves 28 mm: 1:1).
VIEW_LAYOUT = "tall_top"
SHELVES = {
    "SupplierBoreDiameter": (True, "right"),
    "SupplierOuterDiameter": (True, "right"),
    "SupplierLength": (False, "right"),
}
SUPPLIER_MARGINS = {"*Top": (0.010, 0.018, 0.060, 0.018)}


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
        # The side views carry the axis as native centerlines, picked on the
        # OD face at mid-length (frame: axis +Z from the bottom face); the
        # length's line lies on the Top's silhouette, not the axis.
        for orientation, normal in (("*Top", (0.0, 1.0)), ("*Right", (1.0, 0.0))):
            view = views[orientation]
            add_view_centerline(
                adapter, view, label=f"spacer {orientation[1:].upper()} axis",
                face_xy=model_point_in_view(
                    adapter, view,
                    (normal[0] * part.OD / 2000.0, normal[1] * part.OD / 2000.0,
                     part.LENGTH / 2000.0),
                    label=f"spacer {orientation[1:].upper()} OD face",
                ),
            )

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
        adapter, SPEC, item=ITEM, number_fit=NumberFit.SHRINK_TO_CELL,
        general_text=GENERAL_TEXT, view_layout=VIEW_LAYOUT,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,),
        unit=part_drawing_unit(part.PART_NAME),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
