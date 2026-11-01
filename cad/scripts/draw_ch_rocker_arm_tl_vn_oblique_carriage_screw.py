"""Create the purchased reference drawing for the oblique-trammel carriage screw."""

from __future__ import annotations

import argparse
import sys
from functools import partial
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _purchased_title_fit import fit_purchased_title_block
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
import ch_rocker_arm_tl_vn_oblique_carriage_screw_spec as supplier


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_carriage_screw"]
# The footer's ITEM row: the fastener table's callout for the screw.
ITEM = "M4 X 20 SHCS"


async def build(adapter: Any) -> dict[str, str]:
    view_layout = "supplier_top"
    checks = []
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        title_block_setup=partial(
            fit_purchased_title_block, spec=SPEC, material_property="Material"
        ),
        view_layout=view_layout,
        supplier_dimensions=partial(
            annotate_supplier_screw,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
            units=supplier.SUPPLIER_REFERENCE_UNITS,
            settled_checks=checks,
            layout=view_layout,
        ),
        supplier_margins=supplier_screw_margins(
            supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
        ),
        settled_checks=checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
