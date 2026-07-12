r"""Reproduction script: foot-rail hex bolt (book ch. 30 p008; 2 used).

One of the two hex-head hold-down bolts on the rocker-support portal
frame's foot rail (ch. 30 p008 side view shows the heads on the rail's
top face; the rail itself is build_rocker_arm_support.py, M6.9/M6.12 -- the
foot rail was unified into the single portal casting). The bolt drops
through the rail (20 tall) into the base's top plate -- the base holes
are through-drilled (build_harmonic_base.py, documented simplification).
Plain head and shank: thread not modeled (matches the collar/washer
collapses elsewhere).

Dimensions: cad/DIMENSIONS.md ch. 23 portal foot-rail row (M6.10 fasteners
pass) -- 5/16" shank matching the legacy hold-down size, head photo-plausible
(low).

Layout: axis along Y, AUTHORED IN FINAL ORIENTATION (head up): under-head
face on the Top plane at y = 0, hex head rising to +5.5, shank descending
to -32. Inserted with IDENTITY rotation; symmetric about local x = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_hex_bolt.py
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
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
    volume_check,
)

PART_NAME = "hex-bolt"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # black hardware

HEAD_AF = 12.7  # hex across-flats, 1/2" wrench size for a 5/16" bolt (low)
HEAD_H = 5.5  # head height (low)
SHANK_DIA = SPEC.model_diameter_mm  # rides the O8.2 rail/base holes
SHANK_LEN = SPEC.length_mm  # rail 20 + 12 reach into the base top plate

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

    # Hex head 0..+5.5 (Top sketch: sketch (x, y) -> global (X, -Z)).
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
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Top"))
    head = await add_line_chain(adapter, points)
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

    # Shank -32..0 (on-axis circle: only the diameter is a dim).
    shank_dims = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Top"))
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
    await volume_check(adapter, "driven hex bolt (equations neutral)", expected, 0.005 * v_head)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
