r"""Purchased MHA-CH-13-TL-VN-50 edge clamp: Mitee-Bite Pitbull 26000 with its screw.

One installed part of two bodies, the clamp and the #4-40 x 3/8 socket head
cap screw it is supplied with (``ch_rocker_strap_tl_vn_edge_clamp_spec``);
four hold the strap blank's edge on MHA-CH-13-TL-01. The stock recipe
``diagnostics/diag_build_26000.py`` authors both bodies in the part frame,
so no transform applies: the screw axis is part Z (published as
``ScrewAxis``, Top ∩ Right, the stock-part mate contract), z = 0 the heel
line, the knife toward +Y.

Before the single save, the catalogue sizes the specification-control sheet
prints (A, B, C, D, F and the 4-40 major) are authored as hidden
construction references in the final frame (``_supplier_screw_reference``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_strap_tl_vn_edge_clamp.py
"""

from __future__ import annotations

import sys

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_26000 import build_26000
from _part_save import save_part_and_images
from _supplier_screw_reference import add_supplier_reference_sketch
from ch_rocker_strap_tl_vn_edge_clamp_spec import (
    PART_NAME as SPEC_PART_NAME,
    SKU,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
)

PART_NAME = "ch-rocker-strap-tl-vn-edge-clamp"
if PART_NAME != SPEC_PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


def _save_supplier_part(adapter, part_name) -> dict[str, str]:
    # Construction only, authored in the final frame before saving.
    add_supplier_reference_sketch(
        adapter,
        SUPPLIER_REFERENCE_DIMENSIONS,
        starts=SUPPLIER_REFERENCE_STARTS,
        planes=SUPPLIER_REFERENCE_PLANES,
    )
    return save_part_and_images(adapter, part_name)


def build(adapter) -> dict[str, str]:
    return build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=build_26000),),
        material=MATERIAL,
        screw_axis_planes=("Top Plane", "Right Plane"),
        save_unthreaded_part=_save_supplier_part,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
