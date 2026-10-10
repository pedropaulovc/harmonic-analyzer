r"""Create the MHA-SM-004 gooseneck spring screw manufacturing drawing.

The SLDPRT remains authoritative.  A screw carries no datum and no
geometric-control frame (policy rule 3): the relief diameter, relief lead and
tip chamfer keep their native bands, and every other size is an ordinary
model dimension at its part-authored places under the title block's .XX band.

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the crowned head
on the left and the thread tip on the right.  Axial sizes baseline from the
under-head face, the face that clamps the spring eye.  The head-end view is
the ``*Front`` orientation (looking down -Z onto the crown), which is exactly
the third-angle LEFT view of that profile, so it sits on the profile's axis
to its left and shows the slot.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck_spring_screw.py sm-gooseneck-spring-screw
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
    add_view_centerline,
    assert_imported_precision,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    offset_dimension_text,
    read_required_properties,
    set_hidden_lines_removed,
    set_dimension_callouts,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from sm_gooseneck_spring_screw_geom import (
    HEAD_CYL_H,
    HEAD_DIA,
    HEAD_H,
    LENGTH,
    MAJOR_DIA,
    RELIEF_DIA,
    RELIEF_LEAD,
    RELIEF_WIDTH,
    SLOT_FLOOR_Z,
    TIP_CHAMFER,
)
from sm_gooseneck_spring_screw_spec import (
    CHAMFER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
    RELIEF_CALLOUT,
    THREAD_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["sm_gooseneck_spring_screw"]
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
# 4:1 lays the 23.0 profile 92 mm long and the 1.6 slot 6.4 mm wide.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.215, 0.165)
# Third-angle left view of the crowned head end, on the profile's axis.
END_CENTER = (0.085, SIDE_CENTER[1])
ISO_CENTER = (0.360, 0.215)
ISO_SCALE = (2, 1)
# The view centre is the model bounding box's: apex z=HEAD_H to tip z=-LENGTH.
_BOX_MID_Z = (HEAD_H - LENGTH) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left)."""
    return SIDE_CENTER[0] + (_BOX_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the screw axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


APEX_X = _sheet_x(HEAD_H)
RIM_X = _sheet_x(HEAD_CYL_H)
SLOT_FLOOR_X = _sheet_x(SLOT_FLOOR_Z)
UNDERHEAD_X = _sheet_x(0.0)
RELIEF_END_X = _sheet_x(-RELIEF_WIDTH)
TIP_X = _sheet_x(-LENGTH)
# Where the full thread meets the tip chamfer.
THREAD_START_X = _sheet_x(-(LENGTH - TIP_CHAMFER))
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
THREAD_TOP_Y = _sheet_y(MAJOR_DIA / 2.0)
RELIEF_TOP_Y = _sheet_y(RELIEF_DIA / 2.0)
RELIEF_MID_X = (UNDERHEAD_X + RELIEF_END_X) / 2.0
# The relief floor runs from the foot of the 45-degree lead to the flank.
RELIEF_FLOOR_MID_X = (_sheet_x(-RELIEF_LEAD) + RELIEF_END_X) / 2.0

# Rows below the profile, 15 mm apart, the first 15 mm under the head
# (text sits ~3 mm above its requested point, the dimension line ~5 mm
# below it).  Row 0 chains the head height and the under-head length from
# the under-head face; row 1 carries the reference overall.
_ROW_Y = (HEAD_TOP_Y - 0.065, HEAD_TOP_Y - 0.080)
SIDE_KEEP = {
    "HeadHeight": ((APEX_X + UNDERHEAD_X) / 2.0, _ROW_Y[0]),
    "UnderHeadLength": ((UNDERHEAD_X + TIP_X) / 2.0, _ROW_Y[0]),
    "OverallLength": ((APEX_X + TIP_X) / 2.0, _ROW_Y[1]),
    # Diameters on the side view (rule 7): the head's stands clear of the
    # crown, between the profile and the head-end view.
    "HeadDia": (APEX_X - 0.019, SIDE_CENTER[1]),
    # The crown rise and the slot depth both read from the apex, stacked
    # above the head.
    "CrownRise": ((APEX_X + RIM_X) / 2.0, HEAD_TOP_Y + 0.012),
    "SlotDepth": ((APEX_X + SLOT_FLOOR_X) / 2.0, HEAD_TOP_Y + 0.024),
    # The die relief against the under-head face.  Its width reads above it,
    # clear of the head; its Ø below it with the 45-degree lead as its
    # callout, the dimension line standing on the floor.
    "ReliefWidth": (RELIEF_MID_X, HEAD_TOP_Y + 0.005),
    "ReliefDia": (RELIEF_FLOOR_MID_X, SIDE_CENTER[1] - 0.012),
    # The tip chamfer's axial leg reads below-right of the tip.
    "TipChamfer": (TIP_X + 0.012, SIDE_CENTER[1] - 0.016),
}
# The relief Ø's text goes on an OffsetText leader so the under-head
# extension line cannot run through the lead callout.  Width as measured on
# MHA-DT-032's render for the same callout form (farm run 69a2f961).
RELIEF_DIA_TEXT_WIDTH = 0.045
RELIEF_DIA_TEXT_UNDERLINE_DROP = 0.0056
RELIEF_DIA_TEXT_CLEARANCE = 0.0035
RELIEF_DIA_TEXT_XY = (
    UNDERHEAD_X + RELIEF_DIA_TEXT_CLEARANCE + RELIEF_DIA_TEXT_WIDTH / 2.0,
    SIDE_CENTER[1] - 0.019,
)
# The slot width reads right of the head-end view, left of the head Ø.
END_KEEP = {
    "SlotWidth": (
        END_CENTER[0] + HEAD_DIA * _S / 2000.0 + 0.010,
        END_CENTER[1] + 0.010,
    ),
}
# The thread callout's leader lands on the edge where the full thread meets
# the tip chamfer, never on the relief groove.  The note stands up and
# right so the leader slants down-left onto that edge.
THREAD_PICK = (THREAD_START_X, SIDE_CENTER[1] + 0.004)
THREAD_NOTE_XY = (THREAD_START_X + 0.013, SIDE_CENTER[1] + 0.035)
# A point on the thread's cylindrical face, clear of every dimension line.
CENTERLINE_PICK = ((RELIEF_END_X + THREAD_START_X) / 2.0, SIDE_CENTER[1] + 0.003)
ISO_NOTE_XY = (0.340, 0.180)
# Bottom-left, above the title-block line, like the other screw sheets.
NOTES_XY = (0.016, 0.070)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck-spring-screw source", await adapter.open_model(str(SOURCE)))
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
            0: "Gooseneck Spring Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"gooseneck spring clamp; slotted fillister screw; {THREAD_CALLOUT}; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
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
        adapter, annotations, {"TipChamfer": CHAMFER_CALLOUT}, location="below"
    )
    offset_dimension_text(adapter, side_annotations, {"ReliefDia": RELIEF_DIA_TEXT_XY})
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-SM-004 {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"MHA-SM-004 {name}")

    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-SM-004 head-end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-SM-004 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-SM-004 thread callout",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Spring Screw Manufacturing Drawing",
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
