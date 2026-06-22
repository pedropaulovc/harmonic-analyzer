r"""Reproduction script: rocker-arm support portal (book ch. 14 + ch. 30 views).

ONE green cast-iron windowed PORTAL FRAME carrying the rocker-pivot shaft -
recreated from scratch (2026-06-19) to replace the former two-part split
(``rocker-arm-support`` north frustum in frame.SLDASM + ``a-frame`` south
upright/rails in the former output assembly). The true side view (ch30 p008, looking along
X) shows a WINDOWED RECTANGLE; the front/back views (ch30 p002/p006, along Z)
show a TRIANGLE; the perspective side views (p005/p007) show both. This
reconciles as a single casting: two tapered triangular UPRIGHTS - north at
machine z +101.6, south at z -111 - tied by a TOP RAIL (under the pivot-ball
seats) and a FOOT RAIL (on the base), with the open window between them.

Dimension re-derivation (2026-06-19, user-directed "re-derive everything"):
green-mask measurement of the eight-views confirms the structure and the major
dimensions - front-view triangle apex ~20 mm wide, height ~178 mm (7 in); side
view p008 portal outer Z-width ~186, window ~131 Z x ~125 Y, uprights ~27 deep.
The photos' ABSOLUTE Z-scale is perspective-compressed (the base grows ~6 % over
its own height; vertical vs horizontal pixel scale differ ~7 %), so the casting's
Z geometry is anchored on the mechanically-locked neighbours rather than raw
pixels: both pivot ball mounts (channel.SLDASM) sit at machine y 228.6 seat,
z +101.6 (north) / z -111 (south); the 9 in pivot shaft spans the 20-channel
stack (the frame-locked drum grid, machine.yaml); the south plate faces are
pinned by the parked measuring stick (z <= -118) and the ch25 handle cross-rod
(z >= -98). These supersede nothing in the channel/output assemblies - the
interface points are unchanged, so this is a clean PART unification, not a
machine re-layout.

The arbor-clamp boss/bore that the old north frustum carried is GONE: the cone
and cylinder arbor no longer rest on this casting (the arbor's north end gets
its own pedestal, the cone tip its own bracket - both in drive-train.SLDASM).

Local frame (authored MACHINE-HANDED so it inserts unmirrored into the
non-mirroring frame.SLDASM at the same transform the old frustum used):
    local x = machine x - 72.9   (+x east; x=0 is the north frustum centre)
    local y = machine y - 50.8   (+y up;   y=0 is the base top)
    local z = machine z - 101.6  (+z north; z=0 is the north frustum centre)
So the north upright is centred at local (0, *, 0); the south upright's clevis
mid-plane is at local z = -212.6 (= machine z -111). No MIRROR_PLANE entry is
needed (frame.SLDASM never calls mirror_placement).

Built as a single merged solid: the north frustum (Right-plane trapezoid slab +
two Front-plane wedge cuts), the south upright (Front-plane tapered plate +
Top-plane saddle + Top-plane clevis ears), then the TOP and FOOT rails which
each span continuously from the south plate into the north frustum (~2 mm
overlap at each end) - that overlap is what fuses the two uprights into ONE
body. An explicit single-body assertion guards the merge (volume_check sums all
bodies and would miss a detached second one). Finally the north hold-down
sockets and the foot-rail bolt holes.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_rocker_arm_portal.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    IN,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    log,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "rocker-arm-portal"
MATERIAL = "Gray Cast Iron"  # green-painted casting (ch30/photogrammetry)

TOTAL_HEIGHT = 7.00 * IN  # 177.8: apex/seat at machine y 228.6 (front+back views)
SEAT_Y = TOTAL_HEIGHT  # local y of the ball-mount seat (= machine 228.6)

# --- north upright (tapered frustum, centred at local x=0, z=0) ---------------
N_BASE_X = 3.50 * IN  # 88.9   front-view triangle base (photo, med)
N_TOP_X = 20.0  # apex width under the north ball-mount foot (photo, med)
N_BASE_Z = 40.0  # side-view depth at the base (ch30 p008, M6.9, med)
N_TOP_Z = 20.0  # side-view depth at the apex (ch30 p008, M6.9, med)
WEDGE_CUT_DEPTH = N_BASE_Z * 2.5  # mid-plane total; > base depth

# --- south upright (tapered plate + clevis, centred on local x=0) -------------
# Clevis mid-plane at local z = machine -111 - 101.6 = -212.6.
S_Z0 = -111.0 - 101.6  # -212.6: south clevis mid-plane (local z)
S_FOOT_HALF_X = 35.0  # foot plate +-35 about local 0 (machine 37.9..107.9), 70 wide
S_APEX_HALF_X = 14.0  # 28-wide top centred on the pivot (machine 58.9..86.9)
S_PLATE_Z = (S_Z0 - 6.5, S_Z0 + 12.0)  # machine -117.5..-99: stick / ch25-handle pinch
EAR_HALF_GAP = 8.1  # ears flank the ball mount's Ø16 base + 0.1 clearance
EAR_HALF_Z = 11.1  # ears 3 thick (about the clevis mid-plane)
EAR_HEIGHT = 20.0  # ear tops at local 197.8 (machine 248.6): shaft clears by 2
SADDLE_Y0 = 158.0  # saddle block bridges the plate to the wider clevis ears

# --- portal rails (continuous between the uprights; overlap fuses the body) ---
RAIL_OVERLAP = 2.0  # extrude 2 mm into each upright so the solids merge
N_APEX_Z_FACE = -N_TOP_Z / 2.0  # -10: north frustum apex south face (local z)
N_BASE_Z_FACE = -N_BASE_Z / 2.0  # -20: north frustum base south face (local z)
S_BACK_Z_FACE = S_PLATE_Z[1]  # -200.6: south plate back face (local z)
TOP_RAIL_HALF_X = 10.0  # 20 wide (= north apex width), machine 62.9..82.9
TOP_RAIL_DEPTH_Y = 16.0  # y 161.8..177.8 (machine 212.6..228.6 = photo window top)
FOOT_RAIL_X = (59.75 - 72.9, 89.75 - 72.9)  # (-13.15, 16.85): 30 wide, west face
# 0.25 east of the arbor-pedestal block (machine x +35.5..+59.5, drive-train)
FOOT_RAIL_H = 20.0  # photo: bolted foot flange ~20 tall

# --- fasteners ----------------------------------------------------------------
MOUNTING_HOLE_DIA = 0.3125 * IN  # 7.94  north hold-down lag-screw sockets (low)
MOUNTING_HOLE_SPACING = 2.5 * IN  # 63.5  hole pitch across X (low)
MOUNTING_HOLE_DEPTH = 25.0  # socket depth up from the base underside (low)
HOLE_CUT_DEPTH = 2.0 * MOUNTING_HOLE_DEPTH  # mid-plane total about y = 0
BOLT_HOLE_DIA = 8.2  # foot-rail hex-bolt shank holes (5/16", M6.10)
BOLT_HOLE_X = 74.75 - 72.9  # 1.85: rail centreline (machine x 74.75)
BOLT_HOLE_Z = (-54.0 - 101.6, 36.0 - 101.6)  # (-155.6, -65.6): machine z -54 / +36


def _n_frustum_volume() -> float:
    """North frustum volume via the prismatoid integral (w,d linear in s)."""
    a0 = N_BASE_X * N_BASE_Z
    a1 = N_BASE_X * (N_TOP_Z - N_BASE_Z) + N_BASE_Z * (N_TOP_X - N_BASE_X)
    a2 = (N_TOP_X - N_BASE_X) * (N_TOP_Z - N_BASE_Z)
    return TOTAL_HEIGHT * (a0 + a1 / 2.0 + a2 / 3.0)


def _solid_body_count(adapter) -> int:
    """Number of solid bodies in the active part (merge gate)."""
    doc = adapter.currentModel
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, True)) or []
    return len(list(bodies))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs: named globals in the equation manager that drive the sketch
    # dims below. A GUI fine-tune edits THESE (Tools > Equations) -- never an auto
    # "D7@Sketch3". The mm suffix is load-bearing: this is an INCH document and
    # the equation manager reads BARE numbers in document units, so an unsuffixed
    # "177.8" would evaluate as inches and blow the part up 25.4x. Signed-position
    # globals (SZ0, FootRailX0, BoltHoleZ*) hold the local coordinate WITH sign;
    # the dims they drive are unsigned distances from the origin, so the drive
    # expressions below negate them where the coordinate is negative.
    await set_global(adapter, "TotalHeight", f"{TOTAL_HEIGHT}mm")
    await set_global(adapter, "NBaseX", f"{N_BASE_X}mm")
    await set_global(adapter, "NTopX", f"{N_TOP_X}mm")
    await set_global(adapter, "NBaseZ", f"{N_BASE_Z}mm")
    await set_global(adapter, "NTopZ", f"{N_TOP_Z}mm")
    await set_global(adapter, "SFootHalfX", f"{S_FOOT_HALF_X}mm")
    await set_global(adapter, "SApexHalfX", f"{S_APEX_HALF_X}mm")
    await set_global(adapter, "SZ0", f"{S_Z0}mm")
    await set_global(adapter, "EarHalfGap", f"{EAR_HALF_GAP}mm")
    await set_global(adapter, "EarHalfZ", f"{EAR_HALF_Z}mm")
    await set_global(adapter, "EarHeight", f"{EAR_HEIGHT}mm")
    await set_global(adapter, "SaddleY0", f"{SADDLE_Y0}mm")
    await set_global(adapter, "TopRailHalfX", f"{TOP_RAIL_HALF_X}mm")
    await set_global(adapter, "TopRailDepthY", f"{TOP_RAIL_DEPTH_Y}mm")
    await set_global(adapter, "FootRailX0", f"{FOOT_RAIL_X[0]}mm")
    await set_global(adapter, "FootRailX1", f"{FOOT_RAIL_X[1]}mm")
    await set_global(adapter, "FootRailH", f"{FOOT_RAIL_H}mm")
    await set_global(adapter, "MountingHoleDia", f"{MOUNTING_HOLE_DIA}mm")
    await set_global(adapter, "MountingHoleSpacing", f"{MOUNTING_HOLE_SPACING}mm")
    await set_global(adapter, "MountingHoleDepth", f"{MOUNTING_HOLE_DEPTH}mm")
    await set_global(adapter, "BoltHoleDia", f"{BOLT_HOLE_DIA}mm")
    await set_global(adapter, "BoltHoleX", f"{BOLT_HOLE_X}mm")
    await set_global(adapter, "BoltHoleZ0", f"{BOLT_HOLE_Z[0]}mm")
    await set_global(adapter, "BoltHoleZ1", f"{BOLT_HOLE_Z[1]}mm")

    # Each sketch records its dim names + drive equations inline as the define_*
    # helper emits them (a per-sketch SketchDims); drive equations are collected
    # here and applied in one deferred batch at the end, after the whole model +
    # a rebuild exists so every equation target resolves.
    drive_jobs: list[tuple[str, str]] = []

    # ============ north upright: trapezoid slab (Z taper), mid-plane X ========
    n_trap = SketchDims()
    check("create_sketch n-trapezoid", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    trapezoid_pts = [
        (-N_BASE_Z / 2.0, 0.0),
        (N_BASE_Z / 2.0, 0.0),
        (N_TOP_Z / 2.0, TOTAL_HEIGHT),
        (-N_TOP_Z / 2.0, TOTAL_HEIGHT),
    ]
    lines = await add_line_chain(adapter, trapezoid_pts)
    set_sketch_direct_db(adapter, False)
    # Emission (anchor vertex 0 at (-NBaseZ/2, 0), on the X axis = 1 anchor dim;
    # skip segment 3): V0z, S0dx (base width), S1dx + S1dy (taper run + rise),
    # S2dx (apex width) -- 5 dims.
    await define_polygon_chain(
        adapter, lines, trapezoid_pts, label="n-trapezoid", dims=n_trap,
        names=["NTrapV0z", "NTrapBaseZ", "NTrapTaperZ", "NTrapHeight", "NTrapTopZ"],
        drives=[
            '"NBaseZ" / 2',
            '"NBaseZ"',
            '("NBaseZ" - "NTopZ") / 2',
            '"TotalHeight"',
            '"NTopZ"',
        ],
    )
    await ensure_fully_defined(adapter, "n-trapezoid sketch")
    check("exit_sketch n-trapezoid", await adapter.exit_sketch())
    name_last_feature(adapter, "NTrapProfile")
    drive_jobs += n_trap.apply(adapter, "NTrapProfile")
    check(
        "extrude n-trapezoid",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=N_BASE_X, both_directions=True)
        ),
    )
    name_last_feature(adapter, "NTrapSlab")
    v_slab = (N_BASE_Z + N_TOP_Z) / 2.0 * TOTAL_HEIGHT * N_BASE_X
    expected = await volume_check(adapter, "n-trapezoid slab", v_slab, 0.005 * v_slab)

    # X taper: two Front-plane wedge cuts (mapping (x, y) -> (X, Y) is exact).
    n_wedges = SketchDims()
    check("create_sketch n-wedges", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    margin = 15.0
    left_pts = [
        (-N_BASE_X / 2.0, 0.0),
        (-N_TOP_X / 2.0, TOTAL_HEIGHT),
        (-N_BASE_X / 2.0 - margin, TOTAL_HEIGHT),
        (-N_BASE_X / 2.0 - margin, 0.0),
    ]
    right_pts = [
        (N_BASE_X / 2.0, 0.0),
        (N_TOP_X / 2.0, TOTAL_HEIGHT),
        (N_BASE_X / 2.0 + margin, TOTAL_HEIGHT),
        (N_BASE_X / 2.0 + margin, 0.0),
    ]
    left = await add_line_chain(adapter, left_pts)
    right = await add_line_chain(adapter, right_pts)
    set_sketch_direct_db(adapter, False)
    # Both wedges share this sketch's SketchDims. Per wedge (anchor at the base
    # corner on the X axis = 1 dim; skip segment 3): V0x, S0dx + S0dy (taper
    # run + rise), S1dx (top run, depends on the local cut margin -> no knob,
    # left None/static), S2dy (vertical back edge). 5 dims each, 10 total.
    _taper_run = '("NBaseX" - "NTopX") / 2'
    await define_polygon_chain(
        adapter, left, left_pts, label="left wedge", dims=n_wedges,
        names=["LWedgeV0x", "LWedgeRun", "LWedgeRise", None, "LWedgeBack"],
        drives=['"NBaseX" / 2', _taper_run, '"TotalHeight"', None, '"TotalHeight"'],
    )
    await define_polygon_chain(
        adapter, right, right_pts, label="right wedge", dims=n_wedges,
        names=["RWedgeV0x", "RWedgeRun", "RWedgeRise", None, "RWedgeBack"],
        drives=['"NBaseX" / 2', _taper_run, '"TotalHeight"', None, '"TotalHeight"'],
    )
    await ensure_fully_defined(adapter, "n-wedges sketch")
    check("exit_sketch n-wedges", await adapter.exit_sketch())
    name_last_feature(adapter, "NWedgeProfile")
    drive_jobs += n_wedges.apply(adapter, "NWedgeProfile")
    check(
        "cut n-wedges",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=WEDGE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "NWedgeCut")
    expected = await volume_check(
        adapter, "north frustum", _n_frustum_volume(), 0.005 * _n_frustum_volume()
    )

    # ============ south upright: tapered plate (Front sketch, +Z offset) =======
    # Trapezoid in (x, y); offset-extruded along local +z to the plate band.
    s_plate_dims = SketchDims()
    check("create_sketch s-plate", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    plate_pts = [
        (-S_FOOT_HALF_X, 0.0),
        (S_FOOT_HALF_X, 0.0),
        (S_APEX_HALF_X, SEAT_Y),
        (-S_APEX_HALF_X, SEAT_Y),
    ]
    plate = await add_line_chain(adapter, plate_pts)
    set_sketch_direct_db(adapter, False)
    # Emission (anchor vertex 0 at (-SFootHalfX, 0), on the X axis = 1 dim; skip
    # segment 3): V0x, S0dx (foot width), S1dx + S1dy (taper run + rise), S2dx
    # (apex width) -- 5 dims.
    await define_polygon_chain(
        adapter, plate, plate_pts, label="s-plate", dims=s_plate_dims,
        names=["SPlateV0x", "SPlateFootX", "SPlateTaperX", "SPlateHeight", "SPlateApexX"],
        drives=[
            '"SFootHalfX"',
            '"SFootHalfX" * 2',
            '"SFootHalfX" - "SApexHalfX"',
            '"TotalHeight"',
            '"SApexHalfX" * 2',
        ],
    )
    await ensure_fully_defined(adapter, "s-plate sketch")
    check("exit_sketch s-plate", await adapter.exit_sketch())
    name_last_feature(adapter, "SPlateProfile")
    drive_jobs += s_plate_dims.apply(adapter, "SPlateProfile")
    plate_t = S_PLATE_Z[1] - S_PLATE_Z[0]
    extrude_at_offset(adapter, plate_t, S_PLATE_Z[0])
    name_last_feature(adapter, "SPlate")
    foot_w = 2.0 * S_FOOT_HALF_X
    apex_w = 2.0 * S_APEX_HALF_X
    v_plate = (foot_w + apex_w) / 2.0 * SEAT_Y * plate_t
    expected += v_plate
    expected = await volume_check(adapter, "south plate", expected, 0.005 * v_plate)

    # Saddle block at the apex: full clevis width, bridging the plate to the
    # FRONT ear so the ear band is not a detached body. Top sketch (x, y) ->
    # global (X, -Z), so sketch-y = -local-z: the clevis spans local z S_Z0 +-
    # EAR_HALF_Z -> sketch-y = -S_Z0 +- EAR_HALF_Z.
    sy_clevis = -S_Z0  # 212.6
    saddle_dims = SketchDims()
    check("create_sketch saddle", await adapter.create_sketch("Top"))
    saddle_rect = [
        (-S_APEX_HALF_X, sy_clevis - EAR_HALF_Z),
        (S_APEX_HALF_X, sy_clevis - EAR_HALF_Z),
        (S_APEX_HALF_X, sy_clevis + EAR_HALF_Z),
        (-S_APEX_HALF_X, sy_clevis + EAR_HALF_Z),
    ]
    saddle = await add_line_chain(adapter, saddle_rect)
    # Emission (segment dims first, then the anchor at vertex 0): width (apex X
    # span), depth (clevis Z thickness = 2*EarHalfZ), then anchor X + anchor Y.
    # The anchor lands at sketch-y = sy_clevis - EarHalfZ = -SZ0 - EarHalfZ (a
    # positive distance from the origin; SZ0 is negative so it is negated).
    await define_rectilinear_chain(
        adapter, saddle, saddle_rect, label="saddle", dims=saddle_dims,
        names=["SaddleWidth", "SaddleDepth", "SaddleAnchorX", "SaddleAnchorY"],
        drives=[
            '"SApexHalfX" * 2',
            '"EarHalfZ" * 2',
            '"SApexHalfX"',
            '-"SZ0" - "EarHalfZ"',
        ],
    )
    await ensure_fully_defined(adapter, "saddle sketch")
    check("exit_sketch saddle", await adapter.exit_sketch())
    name_last_feature(adapter, "SaddleProfile")
    drive_jobs += saddle_dims.apply(adapter, "SaddleProfile")
    extrude_at_offset(adapter, SEAT_Y - SADDLE_Y0, SADDLE_Y0)
    name_last_feature(adapter, "Saddle")
    # Plate overlap inside the saddle z-band (plate z S_PLATE_Z vs clevis +-EAR).
    plate_in_saddle = min(S_PLATE_Z[1], S_Z0 + EAR_HALF_Z) - max(
        S_PLATE_Z[0], S_Z0 - EAR_HALF_Z
    )
    v_saddle = apex_w * (SEAT_Y - SADDLE_Y0) * (2.0 * EAR_HALF_Z - plate_in_saddle)
    expected += v_saddle
    expected = await volume_check(adapter, "saddle", expected, 0.02 * v_saddle)

    # Clevis ears flanking the south ball-mount base (Top sketch, offset up).
    # Both ears share this sketch's SketchDims. Per ear (segment dims then anchor):
    # width (apex X span), depth (gap->edge = EarHalfZ - EarHalfGap), anchor X,
    # anchor Y (= -SZ0 +- EarHalfGap, the inner edge; SZ0 negative so negated).
    ears_dims = SketchDims()
    check("create_sketch ears", await adapter.create_sketch("Top"))
    for label, side, prefix, anchor_y_drive in (
        ("south ear", 1.0, "SEar", '-"SZ0" + "EarHalfGap"'),
        ("north ear", -1.0, "NEar", '-"SZ0" - "EarHalfGap"'),
    ):
        ear_rect = [
            (-S_APEX_HALF_X, sy_clevis + side * EAR_HALF_GAP),
            (S_APEX_HALF_X, sy_clevis + side * EAR_HALF_GAP),
            (S_APEX_HALF_X, sy_clevis + side * EAR_HALF_Z),
            (-S_APEX_HALF_X, sy_clevis + side * EAR_HALF_Z),
        ]
        ear = await add_line_chain(adapter, ear_rect)
        await define_rectilinear_chain(
            adapter, ear, ear_rect, label=label, dims=ears_dims,
            names=[f"{prefix}Width", f"{prefix}Depth", f"{prefix}AnchorX",
                   f"{prefix}AnchorY"],
            drives=[
                '"SApexHalfX" * 2',
                '"EarHalfZ" - "EarHalfGap"',
                '"SApexHalfX"',
                anchor_y_drive,
            ],
        )
    await ensure_fully_defined(adapter, "ears sketch")
    check("exit_sketch ears", await adapter.exit_sketch())
    name_last_feature(adapter, "EarsProfile")
    drive_jobs += ears_dims.apply(adapter, "EarsProfile")
    extrude_at_offset(adapter, EAR_HEIGHT, SEAT_Y)
    name_last_feature(adapter, "ClevisEars")
    v_ears = 2.0 * apex_w * (EAR_HALF_Z - EAR_HALF_GAP) * EAR_HEIGHT
    expected += v_ears
    expected = await volume_check(adapter, "clevis ears", expected, 0.02 * v_ears)

    # ============ top rail: south plate back -> north apex face ===============
    # Front-plane section, offset-extruded along local -z (toward the north
    # frustum). Spans z [S_BACK_Z_FACE, N_APEX_Z_FACE] with RAIL_OVERLAP into
    # each end so the two uprights fuse into one body.
    top_rail_dims = SketchDims()
    check("create_sketch top rail", await adapter.create_sketch("Front"))
    top_rail_rect = [
        (-TOP_RAIL_HALF_X, SEAT_Y - TOP_RAIL_DEPTH_Y),
        (TOP_RAIL_HALF_X, SEAT_Y - TOP_RAIL_DEPTH_Y),
        (TOP_RAIL_HALF_X, SEAT_Y),
        (-TOP_RAIL_HALF_X, SEAT_Y),
    ]
    top_rail = await add_line_chain(adapter, top_rail_rect)
    # Emission: width (X span = 2*TopRailHalfX), depth (Y = TopRailDepthY), then
    # anchor X + anchor Y. Anchor at sketch-y = SEAT_Y - TopRailDepthY (the
    # window-top edge under the ball seats).
    await define_rectilinear_chain(
        adapter, top_rail, top_rail_rect, label="top rail", dims=top_rail_dims,
        names=["TopRailWidth", "TopRailDepth", "TopRailAnchorX", "TopRailAnchorY"],
        drives=[
            '"TopRailHalfX" * 2',
            '"TopRailDepthY"',
            '"TopRailHalfX"',
            '"TotalHeight" - "TopRailDepthY"',
        ],
    )
    await ensure_fully_defined(adapter, "top rail sketch")
    check("exit_sketch top rail", await adapter.exit_sketch())
    name_last_feature(adapter, "TopRailProfile")
    drive_jobs += top_rail_dims.apply(adapter, "TopRailProfile")
    top_z0 = S_BACK_Z_FACE - RAIL_OVERLAP  # -202.6
    top_z1 = N_APEX_Z_FACE + RAIL_OVERLAP  # -8.0
    extrude_at_offset(adapter, top_z1 - top_z0, top_z0)
    name_last_feature(adapter, "TopRail")
    top_box = 2.0 * TOP_RAIL_HALF_X * TOP_RAIL_DEPTH_Y * (top_z1 - top_z0)
    top_overlap = 2.0 * TOP_RAIL_HALF_X * TOP_RAIL_DEPTH_Y * 2.0 * RAIL_OVERLAP
    expected += top_box - top_overlap
    expected = await volume_check(
        adapter, "top rail", expected, 0.6 * top_overlap + 0.01 * top_box
    )

    # ============ foot rail: south plate back -> north base face ==============
    foot_rail_dims = SketchDims()
    check("create_sketch foot rail", await adapter.create_sketch("Front"))
    foot_rail_rect = [
        (FOOT_RAIL_X[0], 0.0),
        (FOOT_RAIL_X[1], 0.0),
        (FOOT_RAIL_X[1], FOOT_RAIL_H),
        (FOOT_RAIL_X[0], FOOT_RAIL_H),
    ]
    foot_rail = await add_line_chain(adapter, foot_rail_rect)
    # Emission: width (X span = FootRailX1 - FootRailX0), depth (Y = FootRailH),
    # then anchor X (anchor on the X axis = 1 dim; FootRailX0 is negative so the
    # unsigned distance dim negates it). No anchor-Y dim (vertex 0 is on the axis).
    await define_rectilinear_chain(
        adapter, foot_rail, foot_rail_rect, label="foot rail", dims=foot_rail_dims,
        names=["FootRailWidth", "FootRailDepth", "FootRailAnchorX"],
        drives=[
            '"FootRailX1" - "FootRailX0"',
            '"FootRailH"',
            '-"FootRailX0"',
        ],
    )
    await ensure_fully_defined(adapter, "foot rail sketch")
    check("exit_sketch foot rail", await adapter.exit_sketch())
    name_last_feature(adapter, "FootRailProfile")
    drive_jobs += foot_rail_dims.apply(adapter, "FootRailProfile")
    foot_z0 = S_BACK_Z_FACE - RAIL_OVERLAP  # -202.6
    foot_z1 = N_BASE_Z_FACE + RAIL_OVERLAP  # -18.0
    extrude_at_offset(adapter, foot_z1 - foot_z0, foot_z0)
    name_last_feature(adapter, "FootRail")
    foot_rail_w = FOOT_RAIL_X[1] - FOOT_RAIL_X[0]
    foot_box = foot_rail_w * FOOT_RAIL_H * (foot_z1 - foot_z0)
    foot_overlap = foot_rail_w * FOOT_RAIL_H * 2.0 * RAIL_OVERLAP
    expected += foot_box - foot_overlap
    expected = await volume_check(
        adapter, "foot rail", expected, 0.6 * foot_overlap + 0.01 * foot_box
    )

    # ============ MERGE GATE: the casting must now be ONE solid body ==========
    n_bodies = _solid_body_count(adapter)
    if n_bodies != 1:
        raise RuntimeError(
            f"rocker-arm-portal is {n_bodies} bodies, expected 1 - the rails did "
            f"not fuse the north and south uprights (check RAIL_OVERLAP / spans)"
        )
    log(f"merge gate: single solid body confirmed ({n_bodies})")

    # ============ north hold-down sockets (up from the base underside) ========
    # On-axis circles (z 0): only centre-X + diameter are dims (2 each). The two
    # sockets sit at +-MountingHoleSpacing/2; the unsigned X dim is the half-pitch.
    holes_dims = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, -MOUNTING_HOLE_SPACING / 2.0, 0.0, MOUNTING_HOLE_DIA / 2.0, "hole L",
        dims=holes_dims,
        names=("HoleLX", "HoleLZ", "HoleLDia"),
        drives=('"MountingHoleSpacing" / 2', None, '"MountingHoleDia"'),
    )
    await define_circle(
        adapter, MOUNTING_HOLE_SPACING / 2.0, 0.0, MOUNTING_HOLE_DIA / 2.0, "hole R",
        dims=holes_dims,
        names=("HoleRX", "HoleRZ", "HoleRDia"),
        drives=('"MountingHoleSpacing" / 2', None, '"MountingHoleDia"'),
    )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    name_last_feature(adapter, "MountingHolesProfile")
    drive_jobs += holes_dims.apply(adapter, "MountingHolesProfile")
    check(
        "cut mounting holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HOLE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "MountingHoles")
    v_holes = 2.0 * math.pi * (MOUNTING_HOLE_DIA / 2.0) ** 2 * MOUNTING_HOLE_DEPTH
    expected -= v_holes
    expected = await volume_check(
        adapter, "mounting holes", expected, 0.01 * v_holes + 5.0
    )

    # ============ foot-rail hold-down bolt holes (Top sketch -> X, -Z) ========
    # Off-axis circles (both centre coords non-zero): 3 dims each -- centre X,
    # centre Z (= -z, the unsigned distance from the origin; the signed BoltHoleZ*
    # globals are negative, so the drive negates them), then diameter.
    bolt_holes_dims = SketchDims()
    check("create_sketch bolt holes", await adapter.create_sketch("Top"))
    for z, z_global in zip(BOLT_HOLE_Z, ("BoltHoleZ0", "BoltHoleZ1"), strict=True):
        await define_circle(
            adapter, BOLT_HOLE_X, -z, BOLT_HOLE_DIA / 2.0, f"bolt hole z{z:.0f}",
            dims=bolt_holes_dims,
            names=(f"BoltHoleX{z:.0f}", f"BoltHoleZ{z:.0f}", f"BoltHoleDia{z:.0f}"),
            drives=('"BoltHoleX"', f'-"{z_global}"', '"BoltHoleDia"'),
        )
    await ensure_fully_defined(adapter, "bolt holes sketch")
    check("exit_sketch bolt holes", await adapter.exit_sketch())
    name_last_feature(adapter, "BoltHolesProfile")
    drive_jobs += bolt_holes_dims.apply(adapter, "BoltHolesProfile")
    check(
        "cut bolt holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=3.0 * FOOT_RAIL_H, both_directions=True)
        ),
    )
    name_last_feature(adapter, "BoltHoles")
    v_bolts = 2.0 * math.pi * (BOLT_HOLE_DIA / 2.0) ** 2 * FOOT_RAIL_H
    expected -= v_bolts
    expected = await volume_check(
        adapter, "foot-rail bolt holes", expected, 0.02 * v_bolts
    )

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven rocker-arm-portal (equations neutral)", expected, 0.02 * v_bolts
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
