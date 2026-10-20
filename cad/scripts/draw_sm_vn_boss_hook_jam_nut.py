"""Create the purchased reference drawing for the counter-anchor jam nut (MHA-SM-VN-55, McMaster 90760A140)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing


SPEC = DRAWINGS_BY_NAME["sm_vn_boss_hook_jam_nut"]


async def build(adapter: Any) -> dict[str, str]:
    # Every purchased view is hidden-lines-removed (rule 9), which also clears
    # the dashed bore the r6/r7 reviews flagged in the TOP/RIGHT views.
    return await build_purchased_fastener_drawing(adapter, SPEC)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
