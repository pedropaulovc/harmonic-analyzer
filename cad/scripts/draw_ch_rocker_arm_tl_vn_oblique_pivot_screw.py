"""Purchased reference sheet for the oblique-trammel pivot screw.

The sheet prints decimal inch and dimensions the screw on its RIGHT view, axis
horizontal as it lies in the lathe. Its one shop dimension is the cut thread
length from the shoulder face (the thread envelope's own depth), plain at three
places; every supplier size prints as a parenthesised reference, and a leader
names the supplied thread.
"""
from __future__ import annotations

import argparse
import math
import sys

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, iter_views
from solidworks_mcp.adapters.sw_type_info import constant

import _telemetry
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as part
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _session import run_build
from _supplier_dimensions import assert_supplier_reference_dimension, supplier_reference_dimension
from _supplier_limits import LIMIT
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
# The Right view carries every dimension: the head Ø left of the head, the
# shoulder Ø right of the thread end, the shoulder length above, the cut
# length under the thread with its three callout rows, the thread leader
# above-right. The 14.3 mm head leaves the 58 mm row room for both lanes.
SUPPLIER_MARGINS = {"*Right": (0.025, 0.020, 0.045, 0.012)}
DIAMETER_LANE = 0.014  # vertical diameter lines, out from the head / thread end
LENGTH_LANE = 0.008  # horizontal length lines, out from the head's rim
# Every carrier lies on a Right-view edge, so construction curves print as the
# continuous thick outline on this sheet (DP_LineFont, this SLDDRW only), not
# as a grey chain over the edge.
_CONSTRUCTION_LINE_FONT = (
    ("swLineFontConstructionCurvesStyle", "swLineCONTINUOUS"),
    ("swLineFontConstructionCurvesThickness", "swLW_THICK"),
)
_REFERENCES = {
    name: {
        "label": f"{name}@{part.REFERENCE_FEATURE}", "units": "in",
        "precision": part.REFERENCE_FORMATS[name][0], "expected_mm": value,
        "presentation": part.REFERENCE_FORMATS[name][1],
        "callout": part.REFERENCE_FORMATS[name][3],
    }
    for name, value, _ in part.REFERENCE_DIMENSIONS
}
_OWNERS = {
    **{name: part.REFERENCE_FEATURE for name in _REFERENCES},
    part.CUT_DIMENSION: part.CUT_FEATURE,
}


def _construction_curves_as_outline(adapter):
    extension = _early_bound(adapter.currentModel.Extension, "IModelDocExtension")
    option = constant("swDetailingNoOptionSpecified")
    settings = tuple(
        (name, constant(name), constant(value)) for name, value in _CONSTRUCTION_LINE_FONT
    )

    def readback() -> None:
        for name, preference, value in settings:
            if int(extension.GetUserPreferenceInteger(preference, option)) != value:
                raise RuntimeError(f"pivot screw line font {name} readback differs")

    for name, preference, value in settings:
        if not extension.SetUserPreferenceInteger(preference, option, value):
            raise RuntimeError(f"failed to set pivot screw line font {name}")
    readback()
    return readback


def _assert_band(name, display) -> None:
    display = _early_bound(display, "IDisplayDimension")
    tolerance = _early_bound(
        _early_bound(display.GetDimension2(0), "IDimension").Tolerance, "IDimensionTolerance"
    )
    band = part.REFERENCE_TOLERANCES_MM.get(name)
    if band is None:
        if int(tolerance.Type) != 0:
            raise RuntimeError(name + ": unsourced tolerance")
        return
    if int(tolerance.Type) != LIMIT or not all(
        math.isclose(actual, expected / 1000.0, rel_tol=0.0, abs_tol=1e-12)
        for actual, expected in ((float(tolerance.GetMinValue()), band[0]),
                                 (float(tolerance.GetMaxValue()), band[1]))
    ):
        raise RuntimeError(name + ": supplier limits changed")
    if int(display.GetPrimaryTolPrecision2()) != part.REFERENCE_FORMATS[name][0]:
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
        or str(display.GetText(4) or "").replace("\r\n", "\n") != part.CUT_CALLOUT
        or int(tolerance.Type) != 0
    ):
        raise RuntimeError(f"{part.CUT_DIMENSION}: shop cut length lost its plain presentation")


def _assert_dimensions(adapter, displays) -> None:
    for name, display in displays.items():
        if name == part.CUT_DIMENSION:
            _assert_shop_dimension(display)
            continue
        assert_supplier_reference_dimension(adapter, display, **_REFERENCES[name])
        _assert_band(name, display)


def _right_stations(adapter, right):
    """Sheet points on the axis: head end, head underside, step, thread tip."""
    stations = {
        key: model_point_in_view(adapter, right, (0.0, 0.0, z / 1000.0), label=f"pivot screw {key}")
        for key, z in (("head", part.LENGTH), ("joint", part.SHOULDER_LENGTH),
                       ("step", 0.0), ("tip", -part.THREAD_LENGTH))
    }
    scale = tuple(float(value) for value in _early_bound(right, "IView").ScaleRatio)
    return stations, scale[0] / scale[1]


def _place_dimensions(adapter, right) -> dict[str, object]:
    """Import the three supplier references and the cut into the Right view."""
    view = _early_bound(right, "IView")
    view.UpdateViewDisplayGeometry()
    at, scale = _right_stations(adapter, view)
    axis_y = at["step"][1]
    rim = part.HEAD_DIA / 2000.0 * scale
    keep = {
        "SupplierHeadDiameter": (at["head"][0] - DIAMETER_LANE, axis_y),
        "SupplierShoulderDiameter": (at["tip"][0] + DIAMETER_LANE, axis_y),
        "SupplierShoulderLength": ((at["joint"][0] + at["step"][0]) / 2.0, axis_y + rim + LENGTH_LANE),
        part.CUT_DIMENSION: ((at["step"][0] + at["tip"][0]) / 2.0, axis_y - rim - LENGTH_LANE),
    }
    by_feature = {
        part.REFERENCE_FEATURE: tuple(_REFERENCES),
        part.CUT_FEATURE: (part.CUT_DIMENSION,),
    }
    displays = {}
    for raw in curate_view_dimensions(
        adapter, view, keep=keep, view_label="pivot screw RIGHT", dimensions_by_feature=by_feature,
    ):
        name = dimension_name(adapter, raw)
        display = _early_bound(
            _early_bound(raw, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
        )
        if name in _REFERENCES:
            display = supplier_reference_dimension(adapter, display, **_REFERENCES[name])
            precision = _REFERENCES[name]["precision"]
            if name in part.REFERENCE_TOLERANCES_MM and display.SetPrecision3(
                precision, -1, precision, -1
            ) != 0:
                raise RuntimeError(name + ": supplier tolerance precision rejected")
        displays[name] = display
    if set(displays) != set(keep):
        raise RuntimeError(f"pivot screw RIGHT dimensions incomplete: {sorted(displays)}")
    return displays


def _add_thread_note(adapter, right):
    """Name the supplied thread on its upper silhouette, the note above the thread."""
    at, scale = _right_stations(adapter, right)
    edge = model_point_in_view(
        adapter, right, (0.0, part.THREAD_DIA / 2000.0, -part.THREAD_LENGTH * 0.4 / 1000.0),
        label="pivot screw thread silhouette",
    )
    note = add_attached_note(
        adapter, right, text=part.THREAD_NOTE, entity_xy=edge,
        note_xy=(at["tip"][0] - 0.010, at["tip"][1] + part.HEAD_DIA / 2000.0 * scale + LENGTH_LANE),
        label="pivot screw thread", entity_type="SILHOUETTE",
    )
    return _early_bound(note, "INote")


def _settled_right(adapter):
    """Reacquire the Right view's owned dimensions and its one thread note."""
    rights = [view for view in iter_views(adapter) if str(view.GetOrientationName()) == "*Right"]
    if len(rights) != 1:
        raise RuntimeError("pivot screw settled sheet has no single Right view")
    view = _early_bound(rights[0], "IView")
    found: dict[str, list] = {}
    display = view.GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        name, _, feature = str(
            _early_bound(display.GetDimension2(0), "IDimension").FullName
        ).partition("@")
        if _OWNERS.get(name) == feature.partition("@")[0]:
            found.setdefault(name, []).append(display)
        display = display.GetNext5()
    if set(found) != set(_OWNERS) or any(len(rows) != 1 for rows in found.values()):
        raise RuntimeError(f"pivot screw RIGHT dimensions changed: { {k: len(v) for k, v in found.items()} }")
    notes = [
        _early_bound(note, "INote") for note in view.GetNotes() or ()
        if str(_early_bound(note, "INote").GetText()).replace("\r\n", "\n") == part.THREAD_NOTE
    ]
    if len(notes) != 1:
        raise RuntimeError("pivot screw RIGHT view must carry the thread note once")
    return {name: rows[0] for name, rows in found.items()}


async def build(adapter) -> dict[str, str]:
    proofs = []

    def supplier_dimensions(adapter, views):
        if proofs:
            raise RuntimeError("supplier reference callback repeated")
        line_font = _construction_curves_as_outline(adapter)
        right = views["*Right"]
        _assert_dimensions(adapter, _place_dimensions(adapter, right))
        _add_thread_note(adapter, right)
        # Both side views carry the axis as a native centerline, picked on the
        # shoulder face at mid-length.
        for orientation, normal in (("*Top", (0.0, 1.0)), ("*Right", (1.0, 0.0))):
            view = views[orientation]
            add_view_centerline(
                adapter, view, label=f"pivot screw {orientation[1:].upper()} axis",
                face_xy=model_point_in_view(
                    adapter, view,
                    (normal[0] * part.SHOULDER_DIA / 2000.0, normal[1] * part.SHOULDER_DIA / 2000.0,
                     part.SHOULDER_LENGTH / 2000.0),
                    label=f"pivot screw {orientation[1:].upper()} shoulder face",
                ),
            )

        def assert_references():
            line_font()
            _assert_dimensions(adapter, _settled_right(adapter))

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
