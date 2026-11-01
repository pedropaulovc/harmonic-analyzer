"""Purchased reference sheet for the oblique-trammel hub pin."""
from __future__ import annotations

import argparse
import math
import sys

from solidworks_mcp.adapters.solidworks.drawing import iter_views

import _telemetry
import ch_rocker_arm_tl_vn_oblique_hub_pin_spec as part
from _com import _early_bound
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
# dimension, the cut length (machinist review, 3/3 runs).
_CUT_TEXT = f"{part.CUT_LENGTH / 25.4:.{part.CUT_PLACES}f}".removeprefix("0")
GENERAL_TEXT = (
    f"PURCHASED PART; CUT TO {_CUT_TEXT} AT ASSEMBLY, "
    "OTHER GEOMETRY AS SUPPLIED (REFERENCE)."
)
# tall_top's 96 mm Top cell holds the .79 pin at 2:1 (standard's 64 mm: 1:2).
VIEW_LAYOUT = "tall_top"
REFERENCE = "SupplierPinDiameter"
CUT = "SupplierCutLength"
# Both texts shelve right of their witnesses: the diameter on the Top's
# bottom lane, the cut length beside it. Front and Top reserve the same
# left/right space so the fit centres them on one projection line; the
# unannotated Front's equal top/bottom keeps it level with the Right.
SHELVES = {REFERENCE: (True, "right"), CUT: (False, "right")}
SUPPLIER_MARGINS = {
    "*Front": (0.010, 0.010, 0.060, 0.010),
    "*Top": (0.010, 0.016, 0.060, 0.010),
}
_CUT_FORMAT = part.SUPPLIER_REFERENCE_FORMATS[CUT]


def _reference_rows(names):
    return {
        "dimensions": tuple(row for row in part.SUPPLIER_REFERENCE_DIMENSIONS if row[0] in names),
        "formats": {name: part.SUPPLIER_REFERENCE_FORMATS[name] for name in names},
        "planes": {name: part.SUPPLIER_REFERENCE_PLANES[name] for name in names},
        "units": {name: part.SUPPLIER_REFERENCE_UNITS[name] for name in names},
    }


def _make_shop_dimension(display) -> None:
    """The cut length is the shop's size: a plain value, not a parenthesised reference."""
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(1, "")  # swDimensionTextPrefix
    display.SetText(2, "")  # swDimensionTextSuffix


def _assert_shop_dimension(display) -> None:
    display = _early_bound(display, "IDisplayDimension")
    native = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
    if (
        not math.isclose(abs(float(native.SystemValue)) * 1000.0, part.CUT_LENGTH,
                         rel_tol=0.0, abs_tol=1e-6)
        or display.GetOverride() or not display.ShowDimensionValue
        or display.ShowParenthesis
        or int(display.GetPrimaryPrecision2()) != _CUT_FORMAT[0]
        or str(display.GetText(1) or "") or str(display.GetText(2) or "")
        or str(display.GetText(4) or "") != _CUT_FORMAT[3]
        or int(tolerance.Type) != 0
    ):
        raise RuntimeError(f"{CUT}: shop cut length lost its plain presentation")


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
        if str(_early_bound(display.GetDimension2(0), "IDimension").FullName).startswith(CUT + "@"):
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
        displays = annotate_supplier_screw(
            adapter, views, dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=part.SUPPLIER_REFERENCE_FORMATS,
            starts=part.SUPPLIER_REFERENCE_STARTS,
            planes=part.SUPPLIER_REFERENCE_PLANES,
            sides=part.SUPPLIER_REFERENCE_SIDES,
            units=part.SUPPLIER_REFERENCE_UNITS,
        )
        _make_shop_dimension(displays[CUT])
        _assert_shop_dimension(displays[CUT])
        _assert_reference_band(displays[REFERENCE])
        stations = shelve_supplier_text(adapter, displays, SHELVES)
        # The cut length's line lies on the silhouette, so the Top carries the
        # axis as a native centerline, picked on the pin face at mid-length.
        top = views["*Top"]
        add_view_centerline(
            adapter, top, label="hub pin TOP axis",
            face_xy=model_point_in_view(
                adapter, top, (0.0, part.DIA / 2000.0, part.CUT_LENGTH / 2000.0),
                label="hub pin TOP face",
            ),
        )

        def assert_references():
            # The supplier-reference contract covers the diameter only; the
            # Top view's cut length is the shop dimension, checked on its own.
            fresh = assert_supplier_screw(
                adapter, {"*Top": views["*Top"]}, **_reference_rows({REFERENCE}),
                shop={CUT},
            )
            _assert_reference_band(fresh[REFERENCE])
            cut = _settled_cut(adapter)
            _assert_shop_dimension(cut)
            assert_supplier_shelves(
                adapter, {REFERENCE: fresh[REFERENCE], CUT: cut}, SHELVES, stations,
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
