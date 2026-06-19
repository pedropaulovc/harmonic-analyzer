r"""Reproduction script: column-clamp pinch screw (book ch. 21/22; 5 used).

The screw that locks each column clamp's collar to its Ø25.4 column (OD
rederived from the 8-views, M6.11; the clamp docstring's "pinch screws
are omitted" -- modeled in the M6.10 fasteners pass). It enters the
collar's back wall through a radial O3.2 hole (build_column_clamp.py) and
is modeled BACKED OUT: the head bears on the collar back face and the
6.2 shank seats mid-wall, well clear of the column it would pinch (same
convention as the magnifying clamp's thumb screw). Plain head, slot and
thread not modeled.

Dimensions: cad/DIMENSIONS.md ch. 21 (M6.10) -- shank rides the radial
hole; the collar wall is now 24 - 12.8 = 11.2 thick (was 6.4 at the old
Ø35 bore), so the backed-out tip stands further off the column than
before; head photo-plausible (low).

Layout: axis along Z, AUTHORED IN FINAL ORIENTATION (pointing -Z =
machine south, into the clamp's back face): under-head face on the Front
plane at z = 0, head 0..+2.5, shank -6.2..0. Symmetric about local x = 0
(MIRROR_PLANE ("x", 0.0)).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinch_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
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

PART_NAME = "pinch-screw"
MATERIAL = "Plain Carbon Steel"  # black hardware

HEAD_DIA = 6.0  # bears on the collar's curved back face (tangent line, low)
HEAD_H = 2.5
SHANK_DIA = 2.9  # rides the collar's O3.2 radial hole
SHANK_LEN = 6.2  # wall now 11.2 (Ø25.4 column, M6.11): tip seats mid-hole, backed out


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Head 0..+2.5 (Front sketch).
    check("create_sketch head", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head")
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    extrude_at_offset(adapter, HEAD_H, 0.0)
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank -6.2..0.
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
