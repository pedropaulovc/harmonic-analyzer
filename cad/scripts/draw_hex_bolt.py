r"""Create the curated portal-foot hex-bolt drawing."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, run_build
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_drawing import FastenerSheet, build_fastener_sheet


SPEC = DRAWINGS_BY_NAME["hex_bolt"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_SCALE = (4.0, 1.0)
END_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS: dict[str, str] = {}
RECIPE = FastenerSheet(
    title="Hex Bolt Manufacturing Drawing",
    keywords="portal foot bolt; hex-head bolt; made part",
    scale=SHEET_SCALE,
    side_view="*Front",
    end_view="*Top",
    side_center=(0.200, 0.150),
    end_center=(0.070, 0.150),
    iso_center=(0.340, 0.175),
    end_keep=END_KEEP,
    dimension_callouts=DIMENSION_CALLOUTS,
    note_xy=(0.020, 0.070),
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
