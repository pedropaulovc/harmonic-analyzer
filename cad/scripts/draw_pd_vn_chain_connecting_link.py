"""Create the four-view purchased-reference sheet for connecting link 6261K108.

Identification only: the link as installed (two side plates and two pins,
the spring clip not modelled), its stock and ordering SKU. The roller-chain
family diagrams that MHA-SH-VN-50's sheet carries describe an inner link's
roller, which a connecting link does not have; beside this part's own
pictorial they read as contradictory projections (machinist review, fan-out
2026-11-07, rule 25). ITEM names the replacement, so the sheet prints no
supplier sizes.
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

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_vn_chain_connecting_link"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "ANSI #25 ROLLER CHAIN, CONNECTING LINK"


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
