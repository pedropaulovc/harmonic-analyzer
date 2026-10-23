"""Huyett CP-062-0500 installed split-cotter envelope, eye and two spread prongs.

Authored +Y in Front, extrusion +Z. Wrapper rotates to +Z and centres width.
The flattened prongs occupy the catalogue bounding width, not round wire.
"""
from __future__ import annotations

from _check import check
from _feature_tree import name_last_feature
from _sketch import add_line_chain
from _stock_recipe import stock_recipe
import ch_rocker_arm_tl_vn_oblique_pivot_cotter_spec as spec
from diagnostics.diag_mcmaster_lib import no_sketch_inference


@stock_recipe("CP-062-0500", threaded=False)
async def build_CP_062_0500(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("cotter eye sketch", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        for radius in (spec.EYE_OUTER_RADIUS, spec.EYE_INNER_RADIUS):
            check("eye circle", await adapter.add_circle(0, spec.EYE_CENTER, radius))
    check("close eye", await adapter.exit_sketch())
    name_last_feature(adapter, "CotterEyeProfile")
    check("cotter eye", await adapter.create_extrusion(ExtrusionParameters(depth=spec.COTTER_WIDTH)))
    name_last_feature(adapter, "CotterEye")
    for side, tail, label in ((1, spec.LONG_TAIL, "Long"), (-1, spec.SHORT_TAIL, "Short")):
        inner = spec.PRONG_GAP / 2
        outer = inner + spec.PRONG_THICK
        start = spec.PRONG_START
        bend = spec.PRONG_BEND
        # The neck overlaps the eye's upper rim; the gap remains real.
        outline = [(inner, start), (outer, start), (outer, bend),
                   (outer + tail, bend), (outer + tail, bend + spec.PRONG_THICK),
                   (inner, bend + spec.PRONG_THICK)]
        check(f"{label} prong sketch", await adapter.create_sketch("Front"))
        with no_sketch_inference(adapter):
            await add_line_chain(adapter, [(side * x, y) for x, y in outline])
        check(f"close {label} prong", await adapter.exit_sketch())
        name_last_feature(adapter, f"{label}ProngProfile")
        check(f"{label} prong", await adapter.create_extrusion(ExtrusionParameters(depth=spec.COTTER_WIDTH)))
        name_last_feature(adapter, f"{label}SpreadProng")
