"""Create the VN-52 purchased drawing, including its receiving-acceptance note."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_bearing"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "6200-2RS BALL BEARING 10 X 30 X 9"


async def build(adapter: Any) -> dict[str, str]:
    # Fit the original registry Number inside DWG. NO., clear of the REV divider.
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, number_fit=NumberFit.SHRINK_TO_CELL
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
