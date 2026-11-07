"""Native supplier stock diagrams for connecting link 6261K108.

The installed clipless clearance stand-in remains unchanged and undimensioned.
All nominal source sizes belong to a zero-body construction reference state.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _machinist_review_mode import MachinistReviewMode
import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _supplier_chain_dimensions import (
    SOURCE_FEATURES,
    SUPPLIER_MARGINS,
    annotate_chain_stock,
    prepare_chain_diagrams,
)
from _supplier_chain_stock import (
    PIN_DIAMETER,
    PITCH,
    ROLLER_DIAMETER,
    SUPPLIER_REFERENCE_CONFIGURATION,
)
from _supplier_spring_drawing import build_supplier_spring_drawing

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_vn_chain_connecting_link"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "ANSI #25 ROLLER CHAIN, CONNECTING LINK"
# The same family diagrams as MHA-SH-VN-50's sheet, so the same TOP cell: each
# diagram centres its own ink in its cell, so the TOP cell's centre moves right
# by the roller circle's offset from the FRONT ink's centre at the 5:1 fit,
# and the roller-width square stands over the Ø.130 roller circle it projects
# from (machinist review, fan-out 2026-11-07: the TOP read as no projection).
_TOP_SCALE = 5
_ROLLER_FROM_FRONT_CENTRE = (
    PITCH - (PITCH + ROLLER_DIAMETER / 2 - PIN_DIAMETER / 2) / 2
) / 1000 * _TOP_SCALE
_CHAIN_SUPPLIER_MARGINS = {
    **SUPPLIER_MARGINS,
    "free_top": (0.030 + 2 * _ROLLER_FROM_FRONT_CENTRE, 0.010, 0.030, 0.010),
}


async def build(adapter: Any) -> dict[str, str]:
    return await build_supplier_spring_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=annotate_chain_stock,
        supplier_margins=_CHAIN_SUPPLIER_MARGINS,
        stock_configuration=SUPPLIER_REFERENCE_CONFIGURATION,
        prepare_views=prepare_chain_diagrams,
        supplier_reference_features=SOURCE_FEATURES,
        include_right=False,
        stock_caption="SUPPLIER NOMINAL DIAGRAM — NOT INSTALLED",
        spring_metadata=True,
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
