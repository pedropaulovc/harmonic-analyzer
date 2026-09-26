r"""Build MHA-139, the crank handle pivot screw (user ruling U33).

A made slotted shoulder screw turned from 3/8-in cold-finished rod.  The oak
handle MHA-022 spins on the Ø6 shoulder; the #8-32 thread screws into the
crank arm MHA-020's tapped through hole and the shoulder seats tight on the
arm face.  Dimensions and the derived fit facts live in
``crank_handle_pivot_screw_spec``.

Layout: one revolve about local +Z.  The slotted head face is at z=0; the head,
shoulder and threaded section follow in +Z, the threaded section opening
with a thread-relief groove against the seat face (a 45-degree lead from its
floor into the seat face) so a die runs out into air and the shoulder seats
tight, and closing with a 45-degree thread-start chamfer on the tip.  The driver slot is sketched on the Front
Plane (the head face) and cut 1.0 deep across the full head, running along
local X.  ``ArmSeat`` is a named plane on the shoulder's seat face and
``Axis1`` the screw axis, for the assembly mates.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_handle_pivot_screw.py
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
    check,
    define_centered_rectangle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
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
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from crank_handle_pivot_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HEAD_DIA,
    HEAD_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    OVERALL_LENGTH,
    RELIEF_DIA,
    RELIEF_END_STATION,
    RELIEF_LEAD,
    RELIEF_WIDTH,
    SEAT_STATION,
    SHOULDER_DIA,
    SHOULDER_DIA_BAND,
    SHOULDER_LENGTH,
    SHOULDER_LENGTH_TOL,
    SLOT_DEPTH,
    SLOT_WIDTH,
    SURFACE_FINISHES,
    THREAD_LENGTH,
    THREAD_LENGTH_BAND,
    THREAD_MODEL_DIA,
    TIP_CHAMFER,
)


PART_NAME = "crank-handle-pivot-screw"
# Reference sketches this part still saves shown (#880), each with its owner
# and why.  Delete an entry once the part hides that sketch; the release
# refuses to start while any part lists one (visibility_debt).
SHOWN_SKETCH_ALLOWANCES = {
    "StationReference": (
        "crankhub: carries the drawing's marked dimensions; hide it once "
        "the sheet imports them from the hidden sketch"
    ),
}
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

HEAD_R = HEAD_DIA / 2.0
SHOULDER_R = SHOULDER_DIA / 2.0
THREAD_R = THREAD_MODEL_DIA / 2.0
RELIEF_R = RELIEF_DIA / 2.0
# Over-length of the slot rectangle along X: it only has to clear the head.
SLOT_SPAN = HEAD_DIA + 2.0

V_TURNED = math.pi * (
    HEAD_R**2 * HEAD_LENGTH
    + SHOULDER_R**2 * SHOULDER_LENGTH
    + THREAD_R**2 * THREAD_LENGTH
)
# The thread-relief groove: the thread-major -> relief-floor annulus
# RELIEF_WIDTH long, less the 45-degree lead's corner triangle (legs
# RELIEF_LEAD, centroid RELIEF_R + RELIEF_LEAD/3 from the axis) left standing.
V_LEAD = math.pi * RELIEF_LEAD**2 * (RELIEF_R + RELIEF_LEAD / 3.0)
V_RELIEF = math.pi * (THREAD_R**2 - RELIEF_R**2) * RELIEF_WIDTH - V_LEAD
# The 45-degree thread-start chamfer: the tip corner triangle (legs
# TIP_CHAMFER, centroid THREAD_R - TIP_CHAMFER/3 from the axis) removed.
V_TIP_CHAMFER = math.pi * TIP_CHAMFER**2 * (THREAD_R - TIP_CHAMFER / 3.0)
V_BODY = V_TURNED - V_RELIEF - V_TIP_CHAMFER


def slot_strip_area(radius: float, width: float) -> float:
    """Plan area of a centred width-``width`` strip across a radius-``radius`` circle."""
    half = width / 2.0
    return 2.0 * (
        half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)
    )


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
    # document units (see build_crankshaft).
    for name, value in (
        ("HeadDia", HEAD_DIA),
        ("HeadLength", HEAD_LENGTH),
        ("ShoulderDia", SHOULDER_DIA),
        ("ShoulderLength", SHOULDER_LENGTH),
        ("ThreadDia", THREAD_MODEL_DIA),
        ("ThreadLength", THREAD_LENGTH),
        ("ReliefDia", RELIEF_DIA),
        ("ReliefWidth", RELIEF_WIDTH),
        ("ReliefLead", RELIEF_LEAD),
        ("TipChamfer", TIP_CHAMFER),
        ("SlotWidth", SLOT_WIDTH),
        ("SlotDepth", SLOT_DEPTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped revolve profile on the Right plane.  Right sketch (u, v) maps to
    # model (-Z, Y), so negative u runs from the head face (origin) toward the
    # thread tip in model +Z.
    profile = SketchDims()
    check("create_sketch screw profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "screw axis centerline",
        await adapter.add_centerline(0.0, 0.0, -OVERALL_LENGTH, 0.0),
    )
    # The thread-relief groove is part of the profile: the seat face steps down
    # to a 45-degree lead onto the relief floor, which runs to RELIEF_WIDTH
    # from the seat face before the flank rises to the thread major.
    points = [
        (0.0, 0.0),
        (0.0, HEAD_R),
        (-HEAD_LENGTH, HEAD_R),
        (-HEAD_LENGTH, SHOULDER_R),
        (-SEAT_STATION, SHOULDER_R),
        (-SEAT_STATION, RELIEF_R + RELIEF_LEAD),
        (-(SEAT_STATION + RELIEF_LEAD), RELIEF_R),
        (-RELIEF_END_STATION, RELIEF_R),
        (-RELIEF_END_STATION, THREAD_R),
        (-(OVERALL_LENGTH - TIP_CHAMFER), THREAD_R),
        (-OVERALL_LENGTH, THREAD_R - TIP_CHAMFER),
        (-OVERALL_LENGTH, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (u0, v0), (u1, v1) = points[index], points[(index + 1) % len(lines)]
        if u0 != u1 and v0 != v1:
            continue  # a 45-degree lead or chamfer; its two legs define it
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"screw profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    head_outline, shoulder_outline = lines[1], lines[3]
    relief_lead, relief_floor, thread_outline = lines[5], lines[6], lines[8]
    tip_chamfer = lines[9]
    # The threaded section is sized from the seat face to the tip, across the
    # relief; the relief width and the lead's axial leg from the seat face; the
    # tip chamfer's axial leg from the tip.
    for name, start, end, value in (
        ("HeadLength", f"{head_outline}.start", f"{head_outline}.end", HEAD_LENGTH),
        (
            "ShoulderLength",
            f"{shoulder_outline}.start",
            f"{shoulder_outline}.end",
            SHOULDER_LENGTH,
        ),
        ("ThreadLength", f"{relief_lead}.start", f"{tip_chamfer}.end", THREAD_LENGTH),
        ("ReliefWidth", f"{relief_lead}.start", f"{relief_floor}.end", RELIEF_WIDTH),
        ("ReliefLead", f"{relief_lead}.start", f"{relief_lead}.end", RELIEF_LEAD),
        ("TipChamfer", f"{tip_chamfer}.start", f"{tip_chamfer}.end", TIP_CHAMFER),
    ):
        await dimension_between(
            adapter, start, end, "horizontal_distance", value, f"screw {name}"
        )
        profile.record(name, f'"{name}"')
    # The lead's radial leg equals its axial leg by equation: 45 degrees.
    await dimension_between(
        adapter,
        f"{relief_lead}.start",
        f"{relief_lead}.end",
        "vertical_distance",
        RELIEF_LEAD,
        "screw relief lead rise",
    )
    profile.record("ReliefLeadRise", '"ReliefLead"')
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
        ("HeadDia", head_outline, -HEAD_LENGTH / 2.0, HEAD_R),
        (
            "ShoulderDia",
            shoulder_outline,
            -(HEAD_LENGTH + SHOULDER_LENGTH / 2.0),
            SHOULDER_R,
        ),
        (
            "ReliefDia",
            relief_floor,
            -(SEAT_STATION + RELIEF_WIDTH / 2.0),
            RELIEF_R,
        ),
        (
            "ThreadDia",
            thread_outline,
            -(RELIEF_END_STATION + OVERALL_LENGTH - TIP_CHAMFER) / 2.0,
            THREAD_R,
        ),
    ):
        await add_diametric_linear_dimension(
            adapter, axis, line, (u_mid, radius + 4.0), name
        )
        profile.record(name, f'"{name}"')
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", 0.0, 0.0, "screw head face centre"
    )
    await ensure_fully_defined(adapter, "screw profile sketch")
    check("exit_sketch screw profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewProfile")
    drive_jobs += profile.apply(adapter, "ScrewProfile")
    check("revolve screw", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Screw")
    await volume_check(
        adapter, "turned shoulder screw with thread relief and tip chamfer", V_BODY, 0.005 * V_BODY
    )

    # Straight driver slot across the full head, sketched on the head face
    # (Front Plane, z=0).  The rectangle runs along X past the head, so its only
    # manufacturing dimension is the vertical SlotWidth; the cut's blind depth
    # is SlotDepth.  A cut from a principal plane runs against its normal by
    # default, so it is reversed into the +Z head, exactly as build_crank_hub
    # cuts its bore from the Top Plane into its +Y body.
    slot = SketchDims()
    check("create_sketch driver slot", await adapter.create_sketch("Front"))
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
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SLOT_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "DriverSlot")
    slot_depth_dim = name_dimensions(adapter, "DriverSlot", ["SlotDepth"])
    drive_jobs += [(slot_depth_dim[0], '"SlotDepth"')]
    await volume_check(adapter, "slotted screw", V_FINAL, 0.02 * V_SLOT)

    # Drawing-only station reference: the overall length, printed as a
    # reference restatement for stock cut-off.  One construction line on the
    # axis of the Right plane (the side view's plane) whose single driving
    # dimension IS the printed value (policy rule 2), driven by the same
    # globals as the profile so no geometry moves.
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    overall_line = check(
        "overall reference line",
        await adapter.add_line(0.0, 0.0, -OVERALL_LENGTH, 0.0),
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
        adapter, f"{overall_line}.start", 0.0, 0.0, "overall reference head face"
    )
    await dimension_between(
        adapter,
        f"{overall_line}.start",
        f"{overall_line}.end",
        "horizontal_distance",
        OVERALL_LENGTH,
        "overall length reference",
    )
    stations.record("OverallLength", '"HeadLength" + "ShoulderLength" + "ThreadLength"')
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, "StationReference")
    drive_jobs += stations.apply(adapter, "StationReference")

    # Named seat plane on the shoulder's arm-seat face for the assembly mate.
    check(
        "create_plane ArmSeat",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=SEAT_STATION
            )
        ),
    )
    name_last_feature(adapter, "ArmSeat")
    seat_dim = name_dimensions(adapter, "ArmSeat", ["SeatStation"])
    drive_jobs += [(seat_dim[0], '"HeadLength" + "ShoulderLength"')]
    # Hidden but still selectable by name for the arm-seat mate.
    blank_reference_geometry(adapter, (("ArmSeat", "PLANE"),))

    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "screw axis")

    # Apply the deferred drive equations once the whole model exists, then
    # re-check neutrality: every equation evaluates to its as-built value.
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven slotted screw (equations neutral)", V_FINAL, 0.02 * V_SLOT
    )

    # Model-owned bands (policy rule 2): the running-fit shoulder and its
    # length, and the thread length that must stay inside the 8.0 arm.
    set_dimension_bilateral_tolerance(
        adapter, "ScrewProfile", "ShoulderDia", *deviations(SHOULDER_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "ScrewProfile", "ShoulderLength", SHOULDER_LENGTH_TOL
    )
    set_dimension_bilateral_tolerance(
        adapter, "ScrewProfile", "ThreadLength", *deviations(THREAD_LENGTH_BAND)
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
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
    return await save_part_and_images(
        adapter, PART_NAME, allowed_shown=SHOWN_SKETCH_ALLOWANCES
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
