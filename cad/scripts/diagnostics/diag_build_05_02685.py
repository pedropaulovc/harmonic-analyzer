"""Aircraft Spruce .032 stainless wire: one formed length per screw X pair."""
from __future__ import annotations

from _pivot_retention_stock_geometry import circular_sweep
from _stock_recipe import stock_recipe
from ch_rocker_arm_tl_vn_oblique_pivot_lock_wire_spec import WIRE_DIA, installed_wire_segments


@stock_recipe("05-02685", threaded=False)
async def build_05_02685(adapter, truth=None):
    circular_sweep(adapter, installed_wire_segments(), WIRE_DIA, "PairedLockWire")
