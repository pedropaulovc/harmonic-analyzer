"""Create the purchased reference drawing for the transgear retaining ring (MHA-PD-VN-61, McMaster 97431A240)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _machinist_review_mode import MachinistReviewMode
import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing


# Cached machinist review leaf: LEARN until the sheet reaches SHIP.
MACHINIST_REVIEW = MachinistReviewMode.LEARN

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_retaining_ring"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "E-STYLE EXTERNAL RETAINING RING FOR 1/8 SHAFT"


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        unit=part_drawing_unit("pd-vn-transgear-retaining-ring"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
