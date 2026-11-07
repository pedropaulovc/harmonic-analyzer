"""Create the purchased reference drawing for the knob-cup pin.

MHA-PD-VN-62 is pressed through the MHA-PD-16 cup and the MHA-PD-08 journal in a
hole match-drilled through both at assembly. MHA-PD-00's knob-stack step
specifies that hole, so this sheet prints no supplier application hole
(``SHEET_REFERENCE``): the loose circle and its 'MATING HOLE' callout named no
part and read as a second pin feature (machinist review, fan-out 2026-11-07).
The part keeps its catalogue hole sketch, which this sheet neither shows nor
dimensions.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from typing import Any
from collections.abc import Callable

from _machinist_review_mode import MachinistReviewMode
import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_pin_drawing import SPRING_PIN_SUPPLIER_MARGINS, add_supplier_spring_pin_dimensions
from pd_vn_transgear_knob_cup_pin_spec import SUPPLIER_REFERENCE

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_knob_cup_pin"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø1/16 x 5/8 SLOTTED SPRING PIN; SLOT NOT SHOWN"
# The drawing's view of the supplier reference: no application hole.
SHEET_REFERENCE = replace(
    SUPPLIER_REFERENCE, application_hole_limits=None, application_hole_precision=None
)


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
        proofs.append(add_supplier_spring_pin_dimensions(adapter, views_by_orientation, SHEET_REFERENCE))

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("knob-cup pin supplier callback must run exactly once")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions,),
        supplier_margins=SPRING_PIN_SUPPLIER_MARGINS,
        unit=part_drawing_unit(SPEC.artifact_stem),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
