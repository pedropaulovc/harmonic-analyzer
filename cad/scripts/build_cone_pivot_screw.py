r"""Reproduction script: cone platform pivot screw (item 2, p.18 "pivot").

The slotted shoulder screw the swing platform rotates ON: head seats on
the plate top at the pivot, O6.35 shoulder drops through the plate's
O6.5 clearance hole into the harmonic base's pivot hole (the base part
carries the matching hole; agreement asserted in the drive-train
assembly). The plate swings about this shank -- it is the physical p1
pivot pin.

Stacked extrudes from the head seat (origin, Top plane): head up, shank
down; one rectangular cut across the head top forms the driver slot.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_pivot_screw.py
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

PART_NAME = "cone-pivot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # bright steel screw (v4 stills)

HEAD_DIA = 9.5  # covers the plate's O6.5 hole; r 4.75 clears the tip block's
# north face 0.25 (pivot station 196 - block north 191 -- assembly-asserted;
# the first O12 cut clipped the block corner 13.5 mm^3)
HEAD_T = 3.0
SLOT_W = 1.6  # driver slot width
SLOT_D = 1.2  # driver slot depth into the head top
SHANK_DIA = SPEC.model_diameter_mm  # shoulder: the plate's O6.5 hole rides it
SHANK_LEN = SPEC.length_mm  # plate 6.35 + 6.0 engaged into the base's pivot hole


def _slot_strip_area(r: float, w: float) -> float:
    """Plan area of a width-w strip across a radius-r circle (exact)."""
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
    check("extrude head",
          await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_T)))
    name_last_feature(adapter, "Head")
    v = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_T
    volume = await volume_check(adapter, "head", v, 0.005 * v)

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
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    volume = await volume_check(adapter, "shank", volume + v_shank, 0.005 * v_shank)

    # Driver slot: rect cut from the head top, SLOT_D deep.
    check("create_plane HeadTop", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=HEAD_T)))
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
    v_slot = _slot_strip_area(HEAD_DIA / 2.0, SLOT_W) * SLOT_D
    volume = await volume_check(adapter, "slot", volume - v_slot, 0.02 * v_slot)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven screw (equations neutral)", volume, 0.02 * v_slot)

    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "pivot axis")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
