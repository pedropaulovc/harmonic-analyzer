r"""Reproduction script: summing lever (book ch. 18, pp. 42-43).

The cast-iron lever that sums the pull of the 20 channel springs and balances
them against the master (counter) spring -- a FIRST-CLASS LEVER hung in
suspension on a knife edge.

PROVENANCE: the 2026-06-16 reconstruction superseded the M6.4 "knife-edge
tube + Ø14 bore" model. Historical .cs/KCL geometry records that reconstruction,
not the current design authority: the shared spec and owner decisions govern.
Two corrections established the solid pivot and knife-edge trunnions:

* The real lever has **NO bore** -- the M6.4 bored tube was wrong. The .cs
  solid pivot cylinder is correct.
* The .cs was **missing the two hexagonal protrusions at the pivot** that form
  the **knife edge** the lever hangs/rocks on. They are added here (``_hex_knife_
  edges``); exact size/clocking is LOW confidence (museum-glass photos:
  references/.../ch18_images/page001_img0{1,3}, photogrammetry 194637152 /
  194651412) and is tuned against the knife-mount fit + ch30 parity.

Seven principal features:

1. Coefficients plate  -- uniform 7 mm positive-X slab centred at local Y0,
   with faces Y±3.50, matching the centred 7 mm negative-X counter web
   (owner decision #2129). The knife-edge trunnions remain unchanged. The
   body runs from local Z -82.55 to +76.20: the -Z end is extended .25 in
   (owner ruling 4, #1038); the origin, boss and middle rib stay.
2. Pivot cylinder      -- Front-plane solid circle at the origin, extruded
   between the body ends along the long edge (the pivot/rock axis = local Z).
3. Hex knife edges     -- ONE vertex-up hexagonal prism through the pivot,
   extruded out past both body ends: the two trunnion stubs it
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
(-15, 979.6932, 0), so local axes ARE machine axes: +X = the channel-spring
(coefficients-plate) arm (machine west), -X = the counter-spring
(summation-anchor) arm (machine east), +Y up, +Z along the knife edge
(channel direction). The spring-hole X/Z stations remain registered; their
entry face follows the centred coefficient top. The summation anchor lands
where the counter-spring boss-hook attaches (local x -76 -> machine -91).

Sketches follow the repo fully-defined convention (cad/scripts/_sketch.py).
The common rib profile has native tangent constraints, defining dimensions,
face/profile readback and exact incremental-volume gates. Bounded internal
root fillets are selected explicitly and cannot grow into the spring-anchor lane.

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
    DRAWING_NOTES,
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
    COUNTER_FLANK_ANGLE_DEG,
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
    HEX_Z_OUTER_MINUS,
    HEX_Z_OUTER_PLUS,
    KNIFE_SEAT_Z_MINUS,
    KNIFE_SEAT_Z_PLUS,
    KNIFE_FLANK_TO_SIDE_TOL_DEG,
    KNIFE_ENVELOPE_PLACES,
    KNIFE_RIDGE_R,
    KNIFE_RIDGE_R_BAND,
    KNIFE_RIDGE_R_PLACES,
    KNIFE_RIDGE_R_TOL_TYPE,
    PLATE_L,
    PLATE_W_DEVIATIONS,
    PLATE_Z_MINUS,
    PLATE_Z_PLUS,
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

# The historical reconstruction's X direction is opposite the installed
# coefficient arm. SX preserves that registration, not a .cs design authority.
SX = -1.0

# --- retained reconstruction dimensions (inches -> mm) ---------------------
PLATE_W = 1.75 * IN  # coefficients plate width (along the arm, X)   44.45
# The shared spec owns both centred 7 mm sections and their real face levels.
CYL_R = 0.5 * IN  # pivot cylinder radius                          12.70
RIB_PAD = 0.1 * IN  # rib arc padding over the cylinder              2.54
SUM_H = 3.0 * IN  # summation plate height (tip reach)             76.20
SUM_CURV = 0.3 * IN  # summation plate side curvature                7.62
ANCHOR_R = 0.375 * IN  # summation anchor outer radius               9.525
# ANCHOR_H (19.05, the boss height and the counter anchor's engagement) is the
# pure spec's -- build_sm_vn_boss_hook trims the purchased shank to it.

# --- hex knife-edge protrusions (NEW; LOW confidence -- tune vs ch30) -------
# TWO trunnion stubs, one PROTRUDING BEYOND each body end (not flush inside):
# the lever's pivot overhangs the body so the knife edges rest on bearing
# supports standing on the top plate (ch30-p003). Each stub's top vertex line
# is the knife edge the lever is suspended/rocks on.
# Knife-edge trunnion cross-section: vertex-up hex, 8.080 wide (X) x 10.268 tall
# (Y, vertex to vertex) x 21.717 deep (Z protrusion). The top vertex ridge is
# the knife edge (= the rock axis, above the cylinder centreline).
# Both stubs are one prism (``_hex_knife``): one sketch extruded through the
# body from HEX_Z_OUTER_MINUS to HEX_Z_OUTER_PLUS.  Every vertex lies inside
# the solid pivot cylinder (circumradius HEX_H/2 < CYL_R), so between the body
# ends the prism merges into it and the solid is the two stubs' alone.
HEX_W = 8.080  # across-flats width (X); = sm_summing_lever_spec.HEX_W
HEX_H = 10.268  # vertex-to-vertex height (Y) -- vertex-up
HEX_DEPTH = 21.717  # axial length each stub protrudes past the body end
if not HEX_H / 2.0 < CYL_R:
    raise AssertionError("the knife prism must lie inside the pivot cylinder")
# The readback (``_assert_knife_sides_coplanar``) holds each lateral face of
# one stub and its twin on the other to one plane: unit-normal components
# and plane offset (metres, the API's unit) within KNIFE_SIDE_PLANE_TOL.
KNIFE_SIDE_PLANE_TOL = 1e-6
KNIFE_LATERAL_FACES = 6  # per stub: two flanks, two sides, two lower faces

# --- derived ---------------------------------------------------------------
TIP_X = SX * SUM_H  # summation tip / anchor x (counter-spring arm) -76.20


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


def _summation_side_points() -> dict[float, tuple[tuple[float, float], ...]]:
    """Each counter-web side arc as world (x, z): base end, interior, boss end.

    The +Z arc is the retained reconstruction's (through its historical
    interior point).  The -Z arc runs from the extended front body end
    (#1038) to the boss's other quadrant at the SAME radius, bowed towards the
    counter axis like its twin, so the print's one "2X R" sizes both.
    """
    plus = (
        (0.0, PLATE_Z_PLUS),
        (SX * SUM_H / 2.0, PLATE_Z_PLUS / 2.0 - SUM_CURV),
        (TIP_X, ANCHOR_R),
    )
    cx, cz = _circumcenter(*plus)
    radius = math.hypot(plus[0][0] - cx, plus[0][1] - cz)
    start, end = (0.0, PLATE_Z_MINUS), (TIP_X, -ANCHOR_R)
    chord = math.dist(start, end)
    ux, uz = (end[0] - start[0]) / chord, (end[1] - start[1]) / chord
    rise = math.sqrt(radius**2 - (chord / 2.0) ** 2)
    mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    # The centre lies beyond the chord from the counter axis (more -Z, -X).
    centre = (mid[0] - uz * rise, mid[1] + ux * rise)
    if not (centre[1] < mid[1] and centre[0] < mid[0]):
        raise AssertionError("the -Z web arc's centre is on the wrong side")
    interior = (
        centre[0] + (mid[0] - centre[0]) * radius / rise,
        centre[1] + (mid[1] - centre[1]) * radius / rise,
    )
    return {1.0: plus, -1.0: (start, interior, end)}


# The counter web's side arcs, keyed by their Z side.
SUMMATION_SIDE_POINTS = _summation_side_points()
ARC_R = RIB_WRAP_R
# Each edge rib's inner cap; the outside caps are the body ends.
RIB_INNER_Z_PLUS = PLATE_Z_PLUS - RIB_T  # +71.12
RIB_INNER_Z_MINUS = PLATE_Z_MINUS + RIB_T  # -77.47
# No plain anchor bore: the counter anchor's seat is the native COUNTER_HOLE_SPEC
# tap through the boss, authored after the ribs (see _counter_anchor_tap).
# In X, all ribs stop at 35.814 (1.41) before the unchanged spring-hole column
# and the worst protruding anchor-shank footprint at 37.970. The pilot
# continues beyond the 5.08 mm entry rib into the connected coefficient plate,
# not an enlarged receiver.
# The shared positive-X branch meets both plate faces with R.040 tangent
# transitions, with no separate pad, ledge or vertical tip face.
if RIB_REACH > HOLE_X - blind_cut_dia_mm(HOLE_SPEC) / 2.0 - 2.0:
    raise AssertionError("a rib's +X end reaches the spring-hole column")

# Receiver-coordinate marks (``_receiver_coordinate_dimensions``): short
# construction lines whose ends carry the bracket-tap coordinates.  The edge
# mark lies on the free edge below its actual top corner; each tap mark lies
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
    """Centred real seats and persistent extrusion dimensions after rebuild."""
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


def _assert_z_end_planes(
    adapter, name: str, required: tuple[float, ...], allowed: tuple[float, ...] = ()
) -> None:
    """Read ``name``'s planar caps normal to Z: every ``required`` station is
    one, and no cap stands anywhere else (``allowed`` adds coplanar stations
    an earlier feature may own).  The body is not symmetric about the Front
    plane (owner ruling 4, #1038), so its volume no longer shows which side
    of that plane an offset boss went: these planes do."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    raw = model.FeatureByName(name)
    if raw is None:
        raise RuntimeError(f"{name}: missing native feature")
    planes: list[float] = []
    for raw_face in _early_bound(raw, "IFeature").GetFaces() or ():
        surface = _early_bound(_early_bound(raw_face, "IFace2").GetSurface(), "ISurface")
        if surface is None or not surface.IsPlane():
            continue
        values = tuple(float(value) for value in surface.PlaneParams)
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            raise RuntimeError(f"{name}: invalid native plane parameters {values}")
        if abs(abs(values[2]) - 1.0) < 1e-7:
            planes.append(values[5] * 1000.0)
    if not all(
        any(abs(z - station) <= 1e-5 for z in planes) for station in required
    ) or any(
        min(abs(z - station) for station in (*required, *allowed)) > 1e-5
        for z in planes
    ):
        raise RuntimeError(
            f"{name}: native Z caps {sorted(planes)} mm are not {required} mm"
        )
    _telemetry.success(f"{name}: native Z caps {sorted(planes)} mm")


def _assert_boss_face_graph(adapter) -> None:
    """Prove both centred plate/web faces and the unchanged boss envelope.

    Both 7 mm sections meet at Y±3.50. The boss remains centred at Y0 with
    its own ANCHOR_H span; neither the boss nor knife trunnions follow a face.
    """
    model = _early_bound(adapter.currentModel, "IPartDoc")
    for owner, expected in (
        ("SummationAnchor", (-ANCHOR_H / 2.0, ANCHOR_H / 2.0)),
        ("SummationPlate", (-COUNTER_WEB_T / 2.0, COUNTER_WEB_T / 2.0)),
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
        f"{ANCHOR_H / 2.0 - COEFFICIENT_TOP_Y:.6f} mm; both counterweb faces flush"
    )


async def _coefficients_plate(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Feature 1: uniform coefficient slab centred on Y0, with faces Y±3.50.

    The HOLE_COUNT spring holes are ONE seed cut at station j=HOLE_COUNT-1
    plus a native FeatureLinearPattern5 marching at CHANNEL_PITCH down -Z.
    (An early pattern attempt marched along an AUTO-selected plate edge whose
    natural sense silently reversed the field off the -Z plate edge -- only
    j=0 stayed cut -- and was replaced by cutting all 20 stations outright in
    one sketch. The pattern is back with the sense guarded, not
    inference-trusted: a deliberate direction-edge pick whose -Z natural sense
    is MEASURED, the seed at the +Z end of the span so a reversal marches off
    the plate, and an analytic volume gate that resolves a single missing
    hole.)

    Assembly placement retains the knife registration; the spring entry Y
    follows COEFFICIENT_TOP_Y, not a historical fixed-top convention."""
    from solidworks_mcp.adapters.base import LinearPatternParameters

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
    # One blind boss from the -Z body end to datum B: a negative start offset
    # is behind the Front plane and the boss runs along +Z (the edge ribs'
    # ``flip=False`` sense), so PlateLength stays one native end-to-end depth.
    extrude_at_offset(adapter, PLATE_L, PLATE_Z_MINUS)
    name_last_feature(adapter, "CoefficientsPlate")
    _assert_z_end_planes(adapter, "CoefficientsPlate", (PLATE_Z_MINUS, PLATE_Z_PLUS))
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
    """Feature 2: Front-plane solid circle at origin, extruded between the body
    ends along the long edge -- the pivot/rock axis (local Z). NO bore."""

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
    extrude_at_offset(adapter, PLATE_L, PLATE_Z_MINUS)
    name_last_feature(adapter, "PivotCylinder")
    _assert_z_end_planes(
        adapter, "PivotCylinder", (), allowed=(PLATE_Z_MINUS, PLATE_Z_PLUS)
    )


async def _hex_knife(adapter, drive_jobs: list[tuple[str, str]]) -> None:
    """Both hexagonal knife-edge trunnion stubs as ONE prism: a Front-plane
    vertex-up hexagon (HEX_W x HEX_H bounding box) centred on the pivot axis,
    a vertex at the top (the knife edge runs along Z at that top vertex
    line), extruded from HEX_Z_OUTER_MINUS to HEX_Z_OUTER_PLUS.  Inside the body
    it merges into the solid pivot cylinder; past each body end it is a stub,
    the overhang the knife edge rests on a bearing support with.

    One sketch and one extrude, so each side face, flank and lower face of
    the +Z stub lies in the same plane as its -Z twin by construction (code
    review C09): the symmetry Detail D prints for each stub then holds the two
    ridges to each other (``sm_summing_lever_spec.KNIFE_STUB_RIDGE_OFFSET_MAX``).
    ``_assert_knife_sides_coplanar`` reads that back."""
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
    extrude_at_offset(adapter, PLATE_L + 2.0 * HEX_DEPTH, HEX_Z_OUTER_MINUS)
    name_last_feature(adapter, stem)
    _assert_z_end_planes(adapter, stem, (HEX_Z_OUTER_MINUS, HEX_Z_OUTER_PLUS))
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
        [0.0, HEX_H / 2.0, seat_z] for seat_z in (KNIFE_SEAT_Z_PLUS, KNIFE_SEAT_Z_MINUS)
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
        "EdgeRibBack": (RIB_INNER_Z_MINUS, PLATE_Z_MINUS, "EdgeRibThickness", RIB_T),
        "EdgeRibFront": (RIB_INNER_Z_PLUS, PLATE_Z_PLUS, "EdgeRibThickness", RIB_T),
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


def _add_driving_counter_angle(adapter, flank: str, baseline: str) -> None:
    """Drive the upper counter tangent from its on-axis construction ray.

    Select two segments, not the adapter's segment/vertex angular route.
    Front-plane sketch/model XY coincide; place text inside the acute wedge
    before making the measured angle driving, never its supplement.
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    half = math.radians(COUNTER_FLANK_ANGLE_DEG / 2.0)
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [flank, baseline], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        TIP_X / 1000.0 + 0.020 * math.cos(half),
        0.020 * math.sin(half), 0.0,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None or int(status) != 0:  # swAddSpecificDimension_Success
        raise RuntimeError(f"counter angle: AddSpecificDimension failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if (
        int(display.Type2) != 3
        or not math.isclose(
            float(dimension.SystemValue), math.radians(COUNTER_FLANK_ANGLE_DEG),
            rel_tol=0.0, abs_tol=1e-10,
        )
    ):
        raise RuntimeError("counter angle: native dimension is not the nominal acute angle")
    dimension.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(dimension.DrivenState) != 2:
        raise RuntimeError("counter angle: native dimension did not become driving")


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
        counter_axis = await line((TIP_X, 0.0), (0.0, 0.0), "counter axis")
        _as_construction(adapter, counter_axis)
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
        check(
            f"{stem} counter axis origin",
            await adapter.add_sketch_constraint(f"{counter_axis}.end", "origin", "coincident"),
        )
        check(
            f"{stem} counter axis horizontal",
            await adapter.add_sketch_constraint(counter_axis, None, "horizontal"),
        )
        _add_driving_counter_angle(adapter, negative_top, counter_axis)
        rib.record(f"{stem}CounterAngle", '"CounterFlankAngle"')
    for index, (first, second) in enumerate(pairs):
        check(
            f"{stem} tangent {index}",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )
    await ensure_fully_defined(adapter, f"{stem} common tangent profile")
    check(f"{stem} exit sketch", await adapter.exit_sketch())
    name_last_feature(adapter, f"{stem}Profile")
    drive_jobs += rib.apply(adapter, f"{stem}Profile")


def _assert_native_rib_profile(adapter, stem: str, *, equation_bound: bool = False) -> None:
    """Prove native flanks/blends and the counter angle's stage-specific state."""
    model = _early_bound(adapter.currentModel, "IPartDoc")
    raw = model.FeatureByName(stem)
    if raw is None:
        raise RuntimeError(f"{stem}: missing native profile feature")
    found_flanks: set[int] = set()
    found_blends: set[int] = set()
    found_counter: set[int] = set()
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
            if stem == "MiddleRib":
                for index, sign in enumerate((1.0, -1.0)):
                    expected = (ARC_R / TIP_X, sign * math.sqrt(1.0 - (ARC_R / TIP_X)**2), 0.0)
                    aligned = abs(sum(a * b for a, b in zip(normal, expected, strict=True)))
                    offset = sum(a * b for a, b in zip(expected, point, strict=True)) * 1000.0
                    if aligned > 1.0 - 1e-8 and abs(offset - ARC_R) < 1e-5:
                        # Plane intersection with y=0, in MILLIMETRES. A
                        # rounded 11.537-degree driver must fail this gate.
                        apex_x = (point[0] + normal[1] * point[1] / normal[0]) * 1000.0
                        if not math.isfinite(apex_x) or abs(apex_x - TIP_X) > 1e-6:
                            raise RuntimeError(f"{stem}: counter apex {apex_x:.9f} mm, expected {TIP_X}")
                        found_counter.add(index)
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
    if stem == "MiddleRib":
        if found_counter != {0, 1}:
            raise RuntimeError(f"{stem}: missing native counter planes {found_counter}")
        raw_dimension = adapter.currentModel.Parameter("MiddleRibCounterAngle@MiddleRibProfile")
        if raw_dimension is None:
            raise RuntimeError(f"{stem}: missing native driving counter angle")
        dimension = _early_bound(raw_dimension, "IDimension")
        # Equation-controlled dimensions report driven (1), not their
        # creation-time driving state (2), as the PlateWidth control confirms.
        expected_state = 1 if equation_bound else 2
        driven_state = int(dimension.DrivenState)
        actual_radians = float(dimension.SystemValue)
        expected_radians = math.radians(COUNTER_FLANK_ANGLE_DEG)
        if (
            driven_state != expected_state
            or not math.isclose(
                actual_radians, expected_radians,
                rel_tol=0.0, abs_tol=1e-10,
            )
        ):
            raise RuntimeError(
                f"{stem}: counter angle {dimension.FullName!r} is not the nominal native driver: "
                f"DrivenState={driven_state!r}, expected={expected_state}; "
                f"SystemValue={actual_radians!r} rad, expected={expected_radians!r} rad; "
                f"delta={actual_radians - expected_radians!r} rad; "
                f"actual_degrees={math.degrees(actual_radians)!r}"
            )
    _telemetry.success(f"{stem}: both native tangent flanks and R.040 profile blends")


async def _edge_rib(
    adapter, flip: bool, name: str, stem: str, drive_jobs: list[tuple[str, str]]
) -> None:
    """The common tangent profile and uniform thickness at either fixed end:
    ``flip`` builds the -Z rib, mirrored about the Front plane."""
    v_before = await _measured_volume(adapter, f"before {stem}")
    await _rib_profile_sketch(adapter, stem, drive_jobs)
    offset = -RIB_INNER_Z_MINUS if flip else RIB_INNER_Z_PLUS
    extrude_at_offset(adapter, RIB_T, offset, flip=flip)
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
    """Feature 5: Top-plane leaf on the -X arm -- vertical base edge (x=0)
    between the body ends, two curved sides of one radius, short tip edge at
    the anchor (x=TIP_X).  The Top-plane sketch maps world Z to -sketchY."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    sd = SketchDims()
    check("create_sketch summation plate", await adapter.create_sketch("Top"))
    p1 = (0.0, -PLATE_Z_PLUS)
    p2 = (0.0, -PLATE_Z_MINUS)
    p3 = (TIP_X, ANCHOR_R)
    p4 = (TIP_X, -ANCHOR_R)
    top_int, bot_int = (
        (SUMMATION_SIDE_POINTS[side][1][0], -SUMMATION_SIDE_POINTS[side][1][1])
        for side in (-1.0, 1.0)
    )

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
    # positive: base start at y=-PLATE_Z_PLUS drives "PlateZPlus"; the tip-end
    # anchor at (TIP_X<0, -ANCHOR_R) drives |TIP_X|="SumH" then "AnchorR". The
    # two arc centres are circumcentre-derived (no clean global), left None.
    check(
        "summation base vertical",
        await adapter.add_sketch_constraint(base, None, "vertical"),
    )
    await anchor_point_to_origin(adapter, f"{base}.start", *p1, "summation base start")
    sd.record("SumBaseStartZ", '"PlateZPlus"')  # vertical_distance = PLATE_Z_PLUS
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
        if not PLATE_Z_MINUS < inner_z < tip_z < PLATE_Z_PLUS:
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
    z = PLATE_Z_MINUS + RIB_T / 2.0
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


def summation_side_z(x: float, side: float) -> float:
    """World Z of the counter web's ``side`` (+1/-1) arc at X."""
    start, interior, end = SUMMATION_SIDE_POINTS[side]
    if not end[0] <= x <= start[0]:
        raise ValueError(f"counter-web side arc does not span X{x}")
    cx, cz = _circumcenter(start, end, interior)
    radius = math.hypot(start[0] - cx, start[1] - cz)
    return cz + math.copysign(math.sqrt(radius**2 - (x - cx) ** 2), interior[1] - cz)


def longitudinal_root_families() -> tuple[tuple[str, float, float], ...]:
    """Name, X side and face level of each plate/web-to-pivot-cylinder junction."""
    return (
        ("CoefficientUndersideRootFillets", 1.0, COEFFICIENT_BOTTOM_Y),
        ("CoefficientTopRootFillets", 1.0, COEFFICIENT_TOP_Y),
        ("CounterWebTopRootFillets", -1.0, COUNTER_WEB_T / 2.0),
        ("CounterWebUndersideRootFillets", -1.0, -COUNTER_WEB_T / 2.0),
    )


def longitudinal_root_geometry(x_sign: float, face_y: float) -> tuple[
    float, tuple[float, float], tuple[float, float], tuple[tuple[float, float], ...]
]:
    """Signed junction X, tangent R.040 cylinder and two inboard edge runs.

    The fillet circle is externally tangent to the pivot cylinder and tangent
    to the plate or web face. Its centre is R beyond that face, at distance
    CylR + R from the pivot axis. Coefficient runs end at the edge-rib caps;
    counter-web runs end where the web's side arc leaves the cylinder.
    Cap-root corner patches get a one-radius neighbourhood in the native
    audit; neither outside body end is selected.
    """
    radius = RIB_BLEND_R
    if (
        not all(math.isfinite(value) for value in (face_y, radius, CYL_R, PLATE_L))
        or not 0.0 < abs(face_y) < CYL_R
        or radius <= 0.0
    ):
        raise ValueError("plate/cylinder blend violates inboard tangent-run premises")
    edge_x = math.copysign(math.sqrt(CYL_R**2 - face_y**2), x_sign)
    ends = (
        (RIB_INNER_Z_MINUS, RIB_INNER_Z_PLUS)
        if x_sign > 0.0
        else (
            max(RIB_INNER_Z_MINUS, summation_side_z(edge_x, -1.0)),
            min(RIB_INNER_Z_PLUS, summation_side_z(edge_x, 1.0)),
        )
    )
    runs = ((ends[0], -RIB_T / 2.0), (RIB_T / 2.0, ends[1]))
    if any(
        not all(math.isfinite(value) for value in (start, stop))
        or not PLATE_Z_MINUS < start - radius < stop + radius < PLATE_Z_PLUS
        or stop - start <= 4.0 * radius
        for start, stop in runs
    ):
        raise ValueError("plate/cylinder blend violates inboard tangent-run premises")
    center_y = face_y + math.copysign(radius, face_y)
    center_x = math.copysign(math.sqrt((CYL_R + radius) ** 2 - center_y**2), x_sign)
    scale = CYL_R / (CYL_R + radius)
    return edge_x, (center_x, center_y), (center_x * scale, center_y * scale), runs


def counter_flank_crease_x() -> float:
    """X where each negative-X middle-rib flank sinks into a counter-web face."""
    crease = TIP_X + COUNTER_WEB_T / 2.0 / math.tan(math.radians(COUNTER_FLANK_ANGLE_DEG))
    if not TIP_X + ANCHOR_R < crease < 0.0:
        raise ValueError(f"counter flank crease X{crease} is not between boss and pivot")
    return crease


def rib_root_edge_families() -> tuple[tuple[str, list[list[float]], float], ...]:
    """Explicit reentrant roots only; never the outside receiver/knife caps.

    The bound is a conservative r² prism around the selected edge lengths,
    including cylindrical curvature and end-corner interactions. It bounds
    actual ADDED native material, not the unfilleted body's bounding box.
    """
    end_caps = (RIB_INNER_Z_MINUS, RIB_INNER_Z_PLUS)
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
    families = [
        ("RibCylinderRootFillets", cylinder_picks, 4.0 * math.tau * CYL_R),
        ("RibCounterRootFillets", counter_picks, 4.0 * SUM_H),
        ("RibRootFillets", plate_picks, 8.0 * RIB_REACH),
    ]
    # Keep the established cap-root operations and their bounds unchanged.
    # Mid-run longitudinal edges survive those rounds; each later operation
    # joins their corner patches without tangent propagation.
    for name, x_sign, face_y in longitudinal_root_families():
        edge_x, _, _, runs = longitudinal_root_geometry(x_sign, face_y)
        families.append((
            name,
            [[edge_x, face_y, (start + end) / 2.0] for start, end in runs],
            sum(end - start for start, end in runs) + 4.0 * RIB_BLEND_R,
        ))
    # The boss rim on both web faces, the web side's two creases into the
    # boss at its Z extremes, and both middle-rib flank creases into the web.
    # The flank stays inside the web wherever it meets the boss.
    crease_x = counter_flank_crease_x()
    web_picks = [[TIP_X + ANCHOR_R, sign * COUNTER_WEB_T / 2.0, 0.0] for sign in (1.0, -1.0)]
    web_picks += [[TIP_X, 0.0, sign * ANCHOR_R] for sign in (1.0, -1.0)]
    web_picks += [[crease_x, sign * COUNTER_WEB_T / 2.0, 0.0] for sign in (1.0, -1.0)]
    families.append((
        "CounterWebJunctionFillets",
        web_picks,
        math.tau * ANCHOR_R + 2.0 * COUNTER_WEB_T + 2.0 * RIB_T + 12.0 * RIB_BLEND_R,
    ))
    # Each web side arc leaving the pivot cylinder, across the web.
    families.append((
        "CounterWebSideRootFillets",
        [[-CYL_R, 0.0, summation_side_z(-CYL_R, sign)] for sign in (1.0, -1.0)],
        2.0 * COUNTER_WEB_T + 8.0 * RIB_BLEND_R,
    ))
    # Both stub roots at the body end faces: two hexagon perimeters plus
    # one-radius corner neighbourhoods.
    families.append((
        "KnifeShoulderFillets",
        knife_shoulder_picks(),
        2.0 * (HEX_H + 4.0 * math.hypot(HEX_W / 2.0, HEX_H / 4.0)) + 14.0 * RIB_BLEND_R,
    ))
    return tuple(families)


def knife_shoulder_picks() -> list[list[float]]:
    """Each stub root's six lateral-face edges and ridge round at the body end."""
    w2, h2, h4 = HEX_W / 2.0, HEX_H / 2.0, HEX_H / 4.0
    half = math.radians(RIDGE_ANGLE_DEG) / 2.0
    crest = h2 - KNIFE_RIDGE_R / math.sin(half) + KNIFE_RIDGE_R
    flank = (h2 + h4) / 2.0
    section = [
        (-w2 / 2.0, flank), (-w2, 0.0), (-w2 / 2.0, -flank),
        (w2 / 2.0, -flank), (w2, 0.0), (w2 / 2.0, flank), (0.0, crest),
    ]
    return [
        [x, y, body_end] for body_end in (PLATE_Z_PLUS, PLATE_Z_MINUS) for x, y in section
    ]


def _assert_root_feature_bounds(adapter, name: str, minimum_faces: int) -> None:
    """Read only new fillet surfaces: bounded reach, entry and radius."""
    raw = _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(name)
    feature = _early_bound(raw, "IFeature")
    count = seen = 0
    knife = name == "KnifeShoulderFillets"
    expected_radius = RIB_BLEND_R
    reach = [0.0, 0.0, 0.0]  # knife roots: max |x|, |y| and |z| measured
    longitudinal = {
        family: (x_sign, face_y) for family, x_sign, face_y in longitudinal_root_families()
    }.get(name)
    # (x, y, z) limits; None leaves an axis to the common reach/entry checks.
    envelope = (None, None, None)
    if longitudinal is not None:
        x_sign, face_y = longitudinal
        _, center, tangent, runs = longitudinal_root_geometry(x_sign, face_y)
        y_sign = math.copysign(1.0, face_y)
        # A finite one-radius cap-corner neighbourhood surrounds the exact
        # straight-run tangent section. This is not an allowance for the
        # cap-root families, whose reach/entry/radius bounds remain unchanged.
        envelope = (
            tuple(sorted((tangent[0] - x_sign * RIB_BLEND_R, center[0] + x_sign * RIB_BLEND_R))),
            tuple(sorted((tangent[1] + y_sign * RIB_BLEND_R, face_y - y_sign * RIB_BLEND_R))),
            None,
        )
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
            envelope[0][1] >= min(receiver_inner_x, PLATE_W, RIB_REACH)
            or not COEFFICIENT_BOTTOM_Y < face_y - y_sign * RIB_BLEND_R < COEFFICIENT_TOP_Y
        ):
            raise RuntimeError(f"{name}: junction envelope reaches a retained interface")
    elif name == "CounterWebJunctionFillets":
        # Outside the boss and its tap, below its top seat, inboard of the pivot.
        envelope = (
            (TIP_X - RIB_BLEND_R, counter_flank_crease_x() + RIB_BLEND_R),
            (-COUNTER_WEB_T / 2.0 - RIB_BLEND_R, COUNTER_WEB_T / 2.0 + RIB_BLEND_R),
            (-ANCHOR_R - RIB_BLEND_R, ANCHOR_R + RIB_BLEND_R),
        )
    elif name == "CounterWebSideRootFillets":
        # Where each side arc leaves the pivot: across the web, within one
        # radius of the cylinder and of the arc (|Z| below).
        envelope = (
            (
                -CYL_R - 2.0 * RIB_BLEND_R,
                -math.sqrt(CYL_R**2 - (COUNTER_WEB_T / 2.0) ** 2) + RIB_BLEND_R,
            ),
            (-COUNTER_WEB_T / 2.0 - RIB_BLEND_R, COUNTER_WEB_T / 2.0 + RIB_BLEND_R),
            None,
        )
        # |Z| band of each side arc's root, keyed by the arc's Z side.
        side_bands = {
            side: (
                abs(summation_side_z(-CYL_R - 2.0 * RIB_BLEND_R, side)),
                abs(summation_side_z(envelope[0][1] - RIB_BLEND_R, side))
                + 2.0 * RIB_BLEND_R,
            )
            for side in (1.0, -1.0)
        }
        covered_sides = set()
    elif knife:
        # Around each hexagon, inside one radius of the body end face. The
        # roots meet mitred at the sharp bottom vertex, R/sin(half angle) out.
        mitre = RIB_BLEND_R / math.sin(math.radians(RIDGE_ANGLE_DEG) / 2.0)
        envelope = (
            (-HEX_W / 2.0 - RIB_BLEND_R, HEX_W / 2.0 + RIB_BLEND_R),
            (-HEX_H / 2.0 - mitre, HEX_H / 2.0 + mitre),
            None,
        )
    for raw_face in feature.GetFaces() or ():
        seen += 1
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        radius = None
        if surface.IsCylinder():
            radius = float(surface.CylinderParams[6]) * 1000.0
        elif surface.IsTorus():
            radius = float(surface.TorusParams[7]) * 1000.0
        # A transition patch can be nonanalytic. It must pass the same exact
        # bounds, but cannot stand in for a proved cylindrical/toroidal radius.
        # IFace2.GetBox is approximate. A temporary, unsaved sheet body of
        # this actual trimmed fillet face gives exact directional extrema,
        # without confusing its envelope with the plate's X44.45 free edge.
        sheet_raw = face.CreateSheetBody()
        if sheet_raw is None:
            raise RuntimeError(f"{name}: cannot extract native root face for exact bounds")
        sheet = _early_bound(sheet_raw, "IBody2")
        extrema = []
        for direction, axis in (
            ((1.0, 0.0, 0.0), 0), ((0.0, 0.0, -1.0), 2), ((0.0, 0.0, 1.0), 2),
            ((-1.0, 0.0, 0.0), 0), ((0.0, -1.0, 0.0), 1), ((0.0, 1.0, 0.0), 1),
        ):
            result = sheet.GetExtremePoint(direction[0], direction[1], direction[2])
            if result is None or len(result) != 4 or not result[0] or not all(
                math.isfinite(float(value)) for value in result[1:]
            ):
                raise RuntimeError(f"{name}: invalid exact native root extreme {result}")
            extrema.append(float(result[axis + 1]) * 1000.0)
        x_max, z_min, z_max, x_min, y_min, y_max = extrema
        if x_max > RIB_REACH + 1e-5:
            raise RuntimeError(
                f"{name}: R{expected_radius} root face grows beyond X{RIB_REACH}: {extrema}"
            )
        if knife:
            near, far = sorted((abs(z_min), abs(z_max)))
            body_end = PLATE_Z_PLUS if z_min > 0.0 else -PLATE_Z_MINUS
            if (
                z_min * z_max <= 0.0 or near < body_end - 1e-5
                or far > body_end + RIB_BLEND_R + 1e-5
            ):
                raise RuntimeError(f"{name}: shoulder blend leaves the stub root: {extrema}")
            reach = [
                max(reach[0], abs(x_min), abs(x_max)), max(reach[1], abs(y_min), abs(y_max)),
                max(reach[2], far - body_end),
            ]
        elif name == "CounterWebSideRootFillets":
            near, far = sorted((abs(z_min), abs(z_max)))
            side_band = side_bands[math.copysign(1.0, z_min)]
            if z_min * z_max <= 0.0 or near < side_band[0] - 1e-5 or far > side_band[1] + 1e-5:
                raise RuntimeError(f"{name}: native face escapes the junction envelope: {extrema}")
            covered_sides.add(math.copysign(1.0, z_min))
        elif z_min <= PLATE_Z_MINUS + 1e-5 or z_max >= PLATE_Z_PLUS - 1e-5:
            raise RuntimeError(f"{name}: root blend reaches an outside entry/knife cap: {extrema}")
        if any(
            limits is not None
            and not limits[0] - 1e-5 <= low <= high <= limits[1] + 1e-5
            for limits, low, high in zip(
                envelope, (x_min, y_min, z_min), (x_max, y_max, z_max), strict=True,
            )
        ):
            raise RuntimeError(f"{name}: native face escapes the junction envelope: {extrema}")
        if longitudinal is not None:
            if not any(
                start - RIB_BLEND_R - 1e-5 <= z_min <= z_max <= end + RIB_BLEND_R + 1e-5
                for start, end in runs
            ):
                raise RuntimeError(f"{name}: native face escapes the junction envelope: {extrema}")
            if surface.IsCylinder() and z_max - z_min > 4.0 * RIB_BLEND_R:
                parameters = tuple(float(value) for value in surface.CylinderParams)
                if (
                    len(parameters) != 7 or not all(math.isfinite(value) for value in parameters)
                    or not math.isclose(parameters[0] * 1000.0, center[0], abs_tol=1e-5)
                    or not math.isclose(parameters[1] * 1000.0, center[1], abs_tol=1e-5)
                    or abs(parameters[3]) > 1e-6 or abs(parameters[4]) > 1e-6
                    or not math.isclose(abs(parameters[5]), 1.0, abs_tol=1e-6)
                ):
                    raise RuntimeError(f"{name}: native cylinder is not the tangent junction blend: {parameters}")
                for index, (start, end) in enumerate(runs):
                    if z_min <= start + 2.0 * RIB_BLEND_R and z_max >= end - 2.0 * RIB_BLEND_R:
                        covered_runs.add(index)
        if radius is not None:
            if not math.isfinite(radius) or not math.isclose(
                radius, expected_radius, abs_tol=1e-5
            ):
                raise RuntimeError(
                    f"{name}: native root radius {radius} is not R{expected_radius}"
                )
            count += 1
    # The blend between the crossed pivot and side-arc cylinders need not be
    # analytic: the envelope bounds its faces, the feature radius its size.
    analytic_minimum = 0 if name == "CounterWebSideRootFillets" else minimum_faces
    if count < analytic_minimum or seen < minimum_faces:
        raise RuntimeError(
            f"{name}: only {count} native R{expected_radius} root surfaces "
            f"({seen} faces) for {minimum_faces} selected reentrant roots"
        )
    if longitudinal is not None and covered_runs != set(range(len(runs))):
        raise RuntimeError(f"{name}: missing native longitudinal blend run: {sorted(covered_runs)}")
    if name == "CounterWebSideRootFillets" and covered_sides != {1.0, -1.0}:
        raise RuntimeError(f"{name}: missing native side-arc blend at Z side: {sorted(covered_sides)}")
    if knife:
        _telemetry.info(
            f"{name}: native roots reach |X| {reach[0]:.4f}, |Y| {reach[1]:.4f}, "
            f"{reach[2]:.4f} mm beyond the body end"
        )


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
    """Band every modeled rib and junction blend under the R.040 MAX ceiling.

    Profile blends, perpendicular rib-side roots and the longitudinal, boss
    and crease junction blends remain native controls without a duplicate
    drawing callout.
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
    reference), the +X upper flank and side face (FlankToSide, driven), and
    the +X lower flank and side face (LowerFlankToSide, driven, at the title
    block's angular tolerance).  The part saves the sketch hidden and the drawing shows it only in
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
    # The lower half: the side face's other half and the +X lower flank to
    # the bottom vertex, so the lower corner's angle can print.
    lower_side = check(
        "knife-envelope +X lower side face",
        await adapter.add_line(HEX_W / 2.0, 0.0, HEX_W / 2.0, -HEX_H / 4.0),
    )
    lower_flank = check(
        "knife-envelope +X lower flank",
        await adapter.add_line(HEX_W / 2.0, -HEX_H / 4.0, 0.0, -HEX_H / 2.0),
    )
    set_sketch_direct_db(adapter, False)
    for entity in (width, height, flank, side, lower_side, lower_flank):
        _as_construction(adapter, entity)
    for entity, relation in (
        (width, "horizontal"),
        (height, "vertical"),
        (side, "vertical"),
        (lower_side, "vertical"),
    ):
        check(
            f"knife-envelope {entity} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    for first, second in (
        (f"{flank}.start", f"{height}.end"),
        (f"{flank}.end", f"{width}.end"),
        (f"{side}.start", f"{width}.end"),
        (f"{lower_side}.start", f"{side}.end"),
        (f"{lower_flank}.start", f"{lower_side}.end"),
        (f"{lower_flank}.end", f"{height}.start"),
    ):
        check(
            f"knife-envelope {first} on {second}",
            await adapter.add_sketch_constraint(first, second, "coincident"),
        )
    check(
        "knife-envelope side halves equal",
        await adapter.add_sketch_constraint(lower_side, side, "equal"),
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
    # The lower corner at the title block's angular tolerance; its text in
    # the exterior wedge below the +X lower shoulder.
    await add_angular_reference_dimension(
        adapter,
        lower_flank,
        lower_side,
        (HEX_W / 2.0 + 2.0, -HEX_H / 4.0 - 0.6),
        "knife lower flank to side face",
        expected_degrees=180.0 - RIDGE_ANGLE_DEG / 2.0,
    )
    knife.record("LowerFlankToSide")
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
    stub's -X side, from the body end (PLATE_Z_MINUS) to the stub's
    outboard face, carries it as a driving dimension off "HexDepth"; the part
    saves the sketch hidden and the plan shows it as the stubs' "2X".  The
    Top-plane sketch maps world Z to -sketchY."""
    reference = SketchDims()
    check("create knife-stub reference", await adapter.create_sketch("Top"))
    start = (-HEX_W / 2.0, -PLATE_Z_MINUS)
    set_sketch_direct_db(adapter, True)
    length = check(
        "knife-stub length reference",
        await adapter.add_line(*start, start[0], -HEX_Z_OUTER_MINUS),
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
    reference.record("KnifeStubRefZ", '"PlateL" - "PlateZPlus"')
    await ensure_fully_defined(adapter, "knife-stub reference sketch")
    check("exit knife-stub reference", await adapter.exit_sketch())
    name_last_feature(adapter, "KnifeStubReference")
    drive_jobs += reference.apply(adapter, "KnifeStubReference")
    blank_reference_sketches(adapter, ("KnifeStubReference",))


def _reference_display(adapter, feature_name: str, name: str) -> None:
    """Print ``name@feature_name`` as a reference, "(8.080)": untoleranced,
    in parentheses (its prefix and suffix)."""
    display, dimension = _named_dimension(adapter, feature_name, name)
    label = f"{name}@{feature_name}"
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolType_e.swTolNONE
    display.SetText(2, ")")  # swDimensionTextParts_e.swDimensionTextSuffix
    if int(tolerance.Type) != 0 or str(display.GetText(2) or "") != ")":
        raise RuntimeError(f"{label}: reference display did not persist")


def _hex_width_reference(adapter) -> None:
    """HexWidth prints as a reference, "2X (8.080)": a driven dimension, the
    opening parenthesis its native prefix (DIMENSION_PREFIXES)."""
    _, dimension = _named_dimension(adapter, "KnifeEnvelopeReference", "HexWidth")
    if int(dimension.DrivenState) != 1:
        raise RuntimeError("HexWidth@KnifeEnvelopeReference: a reference dimension must be driven")
    _reference_display(adapter, "KnifeEnvelopeReference", "HexWidth")


def _drawing_dimension_contract(adapter) -> None:
    """Size and mark every dimension the print imports (DRAWING_DIMENSIONS)."""
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # The knife-edge controls the free-rock check assumes (code review C09):
    # the ridge from each side face and the flank-to-side angle carry their
    # own tolerances; the vertex height the title block's .XXX (the envelope's
    # places are DRAWING_PRECISION's).
    set_dimension_display_precision(adapter, "KnifeEnvelopeReference", "FlankToSide", 1)
    set_dimension_display_precision(adapter, "KnifeEnvelopeReference", "LowerFlankToSide", 1)
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
    """Native coordinates from the real free edge and actual plate top."""
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
    # Reference stations (owner ruling 2026-11-08 (#2144 item 11.1), Pedro;
    # formerly delegated ruling sm Q7): the taps
    # are spotted through MHA-MG-01's holes at assembly (MHA-SM-00), so the
    # print gives the stations in parentheses, untoleranced; the receiver
    # walls still charge joint.POSITION_BAND as the bracket's placement.
    names = ["ReceiverX0", "ReceiverX1", "ReceiverY0"]
    for name in names + ["ReceiverY1"]:
        set_dimension_prefix(adapter, "ReceiverCoordinates", name, "(")
        _reference_display(adapter, "ReceiverCoordinates", name)
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
    "PlateZPlus": PLATE_Z_PLUS,
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


@_telemetry.traced("part.spring_row_equations")
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
    part = _early_bound(model, "IPartDoc")
    pattern = _early_bound(part.FeatureByName("SpringHolePattern"), "IFeature")
    spacing = float(_early_bound(pattern.Parameter("D3"), "IDimension").SystemValue)
    if not math.isclose(system_mm["SpringPitch"], spacing * 1000.0, abs_tol=1e-6):
        raise RuntimeError(
            f"SpringPitch {system_mm['SpringPitch']!r} mm is not the pattern's "
            f"spacing {spacing * 1000.0!r} mm"
        )
    _telemetry.success(f"spring-row locators equation-driven: {system_mm}")


@_telemetry.traced("part.spring_row_coordinates")
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
    ridge = (0.0, -PLATE_Z_MINUS + 0.3 * HEX_DEPTH)
    end = (SPRING_ROW_END_MARK_X, -PLATE_Z_PLUS)
    seed = (HOLE_X, -HOLE_Z_LAST)
    second = (HOLE_X, -(HOLE_Z_LAST - CHANNEL_PITCH))
    set_sketch_direct_db(adapter, True)
    try:
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
            await adapter.add_line(
                *second, second[0] + SPRING_ROW_TAP_MARK, second[1]
            ),
        )
    finally:
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
    dimensions.record(
        "SpringRowRidgeZ", '"PlateL" - "PlateZPlus" + 0.3 * "HexDepth"'
    )
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
    dimensions.record("SpringRowEndZ", '"PlateZPlus"')
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
    dimensions.record("SpringStartZ", f'"PlateZPlus" - ({SPRING_SEED_STATION_EXPR})')
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
    await set_global(adapter, "PlateZPlus", f"{PLATE_Z_PLUS}mm")
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
    # Keep the derivation native: a degree literal was rounded to angular places.
    await set_global(
        adapter, "CounterFlankAngle",
        'atn("ArcR" / sqr("SumH" * "SumH" - "ArcR" * "ArcR"))',
    )
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
        _assert_native_rib_profile(adapter, stem, equation_bound=True)

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
            "Manufacturing Notes": DRAWING_NOTES,
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
            "Manufacturing Notes",
            "Isometric View Note",
            "Back View Note",
            "Front View Note",
            "Receiver Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
