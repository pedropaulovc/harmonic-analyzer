r"""Reproduction script: fillister screw (book ch. 20/22; 6 used).

The small brass machine screw used twice over: 4x holding the platen
paper-clip strips through their existing O3 end holes into O3 platen
sockets (ch. 22 p. 55 -- the platen's "fastener holes deferred to
assembly" promise, resolved in the M6.10 fasteners pass), and 2x
fastening the magnifying-lever bracket's flange up into the summing
lever's coefficients plate (ch. 20 p. 47 "mounting screws omitted").
Period slotted cheese head with a model-owned 6 BA cosmetic thread callout.

Dimensions: cad/DIMENSIONS.md ch. 20/22 (M6.10) -- shank matches the
clip holes (O3, scaled low); head photo-plausible fillister (low).

Layout: axis along Z, AUTHORED IN FINAL ORIENTATION (pointing +Z =
machine north for the clips; the flange copies rotate Rx(-90) to point
+Y): under-head face on the Front plane at z = 0, head -2.2..0, shank
0..+4. Symmetric about local x = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fillister_screw.py
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
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "fillister-screw"
MATERIAL = "Brass"  # bright screws on the brass clips

HEAD_DIA = 4.2  # period 6 BA cheese-head proportion
HEAD_H = 1.96
SLOT_W = 0.448
SLOT_D = 0.882
SHANK_DIA = 2.8  # 6 BA major diameter
SHANK_LEN = 4.0  # clip 1.2 + 2.8 platen socket; = flange thickness 4


def _blank_reference(adapter, name: str, selection_type: str) -> None:
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    selected = model.Extension.SelectByID2(
        name, selection_type, 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"cannot select {selection_type} {name!r} to hide")
    model.BlankRefGeom()
    model.ClearSelection2(True)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        AddThreadParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units). HeadH/ShankLen
    # are extrude depths (feature params, not sketch dims) -- exposed as knobs but
    # nothing drives them, matching the exemplars.
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadH", f"{HEAD_H}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")
    await set_global(adapter, "SlotW", f"{SLOT_W}mm")
    await set_global(adapter, "SlotD", f"{SLOT_D}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head -2.2..0 (Front sketch, offset extrude up to the under-head plane).
    # On-axis circle (origin): only the diameter is a dim.
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
    extrude_at_offset(adapter, HEAD_H, -HEAD_H)
    name_last_feature(adapter, "Head")
    v_head = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    expected = v_head
    await volume_check(adapter, "head", expected, 0.005 * v_head)

    # Shank 0..+4 (on-axis circle: only the diameter is a dim).
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
    extrude_at_offset(adapter, SHANK_LEN, 0.0)
    name_last_feature(adapter, "Shank")
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    # Cut the period driver slot from the outer head face toward the shank.
    check(
        "create_plane head outer face",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=-HEAD_H
            )
        ),
    )
    name_last_feature(adapter, "HeadOuterFace")
    slot_dims = SketchDims()
    check("create_sketch driver slot", await adapter.create_sketch("HeadOuterFace"))
    await define_centered_rectangle(
        adapter,
        HEAD_DIA / 2.0 + 0.5,
        SLOT_W / 2.0,
        "driver slot",
        dims=slot_dims,
        name_width="SlotLength",
        name_depth="SlotWidth",
        name_corner=("SlotCx", "SlotCy"),
        drive_corner=(None, None),
    )
    await ensure_fully_defined(adapter, "driver slot sketch")
    check("exit_sketch driver slot", await adapter.exit_sketch())
    name_last_feature(adapter, "DriverSlotProfile")
    drive_jobs += slot_dims.apply(adapter, "DriverSlotProfile")
    check(
        "cut driver slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SLOT_D, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "DriverSlot")
    half_slot = SLOT_W / 2.0
    head_radius = HEAD_DIA / 2.0
    slot_area = 2.0 * (
        half_slot * math.sqrt(head_radius**2 - half_slot**2)
        + head_radius**2 * math.asin(half_slot / head_radius)
    )
    v_slot = slot_area * SLOT_D
    expected -= v_slot
    await volume_check(adapter, "slotted head", expected, 0.02 * v_slot)

    thread_result = await adapter.add_thread(
            AddThreadParameters(
                edge_point=[SHANK_DIA / 2.0, 0.0, SHANK_LEN],
                standard="none",
                standard_type="British Association",
                size="6 BA",
                diameter=SHANK_DIA,
                end_type="blind",
                depth=SHANK_LEN,
                note="6 BA, 0.53 PITCH, 47.5 DEG INCLUDED ANGLE",
            )
        )
    check("add model-owned 6 BA thread", thread_result)
    if not thread_result.data or thread_result.data.get("size") != "6 BA":
        raise RuntimeError(f"6 BA cosmetic thread read-back failed: {thread_result.data!r}")
    _blank_reference(adapter, "HeadOuterFace", "PLANE")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven fillister screw (equations neutral)",
        expected,
        0.02 * v_slot,
    )

    axis_name = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "screw axis"
    )
    _blank_reference(adapter, axis_name, "AXIS")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
