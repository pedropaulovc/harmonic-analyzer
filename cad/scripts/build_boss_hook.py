"""Build the counter-spring lower anchor from McMaster 9490T1.

The single open routing eyebolt that hangs the master (counter) spring from the
summing lever's summation-anchor boss. It threads DIRECTLY into the #10-24 tap
through that boss (``summing_lever_spec.COUNTER_HOLE_SPEC``, sourced from this
same anchor record) -- no nut, no separate link ring.

The one supplier option this production part takes is LENGTH: the vendor's
58.7375 mm shank is cut back to the boss height it engages (19.05 mm, the
lever's ``ANCHOR_H``) with the 45 deg deburr restored at the new end, so the
thread ends at y -27.84475 and the factory thread phase is preserved.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT and stays in the vendor's own frame -- eye centre at the origin,
eye plane in XY, shank axis along -Y, thread starting at y -8.79475.
``build_summing_assembly`` positions it; nothing here moves it.

Run (SolidWorks already open)::

    uv run python cad\\scripts\\build_boss_hook.py
"""

from __future__ import annotations

import sys

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_9490T1 import build_9490T1
from stock_anchor_geom import ANCHOR_9490T1
from summing_lever_spec import ANCHOR_H

PART_NAME = "boss-hook"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
ANCHOR = ANCHOR_9490T1

# Finished shank length = the tapped boss it threads into, so the thread engages
# the full boss and ends flush with its underside. ONE source: the lever's spec.
# It is a CUT length on a purchased part, so it is quoted the way the shop cuts
# it -- to 0.001 -- rather than as the raw 0.75 in binary float (19.05).
SHANK_LENGTH_MM = round(ANCHOR_H, 3)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                ANCHOR.sku,
                build_9490T1,
                parameters={"shank_length_mm": SHANK_LENGTH_MM},
            ),
        ),
        material=MATERIAL,
        # Shank axis = the vendor -Y axis through the eye centre (Front n Right),
        # the stable mate reference the old sketched part named "shank axis".
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
