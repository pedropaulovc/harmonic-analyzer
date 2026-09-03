r"""Create the complete harmonic-analyzer assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import build_assembly_package
from _common import run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME


SPEC = DRAWINGS_BY_NAME["harmonic_analyzer_assembly"]
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

SHEET_SCALE = (1.0, 7.0)
REFERENCE_SCALE = (1.0, 16.0)
FRONT_CENTER = (0.105, 0.152)
RIGHT_CENTER = (0.300, 0.152)
ISO_CENTER = (0.335, 0.158)

ASSEMBLY_STEPS = (
    "Level the frame, then install the drive train with crank side toward machine -X.",
    "Install the channel bank so every rod ring rides its matching integral cam.",
    "Hang the summing assembly and link all 20 channel spring hooks to its plate.",
    "Fit the magnifier at output side -Z and connect WIRE 1 to the wheel hub.",
    "Clamp the pen hanger to the wheel bar and connect WIRE 2 to the pen rod.",
    "Install the paper drive, align both sprockets at Z=-155 mm, and close the chain.",
    "Park the measuring stick graduations-up on its stop block on the base deck.",
)
CRITICAL_CHECKS = (
    "Machine +Y is up, -X is crank side, and -Z is the signal-output side.",
    "Column clamps have Ø25.6 bores on Ø25.4 posts; seat both halves without rocking.",
    "Ship with alignment pinion disengaged and the cone train engaged at cosine zero.",
    "Paper feed is 1.596 mm/rev; verify 10 turns = 15.96 mm at the platen edge.",
    "With channels at cosine zero, verify level rockers/levers and free vertical pen travel.",
)
HARDWARE_NOTES = (
    "The top-level BOM identifies seven subassemblies plus all loose parked hardware.",
    "No top-level threadlocker, shim pack, or added lubricant is specified.",
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
        pdf_title="Harmonic Analyzer Assembly Drawing",
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
