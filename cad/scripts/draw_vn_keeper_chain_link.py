"""Identification sheet for the 3606T811 trade-size-3 bead-chain loop link.

The generic capsule model is an installed-clearance stand-in, not a replica
of the supplier's photographed loop link. The supplier source publishes no
numeric dimensions; trade size 3 is an ordering designation, not a size to
attach to model geometry. Existing installed-loop controls remain unchanged.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_part_drawing import build_purchased_part_drawing


SPEC = DRAWINGS_BY_NAME["vn_keeper_chain_link"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "LOOP LINK FOR TRADE SIZE 3 BEAD CHAIN"
PART_STEM = SPEC.artifact_stem


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_part_drawing(
        adapter, SPEC, item=ITEM
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
