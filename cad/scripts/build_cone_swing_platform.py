r"""Reproduction script: cone swing platform (book ch. 12, p. 18 "pivot").

The wedge-shaped plate the whole cone-gear set rides on. The book's
top-down photo (p. 18) labels the TIP end "pivot": the merged green
column (big-end journal + crank pedestal, ONE casting), the cone shaft
and the tip adjuster-carrier block all stand ON this plate, and the whole unit --
crank, 16T pinion, chain wheel included -- swings horizontally about a
vertical axis near the shaft's thin tip to dis/engage the cone set from
the cylinder set (video 4/4, engage/disengage stills). Swing separation
grows with distance from the pivot, so pivoting at the TIP gives the
big-end gears the largest throw.

Plan shape is the p.18 wedge, ASYMMETRIC about the shaft line: the east
side tapers 16 -> 24 half-width, the west side flares 8 -> 37 so the
run from the swing pivot to the cone-lock-knob is SOLID plate (no lobe
protrusion); the open LOCK NOTCH cuts straight into the west edge. The
four plan corners are rounded, echoing the hardware each sits beside
(pivot screw head at the north end, the green column at the south-east,
the lock-knob head at the south-west). A native close-clearance Ø6.756 pivot
hole clears the stock Ø6.35 shoulder. A Ø10.50 x 0.25-deep top relief reduces
only the local bearing thickness to 6.10, preserving 0.25 running axial
clearance without lowering the plate or its mounted hardware.

The shortened envelope and paired 1/4-20 post mounts are the direct platform
cascade from ``cone-pivot-post-v2.SLDPRT``.  Its 42.011 mm casting foot is
centred at cone station -39.9014; the post's world-X hole pair is transformed
into this plate's engaged local frame so the two native tapped holes remain
coaxial after Ry(+12.5182 deg) placement.

The asymmetric flare keeps the part CHIRAL; the assembly places it at
Ry(+INCLINE), under which part-local +x tips machine WEST at the engaged
pose -- the west flare and notch are authored at +x (constants note below).

Named refs for the assembly: "swing pivot" (Axis1, vertical through the
origin), the CRANK AXIS (Axis2 -- the machine-z crank line the
crankshaft mates to, built from an angled plane so it swings WITH the
plate), and "PlateTop" (datum plane on the top face -- the riders'
seat mate).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_swing_platform.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
import sys
from typing import Any

from _common import (
    PANEL_BLACK,
    SketchDims,
    _early_bound,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    name_dimensions,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import wizard_holes
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from build_cone_lock_knob import HEAD_DIA as LOCK_HEAD_DIA
from cone_swing_platform_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FEATURE_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    NOTCH_VIEW_NOTE,
    PIVOT_BEARING_RELIEF_DEPTH,
    PIVOT_BEARING_RELIEF_DIAMETER,
    PIVOT_BEARING_THICKNESS,
    PIVOT_HOLE_DIA,
    PIVOT_HOLE_SPEC,
    PIVOT_HEAD_RADIAL_CLEARANCE,  # noqa: F401 -- public verify contract
    PIVOT_RELIEF_FIT_REQUIREMENT,
    PLATE_THICKNESS,
    POST_ATTACHMENT_SPACING,
    POST_BLOCK_DIA,
    POST_MOUNT_SPEC,
    POST_MOUNT_TAP_DIA,
    PROFILE_VIEW_NOTE,
    SURFACE_FINISHES,
)

PART_NAME = "cone-swing-platform"
MATERIAL = "Plain Carbon Steel"  # black-finished steel plate (p.18 dark wedge)

PLATE_T = PLATE_THICKNESS  # 1/4" plate
HALF_WIDTH_N = 16.0  # north (pivot/tip) half-width, EAST side (the lock-slot
# region keeps its full seat)
WEST_HALF_N = 8.0  # north half-width, WEST side.  The recentered north arbor
# pedestal otherwise clips the flared edge; 8.0 leaves 0.37 mm exact plan
# clearance while retaining the close photo relationship in ch12 img09.
EAST_HALF_S = 24.0  # widened for the v2 post's Ø42.011 casting foot
WEST_HALF_S = 37.0  # west half-width at the south end: the flare that makes
# the pivot -> lock-knob line solid plate (covers the notch seat + collar)
NORTH_OVERHANG = 7.0  # pivot -> north edge (plate continues past the pivot)
# Native 1/4-in close-clearance Hole Wizard feature over the stock Ø6.35
# shoulder; cone_swing_platform_spec owns its table identity and diameter.

THROUGH_CUT_DEPTH = 40.0  # mid-plane total (both_directions splits it half per
# side of the sketch plane); must exceed 2x any extent crossed
if abs(PLATE_T - PIVOT_BEARING_RELIEF_DEPTH - PIVOT_BEARING_THICKNESS) > 1e-9:
    raise AssertionError(
        "pivot bearing relief no longer leaves its specified thickness"
    )

INCLINE_DEG = 12.5182  # cone-axis plan incline (the assembly's ROT_Y_INCLINE)
_SIN_I = math.sin(math.radians(INCLINE_DEG))
_COS_I = math.cos(math.radians(INCLINE_DEG))

# --- cone-pivot-post-v2 attachment footprint -------------------------------
# The rederived casting is centred at cone station -39.90136099793 while the
# plate origin/pivot remains station 196.  Its two vertical attachment holes
# are a world-X pair at +/-13.44352 mm.  Undoing the engaged Ry(+INCLINE)
# placement gives this skewed pair in the platform's local (x, z) frame.
POST_STATION = -39.90136099793
PIVOT_STATION = 152.27232594770453
POST_MAIN_DIA = POST_BLOCK_DIA
POST_LOCAL_Z = POST_STATION - PIVOT_STATION
POST_SOUTH_MARGIN = 3.175  # 1/8 in clearance beyond the post's south rim
PLATE_SOUTH_Z = POST_LOCAL_Z - POST_MAIN_DIA / 2.0 - POST_SOUTH_MARGIN
PLATE_LEN = NORTH_OVERHANG - PLATE_SOUTH_Z
POST_MOUNT_HALF_PITCH = POST_ATTACHMENT_SPACING / 2.0
POST_MOUNT_X = POST_MOUNT_HALF_PITCH * _COS_I
POST_MOUNT_DZ = POST_MOUNT_HALF_PITCH * _SIN_I
POST_MOUNT_WEST_XZ = (POST_MOUNT_X, POST_LOCAL_Z + POST_MOUNT_DZ)
POST_MOUNT_EAST_XZ = (-POST_MOUNT_X, POST_LOCAL_Z - POST_MOUNT_DZ)

# Fail before COM if the v2 foot ever drifts off the tapered plate.  Distance
# is normal to each straight boundary, not merely an axis-aligned half-width.
_POST_R = POST_MAIN_DIA / 2.0
_POST_SOUTH_CLEAR = POST_LOCAL_Z - (NORTH_OVERHANG - PLATE_LEN)
_POST_FRAC = (NORTH_OVERHANG - POST_LOCAL_Z) / PLATE_LEN
_POST_EAST_HALF = HALF_WIDTH_N + (EAST_HALF_S - HALF_WIDTH_N) * _POST_FRAC
_POST_WEST_HALF = WEST_HALF_N + (WEST_HALF_S - WEST_HALF_N) * _POST_FRAC
_POST_EAST_NORMAL_CLEAR = _POST_EAST_HALF / math.hypot(
    1.0, (EAST_HALF_S - HALF_WIDTH_N) / PLATE_LEN
)
_POST_WEST_NORMAL_CLEAR = _POST_WEST_HALF / math.hypot(
    1.0, (WEST_HALF_S - WEST_HALF_N) / PLATE_LEN
)
POST_FOOT_CONTAINMENT = (
    min(_POST_SOUTH_CLEAR, _POST_EAST_NORMAL_CLEAR, _POST_WEST_NORMAL_CLEAR) - _POST_R
)
if POST_FOOT_CONTAINMENT < 0.25:
    raise AssertionError(
        f"v2 post foot has only {POST_FOOT_CONTAINMENT:.3f} mm platform containment"
    )
if POST_MOUNT_HALF_PITCH + POST_MOUNT_TAP_DIA / 2.0 > _POST_R:
    raise AssertionError("v2 post mount taps fall outside the casting foot")

# The open-ended lock notch cuts from the engaged stud seat straight out
# through the plate's WEST edge. The cone-lock-knob stud is fixed to the base;
# on disengage the plate swings until its edge passes the stud and collar.
# Tightened with no plate under it, the collar fences the mouth and locks the
# plate disengaged; tightened on the plate it clamps the engaged pose.
# The notch runs along the swing arc's CHORD: at R~192 over ~3 deg to the
# mouth the sagitta is ~0.07, absorbed by the O6.35-stud-in-8.0 clearance.
#
# LOCAL-FRAME CONVENTION: the assembly places this part at Ry(+INCLINE)
# (train._plate_local_to_machine), under which local +x maps to machine WEST
# at the engaged pose -- every west-side feature below (the flare, the lock
# notch) is authored at local +x, east-side features at local -x.
SLOT_W = 8.0  # Ø6.35 stud clearance plus chord-vs-arc slack
# The stock O25.4 head must clear both the O42.011 post foot and the nearby
# T120/64T gear row.  The northern solution beside the post clears the post but
# overlaps both gears; use the southern solution and move the stud west until
# the head retains the established 2 mm post gap with useful plate edge stock.
SLOT_E_X = 33.0
LOCK_HEAD_POST_CLEARANCE = 2.0
_LOCK_POST_C2C = LOCK_HEAD_DIA / 2.0 + POST_MAIN_DIA / 2.0 + LOCK_HEAD_POST_CLEARANCE
SLOT_E_Z = POST_LOCAL_Z - math.sqrt(_LOCK_POST_C2C**2 - SLOT_E_X**2)
SLOT_R = math.hypot(SLOT_E_X, SLOT_E_Z)
# The plate swings toward disengage (big end away from the drum), so in PLATE
# coords the fixed stud sweeps the INVERSE rotation: unit direction (-z, x)/R
# at E -- outward toward the west edge (+x), slightly north (+z).
_SLOT_TX, _SLOT_TZ = -SLOT_E_Z / SLOT_R, SLOT_E_X / SLOT_R


def _west_edge_x(z_local: float) -> float:
    """Authored x of the west taper edge at local z (linear 8 -> 37)."""
    return (
        WEST_HALF_N
        + (WEST_HALF_S - WEST_HALF_N) * (NORTH_OVERHANG - z_local) / PLATE_LEN
    )


def _chord_exit_travel(x0: float, z0: float) -> float:
    """Stud travel from (x0, z0) along the chord to the west taper edge."""
    # solve x0 + t*TX = _west_edge_x(z0 + t*TZ) for t (both sides linear)
    k = (WEST_HALF_S - WEST_HALF_N) / PLATE_LEN
    return (WEST_HALF_N + k * (NORTH_OVERHANG - z0) - x0) / (_SLOT_TX + k * _SLOT_TZ)


# Stud travel from the engaged seat to the mouth. Past this the stud is out of
# the plate; the shared hardware calculation adds the exact collar radius to
# derive the disengaged pose.
NOTCH_EXIT_TRAVEL = _chord_exit_travel(SLOT_E_X, SLOT_E_Z)
_MOUTH_OVERSHOOT = 4.0  # cut ends past the edge so the mouth opens clean
_SLOT_OUT_X = SLOT_E_X + (NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT) * _SLOT_TX
_SLOT_OUT_Z = SLOT_E_Z + (NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT) * _SLOT_TZ
# Plan angle of the notch run off the plate's east-west line (the run is the
# chord the stud follows, so it climbs north as it opens through the west
# edge).  Printed as a DRIVEN reference on the notch sketch; the chord itself
# is what the sketch geometry pins.
NOTCH_RUN_DEG = math.degrees(math.atan2(_SLOT_TZ, _SLOT_TX))
_NOTCH_ANGLE_RAY_MM = 20.0


async def _add_notch_run_angle(
    adapter: Any, run_line: str, vertex: tuple[float, float], dims: SketchDims
) -> None:
    """Author the notch run's plan angle as a driven dimension on its sketch.

    A horizontal construction ray leaves the run's closed-end corner toward
    the west; the angle between it and the run is the one the print carries.
    ``AddSpecificDimension`` picks whichever of the four angle regions holds
    its text point, so the text goes on the bisector inside the acute wedge,
    with sketch y in both the y and the -z slots (a Top-plane sketch's y is
    model -Z, and a z=0 point lands on the sketch x-axis, outside the wedge).
    The value is checked BEFORE it is made driven, so a supplement fails the
    build instead of printing 170 degrees.
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(_read_member(sketch_mgr, "AddToDB"))
    sketch_mgr.AddToDB = True
    try:
        ray = check(
            "add notch angle construction ray",
            await adapter.add_line(
                vertex[0], vertex[1], vertex[0] + _NOTCH_ANGLE_RAY_MM, vertex[1]
            ),
        )
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    ray_segment = _early_bound(adapter._sketch_entities[ray], "ISketchSegment")
    ray_segment.ConstructionGeometry = True
    if _read_member(ray_segment, "ConstructionGeometry") is not True:
        raise RuntimeError(
            "notch angle construction ray did not remain construction geometry"
        )
    check(
        "notch angle ray start -> run corner",
        await adapter.add_sketch_constraint(
            f"{ray}.start", f"{run_line}.start", "coincident"
        ),
    )
    check(
        "notch angle ray horizontal",
        await adapter.add_sketch_constraint(ray, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{ray}.start",
        f"{ray}.end",
        "horizontal_distance",
        _NOTCH_ANGLE_RAY_MM,
        "notch angle ray",
    )
    dims.record(None)

    half = math.radians(NOTCH_RUN_DEG / 2.0)
    text_x = (vertex[0] + _NOTCH_ANGLE_RAY_MM * math.cos(half)) / 1000.0
    text_y = (vertex[1] - _NOTCH_ANGLE_RAY_MM * math.sin(half)) / 1000.0
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [ray, run_line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_x,
        text_y,
        -text_y,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"notch run angle: AddSpecificDimension failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    expected_rad = math.radians(NOTCH_RUN_DEG)
    actual_rad = abs(float(_read_member(dimension, "SystemValue")))
    if abs(actual_rad - expected_rad) > 1e-8:
        raise RuntimeError(
            f"notch run angle measured {math.degrees(actual_rad):.6f} deg, "
            f"expected {NOTCH_RUN_DEG:.6f} deg"
        )
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(_read_member(dimension, "DrivenState")) != 1:
        raise RuntimeError("notch run angle did not become driven")
    dims.record("NotchRunAngle")


STOP_LOCAL_Z = -105.0


@dataclass(frozen=True, slots=True)
class SwingHardwareGeometry:
    """Shared machine-frame stations for the base-fixed lock and travel stop."""

    lock_xz: tuple[float, float]
    disengage_deg: float
    stop_contact_xz: tuple[float, float]
    stop_xz: tuple[float, float]
    stop_engaged_gap: float


def swing_hardware_geometry(
    pivot_xz: tuple[float, float],
    *,
    lock_collar_dia: float,
    stop_shank_dia: float,
) -> SwingHardwareGeometry:
    """Derive the lock seat and stop contact once from the platform outline."""
    if lock_collar_dia <= 0.0 or stop_shank_dia <= 0.0:
        raise ValueError("swing hardware diameters must be positive")

    def placed(x_local: float, z_local: float, angle_rad: float) -> tuple[float, float]:
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return (
            pivot_xz[0] + x_local * c + z_local * s,
            pivot_xz[1] - x_local * s + z_local * c,
        )

    incline_rad = math.radians(INCLINE_DEG)
    lock_xz = placed(SLOT_E_X, SLOT_E_Z, incline_rad)
    disengage_deg = math.degrees(
        (NOTCH_EXIT_TRAVEL + lock_collar_dia / 2.0 + 2.0) / SLOT_R
    )
    disengaged_rad = incline_rad + math.radians(disengage_deg)

    east_slope = (EAST_HALF_S - HALF_WIDTH_N) / PLATE_LEN
    stop_local_x = -(HALF_WIDTH_N + east_slope * (NORTH_OVERHANG - STOP_LOCAL_Z))
    edge_out_local = (-1.0, east_slope)
    edge_norm = math.hypot(*edge_out_local)
    edge_out_local = (
        edge_out_local[0] / edge_norm,
        edge_out_local[1] / edge_norm,
    )

    contact_xz = placed(stop_local_x, STOP_LOCAL_Z, disengaged_rad)
    c_dis, s_dis = math.cos(disengaged_rad), math.sin(disengaged_rad)
    edge_out_disengaged = (
        edge_out_local[0] * c_dis + edge_out_local[1] * s_dis,
        -edge_out_local[0] * s_dis + edge_out_local[1] * c_dis,
    )
    stop_xz = (
        contact_xz[0] + edge_out_disengaged[0] * stop_shank_dia / 2.0,
        contact_xz[1] + edge_out_disengaged[1] * stop_shank_dia / 2.0,
    )

    engaged_edge_xz = placed(stop_local_x, STOP_LOCAL_Z, incline_rad)
    edge_out_engaged = (
        edge_out_local[0] * _COS_I + edge_out_local[1] * _SIN_I,
        -edge_out_local[0] * _SIN_I + edge_out_local[1] * _COS_I,
    )
    stop_delta = (
        stop_xz[0] - engaged_edge_xz[0],
        stop_xz[1] - engaged_edge_xz[1],
    )
    engaged_gap = (
        stop_delta[0] * edge_out_engaged[0]
        + stop_delta[1] * edge_out_engaged[1]
        - stop_shank_dia / 2.0
    )
    return SwingHardwareGeometry(
        lock_xz=lock_xz,
        disengage_deg=disengage_deg,
        stop_contact_xz=contact_xz,
        stop_xz=stop_xz,
        stop_engaged_gap=engaged_gap,
    )


# --- rounded plan corners (item: they echo the neighbouring hardware) --------
# (authored x, local z, radius): north pair ~ the pivot screw head, south-east
# ~ the green column foot.  The south-west fillet is reduced around the
# relocated lock notch so the corner round and the closed seat do not overlap.
_CORNERS = (
    ("NE", -HALF_WIDTH_N, NORTH_OVERHANG, 10.0),
    ("NW", WEST_HALF_N, NORTH_OVERHANG, 8.0),
    ("SW", WEST_HALF_S, NORTH_OVERHANG - PLATE_LEN, 5.0),
    ("SE", -EAST_HALF_S, NORTH_OVERHANG - PLATE_LEN, 12.0),
)


def _corner_fillet_area(label: str, r: float) -> float:
    """Plan area a radius-r fillet removes at the named sharp corner."""
    idx = [c[0] for c in _CORNERS].index(label)
    x, z = _CORNERS[idx][1], _CORNERS[idx][2]
    xp, zp = _CORNERS[idx - 1][1], _CORNERS[idx - 1][2]
    xn, zn = _CORNERS[(idx + 1) % 4][1], _CORNERS[(idx + 1) % 4][2]
    v1 = (xp - x, zp - z)
    v2 = (xn - x, zn - z)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    theta = math.acos(dot / (math.hypot(*v1) * math.hypot(*v2)))
    return r * r * (1.0 / math.tan(theta / 2.0) - (math.pi - theta) / 2.0)


# --- crank axis (the machine-z crank line, carried BY the plate) -------------
# The merged column's crank bore is oblique geometry only; the KINEMATIC
# reference the crankshaft mates to is this named axis, so the crank rig
# swings with the plate. In the part-local frame the axis runs plan
# direction (-sin I, cos I) -- the direction the Ry(+INCLINE) placement maps
# to machine z (cf. cone-pivot-post) -- at height CRANK_AXIS_Y above the
# plate BOTTOM, passing the plan point (-CRANK_AXIS_OFF * cos I,
# -CRANK_AXIS_OFF * sin I) -- CRANK_AXIS_OFF is the distance the crank axis
# sits EAST of the pivot. This part-local separation is invariant under the
# v2 installation translation and is asserted against the live cone geometry
# in the assembly.
CRANK_AXIS_OFF = 41.6536661190548
CRANK_AXIS_Y = 79.05  # Y_CRANK 129.85 - Y_BASE_TOP 50.8 (above plate BOTTOM)
# Construction: a vertical REFERENCE AXIS through the crank axis's plan
# point (the foot of the pivot's perpendicular onto the axis line), built
# as the intersection of two principal-plane offsets -- name-selected and
# view-independent (a coordinate-picked model edge selects at the SCREEN
# projection and grabbed the notch rail's top edge instead of the vertical
# mouth edge, proven live). CrankAxisVert = "Right Plane" rotated INCLINE
# about that axis (so it CONTAINS the crank axis -- no offset step); the
# crank axis = that plane (x) the Top-offset plane at CRANK_AXIS_Y.
# CrankAxisSeat = "Front Plane" rotated the same way about the same axis,
# so it passes through CRANK_SEAT_ANCHOR -- the anchor the assembly's
# axial-distance mates reference (via _plate_local_to_machine; its machine
# point lands ON the crank axis, x = X_CRANK, asserted SolidWorks-free at
# assembly import). The angle's FLIP side is
# the one remaining EMPIRICAL sign -- flip on assembly crankshaft-mate
# verify failure.
CRANK_PLANE_ANGLE = INCLINE_DEG  # sign candidate (flip side)
CRANK_SEAT_ANCHOR = (-CRANK_AXIS_OFF * _COS_I, -CRANK_AXIS_OFF * _SIN_I)
# (part-local plan x, z) = (-49.92, -11.08); machine (-130.82, 103.29)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateAxisParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 214 = 214 in).
    await set_global(adapter, "PlateT", f"{PLATE_T}mm")
    await set_global(
        adapter, "PivotBearingReliefDia", f"{PIVOT_BEARING_RELIEF_DIAMETER}mm"
    )
    await set_global(
        adapter, "PivotBearingReliefDepth", f"{PIVOT_BEARING_RELIEF_DEPTH}mm"
    )
    await set_global(adapter, "HalfWidthN", f"{HALF_WIDTH_N}mm")
    await set_global(adapter, "WestHalfN", f"{WEST_HALF_N}mm")
    await set_global(adapter, "EastHalfS", f"{EAST_HALF_S}mm")
    await set_global(adapter, "WestHalfS", f"{WEST_HALF_S}mm")
    await set_global(adapter, "PlateLen", f"{PLATE_LEN}mm")
    await set_global(adapter, "NorthOverhang", f"{NORTH_OVERHANG}mm")
    # The pivot hole remains a native Hole Wizard 1/4 close-clearance feature;
    # its diameter and callout come from the table rather than a model global.
    await set_global(adapter, "SlotW", f"{SLOT_W}mm")
    await set_global(adapter, "PostLocalZ", f"{POST_LOCAL_Z}mm")
    await set_global(adapter, "PostMountX", f"{POST_MOUNT_X}mm")
    await set_global(adapter, "PostMountDZ", f"{POST_MOUNT_DZ}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Asymmetric trapezoid plan on the Top plane (sketch (x, y) -> part
    # (X, -Z)). The tapered side lines are sloped, so direct-to-DB keeps
    # inference from snapping them.  Every lateral corner offset is located
    # from the PIVOT (the sketch origin); the north station and conspicuous
    # overall length establish the two end edges without chaining feature
    # locations around the profile.
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    plan_pts = [
        (-HALF_WIDTH_N, -NORTH_OVERHANG),  # north-east (anchor)
        (WEST_HALF_N, -NORTH_OVERHANG),  # north-west (authored +x = west;
        # trimmed to clear the north arbor pedestal, PR8)
        (WEST_HALF_S, PLATE_LEN - NORTH_OVERHANG),  # south-west (flare)
        (-EAST_HALF_S, PLATE_LEN - NORTH_OVERHANG),  # south-east
    ]
    lines = await add_line_chain(adapter, plan_pts)
    set_sketch_direct_db(adapter, False)
    north_line, _west_line, south_line, _east_line = lines
    await anchor_point_to_origin(
        adapter, f"{north_line}.start", *plan_pts[0], "plate plan north-east"
    )
    plate.record("NorthEastX", '"HalfWidthN"')
    plate.record("NorthEdgeZ", '"NorthOverhang"')
    check(
        "horizontal plate north edge",
        await adapter.add_sketch_constraint(north_line, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{north_line}.end",
        "origin",
        "horizontal_distance",
        WEST_HALF_N,
        "plate plan north-west",
    )
    plate.record("NorthWestX", '"WestHalfN"')
    check(
        "horizontal plate south edge",
        await adapter.add_sketch_constraint(south_line, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{south_line}.start",
        "origin",
        "horizontal_distance",
        WEST_HALF_S,
        "plate plan south-west",
    )
    plate.record("SouthWestX", '"WestHalfS"')
    await dimension_between(
        adapter,
        f"{north_line}.start",
        f"{south_line}.start",
        "vertical_distance",
        PLATE_LEN,
        "plate overall length",
    )
    plate.record("PlateLenDim", '"PlateLen"')
    await dimension_between(
        adapter,
        f"{south_line}.end",
        "origin",
        "horizontal_distance",
        EAST_HALF_S,
        "plate plan south-east",
    )
    plate.record("SouthEastX", '"EastHalfS"')
    await ensure_fully_defined(adapter, "plate plan")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_T)),
    )
    name_last_feature(adapter, "Plate")
    plate_thk_dim = name_dimensions(adapter, "Plate", ["PlateThk"])
    drive_jobs += [(plate_thk_dim[0], '"PlateT"')]
    v_plate = (
        ((HALF_WIDTH_N + WEST_HALF_N) + (WEST_HALF_S + EAST_HALF_S))
        / 2.0
        * PLATE_LEN
        * PLATE_T
    )
    volume = await volume_check(adapter, "plate", v_plate, 0.005 * v_plate)

    # Pivot screw clearance hole at the origin: preserve the native Hole
    # Wizard 1/4 close-clearance feature used by this occasional setup pivot.
    # There is no measured evidence that its stock shoulder needs a tighter
    # running-bearing fit.
    pivot_dia = PIVOT_HOLE_DIA
    wizard_holes(
        adapter,
        PIVOT_HOLE_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        "pivot screw hole (1/4 clearance)",
        name="PivotHole",
        dia_tolerance_mm=(0.0, 0.10),
    )
    v_hole = math.pi * (pivot_dia / 2.0) ** 2 * PLATE_T
    volume = await volume_check(
        adapter, "pivot hole", volume - v_hole, 0.01 * v_hole
    )

    # Nominal reconstruction of the shallow top relief. The finished depth is
    # matched to the actual purchased shoulder and plate under the user-approved
    # functional acceptance; 0.25 is reference, not an independent depth limit.
    check(
        "create_plane PivotBearingTop",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=PLATE_T)
        ),
    )
    name_last_feature(adapter, "PivotBearingTop")
    bearing_relief = SketchDims()
    check(
        "create_sketch pivot bearing relief",
        await adapter.create_sketch("PivotBearingTop"),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        PIVOT_BEARING_RELIEF_DIAMETER / 2.0,
        "pivot bearing relief",
        dims=bearing_relief,
        names=("PivotBearingReliefCx", "PivotBearingReliefCz", "PivotBearingReliefDia"),
        drives=(None, None, '"PivotBearingReliefDia"'),
    )
    await ensure_fully_defined(adapter, "pivot bearing relief sketch")
    check("exit_sketch pivot bearing relief", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotBearingReliefProfile")
    drive_jobs += bearing_relief.apply(adapter, "PivotBearingReliefProfile")
    check(
        "cut pivot bearing relief",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIVOT_BEARING_RELIEF_DEPTH)
        ),
    )
    name_last_feature(adapter, "PivotBearingRelief")
    relief_depth_dim = name_dimensions(
        adapter, "PivotBearingRelief", ["PivotBearingReliefDepth"]
    )
    drive_jobs += [(relief_depth_dim[0], '"PivotBearingReliefDepth"')]
    v_relief = (
        math.pi
        * ((PIVOT_BEARING_RELIEF_DIAMETER / 2.0) ** 2 - (pivot_dia / 2.0) ** 2)
        * PIVOT_BEARING_RELIEF_DEPTH
    )
    volume = await volume_check(
        adapter, "pivot bearing relief", volume - v_relief, 0.01 * v_relief
    )

    # The v2 casting's two Fillister-head attachment bores land on matching
    # native 1/4-20 UNC-2B through taps in the platform.  One Hole Wizard
    # feature keeps the pair's thread metadata and 2X drawing callout together.
    post_mount_cut = wizard_holes(
        adapter,
        POST_MOUNT_SPEC,
        [
            [POST_MOUNT_WEST_XZ[0], 0.0, POST_MOUNT_WEST_XZ[1]],
            [POST_MOUNT_EAST_XZ[0], 0.0, POST_MOUNT_EAST_XZ[1]],
        ],
        (0.0, -1.0, 0.0),
        "cone-pivot-post-v2 mounts (1/4-20 tapped through)",
        name="PostMountHoles",
        # Table-derived tap diameters read back as 0.0 on this seat even when
        # the native feature is exact.  The immediately following measured
        # volume gate is the hard proof of the 1/4-20 tap-drill geometry.
        placement_dims=[
            (
                ("PostMountWestX", '"PostMountX"'),
                ("PostMountWestZ", '-"PostLocalZ" - "PostMountDZ"'),
            ),
            (
                # Horizontal-distance dimensions are unsigned; the point's
                # authored side retains the east/west sign.
                ("PostMountEastX", '"PostMountX"'),
                ("PostMountEastZ", '-"PostLocalZ" + "PostMountDZ"'),
            ),
        ],
    )
    drive_jobs += post_mount_cut.placement_drive_jobs
    v_post_mounts = 2.0 * math.pi * (POST_MOUNT_TAP_DIA / 2.0) ** 2 * PLATE_T
    volume = await volume_check(
        adapter, "v2 post mount taps", volume - v_post_mounts, 0.01 * v_post_mounts
    )

    # Lock notch: open-ended channel = rotated rectangle cut (engaged seat ->
    # past the west edge, opening the mouth) + ONE end-cap circle cut at the
    # closed engaged end. The mouth crossing is a straight line, so the
    # in-material rectangle volume is exactly width x NOTCH_EXIT_TRAVEL
    # (rail crossings symmetric about the chord centreline).
    _dx, _dy = _SLOT_TX, -_SLOT_TZ
    _nx, _ny = (-_dy * SLOT_W / 2.0, _dx * SLOT_W / 2.0)
    _e = (SLOT_E_X, -SLOT_E_Z)
    _out = (_SLOT_OUT_X, -_SLOT_OUT_Z)
    slot = SketchDims()
    check("create_sketch lock notch", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    slot_pts = [
        (_e[0] + _nx, _e[1] + _ny),
        (_out[0] + _nx, _out[1] + _ny),
        (_out[0] - _nx, _out[1] - _ny),
        (_e[0] - _nx, _e[1] - _ny),
    ]
    slot_lines = await add_line_chain(adapter, slot_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(
        adapter,
        slot_lines,
        slot_pts,
        label="lock notch",
        dims=slot,
        names=[
            "SlotAnchorX",
            "SlotAnchorZ",
            "SlotRunDx",
            "SlotRunDy",
            "SlotEndDx",
            "SlotEndDy",
            "SlotBackDx",
            "SlotBackDy",
        ],
        drives=[None] * 8,
    )
    # The print locates the notch by its closed-end centre and states its run
    # as the angle off the east-west line (the run is the chord the lock stud
    # follows, tangent to the swing arc about the pivot).  A construction ray
    # from the run's closed-end corner gives that angle a second line; the
    # angle itself is DRIVEN, so it reports the chord and can never bend it.
    await _add_notch_run_angle(adapter, slot_lines[0], slot_pts[0], slot)
    await ensure_fully_defined(adapter, "lock notch sketch")
    check("exit_sketch lock notch", await adapter.exit_sketch())
    name_last_feature(adapter, "LockNotchProfile")
    drive_jobs += slot.apply(adapter, "LockNotchProfile")
    check(
        "cut lock notch",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LockNotch")
    v_slot = NOTCH_EXIT_TRAVEL * SLOT_W * PLATE_T
    # The moved notch exits almost tangent to the east taper; SolidWorks' tiny
    # open-edge cut carries about 0.4 mm^3 of B-rep tessellation noise, larger
    # than one percent of this unusually small 6.3 mm^3 removal.
    volume = await volume_check(
        adapter, "lock notch", volume - v_slot, max(0.01 * v_slot, 0.5)
    )

    # Closed-end cap at the engaged seat (the mouth end is open -- no W cap).
    v_cap = math.pi * (SLOT_W / 2.0) ** 2 / 2.0 * PLATE_T
    cap = SketchDims()
    check("create_sketch notch cap E", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        _e[0],
        _e[1],
        SLOT_W / 2.0,
        "notch cap E",
        dims=cap,
        names=("CapECx", "CapECz", "CapEDia"),
        drives=(None, None, '"SlotW"'),
    )
    await ensure_fully_defined(adapter, "notch cap E sketch")
    check("exit_sketch notch cap E", await adapter.exit_sketch())
    name_last_feature(adapter, "LockNotchCapEProfile")
    drive_jobs += cap.apply(adapter, "LockNotchCapEProfile")
    check(
        "cut notch cap E",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LockNotchCapE")
    volume = await volume_check(adapter, "notch cap E", volume - v_cap, 0.02 * v_cap)

    # Vertical swing axis through the pivot hole -- Axis1 ("swing pivot").
    swing_axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot"
    )

    # Crank-axis construction (see the constants block): a vertical anchor
    # AXIS through CRANK_SEAT_ANCHOR (name-selected pivot, view-independent),
    # then the two angled planes rotated about it.
    anchor_axis = await name_bore_axis(
        adapter,
        "Front Plane",
        CRANK_SEAT_ANCHOR[1],
        "Right Plane",
        CRANK_SEAT_ANCHOR[0],
        "crank anchor (vertical)",
    )
    check(
        "create_plane CrankAxisVert (angled about the anchor axis)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="angle",
                base_plane="Right Plane",
                angle=CRANK_PLANE_ANGLE,
                pivot_axis=anchor_axis,
            )
        ),
    )
    name_last_feature(adapter, "CrankAxisVert")
    check(
        "create_plane CrankAxisHigh (Top + crank height)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=CRANK_AXIS_Y,
            )
        ),
    )
    name_last_feature(adapter, "CrankAxisHigh")
    # Seat plane PERPENDICULAR to the crank axis (Front rotated the same way
    # about the same anchor): the crankshaft/handle axial distance mates
    # reference it, so the crank rig's along-axis position rides the swinging
    # plate instead of a world datum.
    check(
        "create_plane CrankAxisSeat (angled, perpendicular to the axis)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="angle",
                base_plane="Front Plane",
                angle=CRANK_PLANE_ANGLE,
                pivot_axis=anchor_axis,
            )
        ),
    )
    name_last_feature(adapter, "CrankAxisSeat")
    # Crank axis: the machine-z crank line, in plate coordinates.
    check(
        "create_axis crank axis",
        await adapter.create_axis(
            CreateAxisParameters(
                mode="two_planes",
                planes=["CrankAxisVert", "CrankAxisHigh"],
            )
        ),
    )
    name_last_feature(adapter, "crank axis")

    # Semantic axes let the assembly mate the v2 fasteners without depending
    # on feature-tree Axis<N> numbering (which changes as construction grows).
    for axis_name, (mount_x, mount_z) in (
        ("post mount west", POST_MOUNT_WEST_XZ),
        ("post mount east", POST_MOUNT_EAST_XZ),
    ):
        await name_bore_axis(
            adapter, "Front Plane", mount_z, "Right Plane", mount_x, axis_name
        )
        name_last_feature(adapter, axis_name)

    # Rounded plan corners LAST (they consume the sharp corner edges; the
    # notch-mouth edges and the axis construction are already in place).
    v_fillets = 0.0
    for lbl, cx_a, cz_l, r in _CORNERS:
        check(
            f"fillet corner {lbl}",
            await adapter.add_fillet(r, [[cx_a, PLATE_T / 2.0, cz_l]]),
        )
        name_last_feature(adapter, f"Corner{lbl}")
        name_dimensions(adapter, f"Corner{lbl}", [f"Corner{lbl}R"])
        v_fillets += _corner_fillet_area(lbl, r) * PLATE_T
    volume = await volume_check(
        adapter, "rounded corners", volume - v_fillets, 0.01 * v_fillets
    )

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    # Decimal places for imported model dimensions live on the PART.  The
    # Hole Wizard owns the pivot-hole precision and native size callout.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    await volume_check(
        adapter, "driven platform (equations neutral)", volume, 0.01 * v_hole
    )

    # PlateTop datum: a reference plane ON the top face (+PlateT). The column
    # and tip block seat COINCIDENT to it (FootSeat/DeckTop pattern) so the
    # riders' height mates are flip-free and face-pick-free.
    check(
        "create_plane PlateTop (Top Plane, +PLATE_T)",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=PLATE_T)
        ),
    )
    name_last_feature(adapter, "PlateTop")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Profile View Note": PROFILE_VIEW_NOTE,
            "Feature View Note": FEATURE_VIEW_NOTE,
            "Notch View Note": NOTCH_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Pivot Relief Fit": PIVOT_RELIEF_FIT_REQUIREMENT,
        },
    )
    blank_reference_geometry(
        adapter,
        (
            # Unnamed offset planes created inside name_bore_axis. The named
            # PivotBearingTop plane occupies the first generated plane ordinal.
            ("PivotBearingTop", "PLANE"),
            ("Plane2", "PLANE"),
            ("Plane3", "PLANE"),
            ("CrankAxisVert", "PLANE"),
            ("CrankAxisHigh", "PLANE"),
            ("CrankAxisSeat", "PLANE"),
            ("Plane7", "PLANE"),
            ("Plane8", "PLANE"),
            ("Plane9", "PLANE"),
            ("Plane10", "PLANE"),
            ("PlateTop", "PLANE"),
            (swing_axis, "AXIS"),
            (anchor_axis, "AXIS"),
            ("crank axis", "AXIS"),
            ("post mount west", "AXIS"),
            ("post mount east", "AXIS"),
        ),
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
