r"""Reproduction script: column clamp, BACK semi-arc (book ch. 21/22, ch30).

The rear half of the two-piece black collar clamping the platen support bar
to each front column (ch30 p005 quarter view): its relief wraps the column's
back half and its two O4.0 ear holes take the clamp-screw threads (the screw
stack is bar -> front arc -> this shell). Depth 14 spans the column-axis
plane (machine z -112) to z -98, a 1.2 solid back wall past the Ø25.4
column. Geometry: _clamp_arc.py; layout: docs/paper-drive-rework.md E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_column_clamp_back.py
"""

from __future__ import annotations

import sys

from _clamp_arc import build_arc
from _common import run_build

PART_NAME = "column-clamp-back"

DEPTH = 14.0  # column-axis plane to the back face (1.2 wall past the column)
HOLE_DIA = 4.0  # the O3.9 clamp-screw shanks thread in


async def build(adapter) -> dict[str, str]:
    return await build_arc(
        adapter, part_name=PART_NAME, depth=DEPTH, front=False, hole_dia=HOLE_DIA
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
