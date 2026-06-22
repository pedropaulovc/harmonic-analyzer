r"""Reproduction script: pen-hanger screw (book ch. 24; 1 used).

The bolt fixing the pen-hanger strap to the wheel bar (the hanger
docstring's "mounting bolt is omitted" -- modeled in the M6.10 fasteners
pass). It enters from BEHIND the bar: the magnifying wheel's rim back
face (machine z -142.9) passes only 1.0 in front of the strap, so a
front-side head cannot clear it. Hex head against the bar's back face,
shank through the bar into the strap's through-hole, tip recessed 0.5
behind the strap front face. Thread not modeled.

Dimensions: cad/DIMENSIONS.md ch. 24 (M6.10) -- sized to the 5-wide
strap/bar overlap at the bar's free end (walls >= 0.4, low).

Layout: axis along Z, AUTHORED IN FINAL ORIENTATION (pointing -Z =
machine south, into the bar's back face): under-head face on the Front
plane at z = 0, hex head 0..+2.5, shank -12.5..0 (bar 10 + strap 2.5).
Symmetric about local x = 0 (MIRROR_PLANE ("x", 0.0)).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_hanger_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "hanger-screw"
MATERIAL = "Plain Carbon Steel"  # black hardware

HEAD_AF = 7.0  # hex across-flats (low)
HEAD_H = 2.5
SHANK_DIA = 3.5  # rides the bar's O3.8 through-hole / strap's O3.6 hole
SHANK_LEN = 12.5  # bar 10 + 2.5 into the 3-thick strap (tip 0.5 recessed)

# Every hex offset dim is linear in the across-flats (radius = AF/sqrt 3), so a
# single HeadAF global drives them all via dimensionless coefficients -- unit-safe
# (no mm/inch trap) and no SolidWorks sqr() syntax to get wrong.
_INV_SQRT3 = 1.0 / math.sqrt(3.0)  # radius / AF
_HALF_INV_SQRT3 = 0.5 * _INV_SQRT3  # (radius/2) / AF


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "HeadAF", f"{HEAD_AF}mm")
    await set_global(adapter, "HeadH", f"{HEAD_H}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Hex head 0..+2.5 (Front sketch: sketch (x, y) -> global (X, Y)).
    # Exact-arithmetic vertices (r/2, AF/2) keep the flats' offsets exactly
    # axis-parallel for the polygon anchoring scheme.
    radius = HEAD_AF / math.sqrt(3.0)
    half_flat = HEAD_AF / 2.0
    points = [
        (radius, 0.0),
        (radius / 2.0, half_flat),
        (-radius / 2.0, half_flat),
        (-radius, 0.0),
        (-radius / 2.0, -half_flat),
        (radius / 2.0, -half_flat),
    ]
    # Emission order (anchor vertex 0 on +X axis = 1 dim; then segments 0..4,
    # segment 5 closes): V0x, S0dx, S0dy, S1dx, S2dx, S2dy, S3dx, S3dy, S4dx.
    _rx = f'"HeadAF" * {_INV_SQRT3!r}'      # radius
    _rx2 = f'"HeadAF" * {_HALF_INV_SQRT3!r}'  # radius / 2
    _hf = '"HeadAF" / 2'                      # half_flat
    # Direct-db: the AF-7 hexagon's vertices sit close enough to the origin
    # axes for inference snapping to distort the chain (live: head volume
    # 87.8 vs 106.1 analytic without it; the AF-12.7 hex-bolt survived).
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    head = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(
        adapter, head, points, label="head", dims=head_dims,
        names=["HeadV0X", "HeadS0dx", "HeadS0dy", "HeadS1dx",
               "HeadS2dx", "HeadS2dy", "HeadS3dx", "HeadS3dy", "HeadS4dx"],
        drives=[_rx, _rx2, _hf, _rx, _rx2, _hf, _rx2, _hf, _rx],
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HexHeadProfile")
    drive_jobs += head_dims.apply(adapter, "HexHeadProfile")
    extrude_at_offset(adapter, HEAD_H, 0.0)
    name_last_feature(adapter, "HexHead")
    v_head = math.sqrt(3.0) / 2.0 * HEAD_AF**2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank -12.5..0 (on-axis circle: only the diameter is a dim).
    shank_dims = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank", dims=shank_dims,
        names=("ShankCx", "ShankCz", "ShankDia"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_dims.apply(adapter, "ShankProfile")
    extrude_at_offset(adapter, SHANK_LEN, -SHANK_LEN)
    name_last_feature(adapter, "Shank")
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven hanger screw (equations neutral)", expected, 0.005 * v_head)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
