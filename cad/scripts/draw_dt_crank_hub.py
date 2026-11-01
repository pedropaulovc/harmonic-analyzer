r"""Create the curated manufacturing drawing for through hub MHA-DT-31."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimensions,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm, drill_process
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_hub_notes import (
    BORE_CALLOUT,
    CROSS_HOLE_CALLOUT,
    HUB_LENGTH_CALLOUT,
    PIN_PROUD_CALLOUT,
    RELIEF_LENGTH_CALLOUT,
    SEAM_CALLOUT,
    SEAT_CALLOUT,
)
from dt_crank_hub_spec import (
    AXIAL_PIN_DIA,
    AXIAL_PIN_RADIUS_FROM_AXIS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HUB_BARREL_DIA,
    HUB_LENGTH,
    HUB_SEAT_LENGTH,
    REFERENCE_DIMENSIONS,
    RELIEF_STATION,
    SERVICE_PIN_HOLE_SPEC,
    SERVICE_PIN_STATION,
)


SPEC = DRAWINGS_BY_NAME["dt_crank_hub"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = VIEW_SCALE[0] / 1000.0  # sheet metres per model millimetre
# Turned part, laid as it sits in the lathe (drawing-guidelines.md rule 11 (turned parts read like the lathe)): the *Right view
# rotated a quarter turn so the axis is horizontal, inboard end on the left
# and the faced outboard end on the right.  +90 degrees sends model +Y to
# paper-left and model +Z (the six-o'clock MHA-DT-VN-59 seam) to paper-down.  The
# outboard end view is the *Bottom orientation turned half a turn, which is
# exactly the third-angle RIGHT view of that profile: it sits on the profile's
# axis to its right, with the seam at six o'clock as the notes call it.
SIDE_VIEW_ANGLE = math.pi / 2.0
END_VIEW_ANGLE = math.pi
SIDE_CENTER = (0.200, 0.160)
END_CENTER = (0.295, SIDE_CENTER[1])
ISO_CENTER = (0.380, 0.228)


def _sheet_x(station_mm: float) -> float:
    """Sheet X of a model-Y station (0 = outboard face) on the side view."""
    return SIDE_CENTER[0] - (station_mm - HUB_LENGTH / 2.0) * _S


def _sheet_y(z_mm: float) -> float:
    """Sheet Y of a model-Z offset from the axis on the side view (+Z down)."""
    return SIDE_CENTER[1] - z_mm * _S


OUTBOARD_X = _sheet_x(0.0)
SHOULDER_X = _sheet_x(HUB_SEAT_LENGTH)
INBOARD_X = _sheet_x(HUB_LENGTH)
RELIEF_X = _sheet_x(RELIEF_STATION)
SERVICE_PIN_CENTER = (_sheet_x(SERVICE_PIN_STATION), SIDE_CENTER[1])
SERVICE_PIN_DIA = blind_cut_dia_mm(SERVICE_PIN_HOLE_SPEC)
SERVICE_PIN_TOP_RIM = (
    SERVICE_PIN_CENTER[0],
    SERVICE_PIN_CENTER[1] + SERVICE_PIN_DIA / 2.0 * _S,
)
BARREL_TOP = _sheet_y(-HUB_BARREL_DIA / 2.0)
BARREL_BOTTOM = _sheet_y(HUB_BARREL_DIA / 2.0)
# Pick the barrel's cylindrical face between the rear relief and the MHA-DT-09
# cross-hole, above the axis.  The through hole is seen end-on here, so a pick
# inside its circle sees no face (run 20260923T023246758Z-97bfca38).
BARREL_FACE_PICK = ((RELIEF_X + SERVICE_PIN_CENTER[0]) / 2.0, SIDE_CENTER[1] + 0.015)
# Every size and callout sits outside the silhouettes.
# - Lengths: the seat from the faced outboard end, the MHA-DT-09 station from
#   the arm shoulder (drawing-guidelines.md rule 17 (walls and webs)) and the relief from the rear face on
#   rows below the profile; the toleranced overall, front face to rear
#   face, on the row below them.  The barrel is the remainder, not printed.
#   The two banded lengths carry the mate they serve under their text.  The
#   seat and station row stands above the relief's: the overall's stacked
#   +/- band reached the shared row's extension lines (farm run
#   20261031T205208603Z).  The overall's text stands clear under the
#   relief's dimension line, which read into it (machinist review, farm run
#   20261031T233549214Z).
# - Relief and barrel diameters: left of the inboard end, the relief nearer.
#   Seat diameter: between the profile and the end view, its value and
#   light-press callout above.
# - Cross-hole callout: above the barrel, its leader rising almost straight
#   from the hole's top rim, clear of the barrel diameter's extension lines.
# - Bore callout: right of the end view, its leader entering the bore from the
#   right, clear of the six-o'clock seam; the seam callout below the end view.
# - MHA-DT-09 big end's MIN proud: the pin's big end (model -X) is paper-right
#   on the end view (*Bottom turned half a turn), on the horizontal
#   centreline.  Its value and callout print right of the big end's extension
#   line, above the bore callout and below the isometric's label.
_ROW_Y = (0.120, 0.102)
_STATION_ROW_Y = _ROW_Y[0] + 0.006
END_KEEP = {
    "BoreDia": (END_CENTER[0] + 0.070, END_CENTER[1] - 0.020),
    # Four callout lines (r7 review: name the phantom, the pin and the ring):
    # one line higher than the three-line block of farm run
    # 20261031T233549214Z, its last line still above the dimension line, and
    # 7 mm further right, so the wider block's left edge clears the phantom
    # big end (x <= END_CENTER + 31.2 mm, y within 6 mm of the axis).
    "PinProud": (END_CENTER[0] + 0.072, END_CENTER[1] + 0.014),
}
# The cross-hole station is measured from the arm shoulder it must stay clear
# of (dt_crank_hub_geometry), not chained from 8.0: its arrowhead there is
# the ASME dimension-origin circle (r7 review of farm run
# 20261101T022045634Z; draw_mg_wheel_axle's idiom).
ORIGIN_DIMENSIONS = {"ServicePinFromShoulder": SHOULDER_X}
_ORIGIN_ARROWHEAD = 4  # swArrowStyle_e.swORIGIN_ARROWHEAD
_CLOSED_ARROWHEAD = 1  # swArrowStyle_e.swCLOSED_ARROWHEAD
# The hub's half of the seam is the arc bulging from the seat edge toward the
# bore; the callout attaches 45 degrees up its right flank.
SEAM_CENTER = (END_CENTER[0], END_CENTER[1] - AXIAL_PIN_RADIUS_FROM_AXIS * _S)
SEAM_EDGE_PICK = (
    SEAM_CENTER[0] + AXIAL_PIN_DIA / 2.0 * _S * math.cos(math.pi / 4.0),
    SEAM_CENTER[1] + AXIAL_PIN_DIA / 2.0 * _S * math.sin(math.pi / 4.0),
)
# Below the end view with its LEFT end just right of the seam, so the leader
# drops almost straight to it; a block centred under the view attached at its
# far end and crossed both its own text and the bore leader (run a2e1cd67).
SEAM_CALLOUT_XY = (0.303, 0.105)
SIDE_KEEP = {
    "SeatLength": ((OUTBOARD_X + SHOULDER_X) / 2.0, _STATION_ROW_Y),
    "ServicePinFromShoulder": ((SHOULDER_X + SERVICE_PIN_CENTER[0]) / 2.0, _STATION_ROW_Y),
    # The toleranced .990 and its two-line callout fill the span between its
    # extension lines and sat on its own dimension line (machinist review of
    # the inch sheet, r2): they print right of the outboard face instead, the
    # dimension line running out to them, clear of the seam callout.
    "HubLength": (OUTBOARD_X + 0.032, _ROW_Y[1]),
    # Its toleranced text and callout are wider than the relief: they print
    # outside the span, left of the rear face, the dimension line running out
    # to them, the callout ending short of the overall's dimension line.
    "ReliefLength": (INBOARD_X - 0.030, _ROW_Y[0]),
    "ReliefDia": (INBOARD_X - 0.012, SIDE_CENTER[1]),
    "BarrelDia": (INBOARD_X - 0.034, SIDE_CENTER[1]),
    "SeatDia": (OUTBOARD_X + 0.020, 0.225),
}
HOLE_CALLOUT_XY = (0.150, 0.222)
ISO_NOTE_XY = (0.345, 0.190)
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "SeatDia": SEAT_CALLOUT,
    "HubLength": HUB_LENGTH_CALLOUT,
    "ReliefLength": RELIEF_LENGTH_CALLOUT,
    "PinProud": PIN_PROUD_CALLOUT,
}


def _set_callout_below(display: Any, text: str, label: str) -> None:
    """Put the matched-operation prose UNDER a native hole callout.

    The drill size reads first, in the order the work is done; the fit and
    mate prose follows in the callout-below compartment (the Ø9.550 bore
    callout's order).  ``SetText`` reports nothing, so it is read back.
    """
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(4, text)  # swDimensionTextCalloutBelow
    applied = str(display.GetText(4) or "")
    if applied.replace("\r", "") != text:
        raise RuntimeError(f"{label}: callout-below text did not persist: {applied!r}")


def _arrowheads(annotation: Any, label: str) -> list[tuple[float, int]]:
    """Each arrowhead's tip x on the sheet and its style (draw_mg_wheel_axle)."""
    data = annotation.GetDisplayData()
    if data is None:
        raise RuntimeError(f"{label} has no display data")
    data = _early_bound(data, "IDisplayData")
    heads = []
    for index in range(int(data.GetArrowHeadCount() or 0)):
        values = [float(value) for value in (data.GetArrowHeadAtIndex2(index) or ())]
        if len(values) < 9:
            raise RuntimeError(f"{label} arrowhead {index} is incomplete: {values!r}")
        heads.append((values[0], round(values[8])))
    if len(heads) != 2:
        raise RuntimeError(f"{label} has {len(heads)} arrowheads, expected 2")
    return heads


def _set_dimension_origin(
    adapter: Any, annotation: Any, *, origin_x: float, label: str
) -> None:
    """Put the dimension-origin circle on the arrowhead at ``origin_x``, read
    back from the ink (draw_mg_wheel_axle)."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    heads = _arrowheads(annotation, label)
    near = min(range(2), key=lambda index: abs(heads[index][0] - origin_x))
    styles = [_CLOSED_ARROWHEAD, _CLOSED_ARROWHEAD]
    styles[near] = _ORIGIN_ARROWHEAD
    for attempt in (styles, styles[::-1]):
        if not display.SetArrowHeadStyle2(False, *attempt):
            raise RuntimeError(f"failed to set the {label} arrowhead styles")
        rebuild_drawing(adapter, label=f"{label} dimension origin")
        heads = _arrowheads(annotation, label)
        at_origin = min(heads, key=lambda head: abs(head[0] - origin_x))
        far = max(heads, key=lambda head: abs(head[0] - origin_x))
        if (at_origin[1], far[1]) == (_ORIGIN_ARROWHEAD, _CLOSED_ARROWHEAD):
            return
    raise RuntimeError(f"{label} origin circle is not at the shoulder: {heads!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-hub source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Through Hub Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank hub; through sleeve; matched shoulder fit; taper pin",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    for view, angle, label in (
        (front, END_VIEW_ANGLE, "outboard end view"),
        (right, SIDE_VIEW_ANGLE, "side view"),
    ):
        native = _early_bound(view, "IView")
        native.Angle = angle
        if abs(math.remainder(float(native.Angle) - angle, 2.0 * math.pi)) > 1e-9:
            raise RuntimeError(f"failed to rotate the crank-hub {label}")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=END_KEEP,
        view_label="outboard end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    for name, origin_x in ORIGIN_DIMENSIONS.items():
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one crank-hub {name} dimension, got {len(matches)}")
        _set_dimension_origin(
            adapter, matches[0], origin_x=origin_x, label=f"crank hub {name}"
        )

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to crank-hub end view")
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to crank-hub side view")
    add_view_centerline(
        adapter,
        right,
        face_xy=BARREL_FACE_PICK,
        label="crank hub axis centerline",
    )
    cross_hole = add_native_hole_callout(
        adapter,
        right,
        edge_xy=SERVICE_PIN_TOP_RIM,
        callout_xy=HOLE_CALLOUT_XY,
        label="MHA-DT-09 hub pilot",
        process=drill_process(SERVICE_PIN_HOLE_SPEC),
    )
    # The drilled size prints .XXX, the Hole Wizard callout's places.
    set_hole_callout_precision(cross_hole, {"hw-diam": 3}, label="MHA-DT-09 hub pilot")
    _set_callout_below(cross_hole, CROSS_HOLE_CALLOUT, "MHA-DT-09 hub pilot")
    add_attached_note(
        adapter,
        front,
        text=SEAM_CALLOUT,
        entity_xy=SEAM_EDGE_PICK,
        note_xy=SEAM_CALLOUT_XY,
        label="MHA-DT-VN-59 seam callout",
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Through Hub Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
