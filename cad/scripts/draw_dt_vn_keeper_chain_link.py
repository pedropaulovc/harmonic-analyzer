"""Create the four-view purchased-reference sheet for McMaster-Carr 3606T811, brass bead-chain loop link.

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
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_part_drawing import build_purchased_part_drawing


SPEC = DRAWINGS_BY_NAME["dt_vn_keeper_chain_link"]
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "LOOP LINK FOR TRADE SIZE 3 BEAD CHAIN"
PART_STEM = SPEC.artifact_stem


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_part_drawing(
        adapter, SPEC, item=ITEM, unit=part_drawing_unit(PART_STEM)
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
