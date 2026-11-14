"""Create the purchased reference drawing for the MHA-DT-12-TL-VN-53 cam fixture clamp washer."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
import dt_cylinder_gear_tl_vn_cam_clamp_washer_spec as part
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_washer_drawing import supplier_washer_dimensions

SPEC = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_vn_cam_clamp_washer"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "NO. 10 FLAT WASHER, ID .203 X OD .438"
SUPPLIER_MARGINS = {
    "*Top": (0.0, 0.008, 0.040, 0.006),
    "*Front": (0.0, 0.008, 0.035, 0.008),
}


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views: dict[str, Any]) -> None:
        proofs.append(
            supplier_washer_dimensions(
                adapter,
                views,
                axis="y",
                bore_mm=part.ID,
                outer_mm=part.OD,
                thickness_mm=part.THICKNESS,
                units=part.SUPPLIER_UNITS,
                precision=part.DRAWING_REFERENCE_PRECISION,
                model_references=part.SUPPLIER_MODEL_REFERENCES,
                bore_callout=part.SUPPLIER_BORE_CALLOUT,
            )
        )

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError(
                "92141A011 supplier dimensions must be authored exactly once"
            )
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_supplier_dimensions,),
        supplier_data=part.SUPPLIER_DATA,
        unit=part_drawing_unit("dt-cylinder-gear-tl-vn-cam-clamp-washer"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
