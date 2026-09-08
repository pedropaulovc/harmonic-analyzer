"""Create the purchased reference drawing for the lag screw."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing


SPEC = DRAWINGS_BY_NAME["lag_screw"]


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_fastener_drawing(adapter, SPEC)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
