r"""Reproduction script: fulcrum-shaft end keeper (book ch. 17 p. 40; 2 used).

The black bracket at each end of the top-lever fulcrum shaft (ch. 17 p. 40
bottom-left closeup; ch. 30 top view corners + eight-views p008): an upright
round-topped lug sockets a bright Ø9.5 steel ball on the Ø6.35 shaft end
(spherical end bearing, the clevis+ball "shaft END mount" of the dimensions
table), and the foot is screwed down into the top-frame rail top face by one
slotted #10-24 cheese-head frame-side screw (MHA-117) seated flush in a
counterbore. Replaces the photo-refuted chrome baluster pair (the
pivot-ball-mount stays rocker-only at the machine bottom).

Layout (part frame): +X along the shaft, OUTBOARD toward the near shaft end
(the lug mid-plane / ball centre is x = 0); +Y up from the foot seat (y = 0
lands on the rail top face, machine 1036.2); +Z across the 14 width. The
foot reaches inboard to x = -23 with its on-face pad ending at x = -6.5;
outboard of the pad the underside is relieved to y = 4.8 so the bracket
clears the top-frame's 4.5-proud corner-boss land (0.3 margin). The ball is
bored Ø6.5 so the shaft end (placed 2.25 outboard of the ball centre by
build_channel_assembly) floats with the standard 0.15 diametral clearance.

One part serves both ends: the assembly places the +Z (rear) end keeper
part-X -> machine +Z and the front keeper flipped Ry180.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fulcrum_keeper.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
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
)
from _holes import HoleSpec, wizard_holes
from fulcrum_keeper_spec import (
    BALL_DIA,
    BORE_DIA,
    CBORE_DEPTH_MM,
    CBORE_DIA_MM,
    CROWN_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FOOT_H,
    FOOT_REACH,
    HOLE_DIA_MM,
    ISOMETRIC_VIEW_NOTE,
    KEEPER_WIDTH,
    LUG_HALF_T,
    PAD_END_X,
    RELIEF_H,
    SCREW_X,
    SHAFT_AXIS_H,
)

PART_NAME = "fulcrum-keeper"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

LUG_T = 2.0 * LUG_HALF_T  # 6.0 lug thickness along X
# Mid-plane through-cut totals (both_directions splits the depth half per
# side of the sketch plane): past the Ø9.5 ball's +-4.75 X extent.
SOCKET_CUT_DEPTH = 10.0
BORE_CUT_DEPTH = 12.0

# The keeper's foot screw: #10 close-clearance drill with a cheese-head
# counterbore (the MHA-117 head is Ø7 x 3; it seats flush). Table thru/cbore
# values are overridden to the spec's pinned artefact dims.
SCREW_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    "#10",
    overrides_mm={
        "HoleDiameter": HOLE_DIA_MM,
        "CounterBoreDiameter": CBORE_DIA_MM,
        "CounterBoreDepth": CBORE_DEPTH_MM,
    },
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "FootReach", f"{FOOT_REACH}mm")
    await set_global(adapter, "PadEndX", f"{PAD_END_X}mm")
    await set_global(adapter, "ReliefH", f"{RELIEF_H}mm")
    await set_global(adapter, "FootH", f"{FOOT_H}mm")
    await set_global(adapter, "KeeperWidth", f"{KEEPER_WIDTH}mm")
    await set_global(adapter, "LugT", f"{LUG_T}mm")
    await set_global(adapter, "ShaftAxisH", f"{SHAFT_AXIS_H}mm")
    await set_global(adapter, "CrownDia", f"{CROWN_DIA}mm")
    await set_global(adapter, "BallDia", f"{BALL_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Foot + bridge: side-profile L on Front (XY), extruded +-Z --------
    # (-23,0) -> (-6.5,0) is the on-face pad; the underside then steps up to
    # the 4.8 relief plane which runs outboard to the lug face at x = -3.
    foot = SketchDims()
    check("create_sketch foot", await adapter.create_sketch("Front"))
    pts = [
        (-FOOT_REACH, 0.0),
        (-PAD_END_X, 0.0),
        (-PAD_END_X, RELIEF_H),
        (-LUG_HALF_T, RELIEF_H),
        (-LUG_HALF_T, FOOT_H),
        (-FOOT_REACH, FOOT_H),
    ]
    lines = await add_line_chain(adapter, pts)
    await define_rectilinear_chain(
        adapter, lines, pts, label="foot profile", dims=foot,
        names=["PadLen", "ReliefRise", None, "FootRise", "FootReach"],
        drives=[
            '"FootReach" - "PadEndX"',
            '"ReliefH"',
            None,
            '"FootH" - "ReliefH"',
            '"FootReach"',
        ],
    )
    await ensure_fully_defined(adapter, "foot profile")
    check("exit_sketch foot", await adapter.exit_sketch())
    name_last_feature(adapter, "FootProfile")
    drive_jobs += foot.apply(adapter, "FootProfile")
    check(
        "extrude foot",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=KEEPER_WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Foot")
    depth_dim = name_dimensions(adapter, "Foot", ["Depth"])
    drive_jobs += [(depth_dim[0], '"KeeperWidth"')]
    a_pad = (FOOT_REACH - PAD_END_X) * FOOT_H
    a_bridge = (PAD_END_X - LUG_HALF_T) * (FOOT_H - RELIEF_H)
    v_foot = (a_pad + a_bridge) * KEEPER_WIDTH
    volume = await volume_check(adapter, "foot", v_foot, 0.005 * v_foot)

    # --- Lug: end-profile rectangle on Right (ZY), extruded +-X -----------
    lug = SketchDims()
    check("create_sketch lug", await adapter.create_sketch("Right"))
    half_w = KEEPER_WIDTH / 2.0
    lug_pts = [
        (-half_w, RELIEF_H),
        (half_w, RELIEF_H),
        (half_w, SHAFT_AXIS_H),
        (-half_w, SHAFT_AXIS_H),
    ]
    lug_lines = await add_line_chain(adapter, lug_pts)
    await define_rectilinear_chain(
        adapter, lug_lines, lug_pts, label="lug profile", dims=lug,
        names=["LugWidth", "LugRise", "LugAnchorZ", "LugBaseH"],
        drives=[
            '"KeeperWidth"',
            '"ShaftAxisH" - "ReliefH"',
            '"KeeperWidth" / 2',
            '"ReliefH"',
        ],
    )
    await ensure_fully_defined(adapter, "lug profile")
    check("exit_sketch lug", await adapter.exit_sketch())
    name_last_feature(adapter, "LugProfile")
    drive_jobs += lug.apply(adapter, "LugProfile")
    check(
        "extrude lug",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LUG_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LugBody")
    lug_depth = name_dimensions(adapter, "LugBody", ["Depth"])
    drive_jobs += [(lug_depth[0], '"LugT"')]
    v_lug = KEEPER_WIDTH * (SHAFT_AXIS_H - RELIEF_H) * LUG_T
    volume = await volume_check(adapter, "lug", volume + v_lug, 0.005 * v_lug)

    # --- Crown: full-round lug top, concentric with the shaft axis --------
    crown = SketchDims()
    check("create_sketch crown", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, SHAFT_AXIS_H, CROWN_DIA / 2.0, "lug crown", dims=crown,
        names=("CrownCz", "ShaftAxisH", "CrownDia"),
        drives=(None, '"ShaftAxisH"', '"CrownDia"'),
    )
    await ensure_fully_defined(adapter, "lug crown sketch")
    check("exit_sketch crown", await adapter.exit_sketch())
    name_last_feature(adapter, "LugCrownProfile")
    drive_jobs += crown.apply(adapter, "LugCrownProfile")
    check(
        "extrude crown",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LUG_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LugCrown")
    crown_depth = name_dimensions(adapter, "LugCrown", ["Depth"])
    drive_jobs += [(crown_depth[0], '"LugT"')]
    r_c = CROWN_DIA / 2.0
    # The crown circle's lower half merges into the lug rectangle (its
    # centre sits ON the lug top edge), so only the upper half adds metal.
    v_crown = 0.5 * math.pi * r_c * r_c * LUG_T
    volume = await volume_check(
        adapter, "lug crown", volume + v_crown, 0.01 * v_crown
    )

    # --- Spherical seat: socket cut, ball, shaft bore ---------------------
    socket = SketchDims()
    check("create_sketch socket", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, SHAFT_AXIS_H, BALL_DIA / 2.0, "ball socket", dims=socket,
        names=("SocketCz", "SocketH", "SocketDia"),
        drives=(None, '"ShaftAxisH"', '"BallDia"'),
    )
    await ensure_fully_defined(adapter, "ball socket sketch")
    check("exit_sketch socket", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketProfile")
    drive_jobs += socket.apply(adapter, "SocketProfile")
    check(
        "cut socket",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SOCKET_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Socket")
    r_b = BALL_DIA / 2.0
    v_socket = math.pi * r_b * r_b * LUG_T
    volume = await volume_check(
        adapter, "socket", volume - v_socket, 0.01 * v_socket
    )

    # Ball: revolved Ø9.5 sphere merged into the socket (the bright pressed
    # ball of the p. 40 closeup; it renders black with the part -- the
    # single-appearance simplification, noted on the print). Half-disc
    # profile on Front (XY), revolved about the shaft-axis centerline.
    ball = SketchDims()
    check("create_sketch ball", await adapter.create_sketch("Front"))
    check(
        "add_centerline ball axis",
        await adapter.add_centerline(-r_b, SHAFT_AXIS_H, r_b, SHAFT_AXIS_H),
    )
    arc = check(
        "add_arc ball",
        await adapter.add_arc(
            0.0, SHAFT_AXIS_H, -r_b, SHAFT_AXIS_H, r_b, SHAFT_AXIS_H
        ),
    )
    check(
        "add_line ball closure",
        await adapter.add_line(r_b, SHAFT_AXIS_H, -r_b, SHAFT_AXIS_H),
    )
    await anchor_point_to_origin(
        adapter, f"{arc}.center", 0.0, SHAFT_AXIS_H, "ball centre"
    )
    ball.record("BallRise", '"ShaftAxisH"')
    check(
        "ball diameter",
        await adapter.add_sketch_dimension(arc, None, "diameter", BALL_DIA),
    )
    ball.record("BallDia", '"BallDia"')
    check("exit_sketch ball", await adapter.exit_sketch())
    name_last_feature(adapter, "BallProfile")
    drive_jobs += ball.apply(adapter, "BallProfile")
    check(
        "revolve ball",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Ball")
    v_ball = (4.0 / 3.0) * math.pi * r_b**3
    volume = await volume_check(adapter, "ball", volume + v_ball, 0.01 * v_ball)

    # Shaft bore through the ball (and the socket line) along X.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, SHAFT_AXIS_H, BORE_DIA / 2.0, "shaft bore", dims=bore,
        names=("BoreCz", "BoreH", "BoreDia"),
        drives=(None, '"ShaftAxisH"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "shaft bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")
    # Coaxial Ø6.5 cylinder through the Ø9.5 sphere only (the lug material
    # inside the socket ring is already gone): V = 4pi/3 (R^3 - (R^2-a^2)^1.5).
    r_a = BORE_DIA / 2.0
    v_bore = (4.0 * math.pi / 3.0) * (
        r_b**3 - (r_b * r_b - r_a * r_a) ** 1.5
    )
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # --- Foot screw hole: cheese-head counterbore in the pad centre -------
    screw_hole = wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[SCREW_X, FOOT_H, 0.0]],
        (0.0, -1.0, 0.0),
        "keeper foot screw hole (#10 cbore)",
        name="FootScrewHole",
    )
    v_cb = math.pi * (screw_hole.cbore_dia_mm / 2.0) ** 2 * screw_hole.cbore_depth_mm
    v_thru = (
        math.pi
        * (screw_hole.hole_dia_mm / 2.0) ** 2
        * (FOOT_H - screw_hole.cbore_depth_mm)
    )
    volume = await volume_check(
        adapter, "foot screw hole", volume - v_cb - v_thru, 0.01 * (v_cb + v_thru)
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven keeper (equations neutral)", volume, 0.005 * volume
    )

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
