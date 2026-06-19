r"""Reproduction script: fillister screw (book ch. 20/22; 6 used).

The small brass machine screw used twice over: 4x holding the platen
paper-clip strips through their existing O3 end holes into O3 platen
sockets (ch. 22 p. 55 -- the platen's "fastener holes deferred to
assembly" promise, resolved in the M6.10 fasteners pass), and 2x
fastening the magnifying-lever bracket's flange up into the summing
lever's coefficients plate (ch. 20 p. 47 "mounting screws omitted").
Plain cylindrical head: the slot is ~0.8 mm, below comparison-render
resolution (documented simplification); thread not modeled.

Dimensions: cad/DIMENSIONS.md ch. 20/22 (M6.10) -- shank matches the
clip holes (O3, scaled low); head photo-plausible fillister (low).

Layout: axis along Z, AUTHORED IN FINAL ORIENTATION (pointing +Z =
machine north for the clips; the flange copies rotate Rx(-90) to point
+Y): under-head face on the Front plane at z = 0, head -2.2..0, shank
0..+4. Symmetric about local x = 0 (MIRROR_PLANE ("x", 0.0)).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_fillister_screw.py
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
    set_isometric_view,
    volume_check,
)

PART_NAME = "fillister-screw"
MATERIAL = "Brass"  # bright screws on the brass clips

HEAD_DIA = 5.5  # fillister head (low)
HEAD_H = 2.2
SHANK_DIA = 2.9  # rides the clips' O3 holes / the flange's O3.2 holes
SHANK_LEN = 4.0  # clip 1.2 + 2.8 platen socket; = flange thickness 4


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    # Head -2.2..0 (Front sketch, offset extrude up to the under-head plane).
    check("create_sketch head", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head")
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    extrude_at_offset(adapter, HEAD_H, -HEAD_H)
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank 0..+4.
    check("create_sketch shank", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank")
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    extrude_at_offset(adapter, SHANK_LEN, 0.0)
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
