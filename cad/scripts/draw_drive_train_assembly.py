r"""Create the complete drive-train assembly drawing package."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _config
import _telemetry
from _assembly_drawing import AssemblyDrawingLayout, build_assembly_package
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
LAYOUT = AssemblyDrawingLayout(
    working_scale=(1.0, 3.0),
    exploded_scale=(1.0, 10.0),
    procedure_scale=(1.0, 6.0),
    reference_scale=(1.0, 8.0),
    working_front_center=(0.095, 0.168),
    working_right_center=(0.278, 0.168),
    exploded_center=(0.130, 0.180),
    working_display_mode="shaded-with-edges",
)
INTERLEAVE_MIN_MM, INTERLEAVE_MAX_MM = (
    float(value) for value in _config.fit("cone_drum_oblique_mesh", "tip_interleave_mm")
)

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
    f"Engaged cone/drum tooth interleave: {INTERLEAVE_MIN_MM:.2f}–{INTERLEAVE_MAX_MM:.2f} mm.",
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
        layout=LAYOUT,
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
