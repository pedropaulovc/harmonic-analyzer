r"""Create the curated manufacturing drawing for through hub MHA-137."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm, drill_process
from crank_hub_spec import (
    AXIAL_PIN_DIA,
    AXIAL_PIN_RADIUS_FROM_AXIS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    HUB_BARREL_DIA,
    HUB_LENGTH,
    HUB_SEAT_DIA,
    HUB_SEAT_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    REFERENCE_DIMENSIONS,
    SERVICE_PIN_HOLE_SPEC,
    SERVICE_PIN_STATION,
)
from crank_hub_notes import (
    BORE_CALLOUT,
    CROSS_HOLE_CALLOUT,
    SEAM_CALLOUT,
    SEAT_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["crank_hub"]
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
# Turned part, laid as it sits in the lathe (policy rule 7): the *Right view
# rotated a quarter turn so the axis is horizontal, inboard end on the left
# and the faced outboard end on the right.  +90 degrees sends model +Y to
# paper-left and model +Z (the six-o'clock MHA-138 seam) to paper-down.  The
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
SERVICE_PIN_CENTER = (_sheet_x(SERVICE_PIN_STATION), SIDE_CENTER[1])
SERVICE_PIN_DIA = blind_cut_dia_mm(SERVICE_PIN_HOLE_SPEC)
SERVICE_PIN_TOP_RIM = (
    SERVICE_PIN_CENTER[0],
    SERVICE_PIN_CENTER[1] + SERVICE_PIN_DIA / 2.0 * _S,
)
BARREL_TOP = _sheet_y(-HUB_BARREL_DIA / 2.0)
BARREL_BOTTOM = _sheet_y(HUB_BARREL_DIA / 2.0)
# Pick the barrel's cylindrical face between the inboard end and the MHA-024
# cross-hole, above the axis.  The through hole is seen end-on here, so a pick
# inside its circle sees no face (run 20260923T023246758Z-97bfca38).
BARREL_FACE_PICK = (INBOARD_X + 0.008, SIDE_CENTER[1] + 0.015)
# Every size and callout sits outside the silhouettes.
# - Lengths: the seat from the faced outboard end, then the barrel and the
#   MHA-024 station from the arm shoulder (policy rule 12), stacked below the
#   profile shortest-first; the parenthesised overall is the bottom row.
# - Barrel diameter: left of the inboard end.  Seat diameter: between the
#   profile and the end view, its value and matched-fit callout above.
# - Cross-hole callout: above the barrel, its leader rising almost straight
#   from the hole's top rim, clear of the barrel diameter's extension lines.
# - Bore callout: right of the end view, its leader entering the bore from the
#   right, clear of the six-o'clock seam; the seam callout below the end view.
_ROW_Y = (0.120, 0.108, 0.096)
END_KEEP = {"BoreDia": (END_CENTER[0] + 0.070, END_CENTER[1] - 0.020)}
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
# The overall is picked on the two end-face edges seen edge-on, above the axis
# where the seat and barrel circles -- not the bore -- project.
OVERALL_PICK_Y = SIDE_CENTER[1] + 0.8 * HUB_SEAT_DIA / 2.0 * _S
SIDE_KEEP = {
    "SeatLength": ((OUTBOARD_X + SHOULDER_X) / 2.0, _ROW_Y[0]),
    "ServicePinFromShoulder": ((SHOULDER_X + SERVICE_PIN_CENTER[0]) / 2.0, _ROW_Y[0]),
    "BarrelLength": ((SHOULDER_X + INBOARD_X) / 2.0, _ROW_Y[1]),
    "BarrelDia": (INBOARD_X - 0.020, SIDE_CENTER[1]),
    "SeatDia": (OUTBOARD_X + 0.020, 0.225),
}
HOLE_CALLOUT_XY = (0.150, 0.222)
ISO_NOTE_XY = (0.345, 0.180)
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "SeatDia": SEAT_CALLOUT,
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


def _add_overall_reference(adapter: Any, view: Any) -> None:
    """Print the parenthesised overall under the shoulder-based length chain.

    Every controlling length is a model dimension whose places the part
    authored; the overall is their read-only sum with no model dimension to
    import, so its places come from the spec's ``DRAWING_REFERENCE_PRECISION``
    -- never a literal typed here.  ``SetPrecision3`` reports rejection
    through its return status rather than by raising, so it is read back.
    """
    label = "overall length reference"
    overall = add_edge_dimension(
        adapter,
        view,
        p0=(OUTBOARD_X, OVERALL_PICK_Y),
        p1=(INBOARD_X, OVERALL_PICK_Y),
        text_xy=((OUTBOARD_X + INBOARD_X) / 2.0, _ROW_Y[2]),
        label=label,
        orientation="horizontal",
    )
    display = _early_bound(overall, "IDisplayDimension")
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    places = DRAWING_REFERENCE_PRECISION[label]
    # -1: swDimensionPrecisionSettings_e do-not-change for the dual and both
    # tolerance places.  The subscript is written out again because
    # _drawing_contract only accepts a spec lookup here.
    adapter._attempt(
        lambda: display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    )
    applied = adapter._attempt(display.GetPrimaryPrecision2)
    if applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured - HUB_LENGTH) > 1e-5:
        raise RuntimeError(f"{label}: measured {measured:g}, expected {HUB_LENGTH:g} mm")


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    _add_overall_reference(adapter, right)

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
        label="MHA-024 hub pilot",
        process=drill_process(SERVICE_PIN_HOLE_SPEC),
    )
    _set_callout_below(cross_hole, CROSS_HOLE_CALLOUT, "MHA-024 hub pilot")
    add_attached_note(
        adapter,
        front,
        text=SEAM_CALLOUT,
        entity_xy=SEAM_EDGE_PICK,
        note_xy=SEAM_CALLOUT_XY,
        label="MHA-138 seam callout",
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
