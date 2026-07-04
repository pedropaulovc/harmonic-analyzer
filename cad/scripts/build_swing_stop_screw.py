r"""Reproduction script: swing-stop screw (item 6, user review).

Small slotted screw standing in the harmonic base just past the swing
platform's DISENGAGED pose: the swinging plate's west edge bumps its
proud shank, limiting the p1 swing to exactly what disengagement needs
(the knob-washer-clear angle). The base part carries the matching hole;
the contact geometry is asserted in the drive-train assembly.

Origin at the BASE TOP: shank runs 6 down into the base and PROUD_LEN up
past the plate band (the 6.35-tall plate edge bumps the shank, not the
head); slotted head on top.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_swing_stop_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "swing-stop-screw"
MATERIAL = "Plain Carbon Steel"

SHANK_DIA = 4.0
EMBED_LEN = 6.0  # into the base's stop hole
PROUD_LEN = 8.0  # above the base top: covers the 6.35 plate band + margin
HEAD_DIA = 8.0
HEAD_T = 2.5
SLOT_W = 1.2
SLOT_D = 1.0


def _slot_strip_area(r: float, w: float) -> float:
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ProudLen", f"{PROUD_LEN}mm")
    await set_global(adapter, "EmbedLen", f"{EMBED_LEN}mm")
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadT", f"{HEAD_T}mm")
    drive_jobs: list[tuple[str, str]] = []

    shank = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank", dims=shank,
        names=("ShankCx", "ShankCz", "ShankDiaDim"), drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank.apply(adapter, "ShankProfile")
    check("extrude shank (up)", await adapter.create_extrusion(
        ExtrusionParameters(depth=PROUD_LEN)))
    name_last_feature(adapter, "ShankProud")
    v = math.pi * (SHANK_DIA / 2.0) ** 2 * PROUD_LEN
    volume = await volume_check(adapter, "shank proud", v, 0.005 * v)

    embed = SketchDims()
    check("create_sketch embed", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, SHANK_DIA / 2.0, "embed", dims=embed,
        names=("EmbedCx", "EmbedCz", "EmbedDiaDim"), drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "embed sketch")
    check("exit_sketch embed", await adapter.exit_sketch())
    name_last_feature(adapter, "EmbedProfile")
    drive_jobs += embed.apply(adapter, "EmbedProfile")
    check("extrude embed (down)", await adapter.create_extrusion(
        ExtrusionParameters(depth=EMBED_LEN, reverse_direction=True)))
    name_last_feature(adapter, "ShankEmbed")
    v_e = math.pi * (SHANK_DIA / 2.0) ** 2 * EMBED_LEN
    volume = await volume_check(adapter, "shank embed", volume + v_e, 0.005 * v_e)

    check("create_plane ShankTop", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=PROUD_LEN)))
    name_last_feature(adapter, "ShankTop")
    headsk = SketchDims()
    check("create_sketch head", await adapter.create_sketch("ShankTop"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head", dims=headsk,
        names=("HeadCx", "HeadCz", "HeadDiaDim"), drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += headsk.apply(adapter, "HeadProfile")
    check("extrude head", await adapter.create_extrusion(
        ExtrusionParameters(depth=HEAD_T)))
    name_last_feature(adapter, "Head")
    v_h = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_T
    volume = await volume_check(adapter, "head", volume + v_h, 0.005 * v_h)

    check("create_plane HeadTop", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Top Plane",
                              offset=PROUD_LEN + HEAD_T)))
    name_last_feature(adapter, "HeadTop")
    slot = SketchDims()
    check("create_sketch slot", await adapter.create_sketch("HeadTop"))
    await define_centered_rectangle(
        adapter, HEAD_DIA / 2.0 + 1.0, SLOT_W / 2.0, "slot", dims=slot,
        name_width="SlotLen", drive_width=None,
        name_depth="SlotWDim", drive_depth=None,
        name_corner=("SlotCx", "SlotCz"), drive_corner=(None, None),
    )
    await ensure_fully_defined(adapter, "slot sketch")
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    drive_jobs += slot.apply(adapter, "SlotProfile")
    # A CUT's default direction is OPPOSITE the sketch normal (FeatureCut4
    # remarks), so from the head-top plane it already cuts DOWN into the head.
    check("cut slot", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=SLOT_D)))
    name_last_feature(adapter, "DriverSlot")
    v_slot = _slot_strip_area(HEAD_DIA / 2.0, SLOT_W) * SLOT_D
    volume = await volume_check(adapter, "slot", volume - v_slot, 0.02 * v_slot)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven screw (equations neutral)", volume, 0.02 * v_slot)

    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "stop axis")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
