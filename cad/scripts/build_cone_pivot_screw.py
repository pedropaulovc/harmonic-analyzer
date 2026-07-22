r"""Reproduction script: cone platform pivot screw (item 2, p.18 "pivot").

The slotted shoulder screw the swing platform rotates on.  Its ground shoulder
is 0.25 mm longer than the plate thickness, so tightening the threaded tail
against the base leaves running axial clearance instead of clamping the plate.
The distinct 1/4-20 UNC-2A tail engages the base's blind UNC-2B seat.

Stacked extrudes from the under-head datum (origin, Top plane): head up,
shoulder and thread tail down; one rectangular cut across the head top forms
the driver slot.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_pivot_screw.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
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
    extrude_at_offset,
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
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from cone_pivot_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    HEAD_DIA,
    HEAD_T,
    SHOULDER_DIA,
    SHOULDER_LEN,
    SLOT_D,
    SLOT_W,
    THREAD_MAJOR_DIA,
    THREAD_TAIL_LEN,
    UNDERHEAD_LEN,
)

PART_NAME = "cone-pivot-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # bright steel screw (v4 stills)

def _slot_strip_area(r: float, w: float) -> float:
    """Plan area of a width-w strip across a radius-r circle (exact)."""
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters
    from solidworks_mcp.adapters.solidworks.features import (
        _flag_feature_methods,
        _select_edges_geometric,
    )

    check("create_part", await adapter.create_part())
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadT", f"{HEAD_T}mm")
    await set_global(adapter, "ShoulderDia", f"{SHOULDER_DIA}mm")
    await set_global(adapter, "ShoulderLen", f"{SHOULDER_LEN}mm")
    await set_global(adapter, "ThreadMajorDia", f"{THREAD_MAJOR_DIA}mm")
    await set_global(adapter, "ThreadLen", f"{THREAD_TAIL_LEN}mm")
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
    name_dimensions(adapter, "Head", ["HeadHt"])
    v = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_T
    volume = await volume_check(adapter, "head", v, 0.005 * v)

    shoulder = SketchDims()
    check("create_sketch shoulder", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, SHOULDER_DIA / 2.0, "shoulder", dims=shoulder,
        names=("ShoulderCx", "ShoulderCz", "ShoulderDiaDim"),
        drives=(None, None, '"ShoulderDia"'),
    )
    await ensure_fully_defined(adapter, "shoulder sketch")
    check("exit_sketch shoulder", await adapter.exit_sketch())
    name_last_feature(adapter, "ShoulderProfile")
    drive_jobs += shoulder.apply(adapter, "ShoulderProfile")
    extrude_at_offset(adapter, SHOULDER_LEN, -SHOULDER_LEN)
    name_last_feature(adapter, "Shoulder")
    name_dimensions(adapter, "Shoulder", ["ShoulderLg"])
    v_shoulder = math.pi * (SHOULDER_DIA / 2.0) ** 2 * SHOULDER_LEN
    volume = await volume_check(
        adapter, "shoulder", volume + v_shoulder, 0.005 * v_shoulder
    )

    thread = SketchDims()
    check("create_sketch thread tail", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, THREAD_MAJOR_DIA / 2.0, "thread tail", dims=thread,
        names=("ThreadCx", "ThreadCz", "ThreadMajorDiaDim"),
        drives=(None, None, '"ThreadMajorDia"'),
    )
    await ensure_fully_defined(adapter, "thread-tail sketch")
    check("exit_sketch thread tail", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadTailProfile")
    drive_jobs += thread.apply(adapter, "ThreadTailProfile")
    extrude_at_offset(adapter, THREAD_TAIL_LEN, -UNDERHEAD_LEN)
    name_last_feature(adapter, "ThreadTail")
    name_dimensions(adapter, "ThreadTail", ["ThreadLg"])
    v_thread = math.pi * (THREAD_MAJOR_DIA / 2.0) ** 2 * THREAD_TAIL_LEN
    volume = await volume_check(
        adapter, "thread tail", volume + v_thread, 0.005 * v_thread
    )

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
    name_dimensions(adapter, "DriverSlot", ["SlotDepth"])
    v_slot = _slot_strip_area(HEAD_DIA / 2.0, SLOT_W) * SLOT_D
    volume = await volume_check(adapter, "slot", volume - v_slot, 0.02 * v_slot)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven screw (equations neutral)", volume, 0.02 * v_slot)

    thread_edge_point = [THREAD_MAJOR_DIA / 2.0, -UNDERHEAD_LEN, 0.0]
    if not _select_edges_geometric(adapter, [thread_edge_point], tol_mm=0.05):
        raise RuntimeError(
            f"cannot select external-thread start edge at {thread_edge_point}"
        )
    feature_manager = _flag_feature_methods(
        adapter.currentModel.FeatureManager,
        "IFeatureManager",
        "InsertCosmeticThread3",
    )
    cosmetic_thread = feature_manager.InsertCosmeticThread3(
        0,  # swCosmeticStandardType_e.swStandardAnsiInch
        "",
        SPEC.thread,
        0.0,  # standard/size table owns the nominal diameter
        0,  # swCosmeticEndConditions_e.swEndConditionBlind
        THREAD_TAIL_LEN / 1000.0,
        f"{SPEC.thread} UNC-2A",
    )
    if cosmetic_thread is None:
        raise RuntimeError("InsertCosmeticThread3 rejected the selected tail edge")
    _telemetry.success(f"cosmetic external thread {SPEC.thread} UNC-2A")

    pivot_axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "pivot axis"
    )
    _blank_ref_geometry(adapter, "HeadTop", "PLANE")
    _blank_ref_geometry(adapter, pivot_axis, "AXIS")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_symmetric_tolerance(adapter, "HeadProfile", "HeadDiaDim", 0.10)
    set_dimension_symmetric_tolerance(adapter, "Head", "HeadHt", 0.10)
    set_dimension_bilateral_tolerance(
        adapter, "ShoulderProfile", "ShoulderDiaDim", -0.05, -0.02
    )
    set_dimension_bilateral_tolerance(
        adapter, "Shoulder", "ShoulderLg", 0.00, 0.05
    )
    set_dimension_symmetric_tolerance(adapter, "ThreadTail", "ThreadLg", 0.10)
    set_dimension_symmetric_tolerance(adapter, "SlotProfile", "SlotWDim", 0.10)
    set_dimension_symmetric_tolerance(adapter, "DriverSlot", "SlotDepth", 0.10)
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


def _blank_ref_geometry(adapter, name: str, kind: str) -> None:
    """Keep the slot construction plane and mating axis out of saved renders."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, kind, 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {name!r} to hide reference geometry")
    model.BlankRefGeom()
    model.ClearSelection2(True)


if __name__ == "__main__":
    sys.exit(run_build(build))
