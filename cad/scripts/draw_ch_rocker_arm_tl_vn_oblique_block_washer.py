"""Create the purchased reference drawing for the oblique-trammel block screw lock washer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _session import run_build
from _supplier_washer_drawing import SupplierWasherProof, supplier_washer_dimensions
import ch_rocker_arm_tl_vn_oblique_block_washer_spec as part

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_block_washer"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#8 WEDGE-LOCK WASHER PAIR, ID 4.32 x OD 7.62"
# Front/Top share outer X bounds, so both need the face's 40 mm right reserve.
# Front's equal bottom/top reserves already align Y with the uninset Right.
SUPPLIER_MARGINS = {
    "*Top": (0.0, 0.008, 0.040, 0.006),
    "*Front": (0.0, 0.008, 0.040, 0.008),
}


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[SupplierWasherProof] = []

    def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> None:
        proofs.append(supplier_washer_dimensions(
            adapter, views, axis="y", bore_mm=part.ID, outer_mm=part.OD,
            thickness_mm=part.THICKNESS, units=part.SUPPLIER_UNITS,
            precision=part.DRAWING_REFERENCE_PRECISION, bands=part.SUPPLIER_TOLERANCES,
            bore_callout=part.SUPPLIER_BORE_CALLOUT,
        ))

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("91812A215 supplier dimensions must be authored exactly once")
        proofs[0]()

    def saved_dimensions(adapter: Any, path: Path) -> None:
        if len(proofs) != 1:
            raise RuntimeError("supplier washer dimensions must be authored exactly once before saved proof")
        saved = proofs[0].saved_check
        proofs.clear()
        saved(adapter, path)

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        number_fit=NumberFit.SHRINK_TO_CELL,
        settled_checks=(assert_supplier_dimensions,),
        saved_check=saved_dimensions,
        supplier_data=part.SUPPLIER_DATA,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
