"""Supplier-family nominal diagrams beside both installed ANSI #25 members.

The supplier sizes belong to a zero-body construction-only reference state,
not the installed clearance pins/bushes. Both original members remain visible.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _config import parts
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_chain_dimensions import (
    SUPPLIER_MARGINS,
    annotate_chain_stock,
    prepare_chain_diagrams,
)
from _supplier_chain_stock import SUPPLIER_REFERENCE_CONFIGURATION
from _supplier_spring_drawing import build_supplier_spring_drawing


SPEC = DRAWINGS_BY_NAME["sh_vn_chain_link"]
PART_STEM = SPEC.artifact_stem
# Pitch is a native model dimension on the nominal supplier diagram.
ITEM = "ANSI #25 ROLLER CHAIN"
_MEMBER_QUANTITIES = parts(PART_STEM)["configuration_quantities"]
VARIANTS = (
    ("InnerLink", f"INSTALLED INNER LINK, QTY {_MEMBER_QUANTITIES['InnerLink']}"),
    ("OuterLink", f"INSTALLED OUTER LINK, QTY {_MEMBER_QUANTITIES['OuterLink']}"),
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM,
        supplier_dimensions=annotate_chain_stock,
        supplier_margins=SUPPLIER_MARGINS,
        stock_configuration=SUPPLIER_REFERENCE_CONFIGURATION,
        prepare_views=prepare_chain_diagrams,
        include_right=False,
        installed_variants=VARIANTS,
        installed_configuration="InnerLink",
        stock_caption="SUPPLIER FAMILY NOMINAL DIAGRAM — NOT INSTALLED",
        spring_metadata=True,
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
