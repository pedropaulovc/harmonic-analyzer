r"""Purchased MHA-CH-13-TL-VN-51 hub screw: McMaster 91255A267.

A black-oxide alloy steel 10-32 x 5/8 button head hex drive screw
(``_mcmaster_91255a267``; owner ruling 2026-11-23: "change the screw to
#10-32", reversing 2026-11-17's "Use a 1/4-20 hub screw") through the hub
washer (MHA-CH-13-TL-VN-52) and the strap blank's hub into the sub-plate's
tapped hole (MHA-CH-13-TL-01); it only snugs the strap during the outline.
Tier 1: HARDWARE.md carries it, no drawing. The stock recipe
``diagnostics/diag_build_91255A267.py`` models the head and a plain shank
at the thread major.

Frame: the recipe is built about +Y and turned so its axis is +Z: z = 0 the
head's bearing face, the head toward +Z, the shank toward -Z. The axis is
published as ``ScrewAxis`` (Top ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_strap_tl_vn_hub_screw.py
"""

from __future__ import annotations

import math
import sys

from _session import run_build
from _fastener_catalog import fastener
from _mcmaster_91255a267 import SKU
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91255A267 import build_91255A267

PART_NAME = "ch-rocker-strap-tl-vn-hub-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

# Rx(+90 deg) takes the recipe's +Y axis to +Z; the bearing face (y = 0)
# stays on z = 0.
TRANSFORM = RigidTransform(rotation_radians=(math.pi / 2.0, 0.0, 0.0))


def build(adapter) -> dict[str, str]:
    return build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_91255A267, transform=TRANSFORM),
        ),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
