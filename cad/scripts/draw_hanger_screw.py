r"""Create the curated pen-hanger hex-screw drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_drawing import FastenerSheet, build_fastener_sheet
from hanger_screw_spec import THREAD_DESIGNATION


SPEC = DRAWINGS_BY_NAME["hanger_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_SCALE = (7.0, 1.0)
END_KEEP = {"ShankDia": (0.028, 0.150)}
DIMENSION_CALLOUTS = {"ShankDia": THREAD_DESIGNATION}
RECIPE = FastenerSheet(
    title="Hanger Screw Manufacturing Drawing",
    keywords="hanger screw; hex-head machine screw; commercial fastener",
    scale=SHEET_SCALE,
    side_view="*Right",
    end_view="*Front",
    side_center=(0.190, 0.150),
    end_center=(0.070, 0.150),
    iso_center=(0.310, 0.170),
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_fastener_sheet(
        adapter, source=SOURCE, property_view=PART_STEM, outputs=OUTPUTS, recipe=RECIPE
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
