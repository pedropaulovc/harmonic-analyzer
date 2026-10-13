"""Catalogue-only McMaster 96659A104 annulus: Y=0..midpoint thickness.

No supplier CAD was harvested. Pure supplier dimensions are mechanical
inputs; the production functional spec never imports this COM recipe.
"""

import math

from _check import check
from _feature_tree import name_last_feature
from _mcmaster_96659a104 import DIMS
from _part_checks import volume_check
from _sketch import ensure_fully_defined
from _sketch_circle import define_circle
from _stock_recipe import stock_recipe
from diagnostics.diag_mcmaster_lib import no_sketch_inference


@stock_recipe("96659A104", threaded=False)
async def build_96659A104(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch washer annulus", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await define_circle(adapter, 0.0, 0.0, DIMS.od / 2, "washer OD")
        await define_circle(adapter, 0.0, 0.0, DIMS.id / 2, "washer ID")
    await ensure_fully_defined(adapter, "washer annulus")
    check("exit_sketch washer annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    check(
        "extrude washer annulus",
        await adapter.create_extrusion(ExtrusionParameters(depth=DIMS.thickness)),
    )
    name_last_feature(adapter, "WasherBody")
    volume = math.pi / 4 * (DIMS.od**2 - DIMS.id**2) * DIMS.thickness
    await volume_check(adapter, "washer annulus", volume, 0.005 * volume)
