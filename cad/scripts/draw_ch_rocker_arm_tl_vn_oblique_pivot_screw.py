"""Purchased reference sheet for the oblique-trammel pivot screw.

The sheet prints decimal inch. Its one shop dimension is the cut thread length
from the shoulder face (the thread envelope's own depth), plain at three
places in the Top view; every supplier size prints as a parenthesised reference.
"""
from __future__ import annotations

import argparse
import math
import sys

from solidworks_mcp.adapters.solidworks.drawing import iter_views

import _telemetry
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as part
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_hidden_sketches import curate_view_dimensions
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

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_screw"]
ITEM = "18-8 SS SHOULDER SCREW, EXT THREAD, 3/8 X 1-1/2, 5/16-18"
# The default "VIEWS ARE REFERENCE ONLY" line would read as overriding the one
# shop dimension (as on the hub pin's sheet). At most the default cut line's
# 74 characters: 99 ran to x 237 mm, past the footer's 215.5 (farm round 4).
GENERAL_TEXT = "PURCHASED PART; CUT THREAD AND CHAMFER END AT ASSEMBLY. REST AS SUPPLIED."
# tall_top's 96 mm Top cell holds the ~2.3 in cut screw at 1:1.
VIEW_LAYOUT = "tall_top"
# Every text shelves right of its own witnesses, clear of the lines: the
# shoulder Ø on the Top's top lane (past the thread end), the head Ø on its
# bottom lane (under the head), the shoulder length beside the Top. Front and
# Top reserve the same left/right space so the fit centres them on one
# projection line; the unannotated Front's equal top/bottom keeps it level
# with the Right.
SHELVES = {
    "SupplierShoulderDiameter": (True, "right"),
    "SupplierHeadDiameter": (True, "right"),
    "SupplierShoulderLength": (False, "right"),
}
# The Top's bottom lane holds the head Ø's two rows; with the shoulder Ø's
# three over the thread end, the ~2.3 in screw still fits the 96 mm cell at 1:1.
SUPPLIER_MARGINS = {
    "*Front": (0.010, 0.010, 0.060, 0.010),
    "*Top": (0.010, 0.014, 0.060, 0.020),
}
# The cut length's text (63 mm wide with its callout row) centres on its line,
# so the line stands far enough right that the text clears the thread's edge
# and the shoulder Ø's witness lines (x 94-95 mm), and its outside arrow's
# tail clears the shoulder Ø text (x 104-128 mm) over the thread end. At the
# first lane, 6 mm out, it crossed all three (farm round 5 layout audit).
CUT_LANE = 0.028


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


def _assert_shop_dimension(display) -> None:
    """The cut is the shop's size: a plain three-place value, no reference marks."""
    display = _early_bound(display, "IDisplayDimension")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    if (
        not math.isclose(abs(float(native.SystemValue)) * 1000.0, part.CUT_THREAD_LENGTH,
                         rel_tol=0.0, abs_tol=1e-6)
        or display.GetOverride() or not display.ShowDimensionValue
        or display.ShowParenthesis
        or int(display.GetPrimaryPrecision2()) != part.CUT_THREAD_PLACES
        or str(display.GetText(1) or "") or str(display.GetText(2) or "")
        or str(display.GetText(4) or "") != part.CUT_CALLOUT
        or int(tolerance.Type) != 0
    ):
        raise RuntimeError(f"{part.CUT_DIMENSION}: shop cut length lost its plain presentation")


def _place_cut(adapter, top) -> object:
    """Import the cut length into the Top view, its line right of the thread."""
    view = _early_bound(top, "IView")
    view.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in view.GetOutline())
    middle = model_point_in_view(
        adapter, view, (0.0, 0.0, -part.CUT_THREAD_LENGTH / 2000.0), label="cut thread middle",
    )
    (display,) = curate_view_dimensions(
        adapter, view, keep={part.CUT_DIMENSION: (outline[2] + CUT_LANE, middle[1])},
        view_label="pivot screw cut thread",
        dimensions_by_feature={part.CUT_FEATURE: (part.CUT_DIMENSION,)},
    )
    return _early_bound(display, "IAnnotation").GetSpecificAnnotation()


def _settled_cut(adapter) -> object:
    """Reacquire the Top view's one cut-length dimension."""
    tops = [view for view in iter_views(adapter) if str(view.GetOrientationName()) == "*Top"]
    if len(tops) != 1:
        raise RuntimeError(f"{part.CUT_DIMENSION}: settled sheet has no single Top view")
    found = []
    display = _early_bound(tops[0], "IView").GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName)
        if name.startswith(f"{part.CUT_DIMENSION}@{part.CUT_FEATURE}"):
            found.append(display)
        display = display.GetNext5()
    if len(found) != 1:
        raise RuntimeError(f"{part.CUT_DIMENSION}: Top view must carry the cut length once")
    return found[0]


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
        _assert_shop_dimension(_place_cut(adapter, views["*Top"]))
        # The shoulder length's line lies on the silhouette, so the Top
        # carries its axis as a native centerline, picked on the shoulder face.
        top = views["*Top"]
        add_view_centerline(
            adapter, top, label="pivot screw TOP axis",
            face_xy=model_point_in_view(
                adapter, top,
                (0.0, part.SHOULDER_DIA / 2000.0, part.SHOULDER_LENGTH / 2000.0),
                label="pivot screw TOP shoulder face",
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
            _assert_shop_dimension(_settled_cut(adapter))

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
        unit=part_drawing_unit(part.PART_NAME),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
