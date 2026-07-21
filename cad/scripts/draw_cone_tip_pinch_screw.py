r"""Create the curated cone-tip pinch-screw drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_drawing import FastenerSheet, build_fastener_sheet


SPEC = DRAWINGS_BY_NAME["cone_tip_pinch_screw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_SCALE = (8.0, 1.0)
END_KEEP = {"HeadDiaDim": (0.028, 0.176)}
DIMENSION_CALLOUTS: dict[str, str] = {}
RECIPE = FastenerSheet(
    title="Cone Tip Pinch Screw Manufacturing Drawing",
    keywords="cone tip pinch screw; slotted fillister screw; made part",
    scale=SHEET_SCALE,
    side_view="*Front",
    end_view="*Top",
    side_center=(0.190, 0.190),
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
