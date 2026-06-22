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

    uv run python cad\scripts\build_pinch_screw.py
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

PART_NAME = "pinch-screw"
MATERIAL = "Plain Carbon Steel"  # black hardware

HEAD_DIA = 6.0  # bears on the collar's curved back face (tangent line, low)
HEAD_H = 2.5
SHANK_DIA = 2.9  # rides the collar's O3.2 radial hole
SHANK_LEN = 6.2  # wall now 11.2 (Ø25.4 column, M6.11): tip seats mid-hole, backed out


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): head dia/height, shank dia/length. The
    # mm suffix is load-bearing (INCH document; the equation manager reads bare
    # numbers in document units). HeadH/ShankLen are extrude DEPTHS (feature
    # parameters, not sketch dims) -- declared here as editable knobs, but nothing
    # in drive_jobs references them.
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadH", f"{HEAD_H}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head 0..+2.5 (Front sketch; on-axis circle: only the diameter is a dim).
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head", dims=head_dims,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head_dims.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, HEAD_H, 0.0)
    name_last_feature(adapter, "Head")
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank -6.2..0 (on-axis circle: only the diameter is a dim).
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

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pinch screw (equations neutral)", expected, 0.005 * v_shank)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
