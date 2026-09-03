r"""Create the complete summing assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import AssemblyDrawingLayout, build_assembly_package
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

SHEET_SCALE = (1.0, 4.0)
LAYOUT = AssemblyDrawingLayout(
    working_scale=(1.0, 4.0),
    exploded_scale=(1.0, 6.0),
    procedure_scale=(1.0, 5.0),
    reference_scale=(1.0, 12.0),
    exploded_center=(0.135, 0.180),
    reference_front_center=(0.080, 0.052),
    reference_right_center=(0.170, 0.052),
)

ASSEMBLY_STEPS = (
    "Seat one knife mount on each hex trunnion, with both contact ridges collinear.",
    "Thread each hanger stud 12.0 mm into its mount and pass it through the crossbar.",
    "Lower the summing lever onto the two knife ridges; leave the rocking DOF free.",
    "Key the boss hook to the lever anchor eye on the machine -X side.",
    "Hang the counter-spring between boss hook and gooseneck end screw.",
    "Drop the gooseneck post into the east-rail hub and secure it with the set screw.",
)
CRITICAL_CHECKS = (
    "Knife line runs along Z at machine X=-15.0 mm and Y=979.7 mm.",
    "Keep a 0.25 mm gap from each mount to the casting underside after stud seating.",
    "Counter-spring wire, coil, screw head, and arm end each retain at least 0.25 mm air.",
    "At zero the lever is level; rock it through travel with no knife, spring, or link bind.",
    "Adjust gooseneck until the unloaded lever is level by height gauge; lock the hub.",
)
HARDWARE_NOTES = (
    "BOM balloons identify two hanger studs, their integral washers/nuts, and the set screw.",
    "No shims or threadlocker are specified; keep the knife contacts clean and dry.",
    "Tighten the hub set screw only until the post holds; no numeric torque is assigned.",
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_assembly_package(
        adapter,
        source=SOURCE,
        outputs=OUTPUTS,
        sheet_scale=SHEET_SCALE,
        layout=LAYOUT,
        pdf_title="Summing Assembly Drawing",
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
