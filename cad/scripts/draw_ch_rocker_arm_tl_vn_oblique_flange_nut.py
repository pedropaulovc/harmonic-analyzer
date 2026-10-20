"""Create the four-view purchased-reference sheet for the 1/2-13 flange nut (MHA-CH-06-TL-VN-60).

Identification only: the part as installed, its stock and ordering SKU, and
its receipt-verification note; no fabrication dimensions.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_part_drawing import build_purchased_part_drawing


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_flange_nut"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "1/2-13 FLANGE NUT, CLAMPING KIT"


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_part_drawing(adapter, SPEC, item=ITEM)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
