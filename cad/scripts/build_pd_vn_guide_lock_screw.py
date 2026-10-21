r"""Purchased guide-lock screw: McMaster 91792A108, 18-8 stainless slotted pan head.

Ruling R9-31 (2026-09-30): the eight screws that hold the four guide locks
(MHA-PD-12 lock plates) to the platen guides ride the platen, and a brass
fillister head there sweeps into the transgear hanger arm.  They take a low
#4-40 head instead; every other MHA-PD-VN-52 station keeps the fillister.
2026-10-11: the low head is slotted, as the book's guide-lock plates show
(ch22 img05: slotted domed heads, dark ferrous, unlike the brass platen-front
screws), not a hex socket.  The 18-8 slotted pan head is the lowest stocked
slotted #4 rounded head (0.068 in; binding 0.068, round 0.086, fillister
0.107); no black-oxide slotted #4 head is stocked, and the 18-8 family is the
repository's stainless slotted-screw stock (91794A, 91790A).  Ruling R9-48:
3/8 in under the head, into the guide's through taps, so the worst case still
engages 1.5D (``pd_vn_guide_lock_screw_spec.ENGAGEMENT_WORST``).

Geometry source: the catalogue, not a vendor model.  The McMaster family
table read live on 2026-10-11 gives #4-40 UNC-2A, fully threaded, flat tip,
pan head Ø0.219 in x 0.068 in high, 18-8 stainless, ASME B18.6.3.
``diagnostics/diag_build_91792A108.py`` builds it with the shared slotted-head
recipe (``diag_mcmaster_fillister``); it has no replica gate, and no McMaster
.SLDPRT is committed or used.

Frame: the MHA-PD-VN-52 fillister's, so the paper drive places either the same
way: the recipe's head-up body (axis +Y, bearing face at y = 0) turned -90 deg
about X, putting the bearing face on the origin, the head toward -Z and the
shank along +Z.
"""

from __future__ import annotations

import sys
from functools import partial
from math import pi

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from _mcmaster_91792a108 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
)
from diagnostics.diag_build_91792A108 import build_91792A108
from pd_vn_guide_lock_screw_spec import SKU

PART_NAME = "pd-vn-guide-lock-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=SKU,
                author=build_91792A108,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
