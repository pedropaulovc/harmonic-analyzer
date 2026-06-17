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

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_summing_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    define_rectilinear_chain,
    dimension_between,
    ensure_fully_defined,
    extrude_at_offset,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
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
# The 20 channel springs thread these holes; positions reused verbatim from the
# M6.4 part so build_channel_assembly / build_channel_spring_installed need no
# change (cad/DIMENSIONS.md ch18 row 4).
HOLE_DIA = 4.5  # installed eye threads the 5.1 plate (med)
HOLE_X = 37.10  # local +X = machine x +22.10 = channel-lever tab line (derived)
HOLE_COUNT = 20
CHANNEL_Z0 = -67.1  # frame channel j=0 (DIMENSIONS.md ch6)
CHANNEL_PITCH = 7.0565
HOLE_Z_OFFSET = 0.8 - 2.75  # -1.95: hole under the spring's bottom lead
PLATE_TOP_Y = 998.0  # machine-y the plate top registers to at PLACEMENT (med);
# the part itself is centred on the pivot (mid-plane), so this is consumed by
# build_output_assembly's component Y, not by any extrude here.

# --- hex knife-edge protrusions (NEW; LOW confidence -- tune vs ch30) -------
# TWO trunnion stubs, one PROTRUDING BEYOND each body end (not flush inside):
# the lever's pivot overhangs the body so the knife edges rest on bearing
# supports standing on the top plate (ch30-p003). Each stub's top vertex line
# is the knife edge the lever is suspended/rocks on.
HEX_R = 16.0  # vertex radius of the knife-edge hex stub (> CYL_R so it
# protrudes); vertex-up so the top vertex line is the knife edge (low)
HEX_WIDTH = 20.0  # axial length each stub protrudes past the body end (low)
HEX_Z_INNER = PLATE_L / 2.0  # inboard face flush with the body end (76.20)
HEX_Z_OUTER = HEX_Z_INNER + HEX_WIDTH  # outboard face overhangs the body (96.20)

# --- derived ---------------------------------------------------------------
SUM_BASE = PLATE_L / 2.0  # summation plate base length             76.20
TIP_X = SX * SUM_H  # summation tip / anchor x (counter-spring arm) -76.20
ARC_R = CYL_R + RIB_PAD  # rib arc radius wrapping the cylinder     15.24
RIB_OFFSET = PLATE_L / 2.0 - RIB_T  # edge-rib start offset along Z 71.12
ANCHOR_BORE_R = 1.5  # summation-anchor centre hole (counter-spring hook seat)

# Spring-hole Z stations (world Z); the Top-plane sketch maps world Z to -sketchY.
HOLE_Z = [CHANNEL_Z0 + CHANNEL_PITCH * j + HOLE_Z_OFFSET for j in range(HOLE_COUNT)]

# Assembly-facing exports (build_output_assembly imports these).
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


async def _coefficients_plate(adapter) -> None:
    """Feature 1: Top-plane plate on the +X arm (x in [0, w]) carrying the 20
    spring holes; mid-plane extrude (PLATE_T total, centred on the pivot at
    local y 0) so the whole casting stays coplanar with the cylinder and ribs.

    Machine-y registration (the M6.4 plate-top-at-998 convention) is set at
    PLACEMENT, not baked here -- see PLATE_TOP_Y and the Phase 2/3 plan."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch plate", await adapter.create_sketch("Top"))
    # +X arm: x in [0, PLATE_W], length along sketch Y (= world Z) in [-L/2, L/2].
    rect = [
        (0.0, -PLATE_L / 2.0),
        (PLATE_W, -PLATE_L / 2.0),
        (PLATE_W, PLATE_L / 2.0),
        (0.0, PLATE_L / 2.0),
    ]
    outline = await add_line_chain(adapter, rect)
    # Direct-to-DB: inference around the freshly dimensioned neighbour makes
    # add_circle fail from the second hole on (proven on the M6.4 plate).
    set_sketch_direct_db(adapter, True)
    for j, z in enumerate(HOLE_Z):
        # Top-plane sketch Y = -world Z, so a hole at world z sits at sketch -z.
        await define_circle(adapter, HOLE_X, -z, HOLE_DIA / 2.0, f"hole {j + 1}")
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(adapter, outline, rect, label="plate")
    await ensure_fully_defined(adapter, "coefficients plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())
    check(
        "extrude coefficients plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_T, both_directions=True)
        ),
    )


async def _pivot_cylinder(adapter) -> None:
    """Feature 2: Front-plane solid circle at origin, symmetric extrude along the
    long edge -- the pivot/rock axis (local Z). NO bore."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch cylinder", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, CYL_R, "pivot cylinder")
    await ensure_fully_defined(adapter, "pivot cylinder sketch")
    check("exit_sketch cylinder", await adapter.exit_sketch())
    check(
        "extrude cylinder",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_L, both_directions=True)
        ),
    )


async def _hex_collar(adapter, flip: bool, name: str) -> None:
    """One hexagonal knife-edge trunnion stub PROTRUDING beyond a body end,
    vertex-up, blind-extruded along Z over |z| HEX_Z_INNER..HEX_Z_OUTER -- i.e.
    from the body end face out into open air (flip = the -Z end). The overhang
    lets the knife edge rest on a bearing support standing on the top plate.

    Front-plane regular hexagon centred on the pivot axis, a vertex at the top
    (the knife edge runs along Z at that top vertex line)."""
    check(f"create_sketch {name}", await adapter.create_sketch("Front"))
    # Vertex-up hexagon: vertices at 90, 150, 210, 270, 330, 30 degrees.
    verts = [
        (HEX_R * math.cos(math.radians(a)), HEX_R * math.sin(math.radians(a)))
        for a in (90.0, 150.0, 210.0, 270.0, 330.0, 30.0)
    ]
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, verts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, lines, verts, label=name)
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    extrude_at_offset(adapter, HEX_Z_OUTER - HEX_Z_INNER, HEX_Z_INNER, flip=flip)


async def _edge_rib(adapter, flip: bool, name: str) -> None:
    """Feature 4: Front-plane rib -- two lines to the plate-edge tip and a
    semicircle (radius ARC_R, centred at the origin) wrapping the cylinder,
    blind-extruded at the +-RIB_OFFSET start offset along Z.

    Vertices (A, C on the arc, B the +X plate tip): the arc centre is the origin
    (the two y-symmetric ends + the cylinder-side interior point force it there),
    so it defines off a coincident-to-origin centre + a radial dim, with A/C
    pinned on the y-axis."""
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
    check(
        f"{name} arc radius",
        await adapter.add_sketch_dimension(arc, None, "radial", ARC_R),
    )
    check(
        f"{name} arc start on y-axis",
        await adapter.add_sketch_constraint(f"{arc}.start", "origin", "vertical_points"),
    )
    check(
        f"{name} arc end on y-axis",
        await adapter.add_sketch_constraint(f"{arc}.end", "origin", "vertical_points"),
    )
    await anchor_point_to_origin(adapter, f"{line_ab}.end", *b, f"{name} tip")
    _ = line_bc
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    extrude_at_offset(adapter, RIB_T, RIB_OFFSET, flip=flip)


async def _summation_plate(adapter) -> None:
    """Feature 5: Top-plane leaf on the -X arm -- vertical base edge (x=0), two
    curved sides, short tip edge at the anchor (x=TIP_X)."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

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

    check(
        "summation base vertical",
        await adapter.add_sketch_constraint(base, None, "vertical"),
    )
    await anchor_point_to_origin(adapter, f"{base}.start", *p1, "summation base start")
    await dimension_between(
        adapter, f"{base}.start", f"{base}.end", "vertical_distance", PLATE_L, "summation base"
    )
    check(
        "summation tip vertical",
        await adapter.add_sketch_constraint(tip, None, "vertical"),
    )
    await anchor_point_to_origin(adapter, f"{tip}.end", *p4, "summation tip end")
    await dimension_between(
        adapter, f"{tip}.start", f"{tip}.end", "vertical_distance", 2.0 * ANCHOR_R, "summation tip"
    )
    # The base/tip lines pin all four corners; each curved side is then defined
    # by anchoring its (circumcentre) centre -- endpoints already lie on the arc,
    # so the radius is implied and a radial dim would over-define (cf. the
    # magnifying-lever dome caps).
    await anchor_point_to_origin(adapter, f"{top_arc}.center", *top_c, "summation top centre")
    await anchor_point_to_origin(adapter, f"{bot_arc}.center", *bot_c, "summation bottom centre")
    await ensure_fully_defined(adapter, "summation plate sketch")
    check("exit_sketch summation plate", await adapter.exit_sketch())
    check(
        "extrude summation plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_T, both_directions=True)
        ),
    )


async def _summation_anchor(adapter) -> None:
    """Feature 6: Top-plane concentric ring (outer ANCHOR_R, bore ANCHOR_BORE_R)
    at the -X tip -- the eye the counter-spring hook hangs from."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch summation anchor", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, TIP_X, 0.0, ANCHOR_R, "anchor outer")
    await define_circle(adapter, TIP_X, 0.0, ANCHOR_BORE_R, "anchor bore")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "summation anchor sketch")
    check("exit_sketch summation anchor", await adapter.exit_sketch())
    check(
        "extrude summation anchor",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ANCHOR_H, both_directions=True)
        ),
    )


async def _middle_rib(adapter) -> None:
    """Feature 7: Front-plane elongated diamond spanning the lever. Two tangent
    lines run from each end vertex (left = +X plate edge, right = -X summation
    tip) to two coradial arcs that wrap the cylinder -- the C# tangent / coradial
    construction, pinned to scale by the end-vertex anchors, the arc centre at
    the origin, and the arc radius."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch middle rib", await adapter.create_sketch("Front"))
    left = (SX * -PLATE_W, 0.0)  # +X plate-edge vertex
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
    check(
        "middle rib arc radius",
        await adapter.add_sketch_dimension(arc1, None, "radial", r),
    )
    await anchor_point_to_origin(adapter, f"{line1}.start", *left, "middle rib left vertex")
    await anchor_point_to_origin(adapter, f"{line2}.end", *right, "middle rib right vertex")
    await ensure_fully_defined(adapter, "middle rib sketch")
    check("exit_sketch middle rib", await adapter.exit_sketch())
    check(
        "extrude middle rib",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RIB_T, both_directions=True)
        ),
    )


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    await _coefficients_plate(adapter)
    await _pivot_cylinder(adapter)
    await _hex_collar(adapter, flip=False, name="hex knife edge front")
    await _hex_collar(adapter, flip=True, name="hex knife edge back")
    await _edge_rib(adapter, flip=False, name="edge rib front")
    await _edge_rib(adapter, flip=True, name="edge rib back")
    await _summation_plate(adapter)
    await _summation_anchor(adapter)
    await _middle_rib(adapter)

    # pivot axis = local Z through the origin = the knife/rock axis (the
    # suspension line). anchor axis = local Z through the summation-anchor bore
    # = the counter-spring/boss-hook reference (replaces the M6.4 "spin ref").
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "pivot axis")
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", TIP_X, "anchor axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
