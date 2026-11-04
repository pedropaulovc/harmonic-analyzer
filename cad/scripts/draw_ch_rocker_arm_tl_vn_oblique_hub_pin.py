"""Purchased reference sheet for the oblique-trammel hub pin."""
from __future__ import annotations

import argparse
import math
import sys

from solidworks_mcp.adapters.solidworks.drawing import iter_views

import _telemetry
import ch_rocker_arm_tl_vn_oblique_hub_pin_spec as part
from _com import _early_bound
from _construction_line_font import _construction_curves_as_outline
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_centerline import add_view_centerline
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _part_properties import part_drawing_unit
from _session import run_build
from _supplier_screw_dimensions import annotate_supplier_screw, assert_supplier_screw
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_hub_pin"]
ITEM = "CLASS Z NO-GO PLUG GAUGE, Ø.4000 X 2 IN SUPPLY"
# The default "VIEWS ARE REFERENCE ONLY" line read as overriding the one shop
# dimension, the cut length (machinist review, 3/3 runs). The value itself
# prints once, on the Top view.
GENERAL_TEXT = "PURCHASED PART; CUT TO LENGTH AT ASSEMBLY, OTHER GEOMETRY AS SUPPLIED (REFERENCE)."
# tall_top's 96 mm Top cell holds the .79 pin at 2:1 (standard's 64 mm: 1:2).
VIEW_LAYOUT = "tall_top"
REFERENCE = "SupplierPinDiameter"
CUT = part.CUT_DIMENSION
# Both texts shelve right of their witnesses: the diameter on the Top's
# bottom lane, the cut length beside it. Only the Top is annotated; the
# projection fit centres the Front under it.
SHELVES = {REFERENCE: (True, "right"), CUT: (False, "right")}
SUPPLIER_MARGINS = {"*Top": (0.010, 0.016, 0.060, 0.010)}
# The cut length's line, right of the pin, before its text shelves.
CUT_LANE = 0.006
# The Ø carrier lies on the Top's end-face edge. Construction curves print as
# continuous thick lines on this sheet (DP_LineFont, this SLDDRW only), so
# the carrier prints as that edge, not a grey chain over it
# (``_construction_line_font``).
def _assert_shop_dimension(display) -> None:
    """The cut is the shop's size: a plain two-place value, no reference marks."""
    display = _early_bound(display, "IDisplayDimension")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    if (
        not math.isclose(abs(float(native.SystemValue)) * 1000.0, part.CUT_LENGTH,
                         rel_tol=0.0, abs_tol=1e-6)
        or display.GetOverride() or not display.ShowDimensionValue
        or display.ShowParenthesis
        or int(display.GetPrimaryPrecision2()) != part.CUT_PLACES
        or str(display.GetText(1) or "") or str(display.GetText(2) or "")
        or str(display.GetText(4) or "") != part.CUT_CALLOUT
        or int(tolerance.Type) != 0
    ):
        raise RuntimeError(f"{CUT}: shop cut length lost its plain presentation")


def _place_cut(adapter, top) -> object:
    """Import the pin extrusion's depth into the Top view, right of the pin."""
    view = _early_bound(top, "IView")
    view.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in view.GetOutline())
    middle = model_point_in_view(
        adapter, view, (0.0, 0.0, part.CUT_LENGTH / 2000.0), label="hub pin middle",
    )
    (display,) = curate_view_dimensions(
        adapter, view, keep={CUT: (outline[2] + CUT_LANE, middle[1])},
        view_label="hub pin cut length",
        dimensions_by_feature={part.CUT_FEATURE: (CUT,)},
    )
    return _early_bound(display, "IAnnotation").GetSpecificAnnotation()


def _settled_cut(adapter) -> object:
    """Reacquire the Top view's one native cut length."""
    tops = [view for view in iter_views(adapter) if str(view.GetOrientationName()) == "*Top"]
    if len(tops) != 1:
        raise RuntimeError(f"{CUT}: settled sheet has no single Top view")
    view = _early_bound(tops[0], "IView")
    found = []
    display = view.GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName)
        if name.startswith(f"{CUT}@{part.CUT_FEATURE}@"):
            found.append(display)
        display = display.GetNext5()
    if len(found) != 1:
        raise RuntimeError(f"{CUT}: Top view must carry the cut length once")
    return found[0]


def _assert_reference_band(display) -> None:
    native = _early_bound(_early_bound(display, "IDisplayDimension").GetDimension2(0), "IDimension")
    if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
        raise RuntimeError(f"{REFERENCE}: plain reference diameter carries a tolerance")


async def build(adapter) -> dict[str, str]:
    proofs = []

    def supplier_dimensions(adapter, views):
        if proofs:
            raise RuntimeError("supplier reference callback repeated")
        line_font = _construction_curves_as_outline(adapter)
        displays = annotate_supplier_screw(
            adapter, views, dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=part.SUPPLIER_REFERENCE_FORMATS,
            starts=part.SUPPLIER_REFERENCE_STARTS,
            planes=part.SUPPLIER_REFERENCE_PLANES,
            sides=part.SUPPLIER_REFERENCE_SIDES,
            units=part.SUPPLIER_REFERENCE_UNITS,
        )
        _assert_reference_band(displays[REFERENCE])
        top = views["*Top"]
        cut = _place_cut(adapter, top)
        _assert_shop_dimension(cut)
        # The cut length runs between the end faces, so the Top carries the
        # axis as a native centerline, picked on the pin face at mid-length.
        add_view_centerline(
            adapter, top, label="hub pin TOP axis",
            face_xy=model_point_in_view(
                adapter, top, (0.0, part.DIA / 2000.0, part.CUT_LENGTH / 2000.0),
                label="hub pin TOP face",
            ),
        )
        # Shelve last, so the retained stations are the ones the sheet keeps.
        stations = shelve_supplier_text(adapter, {**displays, CUT: cut}, SHELVES)

        def assert_references():
            line_font()
            # The supplier-reference contract covers the diameter only; the
            # cut length is the extrusion's shop dimension, checked on its own.
            fresh = assert_supplier_screw(
                adapter, {"*Top": views["*Top"]},
                dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=part.SUPPLIER_REFERENCE_FORMATS,
                planes=part.SUPPLIER_REFERENCE_PLANES,
                units=part.SUPPLIER_REFERENCE_UNITS,
            )
            _assert_reference_band(fresh[REFERENCE])
            settled = _settled_cut(adapter)
            _assert_shop_dimension(settled)
            assert_supplier_shelves(
                adapter, {REFERENCE: fresh[REFERENCE], CUT: settled}, SHELVES, stations,
            )

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
        settled_checks=(assert_supplier_dimensions,), supplier_data=part.SUPPLIER_DATA,
        unit=part_drawing_unit("ch-rocker-arm-tl-vn-oblique-hub-pin"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
