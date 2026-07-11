r"""Reproduction script: column clamp, BACK semi-arc (book ch. 21/22, ch30).

The rear half of the two-piece black collar clamping the platen support bar
to each front column (ch30 p005 quarter view): its relief wraps the column's
back half and its two O4.0 ear holes take the clamp-screw threads (the screw
stack is bar -> front arc -> this shell). Depth 14 spans the column-axis
plane (machine z -112) to z -98, a 1.2 solid back wall past the Ø25.4
column. Geometry: _clamp_arc.py; layout: memory/paper-drive-rework.md E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_column_clamp_back.py
"""

from __future__ import annotations

import sys

from _clamp_arc import build_arc
from _common import run_build
from _holes import HoleSpec

PART_NAME = "column-clamp-back"

DEPTH = 14.0  # column-axis plane to the back face (1.2 wall past the column)
# The O3.9 clamp-screw shanks THREAD IN here (back arc = last in the stack):
# tapped #8-32 (nearest UNC to the ~Ø4 screw; memory/fastener-policy-us-customary).
HOLE_SPEC = HoleSpec("tapped", "#8-32")


async def build(adapter) -> dict[str, str]:
    return await build_arc(
        adapter, part_name=PART_NAME, depth=DEPTH, front=False, hole_spec=HOLE_SPEC
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
