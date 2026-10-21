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
3. Hex knife edges     -- ONE vertex-up hexagonal prism through the pivot,
   extruded mid-plane out past both body ends: the two trunnion stubs it
   leaves PROTRUDE beyond the body (one per side), so each knife edge rests
   on a bearing support on the top plate (ch30-p003), and the stubs share
   every side face's plane by construction (code review C09).
4. Edge ribs (x2)      -- Front-plane line/line/semicircle wrapping the cylinder
   at the plate ends, blind-extruded at a start offset.
5. Summation plate     -- Top-plane leaf on the -X (counter-spring) arm: vertical
   base edge, two curved sides, short tip edge.
6. Summation anchor    -- Top-plane concentric ring (outer + bore) at the -X tip,
   the eye the counter-spring hangs from.
7. Middle rib          -- Front-plane elongated diamond spanning the lever, two
   tangent lines per side meeting two coradial arcs that wrap the cylinder.

Part-local frame: origin = the knife-edge line, placed IDENTITY at machine
(-15, 979.7, 0), so local axes ARE machine axes: +X = the channel-spring
(coefficients-plate) arm (machine west), -X = the counter-spring
(summation-anchor) arm (machine east), +Y up, +Z along the knife edge
(channel direction). The spring holes sit at their registered local
positions (so the 20 channel springs need no change) and the summation
anchor lands where the counter-spring boss-hook attaches (local x -76 ->
machine -91 ~ the M6.4 hook at -90.5).

Sketches follow the repo fully-defined convention (cad/scripts/_sketch.py): the
prismatic/polygon profiles via point-ref anchors + driving dims; each arc via
its neighbours' fixed endpoints plus a radial dim. Organic-arc volumes are not
analytically gated -- rely on the mass-properties report + ch30 renders.

Dimensions: cad/DIMENSIONS.md ch. 18 (legacy KCL values + M6.4 registration;
low/med confidence).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sm_summing_lever.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import CASTING_GREEN, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _extrude import extrude_at_offset
from _feature_tree import _feature_by_name, name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _paths import IN
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_polygon_chain, define_rectilinear_chain
from _sketch_circle import define_circle
from _hole_spec import blind_cut_dia_mm
from _holes import wizard_holes
from magnifying_bracket_joint_layout import (
    LEVER_HOLE_POINTS,
    TAP_SPEC,
    TAP_DRILL_DIA,
    DRILL_DEPTH,
    DRILL_POINT_DEPTH,
    DRILL_DEPTH_DEVIATIONS,
    THREAD_DEPTH_BAND,
    RIB_DEPTH as RECEIVER_RIB_T,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_dimension_insert import add_angular_reference_dimension
from _drawing_tolerances import (
    set_dimension_symmetric_angular_tolerance,
    set_dimension_symmetric_tolerance,
)
from _drawing_precision import _named_dimension, set_dimension_display_precision
from _fit_deviations import deviations
from _drawing_prefix import set_dimension_prefix
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from sm_summing_lever_notes import (
    BACK_VIEW_NOTE,
    CYLINDER_REFERENCE_Z,
    DIMENSION_PREFIXES,
    DRAWING_DIMENSIONS,
    FRONT_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    MIDDLE_RIB_PLAN_NOTE,
    STUB_ROOT_VIEW_NOTE,
)
from sm_summing_lever_spec import (
    ANCHOR_H,
    ARC_R,
    CHANNEL_PITCH,
    CHANNEL_Z0,
    COUNTER_HOLE_SPEC,
    HOLE_COUNT,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_OFFSET,
    INSIDE_CORNER_R_TOL_TYPE,
    KNIFE_FLANK_TO_SIDE_TOL_DEG,
    KNIFE_RIDGE_R,
    KNIFE_RIDGE_R_BAND,
    KNIFE_RIDGE_R_TOL_TYPE,
    KNIFE_RIDGE_TANGENT_XY,
    RIB_END_R,
    RIB_END_R_BAND,
    RIB_PAD,
    RIB_PLATE_REACH,
    RIDGE_ANGLE_DEG,
    RIDGE_FROM_SIDE_TOL,
    SPRING_PAD_W,
    SPRING_SEAT_T,
    STUB_ROOT_R,
    STUB_ROOT_R_BAND,
    SURFACE_FINISHES,
)

PART_NAME = "sm-summing-lever"
MATERIAL = "Gray Cast Iron"  # see _appearance.apply_material docstring

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
SUM_H = 3.0 * IN  # summation plate height (tip reach)             76.20
SUM_CURV = 0.3 * IN  # summation plate side curvature                7.62
ANCHOR_R = 0.375 * IN  # summation anchor outer radius               9.525
# ANCHOR_H (19.05, the boss height and the counter anchor's engagement) is the
# pure spec's -- build_sm_vn_boss_hook trims the purchased shank to it.

# The 20 channel-spring anchors THREAD into the part-owned native tap pattern.
# The plate is a true coplanar casting -- mid-plane ON the pivot (.cs shape):
# placed at the knife line y=979.7 it spans 977.16..982.24, so the top registers
# at machine 982.24 (the whole summing chain dropped 10.3 with the top-frame
# rederive). The channel springs + magnifying bracket meet it
# (build_channel_*: PLATE_TOP_Y/PLATE_EYE_Y; build_mg_magnifying_bracket:
# FLANGE_Y). Consumed at PLACEMENT (the part is pivot-centred), not by any
# extrude here.
PLATE_TOP_Y = 982.24

# --- hex knife-edge protrusions (NEW; LOW confidence -- tune vs ch30) -------
# TWO trunnion stubs, one PROTRUDING BEYOND each body end (not flush inside):
# the lever's pivot overhangs the body so the knife edges rest on bearing
# supports standing on the top plate (ch30-p003). Each stub's top vertex line
# is the knife edge the lever is suspended/rocks on.
# Knife-edge trunnion cross-section: vertex-up hex, 8.080 wide (X) x 10.268 tall
# (Y, vertex to vertex) x 21.717 deep (Z protrusion). The top vertex ridge is
# the knife edge (= the rock axis, above the cylinder centreline).
# Both stubs are one prism (``_hex_knife``): one sketch extruded through the
# body from -HEX_Z_OUTER to +HEX_Z_OUTER.  Every vertex lies inside the
# solid pivot cylinder (circumradius HEX_H/2 < CYL_R), so between the body
# ends the prism merges into it and the solid is the two stubs' alone.
HEX_W = 8.080  # across-flats width (X); = sm_summing_lever_spec.HEX_W
HEX_H = 10.268  # vertex-to-vertex height (Y) -- vertex-up
HEX_DEPTH = 21.717  # axial length each stub protrudes past the body end
HEX_Z_INNER = PLATE_L / 2.0  # inboard face flush with the body end (76.20)
HEX_Z_OUTER = HEX_Z_INNER + HEX_DEPTH  # outboard face overhangs the body (97.92)
if not HEX_H / 2.0 < CYL_R:
    raise AssertionError("the knife prism must lie inside the pivot cylinder")
# The readback (``_assert_knife_sides_coplanar``) holds each lateral face of
# one stub and its twin on the other to one plane: unit-normal components
# and plane offset (metres, the API's unit) within KNIFE_SIDE_PLANE_TOL.
KNIFE_SIDE_PLANE_TOL = 1e-6
KNIFE_LATERAL_FACES = 6  # per stub: two flanks, two sides, two lower faces

# --- derived ---------------------------------------------------------------
SUM_BASE = PLATE_L / 2.0  # summation plate base length             76.20
TIP_X = SX * SUM_H  # summation tip / anchor x (counter-spring arm) -76.20
# ARC_R (sm_summing_lever_spec, CYL_R + RIB_PAD = 15.24): the rib arc radius.
RIB_OFFSET = PLATE_L / 2.0 - RIB_T  # edge-rib start offset along Z 71.12
# Only the -Z edge rib is the magnifier bracket's receiver: its inward
# extension gives the #2-56 drill an ordinary depth band without moving the
# entry face. The independent +Z rib retains RIB_T.
RECEIVER_RIB_OFFSET = PLATE_L / 2.0 - RECEIVER_RIB_T  # 66.80
# No plain anchor bore: the counter anchor's seat is the native COUNTER_HOLE_SPEC
# tap through the boss, authored after the ribs (see _counter_anchor_tap).
# Every rib extrudes AFTER the spring holes (feature 1), so a rib reaching the
# hole column at HOLE_X re-fills any hole whose z lands in its z-span. The middle
# rib (+-RIB_T/2 = +-2.54) once refilled j=10 (the 4.21 mm^3
# channel-spring-installed-6 clash); on the cam plane (HOLE_Z_OFFSET -3.528) the
# j=0 tap (z -70.63) lies inside the -Z receiver rib's z-span (-76.20..-66.80),
# so that rib would refill it. Every rib's +X end therefore stops inboard of the
# hole column by the spring coil radius (~3.25) + margin so every hole stays
# open; the ribs still stiffen the inner lever, the outer plate arm is the (thin)
# spring-hole field.
# RIB_PLATE_REACH (sm_summing_lever_spec, 35.75 local +X) clears the hole column.
if RIB_PLATE_REACH > HOLE_X - blind_cut_dia_mm(HOLE_SPEC) / 2.0 - 2.0:
    raise AssertionError("a rib's +X vertex reaches the spring-hole column")
# The edge ribs keep SummingLever.cs's slant -- from the arc top towards the
# plate's free corner (PLATE_W, 0) -- and are CLIPPED by a vertical end face at
# RIB_PLATE_REACH rather than pulled in to a point there. The -Z rib is the
# magnifying bracket's receiver (magnifying_bracket_joint_layout): its outer
# #2-56 tap at x 29.7 keeps the full-height slant around its thread (wall
# 3.69 nominal), where a point at 35.75 would leave only the 5.08 plate (1.45).
# The end face stands EDGE_RIB_END_STEP (0.44) proud of each plate face, and
# the print locates its top corner from the plate's top face, a real surface
# (machinist review r10: from the pivot mid-plane the origin is in mid-air).
# The step is derived, not a new knob: the rib's corner stays where the
# slant puts it, so re-dimensioning it moves no geometry.
EDGE_RIB_END_HALF_H = ARC_R * (1.0 - RIB_PLATE_REACH / PLATE_W)  # 2.98
EDGE_RIB_END_STEP = EDGE_RIB_END_HALF_H - PLATE_T / 2.0  # 0.44
if not math.isclose(EDGE_RIB_END_STEP, 0.44, abs_tol=0.005):
    raise AssertionError(
        f"edge-rib end step {EDGE_RIB_END_STEP:.4f} is not the built 0.44"
    )
if not RIB_END_R < EDGE_RIB_END_STEP:
    raise AssertionError(
        f"rib-end round R{RIB_END_R} swallows the {EDGE_RIB_END_STEP:.2f} step"
    )

# Receiver-coordinate marks (``_receiver_coordinate_dimensions``): short
# construction lines whose ends carry the bracket-tap coordinates.  The edge
# mark lies on the free edge below its top corner (the plate is PLATE_T deep
# there); each tap mark lies on its row inside the tap drill.
RECEIVER_EDGE_MARK = 1.0
RECEIVER_TAP_MARK = 0.5
if not RECEIVER_EDGE_MARK < PLATE_T or not RECEIVER_TAP_MARK < TAP_DRILL_DIA / 2.0:
    raise AssertionError("receiver coordinate marks must stay on printed ink")


def edge_rib_half_height(x: float) -> float:
    """Half-height |y| of an edge rib's Front-plane profile at local +X ``x``.

    The profile the edge-rib sketch draws: the slant towards (PLATE_W, 0),
    defined from the arc top (x = 0) to the end face (x = RIB_PLATE_REACH).
    """
    if not 0.0 <= x <= RIB_PLATE_REACH:
        raise ValueError(f"x={x} is outside the edge rib (0..{RIB_PLATE_REACH})")
    return ARC_R * (1.0 - x / PLATE_W)


# Spring-hole Z stations (world Z); the Top-plane sketch maps world Z to -sketchY.
HOLE_Z = [CHANNEL_Z0 + CHANNEL_PITCH * j + HOLE_Z_OFFSET for j in range(HOLE_COUNT)]

# Assembly-facing exports (build_sm_summing_assembly imports these).
SPIN_REF_X = TIP_X  # local X of the summation-anchor tap = counter-spring ref


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

    The HOLE_COUNT spring holes are ONE seed cut at station j=0 + a native
    FeatureLinearPattern5 marching the remaining stations at CHANNEL_PITCH.
    (An early pattern attempt marched along an AUTO-selected plate edge whose
    natural sense silently reversed the field off the -Z plate edge -- only
    j=0 stayed cut -- and was replaced by cutting all 20 stations outright in
    one sketch. The pattern is back with the sense guarded, not
    inference-trusted: a deliberate direction-edge pick whose -Z natural sense
    is MEASURED, the seed at the +Z end of the span so a reversal marches off
    the plate, and an analytic volume gate that resolves a single missing
    hole.)

    Machine-y registration (the M6.4 plate-top-at-998 convention) is set at
    PLACEMENT, not baked here -- see PLATE_TOP_Y and the Phase 2/3 plan."""
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        LinearPatternParameters,
    )

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
        adapter,
        outline,
        rect,
        label="plate",
        dims=plate,
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
    # The mid-plane extrude's one depth is the whole thickness, printed in
    # the drawing's section C-C at the title block's .XX band.
    [plate_thickness] = name_dimensions(
        adapter, "CoefficientsPlate", ["PlateThickness"]
    )
    drive_jobs.append((plate_thickness, '"PlateT"'))
    # The plate is a plain rectangular prism, so an exact analytic volume gate
    # anchors the hole-field tripwires below (the WHOLE part has no analytic
    # gate -- organic arcs -- but this first feature does).
    v_plate = PLATE_W * PLATE_L * PLATE_T
    await volume_check(adapter, "coefficients plate", v_plate, 1e-3 * v_plate)

    # Spring-anchor pad (sm_summing_lever_spec.SPRING_SEAT_T): a Front-plane
    # rectangle from the plate TOP at the free edge down to the pad underside,
    # extruded the plate's full length, so its two dimensions are the tap's
    # own length and the pad's width, both visible edge-on in the end views.
    # It overlaps the plate above its underside; only the 1.92 below adds.
    # Cut BEFORE the spring holes so the through taps run the whole 7.00.
    pad = SketchDims()
    check("create_sketch spring pad", await adapter.create_sketch("Front"))
    pad_top = PLATE_T / 2.0
    pad_bottom = pad_top - SPRING_SEAT_T
    pad_inner = SX * -(PLATE_W - SPRING_PAD_W)
    pad_outer = SX * -PLATE_W
    pad_points = [
        (pad_outer, pad_top),
        (pad_inner, pad_top),
        (pad_inner, pad_bottom),
        (pad_outer, pad_bottom),
    ]
    pad_outline = await add_line_chain(adapter, pad_points)
    await define_rectilinear_chain(
        adapter,
        pad_outline,
        pad_points,
        label="spring pad",
        dims=pad,
        names=[
            "SpringPadWidth",
            "SpringSeatThickness",
            "SpringPadEdgeX",
            "SpringPadTopY",
        ],
        drives=['"SpringPadW"', '"SpringSeatT"', '"PlateW"', '"PlateT" / 2'],
    )
    await ensure_fully_defined(adapter, "spring pad sketch")
    check("exit_sketch spring pad", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringPadProfile")
    drive_jobs += pad.apply(adapter, "SpringPadProfile")
    check(
        "extrude spring pad",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_L, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SpringPad")
    v_plate += SPRING_PAD_W * (SPRING_SEAT_T - PLATE_T) * PLATE_L
    await volume_check(adapter, "spring pad", v_plate, 1e-3 * v_plate)

    # Spring-hole field: ONE seed hole at station j=HOLE_COUNT-1 + a native
    # linear pattern marching the remaining stations down world -Z at
    # CHANNEL_PITCH. History: an earlier FeatureLinearPattern5 marched along an
    # AUTO-selected edge whose natural sense reversed the field off the -Z
    # plate edge (all but j=0 solid), and was replaced by cutting all 20
    # stations outright in one sketch. The pattern returns with the sense RISK
    # managed, not inference-trusted: the direction is the plate's +X top edge
    # (along Z) with an explicit -Z direction_vector, so neither the active
    # view nor the edge's own sense decides it; the seed sits at the +Z END of
    # the station span so the -Z march covers the field and a reversal runs
    # off the plate, and the analytic volume gate below resolves a single
    # missing hole -- a flip cannot pass silently.
    # Native number-drill seed for the patterned spring-hook seats.
    seed_dia = blind_cut_dia_mm(HOLE_SPEC)
    seed_result = wizard_holes(
        adapter,
        HOLE_SPEC,
        [[HOLE_X, PLATE_T / 2.0, HOLE_Z[-1]]],
        (0.0, 1.0, 0.0),
        f"spring hole seed (station j={HOLE_COUNT - 1}, {HOLE_SPEC.size})",
        name="SpringHoleSeed",
        expect_dia_mm=seed_dia,
        placement_dims=[
            (
                ("HoleSeedX", '"HoleX"'),
                (
                    "HoleSeedStation",
                    f'"ChannelZ0" + {HOLE_COUNT - 1} * "ChannelPitch" + "HoleZOffset"',
                ),
            )
        ],
    )
    drive_jobs += seed_result.placement_drive_jobs
    seed_cut = seed_result.name
    v_hole = math.pi * (seed_dia / 2.0) ** 2 * SPRING_SEAT_T
    await volume_check(adapter, "spring hole seed", v_plate - v_hole, 0.02 * v_hole)
    check(
        "linear pattern spring holes",
        await adapter.linear_pattern_feature(
            LinearPatternParameters(
                direction_point=[PLATE_W, PLATE_T / 2.0, 0.0],
                direction_vector=[0.0, 0.0, -1.0],
                features=[seed_cut],
                count=HOLE_COUNT,
                spacing=CHANNEL_PITCH,
            )
        ),
    )
    name_last_feature(adapter, "SpringHolePattern")
    # Drive the pattern's spacing dim from ChannelPitch so the pitch knob is
    # live, not inert (the measuring-stick TickPattern Codex P2). The spacing
    # is D3 (D1 is the pattern's direction-reference length, NOT the pitch);
    # D3 == as-built CHANNEL_PITCH, so it stays neutral.
    drive_jobs.append(("D3@SpringHolePattern", '"ChannelPitch"'))
    await volume_check(
        adapter,
        "spring-hole field",
        v_plate - HOLE_COUNT * v_hole,
        0.01 * HOLE_COUNT * v_hole,
    )


async def _pivot_cylinder(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 2: Front-plane solid circle at origin, symmetric extrude along the
    long edge -- the pivot/rock axis (local Z). NO bore."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    # Origin circle: only the diameter is a dim (the centre is a coincident
    # relation), so define_circle records just that one slot.
    cyl = SketchDims()
    check("create_sketch cylinder", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        CYL_R,
        "pivot cylinder",
        dims=cyl,
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


async def _hex_knife(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Both hexagonal knife-edge trunnion stubs as ONE prism: a Front-plane
    vertex-up hexagon (HEX_W x HEX_H bounding box) centred on the pivot axis,
    a vertex at the top (the knife edge runs along Z at that top vertex
    line), extruded mid-plane to |z| HEX_Z_OUTER.  Inside the body it merges
    into the solid pivot cylinder; past each body end it is a stub, the
    overhang the knife edge rests on a bearing support with.

    One sketch and one extrude, so each side face, flank and lower face of
    the +Z stub lies in the same plane as its -Z twin by construction (code
    review C09): the symmetry Detail D prints for each stub then holds the two
    ridges to each other (``sm_summing_lever_spec.KNIFE_STUB_RIDGE_OFFSET_MAX``).
    ``_assert_knife_sides_coplanar`` reads that back."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    hexd = SketchDims()
    check("create_sketch hex knife", await adapter.create_sketch("Front"))
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
    stem = "HexKnife"
    await define_polygon_chain(
        adapter,
        lines,
        verts,
        label="hex knife",
        dims=hexd,
        names=[
            f"{stem}TopY",
            f"{stem}S0dx",
            f"{stem}S0dy",
            f"{stem}S1dy",
            f"{stem}S2dx",
            f"{stem}S2dy",
            f"{stem}S3dx",
            f"{stem}S3dy",
            f"{stem}S4dy",
        ],
        drives=[_hh2, _hw, _hh4, _hh2, _hw, _hh4, _hw, _hh4, _hh2],
    )
    await ensure_fully_defined(adapter, "hex knife sketch")
    check("exit_sketch hex knife", await adapter.exit_sketch())
    name_last_feature(adapter, f"{stem}Profile")
    drive_jobs += hexd.apply(adapter, f"{stem}Profile")
    check(
        "extrude hex knife",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * HEX_Z_OUTER, both_directions=True)
        ),
    )
    name_last_feature(adapter, stem)
    # The total length is the body plus both stubs; the print sizes a stub's
    # own length from the hidden KnifeStubReference (``_knife_stub_reference``).
    [length] = name_dimensions(adapter, stem, [f"{stem}Length"])
    drive_jobs.append((length, '"PlateL" + 2 * "HexDepth"'))


def knife_side_plane_mismatch(
    faces: list[tuple[tuple[float, ...], float, float]],
) -> str | None:
    """Why the knife prism's lateral faces are NOT one plane per side, or None.

    ``faces`` holds each planar lateral face as (unit normal, plane offset
    in metres along it, face mid z in mm).  Each stub (the sign of z) must
    carry KNIFE_LATERAL_FACES distinct planes, every plane of one stub must
    be a plane of the other within KNIFE_SIDE_PLANE_TOL, and the side pair
    must stand HEX_W/2 either side of the pivot axis."""
    tol = KNIFE_SIDE_PLANE_TOL

    def same(
        a: tuple[tuple[float, ...], float], b: tuple[tuple[float, ...], float]
    ) -> bool:
        return (
            all(abs(p - q) <= tol for p, q in zip(a[0], b[0], strict=True))
            and abs(a[1] - b[1]) <= tol
        )

    stubs: dict[str, list[tuple[tuple[float, ...], float]]] = {"+Z": [], "-Z": []}
    for normal, offset, z_mid in faces:
        planes = stubs["+Z" if z_mid > 0.0 else "-Z"]
        if not any(same((normal, offset), plane) for plane in planes):
            planes.append((tuple(normal), offset))
    for stub, planes in stubs.items():
        if len(planes) != KNIFE_LATERAL_FACES:
            return (
                f"the {stub} stub has {len(planes)} lateral planes, not "
                f"{KNIFE_LATERAL_FACES}: {planes}"
            )
    for plane in stubs["+Z"]:
        if not any(same(plane, twin) for twin in stubs["-Z"]):
            return f"+Z stub plane {plane} is no plane of the -Z stub: {stubs['-Z']}"
    for side in (1.0, -1.0):
        wanted = ((side, 0.0, 0.0), HEX_W / 2000.0)
        if not any(same(wanted, plane) for plane in stubs["+Z"]):
            return f"no side face at x {side * HEX_W / 2.0:+.3f}: {stubs['+Z']}"
    return None


def _assert_knife_sides_coplanar(adapter) -> None:
    """Read HexKnife's planar lateral faces back from the finished body and
    prove both stubs share each one's plane (``knife_side_plane_mismatch``).
    The outboard end faces (normal along Z) and the ridge rounds (cylindrical,
    KnifeRidgeFillet's) are not lateral planes."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    raw = _early_bound(model, "IPartDoc").FeatureByName("HexKnife")
    if raw is None:
        raise RuntimeError("knife sides: the HexKnife feature is missing")
    feature = _early_bound(raw, "IFeature")
    faces: list[tuple[tuple[float, ...], float, float]] = []
    for raw_face in feature.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface is None or not surface.IsPlane():
            continue
        normal = tuple(float(value) for value in face.Normal)
        if len(normal) != 3 or not all(math.isfinite(value) for value in normal):
            raise RuntimeError(f"knife sides: invalid face normal {normal}")
        if abs(normal[2]) > KNIFE_SIDE_PLANE_TOL:
            continue  # an outboard end face
        root = tuple(float(value) for value in surface.PlaneParams)[3:6]
        offset = sum(n * r for n, r in zip(normal, root, strict=True))
        box = tuple(float(value) for value in face.GetBox())
        z_mid_mm = (box[2] + box[5]) * 500.0
        faces.append((normal, offset, z_mid_mm))
    mismatch = knife_side_plane_mismatch(faces)
    if mismatch is not None:
        raise RuntimeError(f"knife stubs' sides are not one plane each: {mismatch}")
    _telemetry.success(
        f"knife sides: {len(faces)} lateral faces, {KNIFE_LATERAL_FACES} planes "
        f"shared by both stubs within {KNIFE_SIDE_PLANE_TOL:g}"
    )


async def _knife_ridge_fillet(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Round both trunnions' top-vertex ridges at KNIFE_RIDGE_R (rule 16: a
    knife edge is truncated by a small stated radius, here the print's R MAX
    limit).  Picked mid-stub on each ridge line, the only edge through that
    point; HexHeight stays the theoretical sharp, the knife axis (Axis3) too."""
    picks = [
        [0.0, HEX_H / 2.0, side * (HEX_Z_INNER + HEX_DEPTH / 2.0)]
        for side in (1.0, -1.0)
    ]
    v_before = await _measured_volume(adapter, "before the knife-ridge round")
    check(
        "fillet knife-edge ridges",
        await adapter.add_fillet(KNIFE_RIDGE_R, picks, propagate=False),
    )
    name_last_feature(adapter, "KnifeRidgeFillet")
    [radius] = name_dimensions(adapter, "KnifeRidgeFillet", ["KnifeRidgeRadius"])
    drive_jobs.append((radius, '"KnifeRidgeR"'))
    # Each ridge loses the spandrel between its two faces and the round:
    # r^2 (cot(a/2) - (pi - a)/2) for the included angle a, over the stub.
    half = math.radians(RIDGE_ANGLE_DEG) / 2.0
    spandrel = KNIFE_RIDGE_R**2 * (1.0 / math.tan(half) - (math.pi / 2.0 - half))
    v_round = 2.0 * spandrel * HEX_DEPTH
    # A ~0.01 mm^3 cut on the whole body is below the mass-property noise, so
    # this only proves the round took nothing else; the drawing's scan of the
    # round's tangent lines proves it is there.
    await volume_check(
        adapter, "knife-edge ridge rounds", v_before - v_round, 1e-4 * v_before
    )


async def _measured_volume(adapter, label: str) -> float:
    await force_rebuild(adapter)
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"mass props {label} failed: {mass.error}")
    return float(mass.data.volume)


def _radius_max_limit(
    adapter,
    feature: str,
    name: str,
    radius: float,
    band: tuple[float, float],
    tol_type: int,
) -> None:
    """``name`` as the single limit "R<radius> MAX" carrying ``band``'s
    deviations (build_ch_pivot_bracket._corner_radius_max_limit's recipe)."""
    lower, upper = deviations(band)
    _, dimension = _named_dimension(adapter, feature, name)
    label = f"{name}@{feature}"
    value = float(dimension.SystemValue)
    if not math.isclose(value, radius / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max {radius}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != tol_type
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    set_dimension_display_precision(adapter, feature, name, 1)
    _telemetry.success(f"{label}: single limit {radius:g} MAX")


# A concave fillet of radius r leaves (1 - pi/4) r^2 of material in its corner,
# whose centroid sits CORNER_FILL_CENTROID * r from the corner on each leg.
CORNER_FILL_CENTROID = (10.0 - 3.0 * math.pi) / (3.0 * (4.0 - math.pi))


def _stub_root_picks(z_mm: float) -> list[list[float]]:
    """A point on each of one stub's seven root edges in the body end face at
    ``z_mm``: the -X side face's first (the imported radius rides a fillet's
    first edge, build_pd_guide_lock's ``StopperChamfer`` finding), then the
    +X side, both lower flanks, both upper flanks between their shoulder and
    the ridge round's tangent line, and the round's own root arc at its
    apex.  Each is the only edge within the adapter's 0.5 mm pick tolerance
    but the apex, whose nearest neighbours, the flanks ending at the round's
    tangent points, lie ~0.06 mm off."""
    tangent_x, tangent_y = KNIFE_RIDGE_TANGENT_XY
    half = math.radians(RIDGE_ANGLE_DEG) / 2.0
    apex_y = HEX_H / 2.0 - KNIFE_RIDGE_R * (1.0 / math.sin(half) - 1.0)
    picks = [[side * HEX_W / 2.0, 0.0, z_mm] for side in (-1.0, 1.0)]
    picks += [[side * HEX_W / 4.0, -3.0 * HEX_H / 8.0, z_mm] for side in (-1.0, 1.0)]
    picks += [
        [
            side * (HEX_W / 2.0 + tangent_x) / 2.0,
            (HEX_H / 4.0 + tangent_y) / 2.0,
            z_mm,
        ]
        for side in (-1.0, 1.0)
    ]
    picks.append([0.0, apex_y, z_mm])
    return picks


def _stub_root_fill() -> float:
    """Material one stub's R STUB_ROOT_R root fillet adds: the corner fill
    swept along the ridge-rounded hexagon's perimeter plus, by Pappus, its
    turn of 2 pi about the convex corners."""
    half = math.radians(RIDGE_ANGLE_DEG) / 2.0
    flank = math.hypot(HEX_W / 2.0, HEX_H / 4.0)
    setback = KNIFE_RIDGE_R / math.tan(half)
    perimeter = (
        HEX_H + 4.0 * flank - 2.0 * setback + KNIFE_RIDGE_R * (math.pi - 2.0 * half)
    )
    area = (1.0 - math.pi / 4.0) * STUB_ROOT_R**2
    return area * (perimeter + 2.0 * math.pi * CORNER_FILL_CENTROID * STUB_ROOT_R)


@_telemetry.traced("lever.inside_corner_fillet", label_param="feature")
async def _inside_corner_fillet(
    adapter,
    drive_jobs: list[tuple[str, str]],
    *,
    feature: str,
    dimension: str,
    radius: float,
    global_name: str,
    picks: list[list[float]],
) -> None:
    """One ``FeatureFillet3`` over ``picks``' edges, named and driven by
    ``global_name``; propagation stays off so only the enumerated root edges
    participate.

    Each pick must lie ON an edge (1 um, not the adapter's 0.5 mm reach, which
    would let the apex pick fall to a flank 0.056 mm off), and the stored
    definition must hold one edge per pick at the radius: a pick that fell to
    an edge another already took leaves the count short."""
    from solidworks_mcp.adapters.solidworks.features import _select_edges_geometric

    if _select_edges_geometric(adapter, picks, tol_mm=0.001) is not True:
        raise RuntimeError(f"{feature}: a pick lies on no edge within 1 um")
    adapter.currentModel.ClearSelection2(True)
    check(
        f"fillet {feature}",
        await adapter.add_fillet(radius, picks, propagate=False),
    )
    name_last_feature(adapter, feature)
    native = _feature_by_name(adapter, feature)
    if native is None:
        raise RuntimeError(f"{feature}: native fillet feature is missing")
    definition = _early_bound(native, "IFeature").GetDefinition()
    if definition is None:
        raise RuntimeError(f"{feature}: fillet definition is missing")
    definition = _early_bound(definition, "ISimpleFilletFeatureData2")
    edges = int(definition.GetEdgeCount())
    stored = float(definition.DefaultRadius) * 1000.0
    _telemetry.annotate(fillet_edges=edges, fillet_radius_mm=stored)
    if edges != len(picks):
        raise RuntimeError(f"{feature}: {edges} edges stored, {len(picks)} picked")
    if not math.isclose(stored, radius, abs_tol=1e-9):
        raise RuntimeError(f"{feature}: radius {stored:.7f} stored, {radius} built")
    _telemetry.success(f"{feature}: {edges} edges R{radius:g}, picks on edge <= 1 um")
    [radius_name] = name_dimensions(adapter, feature, [dimension])
    drive_jobs.append((radius_name, f'"{global_name}"'))


async def _inside_corner_fillets(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Round the casting's inside corners at their printed limits (#1625): the
    root of each trunnion stub on its body end face (STUB_ROOT_R) and the foot
    of each end rib's 0.44 step onto the plate's top face (RIB_END_R).

    Each corner is one feature per end.  The -Z end's StubRootFillet and
    RibEndFillet carry the marked radii the print's sheet 2 shows on that
    end (VIEW K, DETAIL J); the +Z end's Other* twins share their globals and
    carry no ink.  The middle rib ends in a point inside the plate, with no
    step to round."""
    v_before = await _measured_volume(adapter, "before the inside-corner fillets")
    for feature, z_mm in (
        ("StubRootFillet", -HEX_Z_INNER),
        ("OtherStubRootFillet", HEX_Z_INNER),
    ):
        await _inside_corner_fillet(
            adapter,
            drive_jobs,
            feature=feature,
            dimension=feature.replace("Fillet", "Radius"),
            radius=STUB_ROOT_R,
            global_name="StubRootR",
            picks=_stub_root_picks(z_mm),
        )
    for feature, z_mm in (
        ("RibEndFillet", -(PLATE_L / 2.0 - RECEIVER_RIB_T / 2.0)),
        ("OtherRibEndFillet", PLATE_L / 2.0 - RIB_T / 2.0),
    ):
        await _inside_corner_fillet(
            adapter,
            drive_jobs,
            feature=feature,
            dimension=feature.replace("Fillet", "Radius"),
            radius=RIB_END_R,
            global_name="RibEndR",
            picks=[[RIB_PLATE_REACH, PLATE_T / 2.0, z_mm]],
        )
    v_fill = 2.0 * _stub_root_fill() + (1.0 - math.pi / 4.0) * RIB_END_R**2 * (
        RECEIVER_RIB_T + RIB_T
    )
    # ~3 mm^3 on the whole body is below the mass-property noise, so this
    # only proves the fillets took nothing else.
    await volume_check(
        adapter, "inside-corner fillets", v_before + v_fill, 1e-4 * v_before
    )


def edge_rib_added_area_mm2() -> float:
    """Net rib section outside the already-built cylinder, plate and pad.

    The circle lies wholly inside the clipped rib profile. The positive-X
    plate overlaps its central stripe; the pad fills the lower rib tip.
    Neither the spring-hole column nor the knife prism removes this area.
    This is evaluated before the summation web is added.
    """
    reach, radius, half_plate = RIB_PLATE_REACH, CYL_R, PLATE_T / 2.0
    gross = math.pi * ARC_R**2 / 2.0 + 2.0 * ARC_R * reach - ARC_R * reach**2 / PLATE_W
    circle_plate_overlap = (
        half_plate * math.sqrt(radius**2 - half_plate**2)
        + radius**2 * math.asin(half_plate / radius)
    )
    pad_start = PLATE_W - SPRING_PAD_W
    pad_overlap = (
        (ARC_R - half_plate) * (reach - pad_start)
        - ARC_R * (reach**2 - pad_start**2) / (2.0 * PLATE_W)
    )
    return gross - math.pi * radius**2 - PLATE_T * reach + circle_plate_overlap - pad_overlap


def _assert_edge_rib_end_planes(adapter) -> None:
    """Read the inner caps and depths; outer caps may merge with earlier faces."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    expected = {
        "EdgeRibBack": (-RECEIVER_RIB_OFFSET, -PLATE_L / 2.0, "RibDepth", RECEIVER_RIB_T),
        "EdgeRibFront": (RIB_OFFSET, PLATE_L / 2.0, "EdgeRibThickness", RIB_T),
    }
    tolerance_mm = 1e-5
    for name, (inner, outer, depth_name, depth_mm) in expected.items():
        raw = model.FeatureByName(name)
        if raw is None:
            raise RuntimeError(f"{name}: missing native rib feature")
        feature = _early_bound(raw, "IFeature")
        dimension = feature.Parameter(depth_name)
        if dimension is None or not math.isclose(
            float(_early_bound(dimension, "IDimension").SystemValue) * 1000.0,
            depth_mm, rel_tol=0.0, abs_tol=tolerance_mm,
        ):
            raise RuntimeError(f"{name}: native {depth_name} is not {depth_mm} mm")
        planes: list[float] = []
        for raw_face in feature.GetFaces() or ():
            face = _early_bound(raw_face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if surface is None or not surface.IsPlane():
                continue
            values = tuple(float(value) for value in surface.PlaneParams)
            if len(values) != 6 or not all(math.isfinite(value) for value in values):
                raise RuntimeError(f"{name}: invalid native plane parameters {values}")
            if abs(values[0]) > 1e-7 or abs(values[1]) > 1e-7 or abs(abs(values[2]) - 1.0) > 1e-7:
                continue
            z_mm = values[5] * 1000.0
            if not any(abs(z_mm - previous) <= tolerance_mm for previous in planes):
                planes.append(z_mm)
        # Coplanar outside caps can be owned by the earlier plate/cylinder.
        # The required inner cap plus native extrusion depth independently
        # locates that outside cap; any cap this feature does own must agree.
        if not any(abs(inner - z) <= tolerance_mm for z in planes) or any(
            min(abs(z - inner), abs(z - outer)) > tolerance_mm for z in planes
        ):
            raise RuntimeError(
                f"{name}: native end planes {planes} mm do not establish {(inner, outer)} mm"
            )
        _telemetry.success(
            f"{name}: native depth {depth_mm} mm; end planes {sorted(planes)} mm; "
            f"outer boundary {outer} mm"
        )


def _native_values(values, count: int, label: str) -> tuple[float, ...]:
    result = tuple(float(value) for value in values)
    if len(result) != count or not all(math.isfinite(value) for value in result):
        raise RuntimeError(f"{label}: invalid native values {result}")
    return result


def _assert_receiver_trimmed_wall(adapter) -> None:
    """Certify nominal, finite BREP walls, not the print's worst-case bands.

    ClosestDistance receives IFace2 objects, never their infinite ISurfaces.
    Only the intentional entry plane and this receiver's bore faces are
    omitted. Every other body face is tested (including other internal faces,
    conservatively). The rear cap and plate underside must independently
    return the actual notch corner, not an infinite-plane projection.
    """
    from magnifying_bracket_joint_layout import cone_notch_closest_advance

    tol = 1e-5  # mm; native geometry, not a manufacturing allowance
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError("receiver certificate: expected exactly one solid body")
    feature = part.FeatureByName("BracketMountingTaps")
    if feature is None:
        raise RuntimeError("receiver certificate: missing BracketMountingTaps")
    feature = _early_bound(feature, "IFeature")
    radius = TAP_DRILL_DIA / 2.0
    entry = LEVER_HOLE_POINTS[0][2]
    shoulder = entry + DRILL_DEPTH
    rear = entry + RECEIVER_RIB_T
    half_plate = PLATE_T / 2.0
    holes = {(x, y): {} for x, y, _z in LEVER_HOLE_POINTS}
    for raw in feature.GetFaces() or ():
        face = _early_bound(raw, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        cylinder, cone = bool(surface.IsCylinder()), bool(surface.IsCone())
        if not cylinder and not cone:
            raise RuntimeError("receiver certificate: unexpected hole feature face")
        kind = "cylinder" if cylinder else "cone"
        params = _native_values(
            surface.CylinderParams if cylinder else surface.ConeParams2,
            7 if cylinder else 11, f"receiver {kind}",
        )
        if abs(params[3]) > 1e-8 or abs(params[4]) > 1e-8 or abs(abs(params[5]) - 1) > 1e-8:
            raise RuntimeError(f"receiver {kind}: wrong native axis {params[3:6]}")
        station = [
            point for point in holes
            if math.hypot(params[0] * 1000 - point[0], params[1] * 1000 - point[1]) <= tol
        ]
        if len(station) != 1 or kind in holes[station[0]]:
            raise RuntimeError(f"receiver {kind}: wrong or duplicate native station")
        if cylinder and abs(params[6] * 1000 - radius) > tol:
            raise RuntimeError("receiver cylinder: wrong native minor radius")
        if cone and abs(abs(params[7]) - math.atan(radius / DRILL_POINT_DEPTH)) > 1e-8:
            raise RuntimeError("receiver cone: wrong native drill-point angle")
        # Circular trim edges, unlike GetBox, give exact shoulder/end stations.
        rings = []
        vertices = []
        for raw_edge in face.GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle():
                ring = _native_values(curve.CircleParams, 7, "receiver circular trim")
                if (
                    abs(ring[0] * 1000 - station[0][0]) > tol
                    or abs(ring[1] * 1000 - station[0][1]) > tol
                    or abs(ring[3]) > 1e-8 or abs(ring[4]) > 1e-8
                    or abs(abs(ring[5]) - 1) > 1e-8
                    or abs(ring[6] * 1000 - radius) > tol
                ):
                    raise RuntimeError("receiver: wrong native circular trim")
                rings.append(ring[2] * 1000)
                _telemetry.info(
                    f"receiver native x={station[0][0]:g} {kind}: "
                    f"trim centre={tuple(value * 1000 for value in ring[:3])}; "
                    f"axis={params[3:6]}; trim radius={ring[6] * 1000:.9f} mm"
                )
            for vertex in (edge.GetStartVertex(), edge.GetEndVertex()):
                if vertex is not None:
                    vertices.append(tuple(
                        value * 1000 for value in _native_values(
                            _early_bound(vertex, "IVertex").GetPoint(), 3, "receiver vertex"
                        )
                    ))
        expected = (entry, shoulder) if cylinder else (shoulder,)
        if not rings or any(min(abs(z - wanted) for wanted in expected) > tol for z in rings) or any(
            not any(abs(z - wanted) <= tol for z in rings) for wanted in expected
        ):
            raise RuntimeError(f"receiver {kind}: wrong native shoulder/depth {rings}")
        if cone and not any(
            math.dist(point, (*station[0], shoulder + DRILL_POINT_DEPTH)) <= tol
            for point in vertices
        ):
            raise RuntimeError("receiver cone: native blind tip missing or wrong depth")
        holes[station[0]][kind] = face
    if any(set(faces) != {"cylinder", "cone"} for faces in holes.values()):
        raise RuntimeError("receiver certificate: both holes need cylinder and cone")

    external = []
    entry_count = 0
    for raw in _early_bound(bodies[0], "IBody2").GetFaces() or ():
        face = _early_bound(raw, "IFace2")
        owner = _early_bound(face.GetFeature(), "IFeature")
        if owner is None:
            raise RuntimeError("receiver certificate: native face has no owner")
        if str(owner.Name) == "BracketMountingTaps":
            continue
        surface = _early_bound(face.GetSurface(), "ISurface")
        label = "external"
        if surface.IsPlane():
            plane = _native_values(surface.PlaneParams, 6, "receiver external plane")
            nx, ny, nz = plane[:3]
            if abs(nx) < 1e-8 and abs(ny) < 1e-8 and abs(abs(nz) - 1) < 1e-8:
                z = plane[5] * 1000
                if abs(z - entry) <= tol:
                    entry_count += 1
                    continue
                if abs(z - rear) <= tol:
                    label = "rear cap"
            if abs(nx) < 1e-8 and abs(nz) < 1e-8 and abs(abs(ny) - 1) < 1e-8:
                if abs(plane[4] * 1000 + half_plate) <= tol:
                    label = "plate underside"
        external.append((face, label))
    if entry_count == 0 or not external:
        raise RuntimeError("receiver certificate: missing native entry/external faces")
    for (x, y), faces in holes.items():
        for kind, hole in faces.items():
            advance = 0.0 if kind == "cylinder" else cone_notch_closest_advance(
                RECEIVER_RIB_T - DRILL_DEPTH, half_plate, radius,
            )
            radial = radius * (1.0 - advance / DRILL_POINT_DEPTH)
            expected_gap = math.hypot(rear - shoulder - advance, half_plate - radial)
            witnessed = set()
            nearest = math.inf
            for face, label in external:
                distance, raw_a, raw_b = model.ClosestDistance(hole, face)
                distance = float(distance) * 1000
                a = tuple(value * 1000 for value in _native_values(raw_a, 3, "hole witness"))
                b = tuple(value * 1000 for value in _native_values(raw_b, 3, "wall witness"))
                if not math.isfinite(distance) or distance < 0 or abs(math.dist(a, b) - distance) > tol:
                    raise RuntimeError("receiver certificate: native ClosestDistance failed")
                if distance < expected_gap - tol:
                    raise RuntimeError(
                        f"receiver {x:g} {kind}: {label} gap {distance:g} < nominal {expected_gap:g} mm; {a}, {b}"
                    )
                nearest = min(nearest, distance)
                if label in ("rear cap", "plate underside") and abs(distance - expected_gap) <= tol:
                    # The cap may choose either equally close notch corner;
                    # the underside must choose the lower corner.
                    signs = (-1, 1) if label == "rear cap" else (-1,)
                    if any(
                        math.dist(b, (x, sign * half_plate, rear)) <= tol
                        and math.dist(a, (x, sign * radial, shoulder + advance)) <= tol
                        for sign in signs
                    ):
                        witnessed.add(label)
                        _telemetry.info(
                            f"receiver native x={x:g} {kind} -> {label}: "
                            f"{distance:.9f} mm; hole={a}; wall={b}"
                        )
                    elif label == "plate underside":
                        raise RuntimeError("receiver certificate: wrong trimmed underside witness")
            if witnessed != {"rear cap", "plate underside"} or abs(nearest - expected_gap) > tol:
                raise RuntimeError(
                    f"receiver {x:g} {kind}: missing trimmed corner proof {witnessed}; "
                    f"minimum {nearest:g}, nominal {expected_gap:g} mm"
                )
    _telemetry.success("receiver: both native cylinders/cones retain nominal finite-surface walls")


def _assert_middle_rib_profile(adapter) -> None:
    """Read original tangent endpoints and the actual imported dimension refs."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    raw = part.FeatureByName("MiddleRibProfile")
    if raw is None:
        raise RuntimeError("MiddleRibProfile: missing native sketch")
    feature = _early_bound(raw, "IFeature")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    lines = []
    segments = tuple(sketch.GetSketchSegments() or ())
    for raw_segment in segments:
        segment = _early_bound(raw_segment, "ISketchSegment")
        if int(segment.GetType()) != 0:  # swSketchLINE
            continue
        line = _early_bound(raw_segment, "ISketchLine")
        points = []
        for raw_point in (line.GetStartPoint2(), line.GetEndPoint2()):
            point = _early_bound(raw_point, "ISketchPoint")
            points.append(tuple(value * 1000 for value in (point.X, point.Y, point.Z)))
        lines.append(points)
    if len(segments) != 6 or len(lines) != 4:
        raise RuntimeError("MiddleRibProfile: wrong native profile stack")
    for vertex_x in (RIB_PLATE_REACH, TIP_X):
        tx = ARC_R**2 / vertex_x
        ty = ARC_R * math.sqrt(1 - ARC_R**2 / vertex_x**2)
        for sign in (-1, 1):
            expected = ((vertex_x, 0.0, 0.0), (tx, sign * ty, 0.0))
            if sum(
                any(math.dist(a, expected[0]) < 1e-5 and math.dist(b, expected[1]) < 1e-5
                    for a, b in (points, points[::-1]))
                for points in lines
            ) != 1:
                raise RuntimeError("MiddleRibProfile: original native tangent endpoints changed")
    dimension = feature.Parameter("MidRibLeftX")
    if dimension is None:
        raise RuntimeError("MiddleRibProfile: missing MidRibLeftX")
    dimension = _early_bound(dimension, "IDimension")
    if abs(float(dimension.SystemValue) * 1000 - RIB_PLATE_REACH) > 1e-5:
        raise RuntimeError("MiddleRibProfile: wrong theoretical vertex dimension")
    refs = tuple(dimension.ReferencePoints or ())
    if len(refs) != 3:
        raise RuntimeError("MiddleRibProfile: missing native dimension reference points")
    points = [
        tuple(value * 1000 for value in _native_values(
            _early_bound(point, "IMathPoint").ArrayData, 3, "middle rib dimension reference"
        )) for point in refs[:2]
    ]
    if not (
        any(math.dist(point, (RIB_PLATE_REACH, 0, 0)) < 1e-5 for point in points)
        and any(math.dist(point, (0, 0, 0)) < 1e-5 for point in points)
    ):
        raise RuntimeError("MiddleRibProfile: dimension does not reference origin and theoretical vertex")
    tx = ARC_R**2 / RIB_PLATE_REACH
    ty = ARC_R * math.sqrt(1 - ARC_R**2 / RIB_PLATE_REACH**2)
    join = RIB_PLATE_REACH + (tx - RIB_PLATE_REACH) * (PLATE_T / 2) / ty
    _telemetry.success(
        f"MiddleRibProfile: original native tangents; theoretical vertex "
        f"({RIB_PLATE_REACH:g}, 0); visible plate join x={join:.9f} mm"
    )


async def _edge_rib(
    adapter, flip: bool, name: str, stem: str, drive_jobs: list[tuple[str, str]]
) -> None:
    """Feature 4: Front-plane rib -- two slant lines, a vertical end face and a
    semicircle (radius ARC_R, centred at the origin) wrapping the cylinder,
    blind-extruded at the +-RIB_OFFSET start offset along Z (the -Z receiver
    rib RECEIVER_RIB_T deep from +-RECEIVER_RIB_OFFSET).

    Vertices (A, C on the arc; B, D the end face at RIB_PLATE_REACH, short of
    the spring-hole column the -Z rib's span crosses, +-EDGE_RIB_END_HALF_H on
    the slant towards (PLATE_W, 0); P on the end face at the plate's top face):
    the arc centre is the origin (the two y-symmetric ends + the cylinder-side
    interior point force it there), so it defines off a coincident-to-origin
    centre + a radial dim, with A/C pinned on the y-axis.  D takes two distance
    dims from the origin; P, on the vertical P-D, its height from the origin;
    B its reach from the origin and its EDGE_RIB_END_STEP over P, which also
    makes B-P vertical (a vertical relation on top would over-define).  The
    end face is two collinear segments so the printed step runs from P, the
    corner where the face meets the plate top -- below P the face lies inside
    the plate and the spring pad, so the solid is the one-segment face's."""
    v_before = await _measured_volume(adapter, f"before {stem}")
    rib = SketchDims()
    check(f"create_sketch {name}", await adapter.create_sketch("Front"))
    end_x = SX * -RIB_PLATE_REACH
    a, c = (0.0, ARC_R), (0.0, -ARC_R)
    b, d = (end_x, EDGE_RIB_END_HALF_H), (end_x, -EDGE_RIB_END_HALF_H)
    p = (end_x, PLATE_T / 2.0)
    interior = (SX * ARC_R, 0.0)  # cylinder-side point the arc passes through
    set_sketch_direct_db(adapter, True)
    line_ab = check(f"{name} line A-B", await adapter.add_line(*a, *b))
    line_bp = check(f"{name} end step B-P", await adapter.add_line(*b, *p))
    line_pd = check(f"{name} end face P-D", await adapter.add_line(*p, *d))
    line_dc = check(f"{name} line D-C", await adapter.add_line(*d, *c))
    arc, _, _ = await _three_point_arc(adapter, c, a, interior, f"{name} arc")
    set_sketch_direct_db(adapter, False)
    check(
        f"{name} arc centre -> origin",
        await adapter.add_sketch_constraint(f"{arc}.center", "origin", "coincident"),
    )
    # Six display dims, recorded in creation order: the arc radius (-> "ArcR");
    # D's horizontal then vertical distance from the origin (at +RIB_PLATE_REACH
    # since SX=-1, unsigned magnitudes -> "RibReach", "RibEndH"); P's height
    # (-> "PlateT" / 2); B's reach (-> "RibReach") and its step over P.
    check(
        f"{name} arc radius",
        await adapter.add_sketch_dimension(arc, None, "radial", ARC_R),
    )
    rib.record(f"{stem}ArcR", '"ArcR"')
    check(
        f"{name} arc start on y-axis",
        await adapter.add_sketch_constraint(
            f"{arc}.start", "origin", "vertical_points"
        ),
    )
    check(
        f"{name} arc end on y-axis",
        await adapter.add_sketch_constraint(f"{arc}.end", "origin", "vertical_points"),
    )
    bottom = f"{line_dc}.start"
    plate_top = f"{line_pd}.start"
    top = f"{line_ab}.end"
    await anchor_point_to_origin(adapter, bottom, *d, f"{name} end bottom")
    rib.record(f"{stem}EndBottomX", '"RibReach"')
    rib.record(f"{stem}EndBottomY", '"RibEndH"')
    check(
        f"{name} end face P-D vertical",
        await adapter.add_sketch_constraint(line_pd, None, "vertical"),
    )
    await dimension_between(
        adapter, plate_top, "origin", "vertical_distance", p[1], f"{name} plate top"
    )
    rib.record(f"{stem}EndPlateTopY", '"PlateT" / 2')
    await dimension_between(
        adapter,
        top,
        "origin",
        "horizontal_distance",
        RIB_PLATE_REACH,
        f"{name} end reach",
    )
    rib.record(f"{stem}EndTopX", '"RibReach"')
    await dimension_between(
        adapter,
        plate_top,
        top,
        "vertical_distance",
        EDGE_RIB_END_STEP,
        f"{name} end step over plate top",
    )
    rib.record(f"{stem}EndStep", '"RibEndH" - "PlateT" / 2')
    _ = line_bp
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{stem}Profile")
    drive_jobs += rib.apply(adapter, f"{stem}Profile")
    if flip:
        extrude_at_offset(adapter, RECEIVER_RIB_T, RECEIVER_RIB_OFFSET, flip=True)
    else:
        extrude_at_offset(adapter, RIB_T, RIB_OFFSET)
    name_last_feature(adapter, stem)
    added_volume = edge_rib_added_area_mm2() * (RECEIVER_RIB_T if flip else RIB_T)
    await force_rebuild(adapter)
    await volume_check(
        adapter, f"{stem} net rib addition", v_before + added_volume, 1e-4 * added_volume
    )
    if stem == "EdgeRibFront":
        # The -Z rib's depth is the receiver's named RibDepth
        # (_receiver_model_bands); only the +Z rib takes a plain name here.
        [thickness] = name_dimensions(adapter, stem, ["EdgeRibThickness"])
        drive_jobs.append((thickness, '"RibT"'))


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
    top_arc, _top_c, top_r = await _three_point_arc(
        adapter, p2, p3, top_int, "summation top"
    )
    tip = check("summation tip edge", await adapter.add_line(*p3, *p4))
    bot_arc, bot_c, _ = await _three_point_arc(
        adapter, p4, p1, bot_int, "summation bottom"
    )
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
        adapter,
        f"{base}.start",
        f"{base}.end",
        "vertical_distance",
        PLATE_L,
        "summation base",
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
        adapter,
        f"{tip}.start",
        f"{tip}.end",
        "vertical_distance",
        2.0 * ANCHOR_R,
        "summation tip",
    )
    sd.record("SumTipHeight", '2 * "AnchorR"')
    # The base/tip lines pin all four corners.  The top side is controlled by
    # its own radius -- the size the pattern maker lays out and the drawing
    # prints (2X R) -- with its endpoints already fixed; the mirrored lower
    # side keeps its circumcentre anchor (two dims, no clean global knob,
    # left auto-named).  Both values are the as-sketched geometry, so the
    # profile does not move.
    check(
        "summation side profile radius",
        await adapter.add_sketch_dimension(top_arc, None, "radial", top_r),
    )
    sd.record("SummationArcRadius")
    await anchor_point_to_origin(
        adapter, f"{bot_arc}.center", *bot_c, "summation bottom centre"
    )
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
    [web] = name_dimensions(adapter, "SummationPlate", ["WebThickness"])
    drive_jobs.append((web, '"PlateT"'))


async def _summation_anchor(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 6: Top-plane disc (ANCHOR_R) at the -X tip, extruded ANCHOR_H --
    the SOLID boss the counter-spring anchor is tapped into. The seat itself is
    a native tap (``_counter_anchor_tap``), authored after the ribs, so nothing
    is sketched here but the outside of the boss."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    # Centre (TIP_X, 0): centre-X is a dim (driven to "SumH", |TIP_X|),
    # centre-Z (=0) is a relation (slot ignored), plus the diameter.
    sd = SketchDims()
    check("create_sketch summation anchor", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter,
        TIP_X,
        0.0,
        ANCHOR_R,
        "anchor outer",
        dims=sd,
        names=("AnchorOuterX", "AnchorOuterZ", "AnchorOuterDia"),
        drives=('"SumH"', None, '2 * "AnchorR"'),
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
    [height] = name_dimensions(adapter, "SummationAnchor", ["AnchorHeight"])
    drive_jobs.append((height, '"AnchorH"'))


async def _middle_rib(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 7: Front-plane elongated diamond spanning the lever. Two tangent
    lines run from each end vertex (left = +X plate edge, right = -X summation
    tip) to two coradial arcs that wrap the cylinder -- the C# tangent / coradial
    construction, pinned to scale by the end-vertex anchors, the arc centre at
    the origin, and the arc radius."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    sd = SketchDims()
    check("create_sketch middle rib", await adapter.create_sketch("Front"))
    left = (SX * -RIB_PLATE_REACH, 0.0)  # +X arm vertex, short of hole column
    right = (TIP_X, 0.0)  # -X summation-tip vertex
    r = ARC_R
    # Tangent points from each end vertex to the radius-r circle at the origin.
    tx_l, ty_l = (r * r) / left[0], r * math.sqrt(1.0 - (r * r) / (left[0] ** 2))
    tx_r, ty_r = (r * r) / right[0], r * math.sqrt(1.0 - (r * r) / (right[0] ** 2))
    tl_up, tr_up = (tx_l, ty_l), (tx_r, ty_r)
    tl_dn, tr_dn = (tx_l, -ty_l), (tx_r, -ty_r)

    set_sketch_direct_db(adapter, True)
    line1 = check("middle rib line1", await adapter.add_line(*left, *tl_up))
    arc1, _, _ = await _three_point_arc(
        adapter, tl_up, tr_up, (0.0, r), "middle rib upper"
    )
    line2 = check("middle rib line2", await adapter.add_line(*tr_up, *right))
    line3 = check("middle rib line3", await adapter.add_line(*right, *tr_dn))
    arc2, _, _ = await _three_point_arc(
        adapter, tr_dn, tl_dn, (0.0, -r), "middle rib lower"
    )
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
    # left is at +RIB_PLATE_REACH (SX=-1), right at TIP_X<0 -- both unsigned
    # magnitudes positive, so "RibReach" and "SumH" (|TIP_X|).
    check(
        "middle rib arc radius",
        await adapter.add_sketch_dimension(arc1, None, "radial", r),
    )
    sd.record("MidRibArcR", '"ArcR"')
    await anchor_point_to_origin(
        adapter, f"{line1}.start", *left, "middle rib left vertex"
    )
    sd.record("MidRibLeftX", '"RibReach"')
    await anchor_point_to_origin(
        adapter, f"{line2}.end", *right, "middle rib right vertex"
    )
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
    [thickness] = name_dimensions(adapter, "MiddleRib", ["MiddleRibThickness"])
    drive_jobs.append((thickness, '"RibT"'))


async def _counter_anchor_tap(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 8: the native through tap down the summation-anchor boss -- the
    seat the purchased sm-vn-counter-spring anchor (McMaster 9490T1, ``sm-vn-boss-hook``)
    threads straight into. NO NUT: this tap is the nut, so its size is the
    anchor's own thread (``COUNTER_HOLE_SPEC``) and the anchor's trimmed shank
    equals the boss height it engages (``ANCHOR_H``, one spec constant).

    Authored LAST, after every rib: the middle rib's -X vertex lands on this
    station, and a rib extruded after the cut would refill it (the same trap
    the +X hole column hit -- see RIB_PLATE_REACH). Ordering it here also
    makes the gate below exact: inside the boss footprint the plate and rib
    material sits WITHIN the boss's own +-ANCHOR_H/2 Y span, so the cut removes
    boss height and nothing else.
    """
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"pre-tap mass props failed: {mass.error}")
    v_before = float(mass.data.volume)

    tap_dia = blind_cut_dia_mm(COUNTER_HOLE_SPEC)
    result = wizard_holes(
        adapter,
        COUNTER_HOLE_SPEC,
        [[TIP_X, ANCHOR_H / 2.0, 0.0]],
        (0.0, 1.0, 0.0),
        f"counter-spring anchor tap ({COUNTER_HOLE_SPEC.size})",
        name="CounterAnchorTap",
        expect_dia_mm=tap_dia,
        # Boss centre: X is |TIP_X| from the origin (driven by the same "SumH"
        # knob as the tip), Z is 0 -> an origin-axis relation, no dimension.
        placement_dims=[(("CounterTapX", '"SumH"'), (None, None))],
    )
    drive_jobs += result.placement_drive_jobs
    v_tap = math.pi * (tap_dia / 2.0) ** 2 * ANCHOR_H
    await volume_check(
        adapter, "counter-spring anchor tap", v_before - v_tap, 0.02 * v_tap
    )


def _receiver_model_bands(adapter) -> None:
    """Author receiver limits on owned source dimensions, including subfeatures.

    The -Z entry rib's depth (EdgeRibBack's D1; EdgeRibFront is the opposite
    end) is only named and printed: at RIB_DEPTH it holds the drill point at
    the title block's band (magnifying_bracket_joint_layout)."""
    from _com import _com_invoke, _early_bound
    from _dimensions import _feature_display_dimensions
    from _drawing_marks import _feature_tree
    from magnifying_bracket_joint_layout import THREAD_DEPTH

    model = _early_bound(adapter.currentModel, "IPartDoc")
    feature_name = "EdgeRibBack"
    feature = _early_bound(model.FeatureByName(feature_name), "IFeature")
    dimension = feature.Parameter("D1")
    if dimension is not None:
        dimension = _early_bound(dimension, "IDimension")
    if (
        dimension is None
        or abs(float(dimension.SystemValue) * 1000.0 - RECEIVER_RIB_T) > 1e-5
    ):
        raise RuntimeError(f"{feature_name}: missing native receiver depth D1")
    dimension.Name = "RibDepth"
    set_dimension_display_precision(adapter, feature_name, "RibDepth", 2)
    mark_dimensions_for_drawing(adapter, feature_name, ["RibDepth"])

    feature = _early_bound(model.FeatureByName("BracketMountingTaps"), "IFeature")
    required = {
        "FullThreadDepth": (THREAD_DEPTH, (-THREAD_DEPTH_BAND, THREAD_DEPTH_BAND)),
        "TapDrillDepth": (DRILL_DEPTH, DRILL_DEPTH_DEVIATIONS),
    }
    matches = {name: [] for name in required}
    # Hole Wizard thread lengths can belong to its cosmetic-thread subfeature.
    # Follow the same owned-dimension tree as the tolerance/precision helpers;
    # native names are not a semantic API ("depth" is not guaranteed in them).
    for current in _feature_tree(feature):
        owner = str(_com_invoke(current, "IFeature", "Name"))
        for display in _feature_display_dimensions(current):
            dimension = _com_invoke(display, "IDisplayDimension", "GetDimension2", 0)
            full_name = str(_com_invoke(dimension, "IDimension", "FullName"))
            system_value = float(_com_invoke(dimension, "IDimension", "SystemValue"))
            dimension_type = int(_com_invoke(dimension, "IDimension", "GetType"))
            linear = dimension_type == 0  # swDimensionParamTypeDoubleLinear
            value_mm = system_value * 1000.0
            reported_value = value_mm if linear else system_value
            reported_units = "mm" if linear else "SI"
            _telemetry.info(
                f"BracketMountingTaps native dimension {full_name} = "
                f"{reported_value:.6g} {reported_units} (feature {owner}) "
                f"[parameter type {dimension_type}]"
            )
            parts = full_name.split("@")
            if not linear or len(parts) < 2 or parts[1] != owner:
                continue
            for name, (nominal, _band) in required.items():
                if abs(value_mm - nominal) < 1e-5:
                    matches[name].append((owner, parts[0], display, dimension))
    # Native shape (farm, 2026-10-09): Hole Wizard owns the tap drill depth on
    # one sketch subfeature, but adds one cosmetic-thread subfeature PER HOLE,
    # each owning its own full-thread depth.
    expected = {"FullThreadDepth": len(LEVER_HOLE_POINTS), "TapDrillDepth": 1}
    for name, (_nominal, limits) in required.items():
        owners = {match[0] for match in matches[name]}
        if len(matches[name]) != expected[name] or len(owners) != expected[name]:
            raise RuntimeError(
                f"BracketMountingTaps: expected {expected[name]} native {name} "
                f"(one per owner), found {len(matches[name])}: "
                f"{[match[:2] for match in matches[name]]}"
            )
        for owner, native_name, display, dimension in matches[name]:
            # Wizard-owned names are its native parameter contract; never
            # rewrite them. Subfeatures (Sketch14, Hole Thread22...) are not
            # reachable by FeatureByName, and the per-hole threads share the
            # name D1, so band the dimensions already held, not by name.
            _band_held_dimension(
                display, dimension, limits, f"{native_name}@{owner}"
            )


def _band_held_dimension(
    display, dimension, deviations: tuple[float, float], label: str
) -> None:
    """(lower, upper) tolerance in mm + 2-place display on an already-resolved
    dimension: symmetric when the deviations mirror, else bilateral (the
    by-name ``set_dimension_*_tolerance`` contracts, minus lookup)."""
    from _com import _bind, _early_bound
    from _drawing_tolerances import _set_tolerance_precision

    lower, upper = deviations
    kind = 4 if math.isclose(lower, -upper) else 2  # swTolSYMMETRIC / swTolBILAT
    display = _bind(display, "IDisplayDimension")
    dimension = _bind(dimension, "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = kind
    lower_m, upper_m = lower / 1000.0, upper / 1000.0
    if not tolerance.SetValues(lower_m, upper_m):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    minimum = float(tolerance.GetMinValue())
    maximum = float(tolerance.GetMaxValue())
    if (
        int(tolerance.Type) != kind
        or abs(minimum - lower_m) > 1e-9
        or abs(maximum - upper_m) > 1e-9
    ):
        raise RuntimeError(
            f"{label}: tolerance readback type {int(tolerance.Type)} "
            f"{minimum:g}/{maximum:g} m != type {kind} {lower_m:g}/{upper_m:g} m"
        )
    _set_tolerance_precision(display, (lower, upper), label=label)
    display = _early_bound(display, "IDisplayDimension")
    do_not_change = -1  # swDimensionPrecisionSettings_e
    display.SetPrecision3(2, do_not_change, do_not_change, do_not_change)
    if int(display.GetPrimaryPrecision2()) != 2:
        raise RuntimeError(f"{label}: display precision did not persist")
    _telemetry.success(f"toleranced {label}: {upper:+g}/{lower:+g} mm (2 decimals)")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (declared on the
    base ISketchSegment, not the derived ISketchLine the registry binds)."""
    from _com import _early_bound

    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _driven_hex_width(adapter, width: str) -> None:
    """HexWidth as a driven reference across the shoulder line (code review
    C09): the ridge-to-side dimensions own the width, so this one only reads
    it back and prints in parentheses (``_hex_width_reference``)."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [width], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        0.0,
        (-HEX_H / 2.0 - 1.5) / 1000.0,
        0.0,
        11,  # swDimensionType_e.swHorLinearDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(
            f"knife-envelope width: AddSpecificDimension failed ({status})"
        )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(_read_member(dimension, "DrivenState")) != 1:
        raise RuntimeError("knife-envelope width did not become driven")
    measured = float(_read_member(dimension, "SystemValue")) * 1000.0
    if abs(measured - HEX_W) > 1e-6:
        raise RuntimeError(f"knife-envelope width reads {measured:.6f}, not {HEX_W}")


async def _knife_envelope_reference(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Hidden Front-plane reference: the trunnion's knife-edge controls.

    The hexagon sketch is driven by halves and quarters of HexW/HexH, so no
    single dimension of the solid IS the ridge's distance from a side face,
    a flank's angle to its side face, or the vertex height the knife-edge
    seat needs.  Construction lines carry them off the same globals: the
    vertex line (HexHeight), the shoulder line between the upper shoulders
    (the ridge sharp from each end, RidgeFromLeft/Right; HexWidth a driven
    reference), and the +X upper flank and side face (FlankToSide, driven).
    The part saves the sketch hidden and the drawing shows it only in
    Detail D (code review C09, owner ruling T1)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    knife = SketchDims()
    check("create knife-envelope reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    width = check(
        "knife-envelope shoulder line",
        await adapter.add_line(-HEX_W / 2.0, HEX_H / 4.0, HEX_W / 2.0, HEX_H / 4.0),
    )
    height = check(
        "knife-envelope height reference",
        await adapter.add_line(0.0, -HEX_H / 2.0, 0.0, HEX_H / 2.0),
    )
    flank = check(
        "knife-envelope +X upper flank",
        await adapter.add_line(0.0, HEX_H / 2.0, HEX_W / 2.0, HEX_H / 4.0),
    )
    side = check(
        "knife-envelope +X side face",
        await adapter.add_line(HEX_W / 2.0, HEX_H / 4.0, HEX_W / 2.0, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    for entity in (width, height, flank, side):
        _as_construction(adapter, entity)
    for entity, relation in (
        (width, "horizontal"),
        (height, "vertical"),
        (side, "vertical"),
    ):
        check(
            f"knife-envelope {entity} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    for first, second in (
        (f"{flank}.start", f"{height}.end"),
        (f"{flank}.end", f"{width}.end"),
        (f"{side}.start", f"{width}.end"),
    ):
        check(
            f"knife-envelope {first} on {second}",
            await adapter.add_sketch_constraint(first, second, "coincident"),
        )
    check(
        "knife-envelope side foot level with the origin",
        await adapter.add_sketch_constraint(
            f"{side}.end", "origin", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{height}.end",
        f"{width}.start",
        "horizontal_distance",
        HEX_W / 2.0,
        "knife ridge from the -X side",
    )
    knife.record("RidgeFromLeft", '"HexW" / 2')
    await dimension_between(
        adapter,
        f"{height}.end",
        f"{width}.end",
        "horizontal_distance",
        HEX_W / 2.0,
        "knife ridge from the +X side",
    )
    knife.record("RidgeFromRight", '"HexW" / 2')
    await dimension_between(
        adapter,
        f"{width}.start",
        f"{height}.end",
        "vertical_distance",
        HEX_H / 4.0,
        "knife shoulder below the ridge",
    )
    knife.record("ShoulderDrop", '"HexH" / 4')
    await dimension_between(
        adapter,
        f"{height}.start",
        f"{height}.end",
        "vertical_distance",
        HEX_H,
        "knife-envelope height",
    )
    knife.record("HexHeight", '"HexH"')
    await anchor_point_to_origin(
        adapter, f"{height}.start", 0.0, -HEX_H / 2.0, "knife-envelope height start"
    )
    knife.record("HexHeightHalf", '"HexH" / 2')
    _driven_hex_width(adapter, width)
    knife.record("HexWidth")
    # Text up-right of the +X shoulder, in the wedge opposite the solid's
    # corner: the drawing keeps it there (DETAIL_KEEP), outside the hexagon.
    await add_angular_reference_dimension(
        adapter,
        flank,
        side,
        (HEX_W / 2.0 + 2.0, HEX_H / 4.0 + 0.6),
        "knife flank to side face",
        expected_degrees=180.0 - RIDGE_ANGLE_DEG / 2.0,
    )
    knife.record("FlankToSide")
    await ensure_fully_defined(adapter, "knife-envelope reference sketch")
    check("exit knife-envelope reference", await adapter.exit_sketch())
    name_last_feature(adapter, "KnifeEnvelopeReference")
    drive_jobs += knife.apply(adapter, "KnifeEnvelopeReference")
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "KnifeEnvelopeReference", "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("cannot hide knife-envelope reference sketch")
    model.BlankSketch()
    model.ClearSelection2(True)


async def _cylinder_reference(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Hidden Top-plane reference: the pivot cylinder's diameter for the plan.

    Both plates join the cylinder at its mid-plane, so its silhouettes lie
    inside them and the plan shows only the band where it meets the plate
    tops; the end views see the R15.24 rib outline over it.  A construction
    line across the diameter at CYLINDER_REFERENCE_Z carries it as a driving
    dimension off "CylR"; the part saves the sketch hidden and the drawing
    shows it in the plan only (``_drawing_hidden_sketches``).  The Top-plane
    sketch maps world Z to -sketchY."""
    reference = SketchDims()
    check("create cylinder reference", await adapter.create_sketch("Top"))
    start = (-CYL_R, -CYLINDER_REFERENCE_Z)
    set_sketch_direct_db(adapter, True)
    diameter = check(
        "cylinder diameter reference",
        await adapter.add_line(*start, CYL_R, start[1]),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, diameter)
    check(
        "cylinder diameter reference horizontal",
        await adapter.add_sketch_constraint(diameter, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{diameter}.start",
        f"{diameter}.end",
        "horizontal_distance",
        2.0 * CYL_R,
        "cylinder diameter reference",
    )
    reference.record("CylinderDia", '"CylR" * 2')
    await anchor_point_to_origin(
        adapter, f"{diameter}.start", *start, "cylinder diameter reference start"
    )
    reference.record("CylinderRefX", '"CylR"')
    reference.record("CylinderRefZ", None)
    await ensure_fully_defined(adapter, "cylinder reference sketch")
    check("exit cylinder reference", await adapter.exit_sketch())
    name_last_feature(adapter, "CylinderReference")
    drive_jobs += reference.apply(adapter, "CylinderReference")
    blank_reference_sketches(adapter, ("CylinderReference",))


async def _knife_stub_reference(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Hidden Top-plane reference: one trunnion stub's length for the plan.

    Both stubs are one prism through the body (``_hex_knife``), so no feature
    dimension is a stub's own length.  A construction line down the -Z
    stub's -X side, from the body end (|z| HEX_Z_INNER) to the stub's
    outboard face, carries it as a driving dimension off "HexDepth"; the part
    saves the sketch hidden and the plan shows it as the stubs' "2X".  The
    Top-plane sketch maps world Z to -sketchY."""
    reference = SketchDims()
    check("create knife-stub reference", await adapter.create_sketch("Top"))
    start = (-HEX_W / 2.0, HEX_Z_INNER)
    set_sketch_direct_db(adapter, True)
    length = check(
        "knife-stub length reference",
        await adapter.add_line(*start, start[0], HEX_Z_OUTER),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, length)
    check(
        "knife-stub length reference vertical",
        await adapter.add_sketch_constraint(length, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{length}.start",
        f"{length}.end",
        "vertical_distance",
        HEX_DEPTH,
        "knife-stub length reference",
    )
    reference.record("KnifeStubLength", '"HexDepth"')
    await anchor_point_to_origin(
        adapter, f"{length}.start", *start, "knife-stub length reference start"
    )
    reference.record("KnifeStubRefX", '"HexW" / 2')
    reference.record("KnifeStubRefZ", '"PlateL" / 2')
    await ensure_fully_defined(adapter, "knife-stub reference sketch")
    check("exit knife-stub reference", await adapter.exit_sketch())
    name_last_feature(adapter, "KnifeStubReference")
    drive_jobs += reference.apply(adapter, "KnifeStubReference")
    blank_reference_sketches(adapter, ("KnifeStubReference",))


def _hex_width_reference(adapter) -> None:
    """HexWidth prints as a reference, "2X (8.080)": untoleranced, the
    parentheses its native prefix (DIMENSION_PREFIXES) and suffix."""
    display, dimension = _named_dimension(adapter, "KnifeEnvelopeReference", "HexWidth")
    label = "HexWidth@KnifeEnvelopeReference"
    if int(dimension.DrivenState) != 1:
        raise RuntimeError(f"{label}: a reference dimension must be driven")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolType_e.swTolNONE
    display.SetText(2, ")")  # swDimensionTextParts_e.swDimensionTextSuffix
    if int(tolerance.Type) != 0 or str(display.GetText(2) or "") != ")":
        raise RuntimeError(f"{label}: reference display did not persist")


def _drawing_dimension_contract(adapter) -> None:
    """Size and mark every dimension the print imports (DRAWING_DIMENSIONS)."""
    # The knife-edge controls the free-rock check assumes (code review C09):
    # the ridge from each side face and the flank-to-side angle carry their
    # own tolerances; the vertex height three places, the title block's .XXX.
    for name in ("HexWidth", "HexHeight", "RidgeFromLeft", "RidgeFromRight"):
        set_dimension_display_precision(adapter, "KnifeEnvelopeReference", name, 3)
    set_dimension_display_precision(adapter, "KnifeEnvelopeReference", "FlankToSide", 1)
    set_dimension_display_precision(adapter, "MiddleRibProfile", "MidRibLeftX", 2)
    for name in ("RidgeFromLeft", "RidgeFromRight"):
        set_dimension_symmetric_tolerance(
            adapter, "KnifeEnvelopeReference", name, RIDGE_FROM_SIDE_TOL
        )
    set_dimension_symmetric_angular_tolerance(
        adapter,
        "KnifeEnvelopeReference",
        "FlankToSide",
        KNIFE_FLANK_TO_SIDE_TOL_DEG,
        require_driven=True,
    )
    _hex_width_reference(adapter)
    for (feature_name, name), prefix in DIMENSION_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, name, prefix)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)


async def _receiver_coordinate_dimensions(adapter) -> None:
    """Native coordinate dimensions from the real free edge and top face (the
    spring pad hangs below the plate at the free edge, so its old lower-face
    corner is no longer an edge).

    Each dimension runs from the free edge's top corner, a model vertex, to
    a tap centre.  Both are ends of short construction marks that lie on ink
    the view prints anyway: the corner's runs down the free edge, each tap's
    along its row inside the drill, on the centre mark.  The old L-chain
    through the plate-top corner over each tap drew a line across the end
    rib's face at the plate top, read as a face 2.54 over the taps
    (machinist review r11); the rib's slants wall the taps there."""
    from magnifying_bracket_joint_layout import POSITION_BAND
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    check("receiver coordinate sketch", await adapter.create_sketch("Front"))
    dimensions = SketchDims()
    corner = (PLATE_W, PLATE_T / 2.0)
    edge_end = (PLATE_W, corner[1] - RECEIVER_EDGE_MARK)
    set_sketch_direct_db(adapter, True)
    edge_mark = check(
        "receiver free-edge mark", await adapter.add_line(*corner, *edge_end)
    )
    tap_marks = [
        check(
            f"receiver tap {index} mark",
            await adapter.add_line(*point[:2], point[0] + RECEIVER_TAP_MARK, point[1]),
        )
        for index, point in enumerate(LEVER_HOLE_POINTS)
    ]
    set_sketch_direct_db(adapter, False)
    for mark in (edge_mark, *tap_marks):
        _as_construction(adapter, mark)
    origin_corner = f"{edge_mark}.start"
    await anchor_point_to_origin(adapter, origin_corner, *corner, "receiver free edge")
    dimensions.record("ReceiverOriginX", None)
    dimensions.record("ReceiverOriginY", None)
    check(
        "receiver free-edge mark vertical",
        await adapter.add_sketch_constraint(edge_mark, None, "vertical"),
    )
    await dimension_between(
        adapter,
        origin_corner,
        f"{edge_mark}.end",
        "vertical_distance",
        RECEIVER_EDGE_MARK,
        "receiver free-edge mark length",
    )
    dimensions.record("ReceiverEdgeMark", None)
    for index, (mark, point) in enumerate(zip(tap_marks, LEVER_HOLE_POINTS)):
        check(
            f"receiver tap {index} mark horizontal",
            await adapter.add_sketch_constraint(mark, None, "horizontal"),
        )
        await dimension_between(
            adapter,
            f"{mark}.start",
            f"{mark}.end",
            "horizontal_distance",
            RECEIVER_TAP_MARK,
            f"receiver tap {index} mark length",
        )
        dimensions.record(f"ReceiverTapMark{index}", None)
        await dimension_between(
            adapter,
            origin_corner,
            f"{mark}.start",
            "horizontal_distance",
            corner[0] - point[0],
            "receiver X station",
        )
        dimensions.record(f"ReceiverX{index}", None)
        await dimension_between(
            adapter,
            origin_corner,
            f"{mark}.start",
            "vertical_distance",
            corner[1] - point[1],
            "receiver row",
        )
        dimensions.record(f"ReceiverY{index}", None)
    await ensure_fully_defined(adapter, "receiver coordinate sketch")
    check("exit receiver coordinate sketch", await adapter.exit_sketch())
    name_last_feature(adapter, "ReceiverCoordinates")
    dimensions.apply(adapter, "ReceiverCoordinates")
    names = ["ReceiverX0", "ReceiverX1", "ReceiverY0"]
    for name in names + ["ReceiverY1"]:
        set_dimension_symmetric_tolerance(
            adapter, "ReceiverCoordinates", name, POSITION_BAND
        )
        set_dimension_display_precision(adapter, "ReceiverCoordinates", name, 2)
    mark_dimensions_for_drawing(adapter, "ReceiverCoordinates", names)
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "ReceiverCoordinates", "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("cannot hide receiver coordinate sketch")
    model.BlankSketch()
    model.ClearSelection2(True)


async def _bracket_mounting_taps(adapter) -> None:
    """Cut the two blind front-face taps after all structural additions."""
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"pre-bracket-tap mass props failed: {mass.error}")
    wizard_holes(
        adapter,
        TAP_SPEC,
        LEVER_HOLE_POINTS,
        (0.0, 0.0, -1.0),
        "magnifying bracket mounting taps",
        name="BracketMountingTaps",
        expect_dia_mm=TAP_DRILL_DIA,
    )
    cut_volume = (
        len(LEVER_HOLE_POINTS)
        * math.pi
        * (TAP_DRILL_DIA / 2.0) ** 2
        * (DRILL_DEPTH + DRILL_POINT_DEPTH / 3.0)
    )
    await volume_check(
        adapter,
        "magnifying bracket blind taps",
        float(mass.data.volume) - cut_volume,
        0.02 * cut_volume,
    )


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs: named globals in the equation manager that drive every
    # sketch dim below (a GUI fine-tune edits THESE -- Tools > Equations -- never
    # an auto "D3@Sketch5"). Every length carries an explicit ``mm`` unit: this is
    # an INCH document and the equation manager evaluates BARE numbers in document
    # units, so an unsuffixed "152.4" would read as 152.4 inches and blow the part
    # up 25.4x. Derived globals (ArcR, RibReach, RibEndH) reference others as
    # equation strings so a primitive edit propagates. PlateT/RibT/AnchorH
    # are extrude depths/offsets -- feature params, not sketch dims, so nothing
    # drives them, but they stay editable knobs (matches the exemplars).
    # HexDepth drives the knife prism's length and the stub reference.
    await set_global(adapter, "PlateW", f"{PLATE_W}mm")
    await set_global(adapter, "PlateL", f"{PLATE_L}mm")
    await set_global(adapter, "PlateT", f"{PLATE_T}mm")
    await set_global(adapter, "CylR", f"{CYL_R}mm")
    await set_global(adapter, "RibT", f"{RIB_T}mm")
    await set_global(adapter, "ReceiverRibT", f"{RECEIVER_RIB_T}mm")
    await set_global(adapter, "SpringSeatT", f"{SPRING_SEAT_T}mm")
    await set_global(adapter, "SpringPadW", f"{SPRING_PAD_W}mm")
    await set_global(adapter, "RibPad", f"{RIB_PAD}mm")
    await set_global(adapter, "SumH", f"{SUM_H}mm")
    await set_global(adapter, "AnchorR", f"{ANCHOR_R}mm")
    await set_global(adapter, "AnchorH", f"{ANCHOR_H}mm")
    # (The old HoleDia/AnchorBoreR knobs are gone: both anchor seats are native
    # Hole Wizard taps -- a #6-32 seed + linear pattern on the plate and one
    # #10-24 through the boss -- sized by the tap standard from the purchased
    # anchors' own threads, so a diameter knob would be a second, lying source.
    # HoleX stays -- RibReach references it -- and the three station globals
    # drive the seed while ChannelPitch also drives the pattern spacing.)
    await set_global(adapter, "HoleX", f"{HOLE_X}mm")
    await set_global(adapter, "ChannelZ0", f"{CHANNEL_Z0}mm")
    await set_global(adapter, "ChannelPitch", f"{CHANNEL_PITCH}mm")
    await set_global(adapter, "HoleZOffset", f"{HOLE_Z_OFFSET}mm")
    await set_global(adapter, "HexW", f"{HEX_W}mm")
    await set_global(adapter, "HexH", f"{HEX_H}mm")
    await set_global(adapter, "HexDepth", f"{HEX_DEPTH}mm")
    await set_global(adapter, "KnifeRidgeR", f"{KNIFE_RIDGE_R}mm")
    await set_global(adapter, "StubRootR", f"{STUB_ROOT_R}mm")
    await set_global(adapter, "RibEndR", f"{RIB_END_R}mm")
    await set_global(adapter, "ArcR", '"CylR" + "RibPad"')
    await set_global(adapter, "RibReach", '"HoleX" - 4.1mm')
    # EDGE_RIB_END_HALF_H: the edge-rib slant's height at the end face.
    await set_global(adapter, "RibEndH", '"ArcR" * (1 - "RibReach" / "PlateW")')

    # Per-sketch SketchDims record each dim in the helper's emission order; their
    # drive equations are collected here and applied in one deferred batch at the
    # end (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    await _coefficients_plate(adapter, drive_jobs)
    await _pivot_cylinder(adapter, drive_jobs)
    await _hex_knife(adapter, drive_jobs)
    await _knife_ridge_fillet(adapter, drive_jobs)
    await _edge_rib(
        adapter,
        flip=False,
        name="edge rib front",
        stem="EdgeRibFront",
        drive_jobs=drive_jobs,
    )
    await _edge_rib(
        adapter,
        flip=True,
        name="edge rib back",
        stem="EdgeRibBack",
        drive_jobs=drive_jobs,
    )
    await _summation_plate(adapter, drive_jobs)
    await _summation_anchor(adapter, drive_jobs)
    await _middle_rib(adapter, drive_jobs)
    await _inside_corner_fillets(adapter, drive_jobs)
    await _counter_anchor_tap(adapter, drive_jobs)
    await _bracket_mounting_taps(adapter)
    await _knife_envelope_reference(adapter, drive_jobs)
    await _cylinder_reference(adapter, drive_jobs)
    await _knife_stub_reference(adapter, drive_jobs)

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
    _assert_knife_sides_coplanar(adapter)

    # pivot axis (Axis1) = cylinder centreline along Z -- the static mate
    # reference to the knife-mount (keeps the lever at the knife line with no
    # drop until the ridge bearing supports exist).
    # anchor axis (Axis2) = Z line at the summation anchor -- counter-spring rock
    # reference (the anchor's tapped seat itself is vertical, along Y).
    # knife axis (Axis3) = the hex top-vertex ridge (local y +HEX_H/2) = the true
    # rock/suspension line the lever hangs from; the pivot revolute moves here
    # once the top-plate bearing supports are modeled.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "pivot axis")
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", TIP_X, "anchor axis")
    await name_bore_axis(
        adapter, "Top Plane", HEX_H / 2.0, "Right Plane", 0.0, "knife axis"
    )

    await apply_material(adapter, MATERIAL)
    # Green-painted casting on the machine (ch17/ch18 macros show the same
    # paint as the frame), not bare cast iron.
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    _drawing_dimension_contract(adapter)
    _radius_max_limit(
        adapter,
        "KnifeRidgeFillet",
        "KnifeRidgeRadius",
        KNIFE_RIDGE_R,
        KNIFE_RIDGE_R_BAND,
        KNIFE_RIDGE_R_TOL_TYPE,
    )
    _radius_max_limit(
        adapter,
        "StubRootFillet",
        "StubRootRadius",
        STUB_ROOT_R,
        STUB_ROOT_R_BAND,
        INSIDE_CORNER_R_TOL_TYPE,
    )
    _radius_max_limit(
        adapter,
        "RibEndFillet",
        "RibEndRadius",
        RIB_END_R,
        RIB_END_R_BAND,
        INSIDE_CORNER_R_TOL_TYPE,
    )
    _receiver_model_bands(adapter)
    await _receiver_coordinate_dimensions(adapter)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Back View Note": BACK_VIEW_NOTE,
            "Front View Note": FRONT_VIEW_NOTE,
            "Stub Root View Note": STUB_ROOT_VIEW_NOTE,
            "Middle Rib Plan Note": MIDDLE_RIB_PLAN_NOTE,
        },
    )
    # Native dimension metadata must not erase the already-verified blind taps.
    await force_rebuild(adapter)
    await volume_check(
        adapter, "summing lever after native receiver bands", v_built, 1e-5 * v_built
    )
    _assert_edge_rib_end_planes(adapter)
    _assert_receiver_trimmed_wall(adapter)
    _assert_middle_rib_profile(adapter)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Back View Note",
            "Front View Note",
            "Stub Root View Note",
            "Middle Rib Plan Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
