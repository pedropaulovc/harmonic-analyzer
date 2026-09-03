r"""Create the curated knife-hanger stud drawing.

Profile side view with every stack length as an extrude-depth model
dimension (chained from the threaded end), the shank and tip diameters as
linears across the profile, the thread designation leadered to the
threaded neck and the axis centerline; an end view with the washer and
collar diameters (leaders ending at their rims), the hex across-flats as a
drawing-native linear and the drilled centre called out on its circle;
plus an isometric.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import DrawingOutputs, add_attached_note, add_edge_dimension
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_annotations import (
    add_thread_leader,
    end_diameter_leaders_at_rim,
    view_dimension_annotations,
)
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from knife_hanger_stud_spec import (
    CDRILL_DIA,
    CENTER_DRILL_CALLOUT,
    COLLAR_H,
    NUT_AF,
    NUT_H,
    SHANK_LEN,
    THREAD_DESIGNATION,
    THREAD_DIA,
    THREAD_LEN,
    TIP_LEN,
    TOTAL_LEN,
    WASHER_T,
)


SPEC = DRAWINGS_BY_NAME["knife_hanger_stud"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# 1/2-13 x 69.25 stud; 2:1 draws the length as ~139 mm and the washer OD (28)
# as ~56 mm.
SHEET_SCALE = (2.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Top plane, axis +Y, threaded end DOWN: thread 0..12 (the
# reduced O10.6 engagement neck), plain shank 12..48.75, then washer / hex /
# collar / tip up to 69.25.  The concentric stack (tip, collar, hex, washer)
# projects in the *Top view; the profile (axis VERTICAL, stack up) in the
# *Front view.
END_CENTER = (0.080, 0.160)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.320, 0.170)

# Side view: model y -> sheet y (stack up), centred on the profile bbox.
_Y_MID = TOTAL_LEN / 2.0


def _side_y(model_y: float) -> float:
    return SIDE_CENTER[1] + (model_y - _Y_MID) * _S


_WASHER_Y = SHANK_LEN
_NUT_Y = _WASHER_Y + WASHER_T
_COLLAR_Y = _NUT_Y + NUT_H
_TIP_Y = _COLLAR_Y + COLLAR_H
assert _TIP_Y + TIP_LEN == TOTAL_LEN
_THREAD_MID_Y = _side_y(THREAD_LEN / 2.0)
_SHANK_MID_Y = _side_y((THREAD_LEN + SHANK_LEN) / 2.0)
_WASHER_MID_Y = _side_y(_WASHER_Y + WASHER_T / 2.0)
_NUT_MID_Y = _side_y(_NUT_Y + NUT_H / 2.0)
_COLLAR_MID_Y = _side_y(_COLLAR_Y + COLLAR_H / 2.0)
_TIP_MID_Y = _side_y(_TIP_Y + TIP_LEN / 2.0)
_THREAD_HALF = THREAD_DIA / 2.0 * _S

# End view: washer and collar diameters leadered from the left (arrows on
# their rims), the hex across-flats as a vertical between the top and bottom
# flats standing right of the stack, and the drilled centre called out on
# its circle from above (its leader runs between the across-flats extension
# lines and the washer leader).
_AF_HALF = NUT_AF / 2.0 * _S
_CDRILL_HALF = CDRILL_DIA / 2.0 * _S
END_KEEP = {
    "WasherDia": (0.036, END_CENTER[1] + 0.036),
    "CollarDia": (0.036, END_CENTER[1] - 0.034),
}
END_DIAMETERS = ("WasherDia", "CollarDia")
END_FLAT_PICKS = (
    (END_CENTER[0] + 0.004, END_CENTER[1] + _AF_HALF),
    (END_CENTER[0] + 0.004, END_CENTER[1] - _AF_HALF),
)
END_FLATS_TEXT_XY = (0.132, END_CENTER[1])
CDRILL_EDGE_XY = (
    END_CENTER[0] + _CDRILL_HALF * 0.7071,
    END_CENTER[1] + _CDRILL_HALF * 0.7071,
)
CDRILL_NOTE_XY = (END_CENTER[0] - 0.008, END_CENTER[1] + 0.050)
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: thread / shank / nut / tip lengths in a column right of the
# profile, washer thickness and collar height in a column on the left (the
# right column would otherwise stack six dimensions within 30 mm), and the
# shank and tip diameters as linears across the profile with their text to
# the left.
SIDE_KEEP = {
    "ThreadLg": (SIDE_CENTER[0] + 0.052, _THREAD_MID_Y),
    "ShankLg": (SIDE_CENTER[0] + 0.052, _SHANK_MID_Y),
    "NutHt": (SIDE_CENTER[0] + 0.052, _NUT_MID_Y),
    "TipLg": (SIDE_CENTER[0] + 0.052, _TIP_MID_Y),
    "WasherT": (SIDE_CENTER[0] - 0.056, _WASHER_MID_Y),
    "CollarHt": (SIDE_CENTER[0] - 0.056, _COLLAR_MID_Y),
    "ShankDia": (SIDE_CENTER[0] - 0.040, _side_y(30.0)),
    "TipDia": (SIDE_CENTER[0] - 0.038, _TIP_MID_Y),
}
# Thread designation: leader to the neck's left outline, text lower-left of
# the profile above the note block.
THREAD_LEADER_XY = (SIDE_CENTER[0] - _THREAD_HALF, _THREAD_MID_Y)
THREAD_NOTE_XY = (SIDE_CENTER[0] - 0.060, _THREAD_MID_Y - 0.005)
SIDE_AXIS_FACE_XY = (SIDE_CENTER[0], _SHANK_MID_Y)


def _decorate(adapter: Any, side: Any, end: Any, _iso: Any) -> None:
    end_diameter_leaders_at_rim(
        adapter,
        view_dimension_annotations(adapter, end),
        END_DIAMETERS,
        label="stack-end diameters",
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
    add_attached_note(
        adapter,
        end,
        text=CENTER_DRILL_CALLOUT,
        entity_xy=CDRILL_EDGE_XY,
        note_xy=CDRILL_NOTE_XY,
        label="tip centre drill",
    )
    add_thread_leader(
        adapter,
        side,
        designation=THREAD_DESIGNATION,
        silhouette_xy=THREAD_LEADER_XY,
        note_xy=THREAD_NOTE_XY,
        label="neck thread designation",
    )


RECIPE = FastenerSheet(
    title="Knife Hanger Stud Manufacturing Drawing",
    keywords="knife hanger stud; integral washer hex stud; made part",
    scale=SHEET_SCALE,
    side_view="*Front",
    end_view="*Top",
    side_center=SIDE_CENTER,
    end_center=END_CENTER,
    iso_center=ISO_CENTER,
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
    side_keep=SIDE_KEEP,
    note_xy=(0.020, 0.100),
    end_note_xy=(0.040, 0.235),
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
