"""Create the purchased reference drawing for the knob-cup pin.

MHA-VN-048 is pressed through the MHA-PD-016 cup and the MHA-PD-008 journal in a
hole match-drilled through both at assembly.
"""

from __future__ import annotations

from collections.abc import Callable
import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_pin_drawing import SPRING_PIN_SUPPLIER_MARGINS, add_supplier_spring_pin_dimensions
from vn_transgear_knob_cup_pin_spec import SUPPLIER_REFERENCE


SPEC = DRAWINGS_BY_NAME["vn_transgear_knob_cup_pin"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø1/16 x 5/8 SLOTTED SPRING PIN; SLOT NOT SHOWN"


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
        proofs.append(add_supplier_spring_pin_dimensions(adapter, views_by_orientation, SUPPLIER_REFERENCE))

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("transgear knob-cup pin supplier callback must run exactly once")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions,),
        supplier_margins=SPRING_PIN_SUPPLIER_MARGINS,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
