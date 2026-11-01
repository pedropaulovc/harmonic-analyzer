"""Create the purchased reference drawing for the oblique-trammel feed lever screw lock washer."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_washer_drawing import supplier_washer_dimensions
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as part

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_lever_washer"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "5/16 WEDGE-LOCK WASHER PAIR, ID .34 X OD .53"
SUPPLIER_MARGINS = {
    "*Top": (0.0, 0.008, 0.040, 0.006),
    "*Front": (0.0, 0.008, 0.035, 0.008),
}


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> None:
        proofs.append(supplier_washer_dimensions(
            adapter, views, axis="y", bore_mm=part.ID, outer_mm=part.OD,
            thickness_mm=part.THICKNESS, units=part.SUPPLIER_UNITS,
            precision=part.DRAWING_REFERENCE_PRECISION, bands=part.SUPPLIER_TOLERANCES,
            bore_callout=part.SUPPLIER_BORE_CALLOUT,
        ))

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("91812A230 supplier dimensions must be authored exactly once")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,),
        supplier_data=part.SUPPLIER_DATA,
        unit=part_drawing_unit("ch-rocker-arm-tl-vn-oblique-lever-washer"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
