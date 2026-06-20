r"""Reproduction script: foot-rail hex bolt (book ch. 30 p008; 2 used).

One of the two hex-head hold-down bolts on the rocker-support portal
frame's foot rail (ch. 30 p008 side view shows the heads on the rail's
top face; the rail itself is build_rocker_arm_portal.py, M6.9/M6.12 -- the
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
to -32. Inserted with IDENTITY rotation; symmetric about local x = 0
(MIRROR_PLANE ("x", 0.0)).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_hex_bolt.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)

PART_NAME = "hex-bolt"
MATERIAL = "Plain Carbon Steel"  # black hardware

HEAD_AF = 12.7  # hex across-flats, 1/2" wrench size for a 5/16" bolt (low)
HEAD_H = 5.5  # head height (low)
SHANK_DIA = 7.8  # rides the O8.2 rail/base holes (5/16" nominal 7.94 - fit)
SHANK_LEN = 32.0  # rail 20 + 12 reach into the base top plate


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

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
    check("create_sketch head", await adapter.create_sketch("Top"))
    head = await add_line_chain(adapter, points)
    await define_polygon_chain(adapter, head, points, label="head")
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    extrude_at_offset(adapter, HEAD_H, 0.0)
    v_head = math.sqrt(3.0) / 2.0 * HEAD_AF**2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank -32..0.
    check("create_sketch shank", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank")
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    extrude_at_offset(adapter, SHANK_LEN, -SHANK_LEN)
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
