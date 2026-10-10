r"""Build MHA-SM-004, the gooseneck counter-spring clamp screw.

A made slotted fillister screw turned from 1/2-in 12L14 round.  Its #6-32
shank threads into the gooseneck MHA-SM-001's tapped end plug and the
under-head face clamps the counter spring's upper eye against the plug face.
Sizes and bands live in ``sm_gooseneck_spring_screw_geom``; the print's
marks, places and notes in ``sm_gooseneck_spring_screw_spec``.

Layout (``sm_gooseneck_spring_screw_geom`` frame): axis Z, the under-head face
at z=0.  ``HeadProfile`` revolves the cylindrical head and its spherical
crown in +Z (apex at HEAD_H); ``ShankProfile`` revolves the shank in -Z,
opening with the die relief (a 45-degree lead from its floor into the
under-head face) and closing with a 45-degree tip chamfer.  The thread is
modelled as its basic major cylinder.  The driver slot is sketched on a plane
at the apex and cut SLOT_DEPTH down into the head along local X.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sm_gooseneck_spring_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    blank_sketch,
    check,
    define_centered_rectangle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from sm_gooseneck_spring_screw_geom import (
    CROWN_CENTER_Z,
    CROWN_RADIUS,
    CROWN_RISE,
    HEAD_CYL_H,
    HEAD_DIA,
    HEAD_H,
    LENGTH,
    MAJOR_DIA,
    OVERALL_LENGTH,
    RELIEF_DIA,
    RELIEF_DIA_TOL,
    RELIEF_LEAD,
    RELIEF_LEAD_TOL,
    RELIEF_WIDTH,
    SLOT_DEPTH,
    SLOT_FLOOR_Z,
    SLOT_WIDTH,
    TIP_CHAMFER,
    TIP_CHAMFER_BAND,
)
from sm_gooseneck_spring_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "sm-gooseneck-spring-screw"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

HEAD_R = HEAD_DIA / 2.0
THREAD_R = MAJOR_DIA / 2.0
RELIEF_R = RELIEF_DIA / 2.0
# Over-length of the slot rectangle along X: it only has to clear the head.
SLOT_SPAN = HEAD_DIA + 2.0

# Head: the cylinder plus the spherical cap of sagitta CROWN_RISE.
V_HEAD = math.pi * HEAD_R**2 * HEAD_CYL_H + (
    math.pi * CROWN_RISE**2 * (3.0 * CROWN_RADIUS - CROWN_RISE) / 3.0
)
# Shank: the major cylinder less the relief annulus (the lead's corner
# triangle, legs RELIEF_LEAD, centroid RELIEF_R + RELIEF_LEAD/3 out, stays)
# and the tip chamfer's corner triangle (centroid THREAD_R - TIP_CHAMFER/3).
V_LEAD = math.pi * RELIEF_LEAD**2 * (RELIEF_R + RELIEF_LEAD / 3.0)
V_RELIEF = math.pi * (THREAD_R**2 - RELIEF_R**2) * RELIEF_WIDTH - V_LEAD
V_TIP = math.pi * TIP_CHAMFER**2 * (THREAD_R - TIP_CHAMFER / 3.0)
V_SHANK = math.pi * THREAD_R**2 * LENGTH - V_RELIEF - V_TIP
V_BODY = V_HEAD + V_SHANK


def slot_strip_area(radius: float, width: float) -> float:
    """Plan area of a centred width-``width`` strip across a radius-``radius`` circle.

    A circle narrower than the strip lies wholly inside it."""
    half = width / 2.0
    if radius <= half:
        return math.pi * radius**2
    return 2.0 * (
        half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)
    )


def crown_radius_at(z: float) -> float:
    """Head radius at height ``z`` (under-head face z=0)."""
    if z <= HEAD_CYL_H:
        return HEAD_R
    return math.sqrt(max(CROWN_RADIUS**2 - (z - CROWN_CENTER_Z) ** 2, 0.0))


def slot_volume(steps: int = 4000) -> float:
    """Head material inside the slot strip above the slot floor.

    The cylindrical part is closed-form; the crown part integrates the strip
    area of each horizontal slice (midpoint rule)."""
    cylinder = slot_strip_area(HEAD_R, SLOT_WIDTH) * (HEAD_CYL_H - SLOT_FLOOR_Z)
    dz = CROWN_RISE / steps
    crown = sum(
        slot_strip_area(crown_radius_at(HEAD_CYL_H + (i + 0.5) * dz), SLOT_WIDTH)
        for i in range(steps)
    )
    return cylinder + crown * dz


V_SLOT = slot_volume()
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
        ("HeadDia", HEAD_DIA),
        ("HeadHeight", HEAD_H),
        ("CrownRise", CROWN_RISE),
        ("UnderHeadLength", LENGTH),
        ("ThreadDia", MAJOR_DIA),
        ("ReliefDia", RELIEF_DIA),
        ("ReliefWidth", RELIEF_WIDTH),
        ("ReliefLead", RELIEF_LEAD),
        ("TipChamfer", TIP_CHAMFER),
        ("SlotWidth", SLOT_WIDTH),
        ("SlotDepth", SLOT_DEPTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Head revolve on the Right plane: sketch (u, v) maps to model (-Z, Y), so
    # the head (+Z) lies at negative u, the apex at u = -HEAD_H.  Rim-to-apex
    # is the minor CCW arc about the crown centre on the axis.
    head = SketchDims()
    u_rim, u_apex, u_centre = -HEAD_CYL_H, -HEAD_H, -CROWN_CENTER_Z
    check("create_sketch head profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "head axis centerline", await adapter.add_centerline(u_apex, 0.0, 0.0, 0.0)
    )
    head_seat, head_side = await add_line_chain(
        adapter, [(0.0, 0.0), (0.0, HEAD_R), (u_rim, HEAD_R)], close=False
    )
    crown = check(
        "head crown arc",
        await adapter.add_arc(u_centre, 0.0, u_rim, HEAD_R, u_apex, 0.0),
    )
    head_close = check("head axis line", await adapter.add_line(u_apex, 0.0, 0.0, 0.0))
    set_sketch_direct_db(adapter, False)
    for line, relation in (
        (head_seat, "vertical"),
        (head_side, "horizontal"),
        (head_close, "horizontal"),
    ):
        check(
            f"head profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{head_seat}.start", 0.0, 0.0, "under-head face centre"
    )
    await dimension_between(
        adapter,
        f"{head_close}.start",
        f"{head_close}.end",
        "horizontal_distance",
        HEAD_H,
        "head height",
    )
    head.record("HeadHeight", '"HeadHeight"')
    await dimension_between(
        adapter,
        f"{head_side}.end",
        f"{head_close}.start",
        "horizontal_distance",
        CROWN_RISE,
        "crown rise",
    )
    head.record("CrownRise", '"CrownRise"')
    await add_diametric_linear_dimension(
        adapter, axis, head_side, (u_rim / 2.0, HEAD_R + 4.0), "HeadDia"
    )
    head.record("HeadDia", '"HeadDia"')
    check(
        "crown radius",
        await adapter.add_sketch_dimension(crown, None, "radial", CROWN_RADIUS),
    )
    head.record(
        "CrownRadius",
        '("HeadDia" / 2 * "HeadDia" / 2 + "CrownRise" * "CrownRise") / (2 * "CrownRise")',
    )
    await ensure_fully_defined(adapter, "head profile sketch")
    check("exit_sketch head profile", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check("revolve head", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Head")
    await volume_check(adapter, "crowned fillister head", V_HEAD, 0.005 * V_HEAD)

    # Shank revolve on the Right plane, toward +u (model -Z).  The under-head
    # face steps down a 45-degree lead onto the relief floor, which runs to
    # RELIEF_WIDTH before the flank rises to the thread major.
    shank = SketchDims()
    check("create_sketch shank profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    shank_axis = check(
        "shank axis centerline", await adapter.add_centerline(0.0, 0.0, LENGTH, 0.0)
    )
    points = [
        (0.0, 0.0),
        (0.0, RELIEF_R + RELIEF_LEAD),
        (RELIEF_LEAD, RELIEF_R),
        (RELIEF_WIDTH, RELIEF_R),
        (RELIEF_WIDTH, THREAD_R),
        (LENGTH - TIP_CHAMFER, THREAD_R),
        (LENGTH, THREAD_R - TIP_CHAMFER),
        (LENGTH, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (u0, v0), (u1, v1) = points[index], points[(index + 1) % len(lines)]
        if u0 != u1 and v0 != v1:
            continue  # a 45-degree lead or chamfer; its two legs define it
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"shank profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    relief_lead, relief_floor, thread_outline = lines[1], lines[2], lines[4]
    tip_chamfer = lines[5]
    # Every axial size reads from the under-head face, the clamp face.
    for name, start, end, value in (
        ("UnderHeadLength", f"{relief_lead}.start", f"{tip_chamfer}.end", LENGTH),
        ("ReliefWidth", f"{relief_lead}.start", f"{relief_floor}.end", RELIEF_WIDTH),
        ("ReliefLead", f"{relief_lead}.start", f"{relief_lead}.end", RELIEF_LEAD),
        ("TipChamfer", f"{tip_chamfer}.start", f"{tip_chamfer}.end", TIP_CHAMFER),
    ):
        await dimension_between(
            adapter, start, end, "horizontal_distance", value, f"shank {name}"
        )
        shank.record(name, f'"{name}"')
    # The radial legs equal the axial legs by equation: 45 degrees.
    for name, line, value in (
        ("ReliefLead", relief_lead, RELIEF_LEAD),
        ("TipChamfer", tip_chamfer, TIP_CHAMFER),
    ):
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            "vertical_distance",
            value,
            f"shank {name} rise",
        )
        shank.record(f"{name}Rise", f'"{name}"')
    for name, line, u_mid, radius in (
        ("ReliefDia", relief_floor, (RELIEF_LEAD + RELIEF_WIDTH) / 2.0, RELIEF_R),
        (
            "ThreadDia",
            thread_outline,
            (RELIEF_WIDTH + LENGTH - TIP_CHAMFER) / 2.0,
            THREAD_R,
        ),
    ):
        await add_diametric_linear_dimension(
            adapter, shank_axis, line, (u_mid, radius + 4.0), name
        )
        shank.record(name, f'"{name}"')
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", 0.0, 0.0, "shank under-head centre"
    )
    await ensure_fully_defined(adapter, "shank profile sketch")
    check("exit_sketch shank profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank.apply(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shank")
    await volume_check(
        adapter,
        "turned fillister screw with relief and tip chamfer",
        V_BODY,
        0.005 * V_BODY,
    )

    # Driver slot across the crown: sketched on a plane at the apex and cut
    # down into the head (a cut runs against the plane normal by default).
    check(
        "create_plane SlotPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=HEAD_H
            )
        ),
    )
    name_last_feature(adapter, "SlotPlane")
    plane_dim = name_dimensions(adapter, "SlotPlane", ["ApexStation"])
    drive_jobs.append((plane_dim[0], '"HeadHeight"'))
    slot = SketchDims()
    check("create_sketch driver slot", await adapter.create_sketch("SlotPlane"))
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
    drive_jobs.append(
        (name_dimensions(adapter, "DriverSlot", ["SlotDepth"])[0], '"SlotDepth"')
    )
    # A cut the wrong way removes nothing: the volume is the direction check.
    await volume_check(adapter, "slotted fillister screw", V_FINAL, 0.02 * V_SLOT)
    blank_reference_geometry(adapter, (("SlotPlane", "PLANE"),))

    # Drawing-only station reference: the apex-to-tip overall, printed as a
    # reference for stock cut-off.  One construction line on the axis of the
    # Right plane whose single length dimension IS the printed value (policy
    # rule 2), driven by the same globals so no geometry moves.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    overall_line = check(
        "overall reference line",
        await adapter.add_line(u_apex, 0.0, LENGTH, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[overall_line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("overall reference line did not take construction flag")
    check(
        "overall reference horizontal",
        await adapter.add_sketch_constraint(overall_line, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter, f"{overall_line}.start", u_apex, 0.0, "overall reference apex"
    )
    stations.record("ApexReference", '"HeadHeight"')
    await dimension_between(
        adapter,
        f"{overall_line}.start",
        f"{overall_line}.end",
        "horizontal_distance",
        OVERALL_LENGTH,
        "overall length reference",
    )
    stations.record("OverallLength", '"HeadHeight" + "UnderHeadLength"')
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")

    # Apply the deferred drive equations once the whole model exists, then
    # re-check neutrality: every equation evaluates to its as-built value.
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven slotted screw (equations neutral)", V_FINAL, 0.02 * V_SLOT
    )
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"spring screw: expected one solid body, found {len(bodies)}"
        )

    # Model-owned bands (policy rule 2): the relief diameter keeps the die's
    # run-out under the thread root, the relief lead prints as limits on the
    # relief callout, and the tip chamfer is too small to ride the .XX band.
    # Every other mark takes the title block's two-place band.
    set_dimension_symmetric_tolerance(
        adapter, "ShankProfile", "ReliefDia", RELIEF_DIA_TOL
    )
    set_dimension_symmetric_tolerance(
        adapter, "ShankProfile", "ReliefLead", RELIEF_LEAD_TOL
    )
    set_dimension_bilateral_tolerance(
        adapter, "ShankProfile", "TipChamfer", *deviations(TIP_CHAMFER_BAND)
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # The reference sketch owns printed dimensions but no geometry: hide it so
    # no assembly instance renders it (#880).  The drawing shows it per view
    # through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "StationReference")
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
