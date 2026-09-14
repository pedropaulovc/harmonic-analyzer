"""Build the channel-spring lower anchor from McMaster 9489T111.

Twenty of these routing eyebolts replace the old formed-wire J-hook. Each one
threads DIRECTLY into a #6-32 tap through the summing lever's coefficient plate
(``summing_lever_spec.HOLE_SPEC``, sourced from this same anchor record) and the
channel spring's lower eye links onto its eye. The SUPPLIED HEX NUT IS OMITTED:
the tapped plate is the nut, so the production part is the bolt body alone.

The tracked diagnostic recipe is an exact geometric replay of the supplied
vendor SLDPRT and stays in the vendor's own frame -- eye centre at the origin,
eye plane in XY, shank axis along -Y, threads running from y -9.525 to -25.4.
``build_channel_assembly`` positions it; nothing here moves it.

Run (SolidWorks already open)::

    uv run python cad\\scripts\\build_spring_hook.py
"""

from __future__ import annotations

import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_9489T111 import build_9489T111
from stock_anchor_geom import ANCHOR_9489T111

PART_NAME = "spring-hook"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
ANCHOR = ANCHOR_9489T111

# The one supplier option this production part takes. The vendor ships 9489T111
# with a captive hex nut; the anchor threads straight into the summing lever, so
# the nut is never installed and no nut geometry belongs in the SLDPRT.
NUT = "omitted"


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                ANCHOR.sku,
                build_9489T111,
                parameters={"nut": NUT},
            ),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,  # black-oxide hardware
        # Shank axis = the vendor -Y axis through the eye centre (Front n Right),
        # the stable mate reference the old sketched part named "shank axis".
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
