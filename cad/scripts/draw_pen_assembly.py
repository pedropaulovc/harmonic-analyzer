r"""Create the complete pen assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import build_assembly_package
from _common import run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME


SPEC = DRAWINGS_BY_NAME["pen_assembly"]
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

SHEET_SCALE = (2.0, 3.0)
REFERENCE_SCALE = (1.0, 4.0)
FRONT_CENTER = (0.105, 0.152)
RIGHT_CENTER = (0.300, 0.152)
ISO_CENTER = (0.335, 0.160)

ASSEMBLY_STEPS = (
    "Fasten the pen hanger behind the wheel bar with its guide block vertical.",
    "Slide the square pen rod upward through the hanger; leave the Y travel free.",
    "Seat the rod 13.0 mm into the v-block bore nearest the recording paper.",
    "Turn the v-block 45° so the marker groove points forward and east toward the paper.",
    "Lay the marker in the lower groove, then fit the brass stirrup around the block.",
    "Run the set screw upward only enough to retain the marker without crushing it.",
    "Attach WIRE 2 from the magnifying-wheel rim to the pen-rod wire hole.",
)
CRITICAL_CHECKS = (
    "The rod axis is vertical at machine X=3.0 mm and Z=-157.0 mm.",
    "The marker meets the paper at 45°; the v-block and stirrup must remain clear.",
    "Nib reaches the paper while the rod still slides freely through its full Y travel.",
    "Park with the nib just clear of paper and the marker set screw only finger snug.",
)
HARDWARE_NOTES = (
    "BOM balloons identify the hanger screw, marker set screw, stirrup, and WIRE 2.",
    "No shim, threadlocker, or added lubricant is specified for the free guide.",
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_assembly_package(
        adapter,
        source=SOURCE,
        outputs=OUTPUTS,
        sheet_scale=SHEET_SCALE,
        reference_scale=REFERENCE_SCALE,
        front_center=FRONT_CENTER,
        right_center=RIGHT_CENTER,
        iso_center=ISO_CENTER,
        pdf_title="Pen Assembly Drawing",
        assembly_steps=ASSEMBLY_STEPS,
        critical_checks=CRITICAL_CHECKS,
        hardware_notes=HARDWARE_NOTES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
