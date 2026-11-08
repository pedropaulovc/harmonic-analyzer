"""Purchased reference sheet for MHA-SM-VN-56, the gooseneck shoulder screw.

The sheet prints decimal inch and dimensions the screw on its RIGHT view, axis
horizontal as it lies in the lathe (as the oblique trammel's pivot screw,
draw_ch_rocker_arm_tl_vn_oblique_pivot_screw, without its shop cut): every
supplier size prints as a parenthesised reference, and a leader names the
supplied thread.
"""
from __future__ import annotations

import argparse
import sys

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, iter_views

import _telemetry
import sm_vn_gooseneck_shoulder_screw_spec as part
from _com import _early_bound
from _construction_line_font import _construction_curves_as_outline
from _drawing_centerline import add_view_centerline
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _session import run_build
from _supplier_dimensions import assert_supplier_reference_dimension, supplier_reference_dimension
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _supplier_unbanded import assert_supplier_screw_unbanded

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_vn_gooseneck_shoulder_screw"]
ITEM = "ALLOY STEEL SHOULDER SCREW, 5/16 X 3/8, 1/4-20"
# The dimensioned Right view needs the standard layout's taller row; the
# undimensioned Top takes the shorter cell.
VIEW_LAYOUT = "standard"
SUPPLIER_MARGINS = {"*Right": (0.020, 0.020, 0.060, 0.012)}
DIAMETER_LANE = 0.014  # vertical diameter lines, out from the head / thread end
LENGTH_LANE = 0.008  # horizontal length lines, out from the head's rim
# The shoulder Ø's value and callout shelve right of its dimension line, at
# the axis, clear of its short 7.9 mm span.
SHELVES = {"SupplierShoulderDiameter": (False, "right")}
# Note anchors are their text's top-left corner.  The thread note's rows stand
# above the head's rim, its left edge just past the shoulder step, so its
# leader drops almost straight onto the thread next to the shoulder.
THREAD_NOTE_RIGHT = 0.002  # right of the shoulder step
THREAD_NOTE_RISE = 0.021  # above the head rim
THREAD_LANDING = 0.2  # of the thread length, from the shoulder
_REFERENCES = {
    name: {
        "label": f"{name}@{part.REFERENCE_FEATURE}", "units": "in",
        "precision": part.REFERENCE_FORMATS[name][0], "expected_mm": value,
        "presentation": part.REFERENCE_FORMATS[name][1],
        "callout": part.REFERENCE_FORMATS[name][3],
    }
    for name, value, _ in part.REFERENCE_DIMENSIONS
}


def _assert_dimensions(adapter, displays) -> None:
    for name, display in displays.items():
        assert_supplier_reference_dimension(adapter, display, **_REFERENCES[name])
        assert_supplier_screw_unbanded({name: display})


def _right_stations(adapter, right):
    """Sheet points on the axis: head end, head underside, step, thread tip."""
    stations = {
        key: model_point_in_view(adapter, right, (0.0, 0.0, z / 1000.0), label=f"shoulder screw {key}")
        for key, z in (("head", part.LENGTH), ("joint", part.SHOULDER_LENGTH),
                       ("step", 0.0), ("tip", -part.THREAD_LENGTH))
    }
    scale = tuple(float(value) for value in _early_bound(right, "IView").ScaleRatio)
    return stations, scale[0] / scale[1]


def _place_dimensions(adapter, right) -> dict[str, object]:
    """Import the three supplier references into the Right view."""
    view = _early_bound(right, "IView")
    view.UpdateViewDisplayGeometry()
    at, scale = _right_stations(adapter, view)
    axis_y = at["step"][1]
    rim = part.HEAD_DIA / 2000.0 * scale
    keep = {
        "SupplierHeadDiameter": (at["head"][0] - DIAMETER_LANE, axis_y),
        "SupplierShoulderDiameter": (at["tip"][0] + DIAMETER_LANE, axis_y),
        "SupplierShoulderLength": ((at["joint"][0] + at["step"][0]) / 2.0, axis_y + rim + LENGTH_LANE),
    }
    displays = {}
    for raw in curate_view_dimensions(
        adapter, view, keep=keep, view_label="shoulder screw RIGHT",
        dimensions_by_feature={part.REFERENCE_FEATURE: tuple(_REFERENCES)},
    ):
        name = dimension_name(adapter, raw)
        display = _early_bound(
            _early_bound(raw, "IAnnotation").GetSpecificAnnotation(), "IDisplayDimension"
        )
        displays[name] = supplier_reference_dimension(adapter, display, **_REFERENCES[name])
    if set(displays) != set(keep):
        raise RuntimeError(f"shoulder screw RIGHT dimensions incomplete: {sorted(displays)}")
    return displays


def _add_thread_note(adapter, right) -> None:
    """Lead the thread note to the thread's upper silhouette."""
    at, scale = _right_stations(adapter, right)
    rim = part.HEAD_DIA / 2000.0 * scale
    thread = model_point_in_view(
        adapter, right,
        (0.0, part.MAJOR_DIA / 2000.0, -part.THREAD_LENGTH * THREAD_LANDING / 1000.0),
        label="shoulder screw thread silhouette",
    )
    add_attached_note(
        adapter, right, text=part.THREAD_NOTE, entity_xy=thread,
        note_xy=(at["step"][0] + THREAD_NOTE_RIGHT, at["step"][1] + rim + THREAD_NOTE_RISE),
        label="shoulder screw thread", entity_type="SILHOUETTE",
    )


def _settled_right(adapter):
    """Reacquire the Right view's three references and its one thread note."""
    rights = [view for view in iter_views(adapter) if str(view.GetOrientationName()) == "*Right"]
    if len(rights) != 1:
        raise RuntimeError("shoulder screw settled sheet has no single Right view")
    view = _early_bound(rights[0], "IView")
    found: dict[str, list] = {}
    display = view.GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        name, _, feature = str(
            _early_bound(display.GetDimension2(0), "IDimension").FullName
        ).partition("@")
        if name in _REFERENCES and feature.partition("@")[0] == part.REFERENCE_FEATURE:
            found.setdefault(name, []).append(display)
        display = display.GetNext5()
    if set(found) != set(_REFERENCES) or any(len(rows) != 1 for rows in found.values()):
        raise RuntimeError(f"shoulder screw RIGHT dimensions changed: { {k: len(v) for k, v in found.items()} }")
    texts = [
        str(_early_bound(note, "INote").GetText()).replace("\r\n", "\n")
        for note in view.GetNotes() or ()
    ]
    if texts.count(part.THREAD_NOTE) != 1:
        raise RuntimeError("shoulder screw RIGHT view must carry the thread note once")
    return {name: rows[0] for name, rows in found.items()}


async def build(adapter) -> dict[str, str]:
    proofs = []

    def supplier_dimensions(adapter, views):
        if proofs:
            raise RuntimeError("supplier reference callback repeated")
        line_font = _construction_curves_as_outline(adapter)
        right = views["*Right"]
        displays = _place_dimensions(adapter, right)
        _assert_dimensions(adapter, displays)
        _add_thread_note(adapter, right)
        # Both side views carry the axis as a native centerline, picked on the
        # shoulder face at mid-length.
        for orientation, normal in (("*Top", (0.0, 1.0)), ("*Right", (1.0, 0.0))):
            view = views[orientation]
            add_view_centerline(
                adapter, view, label=f"shoulder screw {orientation[1:].upper()} axis",
                face_xy=model_point_in_view(
                    adapter, view,
                    (normal[0] * part.SHOULDER_DIA / 2000.0, normal[1] * part.SHOULDER_DIA / 2000.0,
                     part.SHOULDER_LENGTH / 2000.0),
                    label=f"shoulder screw {orientation[1:].upper()} shoulder face",
                ),
            )
        # Shelve last, after the note and centerline rebuilds: the retained
        # stations are the ones the settled sheet keeps.
        stations = shelve_supplier_text(adapter, displays, SHELVES)

        def assert_references():
            line_font()
            settled = _settled_right(adapter)
            _assert_dimensions(adapter, settled)
            assert_supplier_shelves(adapter, settled, SHELVES, stations)

        proofs.append(assert_references)

    def assert_supplier_dimensions():
        if len(proofs) != 1:
            raise RuntimeError("supplier references omitted or repeated")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=False, number_fit=NumberFit.SHRINK_TO_CELL,
        view_layout=VIEW_LAYOUT, supplier_dimensions=supplier_dimensions,
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
