r"""Create the curated knife-hanger stud drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from knife_hanger_stud_spec import (
    COLLAR_H,
    NUT_H,
    SHANK_LEN,
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

# Authored on the Top plane, axis +Y, threaded end DOWN: shank 0..48.75, then
# washer / hex / collar / tip up to 69.25.  The concentric stack (tip, collar,
# hex, washer) projects in the *Top view; the profile (axis VERTICAL, stack up)
# in the *Front view.
END_CENTER = (0.080, 0.160)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.320, 0.170)

# Side view: model y -> sheet y (stack up), centred on the profile bbox.
_Y_MID = TOTAL_LEN / 2.0


def _side_y(model_y: float) -> float:
    return SIDE_CENTER[1] + (model_y - _Y_MID) * _S


_SHANK_MID_Y = _side_y(SHANK_LEN / 2.0)
_NUT_MID_Y = _side_y(SHANK_LEN + WASHER_T + NUT_H / 2.0)
_TIP_MID_Y = _side_y(TOTAL_LEN - TIP_LEN / 2.0)
assert TOTAL_LEN == SHANK_LEN + WASHER_T + NUT_H + COLLAR_H + TIP_LEN

# End view: the marked washer diameter (the stack's outermost circle),
# leadered clear to the left.
END_DIM_X = 0.036
END_KEEP = {
    "WasherDia": (END_DIM_X, END_CENTER[1] + 0.036),
}
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: the shank/nut/tip lengths as the extrude-depth model dims (the
# vertical profile cannot point-select the edge-on stack steps), stacked to
# the right of the profile clear of the geometry.
SIDE_KEEP = {
    "ShankLg": (SIDE_CENTER[0] + 0.052, _SHANK_MID_Y),
    "NutHt": (SIDE_CENTER[0] + 0.052, _NUT_MID_Y),
    "TipLg": (SIDE_CENTER[0] + 0.052, _TIP_MID_Y),
}

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
