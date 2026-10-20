"""Draw both installed link forms of shared McMaster-Carr 6261K171.

Two explicitly configured four-view panels retain the purchased identification
content. Installed member counts are distinct from chain ordered by the foot.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_variant_drawing import build_purchased_variant_drawing


SPEC = DRAWINGS_BY_NAME["sh_vn_chain_link"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "ANSI #25 ROLLER CHAIN (1/4 PITCH)"
VARIANTS = (("InnerLink", "INNER LINK"), ("OuterLink", "OUTER LINK"))
PURCHASE_UNIT = "CHAIN BY THE FOOT"


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_variant_drawing(
        adapter,
        SPEC,
        variants=VARIANTS,
        item=ITEM,
        purchase_unit=PURCHASE_UNIT,
        cut_to_suit=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
