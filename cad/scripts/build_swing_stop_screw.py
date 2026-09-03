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

from _fastener_catalog import fastener
from _common import (
    SketchDims,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from swing_stop_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    EMBED_LEN,
    END_VIEW_NOTE,
    HEAD_DIA,
    HEAD_T,
    PROUD_LEN,
    SHANK_DIA,
    SHANK_LEN,
    SLOT_D,
    SLOT_W,
)

PART_NAME = "swing-stop-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


def _slot_strip_area(r: float, w: float) -> float:
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    # ProudLen/EmbedLen/ShankLen/HeadT are plane offsets and extrude DEPTHS
    # (feature parameters) -- declared as knobs, nothing in drive_jobs
    # references them.
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ProudLen", f"{PROUD_LEN}mm")
    await set_global(adapter, "EmbedLen", f"{EMBED_LEN}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadT", f"{HEAD_T}mm")
    drive_jobs: list[tuple[str, str]] = []

    # Head first, seated on the ShankTop plane (y = PROUD_LEN) and extruded up
    # HEAD_T; the shank then grows from -EMBED_LEN up to the head's underside
    # as ONE offset-start extrude, so its depth dim IS the under-head length
    # the print carries (the old proud + embedded pair had no single length).
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
    # Name the extrude DEPTH dims so the drawing inserts them as the head-height
    # and under-head-length model dimensions (the depth is the first display
    # dim owned by a blind boss; the ShankTop plane's own offset dim is
    # filtered out by owner).
    name_dimensions(adapter, "Head", ["HeadHt"])
    v_h = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_T
    volume = await volume_check(adapter, "head", v_h, 0.005 * v_h)

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
    extrude_at_offset(adapter, SHANK_LEN, -EMBED_LEN)
    name_last_feature(adapter, "Shank")
    name_dimensions(adapter, "Shank", ["ShankLg"])
    v = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    volume = await volume_check(adapter, "shank", volume + v, 0.005 * v)

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
    # Name the slot cut's DEPTH dim so the print dimensions the slot on the
    # slot-profile view instead of carrying its size in a note.
    name_dimensions(adapter, "DriverSlot", ["SlotDepth"])
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
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
