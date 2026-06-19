r"""Reproduction script: rocker-support hold-down screw (book ch. 14; 2 used).

One of the two hold-down screws that come up through the base into the
rocker-arm-support's O7.94 x 25 underside sockets (the part docstring's
"fasteners not modeled" -- modeled in the M6.10 fasteners pass). The
round head sits recessed in a counterbore on the base underside
(build_harmonic_base.py); plain head and shank, thread not modeled.

Dimensions: cad/DIMENSIONS.md ch. 14 layout (M6.10) -- shank matches the
legacy 5/16" socket; head sized to the O15 counterbore (low).

Layout: axis along Y, AUTHORED IN FINAL ORIENTATION (pointing up): head
underside at y = -4 rising to the under-head plane y = 0, shank 0..+66
(base 50.8 + 19.2 into the 25-deep socket, inserted at machine y 4.5).
Symmetric about local x = 0 (MIRROR_PLANE ("x", 0.0)).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_lag_screw.py
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

PART_NAME = "lag-screw"
MATERIAL = "Plain Carbon Steel"  # black hardware

HEAD_DIA = 14.0  # round head in the O15 base counterbore (low)
HEAD_H = 4.0  # recessed 0.5 below the base bottom (counterbore 4.5)
SHANK_DIA = 7.8  # rides the O8.2 base hole into the O7.94 support socket
SHANK_LEN = 66.0  # base 50.8 + 19.2 socket reach (socket 25 deep)


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    # Head -4..0 (Top sketch, offset extrude up to the under-head plane).
    check("create_sketch head", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head")
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    extrude_at_offset(adapter, HEAD_H, -HEAD_H)
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank 0..+66.
    check("create_sketch shank", await adapter.create_sketch("Top"))
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
