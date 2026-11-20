r"""Purchased MHA-PD-VN-71 knob-cup screw: McMaster 91794A079.

The passivated 18-8 stainless stock screw retains its frame: head +Y, shank -Y,
junction at Y=0, ``ScrewAxis`` = Front ∩ Right.  The paper-drive assembly
seats its under-head plane on the MHA-PD-16 cup web's rear face, its shank
forward through the web into the MHA-PD-08 journal's rear tap
(``pd_vn_transgear_knob_cup_screw_spec``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_vn_transgear_knob_cup_screw.py
"""

from __future__ import annotations

import sys
from functools import partial

from _appearance import POLISHED_STEEL
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from _mcmaster_91794a079 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
)
from diagnostics.diag_build_91794A079 import build_91794A079
from pd_vn_transgear_knob_cup_screw_spec import SKU

PART_NAME = "pd-vn-transgear-knob-cup-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


def build(adapter) -> dict[str, str]:
    return build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(sku=SKU, author=build_91794A079, transform=RigidTransform()),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
        color=POLISHED_STEEL,
        screw_axis_planes=("Front Plane", "Right Plane"),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
