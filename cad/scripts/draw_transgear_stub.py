r"""Create the MHA-082 transgear stud manufacturing drawing.

The SLDPRT remains authoritative.  A turned stud carries no datum and no
geometric-control frame (policy rule 3): the running journal keeps its native
fit band and one bearing-surface finish, the journal length its ±0.05 (the
cluster float), the thread relief its Ø MAX and width band, and every other
size is an ordinary model dimension at its part-authored places.

The stud axis is model +Z, so the ``*Right`` view lays it horizontal as it
sits in the lathe: model +Z runs to paper-LEFT, putting the #6-32 front end on
the left and the #10-32 rear end on the right.  The side view shows hidden
lines for the one hidden feature, the Ø5.40 face relief in the collar's rear
face.  Axial stations baseline from the collar's rear face (the arm seat) and
chain forward from the Ø9 step face.

Run with SolidWorks open::

    uv run python cad\scripts\draw_transgear_stub.py transgear-stub
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
    offset_dimension_text,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from transgear_stub_spec import (
    CAP_SHOULDER_STATION,
    COLLAR_DIA,
    COLLAR_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_RELIEF_DEPTH,
    FRONT_THREAD_CALLOUT,
    FRONT_THREAD_END_STATION,
    FRONT_THREAD_MAJOR,
    JOURNAL_DIA,
    REAR_THREAD_CALLOUT,
    REAR_THREAD_LENGTH,
    REAR_THREAD_MAJOR,
    REAR_TIP_STATION,
    RELIEF_END_STATION,
    SLEEVE_THRUST_STATION,
    SURFACE_FINISHES,
    TIP_STATION,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["transgear_stub"]
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

# The side view prints at the sheet scale, so it needs no caption.  3:1 lays
# the 50.7 stud 152 mm long and the 1.1 thread relief 3.3 mm wide.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.160, 0.165)
ISO_CENTER = (0.350, 0.230)
ISO_SCALE = (2, 1)
_MID_Z = (REAR_TIP_STATION + TIP_STATION) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left)."""
    return SIDE_CENTER[0] + (_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the stud axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


REAR_END_X = _sheet_x(-REAR_THREAD_LENGTH)
SEAT_X = _sheet_x(0.0)
COLLAR_FRONT_X = _sheet_x(COLLAR_LENGTH)
THRUST_X = _sheet_x(SLEEVE_THRUST_STATION)
SHOULDER_X = _sheet_x(CAP_SHOULDER_STATION)
RELIEF_END_X = _sheet_x(RELIEF_END_STATION)
FRONT_END_X = _sheet_x(FRONT_THREAD_END_STATION)
TIP_X = _sheet_x(TIP_STATION)
REAR_TIP_X = _sheet_x(REAR_TIP_STATION)
COLLAR_TOP_Y = _sheet_y(COLLAR_DIA / 2.0)
JOURNAL_TOP_Y = _sheet_y(JOURNAL_DIA / 2.0)
RELIEF_MID_X = (SHOULDER_X + RELIEF_END_X) / 2.0

# Axial rows below the profile, 15 mm apart: row 0 chains the rear thread
# and the collar from the seat face and the journal from the step face; row 1
# the step station from the seat face and the front thread from the shoulder.
# Each row-1 extension line lands on a row-0 junction, so none crosses a
# dimension line.
_ROW_Y = (SIDE_CENTER[1] - 0.034, SIDE_CENTER[1] - 0.049)
SIDE_KEEP = {
    "RearThreadLength": ((REAR_END_X + SEAT_X) / 2.0, _ROW_Y[0]),
    "CollarLength": ((SEAT_X + COLLAR_FRONT_X) / 2.0, _ROW_Y[0]),
    "JournalLength": ((THRUST_X + SHOULDER_X) / 2.0, _ROW_Y[0]),
    "ThrustStation": ((SEAT_X + THRUST_X) / 2.0, _ROW_Y[1]),
    "FrontThreadEnd": ((SHOULDER_X + FRONT_END_X) / 2.0, _ROW_Y[1]),
    # The face relief (hidden) and the collar Ø stand right of the rear tip,
    # their extension lines clearing the #10-32 silhouette.
    "FaceReliefDia": (REAR_TIP_X + 0.012, SIDE_CENTER[1]),
    "CollarDia": (REAR_TIP_X + 0.026, SIDE_CENTER[1]),
    "FaceReliefDepth": (
        SEAT_X - FACE_RELIEF_DEPTH * _S / 2000.0,
        COLLAR_TOP_Y + 0.012,
    ),
    # The step and journal Ø read above the profile on their own sections.
    "StepDia": ((COLLAR_FRONT_X + THRUST_X) / 2.0, COLLAR_TOP_Y + 0.012),
    "JournalDia": (THRUST_X - 0.020, COLLAR_TOP_Y + 0.004),
    # The relief: width above, Ø below with its text offset clear of the
    # journal length's extension line at the shoulder.
    "ReliefWidth": (RELIEF_MID_X, COLLAR_TOP_Y + 0.004),
    "ReliefDia": (RELIEF_MID_X, SIDE_CENTER[1] - 0.012),
    "FrontDomeR": (TIP_X - 0.012, SIDE_CENTER[1] - 0.016),
    "RearDomeR": (REAR_TIP_X + 0.004, SIDE_CENTER[1] - 0.030),
}
RELIEF_DIA_TEXT_XY = ((RELIEF_END_X + FRONT_END_X) / 2.0, SIDE_CENTER[1] - 0.020)
# Each thread callout lands on its own full-thread silhouette and stands out
# past the rows, the front one up-left, the rear one up-right.
FRONT_THREAD_PICK = (
    (RELIEF_END_X + FRONT_END_X) / 2.0,
    _sheet_y(FRONT_THREAD_MAJOR / 2.0),
)
FRONT_THREAD_NOTE_XY = (TIP_X - 0.030, COLLAR_TOP_Y + 0.020)
REAR_THREAD_PICK = (
    (REAR_END_X + SEAT_X) / 2.0 + 0.004,
    _sheet_y(REAR_THREAD_MAJOR / 2.0),
)
REAR_THREAD_NOTE_XY = (REAR_TIP_X + 0.010, COLLAR_TOP_Y + 0.024)
# The journal's upper silhouette, left of its Ø dimension line.
FINISH_PICK = ((THRUST_X + SHOULDER_X) / 2.0 - 0.010, JOURNAL_TOP_Y)
FINISH_SYMBOL = ((THRUST_X + SHOULDER_X) / 2.0 - 0.010, COLLAR_TOP_Y + 0.008)
# A point on the journal face, clear of the Ø dimension line.
CENTERLINE_PICK = ((THRUST_X + SHOULDER_X) / 2.0 + 0.010, SIDE_CENTER[1] + 0.001)
ISO_NOTE_XY = (0.320, 0.185)
NOTES_XY = (0.016, 0.070)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-stub source", await adapter.open_model(str(SOURCE)))
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
            0: "Transgear Stud Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear stud; turned steel; #10-32 and #6-32",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_visible(adapter, side)
    set_hidden_lines_removed(adapter, iso)

    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    offset_dimension_text(adapter, annotations, {"ReliefDia": RELIEF_DIA_TEXT_XY})
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-082 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=FRONT_THREAD_CALLOUT,
        entity_xy=FRONT_THREAD_PICK,
        note_xy=FRONT_THREAD_NOTE_XY,
        label="MHA-082 front thread callout",
    )
    add_attached_note(
        adapter,
        side,
        text=REAR_THREAD_CALLOUT,
        entity_xy=REAR_THREAD_PICK,
        note_xy=REAR_THREAD_NOTE_XY,
        label="MHA-082 rear thread callout",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "journal"),
        label="MHA-082 journal finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Stud Manufacturing Drawing",
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
