"""Supplier-family nominal diagrams beside both installed ANSI #25 members.

The supplier sizes belong to a zero-body construction-only reference state,
not the installed clearance pins/bushes. Both original members remain visible.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
import _config
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
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["sh_vn_chain_link"]
PART_STEM = SPEC.artifact_stem
# Pitch is a native model dimension on the nominal supplier diagram.
ITEM = "ANSI #25 ROLLER CHAIN"
# The 40-mm Top band needs room for the actual width gauge, not a 4-mm slot
# left by the generic family padding. Each diagram centres its own ink in its
# cell, so the Top cell's centre moves right by the roller circle's offset from
# the FRONT ink's centre (pin left edge to roller right edge) at the 5:1 fit:
# the roller-width square then sits over the Ø.130 roller circle (machinist
# review of 892b7f640). The left lane keeps the width text shelf.
_TOP_SCALE = 5
_ROLLER_FROM_FRONT_CENTRE = (
    PITCH - (PITCH + ROLLER_DIAMETER / 2 - PIN_DIAMETER / 2) / 2
) / 1000 * _TOP_SCALE
_CHAIN_SUPPLIER_MARGINS = {
    **SUPPLIER_MARGINS,
    "free_top": (0.030 + 2 * _ROLLER_FROM_FRONT_CENTRE, 0.010, 0.030, 0.010),
}
_MEMBER_QUANTITIES = _config.parts(SPEC.source.stem)["configuration_quantities"]
VARIANTS = (
    ("InnerLink", f"INSTALLED INNER LINK, QTY {_MEMBER_QUANTITIES['InnerLink']}"),
    ("OuterLink", f"INSTALLED OUTER LINK, QTY {_MEMBER_QUANTITIES['OuterLink']}"),
)


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
        installed_variants=VARIANTS,
        installed_configuration="InnerLink",
        stock_caption="SUPPLIER FAMILY NOMINAL DIAGRAM — NOT INSTALLED",
        spring_metadata=True,
        cut_to_suit=True,
        unit=part_drawing_unit("sh-vn-chain-link"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
