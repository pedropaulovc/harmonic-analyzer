r"""Reproduction script: column clamp, BACK semi-arc (book ch. 21/22, ch30).

The rear half of the two-piece black collar clamping the platen support bar
to each front column (ch30 p005 quarter view): its relief wraps the column's
back half and its two #8-32 tapped ear holes take the clamp-screw threads (the
screw stack is bar -> front arc -> this shell). Depth 15.5 spans the
column-axis plane (machine z -112) to the back face at z -96.5, a 2.7 back
wall past the Ø25.6 bore; the mating face stops 0.5 short of the column axis
so the clamp grips (user ruling 2026-10-14; sh_column_clamp_back_geom).
Geometry: _clamp_arc.py; layout: memory/paper-drive-rework.md E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sh_column_clamp_back.py
"""

from __future__ import annotations

import sys

from _clamp_arc import build_arc
from _session import run_build
from sh_column_clamp_back_geom import DEPTH, GRIP_OFFSET, HOLE_SPEC

PART_NAME = "sh-column-clamp-back"


async def build(adapter) -> dict[str, str]:
    return await build_arc(
        adapter,
        part_name=PART_NAME,
        depth=DEPTH,
        front=False,
        hole_spec=HOLE_SPEC,
        grip_offset=GRIP_OFFSET,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
