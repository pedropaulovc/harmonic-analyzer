"""Create the purchased reference drawing for the transgear arm-plate screw.

All four views show the part's native ``SupplierStock`` configuration (the
full 1 in stock with its factory tip, the installed trim suppressed), so the
supplier drawing's sizes are dimensioned on the solid's own spans; the
footer's cut-to-suit note states the installed cut.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from functools import partial
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from vn_transgear_arm_plate_screw_spec import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_FORMATS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_STOCK_CONFIGURATION,
)


SPEC = DRAWINGS_BY_NAME["vn_transgear_arm_plate_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#8-32 x 1 OVAL HEAD SLOTTED SCREW"


async def build(adapter: Any) -> dict[str, str]:
    # Build-local: the annotation callback appends its settled readback,
    # which the finalizer runs after the drawing's last rebuild.
    settled_checks: list[Callable[[], None]] = []
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        cut_to_suit=True,
        configuration=SUPPLIER_STOCK_CONFIGURATION,
        supplier_margins=supplier_screw_margins(
            SUPPLIER_REFERENCE_DIMENSIONS, planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
        ),
        supplier_dimensions=partial(
            annotate_supplier_screw,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            formats=SUPPLIER_REFERENCE_FORMATS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
            settled_checks=settled_checks,
        ),
        settled_checks=settled_checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
