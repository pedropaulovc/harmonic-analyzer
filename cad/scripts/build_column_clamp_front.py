r"""Reproduction script: column clamp, FRONT semi-arc (book ch. 21/22, ch30).

The bar-side half of the two-piece black collar clamping the platen support
bar to each front column (ch30 p005 quarter view): its front face carries the
bar's back face, its relief wraps the column's front half, and the two O4.4
ear holes pass the clamp screws whose heads show on the bar front (ch30
p002). Depth 17.9 spans bar back (machine z -129.9) to the column-axis plane
(z -112). Geometry: _clamp_arc.py; layout: docs/paper-drive-rework.md E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_column_clamp_front.py
"""

from __future__ import annotations

import sys

from _clamp_arc import build_arc
from _common import run_build

PART_NAME = "column-clamp-front"

DEPTH = 17.9  # bar back face to the column-axis plane
HOLE_DIA = 4.4  # clearance for the O3.9 clamp-screw shanks


async def build(adapter) -> dict[str, str]:
    return await build_arc(
        adapter, part_name=PART_NAME, depth=DEPTH, front=True, hole_dia=HOLE_DIA
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
