"""Create the four-view purchased-reference sheet for McMaster-Carr 3606T118, brass bead chain.

Identification only: the part as installed, its stock and ordering SKU, and
its cut-length or fitting note; no fabrication dimensions.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_part_drawing import build_purchased_part_drawing


SPEC = DRAWINGS_BY_NAME["keeper_chain"]
PART_STEM = SPEC.artifact_stem


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_part_drawing(adapter, SPEC)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
