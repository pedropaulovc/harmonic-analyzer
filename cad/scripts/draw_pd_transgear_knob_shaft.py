r"""Create the manufacturing drawing for the transgear knob shaft (MHA-PD-008).

A turned side view, aligned rear and front end views, and an isometric.
The side view imports the source-owned turned sizes, D-flat and unchanged
stations. The front end view carries genuine finite-root REF and driven
parallel-tangent span inspection dimensions; the rear view identifies the
actual running journal datum. The #8-32 thread callout belongs to its real
thread blank. Cutter identity, root acceptance and approved inspection
controls are properties of the saved source, never values retyped here.
The source-linked formed-flank callout carries radial TIR, the paid
pitch-index range at REF pitch diameter, all-space/wrap receiving and the
certified pin. Neither span thickness nor a pin-centre radius substitutes
for that independent index control.
The rear cup remains match-pinned at assembly; the front D-core has no
crosshole. This script does not certify a native build or release a prototype
toothspace runout grade.
"""

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
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _part_pmi import _resolve_faces
from _surface_finish import surface_finish_by_key
from paper_drive_stock_drawing import add_toothspace_callout, require_source_control
from pd_transgear_knob_shaft_spec import (
    CHAMFER_CALLOUT,
    CORE_DIA,
    CORE_FRONT_Z,
    CORE_REAR_Z,
    FRONT_RELIEF_DIA,
    FRONT_RELIEF_WIDTH,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    JOURNAL_DIA,
    OUTSIDE_DIA,
    PLAIN_CORE,
    PRESSURE_ANGLE_DEG,
    GEOMETRIC_CONTROLS,
    GEOMETRIC_TOLERANCES_MM,
    PART_DATUMS,
    REAR_END_Z,
    SURFACE_FINISHES,
    STOCK_PROFILE,
    TOOTH_SPACE_GAUGE_PIN_DIA_MM,
    TOOTH_SPACE_CALLOUT,
    TOOTH_SPACE_CALLOUT_PROPERTY,
    TEETH,
    THREAD_CALLOUT,
    TIP_CHAMFER,
    TIP_STATION,
    TIP_Z,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["pd_transgear_knob_shaft"]
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

# The retained shaft stations fit at 3:1. Inspection carriers use a separate
# aligned front end view, not the journal-obscured rear projection.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.180, 0.160)
# Third-angle: the rear face is the side view's LEFT end, so the view from
# the rear stands left of it, on the shaft axis.
END_CENTER = (0.045, SIDE_CENTER[1])
FRONT_CENTER = (0.335, SIDE_CENTER[1])
ISO_CENTER = (0.365, 0.215)
ISO_SCALE = (1, 1)
_BBOX_MID_Z = (TIP_Z + REAR_END_Z) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left).

    The view is centred on the model bbox, stud tip to rear face.
    """
    return SIDE_CENTER[0] + (_BBOX_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the shaft axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


REAR_X = _sheet_x(REAR_END_Z)
PINION_REAR_X = _sheet_x(FACE_WIDTH)
F_X = _sheet_x(0.0)
CORE_END_X = _sheet_x(CORE_FRONT_Z)
THREAD_END_X = _sheet_x(-PLAIN_CORE)
TIP_X = _sheet_x(TIP_Z)
# Where the thread blank meets the tip chamfer.
CHAMFER_START_X = _sheet_x(-(TIP_STATION - TIP_CHAMFER))
HALF_OD = OUTSIDE_DIA * _S / 2000.0

# Turned sizes stay beside their own axial regions. Baseline lengths nest
# below F, with the cutter limits on separate rows. The D-flat's native
# plane-to-axis dimension is visible edge-on in the side view.
_ABOVE_Y = SIDE_CENTER[1] + HALF_OD + 0.016
_ROW_PITCH = 0.010
_ROW_Y = tuple(SIDE_CENTER[1] - HALF_OD - 0.016 - i * _ROW_PITCH for i in range(6))
# The prefixed texts' centre right of F: half the wider text's printed width
# (test_transgear_knob_shaft_drawing) and an arrow's air.
_CUTTER_TEXT_INSET = 0.040
SIDE_KEEP: dict[str, tuple[float, float]] = {
    "OutsideDia": ((F_X + PINION_REAR_X) / 2.0, _ABOVE_Y),
    "CoreDia": ((F_X + CORE_END_X) / 2.0, _ABOVE_Y + 0.010),
    # Run 12: from the relief's mid the hung text's shoulder started left of
    # F's witness line (214.4) and ran through the front-neck frame. Four
    # fifths along the relief it starts right of F, above that frame.
    "ReliefDia": ((CORE_END_X + 4.0 * THREAD_END_X) / 5.0, _ABOVE_Y + 0.0265),
    # A Ø's line stands at its point; right of the view's centre the text
    # hangs LEFT of it (the 12T's and core's, run 20261001T085006647Z), and
    # the blank's banded text and shoulder run 27.5 mm (19e33c6c2: from the
    # blank's mid the shoulder crossed the relief's line).  9 mm in from the
    # chamfer the line stands clear of the core runout frame below the text
    # and stays 9 mm off the thread callout's leader to the chamfer.
    "ThreadBlankDia": (CHAMFER_START_X - 0.009, _ABOVE_Y),
    "JournalDia": ((PINION_REAR_X + REAR_X) / 2.0, _ABOVE_Y),
    "FaceWidth": ((F_X + PINION_REAR_X) / 2.0, _ROW_Y[4]),
    "CoreFront": ((F_X + CORE_END_X) / 2.0, _ROW_Y[0]),
    "FrontReliefDia": (F_X + 0.031, _ABOVE_Y + 0.047),
    "FrontReliefWidth": (F_X + 0.043, _ABOVE_Y + 0.034),
    "FrontCornerRadius": (F_X + 0.035, _ABOVE_Y + 0.060),
    "FlatToolRadius": (F_X + 0.079, _ABOVE_Y + 0.047),
    "FlatEnd": (F_X + 0.082, _ROW_Y[0]),
    "PlainCore": ((F_X + THREAD_END_X) / 2.0, _ROW_Y[1]),
    "JournalLength": ((PINION_REAR_X + REAR_X) / 2.0, _ROW_Y[0]),
    "TipStation": ((F_X + TIP_X) / 2.0, _ROW_Y[2]),
    "FullDepth": (F_X + _CUTTER_TEXT_INSET, _ROW_Y[3]),
    "CutterRunout": (F_X + _CUTTER_TEXT_INSET, _ROW_Y[5]),
    "FlatToAxis": (CORE_END_X + 0.018, SIDE_CENTER[1] - HALF_OD - 0.004),
    "TipChamfer": (TIP_X + 0.012, SIDE_CENTER[1] - HALF_OD),
}
END_KEEP: dict[str, tuple[float, float]] = {
    # Right of the side view's TipStation witness line (x TIP_X) at its row.
    "RootEnvelope": (FRONT_CENTER[0] - 0.019, FRONT_CENTER[1] - HALF_OD - 0.021),
    "ToothSpan": (FRONT_CENTER[0] + 0.029, FRONT_CENTER[1] + HALF_OD + 0.021),
}
DIMENSION_CALLOUTS_BELOW = {"TipChamfer": CHAMFER_CALLOUT}

# The thread callout lands on the edge where the thread blank meets the tip
# chamfer and stands up and left, clear of the tooth-tip Ø over the 12T.
THREAD_PICK = (CHAMFER_START_X, SIDE_CENTER[1] + 0.002)
THREAD_NOTE_XY = ((THREAD_END_X + CHAMFER_START_X) / 2.0, _ABOVE_Y + 0.020)
# The actual active core (not the new neck) and running journal own finishes.
JOURNAL_FINISH_SYMBOL = (END_CENTER[0] + 0.008, END_CENTER[1] + HALF_OD + 0.012)
_JOURNAL_R = JOURNAL_DIA * _S / 2000.0
JOURNAL_FINISH_ATTACH = (
    END_CENTER[0] + _JOURNAL_R * 0.5,
    END_CENTER[1] + _JOURNAL_R * 3.0**0.5 / 2.0,
)
CORE_FINISH_PICK = (
    _sheet_x((CORE_FRONT_Z + CORE_REAR_Z) / 2.0), _sheet_y(CORE_DIA / 2.0)
)
# Right of the front-neck frame's leader, which climbs past the core's left.
CORE_FINISH_SYMBOL = (F_X + 0.0115, SIDE_CENTER[1] + HALF_OD + 0.004)
# A point on the journal's face for the turning axis.
CENTERLINE_PICK = ((PINION_REAR_X + REAR_X) / 2.0, SIDE_CENTER[1] + 0.003)
GEAR_DATA_XY = (0.016, 0.262)
# Source-linked tooling data occupies its own upper-left lane.
GEAR_DATA_CHAR_HEIGHT = 0.0025
NOTES_XY = (0.016, 0.070)
ROOT_ACCEPTANCE_XY = (0.286, 0.103)
DATUM_A_SYMBOL = (END_CENTER[0] - 0.017, END_CENTER[1] - 0.018)
# The core frame sits low over the thread blank, under the blank's Ø text;
# its leader runs under the core finish symbol to the core's front quarter
# (run 12: from above it crossed the blank's Ø and thread callout texts).
CORE_RUNOUT_LANDING = (
    _sheet_x(CORE_REAR_Z + 0.75 * (CORE_FRONT_Z - CORE_REAR_Z)),
    _sheet_y(CORE_DIA / 2.0),
)
CORE_RUNOUT_FRAME = (THREAD_END_X + 0.0066, SIDE_CENTER[1] + 0.0155)
# Each frame's leader landing on its surface's upper outline, and the frame.
# The neck's straight floor is 0.3 mm long between its two 0.05 corner tori
# (0.9 mm of sheet), so a silhouette hit-test there landed on a neighbour
# (run 10: a type-46 silhouette of another face). Like main's arbor
# finishes, each frame attaches to the model FACE its spec control names,
# resolved on the referenced part, at this landing.
CONTROL_ATTACHMENTS = {
    "core_total_runout": (CORE_RUNOUT_LANDING, CORE_RUNOUT_FRAME),
    "front_neck_total_runout": (
        (_sheet_x(-FRONT_RELIEF_WIDTH / 2.0), _sheet_y(FRONT_RELIEF_DIA / 2.0)),
        # Left of the neck, so the leader's shoulder ends right of it and the
        # leg climbs steeply, left of the core finish symbol's leader.
        (F_X - 0.026, SIDE_CENTER[1] + HALF_OD + 0.038),
    ),
}
# Right of FlatToolRadius's text: the leader drops nearly straight to the gap.
TOOTHSPACE_NOTE_XY = (0.322, 0.258)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-knob-shaft source", await adapter.open_model(str(SOURCE)))
    source_properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Root Acceptance",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
            "Root Acceptance",
            TOOTH_SPACE_CALLOUT_PROPERTY,
        ),
    )
    require_source_control(
        source_properties[TOOTH_SPACE_CALLOUT_PROPERTY], TOOTH_SPACE_CALLOUT,
        label="knob shaft toothspace grade",
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Knob Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: (
                f"transgear knob shaft; steel; {TEETH}T {DIAMETRAL_PITCH:g}DP "
                f"PA{PRESSURE_ANGLE_DEG:g}; finite stock #8; #8-32 stud; D-core"
            ),
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, front, iso):
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
        front,
        keep=END_KEEP,
        view_label="front finite-form inspection",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *end_annotations]
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    add_view_centerline(
        adapter, side, face_xy=CENTERLINE_PICK, label="MHA-PD-008 turning axis"
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-PD-008 stud thread callout",
    )

    # The two running surfaces, authored on the part and read back (rule 5).
    add_surface_finish(
        adapter,
        end,
        symbol_xy=JOURNAL_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "journal"),
        label="journal finish",
        entity=visible_circle_edge(adapter, end, JOURNAL_DIA),
        leader_attach_xy=JOURNAL_FINISH_ATTACH,
        char_height=0.0025,
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=CORE_FINISH_PICK,
        symbol_xy=CORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "core"),
        label="core finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    # The saved source owns datum/control semantics. The drawing attaches
    # those same source declarations to the actual journal/core entities.
    journal_datum = PART_DATUMS[0]
    add_datum_feature(
        adapter,
        end,
        entity=visible_circle_edge(adapter, end, JOURNAL_DIA),
        symbol_xy=DATUM_A_SYMBOL,
        datum=journal_datum.letter,
        label="knob running journal datum",
    )
    controls = {control.key: control for control in GEOMETRIC_CONTROLS}
    if set(controls) != set(GEOMETRIC_TOLERANCES_MM):
        raise RuntimeError("knob shaft frames do not cover the spec's geometric controls")
    control_faces = _resolve_faces(
        _early_bound(_early_bound(side, "IView").ReferencedDocument, "IModelDoc2"),
        {key: control.face for key, control in controls.items()},
    )
    for (key,) in (("core_total_runout",), ("front_neck_total_runout",)):
        control = controls[key]
        landing, frame_xy = CONTROL_ATTACHMENTS[key]
        add_feature_control_frame(
            adapter,
            side,
            entity=control_faces[key],
            leader_attach_xy=landing,
            frame_xy=frame_xy,
            characteristic=control.characteristic,
            tolerance=GEOMETRIC_TOLERANCES_MM[key],
            datums=control.datums,
            diameter=control.tolerance_zone == "diametral",
            entity_type="FACE",
            label=control.key,
        )
    add_toothspace_callout(
        adapter, front, profile=STOCK_PROFILE,
        actual_pin_diameter_mm=TOOTH_SPACE_GAUGE_PIN_DIA_MM,
        rotate_rad=math.pi / TEETH, axial_station_mm=0.0,
        property_name=TOOTH_SPACE_CALLOUT_PROPERTY,
        note_xy=TOOTHSPACE_NOTE_XY,
    )
    add_property_linked_note(
        adapter, "Gear Data", *GEAR_DATA_XY, char_height=GEAR_DATA_CHAR_HEIGHT
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.0025
    )
    add_property_linked_note(
        adapter, "Root Acceptance", *ROOT_ACCEPTANCE_XY, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Knob Shaft Manufacturing Drawing",
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
