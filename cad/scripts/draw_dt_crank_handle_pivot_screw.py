r"""Create the MHA-DT-32 crank handle pivot screw manufacturing drawing.

The SLDPRT remains authoritative.  A screw carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the running-fit shoulder keeps its
native size band and one bearing-surface finish, the shoulder and thread
lengths keep their native bands, and every other size is an ordinary model
dimension at its part-authored places.

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the thread tip on
the left and the slotted head on the right.  Axial locations read from the
tip (see ``dt_crank_handle_pivot_screw_spec``).  The head-end view is
the ``*Back`` orientation, which is exactly the third-angle RIGHT view of that
profile, so it sits on the profile's axis to its right and shows the slot.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_pivot_screw.py dt-crank-handle-pivot-screw
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _com import _early_bound
from _check import check
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_crank_handle_pivot_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEAD_DIA,
    HEAD_DIA_CALLOUT,
    HEAD_LENGTH,
    HEAD_LENGTH_CALLOUT,
    OVERALL_LENGTH,
    REFERENCE_DIMENSIONS,
    RELIEF_CALLOUT,
    RELIEF_DIA,
    RELIEF_END_STATION,
    RELIEF_LEAD,
    RELIEF_LEAD_NOTE,
    SEAT_EDGE_NOTE,
    SEAT_STATION,
    SHOULDER_DIA,
    SHOULDER_FIT_CALLOUT,
    SHOULDER_LENGTH_CALLOUT,
    SURFACE_FINISHES,
    THREAD_CALLOUT,
    THREAD_MODEL_DIA,
    THREAD_SIZE,
    TIP_CHAMFER,
    TIP_CHAMFER_CALLOUT,
)


SPEC = DRAWINGS_BY_NAME["dt_crank_handle_pivot_screw"]
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

# Both orthographic views print at the sheet scale, so neither needs a caption.
# 3:1 lays the 69.5 profile 208 mm long and the 1.0 slot 3 mm wide.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.160, 0.165)
# Third-angle right view of the slotted head end, on the profile's axis.
END_CENTER = (0.322, SIDE_CENTER[1])
ISO_CENTER = (0.380, 0.225)
ISO_SCALE = (1, 1)


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left).

    The view is centred on the model bbox, head face (z=0) to thread tip.
    """
    return SIDE_CENTER[0] + (OVERALL_LENGTH / 2.0 - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the screw axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


HEAD_FACE_X = _sheet_x(0.0)
UNDERHEAD_X = _sheet_x(HEAD_LENGTH)
SEAT_X = _sheet_x(SEAT_STATION)
RELIEF_END_X = _sheet_x(RELIEF_END_STATION)
TIP_X = _sheet_x(OVERALL_LENGTH)
# Where the full thread meets the tip chamfer.
THREAD_START_X = _sheet_x(OVERALL_LENGTH - TIP_CHAMFER)
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
SHOULDER_TOP_Y = _sheet_y(SHOULDER_DIA / 2.0)
THREAD_TOP_Y = _sheet_y(THREAD_MODEL_DIA / 2.0)
THREAD_BOTTOM_Y = _sheet_y(-THREAD_MODEL_DIA / 2.0)
RELIEF_TOP_Y = _sheet_y(RELIEF_DIA / 2.0)
RELIEF_MID_X = (SEAT_X + RELIEF_END_X) / 2.0
# The relief floor runs from the foot of the 45-degree lead to the flank.
RELIEF_FLOOR_MID_X = (_sheet_x(SEAT_STATION + RELIEF_LEAD) + RELIEF_END_X) / 2.0

# Rows below the profile, 15 mm apart (text sits ~3 mm above its requested
# point and the dimension line ~5 mm below it).  Row 0 carries the thread
# length from the tip on the left and the head length from the under-head face
# on the right; row 1 the fitted shoulder length from the seat face; row 2 the
# reference overall.  Row 0 stands 34 mm below the axis so the relief Ø and
# the thread callout can print between it and the profile.  No extension line
# crosses a dimension line.
_ROW_Y = (SIDE_CENTER[1] - 0.034, SIDE_CENTER[1] - 0.049, SIDE_CENTER[1] - 0.064)
SIDE_KEEP = {
    "ThreadLength": ((TIP_X + SEAT_X) / 2.0, _ROW_Y[0]),
    # Right of the head face, outside its extension lines, so its callout
    # stands clear of them and of the under-head and overall extension lines
    # (farm r8 of f5256bf3d: at + 0.020 the 43-mm block's left end crossed
    # the head face's extension line).
    "HeadLength": (HEAD_FACE_X + 0.026, _ROW_Y[0]),
    # The fitted shoulder, seat face to under-head, its fit-up as its callout:
    # two 46-character rows (117 mm) between its 158-mm extension lines.
    "ShoulderLength": ((SEAT_X + UNDERHEAD_X) / 2.0, _ROW_Y[1]),
    "OverallLength": ((TIP_X + HEAD_FACE_X) / 2.0, _ROW_Y[2]),
    # Diameters on the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe)).  The shoulder's dimension line
    # crosses the shoulder right of the relief Ø's callout below it; the
    # head's stands clear of the head face, left of the end view.
    "ShoulderDia": (SEAT_X + 0.075, SIDE_CENTER[1] + 0.030),
    # Above the head, so the callout under the value stands clear of its
    # extension lines and of the slot depth's text left of it.
    "HeadDia": (HEAD_FACE_X + 0.014, SIDE_CENTER[1] + 0.032),
    # The thread-relief groove against the seat face.  Its width from the seat
    # face reads above it alone; its Ø reads below it, the dimension line
    # standing on the floor so nothing crosses.  The 45-degree lead has its
    # own leader note (LEAD_NOTE_XY).
    "ReliefWidth": (RELIEF_MID_X, SIDE_CENTER[1] + 0.022),
    "ReliefDia": (RELIEF_FLOOR_MID_X, SIDE_CENTER[1] - 0.016),
    # The tip chamfer's axial leg reads below-left of the tip, clear of the
    # thread size's extension line at the tip and of the callout above.
    "TipChamfer": (TIP_X - 0.020, SIDE_CENTER[1] - 0.016),
    # The slot shows as a notch in the head face; its depth reads above it.
    "SlotDepth": (HEAD_FACE_X - 0.0015, SIDE_CENTER[1] + 0.026),
}
# The relief Ø's dimension line stands on the floor (SIDE_KEEP); its text
# goes on an OffsetText leader so the seat-face extension line (the thread
# length's right side) cannot run through the callout.  With OffsetText the
# anchor is the CENTRE of the Ø line's bottom edge and the callout is centred
# under it (a dimension exposes no GetExtent), measured on farm run 69a2f961's
# render: the underline, where the leader lands, sits 5.6 mm below the anchor.
# Farm r8 of f5256bf3d rendered the inch callout at 2.5 mm a character, so
# its 18-character rows span 46 mm.  The text's left edge stands 12 mm right
# of the seat face (3.5 mm before the thread callout moved below the thread)
# and 28 mm below the axis, so the leader, dropping to the Ø line under the
# seat-face corner rather than through the shoulder, stays 5 mm clear of the
# thread callout's right end.  The shoulder Ø's arrow is right of it.
RELIEF_DIA_TEXT_WIDTH = 0.046
RELIEF_DIA_TEXT_UNDERLINE_DROP = 0.0056
RELIEF_DIA_TEXT_CLEARANCE = 0.012
RELIEF_DIA_TEXT_XY = (
    SEAT_X + RELIEF_DIA_TEXT_CLEARANCE + RELIEF_DIA_TEXT_WIDTH / 2.0,
    SIDE_CENTER[1] - 0.028,
)
# The 3-mm slot is narrower than the text, so the value stands above its
# extension lines rather than between them.
END_KEEP = {
    "SlotWidth": (END_CENTER[0] + 0.022, END_CENTER[1] + 0.010),
}
# The thread callout lands on the full thread's lower silhouette just in from
# the tip chamfer, from below: above the thread, its leader ran through where
# the relief lead's note now stands (#290 review of b28d38a16).  Its
# 9-character text (23.5 mm on farm r10 of 4e4991e0a) stands 15 mm below the
# axis between the chamfer's extension line and the seat face's, which it
# crossed when it started 5.6 mm in from the thread start (r10).
THREAD_PICK = (THREAD_START_X + 0.0015, THREAD_BOTTOM_Y)
THREAD_NOTE_XY = (THREAD_START_X + 0.0021, SIDE_CENTER[1] - 0.015)
# The 45-degree relief lead's own note (#290 review of b28d38a16), on the
# lead's upper silhouette.  The lead faces up and left, so the note stands up
# and left with its 18-character rows (46 mm) ending 15 mm left of the relief
# end: its leader passes under the relief width's left arrow and over the
# thread, crossing only that dimension's extension line.
LEAD_PICK = (
    SEAT_X - RELIEF_LEAD * _S / 2000.0,
    _sheet_y(RELIEF_DIA / 2.0 + RELIEF_LEAD / 2.0),
)
LEAD_NOTE_WIDTH = 0.046
LEAD_NOTE_XY = (RELIEF_END_X - 0.0147 - LEAD_NOTE_WIDTH, SIDE_CENTER[1] + 0.022)
# The running shoulder's upper flank, right of the Ø dimension line and its
# callout block (farm r1 of eb22a22f1: at x - 0.050 the leader ran through
# the block's right end).
FINISH_PICK = (UNDERHEAD_X - 0.040, SHOULDER_TOP_Y)
FINISH_SYMBOL = (UNDERHEAD_X - 0.030, SIDE_CENTER[1] + 0.030)
# A point on the shoulder face, clear of the Ø dimension line.
CENTERLINE_PICK = (UNDERHEAD_X - 0.025, SIDE_CENTER[1] + 0.003)
# The seat edge's break note lands on the shoulder's silhouette 2.5 mm right
# of its seat-face corner (6 mm read as the shank, not the corner: #290 review
# of d72bdd039), from up and right, above the relief width and the shoulder
# Ø's callout blocks: landing on the seat face itself, its leader crossed the
# relief width's dimension line (farm r8 of f5256bf3d).  The note stands 24 mm
# right of the seat face so the leader passes right of that dimension line's
# outside arrow, which ends 6.4 mm right of the seat face (farm r13: from
# 20 mm and 2 mm the leader crossed it).
SEAT_EDGE_PICK = (SEAT_X + 0.0025, SHOULDER_TOP_Y)
SEAT_EDGE_NOTE_XY = (SEAT_X + 0.024, SIDE_CENTER[1] + 0.060)
# The relief Ø's arrows stand inside the groove: outside, the upper arrow's
# stub stood above the floor where the lead note's leader passes (#290 review
# of f166646c4).
_ARROWS_INSIDE = 0  # swDimArrowsSide_e.swDimArrowsInside
ISO_NOTE_XY = (0.352, 0.200)


def _set_relief_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    matches = [a for a in annotations if dimension_name(adapter, a) == "ReliefDia"]
    if len(matches) != 1:
        raise RuntimeError("expected one MHA-DT-32 ReliefDia dimension")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.ArrowSide = _ARROWS_INSIDE
    if int(display.ArrowSide) != _ARROWS_INSIDE:
        raise RuntimeError("MHA-DT-32 ReliefDia did not keep its arrows inside")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-pivot-screw source", await adapter.open_model(str(SOURCE)))
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
            0: "Crank Handle Pivot Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"crank handle pivot; slotted shoulder screw; {THREAD_SIZE}; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="head-end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *end_annotations]
    set_dimension_callouts(
        adapter, annotations, {"ReliefDia": RELIEF_CALLOUT}, location="below"
    )
    set_dimension_callouts(
        adapter,
        annotations,
        {
            "TipChamfer": TIP_CHAMFER_CALLOUT,
            "ShoulderLength": SHOULDER_LENGTH_CALLOUT,
            "ShoulderDia": SHOULDER_FIT_CALLOUT,
            "HeadDia": HEAD_DIA_CALLOUT,
            "HeadLength": HEAD_LENGTH_CALLOUT,
        },
        location="below",
    )
    offset_dimension_text(adapter, side_annotations, {"ReliefDia": RELIEF_DIA_TEXT_XY})
    _set_relief_arrows_inside(adapter, side_annotations)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-DT-32 {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"MHA-DT-32 {name}")

    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-DT-32 head-end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-DT-32 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-DT-32 thread callout",
        entity_type="SILHOUETTE",
    )
    add_attached_note(
        adapter,
        side,
        text=RELIEF_LEAD_NOTE,
        entity_xy=LEAD_PICK,
        note_xy=LEAD_NOTE_XY,
        label="MHA-DT-32 relief lead",
        entity_type="SILHOUETTE",
    )
    add_attached_note(
        adapter,
        side,
        text=SEAT_EDGE_NOTE,
        entity_xy=SEAT_EDGE_PICK,
        note_xy=SEAT_EDGE_NOTE_XY,
        label="MHA-DT-32 seat edge break",
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_shoulder"),
        label="MHA-DT-32 pivot-shoulder finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Pivot Screw Manufacturing Drawing",
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
