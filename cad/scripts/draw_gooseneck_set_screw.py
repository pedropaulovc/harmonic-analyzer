r"""Create the curated gooseneck set-screw drawing.

Profile side view with the head height and under-head length, the thread
designation leadered to the shank and the axis centerline; a wrench-flats
view with the across-flats; plus an isometric.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_annotations import (
    add_external_thread_depiction,
    add_hidden_shank_circle,
    add_thread_leader,
)
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from gooseneck_set_screw_spec import HEAD_H, SHANK_DIA, SHANK_LEN, THREAD_DESIGNATION


SPEC = DRAWINGS_BY_NAME["gooseneck_set_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# 1/4-20 x 16 screw; 5:1 draws the 22 mm length as ~110 mm and the square head
# (10 across flats) as ~50 mm.
SHEET_SCALE = (5.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Top plane, axis +Y: square head at y in [0, HEAD_H] (top),
# shank at y in [-SHANK_LEN, 0] (bottom).  The wrench-flats square projects in
# the *Top view; the profile (axis VERTICAL, head up) in the *Front view.
END_CENTER = (0.070, 0.150)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.310, 0.170)

# Side view: model y -> sheet y (head up), centred on the profile bbox.
_Y_MID = (HEAD_H - SHANK_LEN) / 2.0


def _side_y(model_y: float) -> float:
    return SIDE_CENTER[1] + (model_y - _Y_MID) * _S


_HEAD_END_Y = _side_y(HEAD_H)  # head outer face (top)
_JUNCTION_Y = _side_y(0.0)  # head/shank step
_SHANK_END_Y = _side_y(-SHANK_LEN)  # shank tip (bottom)
_SHANK_HALF = SHANK_DIA / 2.0 * _S
_SHANK_MID_Y = (_JUNCTION_Y + _SHANK_END_Y) / 2.0

# Head-end view: the marked across-flats width, leadered clear to the left.
END_DIM_X = 0.030
END_KEEP = {
    "HeadWDim": (END_DIM_X, END_CENTER[1] + 0.030),
}
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: the head-height and under-head length as the extrude-depth model
# dims (the vertical profile cannot point-select the edge-on shoulder/tip),
# stacked to the right of the profile clear of the geometry.
SIDE_KEEP = {
    "HeadHt": (SIDE_CENTER[0] + 0.052, (_HEAD_END_Y + _JUNCTION_Y) / 2.0),
    "ShankLg": (SIDE_CENTER[0] + 0.052, _SHANK_MID_Y),
}
# Thread designation: leader to the shank's left outline, text left of the
# profile (the dimensions live on the right).
THREAD_LEADER_XY = (SIDE_CENTER[0] - _SHANK_HALF, _SHANK_MID_Y)
THREAD_NOTE_XY = (SIDE_CENTER[0] - 0.064, _SHANK_MID_Y - 0.006)
SIDE_AXIS_FACE_XY = (SIDE_CENTER[0], _SHANK_MID_Y - 0.012)
THREAD_AXIS_XY = (
    (SIDE_CENTER[0], _JUNCTION_Y),
    (SIDE_CENTER[0], _SHANK_END_Y),
)
THREAD_MODEL_DIAMETER_SHEET = SHANK_DIA * _S
HIDDEN_SHANK_RADIUS_SHEET = SHANK_DIA * _S / 2.0



def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> None:
    add_hidden_shank_circle(
        adapter,
        end,
        center_xy=END_CENTER,
        radius_sheet=HIDDEN_SHANK_RADIUS_SHEET,
        label="wrench-flats hidden shank",
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


RECIPE = FastenerSheet(
    title="Gooseneck Set Screw Manufacturing Drawing",
    keywords="gooseneck set screw; square-head set screw; made part",
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
