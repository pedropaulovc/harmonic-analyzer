"""Create the purchased reference drawing for the platen-clip screw (MHA-VN-059, McMaster 92446A077)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing


SPEC = DRAWINGS_BY_NAME["vn_platen_clip_screw"]


async def build(adapter: Any) -> dict[str, str]:
    # The far-side slot and thread circle only clutter the 5:1 end view; the
    # other views show the head and thread in solid lines (r3 review).
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
