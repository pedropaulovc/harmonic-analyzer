r"""Olander 4C50BHCA -- alloy steel button head socket cap screw, #4-40 x 1/2".

Catalogue and standard: ``_olander_4c50bhca`` (its docstring carries the live
Olander listing, its McMaster 91255A110 cross-reference and the ASME B18.3
Table 11 values).  The screw is the shared button-head recipe
(``diag_mcmaster_button_head.build_button_head``, the 91255A106 family laws)
at the listing's maximum head, plus one feature that recipe does not have:
the underhead fillet, ``UnderheadFillet``, a merging revolve of a concave
quarter circle R ``FILLET_R`` tangent to the bearing face at F max
(ASME B18.3 note 7), run out to the thread root at 45 deg.  Its envelope
contains the recipe's ``ThreadNeck`` cone, so that cone is left as built.
The fillet is a standard-bounded nominal, not vendor geometry.

No vendor model is downloaded or committed (no replica gate); the native
build is checked by the farm leaf.  The standalone run is catalog-only: it
builds the recipe, checks the solid is sane and saves it under
cad/out/reference for inspection.

Frame: axis +Y, head up, bearing face (head underside) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_4C50BHCA.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _stock_recipe import stock_recipe  # noqa: E402

from _olander_4c50bhca import DIMS, FILLET_R  # noqa: E402
from diagnostics.diag_mcmaster_button_head import (  # noqa: E402
    build_button_head,
    catalog_run,
)


def underhead_fillet_profile():
    """The fillet's half-section (mm; x radial, y axial): the arc's start,
    end and mid point, then the chain that closes it from the arc's end."""
    major_r = DIMS.major_dia / 2.0
    centre = (major_r + FILLET_R, -FILLET_R)
    start = (major_r + FILLET_R, 0.0)  # tangent to the bearing face, F max
    end = (major_r, -FILLET_R)  # tangent to the major diameter
    mid = (
        centre[0] - FILLET_R * math.sqrt(0.5),
        centre[1] + FILLET_R * math.sqrt(0.5),
    )
    runout_y = -FILLET_R - (major_r - DIMS.root_r)
    chain = [end, (DIMS.root_r, runout_y), (0.0, runout_y), (0.0, 0.0), start]
    return start, end, mid, chain


@_telemetry.traced("stock.button_head.underhead_fillet")
async def _underhead_fillet(adapter) -> None:
    from _check import check
    from _feature_tree import name_last_feature
    from _sketch import add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    start, end, mid, chain = underhead_fillet_profile()
    check("create_sketch underhead fillet", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        axis_end = chain[1][1] / 1000.0
        if sk_mgr.CreateCenterLine(0.0, 0.0, 0.0, 0.0, axis_end, 0.0) is None:
            raise RuntimeError(
                f"{DIMS.part_no} underhead fillet: CreateCenterLine failed"
            )
        arc = sk_mgr.Create3PointArc(
            start[0] / 1000.0,
            start[1] / 1000.0,
            0.0,
            end[0] / 1000.0,
            end[1] / 1000.0,
            0.0,
            mid[0] / 1000.0,
            mid[1] / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError(f"{DIMS.part_no} underhead fillet: arc failed")
        await add_line_chain(adapter, chain, close=False)
    check("exit_sketch underhead fillet", await adapter.exit_sketch())
    name_last_feature(adapter, "UnderheadFilletProfile")
    check(
        "underhead fillet",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "UnderheadFillet")


@stock_recipe("4C50BHCA", threaded=True)
async def build_4C50BHCA(adapter, truth=None):
    await build_button_head(adapter, DIMS)
    await _underhead_fillet(adapter)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await catalog_run(adapter, DIMS, build_4C50BHCA)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
