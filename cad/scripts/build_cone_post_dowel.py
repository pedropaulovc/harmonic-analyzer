r"""Purchased cone pivot post dowel pin: McMaster 98381A304, black oxide (MHA-151).

#917 S1: two 1/8 x 1/2 in alloy steel dowel pins locate the cone pivot post
(MHA-016) on the swing platform (MHA-091) -- pressed through the platform's
reams, a slip fit in the post's blind reams (``cone_post_dowel_spec``).  The
recipe replays the vendor file's section (see
diagnostics/diag_build_98381A304.py); the vendor SLDPRT itself is never read
by the production build.
"""

from __future__ import annotations

import sys

from _common import PANEL_BLACK, run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_98381A304 import PIN_END_Y as _RECIPE_PIN_END_Y
from diagnostics.diag_build_98381A304 import build_98381A304

PART_NAME = "cone-post-dowel"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
# The recipe is placed untransformed (RigidTransform()), so the part's pin
# ends are the recipe's: symmetric about the Top Plane, which the drive-train
# seats the pin by.
TRANSFORM = RigidTransform()
PIN_END_Y = _RECIPE_PIN_END_Y


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku="98381A304",
                author=build_98381A304,
                transform=TRANSFORM,
            ),
        ),
        material=MATERIAL,
        color=PANEL_BLACK,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
