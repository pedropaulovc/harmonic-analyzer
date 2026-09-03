r"""Reproduction script: short slotted crankshaft retaining screw.

The stock #4-40 fillister screw is too long for this location: after crossing
the 1 mm brass cap, its shank would enter the transverse taper-pin envelope.
This dedicated #0-80 screw retains the coaxial cap with 0.55 mm engagement
(more than 1.7 full threads) and leaves the finished taper pin unobstructed.

Layout: axis along local +Z; under-head plane at z = 0, head at negative Z,
and shank at positive Z.
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
from _fastener_catalog import fastener
from _fastener_slot import FastenerAxis, add_slotted_drive
from crank_end_retainer_spec import (
    SCREW_HEAD_DIA,
    SCREW_HEAD_H,
    SCREW_SHANK_DIA,
    SCREW_SHANK_LEN,
    SCREW_SLOT_D,
    SCREW_SLOT_W,
    SCREW_THREAD,
)


PART_NAME = "crank-retainer-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
if (SPEC.thread, SPEC.length_mm, SPEC.model_diameter_mm) != (
    SCREW_THREAD,
    SCREW_SHANK_LEN,
    SCREW_SHANK_DIA,
):
    raise AssertionError("crank retainer screw disagrees with the fastener catalog")


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    await set_global(adapter, "HeadDia", f"{SCREW_HEAD_DIA}mm")
    await set_global(adapter, "HeadH", f"{SCREW_HEAD_H}mm")
    await set_global(adapter, "ShankDia", f"{SCREW_SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SCREW_SHANK_LEN}mm")

    head = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SCREW_HEAD_DIA / 2.0,
        "retaining screw head",
        dims=head,
        names=("HeadCx", "HeadCy", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "retaining screw head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs = head.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, SCREW_HEAD_H, 0.0, flip=True)
    name_last_feature(adapter, "Head")
    v_head = math.pi * (SCREW_HEAD_DIA / 2.0) ** 2 * SCREW_HEAD_H
    expected = v_head
    await volume_check(adapter, "retaining screw head", expected, 0.005 * v_head)

    shank = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        SCREW_SHANK_DIA / 2.0,
        "retaining screw shank",
        dims=shank,
        names=("ShankCx", "ShankCy", "ShankDia"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "retaining screw shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank.apply(adapter, "ShankProfile")
    extrude_at_offset(adapter, SCREW_SHANK_LEN, 0.0)
    name_last_feature(adapter, "Shank")
    v_shank = math.pi * (SCREW_SHANK_DIA / 2.0) ** 2 * SCREW_SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "retaining screw shank", expected, 0.005 * v_shank)

    expected, slot_jobs = await add_slotted_drive(
        adapter,
        axis=FastenerAxis.Z,
        head_radius_mm=SCREW_HEAD_DIA / 2.0,
        head_face_offset_mm=-SCREW_HEAD_H,
        width_mm=SCREW_SLOT_W,
        depth_mm=SCREW_SLOT_D,
        expected_volume_mm3=expected,
    )
    drive_jobs += slot_jobs

    await force_rebuild(adapter)
    for dim_name, expression in drive_jobs:
        await drive_dimension(adapter, dim_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven retaining screw (equations neutral)",
        expected,
        max(0.005 * v_shank, 0.1),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
