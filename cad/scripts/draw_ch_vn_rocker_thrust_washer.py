"""Create the purchased reference sheet for MHA-CH-VN-56 rocker thrust washer."""

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
import ch_vn_rocker_thrust_washer_spec as part

SPEC = DRAWINGS_BY_NAME["ch_vn_rocker_thrust_washer"]
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
# The final +Z face is Front; Top is parallel to its thickness witness.
# Reserve 12 mm face/14 mm side picks plus supplier band/limit ink widths.
SUPPLIER_MARGINS = {
    "*Front": (0.0, 0.008, 0.040, 0.008),
    "*Top": (0.0, 0.006, 0.035, 0.006),
}


def _supplier_dimensions(
    adapter: Any, views: dict[str, Any]
) -> Callable[[], None]:
    return supplier_washer_dimensions(
        adapter,
        views,
        axis="z",
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
            raise RuntimeError("supplier washer dimensions must be authored exactly once")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item="RING SHIM",
        supplier_dimensions=dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_dimensions,),
        unit=part_drawing_unit("ch-vn-rocker-thrust-washer"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
