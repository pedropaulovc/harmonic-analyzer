"""Create the purchased reference drawing for the oblique-trammel hub washer (MHA-CH-06-TL-VN-85, McMaster 90231A116)."""

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
import ch_rocker_arm_tl_vn_oblique_hub_washer_spec as part

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_hub_washer"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#8 SAE FLAT WASHER"
# Sheet-metre reserves: 12 mm face picks plus the supplier diameter ink,
# and a 14 mm Top thickness pick plus its REF ink.
SUPPLIER_MARGINS = {
    "*Front": (0.0, 0.008, 0.040, 0.006),
    "*Top": (0.0, 0.008, 0.035, 0.008),
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
        model_references=part.SUPPLIER_MODEL_REFERENCES,
        bore_callout=part.SUPPLIER_BORE_CALLOUT,
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
        item=ITEM,
        supplier_dimensions=dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_dimensions,),
        supplier_data=part.SUPPLIER_DATA,
        unit=part_drawing_unit("ch-rocker-arm-tl-vn-oblique-hub-washer"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
