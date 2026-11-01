"""Purchased reference sheet for the oblique-trammel pivot spacer."""
from __future__ import annotations

import argparse
import math
import sys

from solidworks_mcp.adapters.solidworks.drawing import iter_views

import _telemetry
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as part
from _com import _early_bound
from _construction_line_font import _construction_curves_as_outline
from _drawing_centerline import add_view_centerline
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _session import run_build
from _supplier_dimensions import assert_supplier_reference_dimension, supplier_reference_dimension
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
# The OD and length texts shelve right of their own witnesses, clear of the
# lines: the OD on the Top's bottom lane, the length beside it. The bore is
# dimensioned on the Front's visible bore circle, its text up-right of the
# ring. The 5/8 x 5/8 part fits at 2:1 in tall_top's 96 mm Top cell
# (standard's 64 mm leaves 28 mm: 1:1).
VIEW_LAYOUT = "tall_top"
SHELVES = {
    "SupplierOuterDiameter": (True, "right"),
    "SupplierLength": (False, "right"),
}
SUPPLIER_MARGINS = {
    "*Front": (0.004, 0.004, 0.050, 0.030),
    "*Top": (0.010, 0.018, 0.060, 0.018),
}
BORE = part.BORE_DIMENSION
BANDS = {**part.SUPPLIER_REFERENCE_TOLERANCES_MM, BORE: part.BORE_TOLERANCE_MM}
PRECISIONS = {
    **{name: row[0] for name, row in part.SUPPLIER_REFERENCE_FORMATS.items()},
    BORE: part.BORE_FORMAT[0],
}
_BORE_REFERENCE = {
    "label": f"{BORE}@{part.BORE_FEATURE}", "units": "in", "precision": part.BORE_FORMAT[0],
    "expected_mm": part.ID, "presentation": part.BORE_FORMAT[1], "callout": part.BORE_FORMAT[3],
}
# The OD and length carriers lie on Top-view edges; construction curves print
# as the continuous thick outline on this sheet (``_construction_line_font``),
# not as a dashed chain over the edges.


def _assert_supplier_bands(displays):
    for name, display in displays.items():
        display = _early_bound(display, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(native.Tolerance, "IDimensionTolerance")
        lower, upper = BANDS[name]
        if int(tolerance.Type) != LIMIT or not all(
            math.isclose(actual, expected / 1000.0, rel_tol=0.0, abs_tol=1e-12)
            for actual, expected in ((float(tolerance.GetMinValue()), lower),
                                     (float(tolerance.GetMaxValue()), upper))
        ):
            raise RuntimeError(name + ": supplier limits changed")
        if int(display.GetPrimaryTolPrecision2()) != PRECISIONS[name]:
            raise RuntimeError(name + ": supplier tolerance precision changed")


def _place_bore(adapter, front) -> object:
    """Import the ring profile's bore diameter onto the Front's bore circle."""
    view = _early_bound(front, "IView")
    view.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in view.GetOutline())
    (raw,) = curate_view_dimensions(
        adapter, view, keep={BORE: (outline[2] + 0.015, outline[3] + 0.014)},
        view_label="spacer bore", dimensions_by_feature={part.BORE_FEATURE: (BORE,)},
    )
    display = _early_bound(
        _early_bound(raw, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
    )
    display = supplier_reference_dimension(adapter, display, **_BORE_REFERENCE)
    if display.SetPrecision3(PRECISIONS[BORE], -1, PRECISIONS[BORE], -1) != 0:
        raise RuntimeError(BORE + ": bore tolerance precision rejected")
    return display


def _settled_bore(adapter) -> object:
    """Reacquire the Front view's one bore diameter."""
    fronts = [view for view in iter_views(adapter) if str(view.GetOrientationName()) == "*Front"]
    if len(fronts) != 1:
        raise RuntimeError(f"{BORE}: settled sheet has no single Front view")
    found = []
    display = _early_bound(fronts[0], "IView").GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName)
        if name.startswith(f"{BORE}@{part.BORE_FEATURE}@"):
            found.append(display)
        display = display.GetNext5()
    if len(found) != 1:
        raise RuntimeError(f"{BORE}: Front view must carry the bore once")
    return found[0]


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
        _assert_supplier_bands(displays)
        bore = _place_bore(adapter, views["*Front"])
        _assert_supplier_bands({BORE: bore})
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
            line_font()
            fresh = assert_supplier_screw(
                adapter, views, dimensions=part.SUPPLIER_REFERENCE_DIMENSIONS,
                formats=part.SUPPLIER_REFERENCE_FORMATS,
                planes=part.SUPPLIER_REFERENCE_PLANES,
                units=part.SUPPLIER_REFERENCE_UNITS,
            )
            _assert_supplier_bands(fresh)
            assert_supplier_shelves(adapter, fresh, SHELVES, stations)
            settled = _settled_bore(adapter)
            assert_supplier_reference_dimension(adapter, settled, **_BORE_REFERENCE)
            _assert_supplier_bands({BORE: settled})

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
