"""Create the purchased reference drawing for the magnifying-bracket screw."""

from __future__ import annotations

import argparse
from fractions import Fraction
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
import vn_magnifying_bracket_screw_spec as screw


SPEC = DRAWINGS_BY_NAME["vn_magnifying_bracket_screw"]
MM_PER_IN = 25.4
# The SKU's under-head length as the catalogue's inch fraction (5/16 for
# 91794A078), so a SKU swap cannot leave a stale length in the ITEM row.
LENGTH_IN = Fraction(screw.LENGTH / MM_PER_IN).limit_denominator(64)
if abs(float(LENGTH_IN) * MM_PER_IN - screw.LENGTH) > 1e-9:
    raise ValueError(f"{screw.SKU} length {screw.LENGTH} mm is not a 1/64 in fraction")
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
