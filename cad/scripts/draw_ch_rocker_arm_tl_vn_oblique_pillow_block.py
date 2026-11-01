"""Create the four-view purchased-reference sheet for the AMPEC KP08 pillow block (MHA-CH-06-TL-VN-56).

Identification and its receipt-check reference sizes: the part as installed,
its stock and ordering SKU, and the bolt-hole spacing, bolt hole and overall
length on the plan view; no fabrication dimensions.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _purchased_fastener_drawing import NumberFit
from _purchased_part_drawing import build_purchased_part_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
import ch_rocker_arm_tl_vn_oblique_pillow_block_spec as supplier


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pillow_block"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "KP08 PILLOW BLOCK, 8 MM BORE, SET-SCREW INSERT BEARING"
# The bolt hole's two-line text is wider than its 9 mm span at 2:1; centred
# on its line it would sit across its own witnesses, so it shelves left.
SHELVES = {"SupplierBoltHoleDiameter": (False, "left")}


# The hole's shelved text reaches 26 mm past its 6 mm lane: the lane plan's
# 26 mm left reserve put its ink 5 mm past the Front cell (farm run
# 20261101T115426386Z). 34 mm holds it; the empty right keeps the plan's
# 20 mm, so the 121 mm-wide 2:1 plan view still fits the 180 mm cell. The
# fit centres Front and Top on their shared column, so they stay aligned.
_HOLE_TEXT_ROOM_M = 0.034


def _margins() -> dict[str, tuple[float, float, float, float]]:
    margins = supplier_screw_margins(
        supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
    )
    _left, bottom, right, top = margins["*Front"]
    return {**margins, "*Front": (_HOLE_TEXT_ROOM_M, bottom, right, top)}


SUPPLIER_MARGINS = _margins()


async def build(adapter: Any) -> dict[str, str]:
    proofs = []

    def supplier_dimensions(adapter: Any, views: Any) -> None:
        if proofs:
            raise RuntimeError("supplier reference callback repeated")
        checks = []
        displays = annotate_supplier_screw(
            adapter,
            views,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
            units=supplier.SUPPLIER_REFERENCE_UNITS,
            settled_checks=checks,
        )
        stations = shelve_supplier_text(adapter, displays, SHELVES)
        [settled_references] = checks

        def assert_references() -> None:
            assert_supplier_shelves(adapter, settled_references(), SHELVES, stations)

        proofs.append(assert_references)

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("supplier references omitted or repeated")
        proofs[0]()

    # The 18-character registry number overruns the template's DWG. NO.
    # cell into REV; fit it there, measured.
    return await build_purchased_part_drawing(
        adapter,
        SPEC,
        item=ITEM,
        number_fit=NumberFit.SHRINK_TO_CELL,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
