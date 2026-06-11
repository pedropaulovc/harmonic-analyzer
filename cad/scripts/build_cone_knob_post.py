r"""Reproduction script: cone knob post (book ch. 12, p. 18).

Green round post that carries the cone shaft's thin small-end tip (the
0.08" rod past the smallest gears): the tip rests in an open U-slot so
the cone set can be lifted/swung out of mesh by the knurled knob on the
shaft (ch. 12 notes; p. 18 top-down shows the green round post under
the small end, ~Ø32 at 2.23 px/mm from the largest-cone-gear-OD scale).

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive supports" (scaled p.18, low).

Layout: post axis = +Y from the origin; U-slot for the shaft tip opens
upward, running along Z (the assembly rotates the post 19.8 deg about Y
to align the slot with the cone axis); slot floor puts the resting tip's
centre at the drive height.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_cone_knob_post.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "cone-knob-post"
MATERIAL = "Gray Cast Iron"  # green-painted like the base castings

POST_DIA = 32.0  # p.18 top-down green post (scaled, low)
POST_HEIGHT = 80.0  # slot floor ~75 + walls past the tip (low)
TIP_DIA = 0.08 * IN  # 2.032: cone shaft small-end tip (M6.6 -- turned
# down from 1/8" so it clears the last drum gear's tooth tips, see
# build_cone_gear_shaft.py)
SLOT_WIDTH = 2.4  # tip dia + 0.18 clearance per side (derived)
BORE_HEIGHT = 76.0  # resting tip centre = drive height (med)

POST_RADIUS = POST_DIA / 2.0
SLOT_FLOOR = BORE_HEIGHT - TIP_DIA / 2.0  # 74.98: tip rests at drive height
SLOT_TOP = POST_HEIGHT + 2.0  # open upward


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch post", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, POST_RADIUS, "post circle")
    await ensure_fully_defined(adapter, "post sketch")
    check("exit_sketch post", await adapter.exit_sketch())
    check(
        "extrude post",
        await adapter.create_extrusion(ExtrusionParameters(depth=POST_HEIGHT)),
    )
    v_post = math.pi * POST_RADIUS**2 * POST_HEIGHT
    volume = await volume_check(adapter, "post cylinder", v_post, 0.005 * v_post)

    # U-slot: rectangle on the Front plane past the post top, cut through
    # along Z (symmetric) -- leaves an upward-open saddle for the tip.
    half_s = SLOT_WIDTH / 2.0
    check("create_sketch slot", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(
        adapter,
        [
            (-half_s, SLOT_FLOOR),
            (half_s, SLOT_FLOOR),
            (half_s, SLOT_TOP),
            (-half_s, SLOT_TOP),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "slot sketch", fix_entities=lines)
    check("exit_sketch slot", await adapter.exit_sketch())
    check(
        "cut slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=POST_DIA + 4.0, both_directions=True)
        ),
    )
    # Removed material: slot height x the post's plan chord, integrated
    # across the slot width.
    n = 2000
    dx = SLOT_WIDTH / n
    v_slot = 0.0
    for i in range(n):
        x = -half_s + (i + 0.5) * dx
        v_slot += (POST_HEIGHT - SLOT_FLOOR) * 2.0 * math.sqrt(POST_RADIUS**2 - x * x) * dx
    volume = await volume_check(adapter, "slot", volume - v_slot, 0.01 * v_slot)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
