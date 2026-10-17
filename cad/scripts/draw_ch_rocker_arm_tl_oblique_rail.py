"""Create the four-view purchased-reference sheet for the HIWIN HGR15R linear rail cut to 440 (MHA-CH-006-TL-30).

Identification only: the part as installed, its stock and ordering SKU, and
its cut-length or fitting note; no fabrication dimensions.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_part_drawing import build_purchased_part_drawing


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_rail"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "HIWIN HGR15R LINEAR GUIDEWAY RAIL, CUT TO 440 MM"


async def build(adapter: Any) -> dict[str, str]:
    # Bought cut to length, so not cut to suit at assembly.
    return await build_purchased_part_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=False
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
