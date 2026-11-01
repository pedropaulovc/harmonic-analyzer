"""Native supplier stock/application diagrams for connecting link 6261K108.

The installed clipless clearance stand-in remains unchanged and undimensioned.
All nominal source sizes belong to a zero-body construction reference state.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_chain_dimensions import (
    SOURCE_FEATURES,
    SUPPLIER_MARGINS,
    annotate_chain_stock,
    prepare_chain_diagrams,
)
from _supplier_chain_stock import SUPPLIER_REFERENCE_CONFIGURATION
from _supplier_spring_drawing import build_supplier_spring_drawing


SPEC = DRAWINGS_BY_NAME["pd_vn_chain_connecting_link"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "ANSI #25 ROLLER CHAIN, CONNECTING LINK"


def _supplier_dimensions(
    adapter: Any,
    views: dict[str, Any],
    *,
    reference_bounds: Callable[[str], tuple[float, float, float, float]],
) -> tuple[Callable[[], None], ...]:
    return annotate_chain_stock(
        adapter,
        views,
        reference_bounds=reference_bounds,
        connecting=True,
    )


async def build(adapter: Any) -> dict[str, str]:
    return await build_supplier_spring_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=_supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        stock_configuration=SUPPLIER_REFERENCE_CONFIGURATION,
        prepare_views=prepare_chain_diagrams,
        supplier_reference_features=SOURCE_FEATURES,
        include_right=False,
        stock_caption="SUPPLIER NOMINAL / APPLICATION DIAGRAM — NOT INSTALLED",
        spring_metadata=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
