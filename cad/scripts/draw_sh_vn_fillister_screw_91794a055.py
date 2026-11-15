"""Purchase drawing for MHA-SH-VN-59, McMaster 91794A055 #0-80 x 1/4 fillisters.

One SKU in two installed members (``sh_vn_fillister_screw_91794a055_spec``).
Every view shows ``RackScrew``, the screw as supplied, so the catalogue's
references print on it, its 1/4 stock length included.  ``DiscScrew`` is the
same screw with its tip cut at assembly (MHA-PD-00's step prints the window
under the disc's rear face): the general line points to that step and the
sheet draws no cut.  Both quantities are the paper-drive BOM's.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _mcmaster_91794a055 as supplier
import _telemetry
import sh_vn_fillister_screw_91794a055_spec as shared
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["sh_vn_fillister_screw_91794a055"]
PART_STEM = SPEC.artifact_stem
# The views' member: the screw as supplied.
CONFIGURATION = shared.DRAWING_CONFIGURATION
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#0-80 x 1/4 FILLISTER HEAD SLOTTED SCREW"
# The disc screws' tip cut is assembly work (MHA-PD-00 step
# "disc-screws-cut"): the part sheet only points to it. The step number is a
# literal so a renumbered MHA-PD-00 does not re-key this sheet;
# test_sh_vn_fillister_screw_91794a055_drawing pins it to the key.
CUT_STEP = 16
# The stock-length witness stands left of the screw (its start is -HEAD_DIA),
# so its dimension and AS-SUPPLIED STOCK LENGTH print there, clear of the
# shank; the head height takes the right (machinist review, r3).
SIDES = {
    **supplier.SUPPLIER_REFERENCE_SIDES,
    "SupplierStockLength": "left",
    "SupplierHeadHeight": "right",
}
GENERAL_TEXT = (
    f"PURCHASED PART, VIEWS AS SUPPLIED. DISC SCREWS CUT PER MHA-PD-00 STEP {CUT_STEP}."
)


async def build(adapter: Any) -> dict[str, str]:
    supplier_checks = []
    callback_count = 0
    settled = False

    def supplier_dimensions(adapter, views_by_orientation):
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("supplier dimensions callback must run exactly once")
        annotate_supplier_screw(
            adapter,
            views_by_orientation,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=SIDES,
            settled_checks=supplier_checks,
        )

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if settled or callback_count != 1 or len(supplier_checks) != 1:
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        supplier_checks[0]()
        settled = True

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, general_text=GENERAL_TEXT,
        supplier_margins=supplier_screw_margins(
            supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=SIDES,
        ),
        supplier_dimensions=supplier_dimensions,
        configuration=CONFIGURATION,
        settled_checks=(assert_supplier_dimensions_settled,),
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
