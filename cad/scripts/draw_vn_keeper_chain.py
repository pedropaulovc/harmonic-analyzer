"""Reference sheet for McMaster-Carr 3606T118 brass bead chain.

The exact catalogue 3/32-inch bead diameter is imported from the seed bead's
native revolved profile. Pitch, rod and installed pose are project clearance
assumptions, not supplier dimensions. Cut-to-length controls are unchanged.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_part_drawing import build_purchased_part_drawing
from _supplier_chain_dimensions import annotate_keeper_bead


SPEC = DRAWINGS_BY_NAME["vn_keeper_chain"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "BEAD CHAIN, TRADE SIZE 3"
PART_STEM = SPEC.artifact_stem


async def build(adapter: Any) -> dict[str, str]:
    settled_checks: list[Callable[[], None]] = []

    def add_dimensions(target: Any, views: dict[str, Any]) -> None:
        settled_checks.append(annotate_keeper_bead(target, views))

    return await build_purchased_part_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=True,
        supplier_dimensions=add_dimensions,
        supplier_margins={"*Front": (0.0, 0.0, 0.040, 0.020)},
        settled_checks=settled_checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
