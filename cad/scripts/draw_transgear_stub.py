r"""Create the MHA-082 transgear stud manufacturing drawing.

The SLDPRT remains authoritative.  A turned stud carries no datum and no
geometric-control frame (policy rule 3): the running journal keeps its native
fit band and one bearing-surface finish, the journal length its ±0.05 (the
cluster float), each thread relief its Ø MAX and width band, and every other
size is an ordinary model dimension at its part-authored places.

The stud axis is model +Z, so the ``*Right`` view lays it horizontal as it
sits in the lathe: model +Z runs to paper-LEFT, putting the #6-32 front end on
the left and the #10-32 rear end on the right.  Every feature is visible, so
the side view removes hidden lines.  The MHA-178 shim is faced to fit at
assembly (R9-65), so the stud is made to size: the rear stations (the step,
the seat, the rear thread's end) baseline from the Ø9 step face, the rear
relief's width from the seat, and the journal and front thread chain forward
from the step face.

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
    FRONT_THREAD_CALLOUT,
    FRONT_THREAD_END_STATION,
    FRONT_THREAD_MAJOR,
    JOURNAL_DIA,
    REAR_RELIEF_WIDTH,
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
REAR_RELIEF_END_X = _sheet_x(-REAR_RELIEF_WIDTH)
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
REAR_RELIEF_MID_X = (SEAT_X + REAR_RELIEF_END_X) / 2.0

# Axial rows below the profile, 15 mm apart, nested on the step face: row 0
# the step and the journal; row 1 the seat-to-step station and the front
# thread from the shoulder; row 2 the rear thread's end.  Each extension line
# lands on a junction of the rows above it, so none crosses a dimension line.
_ROW_Y = (SIDE_CENTER[1] - 0.034, SIDE_CENTER[1] - 0.049, SIDE_CENTER[1] - 0.064)
SIDE_KEEP = {
    "StepLength": ((COLLAR_FRONT_X + THRUST_X) / 2.0, _ROW_Y[0]),
    "JournalLength": ((THRUST_X + SHOULDER_X) / 2.0, _ROW_Y[0]),
    "ThrustStation": ((SEAT_X + THRUST_X) / 2.0, _ROW_Y[1]),
    "FrontThreadEnd": ((SHOULDER_X + FRONT_END_X) / 2.0, _ROW_Y[1]),
    "RearThreadEnd": ((REAR_END_X + SEAT_X) / 2.0, _ROW_Y[2]),
    # The collar Ø stands right of the rear tip, its extension lines clearing
    # the #10-32 silhouette; the step and journal Ø read above the profile on
    # their own sections.
    "CollarDia": (REAR_TIP_X + 0.026, SIDE_CENTER[1]),
    "StepDia": ((COLLAR_FRONT_X + THRUST_X) / 2.0, COLLAR_TOP_Y + 0.012),
    "JournalDia": (THRUST_X - 0.020, COLLAR_TOP_Y + 0.004),
    # Each relief: width above, Ø below with its text offset clear of the
    # neighbouring station's extension line.  The rear width's text stands
    # over the thread, above the collar Ø's upper extension line and left of
    # the rear thread callout's leader.
    "ReliefWidth": (RELIEF_MID_X, COLLAR_TOP_Y + 0.004),
    "ReliefDia": (RELIEF_MID_X, SIDE_CENTER[1] - 0.012),
    "RearReliefWidth": (REAR_RELIEF_END_X + 0.008, COLLAR_TOP_Y + 0.008),
    "RearReliefDia": (REAR_RELIEF_MID_X, SIDE_CENTER[1] - 0.012),
    "FrontDomeR": (TIP_X - 0.012, SIDE_CENTER[1] - 0.016),
    # Under row 0's extension ends, 12 mm right of the rear tip.  Its shoulder
    # runs from 7.5 mm left to 5.9 mm right of this point, 2.8 mm under it
    # (runs 20261001T051043622Z and 19e33c6c2), and the rear thread's end
    # line at REAR_END_X runs down to row 2, so the shoulder starts 7.5 mm
    # right of that line (19e33c6c2: 4 mm right of the tip, it crossed it).
    "RearDomeR": (REAR_TIP_X + 0.012, _ROW_Y[0] - 0.008),
}
RELIEF_DIA_TEXT_XY = ((RELIEF_END_X + FRONT_END_X) / 2.0, SIDE_CENTER[1] - 0.020)
REAR_RELIEF_DIA_TEXT_XY = (
    (REAR_RELIEF_END_X + REAR_END_X) / 2.0,
    SIDE_CENTER[1] - 0.020,
)
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
    set_hidden_lines_removed(adapter, side)
    set_hidden_lines_removed(adapter, iso)

    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    offset_dimension_text(
        adapter,
        annotations,
        {"ReliefDia": RELIEF_DIA_TEXT_XY, "RearReliefDia": REAR_RELIEF_DIA_TEXT_XY},
    )
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
        entity_type="SILHOUETTE",
    )
    add_attached_note(
        adapter,
        side,
        text=REAR_THREAD_CALLOUT,
        entity_xy=REAR_THREAD_PICK,
        note_xy=REAR_THREAD_NOTE_XY,
        label="MHA-082 rear thread callout",
        entity_type="SILHOUETTE",
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
