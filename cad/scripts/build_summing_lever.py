r"""Reproduction script: summing lever (book ch. 18, pp. 42-43).

The cast-iron lever that sums the pull of the 20 channel springs and balances
them against the master (counter) spring -- a FIRST-CLASS LEVER hung in
suspension on a knife edge.

PROVENANCE / REVERT NOTICE: this restores the legacy ``cad/SummingLever.cs``
shape (commit 9eb1710, itself translated from ``summing-lever.kcl``) at the
user's explicit direction (2026-06-16), superseding the M6.4 "knife-edge tube +
Ø14 bore" model. Two corrections the user made over the raw .cs:

* The real lever has **NO bore** -- the M6.4 bored tube was wrong. The .cs
  solid pivot cylinder is correct.
* The .cs was **missing the two hexagonal protrusions at the pivot** that form
  the **knife edge** the lever hangs/rocks on. They are added here (``_hex_knife_
  edges``); exact size/clocking is LOW confidence (museum-glass photos:
  references/.../ch18_images/page001_img0{1,3}, photogrammetry 194637152 /
  194651412) and is tuned against the knife-mount fit + ch30 parity.

Seven features (the six .cs features + the hex knife edge):

1. Coefficients plate  -- Top-plane rectangle on the +X (channel-spring) arm,
   carrying the 20 spring holes; mid-plane extrude centred on the pivot (local
   y 0). Machine-y registration (M6.4 plate-top-at-998) is set at placement.
2. Pivot cylinder      -- Front-plane solid circle at the origin, symmetric
   extrude along the long edge (the pivot/rock axis = local Z).
3. Hex knife edges     -- two hexagonal trunnion stubs PROTRUDING beyond the
   body ends (one per side), vertex-up; the pivot overhangs the body so each
   knife edge rests on a bearing support on the top plate (ch30-p003).
4. Edge ribs (x2)      -- Front-plane line/line/semicircle wrapping the cylinder
   at the plate ends, blind-extruded at a start offset.
5. Summation plate     -- Top-plane leaf on the -X (counter-spring) arm: vertical
   base edge, two curved sides, short tip edge.
6. Summation anchor    -- Top-plane concentric ring (outer + bore) at the -X tip,
   the eye the counter-spring hangs from.
7. Middle rib          -- Front-plane elongated diamond spanning the lever, two
   tangent lines per side meeting two coradial arcs that wrap the cylinder.

Part-local frame: origin = the knife-edge line (placed at machine (15, 990, 0)),
+X = the channel-spring (coefficients-plate) arm, -X = the counter-spring
(summation-anchor) arm, +Y up, +Z along the knife edge (channel direction). The
.cs is authored with all X negated so this frame matches the M6.4 part the rest
of the machine was built against: the spring holes stay at their registered
local positions (so the 20 channel springs need no change) and the summation
anchor lands where the counter-spring boss-hook attaches (local x -76 ~ machine
91 ~ the M6.4 hook at 90.5). MIRROR_PLANE 'x0' (see _common) still applies.

Sketches follow the repo fully-defined convention (cad/scripts/_common.py): the
prismatic/polygon profiles via point-ref anchors + driving dims; each arc via
its neighbours' fixed endpoints plus a radial dim. Organic-arc volumes are not
analytically gated -- rely on the mass-properties report + ch30 renders.

Dimensions: cad/DIMENSIONS.md ch. 18 (legacy KCL values + M6.4 registration;
low/med confidence).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_summing_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    IN,
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
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

PART_NAME = "summing-lever"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# The .cs is authored with the coefficients plate on -X; the machine wants it on
# the +X arm (to match the M6.4 frame the rest of the assembly registers to), so
# every .cs-derived X is multiplied by SX.
SX = -1.0

# --- SummingLever.cs constants (inches -> mm) ------------------------------
PLATE_W = 1.75 * IN  # coefficients plate width (along the arm, X)   44.45
PLATE_L = 6.0 * IN  # coefficients/pivot length (along Z)           152.40
PLATE_T = 0.2 * IN  # plate thickness                                5.08
CYL_R = 0.5 * IN  # pivot cylinder radius                          12.70
RIB_T = 0.2 * IN  # edge / middle rib thickness                     5.08
RIB_PAD = 0.1 * IN  # rib arc padding over the cylinder              2.54
SUM_H = 3.0 * IN  # summation plate height (tip reach)             76.20
SUM_CURV = 0.3 * IN  # summation plate side curvature                7.62
ANCHOR_R = 0.375 * IN  # summation anchor outer radius               9.525
ANCHOR_H = 0.75 * IN  # summation anchor height                     19.05

# --- spring-hole registration (machine channel bank, NOT the tiny .cs holes) -
# The 20 channel SPRING-HOOKS seat in these holes (the springs themselves no
# longer thread the plate -- a separate open hook fastener does, per
# build_spring_hook.py / build_channel_assembly.py). Each hole holds a hook shank;
# its arm reaches +X back to the still-vertical spring eye above the plate.
HOLE_DIA = 2.0  # snug bore for the O1.4 spring-hook shank (0.3 radial clearance);
# was O4.5 (sized when the spring eye threaded the plate) -- far too big for the
# little hook shank that now seats here (the spring eye links the hook arm above)
HOLE_X = 39.85  # 37.10 (the spring-eye column) + 2.75: local +X maps to WORLD -X
# (world_x = 15 - local_x), so +2.75 local seats the hook shank one arm-offset to
# world -X of the eye, where its +X (world) arm reaches back to the eye (derived)
HOLE_COUNT = 20
CHANNEL_Z0 = -67.1  # frame channel j=0 (DIMENSIONS.md ch6)
CHANNEL_PITCH = 7.0565
HOLE_Z_OFFSET = 0.8  # coaxial with the spring axis (z_j + 0.8): no lead threads
# the bore anymore, so the old -2.75 lead offset is dropped (hook shank is on-axis)
# The plate is a true coplanar casting -- mid-plane ON the pivot (.cs shape):
# placed at the knife line y=990 it spans 987.46..992.54, so the top registers at
# machine 992.54 (NOT the old M6.4 998). The channel springs + magnifying bracket
# were dropped to meet it (build_channel_*: PLATE_TOP_Y/PLATE_EYE_Y;
# build_magnifying_bracket: FLANGE_Y). Consumed at PLACEMENT (the part is
# pivot-centred), not by any extrude here.
PLATE_TOP_Y = 992.54

# --- hex knife-edge protrusions (NEW; LOW confidence -- tune vs ch30) -------
# TWO trunnion stubs, one PROTRUDING BEYOND each body end (not flush inside):
# the lever's pivot overhangs the body so the knife edges rest on bearing
# supports standing on the top plate (ch30-p003). Each stub's top vertex line
# is the knife edge the lever is suspended/rocks on.
# Knife-edge trunnion cross-section: vertex-up hex, 8.653 wide (X) x 10.268 tall
# (Y, vertex to vertex) x 21.717 deep (Z protrusion). The top vertex ridge is
# the knife edge (= the rock axis, above the cylinder centreline).
HEX_W = 8.653  # across-flats width (X)
HEX_H = 10.268  # vertex-to-vertex height (Y) -- vertex-up
HEX_DEPTH = 21.717  # axial length each stub protrudes past the body end
HEX_Z_INNER = PLATE_L / 2.0  # inboard face flush with the body end (76.20)
HEX_Z_OUTER = HEX_Z_INNER + HEX_DEPTH  # outboard face overhangs the body (97.92)

# --- derived ---------------------------------------------------------------
SUM_BASE = PLATE_L / 2.0  # summation plate base length             76.20
TIP_X = SX * SUM_H  # summation tip / anchor x (counter-spring arm) -76.20
ARC_R = CYL_R + RIB_PAD  # rib arc radius wrapping the cylinder     15.24
RIB_OFFSET = PLATE_L / 2.0 - RIB_T  # edge-rib start offset along Z 71.12
ANCHOR_BORE_R = 1.5  # summation-anchor centre hole (counter-spring hook seat)
# The middle rib spans the lever to the +X plate edge (PLATE_W), but its z-span
# (+-RIB_T/2 = +-2.54) crosses the channel-hole column at HOLE_X. The rib extrude
# (feature 7) runs AFTER the holes (feature 1), so it re-fills the one hole whose
# z lands inside that span -- j=10 at z+1.515 -- leaving its spring no clear bore
# (the 4.21 mm^3 channel-spring-installed-6 clash). Stop the +X vertex inboard of
# the hole column by the spring coil radius (~3.25) + margin so every hole stays
# open; the rib still stiffens the inner lever, the outer plate arm is the (thin)
# spring-hole field.
MID_RIB_PLATE_REACH = HOLE_X - 4.1  # 35.75 local +X: clears the (shifted) hole column

# Spring-hole Z stations (world Z); the Top-plane sketch maps world Z to -sketchY.
HOLE_Z = [CHANNEL_Z0 + CHANNEL_PITCH * j + HOLE_Z_OFFSET for j in range(HOLE_COUNT)]

# Assembly-facing exports (build_summing_assembly imports these).
SPIN_REF_X = TIP_X  # local X of the summation-anchor bore = counter-spring ref


def _circumcenter(
    p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]
) -> tuple[float, float]:
    """Centre of the circle through three non-collinear points."""
    (ax, ay), (bx, by), (cx, cy) = p1, p2, p3
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        raise ValueError("circumcenter: collinear points")
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return ux, uy


async def _three_point_arc(
    adapter,
    start: tuple[float, float],
    end: tuple[float, float],
    interior: tuple[float, float],
    label: str,
) -> tuple[str, tuple[float, float], float]:
    """Draw the arc through ``start``/``interior``/``end`` (add_arc is CCW, so
    pick the start/end order whose CCW sweep passes the interior point).

    Returns ``(arc_id, centre, radius)``. The endpoints land exactly on
    ``start``/``end`` regardless of the chosen order, so neighbours still merge.
    """
    cx, cy = _circumcenter(start, end, interior)
    radius = math.hypot(start[0] - cx, start[1] - cy)

    def sweep(a: tuple[float, float], b: tuple[float, float]) -> float:
        t = math.atan2(b[1] - cy, b[0] - cx) - math.atan2(a[1] - cy, a[0] - cx)
        return t % (2.0 * math.pi)

    if sweep(start, interior) <= sweep(start, end):
        s, e = start, end
    else:
        s, e = end, start
    arc = await adapter.add_arc(cx, cy, s[0], s[1], e[0], e[1])
    return check(f"add_arc {label}", arc), (cx, cy), radius


async def _coefficients_plate(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 1: Top-plane plate on the +X arm (x in [0, w]); mid-plane extrude
    (PLATE_T total, centred on the pivot at local y 0) so the whole casting stays
    coplanar with the cylinder and ribs.

    The HOLE_COUNT spring holes are cut OUTRIGHT -- one Top-plane sketch holding
    a circle at every registered station HOLE_Z[0..HOLE_COUNT-1], a single
    cut-extrude. (Earlier this was a seed cut + FeatureLinearPattern5; the
    pattern marches along an auto-selected plate edge whose natural sense is
    ambiguous, and it silently reversed the field off the -Z plate edge -- only
    j=0 stayed cut, so every other spring eye clashed the un-cut bore. Explicit
    per-station circles are direction-free and deterministic.)

    Machine-y registration (the M6.4 plate-top-at-998 convention) is set at
    PLACEMENT, not baked here -- see PLATE_TOP_Y and the Phase 2/3 plan."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Top"))
    # +X arm: x in [0, PLATE_W], length along sketch Y (= world Z) in [-L/2, L/2].
    # NOT origin-centred (x runs 0..PLATE_W), so define_rectilinear_chain rather
    # than define_centered_rectangle. Emission order (rectilinear): the per-segment
    # distance dims skipping the last of each direction -- width (line0, horizontal
    # PLATE_W) then length (line1, vertical PLATE_L) -- THEN the anchor dims for the
    # corner (0, -L/2): x=0 drops, z (=-L/2) is one unsigned vertical distance.
    rect = [
        (0.0, -PLATE_L / 2.0),
        (PLATE_W, -PLATE_L / 2.0),
        (PLATE_W, PLATE_L / 2.0),
        (0.0, PLATE_L / 2.0),
    ]
    outline = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, outline, rect, label="plate", dims=plate,
        names=["PlateWidth", "PlateLength", "PlateAnchorZ"],
        drives=['"PlateW"', '"PlateL"', '"PlateL" / 2'],
    )
    await ensure_fully_defined(adapter, "coefficients plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude coefficients plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CoefficientsPlate")

    # All HOLE_COUNT spring holes in ONE sketch at the registered stations.
    # Top-plane sketch Y = -world Z, so world HOLE_Z[j] sits at sketch -HOLE_Z[j];
    # a single cut through BOTH sides of the mid-plane plate (both_directions
    # covers the +-PLATE_T/2 spread, + margin). Cutting every station outright
    # (no seed + linear pattern) keeps the field direction-free: a directional
    # FeatureLinearPattern5 marched along an auto-selected edge whose natural
    # sense reversed the field off the -Z plate edge, leaving all but j=0 solid.
    # Each off-axis circle emits centre-X, centre-Z, diameter (3 dims): X is the
    # shared HOLE_X column (driven to "HoleX"), diameter to "HoleDia"; the per-
    # station Z has no single global knob, so its slot stays None (auto-named).
    holes = SketchDims()
    check("create_sketch spring holes", await adapter.create_sketch("Top"))
    for j in range(HOLE_COUNT):
        await define_circle(
            adapter, HOLE_X, -HOLE_Z[j], HOLE_DIA / 2.0, f"spring hole {j}",
            dims=holes,
            names=(f"Hole{j}X", None, f"Hole{j}Dia"),
            drives=('"HoleX"', None, '"HoleDia"'),
        )
    await ensure_fully_defined(adapter, "spring-holes sketch")
    check("exit_sketch spring holes", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringHolesProfile")
    drive_jobs += holes.apply(adapter, "SpringHolesProfile")
    check(
        "cut spring holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PLATE_T + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SpringHoles")


async def _pivot_cylinder(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 2: Front-plane solid circle at origin, symmetric extrude along the
    long edge -- the pivot/rock axis (local Z). NO bore."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    # Origin circle: only the diameter is a dim (the centre is a coincident
    # relation), so define_circle records just that one slot.
    cyl = SketchDims()
    check("create_sketch cylinder", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, CYL_R, "pivot cylinder", dims=cyl,
        names=("CylCx", "CylCz", "CylDia"),
        drives=(None, None, '"CylR" * 2'),
    )
    await ensure_fully_defined(adapter, "pivot cylinder sketch")
    check("exit_sketch cylinder", await adapter.exit_sketch())
    name_last_feature(adapter, "CylinderProfile")
    drive_jobs += cyl.apply(adapter, "CylinderProfile")
    check(
        "extrude cylinder",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_L, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotCylinder")


async def _hex_collar(
    adapter, flip: bool, name: str, stem: str, drive_jobs: list[tuple[str, str]]
) -> None:
    """One hexagonal knife-edge trunnion stub PROTRUDING beyond a body end,
    vertex-up, blind-extruded along Z over |z| HEX_Z_INNER..HEX_Z_OUTER -- i.e.
    from the body end face out into open air (flip = the -Z end). The overhang
    lets the knife edge rest on a bearing support standing on the top plate.

    Front-plane vertex-up hexagon (HEX_W x HEX_H bounding box) centred on the
    pivot axis, a vertex at the top (the knife edge runs along Z at that top
    vertex line)."""
    hexd = SketchDims()
    check(f"create_sketch {name}", await adapter.create_sketch("Front"))
    # Vertex-up hexagon fit to the measured box: top/bottom vertices on the
    # y-axis, shoulders at +-W/2 and +-H/4 (CCW from the top vertex).
    w2, h2, h4 = HEX_W / 2.0, HEX_H / 2.0, HEX_H / 4.0
    verts = [
        (0.0, h2),  # top vertex (the knife edge ridge)
        (-w2, h4),  # upper-left shoulder
        (-w2, -h4),  # lower-left shoulder
        (0.0, -h2),  # bottom vertex
        (w2, -h4),  # lower-right shoulder
        (w2, h4),  # upper-right shoulder
    ]
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, verts)
    set_sketch_direct_db(adapter, False)
    # Emission order (polygon, anchor=v0 at (0, +h2)): anchor dims first (x=0
    # drops, y=h2 is one) THEN each kept segment's offsets in line order; the
    # segment closing onto v0 (line5) is skipped. All offsets are halves/quarters
    # of HexW/HexH, so drive every dim off those two globals.
    _hw = '"HexW" / 2'
    _hh2 = '"HexH" / 2'
    _hh4 = '"HexH" / 4'
    await define_polygon_chain(
        adapter, lines, verts, label=name, dims=hexd,
        names=[f"{stem}TopY",
               f"{stem}S0dx", f"{stem}S0dy",
               f"{stem}S1dy",
               f"{stem}S2dx", f"{stem}S2dy",
               f"{stem}S3dx", f"{stem}S3dy",
               f"{stem}S4dy"],
        drives=[_hh2,
                _hw, _hh4,
                _hh2,
                _hw, _hh4,
                _hw, _hh4,
                _hh2],
    )
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{stem}Profile")
    drive_jobs += hexd.apply(adapter, f"{stem}Profile")
    extrude_at_offset(adapter, HEX_Z_OUTER - HEX_Z_INNER, HEX_Z_INNER, flip=flip)
    name_last_feature(adapter, stem)


async def _edge_rib(
    adapter, flip: bool, name: str, stem: str, drive_jobs: list[tuple[str, str]]
) -> None:
    """Feature 4: Front-plane rib -- two lines to the plate-edge tip and a
    semicircle (radius ARC_R, centred at the origin) wrapping the cylinder,
    blind-extruded at the +-RIB_OFFSET start offset along Z.

    Vertices (A, C on the arc, B the +X plate tip): the arc centre is the origin
    (the two y-symmetric ends + the cylinder-side interior point force it there),
    so it defines off a coincident-to-origin centre + a radial dim, with A/C
    pinned on the y-axis."""
    rib = SketchDims()
    check(f"create_sketch {name}", await adapter.create_sketch("Front"))
    a, b, c = (0.0, ARC_R), (SX * -PLATE_W, 0.0), (0.0, -ARC_R)
    interior = (SX * ARC_R, 0.0)  # cylinder-side point the arc passes through
    set_sketch_direct_db(adapter, True)
    line_ab = check(f"{name} line A-B", await adapter.add_line(*a, *b))
    line_bc = check(f"{name} line B-C", await adapter.add_line(*b, *c))
    arc, _, _ = await _three_point_arc(adapter, c, a, interior, f"{name} arc")
    set_sketch_direct_db(adapter, False)
    check(
        f"{name} arc centre -> origin",
        await adapter.add_sketch_constraint(f"{arc}.center", "origin", "coincident"),
    )
    # Two display dims, recorded in creation order: the arc radius (-> "ArcR")
    # then the tip's horizontal distance from the origin (b is at +PLATE_W since
    # SX=-1, unsigned magnitude PLATE_W -> "PlateW").
    check(
        f"{name} arc radius",
        await adapter.add_sketch_dimension(arc, None, "radial", ARC_R),
    )
    rib.record(f"{stem}ArcR", '"ArcR"')
    check(
        f"{name} arc start on y-axis",
        await adapter.add_sketch_constraint(f"{arc}.start", "origin", "vertical_points"),
    )
    check(
        f"{name} arc end on y-axis",
        await adapter.add_sketch_constraint(f"{arc}.end", "origin", "vertical_points"),
    )
    await anchor_point_to_origin(adapter, f"{line_ab}.end", *b, f"{name} tip")
    rib.record(f"{stem}Tip", '"PlateW"')
    _ = line_bc
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{stem}Profile")
    drive_jobs += rib.apply(adapter, f"{stem}Profile")
    extrude_at_offset(adapter, RIB_T, RIB_OFFSET, flip=flip)
    name_last_feature(adapter, stem)


async def _summation_plate(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 5: Top-plane leaf on the -X arm -- vertical base edge (x=0), two
    curved sides, short tip edge at the anchor (x=TIP_X)."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    sd = SketchDims()
    check("create_sketch summation plate", await adapter.create_sketch("Top"))
    p1 = (0.0, -SUM_BASE)
    p2 = (0.0, SUM_BASE)
    p3 = (TIP_X, ANCHOR_R)
    p4 = (TIP_X, -ANCHOR_R)
    top_int = (SX * SUM_H / 2.0, SUM_BASE / 2.0 - SUM_CURV)
    bot_int = (SX * SUM_H / 2.0, -SUM_BASE / 2.0 + SUM_CURV)

    set_sketch_direct_db(adapter, True)
    base = check("summation base edge", await adapter.add_line(*p1, *p2))
    top_arc, top_c, _ = await _three_point_arc(adapter, p2, p3, top_int, "summation top")
    tip = check("summation tip edge", await adapter.add_line(*p3, *p4))
    bot_arc, bot_c, _ = await _three_point_arc(adapter, p4, p1, bot_int, "summation bottom")
    set_sketch_direct_db(adapter, False)

    # Record each manual dim in creation order. Unsigned-distance anchors at
    # negative coordinates negate the (negative) source so the drive evaluates
    # positive: base start at y=-SUM_BASE drives "PlateL" / 2; the tip-end anchor
    # at (TIP_X<0, -ANCHOR_R) drives |TIP_X|="SumH" then "AnchorR". The two arc
    # centres are circumcentre-derived (no clean global), left None.
    check(
        "summation base vertical",
        await adapter.add_sketch_constraint(base, None, "vertical"),
    )
    await anchor_point_to_origin(adapter, f"{base}.start", *p1, "summation base start")
    sd.record("SumBaseStartZ", '"PlateL" / 2')  # vertical_distance = SUM_BASE
    await dimension_between(
        adapter, f"{base}.start", f"{base}.end", "vertical_distance", PLATE_L, "summation base"
    )
    sd.record("SumBaseLength", '"PlateL"')
    check(
        "summation tip vertical",
        await adapter.add_sketch_constraint(tip, None, "vertical"),
    )
    await anchor_point_to_origin(adapter, f"{tip}.end", *p4, "summation tip end")
    sd.record("SumTipX", '"SumH"')  # horizontal_distance = |TIP_X| = SUM_H
    sd.record("SumTipZ", '"AnchorR"')  # vertical_distance = ANCHOR_R
    await dimension_between(
        adapter, f"{tip}.start", f"{tip}.end", "vertical_distance", 2.0 * ANCHOR_R, "summation tip"
    )
    sd.record("SumTipHeight", '2 * "AnchorR"')
    # The base/tip lines pin all four corners; each curved side is then defined
    # by anchoring its (circumcentre) centre -- endpoints already lie on the arc,
    # so the radius is implied and a radial dim would over-define (cf. the
    # magnifying-lever dome caps). Both centres are general points (x, y both
    # nonzero) -> two dims each, no clean global knob, left auto-named.
    await anchor_point_to_origin(adapter, f"{top_arc}.center", *top_c, "summation top centre")
    sd.record(None, None)
    sd.record(None, None)
    await anchor_point_to_origin(adapter, f"{bot_arc}.center", *bot_c, "summation bottom centre")
    sd.record(None, None)
    sd.record(None, None)
    await ensure_fully_defined(adapter, "summation plate sketch")
    check("exit_sketch summation plate", await adapter.exit_sketch())
    name_last_feature(adapter, "SummationPlateProfile")
    drive_jobs += sd.apply(adapter, "SummationPlateProfile")
    check(
        "extrude summation plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SummationPlate")


async def _summation_anchor(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 6: Top-plane concentric ring (outer ANCHOR_R, bore ANCHOR_BORE_R)
    at the -X tip -- the eye the counter-spring hook hangs from."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    # Both circles share centre (TIP_X, 0): centre-X is a dim (driven to "SumH",
    # |TIP_X|), centre-Z (=0) is a relation (slot ignored), plus each diameter.
    sd = SketchDims()
    check("create_sketch summation anchor", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter, TIP_X, 0.0, ANCHOR_R, "anchor outer", dims=sd,
        names=("AnchorOuterX", "AnchorOuterZ", "AnchorOuterDia"),
        drives=('"SumH"', None, '2 * "AnchorR"'),
    )
    await define_circle(
        adapter, TIP_X, 0.0, ANCHOR_BORE_R, "anchor bore", dims=sd,
        names=("AnchorBoreX", "AnchorBoreZ", "AnchorBoreDia"),
        # Bore is concentric with the outer (same centre): the outer's X dim
        # already locates the ring, so driving the bore's X too over-constrains
        # the solve (rebuild fails). Record it (count) but leave it undriven.
        drives=(None, None, '2 * "AnchorBoreR"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "summation anchor sketch")
    check("exit_sketch summation anchor", await adapter.exit_sketch())
    name_last_feature(adapter, "SummationAnchorProfile")
    drive_jobs += sd.apply(adapter, "SummationAnchorProfile")
    check(
        "extrude summation anchor",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ANCHOR_H, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SummationAnchor")


async def _middle_rib(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 7: Front-plane elongated diamond spanning the lever. Two tangent
    lines run from each end vertex (left = +X plate edge, right = -X summation
    tip) to two coradial arcs that wrap the cylinder -- the C# tangent / coradial
    construction, pinned to scale by the end-vertex anchors, the arc centre at
    the origin, and the arc radius."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    sd = SketchDims()
    check("create_sketch middle rib", await adapter.create_sketch("Front"))
    left = (SX * -MID_RIB_PLATE_REACH, 0.0)  # +X arm vertex, short of hole column
    right = (TIP_X, 0.0)  # -X summation-tip vertex
    r = ARC_R
    # Tangent points from each end vertex to the radius-r circle at the origin.
    tx_l, ty_l = (r * r) / left[0], r * math.sqrt(1.0 - (r * r) / (left[0] ** 2))
    tx_r, ty_r = (r * r) / right[0], r * math.sqrt(1.0 - (r * r) / (right[0] ** 2))
    tl_up, tr_up = (tx_l, ty_l), (tx_r, ty_r)
    tl_dn, tr_dn = (tx_l, -ty_l), (tx_r, -ty_r)

    set_sketch_direct_db(adapter, True)
    line1 = check("middle rib line1", await adapter.add_line(*left, *tl_up))
    arc1, _, _ = await _three_point_arc(adapter, tl_up, tr_up, (0.0, r), "middle rib upper")
    line2 = check("middle rib line2", await adapter.add_line(*tr_up, *right))
    line3 = check("middle rib line3", await adapter.add_line(*right, *tr_dn))
    arc2, _, _ = await _three_point_arc(adapter, tr_dn, tl_dn, (0.0, -r), "middle rib lower")
    line4 = check("middle rib line4", await adapter.add_line(*tl_dn, *left))
    set_sketch_direct_db(adapter, False)

    for seg_a, seg_b, lbl in (
        (line1, arc1, "line1-arc1"),
        (arc1, line2, "arc1-line2"),
        (line3, arc2, "line3-arc2"),
        (arc2, line4, "arc2-line4"),
    ):
        check(
            f"middle rib tangent {lbl}",
            await adapter.add_sketch_constraint(seg_a, seg_b, "tangent"),
        )
    # coradial forces arc2 to share arc1's centre AND radius (one circle); each
    # tangent line runs from a fixed end-vertex to that fixed circle, so the four
    # tangent points are pinned without an explicit symmetric relation (which,
    # over the already-symmetric coordinates, would over-define).
    check(
        "middle rib coradial",
        await adapter.add_sketch_constraint(arc1, arc2, "coradial"),
    )
    check(
        "middle rib arc centre -> origin",
        await adapter.add_sketch_constraint(f"{arc1}.center", "origin", "coincident"),
    )
    # Three display dims in creation order: the shared arc radius (-> "ArcR"),
    # then each end-vertex anchor (both on the x-axis -> one horizontal dim each).
    # left is at +MID_RIB_PLATE_REACH (SX=-1), right at TIP_X<0 -- both unsigned
    # magnitudes positive, so "MidRibReach" and "SumH" (|TIP_X|).
    check(
        "middle rib arc radius",
        await adapter.add_sketch_dimension(arc1, None, "radial", r),
    )
    sd.record("MidRibArcR", '"ArcR"')
    await anchor_point_to_origin(adapter, f"{line1}.start", *left, "middle rib left vertex")
    sd.record("MidRibLeftX", '"MidRibReach"')
    await anchor_point_to_origin(adapter, f"{line2}.end", *right, "middle rib right vertex")
    sd.record("MidRibRightX", '"SumH"')
    await ensure_fully_defined(adapter, "middle rib sketch")
    check("exit_sketch middle rib", await adapter.exit_sketch())
    name_last_feature(adapter, "MiddleRibProfile")
    drive_jobs += sd.apply(adapter, "MiddleRibProfile")
    check(
        "extrude middle rib",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RIB_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "MiddleRib")


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs: named globals in the equation manager that drive every
    # sketch dim below (a GUI fine-tune edits THESE -- Tools > Equations -- never
    # an auto "D3@Sketch5"). Every length carries an explicit ``mm`` unit: this is
    # an INCH document and the equation manager evaluates BARE numbers in document
    # units, so an unsuffixed "152.4" would read as 152.4 inches and blow the part
    # up 25.4x. Derived globals (ArcR, MidRibReach) reference others as equation
    # strings so a primitive edit propagates. PlateT/RibT/AnchorH/HexDepth are
    # extrude depths/offsets -- feature params, not sketch dims, so nothing drives
    # them, but they stay editable knobs (matches the exemplars).
    await set_global(adapter, "PlateW", f"{PLATE_W}mm")
    await set_global(adapter, "PlateL", f"{PLATE_L}mm")
    await set_global(adapter, "PlateT", f"{PLATE_T}mm")
    await set_global(adapter, "CylR", f"{CYL_R}mm")
    await set_global(adapter, "RibT", f"{RIB_T}mm")
    await set_global(adapter, "RibPad", f"{RIB_PAD}mm")
    await set_global(adapter, "SumH", f"{SUM_H}mm")
    await set_global(adapter, "AnchorR", f"{ANCHOR_R}mm")
    await set_global(adapter, "AnchorBoreR", f"{ANCHOR_BORE_R}mm")
    await set_global(adapter, "AnchorH", f"{ANCHOR_H}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")
    await set_global(adapter, "HoleX", f"{HOLE_X}mm")
    await set_global(adapter, "HexW", f"{HEX_W}mm")
    await set_global(adapter, "HexH", f"{HEX_H}mm")
    await set_global(adapter, "HexDepth", f"{HEX_DEPTH}mm")
    await set_global(adapter, "ArcR", '"CylR" + "RibPad"')
    await set_global(adapter, "MidRibReach", '"HoleX" - 4.1mm')

    # Per-sketch SketchDims record each dim in the helper's emission order; their
    # drive equations are collected here and applied in one deferred batch at the
    # end (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    await _coefficients_plate(adapter, drive_jobs)
    await _pivot_cylinder(adapter, drive_jobs)
    await _hex_collar(adapter, flip=False, name="hex knife edge front",
                      stem="HexKnifeFront", drive_jobs=drive_jobs)
    await _hex_collar(adapter, flip=True, name="hex knife edge back",
                      stem="HexKnifeBack", drive_jobs=drive_jobs)
    await _edge_rib(adapter, flip=False, name="edge rib front",
                    stem="EdgeRibFront", drive_jobs=drive_jobs)
    await _edge_rib(adapter, flip=True, name="edge rib back",
                    stem="EdgeRibBack", drive_jobs=drive_jobs)
    await _summation_plate(adapter, drive_jobs)
    await _summation_anchor(adapter, drive_jobs)
    await _middle_rib(adapter, drive_jobs)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move; the neutrality re-check is the proof.
    # No analytic volume gate exists for this part (organic arcs), so capture the
    # as-built volume and assert it is unchanged after driving.
    await force_rebuild(adapter)
    _mass = await adapter.get_mass_properties()
    if not _mass.is_success:
        raise RuntimeError(f"as-built mass props failed: {_mass.error}")
    v_built = float(_mass.data.volume)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven summing lever (equations neutral)", v_built, 1e-3 * v_built
    )

    # pivot axis (Axis1) = cylinder centreline along Z -- the static mate
    # reference to the knife-mount (keeps the lever at the knife line with no
    # drop until the ridge bearing supports exist).
    # anchor axis (Axis2) = Z line at the summation anchor -- counter-spring rock
    # reference (the anchor BORE itself is vertical, along Y).
    # knife axis (Axis3) = the hex top-vertex ridge (local y +HEX_H/2) = the true
    # rock/suspension line the lever hangs from; the pivot revolute moves here
    # once the top-plate bearing supports are modeled.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "pivot axis")
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", TIP_X, "anchor axis")
    await name_bore_axis(adapter, "Top Plane", HEX_H / 2.0, "Right Plane", 0.0, "knife axis")

    await apply_material(adapter, MATERIAL)
    # Green-painted casting on the machine (ch17/ch18 macros show the same
    # paint as the frame), not bare cast iron.
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
