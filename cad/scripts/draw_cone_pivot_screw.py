r"""Create the curated cone-platform pivot shoulder-screw drawing.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
pivot screw is not on the rule-3 GD&T allowlist, so it carries no datums and
no feature-control frames -- the two bands the block cannot express ride
their model dimensions (build_cone_pivot_screw.py).  Both turned diameters
and every length sit on the longitudinal side view with the thread
designation, the thread-start chamfer and the under-head fillet leadered
to their features; the slot is dimensioned on the slot-profile (*Right)
view; the thread-end view carries the one roughness symbol, on the ground
shoulder (rule 5).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    set_hidden_lines_visible,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_annotations import add_thread_leader
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from _surface_finish import surface_finish_by_key
from cone_pivot_screw_spec import (
    HEAD_DIA,
    HEAD_T,
    SHOULDER_DIA,
    SHOULDER_LEN,
    SURFACE_FINISHES,
    THREAD_CHAMFER_CALLOUT,
    THREAD_DESIGNATION,
    THREAD_SOLID_DIA,
    UNDERHEAD_FILLET_CALLOUT,
    UNDERHEAD_LEN,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["cone_pivot_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_SCALE = (6.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Stacked from the under-head datum (Top plane, y = 0): head up to HEAD_T,
# shoulder down to -SHOULDER_LEN, tail on to -UNDERHEAD_LEN.  The profile
# (axis VERTICAL, head up) in *Front; the slot notch in *Right, aligned with
# it; the thread-end view in *Bottom.
END_CENTER = (0.070, 0.150)
SIDE_CENTER = (0.190, 0.170)
RIGHT_CENTER = (0.285, 0.170)
ISO_CENTER = (0.370, 0.170)

_Y_MID = (HEAD_T - UNDERHEAD_LEN) / 2.0


def _side_y(model_y: float) -> float:
    return SIDE_CENTER[1] + (model_y - _Y_MID) * _S


_HEAD_TOP_Y = _side_y(HEAD_T)
_UNDERHEAD_Y = _side_y(0.0)
_SHOULDER_END_Y = _side_y(-SHOULDER_LEN)
_TIP_Y = _side_y(-UNDERHEAD_LEN)
_HEAD_HALF = HEAD_DIA / 2.0 * _S
_SHOULDER_HALF = SHOULDER_DIA / 2.0 * _S
_TAIL_HALF = THREAD_SOLID_DIA / 2.0 * _S

# Thread-end view: nothing but the ground shoulder's roughness symbol (the
# diameters read on the side view, where a turned part's sizes belong).
END_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS: dict[str, str] = {}
SHOULDER_FINISH_EDGE_XY = (
    END_CENTER[0] + _SHOULDER_HALF * 0.7071,
    END_CENTER[1] - _SHOULDER_HALF * 0.7071,
)
SHOULDER_FINISH_SYMBOL_XY = (0.125, 0.136)

# Side view: head diameter above the head, head height right of it, shoulder
# length and shoulder diameter on the left (the diameter's dimension line
# sits below the shoulder, its extension lines running beside the narrower
# tail), thread length right of the tail.
SIDE_KEEP = {
    "HeadDiaDim": (SIDE_CENTER[0], _HEAD_TOP_Y + 0.017),
    "HeadHt": (SIDE_CENTER[0] + 0.042, (_HEAD_TOP_Y + _UNDERHEAD_Y) / 2.0),
    "ShoulderLg": (SIDE_CENTER[0] - 0.040, (_UNDERHEAD_Y + _SHOULDER_END_Y) / 2.0),
    "ShoulderDiaDim": (SIDE_CENTER[0] - 0.045, _SHOULDER_END_Y - 0.015),
    "ThreadLg": (SIDE_CENTER[0] + 0.048, (_SHOULDER_END_Y + _TIP_Y) / 2.0),
}
SIDE_DIMENSION_CALLOUTS: dict[str, str] = {}
# Slot-profile view: width across the notch above the head, depth down the
# notch to the right of the head.
SLOT_KEEP = {
    "SlotWDim": (RIGHT_CENTER[0], _HEAD_TOP_Y + 0.019),
    "SlotDepth": (RIGHT_CENTER[0] + _HEAD_HALF + 0.012, _HEAD_TOP_Y - 0.008),
}
# Leadered callouts: the thread designation to the tail's left outline
# (text lower-left), the thread-start chamfer to the same outline near the
# tip (text below the tip), the under-head fillet to the shoulder's right
# outline just under the head (text right of the profile, under the
# head-height dimension and left of the slot-profile view).
THREAD_LEADER_XY = (SIDE_CENTER[0] - _TAIL_HALF, _TIP_Y + 0.018)
THREAD_NOTE_XY = (SIDE_CENTER[0] - 0.058, _TIP_Y + 0.009)
CHAMFER_LEADER_XY = (SIDE_CENTER[0] - _TAIL_HALF, _TIP_Y + 0.004)
CHAMFER_NOTE_XY = (SIDE_CENTER[0] - 0.010, _TIP_Y - 0.017)
FILLET_LEADER_XY = (SIDE_CENTER[0] + _SHOULDER_HALF, _UNDERHEAD_Y - 0.005)
FILLET_NOTE_XY = (SIDE_CENTER[0] + 0.038, _UNDERHEAD_Y - 0.015)
SIDE_AXIS_FACE_XY = (SIDE_CENTER[0], _TIP_Y + 0.028)
SLOT_AXIS_FACE_XY = (RIGHT_CENTER[0], (_HEAD_TOP_Y + _UNDERHEAD_Y) / 2.0)


def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> None:
    """Add the slot-profile view, the leadered callouts and the shoulder finish."""
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    # Hidden lines ON in the slot-profile view (policy rule 7).
    set_hidden_lines_visible(adapter, right)
    curate_view_dimensions(adapter, right, keep=SLOT_KEEP, view_label="slot profile")
    add_view_centerline(
        adapter, right, face_xy=SLOT_AXIS_FACE_XY, label="slot-profile axis centerline"
    )

    add_thread_leader(
        adapter,
        side,
        designation=THREAD_DESIGNATION,
        silhouette_xy=THREAD_LEADER_XY,
        note_xy=THREAD_NOTE_XY,
        label="tail thread designation",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CHAMFER_CALLOUT,
        entity_xy=CHAMFER_LEADER_XY,
        note_xy=CHAMFER_NOTE_XY,
        label="thread start chamfer",
        entity_type="SILHOUETTE",
    )
    add_attached_note(
        adapter,
        side,
        text=UNDERHEAD_FILLET_CALLOUT,
        entity_xy=FILLET_LEADER_XY,
        note_xy=FILLET_NOTE_XY,
        label="under-head fillet",
        entity_type="SILHOUETTE",
    )

    add_surface_finish(
        adapter,
        end,
        edge_xy=SHOULDER_FINISH_EDGE_XY,
        symbol_xy=SHOULDER_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "ground_shoulder"),
        label="ground shoulder finish",
    )


RECIPE = FastenerSheet(
    title="Cone Pivot Screw Manufacturing Drawing",
    keywords="cone pivot screw; slotted shoulder screw; made fastener",
    scale=SHEET_SCALE,
    side_view="*Front",
    # Look from the threaded tail so the ground shoulder is visible inside the
    # larger head outline; the head-end view occludes that shoulder.
    end_view="*Bottom",
    side_center=SIDE_CENTER,
    end_center=END_CENTER,
    iso_center=ISO_CENTER,
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
    side_keep=SIDE_KEEP,
    side_dimension_callouts=SIDE_DIMENSION_CALLOUTS,
    note_xy=(0.020, 0.105),
    end_note_xy=(0.020, 0.245),
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
