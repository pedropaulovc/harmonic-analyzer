r"""Create the complete magnifier assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import build_assembly_package
from _common import run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME


SPEC = DRAWINGS_BY_NAME["magnifier_assembly"]
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

SHEET_SCALE = (1.0, 3.0)
REFERENCE_SCALE = (1.0, 8.0)
FRONT_CENTER = (0.105, 0.152)
RIGHT_CENTER = (0.300, 0.152)
ISO_CENTER = (0.335, 0.160)

ASSEMBLY_STEPS = (
    "Lock the magnifying bracket to the summing lever with its collar on the rod.",
    "Slide the clamp group to the required knife-edge radius; fit its vertical rod.",
    "Clamp the half-width wheel bar to the +X front column, free end toward the pen.",
    "Fit the axle and wheel so the wheel spins freely on its stud.",
    "Hook WIRE 1 at the output fixture, then seat its other end at the hub groove.",
    "Back out the clamp thumb screw to tangent contact and lock the selected ratio.",
)
CRITICAL_CHECKS = (
    "Machine -Z is the output side; keep fixture, hub wire, rim wire, and pen line coplanar.",
    "Set magnification by radius from the knife edge; do not exceed the 4× limit.",
    "WIRE 1 remains 0.25 mm clear of the hub surface in the straight rest pose.",
    "Wheel and lever must return freely through full travel without wire or column rub.",
)
HARDWARE_NOTES = (
    "BOM balloons identify both column-clamp halves, two clamp screws, axle, and thumb screw.",
    "No shims, threadlocker, or added lubricant are specified; the wires are supplied parts.",
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
        pdf_title="Magnifier Assembly Drawing",
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
