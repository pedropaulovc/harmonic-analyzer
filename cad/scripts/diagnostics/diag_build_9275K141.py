r"""Replay McMaster 9275K141's harvested revolved cap section.

Native Sketch2 supplies the straight wall, roof corner arcs and concentric
mouth-flare arcs. Its two adjoining outer flare arcs produce one toroidal
face, reproduced here as one arc. No vendor solid is imported.

    uv run python cad\scripts\diagnostics\diag_build_9275K141.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import add_line_chain, check, name_last_feature  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference, replica_main  # noqa: E402
from tube_frame_cap_spec import (  # noqa: E402
    FLARE_CENTER_RADIUS,
    FLARE_HEIGHT,
    FLARE_INNER_RADIUS,
    FLARE_OUTER_RADIUS,
    INNER_CORNER_R,
    INNER_DIAMETER,
    INSIDE_HEIGHT,
    MAX_OUTER_DIAMETER,
    MOUTH_INNER_DIAMETER,
    OUTER_CORNER_R,
    OUTER_DIAMETER,
    TOP_FLAT_RADIUS,
    TOTAL_HEIGHT,
)


async def build_9275K141(adapter, truth=None):
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create cap section", await adapter.create_sketch("Front"))
    sketch = adapter.currentSketchManager

    def arc(start, end, center, radius):
        a = math.atan2(start[1] - center[1], start[0] - center[0])
        b = math.atan2(end[1] - center[1], end[0] - center[0])
        sweep = (b - a + math.pi) % (2.0 * math.pi) - math.pi
        mid = a + sweep / 2.0
        if (
            sketch.Create3PointArc(
                start[0] / 1000.0,
                start[1] / 1000.0,
                0.0,
                end[0] / 1000.0,
                end[1] / 1000.0,
                0.0,
                (center[0] + radius * math.cos(mid)) / 1000.0,
                (center[1] + radius * math.sin(mid)) / 1000.0,
                0.0,
            )
            is None
        ):
            raise RuntimeError("9275K141: section arc failed")

    inner_r = INNER_DIAMETER / 2.0
    outer_r = OUTER_DIAMETER / 2.0
    corner_y = INSIDE_HEIGHT - INNER_CORNER_R
    corner = (TOP_FLAT_RADIUS, corner_y)
    flare = (FLARE_CENTER_RADIUS, FLARE_HEIGHT)
    with no_sketch_inference(adapter):
        if (
            sketch.CreateCenterLine(
                0.0, -0.001, 0.0, 0.0, (TOTAL_HEIGHT + 1.0) / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError("9275K141: revolve axis failed")
        arc(
            (TOP_FLAT_RADIUS, INSIDE_HEIGHT),
            (inner_r, corner_y),
            corner,
            INNER_CORNER_R,
        )
        arc(
            (inner_r, FLARE_HEIGHT),
            (MOUTH_INNER_DIAMETER / 2.0, 0.0),
            flare,
            FLARE_INNER_RADIUS,
        )
        arc(
            (MAX_OUTER_DIAMETER / 2.0, 0.0),
            (outer_r, FLARE_HEIGHT),
            flare,
            FLARE_OUTER_RADIUS,
        )
        arc(
            (outer_r, corner_y), (TOP_FLAT_RADIUS, TOTAL_HEIGHT), corner, OUTER_CORNER_R
        )
        # Arc endpoints first, then direct-DB lines, matching the proven
        # fillister recipe. Raw CreateLine with inference off left duplicate
        # unmerged endpoint objects in the failed native CapSection harvest.
        await add_line_chain(
            adapter,
            [
                (TOP_FLAT_RADIUS, TOTAL_HEIGHT),
                (0.0, TOTAL_HEIGHT),
                (0.0, INSIDE_HEIGHT),
                (TOP_FLAT_RADIUS, INSIDE_HEIGHT),
            ],
            close=False,
        )
        await add_line_chain(
            adapter,
            [
                (inner_r, corner_y),
                (inner_r, FLARE_HEIGHT),
            ],
            close=False,
        )
        await add_line_chain(
            adapter,
            [
                (MOUTH_INNER_DIAMETER / 2.0, 0.0),
                (MAX_OUTER_DIAMETER / 2.0, 0.0),
            ],
            close=False,
        )
        await add_line_chain(
            adapter,
            [
                (outer_r, FLARE_HEIGHT),
                (outer_r, corner_y),
            ],
            close=False,
        )
    check("exit cap section", await adapter.exit_sketch())
    name_last_feature(adapter, "CapSection")
    check(
        "revolve cap",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "CapRevolve")
    adapter._mcm_com_map = lambda v: [v[0], v[1] + INSIDE_HEIGHT / 2.0, v[2]]


if __name__ == "__main__":
    sys.exit(replica_main("9275K141", build_9275K141))
