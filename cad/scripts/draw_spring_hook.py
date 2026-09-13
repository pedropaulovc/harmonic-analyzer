"""Create the purchased reference drawing for the channel-spring lower anchor.

The anchor is McMaster 9489T111 ordered by SKU, so the sheet identifies it and
carries no fabrication dimensions. The supplied-nut omission and the
direct-into-the-lever threading ride the title block's Stock Name and Finish
cells, which the shared purchased-fastener helper links and verifies.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_spring_hook.py spring-hook
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing


SPEC = DRAWINGS_BY_NAME["spring_hook"]


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
