r"""Create the complete channel assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import AssemblyDrawingLayout, build_assembly_package
from _common import run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME


SPEC = DRAWINGS_BY_NAME["channel_assembly"]
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

SHEET_SCALE = (1.0, 6.0)
LAYOUT = AssemblyDrawingLayout(
    working_scale=(1.0, 7.0),
    exploded_scale=(1.0, 20.0),
    procedure_scale=(1.0, 12.0),
    reference_scale=(1.0, 20.0),
    exploded_center=(0.130, 0.170),
    working_display_mode="shaded-with-edges",
)

ASSEMBLY_STEPS = (
    "Install the pivot and fulcrum shafts with their end keepers at the frame rails.",
    "Alternate 20 rockers with 19 pivot bushings; keep the stations in Z order.",
    "Hang each connecting rod plumb from its cam to the rocker rod-side pin.",
    "Fit each amplitude bar across Z; its end slots straddle the rocker and lever.",
    "Alternate 20 levers with 19 bushings; keep every spring ring normal to its lever.",
    "Seat every lower spring eye on its J-hook above the summing-plate interface.",
)
CRITICAL_CHECKS = (
    "Machine -X is the crank side and -Z is the output side.",
    "At cosine zero, cam lobes point +Y, rockers lie level, and rods hang plumb.",
    "Caliper adjacent channel mid-planes to 7.0565 mm; bars and levers share each plane.",
    "Cycle every free rocker/bar/lever chain; no spring or neighboring channel may rub.",
)
HARDWARE_NOTES = (
    "BOM balloons identify both shaft keepers, screws, bushings, and all 20 J-hooks.",
    "No threadlocker, shim, or added lubricant is specified for this subassembly.",
    "Keeper screws are retention-only; tighten snug without clamping either free shaft.",
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_assembly_package(
        adapter,
        source=SOURCE,
        outputs=OUTPUTS,
        sheet_scale=SHEET_SCALE,
        layout=LAYOUT,
        pdf_title="Channel Assembly Drawing",
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
