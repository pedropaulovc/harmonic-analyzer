"""Create the four-view purchased-reference sheet for the AMPEC KP08 pillow block (MHA-CH-06-TL-VN-56).

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
from _machinist_review_mode import MachinistReviewMode
from _purchased_fastener_drawing import NumberFit
from _purchased_part_drawing import build_purchased_part_drawing


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pillow_block"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "KP08 PILLOW BLOCK, 8 MM BORE, SET-SCREW INSERT BEARING"


async def build(adapter: Any) -> dict[str, str]:
    # The 18-character registry number overruns the template's DWG. NO.
    # cell into REV; fit it there, measured.
    return await build_purchased_part_drawing(
        adapter, SPEC, item=ITEM, number_fit=NumberFit.SHRINK_TO_CELL
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
