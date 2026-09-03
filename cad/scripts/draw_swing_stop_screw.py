r"""Create the curated cone-platform swing-stop screw drawing.

Profile side view with the head height and under-head length, the (REF)
overall outside them, the thread designation leadered to the shank and the
axis centerline; a slot-profile
(*Right) view where the driver slot is a visible notch, carrying its width
and depth; a driver-face view with the head diameter (leader ending at the
rim) and a center mark; plus an isometric.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import (
    DrawingOutputs,
    add_view_centerline,
    curate_view_dimensions,
    set_hidden_lines_visible,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_annotations import (
    add_circle_center_mark,
    add_external_thread_depiction,
    add_overall_reference,
    add_thread_leader,
    end_diameter_leaders_at_rim,
    view_dimension_annotations,
)
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from swing_stop_screw_spec import (
    EMBED_LEN,
    HEAD_DIA,
    HEAD_T,
    PROUD_LEN,
    SHANK_DIA,
    SHANK_LEN,
    SLOT_D,
    THREAD_DESIGNATION,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["swing_stop_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# #8-32 x 14 screw; 6:1 draws the 16.5 mm length as 99 mm and the head OD (8)
# as 48 mm.
SHEET_SCALE = (6.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Top plane, axis +Y, origin at the base top: the shank runs
# from the tip at -EMBED_LEN up to the under-head face at PROUD_LEN, the head
# HEAD_T above that.  Only the extents matter here, so the profile is mapped
# relative to the under-head face (head at [0, HEAD_T], shank at
# [-SHANK_LEN, 0]).  The head-end circle projects in the *Top view; the
# profile (axis VERTICAL, head up) in the *Front view; the slot notch in the
# *Right view, aligned with the profile.
END_CENTER = (0.070, 0.150)
SIDE_CENTER = (0.190, 0.190)
RIGHT_CENTER = (0.285, 0.190)
ISO_CENTER = (0.370, 0.170)

# Side view: model y -> sheet y (head up), centred on the profile bbox.  The
# profile spans SHANK_LEN + HEAD_T regardless of where the origin sits.
_Y_TOP = HEAD_T
_Y_BOTTOM = -SHANK_LEN
_Y_MID = (_Y_TOP + _Y_BOTTOM) / 2.0


def _side_y(model_y: float) -> float:
    return SIDE_CENTER[1] + (model_y - _Y_MID) * _S


_HEAD_END_Y = _side_y(_Y_TOP)  # head outer face (top)
_JUNCTION_Y = _side_y(0.0)  # head/shank step
_SHANK_END_Y = _side_y(_Y_BOTTOM)  # shank tip (bottom)
_HEAD_HALF = HEAD_DIA / 2.0 * _S
_SHANK_HALF = SHANK_DIA / 2.0 * _S
_SHANK_MID_Y = (_JUNCTION_Y + _SHANK_END_Y) / 2.0

# Head-end view: the head diameter leadered from upper-left, arrow on the near
# rim; center mark picked on the lower-right rim, clear of the slot lines.
END_KEEP = {"HeadDiaDim": (0.028, 0.176)}
END_DIAMETERS = ("HeadDiaDim",)
END_CENTER_MARK_XY = (
    END_CENTER[0] + _HEAD_HALF * 0.7071,
    END_CENTER[1] - _HEAD_HALF * 0.7071,
)
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: the head-height and under-head length as the extrude-depth model
# dims, chained in an inner column right of the profile; the (REF) overall
# stands in the outer column so the conspicuous 14.00 reads as the under-head
# length, not the overall.  Both columns clear the slot-profile view at 0.261.
SIDE_DIM_X = SIDE_CENTER[0] + 0.036
OVERALL_DIM_X = SIDE_CENTER[0] + 0.056
SIDE_KEEP = {
    "HeadHt": (SIDE_DIM_X, (_HEAD_END_Y + _JUNCTION_Y) / 2.0),
    "ShankLg": (SIDE_DIM_X, _SHANK_MID_Y),
}
# Overall picks in TRUE model coordinates (origin at the base top): the head
# top at PROUD_LEN + HEAD_T, the tip at -EMBED_LEN, each on the right half of
# its end face (the driver-face rim is whole there; the slot breaks it beside
# the axis).
OVERALL_END_POINTS_MM = (
    (0.7 * HEAD_DIA / 2.0, PROUD_LEN + HEAD_T, 0.0),
    (0.7 * SHANK_DIA / 2.0, -EMBED_LEN, 0.0),
)
OVERALL_TEXT_XY = (OVERALL_DIM_X, SIDE_CENTER[1])
# Slot-profile view: width across the notch above the head, depth down the
# notch to the right of the head.
SLOT_KEEP = {
    "SlotWDim": (RIGHT_CENTER[0], _HEAD_END_Y + 0.014),
    "SlotDepth": (RIGHT_CENTER[0] + _HEAD_HALF + 0.016, _HEAD_END_Y - SLOT_D * _S / 2.0),
}
# Thread designation: leader to the shank's left outline, text left of the
# profile (the dimensions live on the right).
THREAD_LEADER_XY = (SIDE_CENTER[0] - _SHANK_HALF, _SHANK_MID_Y)
THREAD_NOTE_XY = (SIDE_CENTER[0] - 0.062, _SHANK_MID_Y - 0.006)
SIDE_AXIS_FACE_XY = (SIDE_CENTER[0], _SHANK_MID_Y - 0.012)
SLOT_AXIS_FACE_XY = (RIGHT_CENTER[0], (_HEAD_END_Y + _JUNCTION_Y) / 2.0)
THREAD_AXIS_XY = (
    (SIDE_CENTER[0], _JUNCTION_Y),
    (SIDE_CENTER[0], _SHANK_END_Y),
)
THREAD_MODEL_DIAMETER_SHEET = SHANK_DIA * _S



def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> None:
    end_diameter_leaders_at_rim(
        adapter,
        view_dimension_annotations(adapter, end),
        END_DIAMETERS,
        label="head-end diameters",
    )
    add_circle_center_mark(
        adapter, end, edge_xy=END_CENTER_MARK_XY, label="head rim center mark"
    )
    add_external_thread_depiction(
        adapter,
        side,
        axis_start_xy=THREAD_AXIS_XY[0],
        axis_end_xy=THREAD_AXIS_XY[1],
        model_diameter_sheet=THREAD_MODEL_DIAMETER_SHEET,
        sheet_scale_per_mm=_S,
        designation=THREAD_DESIGNATION,
        label="shank external thread",
    )
    add_thread_leader(
        adapter,
        side,
        designation=THREAD_DESIGNATION,
        silhouette_xy=THREAD_LEADER_XY,
        note_xy=THREAD_NOTE_XY,
        label="shank thread designation",
    )
    add_overall_reference(
        adapter,
        side,
        end_points_mm=OVERALL_END_POINTS_MM,
        entity_types=("EDGE", "EDGE"),
        text_xy=OVERALL_TEXT_XY,
        orientation="vertical",
        label="overall length reference",
    )
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    set_hidden_lines_visible(adapter, right)
    curate_view_dimensions(adapter, right, keep=SLOT_KEEP, view_label="slot profile")
    add_view_centerline(
        adapter, right, face_xy=SLOT_AXIS_FACE_XY, label="slot-profile axis centerline"
    )


RECIPE = FastenerSheet(
    title="Swing Stop Screw Manufacturing Drawing",
    keywords="swing stop screw; slotted fillister screw; made part",
    scale=SHEET_SCALE,
    side_view="*Front",
    end_view="*Top",
    side_center=SIDE_CENTER,
    end_center=END_CENTER,
    iso_center=ISO_CENTER,
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
    side_keep=SIDE_KEEP,
    side_centerline_face_xy=SIDE_AXIS_FACE_XY,
    decorate=_decorate,
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_fastener_sheet(
        adapter, source=SOURCE, property_view=PART_STEM, outputs=OUTPUTS, recipe=RECIPE
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
