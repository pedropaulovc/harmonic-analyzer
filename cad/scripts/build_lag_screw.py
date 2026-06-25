r"""Reproduction script: rocker-support hold-down screw (book ch. 14; 2 used).

One of the two hold-down screws that come up through the base into the
rocker-arm-support north upright's O7.94 x 25 underside sockets (the docstring's
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

    uv run python cad\scripts\build_lag_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
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

PART_NAME = "lag-screw"
MATERIAL = "Plain Carbon Steel"  # black hardware

HEAD_DIA = 14.0  # round head in the O15 base counterbore (low)
HEAD_H = 4.0  # recessed 0.5 below the base bottom (counterbore 4.5)
SHANK_DIA = 7.8  # rides the O8.2 base hole into the O7.94 support socket
SHANK_LEN = 66.0  # base 50.8 + 19.2 socket reach (socket 25 deep)


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units). HeadH/ShankLen
    # are extrude depths (feature params, not sketch dims) -- exposed as knobs but
    # nothing drives them, matching the exemplars.
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadH", f"{HEAD_H}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head -4..0 (Top sketch, offset extrude up to the under-head plane).
    # On-axis circle (origin): only the diameter is a dim.
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head", dims=head_dims,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head_dims.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, HEAD_H, -HEAD_H)
    name_last_feature(adapter, "Head")
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank 0..+66 (on-axis circle: only the diameter is a dim).
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
    extrude_at_offset(adapter, SHANK_LEN, 0.0)
    name_last_feature(adapter, "Shank")
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven lag screw (equations neutral)", expected, 0.005 * v_shank)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
