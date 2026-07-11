r"""Reproduction script: rocker-support hold-down screw (book ch. 14; 4 used).

One of the four hold-down screws that come up through the base into the
rocker-arm-support north upright's 9/16-12 tapped foot holes (O12.30376 tap
drill; build_rocker_arm_support.py FootTappedHoles, 25.4 deep up to the window).
The round head sits recessed in a counterbore on the base underside
(build_harmonic_base.py); plain head and shank, thread not modeled (the O12
shank rides the tap-drill foot hole, like the legacy socket fit).

Dimensions: cad/DIMENSIONS.md ch. 14 layout (M6.10) -- shank sized to the
9/16-12 tap-drill foot hole; head sized to the O23 base counterbore (low).

Layout: axis along Y, AUTHORED IN FINAL ORIENTATION (pointing up): head
underside at y = -6 rising to the under-head plane y = 0, shank 0..+63
(base 44.3 above the 6.5 cbore + ~18.7 into the support foot, inserted at
machine y 6.5). Symmetric about local x = 0.

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

HEAD_DIA = 22.0  # round head in the O23 base counterbore (low)
HEAD_H = 6.0  # recessed 0.5 below the base bottom (counterbore 6.5)
SHANK_DIA = 12.0  # rides the O13 base hole into the O12.30 9/16-12 tapped foot hole
SHANK_LEN = 63.0  # 44.3 base (above the 6.5 cbore) + 18.7 into the support foot


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

    # ScrewAxis datum: the screw's central axis = Right Plane ∩ Front Plane (the
    # Y axis through the origin, the revolve axis of the head + shank). frame.SLDASM
    # mates it CONCENTRIC to the base hole axis to seat the hold-down coaxially --
    # constrained, not grounded, no distance mate. Built from the two principal
    # planes so it needs no face pick.
    from solidworks_mcp.adapters.base import CreateAxisParameters

    check(
        "create_axis ScrewAxis (Right ∩ Front)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Right Plane", "Front Plane"])
        ),
    )
    name_last_feature(adapter, "ScrewAxis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
