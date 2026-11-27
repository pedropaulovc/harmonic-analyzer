r"""Purchased MHA-PD-VN-72 feed-rack screw: McMaster 91794A060.

18-8 stainless slotted fillister #0-80 UNF-2A x 1/2, fully threaded,
ASME B18.6.3: four stock screws hold the MHA-PD-26 feed rack to the
MHA-PD-27 bottom guide rail (owner ruling 2026-11-26, #3738;
``pd_feed_rack_screw_spec``). The stock recipe
``diagnostics/diag_build_91794A060.py`` models the head and a plain shank at
the thread major (#2886: no thread, no simplified configuration), in its
stock frame (head +Y, shank -Y, under-head plane Y=0).

Run (SolidWorks open)::

    uv run python cad\scripts\build_pd_vn_feed_rack_screw.py
"""

from __future__ import annotations

import sys

from _fastener_catalog import fastener
from _session import run_build
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91794A060 import build_91794A060
from pd_feed_rack_screw_spec import SKU

PART_NAME = "pd-vn-feed-rack-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


def build(adapter) -> dict[str, str]:
    return build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_91794A060, transform=RigidTransform()),
        ),
        screw_axis_planes=("Front Plane", "Right Plane"),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
