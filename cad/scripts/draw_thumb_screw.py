r"""Create the curated magnifier thumb-screw drawing.

Profile side view with the head length and under-head length in one row
above the profile, the thread designation leadered to the shank below it
and the axis centerline; a shank-end view with the head diameter (before
reeding, leader ending at the rim); plus an isometric.
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
    add_thread_leader,
    end_diameter_leaders_at_rim,
    view_dimension_annotations,
)
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from thumb_screw_spec import (
    HEAD_DIA,
    HEAD_LENGTH,
    SHANK_DIA,
    SHANK_LEN,
    THREAD_DESIGNATION,
)


SPEC = DRAWINGS_BY_NAME["thumb_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# #4-40 x 11 reeded thumb screw; 6:1 draws the 16 mm overall as 96 mm and
# the head OD (10) as 60 mm.
SHEET_SCALE = (6.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Right plane, axis +X: head at x in [0, HEAD_LENGTH], shank at
# x in [HEAD_LENGTH, HEAD_LENGTH + SHANK_LEN].  The end view (*Right) looks
# from the shank tip toward the head; the profile (axis HORIZONTAL, head
# left) in the *Front view.
END_CENTER = (0.070, 0.150)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.335, 0.170)

# Side view: model x -> sheet x, centred on the profile bbox.
_X_MID = (HEAD_LENGTH + SHANK_LEN) / 2.0


def _side_x(model_x: float) -> float:
    return SIDE_CENTER[0] + (model_x - _X_MID) * _S


_HEAD_FACE_X = _side_x(0.0)  # head outer face (left)
_SHOULDER_X = _side_x(HEAD_LENGTH)  # head/shank step
_TIP_X = _side_x(HEAD_LENGTH + SHANK_LEN)  # shank tip (right)
_HEAD_TOP_Y = SIDE_CENTER[1] + HEAD_DIA / 2.0 * _S  # upper head silhouette
_SHANK_BOTTOM_Y = SIDE_CENTER[1] - SHANK_DIA / 2.0 * _S  # lower shank silhouette
_SHANK_MID_X = (_SHOULDER_X + _TIP_X) / 2.0

# Shank-end view: the marked head diameter (the turned blank, before the
# reeding scallops it), leadered from upper-left with its arrow on the rim.
END_KEEP = {"HeadDia": (0.028, 0.176)}
END_DIAMETERS = ("HeadDia",)
DIMENSION_CALLOUTS = {"HeadDia": "BEFORE REEDING"}

# Side view: head length and under-head length as the extrude-depth model dims
# in one row above the profile, both off the shoulder.
_ROW_ABOVE_Y = _HEAD_TOP_Y + 0.014
SIDE_KEEP = {
    "HeadLg": ((_HEAD_FACE_X + _SHOULDER_X) / 2.0, _ROW_ABOVE_Y),
    "ShankLg": (_SHANK_MID_X, _ROW_ABOVE_Y),
}
# Thread designation: leader to the shank's lower outline, text below the
# profile, clear of the note block and the isometric.
THREAD_LEADER_XY = (_SHANK_MID_X + 0.010, _SHANK_BOTTOM_Y)
THREAD_NOTE_XY = (_SHANK_MID_X, _SHANK_BOTTOM_Y - 0.026)
SIDE_AXIS_FACE_XY = (_SHANK_MID_X, SIDE_CENTER[1])


def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> None:
    end_diameter_leaders_at_rim(
        adapter,
        view_dimension_annotations(adapter, end),
        END_DIAMETERS,
        label="head-end diameters",
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
    title="Thumb Screw Manufacturing Drawing",
    keywords="magnifier thumb screw; reeded screw; made part",
    scale=SHEET_SCALE,
    side_view="*Front",
    end_view="*Right",
    side_center=SIDE_CENTER,
    end_center=END_CENTER,
    iso_center=ISO_CENTER,
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
    side_keep=SIDE_KEEP,
    note_xy=(0.020, 0.110),
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
