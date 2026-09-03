r"""Create the complete drive-train assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing import build_assembly_package
from _common import run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME


SPEC = DRAWINGS_BY_NAME["drive_train_assembly"]
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

SHEET_SCALE = (2.0, 5.0)
REFERENCE_SCALE = (1.0, 6.0)
FRONT_CENTER = (0.105, 0.155)
RIGHT_CENTER = (0.300, 0.155)
ISO_CENTER = (0.335, 0.160)

ASSEMBLY_STEPS = (
    "Seat the stationary cylinder arbor in both pedestals on the base reference.",
    "Stack 20 cylinder gear/cams end-for-end; keep every cosine notch toward +Y.",
    "Build the cone shaft big-to-small with each gear face normal to the shaft.",
    "Seat the cone platform on its tip pivot, big-end post, spacer, and cup adjuster.",
    "Install crankshaft, 16T pinion, 64T gear, crank arm, and handle in mesh order.",
    "Match-ream the MHA-020/MHA-026 pilot holes together 1:48, then fit the taper pin.",
    "Install the alignment pinion last and leave its swing rig parked disengaged.",
)
CRITICAL_CHECKS = (
    "Set cone-shaft tip end play to 0.79 mm (1/32 in) with a feeler at the tip spacer.",
    "Engaged cone/drum tooth interleave shall remain within 0.00–1.14 mm.",
    "At zero, all cylinder notches and integral cam lobes point toward machine +Y.",
    "Hand-turn one crank revolution; all 20 stages rotate without bind or axial rub.",
)
HARDWARE_NOTES = (
    "The BOM identifies the external spacer, cup adjuster, taper pin, and retainers.",
    "No threadlocker or shim pack is specified; do not lock either operational swing.",
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
        pdf_title="Drive-Train Assembly Drawing",
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
