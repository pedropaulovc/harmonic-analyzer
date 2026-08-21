r"""Reproduction script: frame subassembly (book ch. 6 / eight-views).

Static structure of the machine: the two-plate cast base, four smooth
polished columns at the corners, the rocker-arm-support that carries the
rocker-pivot shaft, the top-frame casting clamped around the columns, and
the five fasteners that pin the casting (4 corner-boss side screws + the
gooseneck set screw). Column tops rise to 1064.8 -- +28.6 plain capped
stubs above the casting's top face 1036.2 (2026-08-02 top-frame rederive;
supersedes the M6.8 "flush at 1040.7, no stub above" stack).

Layout (from the ch. 6 dimension photo and the ch. 30 eight views; assembly
axes follow the harmonic-base part: X = 46 cm length, Y = up, Z = 28 cm
depth):

* harmonic-base fixed at the origin, top face at Y = 50.8.
* tube-frame x4 standing on the base top face near the top-plate corners at
  x +/-197, z +/-112 -- the original symmetric placement.
* rocker-arm-support x1 (the windowed trapezoidal NORTH support,
  build_rocker_arm_support.py) at (X, Z) = (+72.9, 0), foot seated on the
  base top. A 177.8 x 177.8 cast plate, 63.5 thick (tapering to 16.94 at the
  apex), with the central rounded window; its apex carries the north pivot ball
  mount (channel.SLDASM, at machine z +116.915) and the rocker-pivot SHAFT runs
  along Z. This REPLACES the rocker-arm-portal casting (north + south unified
  portal frame) with the faithful reproduction of the original hand-built
  support -- the NORTH upright ONLY; the south upright and the top/foot rails
  are not part of this casting.

  The part is authored with its big windowed faces normal to its LOCAL Z (the
  thin 63.5 axis) and its 177.8 width along local X. In the machine the window
  must face +/-X -- it reads face-on in the ch. 30 p008 +X side view, exactly
  like the portal it replaces -- so the casting is turned +90 deg about Y
  (ROT_Y_POS90): local Z (window normal) -> machine +X, local X (177.8 width)
  -> machine Z, local Y (height) -> machine Y. The part origin is at the casting
  centre (bbox +/-88.9 in X and Y), so the turned wall spans machine
  Y 50.8..228.6 (foot on the base top, apex at the pivot height) and machine
  Z -88.9..88.9 at its original location. The north pivot ball
  mount (channel.SLDASM) is recentered to z +84.588, so its narrowed
  O13 footprint remains fully seated inside the wall's rear edge -- no cantilever.
  Seat Y = base-top 50.8 + 88.9 (half-height) = 139.7. The pivot x = 72.9, the
  rocker seesaw's mid-span (ch30 GT arm-end triangulation midpoint +72.5; the
  reclosed rod-pin hole 125.890 out reaches the cam centre at -52.990, rods plumb; the old
  "arbor 47.5 + 25.4 rod lever" chain died with the ch30 re-anchor).
  Inserted at its exact authored transform and locked to the fixed base.
* top-frame x1: the green one-piece casting at mid-plane Y = 1017.95 (side
  rails 34.2 wide / front-rear rails 38 wide x 36.5 tall, band
  y 999.7..1036.2; corner bosses Ø52.2 rise to 1040.7), bored around the
  four columns; its east rail (-X) carries the gooseneck hub and its west
  rail top face seats the fulcrum-keeper feet (channel.SLDASM).
* frame-side-screw x4 + gooseneck-set-screw x1: the casting's fasteners
  (see the constants below) -- each placed on its exact machine transform
  and locked to the fixed base (the frame's single-mate fix-all strategy).
* nameplate x1: the maker's plate (book ch. 26), laid FLAT on the base top
  face on the EAST (+X) side, decorated side up, centred front-back between the
  two east columns and read by an operator at that face. Cosmetic; constrained
  at its measured transform and locked to the fixed base (see NAMEPLATE_POS).

Hold-down: four 9/16-12 lag screws come up through the base into the support
foot's tapped holes. The base was re-drilled to the foot's pattern (4 holes at
local X +/-60.32, Z +/-17.46 -> machine x 55.44/90.36,
z -60.32/+60.32; see
build_harmonic_base.py HOLE_XZ) with O23 head counterbores on its underside, and
the lag screws (build_lag_screw.py, resized to the 9/16-12 foot tap) are
inserted at their exact authored transforms and locked to the fixed base. The
screws do NOT constrain the support. Every rigid frame member uses this same
single-mate strategy; transform readback remains the fail-loud placement
tripwire. Final asserts: every component fixed or ``swFullyConstrained``, and
zero interferences.

The 20-channel pitch stations live in the channel subassembly.

Dimensions: cad/DIMENSIONS.md ch. 6 (base/column), ch. 14 layout
(supports), "Channel & top-frame layout" (top frame); placements
photo-derived (med).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_frame_assembly.py
"""

from __future__ import annotations

import sys

from _common import (
    OUT_SLDPRT,
    apply_custom_properties,
    apply_summary_info,
    check,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _assembly import (
    assembly_title_properties,
    assert_component_placed,
    assert_components_fully_defined,
    assert_pattern_targets,
    check_no_interference,
    grid_component_pattern,
    lock_mate,
    named_ref,
    PatternDirection,
    place_component,
    save_assembly_and_images,
)
from _transforms import ROT_X_NEG90, ROT_X_POS90, ROT_Y_POS90, rot_z_rows
from cone_pivot_post_installation import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
)
from rocker_arm_support_spec import (
    SUPPORT_HOLD_DOWN_XZ,
    SUPPORT_WORLD_SEAT_Y,
    SUPPORT_WORLD_X,
    SUPPORT_WORLD_Z,
)

ASM_NAME = "frame"

BASE_TOP_Y = 50.8  # harmonic-base: 0.5 in bottom + 1.5 in top plate
COLUMN_X = 197.0  # column centres, from the ch. 6 / ch. 30 corner placement
FRONT_COLUMN_Z = FRAME_FRONT_COLUMN_Z
REAR_COLUMN_Z = FRAME_REAR_COLUMN_Z
SUPPORT_X = SUPPORT_WORLD_X  # rocker pivot x: the seesaw mid-span (ch30 GT arm-end
# triangulation midpoint +72.5; M6.8 mirror). Rod-side tip reaches the drum.
SUPPORT_Z = SUPPORT_WORLD_Z
SUPPORT_SEAT_Y = SUPPORT_WORLD_SEAT_Y  # rocker-arm-support's origin is
# at the casting centre (bbox Y +/-88.9), so seating its foot on the base top
# lifts the origin by the 88.9 foot half-height.
# Turn the support +90deg about Y so its big windowed faces (local Z normal)
# point along machine +/-X (face-on in the ch. 30 p008 +X side view), matching
# the portal it replaces; local X (177.8 width) maps to machine Z.
SUPPORT_EULER = [0.0, 90.0, 0.0]
SUPPORT_ROWS = ROT_Y_POS90

# Rocker-support hold-down: four 9/16-12 lag screws (build_lag_screw.py)
# constrained coaxial with the base clearance holes (and the support foot's tapped
# holes above them) by concentric + seat mates -- see build(). The
# stations are the foot's tapped pattern in the machine frame: local X +/-60.32,
# Z +/-17.46 turned +90deg about Y -> machine x 72.9 -/+ 17.46 = 55.44/90.36,
# z SUPPORT_Z +/-60.32 (these ARE the base HOLE_XZ machine positions). The screw is authored
# head-down at IDENTITY, so the placement point is the station and y is the under-
# head plane: machine y 6.5 (the base underside counterbore depth) sets the O22
# head recessed in the base underside, the O12 shank rising through the base into
# the O12.30 tapped foot hole. Placed on its exact machine transform (like the
# support); constrained by concentric + seat + spin-pin mates (see build()).
LAG_SCREW_XZ = SUPPORT_HOLD_DOWN_XZ
LAG_SCREW_UNDER_HEAD_Y = 6.5

TOP_FRAME_MID_Y = 1017.95  # casting mid-plane: side rails 34.2 / front-rear
# rails 38 wide x 36.5 tall, band y 999.7..1036.2; corner bosses rise to
# 1040.7 (2026-08-02 top-frame rederive)

# --- Top-frame fasteners (2026-08-02 top-frame rederive; MHA-117/118). Both
# parts are authored axis along local +Y with the origin at the UNDER-HEAD
# bearing plane and the head ABOVE it (+Y), so the placement point is the
# under-head seat and the rotation turns local +Y toward the head side. ---
#
# frame-side-screw: 4x #10-24 UNC x 12.7 slotted cheese-head screws pin the
# casting's four corner bosses (Ø52.2 at x ±197, z ±112) against the columns,
# screwed from OUTSIDE the frame: front bosses from the front (head -Z), rear
# bosses from the rear (head +Z), axes along Z at (x ±197, y TOP_FRAME_MID_Y).
# The under-head plane seats on the boss spot-face (Ø9 x 0.5 into the boss
# extreme z ±138.1) at z ±137.6; local +Y -> -Z for the front pair
# (ROT_X_NEG90, euler [-90,0,0]) and +Y -> +Z for the rear pair (ROT_X_POS90,
# euler [90,0,0]) point the 12.7 shank inboard: tips at z ±124.9, 0.2 clear
# of the column surface z ±124.7 (tapped #10-24 boss holes live in the
# top-frame part).
SIDE_SCREW_HEAD_Z = 137.6  # under-head seat station (spot-faced boss face)
#
# gooseneck-set-screw: 1x 1/4-20 UNC x 16 square-head set screw gripping the
# gooseneck post through the casting's east-hub tapped rib hole, axis along X
# at (y TOP_FRAME_MID_Y, z 3.088 -- the hub/post centreline). Entered from the
# east outer face x -214.1: local +Y -> -X (rot_z_rows(90), euler [0,0,90])
# points the 16 shank inboard, tip at x -205.15 = 0.15 CLEAR (outboard) of the
# Ø16 post surface at x -205 (post centre -197) -- the first build pinned the
# tip at -204.85, 0.15 INSIDE the post (1.39 mm^3 top-level interference),
# under-head plane at x -221.15 (bearing face 7.05 off the outer face,
# the contract standoff), square head outboard to -227.15.
GOOSENECK_HUB_Z = 3.088  # gooseneck bore centreline (unchanged position)
SET_SCREW_TIP_X = -205.15  # 0.15 clear (outboard) of the Ø16 post surface -205
SET_SCREW_UNDER_HEAD_X = SET_SCREW_TIP_X - 16.0  # -221.15 under-head plane

# Maker's nameplate (book ch. 26, pp. 70-71): the 100 x 55 brass plate lies FLAT
# on the base top, decorated side up, on the EAST (+X) face -- read off the in-situ
# photos (photogrammetry 195527397 / 195530756 / 195532820: the plate sits on the
# base top, centred between the two columns of one face, read by an operator
# standing at that face) and the ch. 30 eight views.
#
# The part's decorated face is its FRONT face (+Z local; build_nameplate extrudes
# the body in -Z so the engraving is frontmost and reads with no mirror).
# NAMEPLATE_ROWS (euler [-90,90,0]) lays it flat on the EAST face: local +Z
# (decorated front) -> +Y so the engraving faces up; local +Y (text height) -> -X
# so the text top faces the machine interior and reads upright to an east operator;
# local +X (text length, 100) -> -Z so the line runs front-back; the 1.5 body
# (local -Z) drops onto the base top. The placed point is the part origin CORNER
# (decorated face, x=0/y=0): Y 52.3 lays the decorated face on top with the 1.5
# body resting on the base top (50.8); Z 50 centres the 100 mm line at z 0 between
# the east columns (z +/-112); X 214.25 sets the plate's east edge ~8 mm in from
# the top-plate east edge (x 222.25), span x 159.25..214.25 -- east of the
# rocker-arm-support (x 28..117) and clear of the east columns (which sit at
# both column stations, away from the plate's z -50..50), so it grounds 0-DOF,
# no interference.
NAMEPLATE_POS = [214.25, 52.3, 50.0]
NAMEPLATE_EULER = [-90.0, 90.0, 0.0]
NAMEPLATE_ROWS = [[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _part(name: str) -> str:
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing part {path}; run build_{name.replace('-', '_')}.py first"
        )
    return str(path)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import InsertComponentParameters

    base_path = _part("harmonic-base")
    column_path = _part("tube-frame")
    _part("rocker-arm-support")  # placed via place_component below; assert it exists
    _part("lag-screw")  # support hold-down; placed via place_component below
    _part("frame-side-screw")  # corner-boss screws; placed via place_component
    _part("gooseneck-set-screw")  # west-hub set screw; placed via place_component
    top_frame_path = _part("top-frame")

    check("create_assembly", await adapter.create_assembly())

    # Base: first insert is auto-fixed by SolidWorks.
    res = await adapter.insert_component(InsertComponentParameters(file_path=base_path))
    check("insert_component harmonic-base (auto-fixed)", res)
    base_name = res.data["name"]
    if not res.data.get("fixed"):
        raise RuntimeError("base component was not auto-fixed")

    # Columns at the four top-plate corners: one lock-mated seed and one native
    # two-direction grid replace four inserts and four independent mates.
    # The pattern instances are positioned rigidly by the feature -- they read
    # fully defined (the channel bushing-bank precedent). The asymmetric span
    # preserves the front pair and lands the rear pair on its translated bores.
    column_target = [COLUMN_X, BASE_TOP_Y, REAR_COLUMN_Z]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=column_path, position=column_target)
    )
    check(f"insert_component tube-frame @ {column_target}", res)
    column_name = res.data["name"]
    await lock_mate(
        adapter,
        named_ref(f"Right Plane@{column_name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label=f"column {column_name} fixed to base",
    )
    assert_component_placed(adapter, column_name, column_target, IDENTITY)
    column_instances = await grid_component_pattern(
        adapter,
        [column_name],
        axis1="x",
        spacing1_mm=2.0 * COLUMN_X,
        instances1=2,
        axis2="z",
        spacing2_mm=REAR_COLUMN_Z - FRONT_COLUMN_Z,
        instances2=2,
        direction1=PatternDirection.FORWARD,
        direction2=PatternDirection.REVERSE,
        label="tube-frame column grid",
    )
    assert_pattern_targets(
        adapter,
        column_instances,
        [
            [-COLUMN_X, BASE_TOP_Y, REAR_COLUMN_Z],
            [COLUMN_X, BASE_TOP_Y, FRONT_COLUMN_Z],
            [-COLUMN_X, BASE_TOP_Y, FRONT_COLUMN_Z],
        ],
        IDENTITY,
        "tube-frame column grid",
    )

    # Rocker-pivot support: the windowed trapezoidal NORTH support
    # (build_rocker_arm_support.py), the faithful reproduction of the original
    # hand-built casting that REPLACES the unified rocker-arm-portal. Turned
    # +90deg about Y (SUPPORT_ROWS) so its big windowed faces point along
    # machine +/-X (face-on in the ch. 30 p008 side view), with local X (177.8
    # width) -> machine Z and the foot on the base top. Its origin is the casting
    # centre.
    #
    # Inserted on-solution (a single machine-handed casting) and locked to the
    # fixed base. Its authored transform places the physical foot on the base top.
    support_target = [SUPPORT_X, SUPPORT_SEAT_Y, SUPPORT_Z]
    support_name = await place_component(
        adapter,
        "rocker-arm-support",
        support_target,
        SUPPORT_EULER,
        SUPPORT_ROWS,
        ground=False,
        label="rocker-arm-support",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{support_name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="rocker-arm-support fixed to base",
    )
    assert_component_placed(adapter, support_name, support_target, SUPPORT_ROWS)

    # Hold-down: four 9/16-12 lag screws coaxial with the support foot's tapped
    # holes (and the base clearance holes below them). The authored support pose
    # seats its foot exactly on the base top at the derived machine stations, so the
    # screw at each station rises through the base clearance hole -- its O22 head
    # recessed in the base underside counterbore -- into the O12.30 tapped foot
    # hole. Authored head-down (IDENTITY) on its exact machine transform,
    # not grounded. Each seed uses one lock mate to the fixed base; its exact
    # transform carries the physical coaxiality and head-seat position, and the
    # readback assertion proves the mate did not move it. One real-mated seed and
    # one native two-direction grid populate the other three holes; both spacings
    # derive from the same foot-pattern constants as the base hole grid.
    bx, bz = LAG_SCREW_XZ[0]
    screw_target = [bx, LAG_SCREW_UNDER_HEAD_Y, bz]
    screw_name = await place_component(
        adapter,
        "lag-screw",
        screw_target,
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=f"lag-screw hold-down ({bx:.2f}, {bz:+.2f})",
    )
    await lock_mate(
        adapter,
        named_ref(f"Right Plane@{screw_name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="lag-screw seed fixed to base",
    )
    assert_component_placed(adapter, screw_name, screw_target, IDENTITY)
    pattern_instances = await grid_component_pattern(
        adapter,
        [screw_name],
        axis1="x",
        spacing1_mm=LAG_SCREW_XZ[2][0] - LAG_SCREW_XZ[0][0],
        instances1=2,
        axis2="z",
        spacing2_mm=LAG_SCREW_XZ[0][1] - LAG_SCREW_XZ[1][1],
        instances2=2,
        direction1=PatternDirection.REVERSE,
        direction2=PatternDirection.REVERSE,
        label="lag-screw hold-down grid",
    )
    assert_pattern_targets(
        adapter,
        pattern_instances,
        [[x, LAG_SCREW_UNDER_HEAD_Y, z] for x, z in LAG_SCREW_XZ[1:]],
        IDENTITY,
        "lag-screw hold-down grid",
    )

    # Top-frame casting clamped around the four columns, mid-plane y 1017.95.
    target = [0.0, TOP_FRAME_MID_Y, 0.0]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=top_frame_path, position=target)
    )
    check(f"insert_component top-frame @ {target}", res)
    name = res.data["name"]
    await lock_mate(
        adapter,
        named_ref(f"Right Plane@{name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="top-frame fixed to base",
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    # Maker's nameplate: laid flat on the base top, decorated face up, on the EAST
    # face, centred front-back between the two east columns (see NAMEPLATE_POS /
    # NAMEPLATE_ROWS). Cosmetic + rigid -> locked to the base.
    nameplate_name = await place_component(
        adapter,
        "nameplate",
        NAMEPLATE_POS,
        NAMEPLATE_EULER,
        NAMEPLATE_ROWS,
        ground=False,
        label="nameplate",
    )
    await lock_mate(
        adapter,
        named_ref(f"Top Plane@{nameplate_name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="nameplate fixed to base",
    )
    assert_component_placed(adapter, nameplate_name, NAMEPLATE_POS, NAMEPLATE_ROWS)

    # Corner-boss side screws: one #10-24 cheese-head per boss, screwed from
    # OUTSIDE the frame (front pair from -Z, rear pair from +Z), under-head
    # seat on the boss spot-face at z -/+137.6 (see SIDE_SCREW_HEAD_Z). Rigid
    # fasteners -> the frame's single-mate fix-all strategy: placed on their
    # exact machine transforms, one lock mate to the fixed base each, readback
    # assert proves the mate did not move them.
    for tag, sx, sz, s_euler, s_rows in (
        ("front west", -COLUMN_X, -SIDE_SCREW_HEAD_Z, [-90.0, 0.0, 0.0], ROT_X_NEG90),
        ("front east", COLUMN_X, -SIDE_SCREW_HEAD_Z, [-90.0, 0.0, 0.0], ROT_X_NEG90),
        ("rear west", -COLUMN_X, SIDE_SCREW_HEAD_Z, [90.0, 0.0, 0.0], ROT_X_POS90),
        ("rear east", COLUMN_X, SIDE_SCREW_HEAD_Z, [90.0, 0.0, 0.0], ROT_X_POS90),
    ):
        side_target = [sx, TOP_FRAME_MID_Y, sz]
        side_screw = await place_component(
            adapter,
            "frame-side-screw",
            side_target,
            s_euler,
            s_rows,
            ground=False,
            label=f"frame-side-screw ({tag})",
        )
        await lock_mate(
            adapter,
            named_ref(f"Right Plane@{side_screw}", "PLANE"),
            named_ref(f"Right Plane@{base_name}", "PLANE"),
            label=f"frame-side-screw ({tag}) fixed to base",
        )
        assert_component_placed(adapter, side_screw, side_target, s_rows)

    # Gooseneck set screw: 1/4-20 square head through the west-hub tapped rib
    # hole along +X at the hub centreline; tip 0.15 clear of the Ø16 post
    # (see SET_SCREW_* constants). Same fix-all treatment.
    set_target = [SET_SCREW_UNDER_HEAD_X, TOP_FRAME_MID_Y, GOOSENECK_HUB_Z]
    set_rows = rot_z_rows(90.0)
    set_screw = await place_component(
        adapter,
        "gooseneck-set-screw",
        set_target,
        [0.0, 0.0, 90.0],
        set_rows,
        ground=False,
        label="gooseneck-set-screw (west hub)",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{set_screw}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="gooseneck-set-screw fixed to base",
    )
    assert_component_placed(adapter, set_screw, set_target, set_rows)

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    # Title-block identity for the assembly drawing (draw_frame_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A04",
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The PART cell resolves the document summary Title; "frame assembly" (not
    # the bare stem) so the sheet identifies itself as an assembly drawing.
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
