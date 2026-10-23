"""Catalogue NAS1352N5H12 with six real radial safety-wire openings.

The existing threaded socket-head recipe authors +Y; the production wrapper
rotates its solids +90 degrees about X to publish the installed +Z frame.
"""
from __future__ import annotations

from _pivot_retention_stock_geometry import circular_sweep
from _stock_recipe import stock_recipe
from ch_rocker_arm_tl_oblique_retention_hardware_spec import SCREW_DIMS, SCREW_WIRE_HOLE_DIA
from ch_rocker_arm_tl_vn_oblique_pivot_cap_screw_spec import drilled_head_segments
from diagnostics.diag_mcmaster_socket_head import build_socket_head


@stock_recipe("NAS1352N5H12", threaded=True)
async def build_NAS1352N5H12(adapter, truth=None):
    await build_socket_head(adapter, SCREW_DIMS)
    # Three diametral drills produce six radial openings, 60 degrees apart.
    for index, segment in enumerate(drilled_head_segments(), start=1):
        circular_sweep(
            adapter,
            (segment,),
            SCREW_WIRE_HOLE_DIA,
            f"SafetyWireDrill{index}",
            cut=True,
        )
