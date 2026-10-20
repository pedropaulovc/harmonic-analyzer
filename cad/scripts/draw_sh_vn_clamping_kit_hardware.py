"""Draw the three installed forms from one Precision Matthews clamping kit.

Each explicitly configured member retains its four-view reference content.
The twelve installed members are not twelve procurement units.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_variant_drawing import build_purchased_variant_drawing


SPEC = DRAWINGS_BY_NAME["sh_vn_clamping_kit_hardware"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "52-PIECE CLAMPING KIT, 14 MM T-SLOT, 1/2-13 HARDWARE"
VARIANTS = (
    ("HoldDownStud", "HOLD-DOWN STUD"),
    ("TNut", "T-NUT"),
    ("FlangeNut", "FLANGE NUT"),
)
PURCHASE_UNIT = "52-PIECE KIT"


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_variant_drawing(
        adapter,
        SPEC,
        variants=VARIANTS,
        item=ITEM,
        purchase_unit=PURCHASE_UNIT,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
