r"""Create the complete frame assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import AssemblyDrawingLayout, build_assembly_package
from _common import run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME


SPEC = DRAWINGS_BY_NAME["frame_assembly"]
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
LAYOUT = AssemblyDrawingLayout(
    working_scale=(1.0, 7.0),
    exploded_scale=(1.0, 12.0),
    procedure_scale=(1.0, 8.0),
    reference_scale=(1.0, 22.0),
    working_front_center=(0.100, 0.170),
    working_right_center=(0.280, 0.170),
    exploded_center=(0.135, 0.170),
)

ASSEMBLY_STEPS = (
    "Place the harmonic base on the surface plate with its machined top face up.",
    "Seat all four columns on the base, keeping the original corner pairing.",
    "Turn the rocker support so its window faces ±X; seat its foot on the base.",
    "Bring the top-frame casting down over all columns and seat every corner boss.",
    "Tighten the four corner side screws evenly, then the gooseneck hub set screw.",
    "Fit four 9/16-12 lag screws upward into the support foot and secure the nameplate.",
)
CRITICAL_CHECKS = (
    "Rocker-support window faces ±X; its pivot is on the machine +X side.",
    "All column tops are at Y=1044.8 mm; rail top is Y=1036.2 mm, leaving 8.6 mm proud.",
    "Sweep the top rail with an indicator; correct seating before tightening any side screw.",
    "Verify all four posts square from the base and every support foot fully seated.",
)
HARDWARE_NOTES = (
    "Use four 9/16-12 support lags, four corner screws, and one gooseneck set screw.",
    "Nameplate uses four #4-40 fillister screws from the decorated face; no locker specified.",
    "No numeric torque is assigned; tighten only to full seating without casting distortion.",
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_assembly_package(
        adapter,
        source=SOURCE,
        outputs=OUTPUTS,
        sheet_scale=SHEET_SCALE,
        layout=LAYOUT,
        pdf_title="Frame Assembly Drawing",
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
