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

1. Coefficients plate  -- uniform 7 mm positive-X slab with its top held at
   local Y+2.54; the downward addition leaves spring and knife registration
   unchanged. The negative-X counter web stays 5.08 mm centered on Y0.
2. Pivot cylinder      -- Front-plane solid circle at the origin, symmetric
   extrude along the long edge (the pivot/rock axis = local Z).
3. Hex knife edges     -- ONE vertex-up hexagonal prism through the pivot,
   extruded mid-plane out past both body ends: the two trunnion stubs it
   leaves PROTRUDE beyond the body (one per side), so each knife edge rests
   on a bearing support on the top plate (ch30-p003), and the stubs share
   every side face's plane by construction (code review C09).
4. Edge ribs (x2)      -- common tangent R15.24 wrap/flank/R.040 profile at the
   plate ends, each 5.08 mm thick; the middle rib shares that thickness.
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

Sketches follow the repo fully-defined convention (cad/scripts/_sketch.py).
The common rib profile has native tangent constraints, defining dimensions,
face/profile readback and exact incremental-volume gates. Bounded internal
root fillets are selected explicitly and cannot grow into the spring-nut lane.

Dimensions: cad/DIMENSIONS.md ch. 18 (legacy KCL values + M6.4 registration;
low/med confidence).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sm_summing_lever.py
"""

from __future__ import annotations

import math
import re
import sys

import _telemetry
from _appearance import CASTING_GREEN, apply_color, apply_material
from _document_units import apply_package_model_units
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _named_views import name_octant_views
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _paths import IN
from _part_properties import part_drawing_unit
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
    DRILL_DEPTH_BAND,
    DRILL_POINT_DEPTH,
    RECEIVER_DRILL_DEPTH_PLACES,
    RECEIVER_HOLE_PLACES,
    THREAD_DEPTH_BAND,
    RECEIVER_PILOT_WALL_MIN,
    receiver_pilot_material_wall_budget,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_dimension_insert import add_angular_reference_dimension
from _drawing_tolerances import (
    set_dimension_basic_tolerance,
    set_dimension_symmetric_angular_tolerance,
    set_dimension_symmetric_tolerance,
)
from _drawing_precision import (
    _named_dimension,
    apply_drawing_precision,
    set_dimension_display_precision,
)
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
    RECEIVER_COORDINATE_PLACES,
    SPRING_ROW_LOCATORS,
    BASIC_PLACES,
    RECEIVER_ISOMETRIC_OCTANT,
    RECEIVER_ISOMETRIC_VIEW_NOTE,
)
from sm_summing_lever_spec import (
    ANCHOR_H,
    COEFFICIENT_BOTTOM_Y,
    COEFFICIENT_T,
    COEFFICIENT_TOP_Y,
    COUNTER_WEB_T,
    CHANNEL_PITCH,
    CHANNEL_Z0,
    COUNTER_HOLE_SPEC,
    DRAWING_PRECISION,
    HOLE_COUNT,
    HOLE_END_OFFSET_LAST,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_OFFSET,
    HOLE_Z_LAST,
    KNIFE_FLANK_TO_SIDE_TOL_DEG,
    KNIFE_ENVELOPE_PLACES,
    KNIFE_RIDGE_R,
    KNIFE_RIDGE_R_BAND,
    KNIFE_RIDGE_R_PLACES,
    KNIFE_RIDGE_R_TOL_TYPE,
    PLATE_W_DEVIATIONS,
    RIDGE_ANGLE_DEG,
    RIDGE_FROM_SIDE_TOL,
    RIB_BLEND_R,
    RIB_BLEND_R_BAND,
    RIB_BLEND_R_PLACES,
    RIB_BLEND_R_TOL_TYPE,
    RIB_REACH,
    RIB_T,
    RIB_WRAP_R,
    SURFACE_FINISHES,
    UNIT,
)
from sm_summing_lever_profile import LOWER, UPPER, edge_rib_added_area_mm2
from sm_summing_lever_profile import receiver_pilot_wall_budget, receiver_wall_margin

PART_NAME = "sm-summing-lever"
MATERIAL = "Gray Cast Iron"  # see _appearance.apply_material docstring

# The .cs is authored with the coefficients plate on -X; the machine wants it on
# the +X arm (to match the M6.4 frame the rest of the assembly registers to), so
# every .cs-derived X is multiplied by SX.
SX = -1.0

# --- SummingLever.cs constants (inches -> mm) ------------------------------
PLATE_W = 1.75 * IN  # coefficients plate width (along the arm, X)   44.45
PLATE_L = 6.0 * IN  # coefficients/pivot length (along Z)           152.40
# Coefficient thickness and fixed top are imported separately from counter web.
CYL_R = 0.5 * IN  # pivot cylinder radius                          12.70
RIB_PAD = 0.1 * IN  # rib arc padding over the cylinder              2.54
SUM_H = 3.0 * IN  # summation plate height (tip reach)             76.20
SUM_CURV = 0.3 * IN  # summation plate side curvature                7.62
ANCHOR_R = 0.375 * IN  # summation anchor outer radius               9.525
# ANCHOR_H (19.05, the boss height and the counter anchor's engagement) is the
# pure spec's -- build_sm_vn_boss_hook trims the purchased shank to it.

# The coefficient plate's fixed local top registers at machine Y982.24.
# Thickness grows downward, never through a changed installation transform.
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
ARC_R = RIB_WRAP_R
RIB_OFFSET = PLATE_L / 2.0 - RIB_T  # both edge-rib inner caps; outside ends fixed
# No plain anchor bore: the counter anchor's seat is the native COUNTER_HOLE_SPEC
# tap through the boss, authored after the ribs (see _counter_anchor_tap).
# In X, all ribs stop at 35.814 (1.41) before the unchanged spring-hole column
# and worst jam-nut footprint at 36.449. The pilot continues beyond the 5.08 mm
# entry rib into the connected coefficient plate, not an enlarged receiver.
# The shared positive-X branch meets both plate faces with R.040 tangent
# transitions, with no separate pad, ledge or vertical tip face.
if RIB_REACH > HOLE_X - blind_cut_dia_mm(HOLE_SPEC) / 2.0 - 2.0:
    raise AssertionError("a rib's +X end reaches the spring-hole column")

# Receiver-coordinate marks (``_receiver_coordinate_dimensions``): short
# construction lines whose ends carry the bracket-tap coordinates.  The edge
# mark lies on the free edge below its fixed top corner; each tap mark lies
# on its row inside the tap drill.
RECEIVER_EDGE_MARK = 1.0
RECEIVER_TAP_MARK = 0.5
if not RECEIVER_EDGE_MARK < COEFFICIENT_T or not RECEIVER_TAP_MARK < TAP_DRILL_DIA / 2.0:
    raise AssertionError("receiver coordinate marks must stay on printed ink")
# Spring-row marks (``_spring_row_coordinates``): the ridge mark lies on the
# plan's ridge centreline beyond the -Z stub's inboard face, the end mark on
# the +Z end edge at X10 (the edge the plan names datum B), each tap mark on
# its row inside the tap drill.
SPRING_ROW_MARK = 1.0
SPRING_ROW_TAP_MARK = 0.5
SPRING_ROW_END_MARK_X = 10.0
if (
    not 0.3 * HEX_DEPTH + SPRING_ROW_MARK < HEX_DEPTH
    or not SPRING_ROW_TAP_MARK < blind_cut_dia_mm(HOLE_SPEC) / 2.0
):
    raise AssertionError("spring-row coordinate marks must stay on printed ink")


# Spring-hole Z stations (world Z); the Top-plane sketch maps world Z to -sketchY.
HOLE_Z = [CHANNEL_Z0 + CHANNEL_PITCH * j + HOLE_Z_OFFSET for j in range(HOLE_COUNT)]
# The spring-tap pattern's equation drives: the seed's row X and station and
# the pattern's spacing.  The plan's hidden locators (_spring_row_coordinates)
# are driven by the same expressions, so a Tools > Equations edit to any of
# these globals moves the holes and the printed BASICs together.
SPRING_ROW_X_EXPR = '"HoleX"'
SPRING_SEED_STATION_EXPR = (
    f'"ChannelZ0" + {HOLE_COUNT - 1} * "ChannelPitch" + "HoleZOffset"'
)
SPRING_PITCH_EXPR = '"ChannelPitch"'

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


def _assert_coefficient_slab(adapter) -> None:
    """Fixed real seats and persistent extrusion dimensions after rebuild."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    feature = _early_bound(model.FeatureByName("CoefficientsPlate"), "IFeature")
    heights = []
    for raw in feature.GetFaces() or ():
        surface = _early_bound(_early_bound(raw, "IFace2").GetSurface(), "ISurface")
        if not surface.IsPlane():
            continue
        values = tuple(float(value) for value in surface.PlaneParams)
        if abs(abs(values[1]) - 1.0) < 1e-8:
            heights.append(values[4] * 1000.0)
    for expected in (COEFFICIENT_TOP_Y, COEFFICIENT_BOTTOM_Y):
        if not any(math.isclose(actual, expected, abs_tol=1e-5) for actual in heights):
            raise RuntimeError(f"CoefficientsPlate: missing seat Y{expected}; found {heights}")
    for owner, name, expected in (
        ("PlateProfile", "PlateThickness", COEFFICIENT_T),
        ("PlateProfile", "PlateTopY", COEFFICIENT_TOP_Y),
        ("CoefficientsPlate", "PlateLength", PLATE_L),
    ):
        owned = _early_bound(model.FeatureByName(owner), "IFeature")
        raw = owned.Parameter(name)
        if raw is None or not math.isclose(
            float(_early_bound(raw, "IDimension").SystemValue) * 1000.0,
            expected, abs_tol=1e-6,
        ):
            raise RuntimeError(f"{owner}: native {name} did not persist")
    _telemetry.success(
        f"uniform coefficient slab: native Y{COEFFICIENT_BOTTOM_Y}..{COEFFICIENT_TOP_Y}, "
        f"thickness {COEFFICIENT_T}"
    )


def _assert_boss_face_graph(adapter) -> None:
    """Real Y faces tie the boss and counterweb to the coefficient top.

    The plate is not symmetric about Y0. Its actual top is the common web
    top; the boss top stands ANCHOR_H/2 above Y0, not above the plate centre.
    This proves the flush caption without inventing a midplane datum.
    """
    model = _early_bound(adapter.currentModel, "IPartDoc")
    for owner, expected in (
        ("SummationAnchor", (-ANCHOR_H / 2.0, ANCHOR_H / 2.0)),
        ("SummationPlate", (-COUNTER_WEB_T / 2.0, COEFFICIENT_TOP_Y)),
        ("CoefficientsPlate", (COEFFICIENT_BOTTOM_Y, COEFFICIENT_TOP_Y)),
    ):
        raw_feature = model.FeatureByName(owner)
        if raw_feature is None:
            raise RuntimeError(f"{owner}: missing native face-graph owner")
        heights = []
        for raw in _early_bound(raw_feature, "IFeature").GetFaces() or ():
            surface = _early_bound(_early_bound(raw, "IFace2").GetSurface(), "ISurface")
            if surface.IsPlane():
                values = tuple(float(value) for value in surface.PlaneParams)
                if abs(abs(values[1]) - 1.0) < 1e-8:
                    heights.append(values[4] * 1000.0)
        if not all(
            any(math.isclose(actual, level, abs_tol=1e-5) for actual in heights)
            for level in expected
        ):
            raise RuntimeError(f"{owner}: native Y faces {heights} do not contain {expected}")
    _telemetry.success(
        "boss face graph: boss top above coefficient top by "
        f"{ANCHOR_H / 2.0 - COEFFICIENT_TOP_Y:.6f} mm; counterweb top flush"
    )


async def _coefficients_plate(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 1: uniform coefficient slab from Y-4.46 to fixed Y+2.54.

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
    check("create_sketch plate", await adapter.create_sketch("Front"))
    # The actual +X end's vertical line owns the 7 mm native dimension, so
    # VIEW F can import real top/bottom witnesses rather than an extrusion
    # depth whose automatic attachment may sit behind the pivot body.
    rect = [
        (0.0, COEFFICIENT_TOP_Y),
        (PLATE_W, COEFFICIENT_TOP_Y),
        (PLATE_W, COEFFICIENT_BOTTOM_Y),
        (0.0, COEFFICIENT_BOTTOM_Y),
    ]
    set_sketch_direct_db(adapter, True)
    outline = await add_line_chain(adapter, rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter,
        outline,
        rect,
        label="plate",
        dims=plate,
        names=["PlateWidth", "PlateThickness", "PlateTopY"],
        drives=['"PlateW"', '"CoefficientT"', '"CoefficientTopY"'],
    )
    await ensure_fully_defined(adapter, "coefficients plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude coefficients plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_L, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CoefficientsPlate")
    [length] = name_dimensions(adapter, "CoefficientsPlate", ["PlateLength"])
    drive_jobs.append((length, '"PlateL"'))
    _assert_coefficient_slab(adapter)
    v_plate = PLATE_W * PLATE_L * COEFFICIENT_T
    await volume_check(adapter, "coefficients plate", v_plate, 1e-3 * v_plate)

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
        [[HOLE_X, COEFFICIENT_TOP_Y, HOLE_Z[-1]]],
        (0.0, 1.0, 0.0),
        f"spring hole seed (station j={HOLE_COUNT - 1}, {HOLE_SPEC.size})",
        name="SpringHoleSeed",
        expect_dia_mm=seed_dia,
        placement_dims=[
            (
                ("HoleSeedX", SPRING_ROW_X_EXPR),
                ("HoleSeedStation", SPRING_SEED_STATION_EXPR),
            )
        ],
    )
    drive_jobs += seed_result.placement_drive_jobs
    seed_cut = seed_result.name
    v_hole = math.pi * (seed_dia / 2.0) ** 2 * COEFFICIENT_T
    await volume_check(adapter, "spring hole seed", v_plate - v_hole, 0.02 * v_hole)
    check(
        "linear pattern spring holes",
        await adapter.linear_pattern_feature(
            LinearPatternParameters(
                direction_point=[PLATE_W, COEFFICIENT_TOP_Y, 0.0],
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
    drive_jobs.append(("D3@SpringHolePattern", SPRING_PITCH_EXPR))
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


def _knife_ridge_max_limit(adapter) -> None:
    """KnifeRidgeRadius as the single limit "R.004 MAX" carrying the band's
    deviations (build_ch_pivot_bracket._corner_radius_max_limit's recipe)."""
    lower, upper = deviations(KNIFE_RIDGE_R_BAND)
    _, dimension = _named_dimension(adapter, "KnifeRidgeFillet", "KnifeRidgeRadius")
    label = "KnifeRidgeRadius@KnifeRidgeFillet"
    value = float(dimension.SystemValue)
    if not math.isclose(value, KNIFE_RIDGE_R / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max "
            f"{KNIFE_RIDGE_R}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = KNIFE_RIDGE_R_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != KNIFE_RIDGE_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    set_dimension_display_precision(
        adapter, "KnifeRidgeFillet", "KnifeRidgeRadius", KNIFE_RIDGE_R_PLACES
    )
    _telemetry.success(f"{label}: single limit {KNIFE_RIDGE_R:g} MAX")


def _assert_edge_rib_end_planes(adapter) -> None:
    """Read all three native rib depths and caps; edge outer caps may merge."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    expected = {
        "EdgeRibBack": (-RIB_OFFSET, -PLATE_L / 2.0, "EdgeRibThickness", RIB_T),
        "EdgeRibFront": (RIB_OFFSET, PLATE_L / 2.0, "EdgeRibThickness", RIB_T),
        "MiddleRib": (-RIB_T / 2.0, RIB_T / 2.0, "MiddleRibThickness", RIB_T),
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
        required = (inner, outer) if name == "MiddleRib" else (inner,)
        if not all(
            any(abs(cap - z) <= tolerance_mm for z in planes) for cap in required
        ) or any(
            min(abs(z - inner), abs(z - outer)) > tolerance_mm for z in planes
        ):
            raise RuntimeError(
                f"{name}: native end planes {planes} mm do not establish {(inner, outer)} mm"
            )
        _telemetry.success(
            f"{name}: native depth {depth_mm:.2f} mm; end planes {sorted(planes)} mm; "
            f"inner cap {inner:.2f} mm; outer boundary {outer:.2f} mm"
        )


async def _rib_profile_sketch(
    adapter, stem: str, drive_jobs: list[tuple[str, str]], *, middle: bool = False
) -> None:
    """One G1 positive-X profile; the middle's negative-X tangents are unchanged.

    Native tangencies, radii and end-point dimensions derive the flank
    stations. Rounded design-report coordinates are never independent knobs.
    The closing line lies wholly inside the coefficient plate, so it creates
    no vertical rib-tip face in the merged solid.
    """
    rib = SketchDims()
    check(f"{stem} sketch", await adapter.create_sketch("Front"))

    async def line(a, b, label):
        return check(
            f"{stem} {label}", await adapter.add_line(a[0], a[1], b[0], b[1])
        )

    async def arc(center, a, b, label):
        return check(
            f"{stem} {label}",
            await adapter.add_arc(
                center[0], center[1], a[0], a[1], b[0], b[1]
            ),
        )

    set_sketch_direct_db(adapter, True)
    upper_blend = await arc(
        UPPER.center_xy, UPPER.flank_xy, UPPER.end_xy, "upper R.040 blend"
    )
    end = await line(UPPER.end_xy, LOWER.end_xy, "buried closing line")
    lower_blend = await arc(
        LOWER.center_xy, LOWER.end_xy, LOWER.flank_xy, "lower R.040 blend"
    )
    upper_flank = await line(UPPER.wrap_xy, UPPER.flank_xy, "upper tangent flank")
    lower_flank = await line(LOWER.flank_xy, LOWER.wrap_xy, "lower tangent flank")
    negative_top = negative_bottom = None
    if middle:
        tangent_x = ARC_R**2 / TIP_X
        tangent_y = ARC_R * math.sqrt(1.0 - ARC_R**2 / TIP_X**2)
        top, bottom = (tangent_x, tangent_y), (tangent_x, -tangent_y)
        wrap = await arc((0.0, 0.0), UPPER.wrap_xy, top, "upper wrap")
        negative_top = await line(top, (TIP_X, 0.0), "counter upper tangent")
        negative_bottom = await line((TIP_X, 0.0), bottom, "counter lower tangent")
        lower_wrap = await arc((0.0, 0.0), bottom, LOWER.wrap_xy, "lower wrap")
    else:
        wrap = await arc((0.0, 0.0), UPPER.wrap_xy, LOWER.wrap_xy, "pivot wrap")
        lower_wrap = wrap
    set_sketch_direct_db(adapter, False)

    check(
        f"{stem} wrap origin",
        await adapter.add_sketch_constraint(f"{wrap}.center", "origin", "coincident"),
    )
    check(
        f"{stem} wrap radius",
        await adapter.add_sketch_dimension(wrap, None, "radial", ARC_R),
    )
    rib.record(f"{stem}ArcR", '"ArcR"')
    if middle:
        check(
            f"{stem} common wrap circle",
            await adapter.add_sketch_constraint(wrap, lower_wrap, "coradial"),
        )
    await anchor_point_to_origin(
        adapter, f"{end}.start", *UPPER.end_xy, f"{stem} actual upper end"
    )
    rib.record("RibReach" if stem == "EdgeRibFront" else f"{stem}Reach", '"RibReach"')
    rib.record(f"{stem}TopY", '"CoefficientTopY"')
    check(
        f"{stem} closing line vertical",
        await adapter.add_sketch_constraint(end, None, "vertical"),
    )
    await dimension_between(
        adapter, f"{end}.start", f"{end}.end", "vertical_distance",
        COEFFICIENT_T, f"{stem} plate thickness",
    )
    rib.record(f"{stem}PlateThickness", '"CoefficientT"')
    for blend, endpoint, suffix in (
        (upper_blend, f"{end}.start", "Upper"),
        (lower_blend, f"{end}.end", "Lower"),
    ):
        check(
            f"{stem} {suffix} blend radius",
            await adapter.add_sketch_dimension(blend, None, "radial", RIB_BLEND_R),
        )
        rib.record(f"{stem}{suffix}BlendR", '"RibBlendR"')
        check(
            f"{stem} {suffix} blend flat tangency",
            await adapter.add_sketch_constraint(
                f"{blend}.center", endpoint, "vertical_points"
            ),
        )
    pairs = [
        (upper_blend, upper_flank), (upper_flank, wrap),
        (lower_blend, lower_flank), (lower_flank, lower_wrap),
    ]
    if middle:
        pairs += [(wrap, negative_top), (lower_wrap, negative_bottom)]
        await anchor_point_to_origin(
            adapter, f"{negative_top}.end", TIP_X, 0.0, f"{stem} counter tip"
        )
        rib.record(f"{stem}CounterReach", '"SumH"')
    for index, (first, second) in enumerate(pairs):
        check(
            f"{stem} tangent {index}",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )
    await ensure_fully_defined(adapter, f"{stem} common tangent profile")
    check(f"{stem} exit sketch", await adapter.exit_sketch())
    name_last_feature(adapter, f"{stem}Profile")
    drive_jobs += rib.apply(adapter, f"{stem}Profile")


def _assert_native_rib_profile(adapter, stem: str) -> None:
    """Prove both real flanks and both R.040 blend surfaces, not only the sketch."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    raw = model.FeatureByName(stem)
    if raw is None:
        raise RuntimeError(f"{stem}: missing native profile feature")
    found_flanks: set[int] = set()
    found_blends: set[int] = set()
    for raw_face in _early_bound(raw, "IFeature").GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface.IsPlane():
            values = tuple(float(value) for value in surface.PlaneParams)
            normal, point = values[:3], values[3:]
            for index, branch in enumerate((UPPER, LOWER)):
                expected = (*branch.normal_xy, 0.0)
                aligned = abs(sum(a * b for a, b in zip(normal, expected, strict=True)))
                offset = sum(a * b for a, b in zip(expected, point, strict=True)) * 1000.0
                if aligned > 1.0 - 1e-8 and abs(offset - ARC_R) < 1e-5:
                    found_flanks.add(index)
        elif surface.IsCylinder():
            values = tuple(float(value) for value in surface.CylinderParams)
            if len(values) != 7 or abs(abs(values[5]) - 1.0) > 1e-8:
                continue
            for index, branch in enumerate((UPPER, LOWER)):
                if (
                    math.dist(tuple(value * 1000.0 for value in values[:2]), branch.center_xy) < 1e-5
                    and abs(values[6] * 1000.0 - RIB_BLEND_R) < 1e-5
                ):
                    found_blends.add(index)
    if found_flanks != {0, 1} or found_blends != {0, 1}:
        raise RuntimeError(
            f"{stem}: native tangent profile lost flanks {found_flanks} "
            f"or bounded blends {found_blends}"
        )
    _telemetry.success(f"{stem}: both native tangent flanks and R.040 profile blends")


async def _edge_rib(
    adapter, flip: bool, name: str, stem: str, drive_jobs: list[tuple[str, str]]
) -> None:
    """The common tangent profile and uniform thickness at either fixed end."""
    v_before = await _measured_volume(adapter, f"before {stem}")
    await _rib_profile_sketch(adapter, stem, drive_jobs)
    extrude_at_offset(adapter, RIB_T, RIB_OFFSET, flip=flip)
    name_last_feature(adapter, stem)
    added_volume = edge_rib_added_area_mm2() * RIB_T
    await force_rebuild(adapter)
    await volume_check(
        adapter, f"{stem} net rib addition", v_before + added_volume, 1e-4 * added_volume
    )
    [thickness] = name_dimensions(adapter, stem, ["EdgeRibThickness"])
    drive_jobs.append((thickness, '"RibT"'))
    _assert_native_rib_profile(adapter, stem)


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
            ExtrusionParameters(depth=COUNTER_WEB_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SummationPlate")
    [web] = name_dimensions(adapter, "SummationPlate", ["WebThickness"])
    drive_jobs.append((web, '"CounterWebT"'))


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
    """Shared positive branches; unchanged negative counter-arm tangent profile."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    await _rib_profile_sketch(adapter, "MiddleRib", drive_jobs, middle=True)
    check(
        "extrude middle rib",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RIB_T, both_directions=True)
        ),
    )
    name_last_feature(adapter, "MiddleRib")
    [thickness] = name_dimensions(adapter, "MiddleRib", ["MiddleRibThickness"])
    drive_jobs.append((thickness, '"RibT"'))
    _assert_native_rib_profile(adapter, "MiddleRib")


@_telemetry.traced("part.receiver_plate_backing")
def _assert_receiver_plate_backing(adapter) -> None:
    """Read the real plate boundaries beyond the entry rib, before drilling.

    The initial uniform slab and merged rib construction supply connectivity.
    Trimmed-face witnesses must retain the complete nominal pilot width from
    the inner cap through the drill-point tip. This is nominal geometry proof,
    not a finished-thread cavity or a manufactured tolerance guarantee; the
    independent printed-pilot budget and subsequent exact cut-volume gate
    remain mandatory.
    """
    model = _early_bound(adapter.currentModel, "IPartDoc")
    raw = model.FeatureByName("CoefficientsPlate")
    if raw is None:
        raise RuntimeError("receiver: missing native coefficient-plate backing")
    boundaries = (
        (1, COEFFICIENT_TOP_Y),
        (1, COEFFICIENT_BOTTOM_Y),
        (0, PLATE_W),
    )
    _telemetry.annotate(receivers=len(LEVER_HOLE_POINTS), boundaries=len(boundaries))
    faces = {boundary: [] for boundary in boundaries}
    for raw_face in _early_bound(raw, "IFeature").GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        raw_surface = face.GetSurface()
        if raw_surface is None:
            raise RuntimeError("receiver: missing native backing surface")
        surface = _early_bound(raw_surface, "ISurface")
        if not surface.IsPlane():
            continue
        values = tuple(float(value) for value in surface.PlaneParams)
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            raise RuntimeError("receiver: invalid native backing plane parameters")
        for axis, level in boundaries:
            if (
                abs(abs(values[axis]) - 1.0) < 1e-8
                and all(abs(values[index]) < 1e-8 for index in range(3) if index != axis)
                and math.isclose(values[axis + 3] * 1000.0, level, abs_tol=1e-5)
            ):
                faces[(axis, level)].append(face)
    if not all(faces.values()):
        raise RuntimeError("receiver: missing native plate top, underside or free-edge backing plane")
    radius = TAP_DRILL_DIA / 2.0
    for x, y, entry_z in LEVER_HOLE_POINTS:
        inner_z = entry_z + RIB_T
        tip_z = entry_z + DRILL_DEPTH + DRILL_POINT_DEPTH
        if not -PLATE_L / 2.0 < inner_z < tip_z < PLATE_L / 2.0:
            raise RuntimeError("receiver: pilot backing interval is not inside the coefficient plate")
        for axis, level in boundaries:
            clearance = level - (x if axis == 0 else y) - radius
            if axis == 1 and level == COEFFICIENT_BOTTOM_Y:
                clearance = y - level - radius
            if clearance < RECEIVER_PILOT_WALL_MIN:
                raise RuntimeError("receiver: native plate backing loses nominal pilot wall")
            for z in (inner_z, (inner_z + tip_z) / 2.0, tip_z):
                for side in (-1.0, 1.0):
                    witness = (x + side * radius, level, z) if axis == 1 else (
                        level, y + side * radius, z
                    )
                    distances = []
                    for face in faces[(axis, level)]:
                        result = face.GetClosestPointOn(
                            witness[0] / 1000.0, witness[1] / 1000.0, witness[2] / 1000.0
                        )
                        if result is None or len(result) != 5 or not all(
                            math.isfinite(float(value)) for value in result
                        ):
                            raise RuntimeError("receiver: invalid native backing closest point")
                        point = tuple(float(value) * 1000.0 for value in result[:3])
                        distances.append(math.dist(witness, point))
                    if min(distances) > 1e-4:
                        raise RuntimeError(
                            f"receiver X{x}: native trimmed plate backing misses {witness}; "
                            f"distance {min(distances):.6f} mm"
                        )
        _telemetry.success(
            f"receiver X{x}, Y{y}: native plate top/underside/free edge retain nominal "
            f"pilot width from inner cap Z{inner_z:.6f} through point Z{tip_z:.6f}"
        )


def _assert_receiver_profile_walls(adapter) -> None:
    """Cross-check the native pilot profile and its printed tolerance budget.

    Native trimmed-face distances establish the nominal pilot clearance.
    The independent budget includes the printed pilot band and drill wander;
    it does not bound the finished thread cavity. Native pilot-volume/end-plane
    gates remain separate. Later concave roots only add material.
    """
    raw = _early_bound(adapter.currentModel, "IPartDoc").FeatureByName("EdgeRibBack")
    if raw is None:
        raise RuntimeError("receiver: missing native entry rib")
    feature = _early_bound(raw, "IFeature")
    sides = []
    for raw_face in feature.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface.IsPlane():
            normal = tuple(float(value) for value in surface.PlaneParams[:3])
            if abs(normal[2]) > 1e-8:
                continue
        sides.append(face)
    if not sides:
        raise RuntimeError("receiver: no native longitudinal profile faces")
    radius = TAP_DRILL_DIA / 2.0
    z = -PLATE_L / 2.0 + RIB_T / 2.0
    for x, y, _ in LEVER_HOLE_POINTS:
        distances = []
        for face in sides:
            result = face.GetClosestPointOn(x / 1000.0, y / 1000.0, z / 1000.0)
            if result is None or len(result) != 5 or not all(
                math.isfinite(float(value)) for value in result
            ):
                raise RuntimeError("receiver: invalid native trimmed-face closest point")
            point = tuple(float(value) * 1000.0 for value in result[:3])
            distances.append(math.dist((x, y, z), point) - radius)
        native_clearance = min(distances)
        expected = receiver_wall_margin(x, y, radius)
        if not math.isclose(native_clearance, expected, abs_tol=1e-4):
            raise RuntimeError(
                f"receiver X{x}: native pilot-profile clearance {native_clearance:.6f} "
                f"!= signed profile {expected:.6f}"
            )
        if native_clearance < RECEIVER_PILOT_WALL_MIN:
            raise RuntimeError(
                f"receiver X{x}: native pilot-profile clearance {native_clearance:.6f} "
                f"below {RECEIVER_PILOT_WALL_MIN:g} mm"
            )
        _telemetry.success(
            f"receiver X{x}: native pilot-profile clearance {native_clearance:.6f} mm "
            f"outside nominal pilot radius {radius:.6f} mm"
        )
    _assert_receiver_plate_backing(adapter)
    for budget in receiver_pilot_wall_budget():
        if not math.isfinite(budget.minimum_mm) or budget.minimum_mm < RECEIVER_PILOT_WALL_MIN:
            raise RuntimeError(
                f"receiver X{budget.x_mm}: printed-pilot longitudinal wall "
                f"{budget.minimum_mm:.6f} below {RECEIVER_PILOT_WALL_MIN}; "
                f"witness {budget.minimum_witness}"
            )
        _telemetry.success(
            f"receiver X{budget.x_mm}: printed-pilot longitudinal wall "
            f"{budget.minimum_mm:.6f} mm (upper {budget.upper_mm:.6f}, "
            f"lower {budget.lower_mm:.6f}); drill allowance and wander included"
        )
    material_wall = receiver_pilot_material_wall_budget()
    if not math.isfinite(material_wall) or material_wall < RECEIVER_PILOT_WALL_MIN:
        raise RuntimeError(
            f"receiver: printed-pilot connected-material wall {material_wall:.6f} mm "
            f"below {RECEIVER_PILOT_WALL_MIN:g} mm"
        )
    _telemetry.success(
        f"receiver: printed-pilot connected-material wall {material_wall:.6f} mm "
        f">= {RECEIVER_PILOT_WALL_MIN:g} mm; uniform RibT {RIB_T:.2f} mm; pilot only"
    )


def coefficient_underside_root_geometry() -> tuple[
    float, tuple[float, float], tuple[float, float], tuple[tuple[float, float], ...]
]:
    """Nominal lower junction, tangent R.040 cylinder and two inboard edge runs.

    The fillet circle is externally tangent to the pivot cylinder and tangent
    to the plate underside. Its centre is R below the underside, at distance
    CylR + R from the pivot axis. Cap-root corner patches get a one-radius
    neighbourhood in the native audit; neither outside body end is selected.
    """
    bottom, radius = COEFFICIENT_BOTTOM_Y, RIB_BLEND_R
    runs = (
        (-RIB_OFFSET, -RIB_T / 2.0),
        (RIB_T / 2.0, RIB_OFFSET),
    )
    if (
        not all(math.isfinite(value) for value in (bottom, radius, CYL_R, PLATE_L))
        or not -CYL_R < bottom < 0.0
        or radius <= 0.0
        or any(
            not all(math.isfinite(value) for value in (start, end))
            or not -PLATE_L / 2.0 < start - radius < end + radius < PLATE_L / 2.0
            or end - start <= 4.0 * radius
            for start, end in runs
        )
    ):
        raise ValueError("lower plate/cylinder blend violates inboard tangent-run premises")
    edge_x = math.sqrt(CYL_R**2 - bottom**2)
    center_y = bottom - radius
    center_x = math.sqrt((CYL_R + radius)**2 - center_y**2)
    tangent = (
        center_x * CYL_R / (CYL_R + radius),
        center_y * CYL_R / (CYL_R + radius),
    )
    return edge_x, (center_x, center_y), tangent, runs


def rib_root_edge_families() -> tuple[tuple[str, list[list[float]], float], ...]:
    """Explicit reentrant roots only; never the outside receiver/knife caps.

    The bound is a conservative r² prism around the selected edge lengths,
    including cylindrical curvature and end-corner interactions. It bounds
    actual ADDED native material, not the unfilleted body's bounding box.
    """
    end_caps = (-RIB_OFFSET, RIB_OFFSET)
    middle_caps = (-RIB_T / 2.0, RIB_T / 2.0)
    plate_picks = [
        [25.0, y, z]
        for z in (*end_caps, *middle_caps)
        for y in (COEFFICIENT_TOP_Y, COEFFICIENT_BOTTOM_Y)
    ]
    cylinder_picks = [[-CYL_R, 0.0, z] for z in end_caps]
    cylinder_picks += [
        [0.0, sign * CYL_R, z] for z in middle_caps for sign in (-1.0, 1.0)
    ]
    counter_picks = [
        [-30.0, sign * COUNTER_WEB_T / 2.0, z]
        for z in middle_caps for sign in (-1.0, 1.0)
    ]
    edge_x, _, _, longitudinal_runs = coefficient_underside_root_geometry()
    longitudinal_picks = [
        [edge_x, COEFFICIENT_BOTTOM_Y, (start + end) / 2.0]
        for start, end in longitudinal_runs
    ]
    return (
        ("RibCylinderRootFillets", cylinder_picks, 4.0 * math.tau * CYL_R),
        ("RibCounterRootFillets", counter_picks, 4.0 * SUM_H),
        ("RibRootFillets", plate_picks, 8.0 * RIB_REACH),
        # Keep the established cap-root operations and their bounds unchanged.
        # Mid-run longitudinal edges survive those rounds; the last operation
        # joins their corner patches without tangent propagation.
        (
            "CoefficientUndersideRootFillets",
            longitudinal_picks,
            sum(end - start for start, end in longitudinal_runs) + 4.0 * RIB_BLEND_R,
        ),
    )


def _assert_root_feature_bounds(adapter, name: str, minimum_faces: int) -> None:
    """Read only new fillet surfaces: bounded reach, entry and radius."""
    raw = _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(name)
    feature = _early_bound(raw, "IFeature")
    count = 0
    underside = name == "CoefficientUndersideRootFillets"
    if underside:
        _, center, tangent, runs = coefficient_underside_root_geometry()
        # A finite one-radius cap-corner neighbourhood surrounds the exact
        # straight-run tangent section. This is not an allowance for the old
        # families, whose reach/entry/radius bounds below remain unchanged.
        lower_bounds = (tangent[0] - RIB_BLEND_R, tangent[1] - RIB_BLEND_R)
        upper_bounds = (center[0] + RIB_BLEND_R, COEFFICIENT_BOTTOM_Y + RIB_BLEND_R)
        covered_runs = set()
        from magnifying_bracket_joint_layout import (
            DRILL_WANDER_MAX, POSITION_BAND, receiver_pilot_radius_max,
        )

        pilot_radius = receiver_pilot_radius_max() + DRILL_WANDER_MAX
        # This X-disjointness proof covers the finite pilot, with ordinary
        # free-edge motion and the actual-axis position band. No wall credit
        # is taken for the material added by the concave blend.
        receiver_inner_x = (
            min(point[0] for point in LEVER_HOLE_POINTS)
            + PLATE_W_DEVIATIONS[0] - POSITION_BAND - pilot_radius
        )
        if (
            upper_bounds[0] >= min(receiver_inner_x, PLATE_W, RIB_REACH)
            or upper_bounds[1] >= COEFFICIENT_TOP_Y
        ):
            raise RuntimeError(f"{name}: lower-junction envelope reaches a retained interface")
    for raw_face in feature.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        radius = None
        if surface.IsCylinder():
            radius = float(surface.CylinderParams[6]) * 1000.0
        elif surface.IsTorus():
            radius = float(surface.TorusParams[7]) * 1000.0
        # A transition patch can be nonanalytic. It must pass the same exact
        # bounds, but cannot stand in for a proved cylindrical/toroidal R.040.
        # IFace2.GetBox is approximate. A temporary, unsaved sheet body of
        # this actual trimmed fillet face gives exact directional extrema,
        # without confusing its envelope with the plate's X44.45 free edge.
        sheet_raw = face.CreateSheetBody()
        if sheet_raw is None:
            raise RuntimeError(f"{name}: cannot extract native root face for exact bounds")
        sheet = _early_bound(sheet_raw, "IBody2")
        extrema = []
        directions = [
            ((1.0, 0.0, 0.0), 0), ((0.0, 0.0, -1.0), 2), ((0.0, 0.0, 1.0), 2),
        ]
        if underside:
            directions += [
                ((-1.0, 0.0, 0.0), 0), ((0.0, -1.0, 0.0), 1), ((0.0, 1.0, 0.0), 1),
            ]
        for direction, axis in directions:
            result = sheet.GetExtremePoint(direction[0], direction[1], direction[2])
            if result is None or len(result) != 4 or not result[0] or not all(
                math.isfinite(float(value)) for value in result[1:]
            ):
                raise RuntimeError(f"{name}: invalid exact native root extreme {result}")
            extrema.append(float(result[axis + 1]) * 1000.0)
        x_max, z_min, z_max = extrema[:3]
        if x_max > RIB_REACH + 1e-5:
            raise RuntimeError(
                f"{name}: R{RIB_BLEND_R} root face grows beyond X{RIB_REACH}: {extrema}"
            )
        if z_min <= -PLATE_L / 2.0 + 1e-5 or z_max >= PLATE_L / 2.0 - 1e-5:
            raise RuntimeError(f"{name}: root blend reaches an outside entry/knife cap: {extrema}")
        if underside:
            x_min, y_min, y_max = extrema[3:]
            if (
                x_min < lower_bounds[0] - 1e-5 or x_max > upper_bounds[0] + 1e-5
                or y_min < lower_bounds[1] - 1e-5 or y_max > upper_bounds[1] + 1e-5
                or not any(
                    start - RIB_BLEND_R - 1e-5 <= z_min <= z_max <= end + RIB_BLEND_R + 1e-5
                    for start, end in runs
                )
            ):
                raise RuntimeError(f"{name}: native face escapes the lower-junction envelope: {extrema}")
            if surface.IsCylinder() and z_max - z_min > 4.0 * RIB_BLEND_R:
                parameters = tuple(float(value) for value in surface.CylinderParams)
                if (
                    len(parameters) != 7 or not all(math.isfinite(value) for value in parameters)
                    or not math.isclose(parameters[0] * 1000.0, center[0], abs_tol=1e-5)
                    or not math.isclose(parameters[1] * 1000.0, center[1], abs_tol=1e-5)
                    or abs(parameters[3]) > 1e-6 or abs(parameters[4]) > 1e-6
                    or not math.isclose(abs(parameters[5]), 1.0, abs_tol=1e-6)
                ):
                    raise RuntimeError(f"{name}: native cylinder is not the lower tangent blend: {parameters}")
                for index, (start, end) in enumerate(runs):
                    if z_min <= start + 2.0 * RIB_BLEND_R and z_max >= end - 2.0 * RIB_BLEND_R:
                        covered_runs.add(index)
        if radius is not None:
            if not math.isfinite(radius) or not math.isclose(
                radius, RIB_BLEND_R, abs_tol=1e-5
            ):
                raise RuntimeError(
                    f"{name}: native root radius {radius} is not R{RIB_BLEND_R}"
                )
            count += 1
    if count < minimum_faces:
        raise RuntimeError(
            f"{name}: only {count} native R{RIB_BLEND_R} root surfaces "
            f"for {minimum_faces} selected reentrant roots"
        )
    if underside and covered_runs != set(range(len(runs))):
        raise RuntimeError(f"{name}: missing native longitudinal blend run: {sorted(covered_runs)}")


async def _rib_root_fillets(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Bounded R.040 roots with no tangent propagation or geometry fallback."""
    for name, picks, edge_length_bound in rib_root_edge_families():
        before = await _measured_volume(adapter, f"before {name}")
        check(
            f"{name}: selected concave roots R{RIB_BLEND_R}, reach {RIB_REACH}",
            await adapter.add_fillet(RIB_BLEND_R, picks, propagate=False),
        )
        name_last_feature(adapter, name)
        dimension_name = "RibRootRadius" if name == "RibRootFillets" else f"{name}Radius"
        [radius] = name_dimensions(adapter, name, [dimension_name])
        drive_jobs.append((radius, '"RibBlendR"'))
        after = await _measured_volume(adapter, f"after {name}")
        addition = after - before
        upper_bound = 2.0 * RIB_BLEND_R**2 * edge_length_bound
        if not 0.0 < addition <= upper_bound:
            raise RuntimeError(
                f"{name}: native concave roots added {addition:.6f} mm^3, "
                f"outside (0, {upper_bound:.6f}]; no redesign/fallback allowed"
            )
        _assert_root_feature_bounds(adapter, name, len(picks))
        _telemetry.success(
            f"{name}: bounded native R.040 roots added {addition:.6f} mm^3"
        )


def _rib_radius_max_limits(adapter) -> None:
    """Band every modeled rib blend under the title-block R.040 MAX ceiling.

    Profile blends, perpendicular rib-side roots and the changed longitudinal
    coefficient underside remain native controls without a duplicate drawing
    callout. Unchanged body junctions are not given a modeled-fillet claim.
    """
    owners = [
        (f"{stem}Profile", f"{stem}{side}BlendR")
        for stem in ("EdgeRibFront", "EdgeRibBack", "MiddleRib")
        for side in ("Upper", "Lower")
    ]
    owners += [
        (name, "RibRootRadius" if name == "RibRootFillets" else f"{name}Radius")
        for name, _, _ in rib_root_edge_families()
    ]
    lower, upper = deviations(RIB_BLEND_R_BAND)
    for feature, name in owners:
        _, dimension = _named_dimension(adapter, feature, name)
        if not math.isclose(float(dimension.SystemValue) * 1000.0, RIB_BLEND_R, abs_tol=1e-6):
            raise RuntimeError(f"{name}@{feature}: native blend radius changed")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = RIB_BLEND_R_TOL_TYPE
        if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
            raise RuntimeError(f"{name}@{feature}: R.040 MAX limits refused")
        if (
            int(tolerance.Type) != RIB_BLEND_R_TOL_TYPE
            or abs(float(tolerance.GetMinValue()) - lower / 1000.0) > 1e-12
            or abs(float(tolerance.GetMaxValue()) - upper / 1000.0) > 1e-12
        ):
            raise RuntimeError(f"{name}@{feature}: R.040 MAX limits did not persist")
        set_dimension_display_precision(adapter, feature, name, RIB_BLEND_R_PLACES)


async def _counter_anchor_tap(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 8: the native through tap down the summation-anchor boss -- the
    seat the purchased sm-vn-counter-spring anchor (McMaster 9490T1, ``sm-vn-boss-hook``)
    threads straight into. NO NUT: this tap is the nut, so its size is the
    anchor's own thread (``COUNTER_HOLE_SPEC``) and the anchor's trimmed shank
    equals the boss height it engages (``ANCHOR_H``, one spec constant).

    Authored LAST, after every rib: the middle rib's -X vertex lands on this
    station, and a rib extruded after the cut would refill it (the same trap
    the +X hole column hit -- see RIB_REACH). Ordering it here also
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
    """Author ordinary blind-tap limits on the Wizard-owned source dimensions.

    Uniform rib thicknesses are already named and driven by the shared RibT.
    The deeper pilot is backed by the coefficient plate, not by rib depth.
    """
    from _com import _com_invoke, _early_bound
    from _dimensions import _feature_display_dimensions
    from _drawing_marks import _feature_tree
    from magnifying_bracket_joint_layout import THREAD_DEPTH

    model = _early_bound(adapter.currentModel, "IPartDoc")
    feature = _early_bound(model.FeatureByName("BracketMountingTaps"), "IFeature")
    # name -> (nominal mm, (lower, upper) mm, display places)
    required = {
        "FullThreadDepth": (
            THREAD_DEPTH, (-THREAD_DEPTH_BAND, THREAD_DEPTH_BAND), RECEIVER_HOLE_PLACES
        ),
        "TapDrillDepth": (
            DRILL_DEPTH, (-DRILL_DEPTH_BAND, DRILL_DEPTH_BAND),
            RECEIVER_DRILL_DEPTH_PLACES,
        ),
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
            for name, (nominal, _band, _places) in required.items():
                if abs(value_mm - nominal) < 1e-5:
                    matches[name].append((owner, parts[0], display, dimension))
    # Native shape (farm, 2026-10-09): Hole Wizard owns the tap drill depth on
    # one sketch subfeature, but adds one cosmetic-thread subfeature PER HOLE,
    # each owning its own full-thread depth.
    expected = {"FullThreadDepth": len(LEVER_HOLE_POINTS), "TapDrillDepth": 1}
    for name, (_nominal, limits, places) in required.items():
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
                display, dimension, limits, f"{native_name}@{owner}", places=places
            )


def _band_held_dimension(
    display, dimension, deviations: tuple[float, float], label: str, *, places: int
) -> None:
    """(lower, upper) tolerance in mm + ``places`` display on an already-resolved
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
    _set_tolerance_precision(
        display, (lower, upper), display_unit=UNIT, label=label,
        places=places,
    )
    display = _early_bound(display, "IDisplayDimension")
    do_not_change = -1  # swDimensionPrecisionSettings_e
    display.SetPrecision3(places, do_not_change, do_not_change, do_not_change)
    if int(display.GetPrimaryPrecision2()) != places:
        raise RuntimeError(f"{label}: display precision did not persist")
    _telemetry.success(
        f"toleranced {label}: {upper:+g}/{lower:+g} mm ({places} decimals)"
    )


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
    # In the Front-plane model, put text up-right of the +X shoulder in
    # the exterior wedge. Back-derived Detail D mirrors this upper-left.
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
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # The knife-edge controls the free-rock check assumes (code review C09):
    # the ridge from each side face and the flank-to-side angle carry their
    # own tolerances; the vertex height the title block's .XXX (the envelope's
    # places are DRAWING_PRECISION's).
    set_dimension_display_precision(adapter, "KnifeEnvelopeReference", "FlankToSide", 1)
    for name in ("RidgeFromLeft", "RidgeFromRight"):
        set_dimension_symmetric_tolerance(
            adapter, "KnifeEnvelopeReference", name, RIDGE_FROM_SIDE_TOL,
            places=KNIFE_ENVELOPE_PLACES, display_unit=UNIT,
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
    """Native coordinates from the real free edge and fixed plate top.

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
    corner = (PLATE_W, COEFFICIENT_TOP_Y)
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
            adapter, "ReceiverCoordinates", name, POSITION_BAND,
            places=RECEIVER_COORDINATE_PLACES, display_unit=UNIT,
        )
        set_dimension_display_precision(
            adapter, "ReceiverCoordinates", name, RECEIVER_COORDINATE_PLACES
        )
    mark_dimensions_for_drawing(adapter, "ReceiverCoordinates", names)
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "ReceiverCoordinates", "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("cannot hide receiver coordinate sketch")
    model.BlankSketch()
    model.ClearSelection2(True)


# The globals the spring row's drives read, as ``build`` sets them (mm).
SPRING_ROW_GLOBALS_MM = {
    "PlateL": PLATE_L,
    "HexDepth": HEX_DEPTH,
    "HoleX": HOLE_X,
    "ChannelZ0": CHANNEL_Z0,
    "ChannelPitch": CHANNEL_PITCH,
    "HoleZOffset": HOLE_Z_OFFSET,
}


def _evaluate_drive(expression: str, values: dict[str, float]) -> float:
    """An equation-manager expression (arithmetic over quoted globals)."""
    python = re.sub(r'"([^"]+)"', lambda name: f"({values[name.group(1)]!r})", expression)
    return float(eval(python, {"__builtins__": {}}))


def _assert_spring_row_equations(adapter, drives: list[tuple[str, str]]) -> None:
    """Native readback of the spring row's drive equations after a rebuild.

    Each drive is in the equation manager with its recorded expression; that
    expression over the model's own global values is the equation's value
    (every expression is first-degree in length, so the manager's display
    unit cancels); the dimension's SystemValue is the expression over the
    built globals; and the pitch is the live pattern's spacing."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    manager = _early_bound(model.GetEquationMgr(), "IEquationMgr")
    rows: dict[str, tuple[int, str]] = {}
    for index in range(int(_read_member(manager, "GetCount") or 0)):
        left, _, right = str(manager.Equation(index) or "").partition("=")
        rows[left.strip().strip('"')] = (index, "".join(right.split()))

    def value(name: str) -> float:
        if name not in rows:
            raise RuntimeError(f"no equation drives {name}")
        index = rows[name][0]
        evaluated = float(manager.Value(index))
        if int(manager.Status) != index:
            raise RuntimeError(f"equation for {name} does not evaluate")
        return evaluated

    model_globals = {name: value(name) for name in SPRING_ROW_GLOBALS_MM}
    system_mm: dict[str, float] = {}
    for dim_name, expression in drives:
        native = value(dim_name)
        if rows[dim_name][1] != "".join(expression.split()):
            raise RuntimeError(f"{dim_name}: equation reads {rows[dim_name][1]!r}")
        from_globals = _evaluate_drive(expression, model_globals)
        if not math.isclose(from_globals, native, rel_tol=1e-6, abs_tol=1e-9):
            raise RuntimeError(
                f"{dim_name}: {expression} over the model globals is "
                f"{from_globals!r}, its equation evaluates {native!r}"
            )
        leaf, _, owner = dim_name.partition("@")
        _, dimension = _named_dimension(adapter, owner, leaf)
        system_mm[leaf] = float(dimension.SystemValue) * 1000.0
        expected = _evaluate_drive(expression, SPRING_ROW_GLOBALS_MM)
        if not math.isclose(system_mm[leaf], expected, abs_tol=1e-6):
            raise RuntimeError(
                f"{dim_name}: SystemValue {system_mm[leaf]!r} mm, its "
                f"expression {expression} evaluates {expected!r} mm"
            )
    pattern = _early_bound(model.FeatureByName("SpringHolePattern"), "IFeature")
    spacing = float(_early_bound(pattern.Parameter("D3"), "IDimension").SystemValue)
    if not math.isclose(system_mm["SpringPitch"], spacing * 1000.0, abs_tol=1e-6):
        raise RuntimeError(
            f"SpringPitch {system_mm['SpringPitch']!r} mm is not the pattern's "
            f"spacing {spacing * 1000.0!r} mm"
        )
    _telemetry.success(f"spring-row locators equation-driven: {system_mm}")


async def _spring_row_coordinates(adapter) -> None:
    """Native BASIC locators of the 20X spring-tap pattern for the plan.

    Row X runs from datum A's -Z ridge axis, start Z from the +Z plate end
    (datum B) and the pitch between the first two stations, each to a hole
    centre.  As in ``_receiver_coordinate_dimensions``, every end is the start
    of a short construction mark lying on ink the plan prints anyway: on the
    ridge centreline beyond the -Z stub, along the +Z end edge, and along each
    tap's row inside its drill.  The part owns their BASIC type, four places
    and the 19X count (rule 3); the sketch is saved hidden and the plan shows
    it (``_drawing_hidden_sketches``).  The locators and the plate-end and
    ridge stations they run from are driven by the pattern's own expressions
    (``SPRING_*_EXPR``), so an Equations edit moves holes and locators
    together.  The Top-plane sketch maps world Z to -sketchY."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    check("spring-row coordinate sketch", await adapter.create_sketch("Top"))
    dimensions = SketchDims()
    ridge = (0.0, PLATE_L / 2.0 + 0.3 * HEX_DEPTH)
    end = (SPRING_ROW_END_MARK_X, -PLATE_L / 2.0)
    seed = (HOLE_X, -HOLE_Z_LAST)
    second = (HOLE_X, -(HOLE_Z_LAST - CHANNEL_PITCH))
    set_sketch_direct_db(adapter, True)
    ridge_mark = check(
        "spring-row ridge mark",
        await adapter.add_line(*ridge, ridge[0], ridge[1] + SPRING_ROW_MARK),
    )
    end_mark = check(
        "spring-row end mark",
        await adapter.add_line(*end, end[0] + SPRING_ROW_MARK, end[1]),
    )
    seed_mark = check(
        "spring-row seed mark",
        await adapter.add_line(*seed, seed[0] + SPRING_ROW_TAP_MARK, seed[1]),
    )
    second_mark = check(
        "spring-row second mark",
        await adapter.add_line(*second, second[0] + SPRING_ROW_TAP_MARK, second[1]),
    )
    set_sketch_direct_db(adapter, False)
    for mark in (ridge_mark, end_mark, seed_mark, second_mark):
        _as_construction(adapter, mark)
    check(
        "spring-row ridge mark vertical",
        await adapter.add_sketch_constraint(ridge_mark, None, "vertical"),
    )
    await dimension_between(
        adapter, f"{ridge_mark}.start", f"{ridge_mark}.end", "vertical_distance",
        SPRING_ROW_MARK, "spring-row ridge mark length",
    )
    dimensions.record("SpringRowRidgeMark", None)
    await anchor_point_to_origin(
        adapter, f"{ridge_mark}.start", *ridge, "spring-row ridge station"
    )
    dimensions.record("SpringRowRidgeZ", '"PlateL" / 2 + 0.3 * "HexDepth"')
    check(
        "spring-row end mark horizontal",
        await adapter.add_sketch_constraint(end_mark, None, "horizontal"),
    )
    await dimension_between(
        adapter, f"{end_mark}.start", f"{end_mark}.end", "horizontal_distance",
        SPRING_ROW_MARK, "spring-row end mark length",
    )
    dimensions.record("SpringRowEndMark", None)
    await anchor_point_to_origin(
        adapter, f"{end_mark}.start", *end, "spring-row plate end"
    )
    dimensions.record("SpringRowEndX", None)
    dimensions.record("SpringRowEndZ", '"PlateL" / 2')
    for label, mark in (("seed", seed_mark), ("second", second_mark)):
        check(
            f"spring-row {label} mark horizontal",
            await adapter.add_sketch_constraint(mark, None, "horizontal"),
        )
        await dimension_between(
            adapter, f"{mark}.start", f"{mark}.end", "horizontal_distance",
            SPRING_ROW_TAP_MARK, f"spring-row {label} mark length",
        )
        dimensions.record(f"SpringRow{label.title()}Mark", None)
    await dimension_between(
        adapter, f"{ridge_mark}.start", f"{seed_mark}.start", "horizontal_distance",
        HOLE_X, "spring-hole row X",
    )
    dimensions.record("SpringRowX", SPRING_ROW_X_EXPR)
    await dimension_between(
        adapter, f"{end_mark}.start", f"{seed_mark}.start", "vertical_distance",
        HOLE_END_OFFSET_LAST, "spring-hole start Z",
    )
    dimensions.record("SpringStartZ", f'"PlateL" / 2 - ({SPRING_SEED_STATION_EXPR})')
    check(
        "spring-row second station on the row",
        await adapter.add_sketch_constraint(
            f"{seed_mark}.start", f"{second_mark}.start", "vertical_points"
        ),
    )
    await dimension_between(
        adapter, f"{seed_mark}.start", f"{second_mark}.start", "vertical_distance",
        CHANNEL_PITCH, "spring-hole pitch",
    )
    dimensions.record("SpringPitch", SPRING_PITCH_EXPR)
    await ensure_fully_defined(adapter, "spring-row coordinate sketch")
    check("exit spring-row coordinate sketch", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringRowCoordinates")
    drives = dimensions.apply(adapter, "SpringRowCoordinates")
    for dim_name, expr in drives:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    _assert_spring_row_equations(adapter, drives)
    for name in SPRING_ROW_LOCATORS:
        set_dimension_basic_tolerance(adapter, "SpringRowCoordinates", name)
        set_dimension_display_precision(
            adapter, "SpringRowCoordinates", name, BASIC_PLACES
        )
    # Twenty taps are nineteen pitches: the count is the pitch's own prefix.
    set_dimension_prefix(
        adapter, "SpringRowCoordinates", "SpringPitch", f"{HOLE_COUNT - 1}X "
    )
    mark_dimensions_for_drawing(adapter, "SpringRowCoordinates", SPRING_ROW_LOCATORS)
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "SpringRowCoordinates", "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("cannot hide spring-row coordinate sketch")
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
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs: named globals in the equation manager that drive every
    # sketch dim below (a GUI fine-tune edits THESE -- Tools > Equations -- never
    # an auto "D3@Sketch5"). Every length carries an explicit ``mm`` unit: this is
    # an INCH document and the equation manager evaluates BARE numbers in document
    # units, so an unsuffixed "152.4" would read as 152.4 inches and blow the part
    # up 25.4x. Derived globals reference defining dimensions so a primitive
    # edit propagates through tangent constraints and feature depth equations.
    # HexDepth drives the knife prism's length and the stub reference.
    await set_global(adapter, "PlateW", f"{PLATE_W}mm")
    await set_global(adapter, "PlateL", f"{PLATE_L}mm")
    await set_global(adapter, "CounterWebT", f"{COUNTER_WEB_T}mm")
    await set_global(adapter, "CoefficientT", f"{COEFFICIENT_T}mm")
    await set_global(adapter, "CoefficientTopY", f"{COEFFICIENT_TOP_Y}mm")
    await set_global(adapter, "CylR", f"{CYL_R}mm")
    await set_global(adapter, "RibT", f"{RIB_T}mm")
    await set_global(adapter, "RibBlendR", f"{RIB_BLEND_R}mm")
    await set_global(adapter, "RibPad", f"{RIB_PAD}mm")
    await set_global(adapter, "SumH", f"{SUM_H}mm")
    await set_global(adapter, "AnchorR", f"{ANCHOR_R}mm")
    await set_global(adapter, "AnchorH", f"{ANCHOR_H}mm")
    # (The old HoleDia/AnchorBoreR knobs are gone: both anchor seats are native
    # Hole Wizard taps -- a #6-32 seed + linear pattern on the plate and one
    # #10-24 through the boss -- sized by the tap standard from the purchased
    # anchors' own threads, so a diameter knob would be a second, lying source.
    # HoleX stays -- it places the seed -- and the three station globals
    # drive the seed while ChannelPitch also drives the pattern spacing.)
    await set_global(adapter, "HoleX", f"{HOLE_X}mm")
    await set_global(adapter, "ChannelZ0", f"{CHANNEL_Z0}mm")
    await set_global(adapter, "ChannelPitch", f"{CHANNEL_PITCH}mm")
    await set_global(adapter, "HoleZOffset", f"{HOLE_Z_OFFSET}mm")
    await set_global(adapter, "HexW", f"{HEX_W}mm")
    await set_global(adapter, "HexH", f"{HEX_H}mm")
    await set_global(adapter, "HexDepth", f"{HEX_DEPTH}mm")
    await set_global(adapter, "KnifeRidgeR", f"{KNIFE_RIDGE_R}mm")
    await set_global(adapter, "ArcR", '"CylR" + "RibPad"')
    # On its printed 1.41 grid (rule 3), not offset from the hole column.
    await set_global(adapter, "RibReach", f"{RIB_REACH}mm")
    await set_global(adapter, "CoefficientBottomY", '"CoefficientTopY" - "CoefficientT"')

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
    _assert_receiver_profile_walls(adapter)
    await _summation_plate(adapter, drive_jobs)
    await _summation_anchor(adapter, drive_jobs)
    await _middle_rib(adapter, drive_jobs)
    await _rib_root_fillets(adapter, drive_jobs)
    await _counter_anchor_tap(adapter, drive_jobs)
    await _bracket_mounting_taps(adapter)
    await _knife_envelope_reference(adapter, drive_jobs)
    await _cylinder_reference(adapter, drive_jobs)
    await _knife_stub_reference(adapter, drive_jobs)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move; the neutrality re-check is the proof.
    # Component increments have analytic gates; the complete organic solid
    # including native corner patches uses measured as-built neutrality.
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
    _assert_coefficient_slab(adapter)
    _assert_boss_face_graph(adapter)
    for stem in ("EdgeRibFront", "EdgeRibBack", "MiddleRib"):
        _assert_native_rib_profile(adapter, stem)

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
    _knife_ridge_max_limit(adapter)
    _rib_radius_max_limits(adapter)
    _receiver_model_bands(adapter)
    await _receiver_coordinate_dimensions(adapter)
    await _spring_row_coordinates(adapter)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Back View Note": BACK_VIEW_NOTE,
            "Front View Note": FRONT_VIEW_NOTE,
            "Receiver Isometric View Note": RECEIVER_ISOMETRIC_VIEW_NOTE,
        },
    )
    # Native dimension metadata must not erase the already-verified blind taps.
    await force_rebuild(adapter)
    await volume_check(
        adapter, "summing lever after native receiver bands", v_built, 1e-5 * v_built
    )
    _assert_edge_rib_end_planes(adapter)
    for name, picks, _ in rib_root_edge_families():
        _assert_root_feature_bounds(adapter, name, len(picks))
    name_octant_views(
        adapter,
        octants={"REAR-BOTTOM-RIGHT": RECEIVER_ISOMETRIC_OCTANT},
        label=PART_NAME,
    )
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
            "Receiver Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
