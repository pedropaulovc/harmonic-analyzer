r"""Create the drawing for the rocker arm's pivot shoulder screw (MHA-CH-006-TL-06).

No datum and no geometric-control frame (fixture policy): the two lapped
locating diameters keep their native bands, the shoulder its Ra 0.8 finish,
and the coaxiality requirement is a no-digit note. The ``*Right`` view lays
the axis horizontal with model +Z (the head) to paper-left; every axial size
reads from the faced head top. The head-end view (``*Front``, third-angle
left view) sits on the profile's axis to its left and shows the slot.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_pivot_screw.py ch-rocker-arm-tl-pivot-screw
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
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_reference_dimensions,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from ch_rocker_arm_tl_pivot_screw_spec import (
    HEAD_FIT_CALLOUT,
    SHOULDER_FIT_CALLOUT,
    CHAMFER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HEAD_DIA,
    HEAD_TOP_Z,
    SHOULDER_DIA,
    SHOULDER_END_Z,
    SURFACE_FINISHES,
    THREAD_CALLOUT,
    THREAD_MODEL_DIA,
    TIP_Z,
    UNDERHEAD_Z,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_pivot_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# 4:1 lays the 32.7 screw 131 mm long and the 1.0 slot 4 mm wide.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.215, 0.165)
END_CENTER = (0.085, SIDE_CENTER[1])
ISO_CENTER = (0.355, 0.215)
ISO_SCALE = (2, 1)
ISO_NOTE_XY = (0.325, 0.255)
NOTES_XY = (0.020, 0.070)
_Z_MID = (HEAD_TOP_Z + TIP_Z) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left)."""
    return SIDE_CENTER[0] - (model_z_mm - _Z_MID) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the screw axis."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


HEAD_TOP_X = _sheet_x(HEAD_TOP_Z)
UNDERHEAD_X = _sheet_x(UNDERHEAD_Z)
SHOULDER_END_X = _sheet_x(SHOULDER_END_Z)
TIP_X = _sheet_x(TIP_Z)
# Rows below the profile, 15 mm apart: the head length from the head top,
# the stack lengths from the underhead.
_ROW_Y = (SIDE_CENTER[1] - 0.032, SIDE_CENTER[1] - 0.047, SIDE_CENTER[1] - 0.062)
SIDE_KEEP = {
    "HeadLength": ((HEAD_TOP_X + UNDERHEAD_X) / 2.0, _ROW_Y[0]),
    "ShoulderLength": ((UNDERHEAD_X + SHOULDER_END_X) / 2.0, _ROW_Y[1]),
    "UnderHeadLength": ((UNDERHEAD_X + TIP_X) / 2.0, _ROW_Y[2]),
    # Diameters on the profile beside their steps.
    "HeadDia": ((HEAD_TOP_X + UNDERHEAD_X) / 2.0, _sheet_y(HEAD_DIA / 2.0) + 0.042),
    # Its six-line fit callout reads below its text, right of the head's.
    "ShoulderDia": (UNDERHEAD_X + 0.077, _sheet_y(SHOULDER_DIA / 2.0) + 0.037),
    "TipChamfer": (TIP_X + 0.010, SIDE_CENTER[1] - 0.018),
    # The slot shows as a notch in the head top; its depth reads beside it.
    "SlotDepth": (HEAD_TOP_X - 0.012, SIDE_CENTER[1] + 0.024),
}
END_KEEP = {
    "SlotWidth": (END_CENTER[0] + 0.026, END_CENTER[1] + 0.024),
}
THREAD_PICK = ((SHOULDER_END_X + TIP_X) / 2.0, _sheet_y(THREAD_MODEL_DIA / 2.0))
THREAD_NOTE_XY = (TIP_X + 0.012, SIDE_CENTER[1] + 0.034)
# Below the journal: the fit callout fills the space above it.
FINISH_PICK = (SHOULDER_END_X - 0.030, _sheet_y(-SHOULDER_DIA / 2.0))
FINISH_SYMBOL = (SHOULDER_END_X - 0.045, _sheet_y(-SHOULDER_DIA / 2.0) - 0.014)
HEAD_FINISH_PICK = ((HEAD_TOP_X + UNDERHEAD_X) / 2.0, _sheet_y(-HEAD_DIA / 2.0))
HEAD_FINISH_SYMBOL = ((HEAD_TOP_X + UNDERHEAD_X) / 2.0, _sheet_y(-HEAD_DIA / 2.0) - 0.014)
CENTERLINE_PICK = (SHOULDER_END_X - 0.050, SIDE_CENTER[1] + 0.003)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-screw source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Pivot Screw Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm S4 pivot shoulder screw; lapped 4140; MHA-CH-006-TL-06",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            side,
            keep=SIDE_KEEP,
            view_label="side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            end,
            keep=END_KEEP,
            view_label="head-end",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # The tip chamfer is defined by its callout (to the thread root): its size
    # is reference.
    set_reference_dimensions(adapter, annotations, ("ShoulderDia", "HeadDia", "TipChamfer"))
    set_dimension_callouts(
        adapter,
        annotations,
        # The below lane: a leadered diameter renders no above-text
        # (run 20261007T193228511Z printed neither fit callout).
        {
            "ShoulderDia": SHOULDER_FIT_CALLOUT,
            "HeadDia": HEAD_FIT_CALLOUT,
            "TipChamfer": CHAMFER_CALLOUT,
        },
        location="below",
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add the center mark to the pivot-screw head-end view")
    add_view_centerline(adapter, side, face_xy=CENTERLINE_PICK, label="pivot-screw turning axis")
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="pivot-screw thread callout",
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_shoulder"),
        label="pivot-screw shoulder finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=HEAD_FINISH_PICK,
        symbol_xy=HEAD_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_head"),
        label="pivot-screw head finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Pivot Screw Drawing",
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
