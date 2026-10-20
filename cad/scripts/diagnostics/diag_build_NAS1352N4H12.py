"""Catalogue NAS1352N4H12 with six real radial safety-wire openings.

The existing threaded socket-head recipe authors +Y; the production wrapper
rotates its solids +90 degrees about X to publish the installed +Z frame.
"""
from __future__ import annotations

import math

from _pivot_retention_stock_geometry import circular_sweep, line_bezier
from _stock_recipe import stock_recipe
from ch_rocker_arm_tl_oblique_retention_hardware_spec import (
    SCREW_DIMS, SCREW_WIRE_HEIGHT, SCREW_WIRE_HOLE_DIA,
)
from diagnostics.diag_mcmaster_socket_head import build_socket_head


@stock_recipe("NAS1352N4H12", threaded=True)
async def build_NAS1352N4H12(adapter, truth=None):
    await build_socket_head(adapter, SCREW_DIMS)
    # Three diametral drills produce six radial openings, 60 degrees apart.
    for index, angle in enumerate((0.0, 60.0, 120.0)):
        theta = math.radians(angle)
        x = SCREW_DIMS.head_dia * math.cos(theta)
        z = -SCREW_DIMS.head_dia * math.sin(theta)
        circular_sweep(
            adapter,
            (line_bezier((-x, SCREW_WIRE_HEIGHT, -z),
                         (x, SCREW_WIRE_HEIGHT, z)),),
            SCREW_WIRE_HOLE_DIA,
            f"SafetyWireDrill{index + 1}",
            cut=True,
        )
