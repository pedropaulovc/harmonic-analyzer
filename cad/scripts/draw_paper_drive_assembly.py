r"""Create the complete paper-drive assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import build_assembly_package
from _common import run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME


SPEC = DRAWINGS_BY_NAME["paper_drive_assembly"]
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

SHEET_SCALE = (1.0, 4.0)
REFERENCE_SCALE = (1.0, 10.0)
FRONT_CENTER = (0.105, 0.152)
RIGHT_CENTER = (0.300, 0.152)
ISO_CENTER = (0.335, 0.160)

ASSEMBLY_STEPS = (
    "Clamp the single support bar between the front and back halves at both columns.",
    "Hang the platen on the bar with two guide rails and four rear lock plates.",
    "Lock the rack to the platen with teeth down along the lower paper edge.",
    "Fit the transgear bracket, stud, 120T disc, and locked 12T feed pinion stack.",
    "Fit the latch arm, knob shaft, 12T third gear, T24 sprocket, knob, and thumbnut.",
    "Loop the chain from crank T12 to mounted T24; retain the spare T18 loose on the base.",
    "Install the paper and both edge clips only after the platen slides freely.",
)
CRITICAL_CHECKS = (
    "Align both chain sprockets in the machine Z=-155 mm plane.",
    "Paper feed is 1.596 mm/rev; verify 10 turns = 15.96 mm at the platen edge.",
    "Rack teeth face down; the 12T feed pinion stays meshed through full platen travel.",
    "Keep the latch-arm 12T:120T mesh engaged; the arm pivots on the stud but does not park out.",
    "Turn the crank through a full chain cycle; reject tight links, gear bind, or axial rub.",
)
HARDWARE_NOTES = (
    "BOM balloons identify clamp screws, guide locks, bracket screws, thumbnut, and clips.",
    "The T18 sprocket is a loose swap part; no threadlocker, shims, or lubricant specified.",
    "Tighten paired clamp screws evenly until the bar cannot slip; no numeric torque assigned.",
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
        pdf_title="Paper-Drive Assembly Drawing",
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
