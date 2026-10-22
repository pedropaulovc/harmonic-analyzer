"""Create the four-view purchased-reference sheet for ZYLtech HW-SC-T8x2-NUT, Tr8x2 brass flange nut.

Identification and supplier-native nominal size references, with its stock,
ordering SKU and fitting note; no fabrication controls.
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_part_drawing import build_purchased_part_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as supplier


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_leadscrew_nut"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "TR8X2 BRASS FLANGE NUT"


async def build(adapter: Any) -> dict[str, str]:
    checks = []
    return await build_purchased_part_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=partial(
            annotate_supplier_screw,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
            units=supplier.SUPPLIER_REFERENCE_UNITS,
            settled_checks=checks,
        ),
        supplier_margins=supplier_screw_margins(
            supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
        ),
        supplier_data=("SOURCE NOMINALS; INTERNAL THREAD NOT MODELLED.",),
        settled_checks=checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
