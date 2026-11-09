r"""Build MHA-DT-VN-71 from complete 98830A511 key stock, then cut it to length.

Owner decision C1 keyed, 2026-11-09 (PR #1992): the 1/16 square key in
MHA-DT-04's land-1 keyseat (``dt_vn_cone_shaft_key_spec``).  The stock
recipe ``diagnostics/diag_build_98830A511.py`` models the whole 12 in bar;
the native ``CutLength`` (``KeyCutProfile``, marked for the drawing at the
title block's .XX) drives the cut plane from the south end, and the cut
removes the rest of the bar.  The section stays the stock's, its two sizes
(``KeyProfile``) marked for the drawing as the supplier's reference.

Frame (the spec's): origin at the south end on the bottom face, mid-width;
length along +Z, height along +X (bottom face on the Right Plane), width
centred on the Top Plane.  The cut is sketched on the Right Plane, whose
sketch x is model -Z (the MHA-DT-VN-59 pin builder's convention).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_vn_cone_shaft_key.py
"""

from __future__ import annotations

import sys
from functools import wraps

from _appearance import POLISHED_STEEL
from _check import check
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _fastener_catalog import fastener
from _feature_tree import name_last_feature
from _part_checks import volume_check
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _stock_fastener import StockComponent, build_stock_fastener
from diagnostics.diag_build_98830A511 import build_98830A511
from diagnostics.diag_mcmaster_lib import no_sketch_inference
from dt_vn_cone_shaft_key_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    LENGTH,
    SIZE,
    SKU,
    STOCK_LENGTH,
)

PART_NAME = "dt-vn-cone-shaft-key"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def _cut_stock(adapter) -> None:
    """Cut the bar at ``CutLength`` from its south end; the cutter's other
    edges stand one key size clear of the bar."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    margin = SIZE
    far = STOCK_LENGTH + margin
    dims = SketchDims()
    check("create_sketch key cut", await adapter.create_sketch("Right"))
    with no_sketch_inference(adapter):
        # Right sketch x is model -Z: the kept key lies at x in [-LENGTH, 0].
        lines = await add_line_chain(
            adapter,
            [(-LENGTH, -margin), (-far, -margin), (-far, margin), (-LENGTH, margin)],
        )
        for line, relation in zip(
            lines, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                f"key cut {relation} {line}",
                await adapter.add_sketch_constraint(line, None, relation),
            )
        # The general anchor dimensions x first (the cut length), then y.
        await anchor_point_to_origin(
            adapter, f"{lines[0]}.start", -LENGTH, -margin, "key cut plane"
        )
        dims.record("CutLength")
        dims.record("CutterBottom")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            far - LENGTH,
            "key cutter reach",
        )
        dims.record("CutterReach")
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            f"{lines[1]}.end",
            "vertical_distance",
            2.0 * margin,
            "key cutter height",
        )
        dims.record("CutterHeight")
        await ensure_fully_defined(adapter, "key cut")
    check("exit_sketch key cut", await adapter.exit_sketch())
    name_last_feature(adapter, "KeyCutProfile")
    dims.apply(adapter, "KeyCutProfile")
    check(
        "cut key to length",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * margin, both_directions=True)
        ),
    )
    name_last_feature(adapter, "KeyCut")
    volume = SIZE * SIZE * LENGTH
    await volume_check(adapter, "key cut to length", volume, 0.005 * volume)


def _manufacturing_controls(adapter) -> None:
    clear_dimensions_for_drawing(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})


@wraps(build_98830A511)
async def _cut_to_length(adapter, truth=None):
    # The shared recipe builds the supplied bar; the cut makes the key.
    await build_98830A511(adapter, truth)
    await _cut_stock(adapter)
    _manufacturing_controls(adapter)
    await force_rebuild(adapter)


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent(sku=SKU, author=_cut_to_length),),
        material=MATERIAL,
        color=POLISHED_STEEL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
