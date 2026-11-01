"""Create the purchased reference sheet for MHA-PD-VN-68 transgear cluster shim."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _part_properties import part_drawing_unit
from _session import run_build
from _supplier_washer_drawing import supplier_washer_dimensions
import pd_vn_transgear_cluster_shim_spec as part

# Cached machinist review leaf; ENFORCE once the sheet reaches SHIP.
MACHINIST_REVIEW = MachinistReviewMode.LEARN

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_cluster_shim"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "SHOULDER SHIM"
# The +Y axis faces *Top; *Front is parallel to the thickness witness.
# Reserve the face/side picks plus the supplier limit ink widths.
SUPPLIER_MARGINS = {
    "*Top": (0.0, 0.008, 0.040, 0.008),
    "*Front": (0.0, 0.006, 0.035, 0.006),
}


def _supplier_dimensions(adapter: Any, views: dict[str, Any]) -> Callable[[], None]:
    return supplier_washer_dimensions(
        adapter,
        views,
        axis="y",
        bore_mm=part.ID,
        outer_mm=part.OD,
        thickness_mm=part.THICKNESS,
        units=part.SUPPLIER_UNITS,
        precision=part.DRAWING_REFERENCE_PRECISION,
        bands=part.SUPPLIER_TOLERANCES,
    )


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def dimensions(adapter: Any, views: dict[str, Any]) -> None:
        proofs.append(_supplier_dimensions(adapter, views))

    def assert_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError(
                "supplier washer dimensions must be authored exactly once"
            )
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_dimensions,),
        unit=part_drawing_unit(SPEC.artifact_stem),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
