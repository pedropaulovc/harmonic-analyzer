"""Native custom rod-pivot pin; head face at Z=0, thread pointing +Z."""

from __future__ import annotations

import math
import sys

from _common import (
    apply_material, check, define_circle, define_centered_rectangle,
    ensure_fully_defined, force_rebuild, name_dimensions, name_last_feature,
    run_build, save_part_and_images, volume_check,
)
import rod_pivot_spec as pivot

PART_NAME = "rod-pivot-pin"
MATERIAL = "Plain Carbon Steel"


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import AddThreadParameters, ExtrusionParameters

    check("create pivot pin", await adapter.create_part())
    shoulder_end = pivot.PIN_HEAD_THICKNESS + pivot.PIN_SHOULDER_LENGTH
    for feature, diameter, length in (
        ("Head", pivot.PIN_HEAD_DIA, pivot.PIN_HEAD_THICKNESS),
        ("Shoulder", pivot.PIN_SHOULDER_DIA, shoulder_end),
        ("ThreadBlank", pivot.THREAD_MAJOR, pivot.PIN_LENGTH),
    ):
        check(f"sketch {feature}", await adapter.create_sketch("Front"))
        await define_circle(adapter, 0.0, 0.0, diameter / 2.0, feature)
        await ensure_fully_defined(adapter, feature)
        check(f"exit {feature}", await adapter.exit_sketch())
        name_last_feature(adapter, f"{feature}Profile")
        check(f"extrude {feature}", await adapter.create_extrusion(ExtrusionParameters(depth=length)))
        name_last_feature(adapter, feature)
        name_dimensions(adapter, feature, ["Length"])

    # A narrow relief lets the shoulder seat without a partial thread fouling it.
    check("sketch thread relief", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, pivot.THREAD_MAJOR / 2.0 + 0.1, "relief outside")
    await define_circle(adapter, 0.0, 0.0, pivot.PIN_THREAD_RELIEF_DIA / 2.0, "relief root")
    await ensure_fully_defined(adapter, "thread relief")
    check("exit thread relief", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadReliefProfile")
    check("cut thread relief", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=pivot.PIN_THREAD_RELIEF_LENGTH, start_offset=shoulder_end,
        reverse_direction=True,
    )))
    name_last_feature(adapter, "ThreadRelief")

    check("sketch driver slot", await adapter.create_sketch("Front"))
    await define_centered_rectangle(adapter, pivot.PIN_HEAD_DIA / 2.0 + 0.2, pivot.PIN_SLOT_WIDTH / 2.0, "driver slot")
    await ensure_fully_defined(adapter, "driver slot")
    check("exit driver slot", await adapter.exit_sketch())
    name_last_feature(adapter, "DriverSlotProfile")
    check("cut driver slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=pivot.PIN_SLOT_DEPTH, reverse_direction=True,
    )))
    name_last_feature(adapter, "DriverSlot")
    await force_rebuild(adapter)
    r = pivot.PIN_HEAD_DIA / 2.0
    half_slot = pivot.PIN_SLOT_WIDTH / 2.0
    slot_area = 2.0 * (half_slot * math.sqrt(r * r - half_slot * half_slot) + r * r * math.asin(half_slot / r))
    volume = math.pi / 4.0 * (
        pivot.PIN_HEAD_DIA**2 * pivot.PIN_HEAD_THICKNESS
        + pivot.PIN_SHOULDER_DIA**2 * pivot.PIN_SHOULDER_LENGTH
        + pivot.THREAD_MAJOR**2 * pivot.PIN_THREAD_LENGTH
        - (pivot.THREAD_MAJOR**2 - pivot.PIN_THREAD_RELIEF_DIA**2) * pivot.PIN_THREAD_RELIEF_LENGTH
    ) - slot_area * pivot.PIN_SLOT_DEPTH
    await volume_check(adapter, "recessed pivot pin", volume, 0.002 * volume)
    check("pivot pin external thread", await adapter.add_thread(AddThreadParameters(
        edge_point=[pivot.THREAD_MAJOR / 2.0, 0.0, pivot.PIN_LENGTH],
        standard="ansi_inch", size=pivot.THREAD_SIZE,
        diameter=pivot.THREAD_TAP_DRILL, end_type="blind",
        depth=pivot.PIN_THREAD_LENGTH - pivot.PIN_THREAD_RELIEF_LENGTH,
        note=f"{pivot.THREAD_SIZE} UNF-2A",
    )))
    await apply_material(adapter, MATERIAL)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
