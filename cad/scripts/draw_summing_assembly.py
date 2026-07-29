r"""Create the one-sheet Front/Right/Isometric summing assembly drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import build_simple_three_view_drawing
from _common import run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME


SPEC = DRAWINGS_BY_NAME["summing_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 5.0)
FRONT_CENTER = (0.060, 0.150)
RIGHT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.225, 0.140)


async def build(adapter: Any) -> dict[str, str]:
    return await build_simple_three_view_drawing(
        adapter,
        source=SOURCE,
        outputs=OUTPUTS,
        sheet_scale=SHEET_SCALE,
        front_center=FRONT_CENTER,
        right_center=RIGHT_CENTER,
        iso_center=ISO_CENTER,
        pdf_title="Summing Assembly Drawing",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
