r"""Reproduction script: cone tip pinch screw (item 5, v4_t00471 / 7:49).

The small slotted screw PERPENDICULAR to the tip block's top slit: it
squeezes the slit closed, clamping the block's threaded bore around the
axial adjuster so the end-play setting can't back off (the McMaster
61815K41 base-mount shaft-support pattern, applied to lock the adjuster
screw rather than a shaft).

Authored along +Y from the head seat (origin): head up, shank down;
the assembly lays it horizontally across the slit.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_pinch_screw.py
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
    force_rebuild,
    name_bore_axis,
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
from cone_tip_pinch_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    HEAD_DIA,
    HEAD_T,
    SHANK_DIA,
    SHANK_LEN,
)

PART_NAME = "cone-tip-pinch-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # bright screw (t00471 chrome head)

SLOT_W = 0.8
SLOT_D = 0.8


def _slot_strip_area(r: float, w: float) -> float:
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadT", f"{HEAD_T}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")
    drive_jobs: list[tuple[str, str]] = []

    head = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head", dims=head,
        names=("HeadCx", "HeadCz", "HeadDiaDim"), drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check("extrude head", await adapter.create_extrusion(
        ExtrusionParameters(depth=HEAD_T)))
    name_last_feature(adapter, "Head")
    v = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_T
    volume = await volume_check(adapter, "head", v, 0.01 * v)

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
    check("extrude shank (down)", await adapter.create_extrusion(
        ExtrusionParameters(depth=SHANK_LEN, reverse_direction=True)))
    name_last_feature(adapter, "Shank")
    v_s = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    volume = await volume_check(adapter, "shank", volume + v_s, 0.01 * v_s)

    check("create_plane HeadTop", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=HEAD_T)))
    name_last_feature(adapter, "HeadTop")
    slot = SketchDims()
    check("create_sketch slot", await adapter.create_sketch("HeadTop"))
    await define_centered_rectangle(
        adapter, HEAD_DIA / 2.0 + 0.5, SLOT_W / 2.0, "slot", dims=slot,
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
    v_slot = _slot_strip_area(HEAD_DIA / 2.0, SLOT_W) * SLOT_D
    volume = await volume_check(adapter, "slot", volume - v_slot, 0.05 * v_slot)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven screw (equations neutral)", volume,
                       0.05 * v_slot)

    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "screw axis")
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
