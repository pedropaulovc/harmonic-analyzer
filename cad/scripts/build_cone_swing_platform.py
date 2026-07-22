r"""Reproduction script: cone swing platform (book ch. 12, p. 18 "pivot").

The wedge-shaped plate the whole cone-gear set rides on. The book's
top-down photo (p. 18) labels the TIP end "pivot": the merged green
column (big-end journal + crank pedestal, ONE casting), the cone shaft
and the tip clamp block all stand ON this plate, and the whole unit --
crank, 16T pinion, chain wheel included -- swings horizontally about a
vertical axis near the shaft's thin tip to dis/engage the cone set from
the cylinder set (video 4/4, engage/disengage stills). Swing separation
grows with distance from the pivot, so pivoting at the TIP gives the
big-end gears the largest throw.

Plan shape is the p.18 wedge, ASYMMETRIC about the shaft line: the east
side tapers 12 -> 20 half-width, the west side flares 12 -> 37 so the
run from the swing pivot to the cone-lock-knob is SOLID plate (no lobe
protrusion); the open LOCK NOTCH cuts straight into the west edge. The
four plan corners are rounded, echoing the hardware each sits beside
(pivot screw head at the north end, the green column at the south-east,
the lock knob washer at the south-west). A O6.5 pivot hole takes the
slotted pivot screw (clearance over its O6.35 shoulder -- the plate
rotates ON the screw).

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
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import HoleSpec, blind_cut_dia_mm, wizard_holes
from cone_swing_platform_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    PLAN_VIEW_NOTE,
)

PART_NAME = "cone-swing-platform"
MATERIAL = "Plain Carbon Steel"  # black-finished steel plate (p.18 dark wedge)

PLATE_T = 6.35  # 1/4" plate
HALF_WIDTH_N = 12.0  # north (pivot/tip) half-width, EAST side (the lock-slot
# region keeps its full seat)
WEST_HALF_N = 9.5  # north half-width, WEST side (PR8: trimmed 12 -> 9.5 so
# the flared west edge clears the NORTH arbor pedestal at z 89.5..105.5 --
# 12 put the plate corner-touching the clamp's east flank; ch12 img09 shows
# the real plate narrow at the tip with the clamp hugging its edge)
EAST_HALF_S = 20.0  # east half-width at the south (big) end -- unchanged taper
WEST_HALF_S = 37.0  # west half-width at the south end: the flare that makes
# the pivot -> lock-knob line solid plate (covers the notch seat + washer)
PLATE_LEN = 214.0  # north edge -> south edge along the cone axis: covers the
# pivot post's south flank by 0.5 while keeping clear air to nothing -- the
# crank column now RIDES this plate (one casting with the big-end journal),
# so the old crank-pedestal edge-gap constraint is gone with the pedestal
NORTH_OVERHANG = 7.0  # pivot -> north edge (plate continues past the pivot)
# Clearance over the O6.35 pivot-screw shoulder: the plate swings ON the screw
# (build_cone_pivot_screw). 1/4 clearance CLOSE fit (Ø6.756, the wizard twin of
# the old Ø6.5 artefact dim).
PIVOT_HOLE_SPEC = HoleSpec("clearance", "1/4", fit="close")

THROUGH_CUT_DEPTH = 40.0  # mid-plane total (both_directions splits it half per
# side of the sketch plane); must exceed 2x any extent crossed

INCLINE_DEG = 12.5182  # cone-axis plan incline (the assembly's ROT_Y_INCLINE)
_SIN_I = math.sin(math.radians(INCLINE_DEG))
_COS_I = math.cos(math.radians(INCLINE_DEG))

# --- lock notch (the v4_t00411 clamp knob rides this) ------------------------
# The open-ended lock notch cuts from the engaged stud seat straight out
# through the plate's WEST edge (the mouth). The cone-lock-knob's stud (fixed
# to the base) sits at the notch's closed end when engaged; on disengage the
# plate swings until its edge passes the stud entirely -- v4_t00417 shows the
# bolt standing PAST the plate edge. Screwed down with no plate under it, the
# knob's washer drops past plate-top level and fences the mouth, locking the
# plate DISENGAGED (tightened ON the plate it clamps ENGAGED).
# The notch runs along the swing arc's CHORD: at R~192 over ~3 deg to the
# mouth the sagitta is ~0.07, absorbed by the O6.35-stud-in-8.0 clearance.
#
# LOCAL-FRAME CONVENTION: the assembly places this part at Ry(+INCLINE)
# (train._plate_local_to_machine), under which local +x maps to machine WEST
# at the engaged pose -- every west-side feature below (the flare, the lock
# notch) is authored at local +x, east-side features at local -x.
SLOT_W = 8.0  # notch width: O6.35 stud + chord-vs-arc slack (see above)
SLOT_E_X, SLOT_E_Z = 24.5, -190.1  # engaged stud centre (part-local frame)
SLOT_R = math.hypot(SLOT_E_X, SLOT_E_Z)  # 191.67 about the swing pivot
# The plate swings toward disengage (big end away from the drum), so in PLATE
# coords the fixed stud sweeps the INVERSE rotation: unit direction (-z, x)/R
# at E -- outward toward the west edge (+x), slightly north (+z).
_SLOT_TX, _SLOT_TZ = -SLOT_E_Z / SLOT_R, SLOT_E_X / SLOT_R


def _west_edge_x(z_local: float) -> float:
    """Authored x of the west taper edge at local z (linear 9.5 -> 37)."""
    return WEST_HALF_N + (WEST_HALF_S - WEST_HALF_N) * (
        NORTH_OVERHANG - z_local) / PLATE_LEN


def _chord_exit_travel(x0: float, z0: float) -> float:
    """Stud travel from (x0, z0) along the chord to the west taper edge."""
    # solve x0 + t*TX = _west_edge_x(z0 + t*TZ) for t (both sides linear)
    k = (WEST_HALF_S - WEST_HALF_N) / PLATE_LEN
    return (WEST_HALF_N + k * (NORTH_OVERHANG - z0) - x0) / (_SLOT_TX + k * _SLOT_TZ)


# Stud travel (in plate coords) from the engaged seat to the mouth. Past this
# the stud is OUT of the plate; the assembly derives the disengaged pose
# (edge clear of the knob washer, DISENGAGE_DEG) from it.
NOTCH_EXIT_TRAVEL = _chord_exit_travel(SLOT_E_X, SLOT_E_Z)  # 10.46
_MOUTH_OVERSHOOT = 4.0  # cut ends past the edge so the mouth opens clean
_SLOT_OUT_X = SLOT_E_X + (NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT) * _SLOT_TX
_SLOT_OUT_Z = SLOT_E_Z + (NOTCH_EXIT_TRAVEL + _MOUTH_OVERSHOOT) * _SLOT_TZ

# --- rounded plan corners (item: they echo the neighbouring hardware) --------
# (authored x, local z, radius): north pair ~ the pivot screw head, south-east
# ~ the green column foot, south-west ~ the knob washer. Sharp-corner plan
# points; the fillets are cut on the vertical edges after all through-cuts.
_CORNERS = (
    ("NE", -HALF_WIDTH_N, NORTH_OVERHANG, 10.0),
    ("NW", WEST_HALF_N, NORTH_OVERHANG, 8.0),
    ("SW", WEST_HALF_S, NORTH_OVERHANG - PLATE_LEN, 10.0),
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
# sits EAST of the pivot, pivot.x - X_CRANK = 43.11 (asserted against the
# live cone geometry in the assembly).
CRANK_AXIS_OFF = 43.11  # east offset: ppivot.x -79.69 - X_CRANK -122.8
CRANK_AXIS_Y = 92.185  # Y_CRANK 142.985 - Y_BASE_TOP 50.8 (above plate BOTTOM;
# 2026-07-14 crank-mesh rederive: the crank dropped onto the ENGAGED 16T:64T
# centre distance R64 + R16 + 0.25 -- see build_drive_train_assembly)
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
# (part-local plan x, z) = (-42.09, -9.34); machine (-122.80, 103.29)


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
    await set_global(adapter, "HalfWidthN", f"{HALF_WIDTH_N}mm")
    await set_global(adapter, "WestHalfN", f"{WEST_HALF_N}mm")
    await set_global(adapter, "EastHalfS", f"{EAST_HALF_S}mm")
    await set_global(adapter, "WestHalfS", f"{WEST_HALF_S}mm")
    await set_global(adapter, "PlateLen", f"{PLATE_LEN}mm")
    await set_global(adapter, "NorthOverhang", f"{NORTH_OVERHANG}mm")
    # (The old PivotHoleDia knob is gone: the pivot hole is now a native Hole
    # Wizard 1/4 clearance feature whose diameter comes from the table.)
    await set_global(adapter, "SlotW", f"{SLOT_W}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Asymmetric trapezoid plan on the Top plane (sketch (x, y) -> part
    # (X, -Z)). The tapered side lines are sloped, so direct-to-DB keeps
    # inference from snapping them.
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
    await define_polygon_chain(
        adapter, lines, plan_pts, label="plate plan", dims=plate,
        names=["NorthHalfW", "NorthOverhangDim", "NorthEdge",
               "WestTaperDx", "PlateLenDim", "SouthEdge"],
        drives=['"HalfWidthN"', '"NorthOverhang"',
                '"HalfWidthN" + "WestHalfN"',
                '"WestHalfS" - "WestHalfN"', '"PlateLen"',
                '"WestHalfS" + "EastHalfS"'],
    )
    await ensure_fully_defined(adapter, "plate plan")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_T)),
    )
    name_last_feature(adapter, "Plate")
    v_plate = ((HALF_WIDTH_N + WEST_HALF_N) + (WEST_HALF_S + EAST_HALF_S)) / 2.0 \
        * PLATE_LEN * PLATE_T
    volume = await volume_check(adapter, "plate", v_plate, 0.005 * v_plate)

    # Pivot screw clearance hole at the origin: ONE native Hole Wizard 1/4
    # clearance (close fit) feature, through-all along Y, drilled from the
    # plate bottom (y=0) while the plate is still a plain trapezoidal slab
    # (before the lock notch/fillets explode the face count). The plate swings
    # ON the Ø6.35 pivot-screw shoulder, so a close 1/4 clearance (Ø6.756).
    pivot_dia = blind_cut_dia_mm(PIVOT_HOLE_SPEC)
    wizard_holes(
        adapter, PIVOT_HOLE_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0), "pivot screw hole (1/4 clearance)", name="PivotHole",
        dia_tolerance_mm=(0.0, 0.10),
    )
    v_hole = math.pi * (pivot_dia / 2.0) ** 2 * PLATE_T
    volume = await volume_check(adapter, "pivot hole", volume - v_hole, 0.01 * v_hole)

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
        adapter, slot_lines, slot_pts, label="lock notch", dims=slot,
        names=["SlotAnchorX", "SlotAnchorZ", "SlotRunDx", "SlotRunDy",
               "SlotEndDx", "SlotEndDy", "SlotBackDx", "SlotBackDy"],
        drives=[None] * 8,
    )
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
    volume = await volume_check(adapter, "lock notch", volume - v_slot, 0.01 * v_slot)

    # Closed-end cap at the engaged seat (the mouth end is open -- no W cap).
    v_cap = math.pi * (SLOT_W / 2.0) ** 2 / 2.0 * PLATE_T
    cap = SketchDims()
    check("create_sketch notch cap E", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, _e[0], _e[1], SLOT_W / 2.0, "notch cap E", dims=cap,
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
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot")

    # Crank-axis construction (see the constants block): a vertical anchor
    # AXIS through CRANK_SEAT_ANCHOR (name-selected pivot, view-independent),
    # then the two angled planes rotated about it.
    anchor_axis = await name_bore_axis(
        adapter, "Front Plane", CRANK_SEAT_ANCHOR[1],
        "Right Plane", CRANK_SEAT_ANCHOR[0], "crank anchor (vertical)",
    )
    check(
        "create_plane CrankAxisVert (angled about the anchor axis)",
        await adapter.create_plane(CreatePlaneParameters(
            mode="angle", base_plane="Right Plane", angle=CRANK_PLANE_ANGLE,
            pivot_axis=anchor_axis,
        )),
    )
    name_last_feature(adapter, "CrankAxisVert")
    check(
        "create_plane CrankAxisHigh (Top + crank height)",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Top Plane", offset=CRANK_AXIS_Y,
        )),
    )
    name_last_feature(adapter, "CrankAxisHigh")
    # Seat plane PERPENDICULAR to the crank axis (Front rotated the same way
    # about the same anchor): the crankshaft/handle axial distance mates
    # reference it, so the crank rig's along-axis position rides the swinging
    # plate instead of a world datum.
    check(
        "create_plane CrankAxisSeat (angled, perpendicular to the axis)",
        await adapter.create_plane(CreatePlaneParameters(
            mode="angle", base_plane="Front Plane", angle=CRANK_PLANE_ANGLE,
            pivot_axis=anchor_axis,
        )),
    )
    name_last_feature(adapter, "CrankAxisSeat")
    # Crank axis: the machine-z crank line, in plate coordinates.
    check(
        "create_axis crank axis",
        await adapter.create_axis(CreateAxisParameters(
            mode="two_planes", planes=["CrankAxisVert", "CrankAxisHigh"],
        )),
    )
    name_last_feature(adapter, "crank axis")

    # Rounded plan corners LAST (they consume the sharp corner edges; the
    # notch-mouth edges and the axis construction are already in place).
    v_fillets = 0.0
    for lbl, cx_a, cz_l, r in _CORNERS:
        check(
            f"fillet corner {lbl}",
            await adapter.add_fillet(r, [[cx_a, PLATE_T / 2.0, cz_l]]),
        )
        name_last_feature(adapter, f"Corner{lbl}")
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
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Plan View Note": PLAN_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "End View Note": END_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
