"""6261K171 outer-link identification: supplier stock and installed stand-in.

Exact source-derived pin/roller/width/pitch references are isolated from the
installed clearance representation. Installed-loop quantities and fitting
controls remain unchanged; no nominal supplier size is forced onto a stand-in.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_spring_drawing import build_supplier_spring_drawing
from _supplier_chain_dimensions import annotate_chain_stock


SPEC = DRAWINGS_BY_NAME["vn_chain_outer_link"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "ANSI #25 ROLLER CHAIN, OUTER LINK (1/4 PITCH)"


def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> tuple[Callable[[], None], ...]:
    return annotate_chain_stock(adapter, views, kind="outer")


async def build(adapter: Any) -> dict[str, str]:
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=False,
        spring_metadata=True,
        stock_caption="SUPPLIER STOCK SEGMENT",
        right_caption="SUPPLIER STOCK SEGMENT — RIGHT",
        dimensions=supplier_dimensions,
        supplier_margins={
            "free_front": (0.035, 0.018, 0.035, 0.016),
            "free_top": (0.040, 0.0, 0.0, 0.0),
        },
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
