"""Create the purchased reference drawing for the transgear collar flat pin.

The sheet documents the catalogue pin: its views reference the part's
``AS SUPPLIED STOCK`` configuration, not the faced one the assembly places.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any
from collections.abc import Callable

from _machinist_review_mode import MachinistReviewMode
import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _rebuild import active_configuration_name
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_pin_drawing import DOWEL_SUPPLIER_MARGINS, add_supplier_dowel_dimensions
from pd_vn_transgear_collar_flat_pin_spec import (
    SUPPLIER_REFERENCE,
    SUPPLIER_STOCK_CONFIGURATION,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_collar_flat_pin"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø1/16 x 3/16 DOWEL PIN"


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
        # The supplier witnesses are read from the part's named sketches and
        # mapped into the views, so the part must be in the configuration the
        # views show; it is saved in the faced one the assembly places.
        model = views_by_orientation["*Top"].ReferencedDocument
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            if model.ShowConfiguration2(SUPPLIER_STOCK_CONFIGURATION) is not True:
                raise RuntimeError(
                    "collar flat pin: AS SUPPLIED STOCK did not activate"
                )
        if active_configuration_name(adapter, model) != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError(
                "collar flat pin: AS SUPPLIED STOCK is not the active source"
            )
        proofs.append(
            add_supplier_dowel_dimensions(
                adapter, views_by_orientation, SUPPLIER_REFERENCE
            )
        )

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError(
                "collar flat pin supplier callback must run exactly once"
            )
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions,),
        supplier_margins=DOWEL_SUPPLIER_MARGINS,
        configuration=SUPPLIER_STOCK_CONFIGURATION,
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
