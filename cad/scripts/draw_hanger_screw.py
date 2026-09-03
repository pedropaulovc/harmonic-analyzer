r"""Create the curated pen-hanger hex-screw drawing.

Profile side view with the head height and under-head length in one row
above the profile, the thread designation leadered to the shank below it
and the axis centerline; a hex-head view carrying the across-flats as a
drawing-native linear; plus an isometric.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import DrawingOutputs, add_edge_dimension
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_annotations import add_thread_leader
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from hanger_screw_spec import HEAD_AF, HEAD_H, SHANK_DIA, SHANK_LEN, THREAD_DESIGNATION


SPEC = DRAWINGS_BY_NAME["hanger_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# #6-32 x 11.5 screw; 7:1 draws the 14 mm length as 98 mm and the hex head
# (7 across flats) as 49 mm.
SHEET_SCALE = (7.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Front plane, axis +Z: hex head at z in [0, HEAD_H], shank at
# z in [-SHANK_LEN, 0].  The hexagon (flats top and bottom) projects in the
# *Front view; the profile projects in the *Right view with the head on the
# LEFT (sheet +x is model -z) and the shank running right to its tip.
END_CENTER = (0.070, 0.150)
SIDE_CENTER = (0.190, 0.150)
ISO_CENTER = (0.325, 0.170)

# Side view: model z -> sheet x (head left), centred on the profile bbox.
_Z_MID = (HEAD_H - SHANK_LEN) / 2.0


def _side_x(model_z: float) -> float:
    return SIDE_CENTER[0] + (_Z_MID - model_z) * _S


_HEAD_END_X = _side_x(HEAD_H)  # head outer face (left)
_JUNCTION_X = _side_x(0.0)  # head/shank step
_SHANK_END_X = _side_x(-SHANK_LEN)  # shank tip (right)
_HEAD_TOP_Y = SIDE_CENTER[1] + HEAD_AF / 2.0 * _S  # upper flat silhouette
_SHANK_BOTTOM_Y = SIDE_CENTER[1] - SHANK_DIA / 2.0 * _S  # lower shank silhouette
_SHANK_MID_X = (_JUNCTION_X + _SHANK_END_X) / 2.0

# Head-end view: the hex is a polygon with no marked diameter, so its
# across-flats is a drawing-native vertical between the two flats, standing
# left of the hexagon.
_AF_HALF = HEAD_AF / 2.0 * _S
END_FLAT_PICKS = (
    (END_CENTER[0], END_CENTER[1] + _AF_HALF),
    (END_CENTER[0], END_CENTER[1] - _AF_HALF),
)
END_FLATS_TEXT_XY = (0.030, END_CENTER[1])
END_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: head height and under-head length as the extrude-depth model
# dims in one row above the profile, both off the under-head face.
_ROW_ABOVE_Y = _HEAD_TOP_Y + 0.014
SIDE_KEEP = {
    "HeadHt": ((_HEAD_END_X + _JUNCTION_X) / 2.0, _ROW_ABOVE_Y),
    "ShankLg": (_SHANK_MID_X, _ROW_ABOVE_Y),
}
# Thread designation: leader to the shank's lower outline, text below the
# profile, clear of the note block and the isometric.
THREAD_LEADER_XY = (_SHANK_MID_X + 0.010, _SHANK_BOTTOM_Y)
THREAD_NOTE_XY = (_SHANK_MID_X + 0.005, _SHANK_BOTTOM_Y - 0.024)
SIDE_AXIS_FACE_XY = (_SHANK_MID_X, SIDE_CENTER[1])


def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> None:
    add_thread_leader(
        adapter,
        side,
        designation=THREAD_DESIGNATION,
        silhouette_xy=THREAD_LEADER_XY,
        note_xy=THREAD_NOTE_XY,
        label="shank thread designation",
    )
    add_edge_dimension(
        adapter,
        end,
        p0=END_FLAT_PICKS[0],
        p1=END_FLAT_PICKS[1],
        text_xy=END_FLATS_TEXT_XY,
        label="hex across-flats",
        orientation="vertical",
    )


RECIPE = FastenerSheet(
    title="Hanger Screw Manufacturing Drawing",
    keywords="hanger screw; hex-head machine screw; made part",
    scale=SHEET_SCALE,
    side_view="*Right",
    end_view="*Front",
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
