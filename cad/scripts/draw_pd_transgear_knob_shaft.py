r"""Create the manufacturing drawing for the transgear knob shaft (MHA-PD-008).

A side view, the rear end view and an isometric.  The side view (``*Right``,
model +Z running left) carries every turned size beside its axial extent
(rule 7): the tooth-tip, core, relief, thread-blank and journal diameters
above the shaft, and the lengths below it baselined from F, the 12T's front
face (the stud stations) and from the 12T's rear face (the journal).  The
1/4-20 thread is a callout on the Ø6.22 blank; its full-thread end is the
PlainCore station, on the thread relief's front shoulder, and the core ends
at the CoreLength station.  The form cutter's full-depth station and run-out
limit print as native lengths from F; the notes give the largest cutter.  The
rear end view (``*Front``, looking at the rear face) carries the journal's
running finish.  The journal's rear extension carries the MHA-PD-016 cup, pinned
through a hole drilled at assembly (R9-70 K-1), so it carries no feature on
this sheet.  All dimensions import natively from the part with the places
and bands ``transgear_knob_shaft_spec`` authored.
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
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _surface_finish import surface_finish_by_key
from pd_transgear_knob_shaft_spec import (
    CHAMFER_CALLOUT,
    CORE_DIA,
    CORE_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FACE_WIDTH,
    JOURNAL_DIA,
    OUTSIDE_DIA,
    PLAIN_CORE,
    REAR_END_Z,
    SURFACE_FINISHES,
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

# 3:1 lays the 70.74 shaft 212 mm long (sheet x 0.074 .. 0.286, clear of the
# end view's 0.059 and the isometric) and the 12T's Ø9.36 tips 28 mm tall.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.180, 0.160)
# Third-angle: the rear face is the side view's LEFT end, so the view from
# the rear stands left of it, on the shaft axis.
END_CENTER = (0.045, SIDE_CENTER[1])
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
CORE_END_X = _sheet_x(-CORE_LENGTH)
THREAD_END_X = _sheet_x(-PLAIN_CORE)
TIP_X = _sheet_x(TIP_Z)
# Where the thread blank meets the tip chamfer.
CHAMFER_START_X = _sheet_x(-(TIP_STATION - TIP_CHAMFER))
HALF_OD = OUTSIDE_DIA * _S / 2000.0

# Diameters stand above the shaft over their own spans; the lengths stack
# below it, 10 mm apart, each side of F shortest innermost so no extension
# line crosses an inner row's text.  Right of F: row 0 the core length, row 1
# the full-thread end, row 2 the stud tip.  Left of F: row 0 the journal
# length from the 12T's rear face; rows 3..5 the cutter's full-depth station
# (R9-21), the face width and the run-out limit.  The two cutter stations
# carry their names as model prefixes, too wide for their spans, so their
# text stands right of F, below the stud's rows; the run-out's extension line
# crosses the journal length's dimension line, the one crossing two datums
# (F and the 12T's rear face) leave.  The tip chamfer's leg reads under the
# tip with its 45-degree callout.  Right of the view's centre a Ø's text hangs
# LEFT of its line, so the core's banded text (181..211 at 8b5e1f354) ran
# over the 12T's Ø9.36 (181.5..194.5): the core reads one step up, and the
# narrow relief's Ø, whose text the core's line would otherwise cross, two
# and a half steps up.
_ABOVE_Y = SIDE_CENTER[1] + HALF_OD + 0.016
_ROW_PITCH = 0.010
_ROW_Y = tuple(SIDE_CENTER[1] - HALF_OD - 0.016 - i * _ROW_PITCH for i in range(6))
# The prefixed texts' centre right of F: half the wider text's printed width
# (test_transgear_knob_shaft_drawing) and an arrow's air.
_CUTTER_TEXT_INSET = 0.040
SIDE_KEEP: dict[str, tuple[float, float]] = {
    "OutsideDia": ((F_X + PINION_REAR_X) / 2.0, _ABOVE_Y),
    "CoreDia": ((F_X + CORE_END_X) / 2.0, _ABOVE_Y + 0.010),
    "ReliefDia": ((CORE_END_X + THREAD_END_X) / 2.0, _ABOVE_Y + 0.024),
    # A Ø's line stands at its point; right of the view's centre the text
    # hangs LEFT of it (the 12T's and core's, run 20261001T085006647Z), and
    # the blank's banded text and shoulder run 27.5 mm (19e33c6c2: from the
    # blank's mid the shoulder crossed the relief's line).  12.5 mm in from
    # the chamfer the shoulder starts 10.7 mm right of the relief's line and
    # the line stays 12.5 mm off the thread callout's leader to the chamfer.
    "ThreadBlankDia": (CHAMFER_START_X - 0.0125, _ABOVE_Y),
    "JournalDia": ((PINION_REAR_X + REAR_X) / 2.0, _ABOVE_Y),
    "FaceWidth": ((F_X + PINION_REAR_X) / 2.0, _ROW_Y[4]),
    "CoreLength": ((F_X + CORE_END_X) / 2.0, _ROW_Y[0]),
    "PlainCore": ((F_X + THREAD_END_X) / 2.0, _ROW_Y[1]),
    "JournalLength": ((PINION_REAR_X + REAR_X) / 2.0, _ROW_Y[0]),
    "TipStation": ((F_X + TIP_X) / 2.0, _ROW_Y[2]),
    "FullDepth": (F_X + _CUTTER_TEXT_INSET, _ROW_Y[3]),
    "CutterRunout": (F_X + _CUTTER_TEXT_INSET, _ROW_Y[5]),
    "TipChamfer": (TIP_X + 0.012, SIDE_CENTER[1] - HALF_OD),
}
END_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS_BELOW = {"TipChamfer": CHAMFER_CALLOUT}

# The thread callout lands on the edge where the thread blank meets the tip
# chamfer and stands up and left, clear of the tooth-tip Ø over the 12T.
THREAD_PICK = (CHAMFER_START_X, SIDE_CENTER[1] + 0.002)
THREAD_NOTE_XY = ((THREAD_END_X + CHAMFER_START_X) / 2.0, _ABOVE_Y + 0.020)
# Finishes: the journal on its rear-face circle in the end view, the core on
# its upper silhouette just in front of F.  The journal's leader lands on the
# circle at 60 degrees, under its symbol: left to SolidWorks it landed at the
# circle's bottom and crossed the whole view (234a39c87).
JOURNAL_FINISH_SYMBOL = (END_CENTER[0] + 0.008, END_CENTER[1] + HALF_OD + 0.012)
_JOURNAL_R = JOURNAL_DIA * _S / 2000.0
JOURNAL_FINISH_ATTACH = (
    END_CENTER[0] + _JOURNAL_R * 0.5,
    END_CENTER[1] + _JOURNAL_R * 3.0**0.5 / 2.0,
)
CORE_FINISH_PICK = (F_X + 0.004, _sheet_y(CORE_DIA / 2.0))
CORE_FINISH_SYMBOL = (F_X + 0.010, SIDE_CENTER[1] + HALF_OD + 0.004)
# A point on the journal's face for the turning axis.
CENTERLINE_PICK = ((PINION_REAR_X + REAR_X) / 2.0, SIDE_CENTER[1] + 0.003)
GEAR_DATA_XY = (0.016, 0.262)
NOTES_XY = (0.016, 0.070)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-knob-shaft source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
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
            3: "transgear knob shaft; steel; 12T DP38 pinion, 1/4-20 stud, journal",
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
        view_label="rear end",
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

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_XY, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.0025
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
