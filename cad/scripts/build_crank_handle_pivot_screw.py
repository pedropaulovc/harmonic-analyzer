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

import _config
from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    active_configuration_name,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    assert_saved_configurations_regenerate,
    blank_sketch,
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
from _configuration_material import require_material_in_every_configuration
from _fit_limits import deviations
from _grouped_bom_properties import apply_grouped_bom_properties
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from crank_handle_pivot_screw_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    HEAD_DIA,
    HEAD_DIA_TOL,
    HEAD_LENGTH,
    INSTALLED_CONFIG,
    INSTALLED_THREAD_LENGTH,
    INSTALLED_TIP_CHAMFER,
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
    SLOT_DEPTH,
    SLOT_DEPTH_TOL,
    SLOT_WIDTH,
    SURFACE_FINISHES,
    THREAD_LENGTH,
    THREAD_LENGTH_BAND,
    THREAD_MODEL_DIA,
    TIP_CHAMFER,
    TIP_CHAMFER_BAND,
)


PART_NAME = "crank-handle-pivot-screw"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

HEAD_R = HEAD_DIA / 2.0
SHOULDER_R = SHOULDER_DIA / 2.0
THREAD_R = THREAD_MODEL_DIA / 2.0
RELIEF_R = RELIEF_DIA / 2.0
# Over-length of the slot rectangle along X: it only has to clear the head.
SLOT_SPAN = HEAD_DIA + 2.0

# The thread-relief groove: the thread-major -> relief-floor annulus
# RELIEF_WIDTH long, less the 45-degree lead's corner triangle (legs
# RELIEF_LEAD, centroid RELIEF_R + RELIEF_LEAD/3 from the axis) left standing.
V_LEAD = math.pi * RELIEF_LEAD**2 * (RELIEF_R + RELIEF_LEAD / 3.0)
V_RELIEF = math.pi * (THREAD_R**2 - RELIEF_R**2) * RELIEF_WIDTH - V_LEAD


def turned_volume(thread_length: float, tip_chamfer: float) -> float:
    """Revolved body volume for a threaded section and tip chamfer.

    The 45-degree tip chamfer removes the corner triangle (legs
    ``tip_chamfer``, centroid ``THREAD_R - tip_chamfer/3`` from the axis).
    """
    turned = math.pi * (
        HEAD_R**2 * HEAD_LENGTH
        + SHOULDER_R**2 * SHOULDER_LENGTH
        + THREAD_R**2 * thread_length
    )
    chamfer = math.pi * tip_chamfer**2 * (THREAD_R - tip_chamfer / 3.0)
    return turned - V_RELIEF - chamfer


V_BODY = turned_volume(THREAD_LENGTH, TIP_CHAMFER)


def slot_strip_area(radius: float, width: float) -> float:
    """Plan area of a centred width-``width`` strip across a radius-``radius`` circle."""
    half = width / 2.0
    return 2.0 * (
        half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)
    )


V_SLOT = slot_strip_area(HEAD_R, SLOT_WIDTH) * SLOT_DEPTH
V_FINAL = V_BODY - V_SLOT
V_INSTALLED = turned_volume(INSTALLED_THREAD_LENGTH, INSTALLED_TIP_CHAMFER) - V_SLOT


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
        SetGlobalVariableParameters,
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
    # The under-head face located from the TIP, the one faced end every axial
    # location reads from (MHA-139 re-reviews): the seat is the thread length
    # from the tip, the under-head face this reference -- the shoulder is
    # turned to suit the bonded handle -- and the head face the overall.  It
    # runs at mid-height of the under-head annulus so its head end sits on
    # that face.
    under_head_v = -(SHOULDER_R + HEAD_R) / 2.0
    set_sketch_direct_db(adapter, True)
    under_head_line = check(
        "under-head location reference line",
        await adapter.add_line(-OVERALL_LENGTH, under_head_v, -HEAD_LENGTH, under_head_v),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[under_head_line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("under-head location reference line did not take construction flag")
    check(
        "under-head location reference horizontal",
        await adapter.add_sketch_constraint(under_head_line, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter,
        f"{under_head_line}.start",
        -OVERALL_LENGTH,
        under_head_v,
        "under-head location from the tip",
    )
    stations.record(
        "UnderHeadTipX", '"HeadLength" + "ShoulderLength" + "ThreadLength"'
    )
    stations.record("UnderHeadY", '( "ShoulderDia" + "HeadDia" ) / 4')
    await dimension_between(
        adapter,
        f"{under_head_line}.start",
        f"{under_head_line}.end",
        "horizontal_distance",
        OVERALL_LENGTH - HEAD_LENGTH,
        "under-head location reference",
    )
    stations.record("UnderHeadLocation", '"ShoulderLength" + "ThreadLength"')
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
    set_dimension_symmetric_tolerance(adapter, "ScrewProfile", "HeadDia", HEAD_DIA_TOL)
    # The two small features the MHA-139 re-review found could print as
    # nothing at .X: the tip chamfer and the slot depth.
    set_dimension_bilateral_tolerance(
        adapter, "ScrewProfile", "TipChamfer", *deviations(TIP_CHAMFER_BAND)
    )
    set_dimension_symmetric_tolerance(adapter, "DriverSlot", "SlotDepth", SLOT_DEPTH_TOL)
    set_dimension_bilateral_tolerance(
        adapter, "ScrewProfile", "ThreadLength", *deviations(THREAD_LENGTH_BAND)
    )

    # Every model edit -- the material, the appearance, the drawing marks, the
    # PMI and the hidden reference sketch -- precedes the INSTALLED split, so
    # the split copies a finished default (the MHA-135 lesson: an edit after
    # it touches the active configuration only and leaves the other stale).
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    # The reference sketch owns printed dimensions but no geometry: hide it so
    # no assembly instance renders it (#880).  The drawing shows it per view
    # through _drawing_hidden_sketches to import those dimensions.
    blank_sketch(adapter, "StationReference")

    # Installed configuration (user ruling 2026-09-29): the drive train places
    # the screw as assembly leaves it, its tip filed flush with the arm's
    # inboard face and the edge broken.  The default stays the as-turned
    # screw the drawing prints; both carry one MHA-139 BOM identity.  The two
    # globals are set per configuration in each, so neither inherits the
    # other's value.
    default_config = active_configuration_name(adapter)
    check(
        f"create_configuration {INSTALLED_CONFIG}",
        await adapter.create_configuration(
            CreateConfigurationParameters(
                name=INSTALLED_CONFIG,
                comment="tip filed flush with the arm's inboard face",
            )
        ),
    )
    for name, thread_length, tip_chamfer in (
        (default_config, THREAD_LENGTH, TIP_CHAMFER),
        (INSTALLED_CONFIG, INSTALLED_THREAD_LENGTH, INSTALLED_TIP_CHAMFER),
    ):
        for global_name, value in (
            ("ThreadLength", thread_length),
            ("TipChamfer", tip_chamfer),
        ):
            check(
                f"{global_name} = {value} in {name}",
                await adapter.set_global_variable(
                    SetGlobalVariableParameters(
                        name=global_name, expression=f"{value}mm", configuration=name
                    )
                ),
            )
    check(
        f"activate {INSTALLED_CONFIG}",
        await adapter.set_active_configuration(INSTALLED_CONFIG),
    )
    await force_rebuild(adapter)
    await volume_check(adapter, "installed screw (tip filed flush)", V_INSTALLED, 0.02 * V_SLOT)
    check(
        f"re-activate {default_config}",
        await adapter.set_active_configuration(default_config),
    )
    await force_rebuild(adapter)
    await volume_check(adapter, "as-turned screw (default)", V_FINAL, 0.02 * V_SLOT)
    # The configuration description wins over the drive-train BOM's written
    # cell, so it is the text that BOM prints (the MHA-135 precedent).
    grouped_spec = _config.parts(PART_NAME)
    apply_grouped_bom_properties(
        adapter,
        [default_config, INSTALLED_CONFIG],
        part_number=str(grouped_spec["number"]),
        description=str(grouped_spec["description"]),
    )
    await report_mass_properties(adapter)
    require_material_in_every_configuration(
        adapter, PART_NAME, MATERIAL, (default_config, INSTALLED_CONFIG)
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    # The drive train places INSTALLED while the part saves on its default, so
    # INSTALLED's saved cache is what it rebuilds.  Reopen and prove it the way
    # the assembly loads it (cg-fx1).
    part_title = str(_early_bound(adapter.currentModel, "IModelDoc2").GetTitle())
    adapter.swApp.CloseDoc(part_title)
    adapter.currentModel = None
    check(
        f"reopen saved {PART_NAME}", await adapter.open_model(artefacts["part"])
    )
    assert_saved_configurations_regenerate(adapter, PART_NAME)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
