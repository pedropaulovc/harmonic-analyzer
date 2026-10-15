"""Catalogue-only McMaster 98055A098 DIN 988 shim: annulus Y=0..0.5 nominal.

No supplier CAD was harvested. Pure supplier dimensions are mechanical
inputs; the production functional spec never imports this COM recipe.
"""

import math

from _check import check
from _feature_tree import name_last_feature
from _mcmaster_98055a098 import DIMS, THICKNESS_NOMINAL
from _part_checks import volume_check
from _sketch import ensure_fully_defined
from _sketch_circle import define_circle
from _stock_recipe import stock_recipe
from diagnostics.diag_mcmaster_lib import no_sketch_inference


@stock_recipe("98055A098", threaded=False)
async def build_98055A098(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch shim annulus", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await define_circle(adapter, 0.0, 0.0, DIMS.od / 2, "shim OD")
        await define_circle(adapter, 0.0, 0.0, DIMS.id / 2, "shim ID")
    await ensure_fully_defined(adapter, "shim annulus")
    check("exit_sketch shim annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "ShimProfile")
    check(
        "extrude shim annulus",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS_NOMINAL)),
    )
    name_last_feature(adapter, "ShimBody")
    volume = math.pi / 4 * (DIMS.od**2 - DIMS.id**2) * THICKNESS_NOMINAL
    await volume_check(adapter, "shim annulus", volume, 0.005 * volume)
