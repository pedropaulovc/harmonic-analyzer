r"""Create the curated top-frame boss side-screw drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from frame_side_screw_spec import HEAD_H, SHANK_LEN


SPEC = DRAWINGS_BY_NAME["frame_side_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# #10-24 x 12.7 screw; 6:1 draws the ~15.7 mm length as ~94 mm and the head
# OD (7) as ~42 mm.
SHEET_SCALE = (6.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Top plane, axis +Y: head at y in [0, HEAD_H] (top), shank at
# y in [-SHANK_LEN, 0] (bottom).  The head-end circle projects in the *Top
# view; the profile (axis VERTICAL, head up) in the *Front view.
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

# Head-end view: the marked head diameter, leadered clear to the left.
END_DIM_X = 0.030
END_KEEP = {
    "HeadDia": (END_DIM_X, END_CENTER[1] + 0.028),
}
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: the head-height and under-head length as the extrude-depth model
# dims (the vertical profile cannot point-select the edge-on shoulder/tip),
# stacked to the right of the profile clear of the geometry.
SIDE_KEEP = {
    "HeadHt": (SIDE_CENTER[0] + 0.052, (_HEAD_END_Y + _JUNCTION_Y) / 2.0),
    "ShankLg": (SIDE_CENTER[0] + 0.052, (_JUNCTION_Y + _SHANK_END_Y) / 2.0),
}

RECIPE = FastenerSheet(
    title="Frame Side Screw Manufacturing Drawing",
    keywords="frame side screw; slotted cheese-head screw; made part",
    scale=SHEET_SCALE,
    side_view="*Front",
    end_view="*Top",
    side_center=SIDE_CENTER,
    end_center=END_CENTER,
    iso_center=ISO_CENTER,
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
    side_keep=SIDE_KEEP,
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
