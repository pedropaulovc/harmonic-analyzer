"""Create the purchased reference drawing for the magnifying-bracket screw."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_fraction import inch_fraction
from _purchased_fastener_drawing import build_purchased_fastener_drawing
import vn_magnifying_bracket_screw_spec as screw


SPEC = DRAWINGS_BY_NAME["vn_magnifying_bracket_screw"]
# The SKU's under-head length as the catalogue's inch fraction (5/16 for
# 91794A078), so a SKU swap cannot leave a stale length in the ITEM row.
LENGTH_IN = inch_fraction(screw.LENGTH, what=f"{screw.SKU} length")
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = f"{screw.THREAD} x {LENGTH_IN} FILLISTER HEAD SLOTTED SCREW"


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
