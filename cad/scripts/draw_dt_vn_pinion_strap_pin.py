"""Create the purchased reference drawing for the pinion strap spring pin."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from collections.abc import Callable

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_pin_drawing import SPRING_PIN_SUPPLIER_MARGINS, add_supplier_spring_pin_dimensions
from dt_vn_pinion_strap_pin_spec import SUPPLIER_REFERENCE


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["dt_vn_pinion_strap_pin"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø1/16 x 1/2 SLOTTED SPRING PIN; SLOT NOT SHOWN"


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
        proofs.append(add_supplier_spring_pin_dimensions(adapter, views_by_orientation, SUPPLIER_REFERENCE))

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("pinion strap pin supplier callback must run exactly once")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions,),
        supplier_margins=SPRING_PIN_SUPPLIER_MARGINS,
        unit=part_drawing_unit("dt-vn-pinion-strap-pin"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
