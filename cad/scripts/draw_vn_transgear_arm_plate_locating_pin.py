"""Purchased reference drawing for MHA-VN-056 McMaster 93600A189."""
from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing

SPEC = DRAWINGS_BY_NAME["vn_transgear_arm_plate_locating_pin"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø2 x 6 DOWEL PIN, ISO 2338 m6"


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem], nargs="?", default=SPEC.artifact_stem)
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
