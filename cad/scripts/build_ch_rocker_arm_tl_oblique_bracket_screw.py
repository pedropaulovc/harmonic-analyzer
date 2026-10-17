r"""Purchased MHA-CH-006-TL-42 oblique-trammel end bracket screw: McMaster 91251A196.

The ``#8-32 X 5/8 SHCS`` (``ch_rocker_arm_tl_oblique_bracket_screw_spec``) that holds a TL-28 end bracket to the TL-20 base bar, up from the bar's underside into the bracket, tapped THRU.
The stock recipe ``diagnostics/diag_build_91251A196.py`` builds the catalogue screw on
the 91251A family recipe (``diag_mcmaster_socket_head.build_socket_head``);
the recipe's standalone run is catalog-only (no replica gate, user ruling
2026-10-17).

Frame: screw axis +Y, head up, the bearing face (head underside) at y = 0,
the tip at y = -length.  The axis is published as ``ScrewAxis``
(Front ∩ Right), the stock-part mate contract.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_bracket_screw.py
"""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _simplified_part import save_simplified_part
from ch_rocker_arm_tl_oblique_bracket_screw_spec import SKU
from diagnostics.diag_build_91251A196 import build_91251A196

PART_NAME = "ch-rocker-arm-tl-oblique-bracket-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_91251A196),),
        material=MATERIAL,
        save_threaded_part=save_simplified_part,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
