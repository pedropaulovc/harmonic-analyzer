"""Huyett headed clevis, catalogue-native, +X from head bearing face x=0."""
from __future__ import annotations

from _bore_axis import name_bore_axis
from _check import check
from _feature_tree import name_last_feature
from _sketch import add_line_chain
from _stock_recipe import stock_recipe
from ch_rocker_arm_tl_oblique_retention_hardware_spec import (
    CLEVIS_DIA, CLEVIS_HEAD_DIA, CLEVIS_HEAD_HEIGHT, CLEVIS_LENGTH,
    CLEVIS_HOLE_DIA, CLEVIS_HOLE_FROM_HEAD,
)
from diagnostics.diag_mcmaster_lib import no_sketch_inference


@stock_recipe("CLPS6-0187-1250D", threaded=False)
async def build_CLPS6_0187_1250D(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("clevis profile", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        check("clevis centreline", await adapter.add_centerline(-CLEVIS_HEAD_HEIGHT, 0, CLEVIS_LENGTH, 0))
        await add_line_chain(adapter, [
            (-CLEVIS_HEAD_HEIGHT, 0),
            (-CLEVIS_HEAD_HEIGHT, CLEVIS_HEAD_DIA / 2),
            (0, CLEVIS_HEAD_DIA / 2),
            (0, CLEVIS_DIA / 2),
            (CLEVIS_LENGTH, CLEVIS_DIA / 2),
            (CLEVIS_LENGTH, 0),
        ])
    check("close clevis profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ClevisProfile")
    check("turn clevis", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "HeadedClevis")
    check("cotter hole sketch", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        check("cotter hole circle", await adapter.add_circle(CLEVIS_HOLE_FROM_HEAD, 0, CLEVIS_HOLE_DIA / 2))
    check("close cotter hole", await adapter.exit_sketch())
    name_last_feature(adapter, "CotterHoleProfile")
    check("drill cotter hole", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=CLEVIS_DIA * 2, both_directions=True)))
    name_last_feature(adapter, "CotterHole")
    await name_bore_axis(adapter, "Right Plane", CLEVIS_HOLE_FROM_HEAD,
                         "Top Plane", 0.0, "clevis cotter hole")
    name_last_feature(adapter, "CotterHoleAxis")
