r"""Create the MHA-139 crank handle pivot screw manufacturing drawing.

The SLDPRT remains authoritative.  A screw carries no datum and no
geometric-control frame (policy rule 3): the running-fit shoulder keeps its
native size band and one bearing-surface finish, the shoulder and thread
lengths keep their native bands, and every other size is an ordinary model
dimension at its part-authored places.

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the thread tip on
the left and the slotted head on the right.  Lengths baseline from the
under-head face (see ``crank_handle_pivot_screw_spec``).  The head-end view is
the ``*Back`` orientation, which is exactly the third-angle RIGHT view of that
profile, so it sits on the profile's axis to its right and shows the slot.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_handle_pivot_screw.py crank-handle-pivot-screw
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_dimension_callouts,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from crank_handle_pivot_screw_spec import (
    CHAMFER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEAD_DIA,
    HEAD_LENGTH,
    OVERALL_LENGTH,
    REFERENCE_DIMENSIONS,
    RELIEF_DIA,
    RELIEF_END_STATION,
    RELIEF_LEAD,
    SEAT_STATION,
    SHOULDER_DIA,
    SURFACE_FINISHES,
    THREAD_CALLOUT,
    THREAD_MODEL_DIA,
    TIP_CHAMFER,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["crank_handle_pivot_screw"]
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
RELIEF_TOP_Y = _sheet_y(RELIEF_DIA / 2.0)
RELIEF_MID_X = (SEAT_X + RELIEF_END_X) / 2.0
# The relief floor runs from the foot of the 45-degree lead to the flank.
RELIEF_FLOOR_MID_X = (_sheet_x(SEAT_STATION + RELIEF_LEAD) + RELIEF_END_X) / 2.0

# Rows below the profile, 15 mm apart (text sits ~3 mm above its requested
# point and the dimension line ~5 mm below it).  Row 0 carries the thread size
# from the seat face on the left and the head length from the under-head face
# on the right; row 1 the shoulder length from the under-head face; row 2 the
# reference overall.  Row 0 stands 34 mm below the axis so the relief Ø can
# print between it and the profile.  No extension line crosses a dimension
# line.
_ROW_Y = (SIDE_CENTER[1] - 0.034, SIDE_CENTER[1] - 0.049, SIDE_CENTER[1] - 0.064)
SIDE_KEEP = {
    "ThreadLength": ((TIP_X + SEAT_X) / 2.0, _ROW_Y[0]),
    "HeadLength": ((UNDERHEAD_X + HEAD_FACE_X) / 2.0, _ROW_Y[0]),
    "ShoulderLength": ((UNDERHEAD_X + SEAT_X) / 2.0, _ROW_Y[1]),
    "OverallLength": ((TIP_X + HEAD_FACE_X) / 2.0, _ROW_Y[2]),
    # Diameters on the side view (rule 7).  The shoulder's dimension line
    # crosses the shoulder near its thread end; the head's stands clear of the
    # head face, left of the end view.
    "ShoulderDia": (SEAT_X + 0.050, SIDE_CENTER[1] + 0.030),
    "HeadDia": (HEAD_FACE_X + 0.014, SIDE_CENTER[1]),
    # The thread-relief groove against the seat face.  Its width from the seat
    # face reads above it, one row over the 45-degree lead's axial leg, whose
    # text stands right of the seat face over the shoulder; its Ø reads below
    # it, the dimension line standing on the floor so nothing crosses.
    "ReliefLead": (SEAT_X + 0.010, SIDE_CENTER[1] + 0.015),
    "ReliefWidth": (RELIEF_MID_X, SIDE_CENTER[1] + 0.026),
    "ReliefDia": (RELIEF_FLOOR_MID_X, SIDE_CENTER[1] - 0.016),
    # The tip chamfer's axial leg reads below-left of the tip, clear of the
    # thread size's extension line at the tip and of the callout above.
    "TipChamfer": (TIP_X - 0.020, SIDE_CENTER[1] - 0.016),
    # The slot shows as a notch in the head face; its depth reads above it.
    "SlotDepth": (HEAD_FACE_X - 0.0015, SIDE_CENTER[1] + 0.026),
}
END_KEEP = {
    "SlotWidth": (END_CENTER[0] + 0.022, END_CENTER[1]),
}
# The thread callout's leader lands on the edge where the full thread meets
# the tip chamfer, the full-thread portion's own end edge in the side view (the
# relief-flank edge at the other end would read as pointing at the groove).
THREAD_PICK = (THREAD_START_X, SIDE_CENTER[1] + 0.004)
THREAD_NOTE_XY = (0.030, SIDE_CENTER[1] + 0.040)
# The running shoulder's upper flank, right of the Ø dimension line.
FINISH_PICK = (UNDERHEAD_X - 0.060, SHOULDER_TOP_Y)
FINISH_SYMBOL = (UNDERHEAD_X - 0.050, SIDE_CENTER[1] + 0.030)
# A point on the shoulder face, clear of the Ø6.00 dimension line.
CENTERLINE_PICK = (UNDERHEAD_X - 0.100, SIDE_CENTER[1] + 0.003)
ISO_NOTE_XY = (0.352, 0.200)
# Bottom-left, above the title-block line, like the other crank sheets.
NOTES_XY = (0.016, 0.070)


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
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
            0: "Crank Handle Pivot Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle pivot; slotted shoulder screw; #10-24; steel",
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
        adapter, annotations, {"ReliefLead": CHAMFER_CALLOUT}, location="above"
    )
    set_dimension_callouts(
        adapter, annotations, {"TipChamfer": CHAMFER_CALLOUT}, location="below"
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-139 {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"MHA-139 {name}")

    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-139 head-end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-139 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-139 thread callout",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_shoulder"),
        label="MHA-139 pivot-shoulder finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
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
