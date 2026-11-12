r"""Build MHA-DT-32, the crank handle pivot screw (user ruling U33).

A made slotted shoulder screw turned from 3/8-in cold-finished rod.  The oak
handle MHA-DT-08 spins on the Ø6 shoulder; the #8-32 thread screws into the
crank arm MHA-DT-06's tapped through hole and the shoulder seats tight on the
arm face.  Dimensions and the derived fit facts live in
``dt_crank_handle_pivot_screw_spec``.

Layout: one revolve about local +Z.  The slotted head face is at z=0; the head,
shoulder and threaded section follow in +Z, the threaded section opening
with a thread-relief groove against the seat face (a 45-degree lead from its
floor into the seat face) so a die runs out into air and the shoulder seats
tight, and closing with a 45-degree thread-start chamfer on the tip.  The head
meets the shoulder in a tangent under-head radius, and its outer under-head
edge carries a 45-degree break (``dt_crank_handle_head_seat_spec``, #1757), so
the head seats flat on the MHA-DT-35 floor.  The driver slot is sketched on the Front
Plane (the head face) and cut 1.0 deep across the full head, running along
local X.  ``ArmSeat`` is a named plane on the shoulder's seat face and
``Axis1`` the screw axis, for the assembly mates.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_handle_pivot_screw.py
"""

from __future__ import annotations

import math
import sys

import _config
from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import (
    active_configuration_name,
    assert_saved_configurations_regenerate,
    force_rebuild,
)
from _limit_tolerance import set_limits
from _session import run_build
from _single_limit_tolerance import set_single_limit
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_rectangle import define_centered_rectangle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _configuration_material import require_material_in_every_configuration
from _fit_deviations import deviations
from _grouped_bom_properties import apply_grouped_bom_properties
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from dt_crank_handle_head_seat_spec import (
    HEAD_CHAMFER,
    HEAD_CHAMFER_LIMITS,
    SCREW_DRAWING_DIMENSIONS as DRAWING_DIMENSIONS,
    SCREW_DRAWING_PRECISION as DRAWING_PRECISION,
    UNDER_HEAD_RADIUS_BAND,
    UNDER_HEAD_RADIUS_MAX,
    UNDER_HEAD_RADIUS_TOL_TYPE,
)
from dt_crank_handle_pivot_screw_spec import (
    HEAD_DIA,
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
    SLOT_WIDTH,
    SURFACE_FINISHES,
    THREAD_LENGTH,
    THREAD_MODEL_DIA,
    TIP_CHAMFER,
    TIP_CHAMFER_BAND,
    TIP_CHAMFER_TOL_TYPE,
    UNIT,
)


PART_NAME = "dt-crank-handle-pivot-screw"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

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
# The head seat (#1757).  The under-head radius fills the square outside a
# quarter disk at the shoulder: area R^2(1 - pi/4), first radial moment about
# the shoulder surface R^3(10 - 3 pi)/12 (Pappus).  The head's 45-degree break
# removes its corner triangle (legs HEAD_CHAMFER, centroid HEAD_R -
# HEAD_CHAMFER/3 from the axis).
_R = UNDER_HEAD_RADIUS_MAX
V_UNDER_HEAD_RADIUS = 2.0 * math.pi * (
    SHOULDER_R * _R**2 * (1.0 - math.pi / 4.0) + _R**3 * (10.0 - 3.0 * math.pi) / 12.0
)
V_HEAD_CHAMFER = math.pi * HEAD_CHAMFER**2 * (HEAD_R - HEAD_CHAMFER / 3.0)


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
    return turned - V_RELIEF - chamfer + V_UNDER_HEAD_RADIUS - V_HEAD_CHAMFER


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
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_dt_crankshaft).
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
        ("HeadChamfer", HEAD_CHAMFER),
        ("UnderHeadRadius", UNDER_HEAD_RADIUS_MAX),
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
    # from the seat face before the flank rises to the thread major.  The head
    # seat (#1757): the head's OD breaks 45 degrees onto the flat under-head
    # face, which runs down into a tangent quarter arc onto the shoulder.
    round_r = UNDER_HEAD_RADIUS_MAX
    round_center = (-(HEAD_LENGTH + round_r), SHOULDER_R + round_r)
    round_on_shoulder = (-(HEAD_LENGTH + round_r), SHOULDER_R)
    round_on_face = (-HEAD_LENGTH, SHOULDER_R + round_r)
    head_points = [
        (0.0, 0.0),
        (0.0, HEAD_R),
        (-(HEAD_LENGTH - HEAD_CHAMFER), HEAD_R),
        (-HEAD_LENGTH, HEAD_R - HEAD_CHAMFER),
        round_on_face,
    ]
    shank_points = [
        round_on_shoulder,
        (-SEAT_STATION, SHOULDER_R),
        (-SEAT_STATION, RELIEF_R + RELIEF_LEAD),
        (-(SEAT_STATION + RELIEF_LEAD), RELIEF_R),
        (-RELIEF_END_STATION, RELIEF_R),
        (-RELIEF_END_STATION, THREAD_R),
        (-(OVERALL_LENGTH - TIP_CHAMFER), THREAD_R),
        (-OVERALL_LENGTH, THREAD_R - TIP_CHAMFER),
        (-OVERALL_LENGTH, 0.0),
        head_points[0],
    ]
    head_lines = await add_line_chain(adapter, head_points, close=False)
    # add_arc is CCW: shoulder -> face is the 90-degree arc, not the
    # 270-degree complement (build_dt_crank_handle_butt_cup's floor round).
    under_head_round = check(
        "under-head round",
        await adapter.add_arc(*round_center, *round_on_shoulder, *round_on_face),
    )
    shank_lines = await add_line_chain(adapter, shank_points, close=False)
    set_sketch_direct_db(adapter, False)
    for line, (u0, v0), (u1, v1) in (
        *zip(head_lines, head_points, head_points[1:], strict=True),
        *zip(shank_lines, shank_points, shank_points[1:], strict=True),
    ):
        if u0 != u1 and v0 != v1:
            continue  # a 45-degree lead or chamfer; its two legs define it
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"screw profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    head_face, head_outline, head_chamfer, under_head_face = head_lines
    shoulder_outline = shank_lines[0]
    relief_lead, relief_floor, thread_outline = shank_lines[2], shank_lines[3], shank_lines[5]
    tip_chamfer = shank_lines[6]
    # The threaded section is sized from the seat face to the tip, across the
    # relief; the relief width and the lead's axial leg from the seat face; the
    # tip chamfer's axial leg from the tip.
    for name, start, end, value in (
        # Head face to the flat under-head face, and that face to the seat:
        # both stations stand on the flat face, past the break and the round.
        ("HeadLength", f"{head_face}.end", f"{under_head_face}.start", HEAD_LENGTH),
        (
            "ShoulderLength",
            f"{under_head_face}.end",
            f"{shoulder_outline}.end",
            SHOULDER_LENGTH,
        ),
        ("ThreadLength", f"{relief_lead}.start", f"{tip_chamfer}.end", THREAD_LENGTH),
        ("ReliefWidth", f"{relief_lead}.start", f"{relief_floor}.end", RELIEF_WIDTH),
        ("ReliefLead", f"{relief_lead}.start", f"{relief_lead}.end", RELIEF_LEAD),
        ("TipChamfer", f"{tip_chamfer}.start", f"{tip_chamfer}.end", TIP_CHAMFER),
        ("HeadChamfer", f"{head_chamfer}.start", f"{head_chamfer}.end", HEAD_CHAMFER),
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
    await dimension_between(
        adapter,
        f"{head_chamfer}.start",
        f"{head_chamfer}.end",
        "vertical_distance",
        HEAD_CHAMFER,
        "screw head chamfer rise",
    )
    profile.record("HeadChamferRise", '"HeadChamfer"')
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
    check(
        "under-head radius",
        await adapter.add_sketch_dimension(
            under_head_round, None, "radial", UNDER_HEAD_RADIUS_MAX
        ),
    )
    profile.record("UnderHeadRadius", '"UnderHeadRadius"')
    for first, second, label in (
        (under_head_face, under_head_round, "under-head face"),
        (under_head_round, shoulder_outline, "shoulder"),
    ):
        check(
            f"under-head round tangent to {label}",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )
    await anchor_point_to_origin(
        adapter, f"{head_face}.start", 0.0, 0.0, "screw head face centre"
    )
    await ensure_fully_defined(adapter, "screw profile sketch")
    check("exit_sketch screw profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewProfile")
    drive_jobs += profile.apply(adapter, "ScrewProfile")
    check("revolve screw", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Screw")
    await volume_check(
        adapter,
        "turned shoulder screw with thread relief, tip chamfer and head seat",
        V_BODY,
        0.005 * V_BODY,
    )

    # Straight driver slot across the full head, sketched on the head face
    # (Front Plane, z=0).  The rectangle runs along X past the head, so its only
    # manufacturing dimension is the vertical SlotWidth; the cut's blind depth
    # is SlotDepth.  A cut from a principal plane runs against its normal by
    # default, so it is reversed into the +Z head, exactly as build_dt_crank_hub
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
    # dimension IS the printed value (drawing-simplicity-policy.md `How the repository implements the guidelines`), driven by the same
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

    # Model-owned bands (drawing-simplicity-policy.md `How the repository
    # implements the guidelines`): the running-fit shoulder, and the tip
    # chamfer's single limit .015 MAX (#290 review of b28d38a16).  The relief
    # diameter, the relief lead (detail A), the thread length and the head and
    # slot sizes print under the title block's bands (#2314).
    set_dimension_bilateral_tolerance(
        adapter, "ScrewProfile", "ShoulderDia", *deviations(SHOULDER_DIA_BAND),
        display_unit=UNIT,
    )
    set_single_limit(
        adapter,
        "ScrewProfile",
        "TipChamfer",
        limit=TIP_CHAMFER,
        band=TIP_CHAMFER_BAND,
        tol_type=TIP_CHAMFER_TOL_TYPE,
    )
    # The head seat (#1757): the under-head radius as its single limit
    # R.004 MAX, the head's break as its two limits.
    set_single_limit(
        adapter,
        "ScrewProfile",
        "UnderHeadRadius",
        limit=UNDER_HEAD_RADIUS_MAX,
        band=UNDER_HEAD_RADIUS_BAND,
        tol_type=UNDER_HEAD_RADIUS_TOL_TYPE,
    )
    set_limits(
        adapter,
        "ScrewProfile",
        "HeadChamfer",
        limits=HEAD_CHAMFER_LIMITS,
        places=DRAWING_PRECISION["ScrewProfile"]["HeadChamfer"],
        display_unit=UNIT,
    )

    # Every model edit -- the material, the appearance, the drawing marks, the
    # PMI and the hidden reference sketch -- precedes the INSTALLED split, so
    # the split copies a finished default (the MHA-DT-30 lesson: an edit after
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
    # screw the drawing prints; both carry one MHA-DT-32 BOM identity.  The two
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
    # cell, so it is the text that BOM prints (the MHA-DT-30 precedent).
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
        {"Isometric View Note": ISOMETRIC_VIEW_NOTE},
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
