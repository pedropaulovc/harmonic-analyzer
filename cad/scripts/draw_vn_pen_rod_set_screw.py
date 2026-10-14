"""Create the purchased reference drawing for the pen-rod set screw (MHA-VN-061, McMaster 91385A105)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing


SPEC = DRAWINGS_BY_NAME["vn_pen_rod_set_screw"]


async def build(adapter: Any) -> dict[str, str]:
    # The vn-fulcrum-set-screw ruling (machinist review r8): thread and socket
    # hidden edges order and install nothing; the SKU defines the part.
    return await build_purchased_fastener_drawing(
        adapter, SPEC, hidden_lines_removed=True
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
