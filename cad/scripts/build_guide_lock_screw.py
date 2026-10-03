r"""Purchased guide-lock screw: McMaster 91255A108, black oxide.

Ruling R9-31 (2026-09-30): the eight screws that hold the four guide locks
(MHA-112 lock plates) to the platen guides ride the platen, and a brass
fillister head there sweeps into the transgear hanger arm.  They take a
#4-40 button head socket cap screw instead; every other MHA-030 station keeps
the fillister.  Ruling R9-48: 3/8 in under the head, into the guide's
through taps, so the worst case still engages 1.5D
(``guide_lock_screw_spec.ENGAGEMENT_WORST``).

Geometry source: the catalogue, not a vendor model.  The series dimensions
are the McMaster product page for 91255A106 (read in a headless browser on
2026-09-30): #4-40 UNC-3A, fully threaded, button head Ø0.213 in x 0.059 in
high, 1/16 in hex drive, black-oxide alloy steel, ASTM F835.  [INFERENCE]
91255A108 is the same series at 3/8 in; its page is not yet read live.
``diagnostics/diag_build_91255A108.py`` builds it with the 91255A106 recipe;
it has no replica gate, and no McMaster .SLDPRT is committed or used.

Frame: the MHA-030 fillister's, so the paper drive places either the same
way: the recipe's head-up body (axis +Y, bearing face at y = 0) turned -90 deg
about X, putting the bearing face on the origin, the head toward -Z and the
shank along +Z.
"""

from __future__ import annotations

import sys
from math import pi

from _common import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_91255A108 import build_91255A108
from guide_lock_screw_spec import SKU

PART_NAME = "guide-lock-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_91255A108,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
