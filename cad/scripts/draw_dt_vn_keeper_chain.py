"""Reference sheet for McMaster-Carr 3603T354 #18 brass jack chain.

The catalogue wire diameter imports the native diameter of the part's
neck-section reference circle. The eye inside diameter is unpublished and the
installed pose is a project assumption; the cut (LINK_COUNT links) is the note.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_part_drawing import build_purchased_part_drawing
from _supplier_keeper_dimensions import VIEW as SUPPLIER_VIEW
from _supplier_keeper_dimensions import annotate_keeper_wire


SPEC = DRAWINGS_BY_NAME["dt_vn_keeper_chain"]
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "JACK CHAIN, TRADE SIZE 18"
PART_STEM = SPEC.artifact_stem


async def build(adapter: Any) -> dict[str, str]:
    settled_checks: list[Callable[[], None]] = []

    def add_dimensions(target: Any, views: dict[str, Any]) -> None:
        settled_checks.append(annotate_keeper_wire(target, views))

    return await build_purchased_part_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=True,
        supplier_dimensions=add_dimensions,
        # The catalogue wire size stands right of the right view
        # (_supplier_keeper_dimensions): its text block is about 45 mm wide.
        supplier_margins={SUPPLIER_VIEW: (0.0, 0.0, 0.055, 0.0)},
        settled_checks=settled_checks,
        unit=part_drawing_unit(PART_STEM),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
