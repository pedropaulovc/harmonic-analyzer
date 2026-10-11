r"""Build the rocker arm's pivot shoulder screw (MHA-CH-006-TL-06; shop fixture).

A slotted shoulder screw turned and ring-lapped from 4140 bar
(``ch_rocker_arm_tl_pivot_screw_spec``). One revolve about model +Z in the
inventory's fixture frame: head top at Z5.5, under-head face at Z1.5 (the
washer's top), shoulder to Z-20, M5 thread to the Z-27.2 tip with a 45-degree
start chamfer. Every axial size baselines from the faced head top. The
driver slot is sketched on a plane at the head top and cut down into the head.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_pivot_screw.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_rectangle import define_centered_rectangle
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_pivot_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HEAD_DIA,
    HEAD_LENGTH,
    HEAD_TOP_Z,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_LENGTH,
    SHOULDER_DIA,
    SHOULDER_LENGTH,
    SLOT_DEPTH,
    SLOT_WIDTH,
    SURFACE_FINISHES,
    THREAD_LENGTH,
    THREAD_MODEL_DIA,
    TIP_CHAMFER,
    UNDER_HEAD_LENGTH,
)

PART_NAME = "ch-rocker-arm-tl-pivot-screw"
MATERIAL = "Alloy Steel"  # the registry row names the 4140 pre-hardened bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

HEAD_R = HEAD_DIA / 2.0
SHOULDER_R = SHOULDER_DIA / 2.0
THREAD_R = THREAD_MODEL_DIA / 2.0
SLOT_SPAN = HEAD_DIA + 2.0

V_CHAMFER = math.pi * TIP_CHAMFER**2 * (THREAD_R - TIP_CHAMFER / 3.0)
V_BODY = (
    math.pi
    * (HEAD_R**2 * HEAD_LENGTH + SHOULDER_R**2 * SHOULDER_LENGTH + THREAD_R**2 * THREAD_LENGTH)
    - V_CHAMFER
)


def slot_strip_area(radius: float, width: float) -> float:
    """Plan area of a centred width-``width`` strip across a radius-``radius`` circle."""
    half = width / 2.0
    return 2.0 * (half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius))


V_SLOT = slot_strip_area(HEAD_R, SLOT_WIDTH) * SLOT_DEPTH
V_FINAL = V_BODY - V_SLOT


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units.
    for name, value in (
        ("HeadTop", HEAD_TOP_Z),
        ("HeadDia", HEAD_DIA),
        ("HeadLength", HEAD_LENGTH),
        ("ShoulderDia", SHOULDER_DIA),
        ("ShoulderLength", SHOULDER_LENGTH),
        ("ThreadDia", THREAD_MODEL_DIA),
        ("UnderHeadLength", UNDER_HEAD_LENGTH),
        ("TipChamfer", TIP_CHAMFER),
        ("SlotWidth", SLOT_WIDTH),
        ("SlotDepth", SLOT_DEPTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped revolve profile on the Right plane: sketch (u, v) maps to model
    # (-Z, Y), so the head top (Z5.5) is u = -5.5 and the tip runs to +u.
    profile = SketchDims()
    u_top = -HEAD_TOP_Z
    u_tip = u_top + OVERALL_LENGTH
    check("create_sketch screw profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "screw axis centerline", await adapter.add_centerline(u_top, 0.0, u_tip, 0.0)
    )
    points = [
        (u_top, 0.0),
        (u_top, HEAD_R),
        (u_top + HEAD_LENGTH, HEAD_R),
        (u_top + HEAD_LENGTH, SHOULDER_R),
        (u_top + HEAD_LENGTH + SHOULDER_LENGTH, SHOULDER_R),
        (u_top + HEAD_LENGTH + SHOULDER_LENGTH, THREAD_R),
        (u_tip - TIP_CHAMFER, THREAD_R),
        (u_tip, THREAD_R - TIP_CHAMFER),
        (u_tip, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (u0, v0), (u1, v1) = points[index], points[(index + 1) % len(lines)]
        if u0 != u1 and v0 != v1:
            continue  # the 45-degree tip chamfer; its two legs define it
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"screw profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    head_outline, shoulder_outline, thread_outline = lines[1], lines[3], lines[5]
    tip_chamfer, tip_face = lines[6], lines[7]
    # The head-top centre sits at the frame's HEAD_TOP_Z.
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", u_top, 0.0, "screw head-top centre"
    )
    profile.record("HeadTop", '"HeadTop"')
    # The head length from the faced head top; the stack lengths from the
    # underhead, the face that clamps the washer.
    for name, start, end, value in (
        ("HeadLength", f"{head_outline}.start", f"{head_outline}.end", HEAD_LENGTH),
        ("ShoulderLength", f"{head_outline}.end", f"{shoulder_outline}.end", SHOULDER_LENGTH),
        ("UnderHeadLength", f"{head_outline}.end", f"{tip_face}.end", UNDER_HEAD_LENGTH),
    ):
        await dimension_between(
            adapter, start, end, "horizontal_distance", value, f"screw {name}"
        )
        profile.record(name, f'"{name}"')
    await dimension_between(
        adapter,
        f"{tip_chamfer}.start",
        f"{tip_chamfer}.end",
        "horizontal_distance",
        TIP_CHAMFER,
        "screw tip chamfer",
    )
    profile.record("TipChamfer", '"TipChamfer"')
    await dimension_between(
        adapter,
        f"{tip_chamfer}.start",
        f"{tip_chamfer}.end",
        "vertical_distance",
        TIP_CHAMFER,
        "screw tip chamfer rise",
    )
    profile.record("TipChamferRise", '"TipChamfer"')
    for name, line, u_mid, radius in (
        ("HeadDia", head_outline, u_top + HEAD_LENGTH / 2.0, HEAD_R),
        ("ShoulderDia", shoulder_outline, u_top + HEAD_LENGTH + SHOULDER_LENGTH / 2.0, SHOULDER_R),
        ("ThreadDia", thread_outline, u_top + HEAD_LENGTH + SHOULDER_LENGTH + THREAD_LENGTH / 2.0, THREAD_R),
    ):
        await add_diametric_linear_dimension(adapter, axis, line, (u_mid, radius + 4.0), name)
        profile.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "screw profile sketch")
    check("exit_sketch screw profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewProfile")
    drive_jobs += profile.apply(adapter, "ScrewProfile")
    check("revolve screw", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Screw")
    await volume_check(adapter, "turned shoulder screw", V_BODY, 0.005 * V_BODY)

    # Driver slot across the head top: sketched on a plane at the head top and
    # cut down into the head (a cut runs against the plane normal by default).
    check(
        "create_plane HeadTopPlane",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=HEAD_TOP_Z)
        ),
    )
    name_last_feature(adapter, "HeadTopPlane")
    plane_dim = name_dimensions(adapter, "HeadTopPlane", ["HeadTopStation"])
    drive_jobs.append((plane_dim[0], '"HeadTop"'))
    slot = SketchDims()
    check("create_sketch driver slot", await adapter.create_sketch("HeadTopPlane"))
    await define_centered_rectangle(
        adapter,
        SLOT_SPAN / 2.0,
        SLOT_WIDTH / 2.0,
        "driver slot",
        dims=slot,
        name_width="SlotSpan",
        name_depth="SlotWidth",
        drive_depth='"SlotWidth"',
    )
    await ensure_fully_defined(adapter, "driver slot sketch")
    check("exit_sketch driver slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    drive_jobs += slot.apply(adapter, "SlotProfile")
    check(
        "cut driver slot",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=SLOT_DEPTH)),
    )
    name_last_feature(adapter, "DriverSlot")
    drive_jobs.append((name_dimensions(adapter, "DriverSlot", ["SlotDepth"])[0], '"SlotDepth"'))
    # A cut the wrong way removes nothing: the volume is the direction check.
    await volume_check(adapter, "slotted screw", V_FINAL, 0.02 * V_SLOT)
    blank_reference_geometry(adapter, (("HeadTopPlane", "PLANE"),))

    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven slotted screw (equations neutral)", V_FINAL, 0.02 * V_SLOT
    )
    bodies = tuple(_early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"pivot screw: expected one solid body, found {len(bodies)}")

    # The lapped diameters are match-fitted (drawing notes): no model band.
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
