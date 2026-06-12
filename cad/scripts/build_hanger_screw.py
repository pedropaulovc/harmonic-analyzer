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

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_hanger_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)

PART_NAME = "hanger-screw"
MATERIAL = "Plain Carbon Steel"  # black hardware

HEAD_AF = 7.0  # hex across-flats (low)
HEAD_H = 2.5
SHANK_DIA = 3.5  # rides the bar's O3.8 through-hole / strap's O3.6 hole
SHANK_LEN = 12.5  # bar 10 + 2.5 into the 3-thick strap (tip 0.5 recessed)


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Hex head 0..+2.5 (Front sketch: sketch (x, y) -> global (X, Y)).
    radius = HEAD_AF / math.sqrt(3.0)
    points = [
        (radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a)))
        for a in range(0, 360, 60)
    ]
    check("create_sketch head", await adapter.create_sketch("Front"))
    head = await add_line_chain(adapter, points)
    await ensure_fully_defined(adapter, "head sketch", fix_entities=head)
    check("exit_sketch head", await adapter.exit_sketch())
    extrude_at_offset(adapter, HEAD_H, 0.0)
    v_head = math.sqrt(3.0) / 2.0 * HEAD_AF**2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank -12.5..0.
    check("create_sketch shank", await adapter.create_sketch("Front"))
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
