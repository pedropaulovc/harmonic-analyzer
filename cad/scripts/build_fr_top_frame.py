r"""Reproduction script: top frame casting (2026-08-02 rederive; 1 used).

ONE green cast iron piece that absorbed the old separate top-crossbar
(full-height integral bar) and gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side). Derived from the ch30 eight views (px
measurement anchored on the 394 x 224 column pitch), the GT bundle solve
rescaled onto the model column grid, and ch19 close-ups (webbing, hub, screw):

* Rail band y 999.6932..1036.193 (39.358..40.795, H 36.4998 = 1.437; the old
  41-tall band top 1040.7 was the BOSS top -- the rail top face is 4.572
  lower). Assembly inserts the part at ring mid-plane TOP_FRAME_MID_Y = 1017.9431.
* Side rails (along Z at x +/-197.0024) 34.29 (1.35) wide -> outer faces
  x +/-214.1474, window x +/-179.8574. Front/rear rails (along X at
  z -/+112.014) 38.1 (1.50) wide -> outer faces z -/+131.064, window z -/+92.964.
* Corner bosses O44.958 (1.77) spanning y 993.267..1040.765 (proud .18
  above the rail top, hanging .253 below the underside, 1.87 overall). All
  four upper/lower bosses use the smaller user-ruled diameter so the
  outward keeper feet sit flat. The O25.5016 column bores and O27.5082 cap
  recesses follow the column and attachment specs. Four stock 1-3/4 in
  cross screws seat flush in front/rear O8.89 (.35) counterbores, pass a
  #10 close clearance through the near casting wall (owner ruling
  2026-11-05) and both tube walls, and thread into the far casting wall/web
  through #10-32 taps on TOP_SCREW_Y, .72 below the rail top (.90 below the
  boss top).
* The whole TOP plane between the four corner bosses -- rail flange tops,
  crossbar and gussets -- is faced at the Ra 125 µin locating-seat finish (user
  rulings 2026-10-11 and 2026-10-14, one linked manufacturing note), the
  keeper rail flat within the keeper-owned 0.04 zone so both keeper feet
  land on one face wherever fit-up puts them. The nominal rail-top plane
  stays fixed; the H-H top flange thickness (TYP, .XX, minimum 7.874) is
  the finished flange under it.
* Integral crossbar 25.146 (.99) wide, centred on the knife line x -15.0,
  spanning the window along Z, flush with BOTH faces at its junctions (the
  faced underside 999.6932 is the knife-mount seat plane), with 18.034 (.71)
  plan gussets at all four rail
  junctions and, at z 3.088 -/+ 87.06, a plain #10 through-hole (C drill) per
  knife mount. The cut-to-length #10-24 hex bolt bears on a 96659A104
  washer on the faced top; each unchanged 98381A473 dowel presses into a
  blind flat-floor underside ream with a #51 knockout drilled up from its
  floor on the ream's drawn axis (owner ruling 2026-10-24, T+H3), its
  coaxiality the title block's implied +/-.005, charged in the floor land
  (.0124, accepted as RV-06 by owner ruling 2026-10-27). Over its middle
  (|z| <= 68.834, short of the knife-mount seats) the bar is a T like the
  rails: the .99-wide, .32-tall top flange over a .51 web centred on the
  knife line through the
  underside, with R.12 roots.
* Every face on the underside plane 999.6932 between the bosses -- rail web
  bottoms, junction lands, plan gussets and the crossbar's full-depth ends
  under both knife mounts -- is faced at the Ra 125 µin seat finish (user
  ruling 2026-10-12, one linked manufacturing note); the corner-boss
  bottoms .253 below it and the hub boss and V-gussets .31 below stay off
  it. 999.6932 is the FINISHED plane: the cut comes out of casting allowance,
  so the model, its bands and every stack read from it unchanged. It is
  faced first. The #10 clearance holes are drilled through from it (Q7
  option C); the dowel reams are cut blind from it and located
  from each #10 hole's axis there (sheet 6
  dimensions them in the underside view). Each axis is therefore true at
  the knife-mount seat and its drift grows toward the top. The finished
  top-to-underside grip is 1.437 at the title block's .XXX band: HangerGrip,
  the crossbar's own full-height extrude depth, is driven by the RingHeight
  global and carries no band of its own (owner ruling 2026-10-18: each
  MHA-SM-VN-52 is cut to the measured grip at MHA-SM-00).
  Datum D on the native crossbar width, as cast (owner ruling B5),
  establishes BOTH-face median plane; the hanger axes' linear position zone
  centres them within +/-.005 of it.
* Gooseneck hub on the east rail (-X) at z +3.088: full-height rib 1.10 wide,
  O.520 slip bore for the gooseneck's bare 1/2 in leg, underside boss
  O1.18 x .31 with twin V-gussets (ch30 p004), a square-sided cast boss on
  the rib's outer face, the rail's full height and flush with the faced top
  (ch19 img04; user ruling 2026-10-12; owner ruling B4, #2333), its cast
  face .95 from the bore axis on the faced top, spot-faced .83 from the
  bore axis, and a 1/4-20 tap from the spot face to the bore for the
  square-head set screw on the cross taps' plane, .72 below the rail top
  (book p.45: "a square-head screw pinches the post in its socket").
* Webbed faces (T-rail section): a .32-tall full-thickness top flange, then
  the web thins to .51 centred on each rail and STAYS thin through the
  bottom edge. The former photo-read 12.7 web is thickened for the keeper
  receivers' printed-band plus drill-wander stack; full-thickness lands remain
  at the bosses, hub rib and crossbar junctions.
* Gray-iron casting, machined on the seats only (owner rulings B1-B6 and
  D1-D6, #2333; fr_top_frame_spec records each).  Every cast wall carries
  2 deg of draft about the faced plane its nominal stands on: ADDED on the
  rail webs, the crossbar web and sides, the plan gussets, the junction
  lands, the hub rib, the hub V-gussets and the set-screw boss's side
  walls (nominal on the underside, thicker toward the top; 2 +1/-0 deg);
  TAKEN OUT on the corner-boss barrels (O1.77 on the faced top plane, both
  barrels narrowing away from it), the flange's outer and window rims with
  the rib and land strips flush with them (nominal on the faced top), the
  hub boss barrel (O1.18 on the underside) and the set-screw boss face
  (2 +/-1 deg).  Faced planes, boss tops, bores, recesses, the spot face,
  counterbores and holes are machined and plumb.  Each printed dimension
  with an as-cast end carries +/-.03 on its own model dimension, and every
  wall and fit proof below charges that band and the binding draft extreme.
* Finishing (chamfer external, fillet internal): R.12 cast fillets along
  the internal web/flange T-roots (both shelves of every rail and the
  crossbar web, ch19 img04's panel blends), .06 x 45 breaks (the base's
  1/16 in, printed .06 at .XX) on the top-face rims --
  outer rail rim and both window rims -- then on every other external
  convex edge (flange undersides, web bottoms, lands, crossbar, hub rib,
  boss rims), and .040 x 45 lead-ins on the bore TOP ends
  only. The R.885 bosses bulge 5.4 beyond the side rails and 3.4 beyond
  the front/rear rails, but do not reach the rectangular flange's plan
  corners (25.60 from their centres), so each corner is cropped back to its
  boss barrel (user ruling 2026-10-14), with the crop's chord inside the
  smallest printed barrel at the farthest printed faces: window corners
  remain square and the outer rim runs die into the barrels. Edge breaks
  are judged at the print's limits, since a conforming casting may carry
  any printed size: edges too close to a feature, too short or on too
  narrow a flange shelf there, or under a knife-mount seat, for the printed
  worst break the model leaves unbroken at .06 (listed in
  _external_edge_breaks), as it does hole and bore low ends; the title
  block's .010 break applies to them (owner ruling 2026-11-07).

Layout: plan profile in XZ about the ring mid-plane (rails y
-18.2499..+18.2499 local). Sketches on the Top plane use the
(x, y) -> (X, -Z) handedness; sketches on Right-plane offsets map
(x, y) -> (Z, Y) (build_fr_rocker_arm_support precedent; NEGATIVE-offset
planes mirror sketch x -- see the gusset/boss sites). Build order
(ADDITIVE T-section -- the web/flange rings are extruded, not pocketed;
every cast wall a drafted blind extrude from the faced plane its nominal
stands on, _drafted_extrude):
web ring (up from the underside) -> top-flange ring (down from the faced
top) -> hub rib restore -> crossbar, gussets and junction lands (one
polygon) -> crossbar T pockets -> flange corner crops -> corner bosses
(up/down pair from the faced top) -> hub V-gusset plate and its ramp cuts
-> hub boss -> set-screw boss and spot face -> counterbores -> column
bores -> gooseneck
bore -> wizard holes (#10 C-drill hanger clearance holes) -> dowel reams ->
dowel knockouts (wizard) -> wizard
holes (side-screw taps, set-screw tap, keeper taps) -> internal T-root
fillets (R.12) -> external top-rim breaks (1/16 in) -> .040 bore top lead-ins ->
remaining external edge breaks (1/16 in, one feature per connected chain: rail
runs, crossbar, west window, hub rail, hub set-screw boss, boss rims).
Wizard holes come after the face cuts so every seat face is final; the
edge breaks follow the solid features.
Analytic volume checks after every feature: each drafted prism's closed
form accepts its feature (a drafted extrude's flags are proved by what
they do to the solid), boss additions and top-rim breaks use
circle-segment formulas, the remaining edge breaks sum per-edge chamfer
sections, while counterbore/tap expectations use small grid integrals
against the drafted solid.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fr_top_frame.py
"""

from __future__ import annotations

import math
import sys

import _config
from _appearance import CASTING_GREEN, apply_color, apply_material
from _check import check
from _com import _early_bound
from _document_units import apply_package_model_units
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _dimensions import drive_dimension, name_dimensions, set_global
from _drafted_extrude import (
    assert_drafted,
    drafted_extrude,
    drafted_forms,
    name_feature_dimensions,
    set_draft_angle_tolerance,
)
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_point,
    dimension_between,
    ensure_fully_defined,
)
from _sketch_chains import define_polygon_chain, define_rectilinear_chain
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _visibility import blank_reference_geometry
from _holes import (
    DRILL_POINT_H,
    HoleSpec,
    TAP_DRILL_MM,
    THREAD_MAJOR_MM,
    blind_hole_volume_mm3,
    find_planar_face,
    wizard_holes,
)
from _gtol_face_resolve import resolve_faces
from _part_pmi import author_part_pmi
from _named_views import name_octant_views
from fr_top_frame_spec import (
    AS_CAST_BAND,
    AS_CAST_DIMENSIONS,
    BORE_DIA,
    BOSS_ABOVE,
    BOSS_DIA,
    CAP_RECESS_FLOOR_Y,
    COLUMN_X,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_NOTES_B,
    DRAWING_NOTES_C,
    DRAWING_PRECISION,
    DRAWING_REFERENCE_PRECISION,
    DRAFT_ADDED_DEG_MIN,
    DRAFT_ANGLE_DIMENSIONS,
    DRAFT_DEG,
    DRAFT_DEG_MAX,
    DRAFT_DEG_MIN,
    DRAFT_TAKEN_OUT_ON_UNNAMED_FACES,
    DATUM_TARGET_BARREL_HEIGHT,
    DATUM_TARGET_BOTTOM_RADIUS,
    DRAFT_TAN,
    EDGE_CHAMFER,
    FLANGE_THICKNESS_MM,
    HANGER_CROSSBAR_WIDTH,
    HANGER_CROSSBAR_CENTER_TOL,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    HALF_H,
    HUB_BOSS_DROP,
    HUB_SET_BOSS_FROM_AXIS,
    HUB_SET_BOSS_W,
    HUB_SET_SPOT_DIA,
    HUB_SET_SPOT_FROM_AXIS,
    HUB_SET_SPOT_PLACES,
    RAIL_SECTION_X,
    RAIL_WEB_POSITION_ZONE,
    SIDE_SECTION_Z,
    SOCKET_PATTERN_LOCATION_ZONE,
    SOCKET_PATTERN_REFINEMENT_ZONE,
    HANGER_WASHER,
    HANGER_WASHER_FLOAT_MAX,
    HANGER_WASHER_CONCENTRIC_ANNULUS_MIN,
    HANGER_CLEARANCE_DIA,
    HANGER_CLEARANCE_DIA_MAX,
    SCREW_AXIS_BELOW_RAIL_TOP,
    SCREW_AXIS_Y,
    HANGER_GRIP,
    HANGER_GRIP_TOL,
    HANGER_HOLE_SPEC,
    HANGER_KNOCKOUT_COAXIAL_TOL,
    HANGER_KNOCKOUT_DIA,
    HANGER_KNOCKOUT_DIA_MAX,
    HANGER_KNOCKOUT_LENGTH,
    HANGER_KNOCKOUT_LENGTH_MAX,
    HANGER_KNOCKOUT_SPEC,
    HANGER_PIN_HOLE_DEPTH,
    HANGER_PIN_HOLE_DEPTH_TOL,
    HANGER_PIN_HOLE_DIA,
    HANGER_PIN_HOLE_DIA_BAND,
    HANGER_PIN_HOLE_DIA_MAX,
    HANGER_PIN_HOLE_DIA_PLACES,
    HANGER_PIN_X,
    HANGER_PIN_X_TOL,
    HANGER_X,
    PIN_HOLE_X,
    STUD_Z_FRONT,
    STUD_Z_REAR,
    KEEPER_TAP_CALLOUT_PRECISION,
    KEEPER_TAP_DRILL_WANDER_DEG,
    DRILL_DRIFT_PER_MM,
    PRINTED_DRILLED_HOLE_PLUS_MM,
    PRINTED_LINEAR_BAND_MM,
    REAR_COLUMN_Z,
    UNIT,
    TOP_CROSS_SCREW_FAR_WALL_START_MAX,
    printed_limit,
    SET_SCREW_THREAD,
    RING_HEIGHT,
    SURFACE_FINISHES,
    WEB_T,
)
from _cone_axis_constants import (
    FRAME_COLUMN_Z_CENTER,
    SUMMING_Z,
)
from fr_frame_attachment_spec import (
    CAP_RECESS_DEPTH,
    CAP_RECESS_DIAMETER,
    CASTING_FULL_THREAD_DEPTH,
    TOP_CASTING_TAP_DRILL_DEPTH,
    TOP_SCREW_COUNTERBORE_DIAMETER,
    TOP_SCREW_SEAT_Z,
)
from fr_frame_cross_screw import (
    FAR_WALL_ENGAGEMENT_FLOOR_MM,
    NEAR_WALL_CLEARANCE_DIAMETER,
    NEAR_WALL_CLEARANCE_FIT,
    NEAR_WALL_CLEARANCE_SIZE,
    far_wall_full_thread_min_mm,
    far_wall_start_max_mm,
    near_wall_hole_volume_mm3,
)
from _fit_deviations import deviations
from fr_vn_tube_frame_cap_spec import MAX_OUTER_DIAMETER as CAP_MAX_OUTER_DIAMETER
import sm_knife_mount_spec as KNIFE_MOUNT
import sm_vn_knife_mount_dowel_spec as KNIFE_DOWEL
from _printed_tolerance import (
    angular_band_deg,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_deviations,
)
from ch_vn_frame_side_screw_spec import SHANK_DIA as KEEPER_SCREW_MAJOR_DIA
from _mcmaster_90280a837 import (
    HEAD_DIA as CROSS_SCREW_HEAD_DIA,
    HEAD_H as CROSS_SCREW_HEAD_H,
)
from ch_fulcrum_keeper_spec import (
    DRAWING_PRECISION as KEEPER_DRAWING_PRECISION,
    FOOT_COUNTERBORE_DEPTH_PLACES,
    FOOT_H,
    FOOT_SCREW_LENGTH_MM,
    CBORE_DEPTH_MM,
    KEEPER_FITUP_X_FROM_WEB_MM,
    KEEPER_SCREW_TRANSVERSE_BAND_MM,
    SCREW_FROM_SIDE,
    KEEPER_FITUP_LOCATION_BAND_MM,
    KEEPER_FITUP_X_BAND_MM,
    KEEPER_FITUP_PLACES,
    KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM,
    OVERALL_LENGTH as KEEPER_OVERALL_LENGTH,
    FOOT_TIP_X,
    FULCRUM_KEEPER_CENTRE_Z,
    KEEPER_SCREW_Z_OFF,
    KEEPER_TAP_SPEC,
    KEEPER_WIDTH,
    KEEPER_Z_OFF,
)

import _telemetry

PART_NAME = "fr-top-frame"
MATERIAL = "Gray Cast Iron"  # green-painted casting like the base

# --- Plan geometry (machine == part-local x/z; part y = machine y - TOP_FRAME_MID_Y)
#
# COLUMN_X, FRONT/REAR_COLUMN_Z, RING_HEIGHT, HALF_H, BOSS_ABOVE, BORE_DIA,
# CAP_RECESS_FLOOR_Y, GOOSENECK_X and GOOSENECK_BORE_DIA are imported from
# fr_top_frame_spec: the machined-surface face specs are keyed off those stations,
# and the spec is the COM-free contract the drawing's finish symbols are
# provenance-checked against.
FRAME_CENTER_Z = FRAME_COLUMN_Z_CENTER  # 0.0

RAIL_W_SIDE = 34.29  # 1.35 side rails, along Z (GT corner rescale 221.5 -> 214.1)
RAIL_W_FR = 38.1  # 1.50 front/rear rails, along X (GT z-corner rescale 137.4 -> 131)

# .253 boss hang below the underside (p006 read 5.7-7): the boss's overall
# height closes on the .XX grid at 1.87 over the .18 rise and the 1.437 rail.
BOSS_BELOW = 6.4262
# The cap recess diameter prints 1.083 under the title block's .XXX
# (owner ruling 2026-11-06): no explicit band; the proofs read its limits.
CAP_RECESS_DIAMETER_PLACES = DRAWING_PRECISION["CapRecessProfile"]["CapRecessDia"]
CAP_RECESS_DIAMETER_MIN = printed_limit(
    CAP_RECESS_DIAMETER, CAP_RECESS_DIAMETER_PLACES, -1.0
)  # 27.3812
CAP_RECESS_DIAMETER_MAX = printed_limit(
    CAP_RECESS_DIAMETER, CAP_RECESS_DIAMETER_PLACES, 1.0
)  # 27.6352
# The recess depth keeps its .642 minimum under a unilateral band in a plain
# inch step, +.010/0 (machinist review of fanout/integration 8fb7fb46f7 read
# +.012/0 as a converted 0.3 mm); the proofs below charge its deepest floor.
CAP_RECESS_DEPTH_BAND = (0.254, 0.0)  # +.010/0
# The smallest printed recess round the largest MHA-FR-VN-54 skirt.
CAP_RECESS_DIAMETRAL_CLEARANCE = CAP_RECESS_DIAMETER_MIN - CAP_MAX_OUTER_DIAMETER
if CAP_RECESS_DIAMETRAL_CLEARANCE <= 0.0:
    raise AssertionError("purchased cap does not clear the top-frame recess")

OUTER_X = COLUMN_X + RAIL_W_SIDE / 2.0  # 214.0966
INNER_X = COLUMN_X - RAIL_W_SIDE / 2.0  # 179.9082
OUTER_Z = abs(FRONT_COLUMN_Z) + RAIL_W_FR / 2.0  # 131.064
INNER_Z = abs(FRONT_COLUMN_Z) - RAIL_W_FR / 2.0  # 92.964

# --- Integral crossbar (old top-crossbar, merged) ---------------------------
# Centred on the spec's hanger x (HANGER_X, the knife's); the hanger
# stations and their one ream each (PIN_HOLE_X, +X of the screw axis; Owner
# ruling 2026-11-08 (Pedro), #2144 item 11.3) are the spec's.
BAR_X0, BAR_X1 = (
    HANGER_X - HANGER_CROSSBAR_WIDTH / 2.0,
    HANGER_X + HANGER_CROSSBAR_WIDTH / 2.0,
)
GUSSET = 18.034  # .71 plan gusset legs at the four rail junctions

# --- Cast datum targets (owner rulings B6 and D2, #2333) ---------------------
# Six points fixture the casting for its first cut.  E1-E3 stand on three
# corner-boss bottoms, DATUM_TARGET_BOTTOM_RADIUS from each socket axis: E1
# toward the front on the rear-west boss, E2 toward the east on the rear-east
# one, E3 toward the front on the front-east one, so the hypotenuse E1-E3
# stands CAST_DATUM_E_MARGIN (13.9) clear of the frame's centre, on the hub's
# side of which the casting's centroid lies.  F1 and F2 stand on the two rear
# barrels' rear generators and G1 on the rear-west barrel's west generator
# (owner ruling D2), each DATUM_TARGET_BARREL_HEIGHT over its boss bottom.
# The barrels are taken-out draft (D1), so the F and G planes stand
# DATUM_TARGET_BARREL_R off the socket axes, and their corner is the hole
# table's origin.  Datum D's station prints from G.
BOSS_BOTTOM_Y = -(HALF_H + BOSS_BELOW)  # -24.6761
DATUM_TARGET_Y = BOSS_BOTTOM_Y + DATUM_TARGET_BARREL_HEIGHT  # -21.3741
DATUM_TARGET_BARREL_R = BOSS_DIA / 2.0 - (HALF_H - DATUM_TARGET_Y) * DRAFT_TAN  # 21.0953
CAST_DATUM_TARGETS: dict[str, tuple[float, float, float]] = {
    "E1": (COLUMN_X, BOSS_BOTTOM_Y, REAR_COLUMN_Z - DATUM_TARGET_BOTTOM_RADIUS),
    "E2": (-COLUMN_X - DATUM_TARGET_BOTTOM_RADIUS, BOSS_BOTTOM_Y, REAR_COLUMN_Z),
    "E3": (-COLUMN_X, BOSS_BOTTOM_Y, FRONT_COLUMN_Z - DATUM_TARGET_BOTTOM_RADIUS),
    "F1": (COLUMN_X, DATUM_TARGET_Y, REAR_COLUMN_Z + DATUM_TARGET_BARREL_R),
    "F2": (-COLUMN_X, DATUM_TARGET_Y, REAR_COLUMN_Z + DATUM_TARGET_BARREL_R),
    "G1": (COLUMN_X + DATUM_TARGET_BARREL_R, DATUM_TARGET_Y, REAR_COLUMN_Z),
}
CAST_DATUM_ORIGIN_XZ = (
    COLUMN_X + DATUM_TARGET_BARREL_R,
    REAR_COLUMN_Z + DATUM_TARGET_BARREL_R,
)  # the F and G planes' corner: (218.0977, 133.1093)
D_STATION = CAST_DATUM_ORIGIN_XZ[0] - HANGER_X  # 233.0977, 9.18 from G
# The construction line that carries D's station stands this far in front of
# the frame's centre (6 past the front bosses), and the span that finds the
# bar's median a step in front of that: the casting's rear is where the
# datum-target symbols stand.
D_STATION_LINE_Z = FRONT_COLUMN_Z - BOSS_DIA / 2.0 - 6.0  # -140.493
D_STATION_SPAN_STEP = 5.0
# A boss-bottom target keeps this much of the bottom's ring either side of
# it, and a barrel target this much of the barrel's free band above and
# below it: the ring runs from the socket bore to the bottom's edge break,
# the band from that break's upper edge to the faced underside.
DATUM_TARGET_LAND_MIN = 1.5
_BOSS_BOTTOM_EDGE_R = (
    BOSS_DIA / 2.0 - (RING_HEIGHT + BOSS_BELOW) * DRAFT_TAN - EDGE_CHAMFER
)  # 19.456
_BOSS_BOTTOM_BREAK_TOP_Y = BOSS_BOTTOM_Y + EDGE_CHAMFER * math.sin(
    math.radians(45.0)
) / math.sin(math.radians(45.0 - DRAFT_DEG)) * math.cos(math.radians(DRAFT_DEG))
DATUM_TARGET_LANDS = (
    DATUM_TARGET_BOTTOM_RADIUS - BORE_DIA / 2.0,  # 3.251
    _BOSS_BOTTOM_EDGE_R - DATUM_TARGET_BOTTOM_RADIUS,  # 3.454
    DATUM_TARGET_Y - _BOSS_BOTTOM_BREAK_TOP_Y,  # 1.723
    -HALF_H - DATUM_TARGET_Y,  # 3.124
)
if min(DATUM_TARGET_LANDS) < DATUM_TARGET_LAND_MIN:
    raise AssertionError(
        f"a cast datum target stands {min(DATUM_TARGET_LANDS):.3f} mm from the "
        f"edge of its face; needs {DATUM_TARGET_LAND_MIN:g}"
    )


def _e_triangle_margin() -> float:
    """How far the frame's centre stands inside the E1-E2-E3 triangle, mm."""
    points = [(x, z) for x, _y, z in (CAST_DATUM_TARGETS[k] for k in ("E1", "E2", "E3"))]
    margins = []
    for i in range(3):
        (x0, z0), (x1, z1), (x2, z2) = points[i], points[(i + 1) % 3], points[(i + 2) % 3]
        length = math.hypot(x1 - x0, z1 - z0)
        side = ((x1 - x0) * (z2 - z0) - (z1 - z0) * (x2 - x0)) / length
        centre = ((x1 - x0) * (0.0 - z0) - (z1 - z0) * (0.0 - x0)) / length
        margins.append(centre if side > 0.0 else -centre)
    return min(margins)


CAST_DATUM_E_MARGIN = _e_triangle_margin()  # 13.91
CAST_DATUM_E_MARGIN_MIN = 10.0
if CAST_DATUM_E_MARGIN < CAST_DATUM_E_MARGIN_MIN:
    raise AssertionError(
        f"the frame's centre stands {CAST_DATUM_E_MARGIN:.2f} mm inside the E "
        f"targets' triangle; needs {CAST_DATUM_E_MARGIN_MIN:g}"
    )


def swept_contours_disjoint(
    contours: tuple[tuple[tuple[float, float], tuple[float, float], float], ...],
) -> bool:
    """Whether one sketch's closed contours enclose disjoint regions.

    Each contour is a core segment ``(start, end)`` swept by a radius: a
    stadium, or a circle when the segment is a point.  A cut fails on
    contours that cross (FeatureCut3 "Type mismatch") and merges ones that
    touch, so the regions must stand strictly apart.
    """

    def segment_gap(a0, a1, b0, b1) -> float:
        def point_to_segment(p, s0, s1) -> float:
            dx, dy = s1[0] - s0[0], s1[1] - s0[1]
            span = dx * dx + dy * dy
            t = 0.0
            if span > 0.0:
                t = ((p[0] - s0[0]) * dx + (p[1] - s0[1]) * dy) / span
                t = min(1.0, max(0.0, t))
            return math.hypot(p[0] - (s0[0] + t * dx), p[1] - (s0[1] + t * dy))

        # The two cores of one sketch's contours never cross here (parallel
        # or point cores), so the endpoint distances bound the gap.
        return min(
            point_to_segment(a0, b0, b1),
            point_to_segment(a1, b0, b1),
            point_to_segment(b0, a0, a1),
            point_to_segment(b1, a0, a1),
        )

    return all(
        segment_gap(*a[:2], *b[:2]) > a[2] + b[2]
        for i, a in enumerate(contours)
        for b in contours[i + 1 :]
    )


# The ream sketch's contours in model (x, z): the one ream at each station,
# one closed circle each.
HANGER_PIN_CONTOURS = tuple(
    ((PIN_HOLE_X, z), (PIN_HOLE_X, z), HANGER_PIN_HOLE_DIA / 2.0)
    for z in (STUD_Z_FRONT, STUD_Z_REAR)
)
if not swept_contours_disjoint(HANGER_PIN_CONTOURS):
    raise AssertionError(
        f"the dowel ream sketch's contours overlap: {HANGER_PIN_CONTOURS}"
    )

# --- Gooseneck hub (old gooseneck-clamp function, merged) -------------------
GOOSENECK_Z = SUMMING_Z
HUB_RIB_W = 27.94  # 1.10 full-height rib band across the east rail
HUB_BOSS_DIA = 29.972  # 1.18 underside boss around the bore exit
HUB_GUSSET_T = 7.112  # .28 V-gusset thickness along X, centred on the bore
HUB_GUSSET_HALF_IN = 8.0  # full-depth span |z - 3.088| <= 8 (ramp start, not printed)
HUB_GUSSET_HALF_OUT = 29.972  # feathers to the underside at |z - 3.088| = 29.972 (span 2.36)
# Set-screw boss (fr_top_frame_spec, owner ruling B4): its cast face at the
# faced top and its spot face, as model X on the east side.
SET_BOSS_FACE_X = GOOSENECK_X - HUB_SET_BOSS_FROM_AXIS  # -221.1324
SET_SPOT_FACE_X = GOOSENECK_X - HUB_SET_SPOT_FROM_AXIS  # -218.0844
# The tap opens into the gooseneck bore; it has no blind thread-depth limit.
SET_TAP_SPEC = HoleSpec("tapped", SET_SCREW_THREAD, end="through_next")

# --- Cross screws (frame -> tube-frame columns -> far casting wall) ----------
# Flush counterbores: the Ø9 cut starts 0.4 outside the boss crown and stops
# at the screw seat, deep enough that the stock fillister head sits below
# the mouth's lowest barrel point (guards below). From each floor the near
# casting wall is a #10 close clearance into the socket and only the far
# wall is tapped (owner ruling 2026-11-05, fr_frame_cross_screw).
COUNTERBORE_DIA = TOP_SCREW_COUNTERBORE_DIAMETER
COUNTERBORE_PLANE = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0 + 0.4
COUNTERBORE_FLOOR = TOP_SCREW_SEAT_Z
SIDE_TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    "#10-32",
    end="blind",
    depth_mm=TOP_CASTING_TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": CASTING_FULL_THREAD_DEPTH},
)
SIDE_TAP_DRILL_DIA = TAP_DRILL_MM[SIDE_TAP_SPEC.size]
SIDE_SCREW_XS = (-COLUMN_X, COLUMN_X)
SIDE_SCREW_FACES = (
    ("front", -1.0, True),
    ("rear", 1.0, False),
)
if CAP_RECESS_FLOOR_Y - (SCREW_AXIS_Y + SIDE_TAP_DRILL_DIA / 2.0) <= 0.0:
    raise AssertionError("cap recess breaks into the cross-screw drill")
# The clearance's model depth runs from the floor to the socket axis: past
# the near wall it cuts only socket air, and its drill point stops far short
# of the far wall. The sheet prints DRILL TO SOCKET, not this depth.
SIDE_CLEARANCE_DEPTH = COUNTERBORE_FLOOR - abs(FRONT_COLUMN_Z)  # 16.510
SIDE_CLEARANCE_SPEC = HoleSpec(
    "clearance",
    NEAR_WALL_CLEARANCE_SIZE,
    end="blind",
    depth_mm=SIDE_CLEARANCE_DEPTH,
    fit=NEAR_WALL_CLEARANCE_FIT,
)

# --- Fulcrum keepers (west rail top face; shaft-end brackets, ch17 p.40) ----
# The keeper's pure spec owns both screw station and receiver geometry:
# #2-56 with 7.6 full thread and 11.5 drill retains a five-pitch plug
# lead at the sheet's general .X depth band. No assembly recipe dependency.
KEEPER_TAP_X = COLUMN_X + KEEPER_FITUP_X_FROM_WEB_MM  # nominal fulcrum line
KEEPER_TAP_Z_FRONT = FULCRUM_KEEPER_CENTRE_Z - KEEPER_SCREW_Z_OFF  # -83.504
KEEPER_TAP_Z_REAR = FULCRUM_KEEPER_CENTRE_Z + KEEPER_SCREW_Z_OFF  # +82.496

# --- Webbing ----------------------------------------------------------------
# T-rail section (user-corrected vs ch19 img04): an 8-tall full-thickness top
# flange, below which the web thins to WEB_T centred on each rail's centreline
# and STAYS thin through the bottom edge (no bottom flange). Built ADDITIVELY:
# a full-height thin web ring + an 8-tall full-width flange ring (two
# nested-rectangle sketches), plus full-thickness restore pads at the hub rib
# and the crossbar junctions. The corner bosses supply the corner lands. The
# per-face setback differs by rail family (the rails are 34.2/38.0 wide but
# share one web thickness).
FLANGE = FLANGE_THICKNESS_MM  # final top flange, also below the faced rail top
RECESS_SIDE = (RAIL_W_SIDE - WEB_T) / 2.0  # 10.668 setback per side-rail face
RECESS_FR = (RAIL_W_FR - WEB_T) / 2.0  # 12.573 setback per front/rear-rail face
FLANGE_BOT_Y = RING_HEIGHT / 2.0 - FLANGE  # +10.2489 (flange underside)
WEB_OUT_X = COLUMN_X + WEB_T / 2.0  # 203.477
WEB_IN_X = COLUMN_X - WEB_T / 2.0  # 190.523
WEB_OUT_Z = abs(FRONT_COLUMN_Z) + WEB_T / 2.0  # 118.477
WEB_IN_Z = abs(FRONT_COLUMN_Z) - WEB_T / 2.0  # 105.523
LAND_MARGIN = 6.096  # .24 land pad past each gusset leg
LAND_X0 = BAR_X0 - GUSSET - LAND_MARGIN  # -51.6268; crossbar junction land pads
LAND_X1 = BAR_X1 + GUSSET + LAND_MARGIN  # +21.6268; front/rear inner faces
# Crossbar T-section: over the middle of the bar (|z| <= BAR_POCKET_Z) the
# crossbar keeps its .99-wide, FLANGE-tall top flange and below it thins to a
# WEB_T web centred on the knife line, through the underside. Two flanking
# pockets cut it out of the full-height bar; they stop .24 short of the
# gusset legs (z +/-74.93) so the full-depth ends, which carry every hanger
# hole, keep the whole knife-mount top seat clear of the pocket-end edge
# breaks.
BAR_WEB_X0 = HANGER_X - WEB_T / 2.0  # -21.5024
BAR_WEB_X1 = HANGER_X + WEB_T / 2.0  # -8.4976
BAR_POCKET_Z = 68.834  # 2.71: pocket length 5.42; its end from the socket axis flows through

# --- Draft (owner ruling B1, #2333) -------------------------------------------
# Every drag face leans DRAFT_DEG the same way: the casting narrows toward its
# cast underside.  Added draft keeps a face's nominal on the underside plane
# (the wall thickens toward the top: webs, crossbar web and sides, plan
# gussets, junction lands, hub rib, V-gussets, set-boss sides); taken-out
# draft keeps it on the faced top (the outline shrinks below it: flange rims,
# corner-boss barrels, the set-boss face).  The hub boss barrel keeps its
# nominal on the underside plane and narrows below it.  A taken-out face that
# continues an added one is modelled added from its underside station, here
# the rim's top position less the draft over the rail band: the junction
# lands' and the hub rib's faces stay coplanar with the rims above them.  The
# model is the 2° casting; the proofs charge the binding angle extreme.
DRAFT_T = DRAFT_TAN
RIM_RECEDE = RING_HEIGHT * DRAFT_T  # 1.2746, a rim face over the rail band
LAND_FACE_Z0 = INNER_Z + RIM_RECEDE  # land window faces on the underside
RIB_OUT_X0 = OUTER_X - RIM_RECEDE  # hub rib faces on the underside
RIB_IN_X0 = INNER_X + RIM_RECEDE
POCKET_H = RING_HEIGHT - FLANGE  # 28.37, underside to flange underside
# Construction overruns, no printed meaning: the lands' web edge buried in
# the web, the crossbar pockets' outer edge past the bar side (it must beat
# the two faces' lean over the pocket), the V-gusset plate past its ramps.
LAND_WEB_BURY = 1.0
BAR_POCKET_OVERRUN = 3.0
if BAR_POCKET_OVERRUN <= 2.0 * POCKET_H * DRAFT_T:
    raise AssertionError("crossbar pocket overrun shorter than its faces' lean")
HUB_GUSSET_BOTTOM_Y = -HALF_H - HUB_BOSS_DROP
HUB_GUSSET_PLATE_HALF = HUB_GUSSET_HALF_OUT + 2.0
SET_BOSS_FACE_X0 = SET_BOSS_FACE_X + RIM_RECEDE  # the cast face on the underside
SET_BOSS_INNER_X0 = -RIB_OUT_X0 + 2.0  # its sketch edge, inside the rib
SET_BOSS_PROUD = -SET_BOSS_FACE_X - OUTER_X  # 7.036 past the rail face, constant

# Flange corner crops (user ruling 2026-10-14): the R22.479 corner bosses stop
# short of the rectangular flange's plan corners, 25.60 from each boss axis,
# which left a flange nib outside every barrel -- bounded by the two outer
# faces from their barrel intersections to the corner and by the barrel arc
# between them. Each corner is cropped by one triangle cut through the band
# before the bosses. The print, not the nominal barrel, places its chord: a
# conforming part may pair the smallest .X barrel with both outer faces at
# their farthest printed offsets, so the chord's ends stand on that barrel
# where those faces cross it, and the chord lies inside every printed barrel
# across every printed face (a chord inside the nominal barrel alone left
# flange outside an R22.1 one). Its apex and legs overrun the farthest faces
# by CORNER_CROP_OVERRUN, so no sketch edge lies on a face. The boss union
# then restores the barrel segment inside the chord: no flange stays outside
# a barrel, and the barrels, counterbores and bores are unchanged.
_BOSS_R = BOSS_DIA / 2.0
CORNER_SIDE_CUT = math.sqrt(_BOSS_R**2 - (RAIL_W_SIDE / 2.0) ** 2)  # 14.623
CORNER_FR_CUT = math.sqrt(_BOSS_R**2 - (RAIL_W_FR / 2.0) ** 2)  # 12.052
CORNER_CROP_OVERRUN = 1.0


def _printed_limit(value: float, places: int, sign: float) -> float:
    """``value`` as the sheet prints it at ``places``, ``sign`` bands out."""
    return printed_limit(value, places, sign)


def _printed_nominal(value: float, places: int) -> float:
    """``value`` as the sheet prints it at ``places``, in mm."""
    lower, upper = printed_deviations(value, places, unit=UNIT)
    return value + (lower + upper) / 2.0


def _tan(deg: float) -> float:
    return math.tan(math.radians(deg))


DRAFT_T_MIN = _tan(DRAFT_DEG_MIN)  # 1°, the shallowest taken-out face
DRAFT_T_MAX = _tan(DRAFT_DEG_MAX)  # 3°, the steepest face
DRAFT_T_ADDED_MIN = _tan(DRAFT_ADDED_DEG_MIN)  # 2°, an added face's least


def _cast_limit(value: float, sign: float) -> float:
    """``value`` at the far (``sign`` > 0) or near limit of its as-cast band
    (owner ruling B2: ±.03 on every printed dimension with an as-cast end)."""
    return value + math.copysign(AS_CAST_BAND, sign)


# The barrels are taken out: the least Ø1.77 stands on the faced top plane
# and narrows below it, steepest at 3°, to the flange underside.
CORNER_CROP_BOSS_R_TOP_MIN = _cast_limit(BOSS_DIA, -1.0) / 2.0  # 22.098
CORNER_CROP_BOSS_R_MIN = CORNER_CROP_BOSS_R_TOP_MIN - FLANGE * DRAFT_T_MAX  # 21.672


def _cast_face_offsets(extent: float, pitch: float) -> tuple[float, float]:
    """Least and greatest offset of an outer flange face from its boss axis on
    the faced top.

    The plan centres the rail flange extents on the socket pattern, so each
    outer face stands half the extent less half the socket pitch off its
    boss's axis.  Face and barrel are one pattern's: half the extent's
    as-cast band at each face, plus the barrel's own as-cast station.
    """
    offset = (extent - pitch) / 2.0
    return offset - AS_CAST_BAND, offset + AS_CAST_BAND


CORNER_CROP_FACE_OFFSETS = {
    "side": _cast_face_offsets(2.0 * OUTER_X, 2.0 * COLUMN_X),  # 16.383 .. 17.907
    "front/rear": _cast_face_offsets(
        2.0 * OUTER_Z, 2.0 * abs(FRONT_COLUMN_Z)
    ),  # 18.288 .. 19.812
}
# On the flange underside the taken-out faces have receded at least their
# 1° lean over the flange; the chord's ends stand where those farthest faces
# cross the smallest barrel there.
_CROP_SIDE_FACE_MAX = CORNER_CROP_FACE_OFFSETS["side"][1] - FLANGE * DRAFT_T_MIN
_CROP_FR_FACE_MAX = CORNER_CROP_FACE_OFFSETS["front/rear"][1] - FLANGE * DRAFT_T_MIN
# The chord's ends, as plan offsets (x, z) from the boss axis outward.
_CROP_SIDE_END = (
    _CROP_SIDE_FACE_MAX,
    math.sqrt(CORNER_CROP_BOSS_R_MIN**2 - _CROP_SIDE_FACE_MAX**2),
)
_CROP_FR_END = (
    math.sqrt(CORNER_CROP_BOSS_R_MIN**2 - _CROP_FR_FACE_MAX**2),
    _CROP_FR_FACE_MAX,
)
_CROP_SLOPE = (_CROP_FR_END[1] - _CROP_SIDE_END[1]) / (
    _CROP_SIDE_END[0] - _CROP_FR_END[0]
)


def _crop_chord_z(x: float) -> float:
    """The chord's offset from the boss axis along z where it crosses x."""
    return _CROP_SIDE_END[1] - (x - _CROP_SIDE_END[0]) * _CROP_SLOPE


def _crop_chord_x(z: float) -> float:
    """The chord's offset from the boss axis along x where it crosses z."""
    return _CROP_FR_END[0] - (z - _CROP_FR_END[1]) / _CROP_SLOPE


# The sketched triangle: apex past the farthest plan corner on the faced top,
# then the chord carried past the farthest side and front/rear faces.
_CROP_APEX = (
    CORNER_CROP_FACE_OFFSETS["side"][1] + CORNER_CROP_OVERRUN,
    CORNER_CROP_FACE_OFFSETS["front/rear"][1] + CORNER_CROP_OVERRUN,
)
CORNER_CROP_TRIANGLE = (
    _CROP_APEX,
    (_CROP_APEX[0], _crop_chord_z(_CROP_APEX[0])),
    (_crop_chord_x(_CROP_APEX[1]), _CROP_APEX[1]),
)
# The printed web stays clear of the triangle at every height: its outer
# face stands at most half the thickest web, its median's offset and its
# steepest added lean at the flange underside off the boss axis, and the
# chord passes outside that web corner.
CORNER_CROP_WEB_FACE_MAX = (
    _cast_limit(WEB_T, 1.0) / 2.0
    + RAIL_WEB_POSITION_ZONE / 2.0
    + POCKET_H * DRAFT_T_MAX
)  # 9.106
# Every printed face position, on the faced top and on the flange
# underside, crosses the chord inside that level's smallest barrel.
_CROP_LEVELS = (
    (CORNER_CROP_BOSS_R_TOP_MIN, 0.0, 0.0),
    (CORNER_CROP_BOSS_R_MIN, FLANGE * DRAFT_T_MAX, FLANGE * DRAFT_T_MIN),
)
if not (
    math.hypot(RAIL_W_SIDE / 2.0, RAIL_W_FR / 2.0) > BOSS_DIA / 2.0
    and all(
        math.hypot(side - recede, _crop_chord_z(side - recede)) <= radius + 1e-9
        and math.hypot(_crop_chord_x(fr - recede), fr - recede) <= radius + 1e-9
        for radius, steep, shallow in _CROP_LEVELS
        for recede in (steep, shallow)
        for side in CORNER_CROP_FACE_OFFSETS["side"]
        for fr in CORNER_CROP_FACE_OFFSETS["front/rear"]
    )
    and _crop_chord_z(CORNER_CROP_WEB_FACE_MAX) > CORNER_CROP_WEB_FACE_MAX
):
    raise AssertionError(
        "flange corner crop needs a plan corner outside the barrel, its chord"
        " inside the smallest printed barrel at every printed outer face and"
        " the triangle clear of the printed web"
    )

THROUGH_CUT_DEPTH = 110.0  # mid-plane total; > boss stack (47.3)

# --- Edge finishing ----------------------------------------------------------
# Convention (2026-08-03): CHAMFER external edges, FILLET internal wall
# junctions. User ruling 2026-10-14: the base's 1/16 in x 45 (EDGE_CHAMFER,
# the spec's) on EVERY external convex edge, top and bottom, except where an
# edge cannot take it (_external_edge_breaks).
ROOT_FILLET_R = 3.048  # .12 internal web/flange T-root blends (cast root, ch19 img04)
# The sheet prints the leg at the top rim break's places (.06 at .XX, the
# non-functional break's grid) under that row's band: every guard charges the
# printed worst leg (1.778), never the model's; picks and volumes use the model's.
_EDGE_BREAK_PLACES = DRAWING_REFERENCE_PRECISION["top rim chamfer"]
EDGE_BREAK_PRINTED = _printed_nominal(EDGE_CHAMFER, _EDGE_BREAK_PLACES)  # 1.524
EDGE_BREAK_PRINTED_MAX = _printed_limit(EDGE_CHAMFER, _EDGE_BREAK_PLACES, 1.0)  # 1.778
# Least land two separate edge-break features may leave between their faces.
EDGE_BREAK_SLIVER_MIN = 0.1
# Print-worst reach of a finished edge-break band into the underside: the
# edge off its nominal by two as-cast bands (as the pocket end: its station
# from the front socket and its chained length) and the printed worst leg.
_EDGE_LOCATION_BAND = 2.0 * AS_CAST_BAND
KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE = 0.5
# Owner ruling 2026-11-07 (RV-04 rescoped to the edges the .06 break fits):
# the model leaves the edges _external_edge_breaks does not pick unbroken at
# .06; the title block's .010 break applies, as a radius or a chamfer at its
# largest.  It stays inside the knife seats' edge-break clearance, so a seat
# over the crossbar's front side bottoms or a gusset hypotenuse still bears
# on flat face where the .06 bands are kept off it.
TITLE_BLOCK_EDGE_BREAK_MAX = max(
    edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT)
)  # 0.254
if TITLE_BLOCK_EDGE_BREAK_MAX >= KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE:
    raise AssertionError(
        f"the title block's {TITLE_BLOCK_EDGE_BREAK_MAX:g} edge break reaches the"
        f" knife seats' {KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE:g} edge-break clearance"
    )
BORE_CHAMFER = 0.762  # .03 note 9: x 45 TOP-end bore lead-ins (non-functional); low ends take the title block's .010 break
# Owner ruling B4: the set boss's cast face stands .95 from the bore axis on
# the faced top (its as-cast band) and recedes below it at its taken-out
# draft, while the machined spot face prints .83 (.XX).  The spot face's
# deepest point, the axis low in its band and the widest spot, sits on the
# least stock at the steepest draft; that stock stays positive.
_SET_SPOT_R_MAX = (
    HUB_SET_SPOT_DIA
    + PRINTED_LINEAR_BAND_MM[DRAWING_PRECISION["SetSpotProfile"]["SetSpotDia"]]
) / 2.0  # 5.08
_SET_AXIS_BAND = PRINTED_LINEAR_BAND_MM[
    DRAWING_REFERENCE_PRECISION["set screw axis from rail top"]
]
SET_SPOT_STOCK_MIN = (
    _cast_limit(HUB_SET_BOSS_FROM_AXIS, -1.0)
    - (SCREW_AXIS_BELOW_RAIL_TOP + _SET_AXIS_BAND + _SET_SPOT_R_MAX) * DRAFT_T_MAX
    - (HUB_SET_SPOT_FROM_AXIS + PRINTED_LINEAR_BAND_MM[HUB_SET_SPOT_PLACES])
)  # 0.794, .031
if SET_SPOT_STOCK_MIN <= 0.0:
    raise AssertionError(
        f"set-screw spot face has no stock under the cast face: {SET_SPOT_STOCK_MIN:.3f}"
    )
# The spot face keeps a land inside its cast face's edge breaks
# (drawing-guidelines.md rule 17 (walls and webs)): each break's printed worst
# leg past the least stock reaches the spot's floor, round the widest spot
# across the narrowest boss and from the faced top and underside.
_SET_SPOT_BREAK_REACH = EDGE_BREAK_PRINTED_MAX - SET_SPOT_STOCK_MIN  # 0.984
SET_SPOT_LAND_MIN = {
    "across the boss": _cast_limit(HUB_SET_BOSS_W, -1.0) / 2.0
    - _SET_SPOT_BREAK_REACH
    - _SET_SPOT_R_MAX,  # 2.572
    "under the faced top": SCREW_AXIS_BELOW_RAIL_TOP
    - _SET_AXIS_BAND
    - EDGE_BREAK_PRINTED_MAX
    - _SET_SPOT_R_MAX,
    "over the faced underside": RING_HEIGHT
    - SCREW_AXIS_BELOW_RAIL_TOP
    - _SET_AXIS_BAND
    - EDGE_BREAK_PRINTED_MAX
    - _SET_SPOT_R_MAX,
}
for _label, _land in SET_SPOT_LAND_MIN.items():
    if _land < EDGE_BREAK_SLIVER_MIN:
        raise AssertionError(
            f"set-screw spot face breaks into the boss edge break {_label}: "
            f"land {_land:.3f}"
        )
# Owner ruling B4: the full-height boss's face projects past the east corner
# bosses' tangent line by .065 nominal (the hole-table origin is the west/rear
# F-G corner, so nothing locates on the east tangent any more): negative.
SET_BOSS_FACE_TANGENT_MARGIN = BOSS_DIA / 2.0 - HUB_SET_BOSS_FROM_AXIS  # -1.651
if abs(GOOSENECK_X + COLUMN_X) > 1e-9:
    raise AssertionError("the set-screw boss is not on the east bosses' axis line")
# Edge-break eligibility is judged at the print's limits, not on the nominal
# model: a conforming casting may carry any printed size, so the model
# leaves an edge unbroken at .06 wherever some printed extreme leaves it too
# short, or its face too narrow, for the printed worst break
# (_external_edge_breaks); the title block's .010 break applies there.
# A T flange's underside break needs that leg and the sliver land on the
# flat between the flange's outer face and its R.12 web root, at the print's
# limits (owner rulings B1/B2): the narrowest flange, its rims taken out at
# the steepest draft; the thickest web at its steepest added lean; the web's
# median off its rail's socket-axis line (⌖.06) and the flange's faces off
# that line by half their band; the largest root.  The rails keep 3.04 and
# 4.94, the .99-wide crossbar none, so its flange undersides stay unbroken.
_ROOT_R_PRINTED_MAX = _cast_limit(ROOT_FILLET_R, 1.0)  # 3.810


def _t_flange_shelf_printed_min(width: float, median_offset: float) -> float:
    flange_half = _cast_limit(width, -1.0) / 2.0 - FLANGE * DRAFT_T_MAX
    web_half = _cast_limit(WEB_T, 1.0) / 2.0 + POCKET_H * DRAFT_T_MAX
    return flange_half - web_half - median_offset - _ROOT_R_PRINTED_MAX


_RAIL_WEB_MEDIAN_OFFSET = RAIL_WEB_POSITION_ZONE / 2.0 + AS_CAST_BAND / 2.0
T_FLANGE_SHELF_PRINTED_MIN = {
    "side rail": _t_flange_shelf_printed_min(RAIL_W_SIDE, _RAIL_WEB_MEDIAN_OFFSET),
    "front/rear rail": _t_flange_shelf_printed_min(RAIL_W_FR, _RAIL_WEB_MEDIAN_OFFSET),
    "crossbar": _t_flange_shelf_printed_min(BAR_X1 - BAR_X0, AS_CAST_BAND),
}
# The hub rib's outer bottom either side of the set-screw boss runs 4.953
# nominal; the narrowest rib (centred on the bore) less the widest boss
# (centred on the tap, on the bore axis), halved, is 4.191 on the underside
# where both stand at their nominals: over the printed worst legs of the
# breaks at both its ends (the rib's corner and side bottom, the boss's side
# bottom), so it is broken and joins the boss's breaks to the rib's.
HUB_RIB_STUB_PRINTED_MIN = (
    _cast_limit(HUB_RIB_W, -1.0) - _cast_limit(HUB_SET_BOSS_W, 1.0)
) / 2.0  # 4.191
HUB_RIB_STUB_LAND_MIN = HUB_RIB_STUB_PRINTED_MIN - EDGE_BREAK_PRINTED_MAX  # 2.413
if HUB_RIB_STUB_LAND_MIN < EDGE_BREAK_SLIVER_MIN:
    raise AssertionError(
        "hub rib corner break runs into the set-screw boss's side: land "
        f"{HUB_RIB_STUB_LAND_MIN:.3f}"
    )

if abs(FRONT_COLUMN_Z + REAR_COLUMN_Z) > 1e-12 or abs(FRAME_CENTER_Z) > 1e-12:
    raise AssertionError("top-frame assumes a symmetric column span about z 0")
if STUD_Z_REAR + HANGER_WASHER.OD_MAX / 2.0 >= INNER_Z + GUSSET:
    raise AssertionError("rear hanger washer overhangs the junction material")
# Dowel press reams (drawing-guidelines.md rule 17 (walls and webs),
# print-worst): the largest ream keeps a wall to the crossbar's +X face and
# to the largest drilled screw clearance hole, the ream at its .XXX station
# limit from its #10 axis (HANGER_PIN_X_TOL; Owner ruling 2026-11-08
# (Pedro), #2144 item 11.3: the -X ream is gone), the axis within its
# ⌖.010|D centring of D (owner ruling 2026-11-06).  Its blind floor stays
# below the finished top (the knockouts' own walls follow the washer stack
# below).  The #10 holes are drilled from the faced underside and the reams
# cut from it.  Every hole's drift is greatest at the deepest printed floor;
# charge both axes toward each other.
_PIN_HOLE_MAX_R = HANGER_PIN_HOLE_DIA_MAX / 2.0
_CLEARANCE_MAX_R = HANGER_CLEARANCE_DIA_MAX / 2.0
_REAM_FLOOR_DEPTH_MAX = HANGER_PIN_HOLE_DEPTH + HANGER_PIN_HOLE_DEPTH_TOL  # 12.8
HANGER_DRIFT_AT_REAM_FLOOR = DRILL_DRIFT_PER_MM * _REAM_FLOOR_DEPTH_MAX  # 0.067
# Datum D is the median plane of BOTH as-cast crossbar side faces (owner
# ruling B5), so a face stands half the width's least printed size from it,
# whatever the bar's station; on the underside, where the added draft leaves
# the bar its narrowest.
HANGER_BAR_HALF_WIDTH_MIN = _cast_limit(BAR_X1 - BAR_X0, -1.0) / 2.0  # 12.192
# A ream axis's least reach to its crossbar face: its #10 axis within the
# ⌖.010|D centring of D, the ream at its .XXX station from that axis.
_REAM_BAR_FACE_REACH = (
    HANGER_BAR_HALF_WIDTH_MIN
    - HANGER_CROSSBAR_CENTER_TOL
    - HANGER_PIN_X
    - HANGER_PIN_X_TOL
)  # 4.572
PIN_HOLE_BAR_WALL = (
    _REAM_BAR_FACE_REACH - _PIN_HOLE_MAX_R - HANGER_DRIFT_AT_REAM_FLOOR
)  # 2.927
PIN_HOLE_SCREW_WALL = (
    HANGER_PIN_X
    - HANGER_PIN_X_TOL
    - _PIN_HOLE_MAX_R
    - _CLEARANCE_MAX_R
    - 2.0 * HANGER_DRIFT_AT_REAM_FLOOR
)  # 2.660
# At the underside mouth the ream has not drifted, but the crossbar's front
# side bottom it stands beside takes the title block's break there.
PIN_HOLE_MOUTH_BAR_WALL = (
    _REAM_BAR_FACE_REACH - _PIN_HOLE_MAX_R - TITLE_BLOCK_EDGE_BREAK_MAX
)  # 2.737
PIN_HOLE_FLOOR_MARGIN = HANGER_GRIP - HANGER_GRIP_TOL - _REAM_FLOOR_DEPTH_MAX
for _label, _value in (
    ("ream wall to the crossbar side face", PIN_HOLE_BAR_WALL),
    ("ream mouth wall inside the crossbar side's edge break", PIN_HOLE_MOUTH_BAR_WALL),
    ("ream wall to the screw clearance hole", PIN_HOLE_SCREW_WALL),
    ("ream floor below the finished top", PIN_HOLE_FLOOR_MARGIN),
):
    if _value < WALL_TARGET_MM:
        raise AssertionError(
            f"knife-mount dowel press {_label}: {_value:.3f} after drill drift"
        )
# Crossbar pockets (drawing-guidelines.md rule 17 (walls and webs), print-worst): every hanger hole stays in the
# full-depth junction beyond the pocket end. The nearer (front) station
# keeps its wall in z with the station at its .XXX band from the socket
# axes (owner ruling D2: the hangers print from the socket axes), each pocket
# end two as-cast bands out: the sheet locates the front end from the front
# socket axis and chains the length to the rear end, so the rear end carries
# both bands.  The pockets' ends stand at their nominal on the underside and
# close in above it.  Then the largest printed hole and the 0.3 deg drill
# drift from the faced underside: the through hole's longest path to the
# highest pocket roof is charged.
HANGER_STATION_BAND = PRINTED_LINEAR_BAND_MM[3]
_POCKET_STATION = min(abs(STUD_Z_FRONT), abs(STUD_Z_REAR)) - HANGER_STATION_BAND
_POCKET_END = BAR_POCKET_Z + 2.0 * AS_CAST_BAND  # 70.358
# The plain through hole's drift is greatest at the finished top, its
# farthest printed height above the underside entry.
HANGER_DRIFT_AT_TOP = DRILL_DRIFT_PER_MM * (HANGER_GRIP + HANGER_GRIP_TOL)
# Fore/aft outer rail faces on the faced top, where the taken-out rims stand
# at their nominal: the least as-cast width, half the band again for the
# face's own station, and the socket pattern's Ø.010 refinement for the far
# face measured from the other socket row.
_FR_RAIL_HALF_WIDTH_MIN = _cast_limit(RAIL_W_FR, -1.0) / 2.0 - AS_CAST_BAND / 2.0
# Match the assembly's tap/dowel mismatch without importing a COM recipe
# (build_sm_summing_assembly.HANGER_SCREW_MISMATCH; Owner ruling 2026-11-08
# (Pedro), #2144 item 11.3, scheme S1).  Along the dowel line: the ream's
# .XXX station, the tap's position-zone radius (KNIFE_MOUNT.STUD_TAP_POSITION_TOL
# / 2, ⌖|A|B|C▷: owner ruling 2026-11-10 (Pedro), #2334), B's slip on its pin and B's datum simulator t/2 (codjiflo round
# 5).  Across it: the ream's implied-zero .XXX "SAME Z", the same three
# block terms, and the turn the gauge bar gives the block about its dowel,
# which moves the tap across by PIN_HOLE_X times the bar line's yaw
# (HANGER_BAR_YAW_SHIFT).  The bar line passes through both bores, each off
# its station by the hole's ⌖.010|D centring to datum D (owner ruling
# 2026-11-06), the ream's .XXX station, B's slip and simulator and the
# bore's ⌖Ø.008|A|B radius, at opposite limits over the stations' spacing.
_KNIFE_DOWEL_SLIP_MAX = KNIFE_DOWEL.SLIP_CLEARANCE_MAX
_KNIFE_DOWEL_HOLE_PERP = KNIFE_MOUNT.DOWEL_HOLE_PERPENDICULARITY_TOL
_HANGER_BLOCK_SHIFT = (
    HANGER_PIN_X_TOL
    + KNIFE_MOUNT.STUD_TAP_POSITION_TOL / 2.0
    + _KNIFE_DOWEL_SLIP_MAX / 2.0
    + _KNIFE_DOWEL_HOLE_PERP / 2.0
)  # 0.2489
_HANGER_BORE_LINE_OFFSET = (
    HANGER_CROSSBAR_CENTER_TOL
    + HANGER_PIN_X_TOL
    + _KNIFE_DOWEL_SLIP_MAX / 2.0
    + _KNIFE_DOWEL_HOLE_PERP / 2.0
    + KNIFE_MOUNT.KNIFE_BORE_POSITION_TOL / 2.0
)  # 0.4140, each station
# The bar's own diametral clearance in each bore turns each block on it a
# further atan(clearance / shortest bore) (build_sm_summing_assembly
# KNIFE_BAR_PLAY_YAW_DEG, owner review of #2334); the tap turns with it.
_HANGER_BAR_PLAY_YAW = math.atan(
    (2.0 * KNIFE_MOUNT.BORE_R_MAX - KNIFE_MOUNT.KNIFE_GAUGE_BAR_DIA_MIN)
    / (KNIFE_MOUNT.SUPPORT_Z_THICK - KNIFE_MOUNT.BLOCK_SIZE_TOL)
)
HANGER_BAR_YAW_SHIFT = HANGER_PIN_X * math.tan(
    math.atan(2.0 * _HANGER_BORE_LINE_OFFSET / (STUD_Z_REAR - STUD_Z_FRONT))
    + _HANGER_BAR_PLAY_YAW
)  # 0.0602
HANGER_SEAT_BOLT_MISMATCH = math.hypot(
    _HANGER_BLOCK_SHIFT, _HANGER_BLOCK_SHIFT + HANGER_BAR_YAW_SHIFT
)
# The washer's centre wanders from the nominal axis by its own float on the
# bolt, the bolt's seat mismatch, the hole's drift at the top and the
# washer's own OD/ID runout.
HANGER_WASHER_OFFSET_MAX = (
    HANGER_WASHER_FLOAT_MAX
    + HANGER_SEAT_BOLT_MISMATCH
    + HANGER_DRIFT_AT_TOP
    + HANGER_WASHER.OD_ID_RUNOUT_MAX
)
_HANGER_WASHER_REACH = HANGER_WASHER.OD_MAX / 2.0 + HANGER_WASHER_OFFSET_MAX
# Each washer bears wholly on the faced top, inside the crossbar's top-rim
# break at its printed worst leg: conservatively the plain bar's narrowest
# printed half width, ignoring the gusset spread at both stations.
HANGER_WASHER_BAR_TOP_MARGIN = (
    HANGER_BAR_HALF_WIDTH_MIN
    - HANGER_CROSSBAR_CENTER_TOL
    - EDGE_BREAK_PRINTED_MAX
    - _HANGER_WASHER_REACH
)
_HANGER_WASHER_Z_REACH = HANGER_STATION_BAND + _HANGER_WASHER_REACH
_HANGER_WASHER_FRONT_END_WALL = min(
    station - FRONT_COLUMN_Z + _FR_RAIL_HALF_WIDTH_MIN - _HANGER_WASHER_Z_REACH
    for station in (STUD_Z_FRONT, STUD_Z_REAR)
)
HANGER_WASHER_OUTER_END_WALL = min(
    _HANGER_WASHER_FRONT_END_WALL,
    *(
        REAR_COLUMN_Z
        - station
        + _FR_RAIL_HALF_WIDTH_MIN
        - SOCKET_PATTERN_REFINEMENT_ZONE
        - _HANGER_WASHER_Z_REACH
        for station in (STUD_Z_FRONT, STUD_Z_REAR)
    ),
)
# Pure full-annulus contact geometry, not a preload/material strength claim.
HANGER_WASHER_BEARING_MIN = (
    HANGER_WASHER_CONCENTRIC_ANNULUS_MIN - HANGER_WASHER_OFFSET_MAX
)
for _label, _value, _minimum in (
    (
        "washer full support inside the crossbar top breaks",
        HANGER_WASHER_BAR_TOP_MARGIN,
        0.0,
    ),
    ("washer to outer rail ends", HANGER_WASHER_OUTER_END_WALL, WALL_TARGET_MM),
    ("washer continuous bearing annulus", HANGER_WASHER_BEARING_MIN, 0.0),
):
    if _value < _minimum:
        raise AssertionError(f"knife-hanger {_label}: {_value:.3f} below {_minimum:g}")
# The knockouts (fr_top_frame_spec.HANGER_KNOCKOUT_SPEC), drilled up from
# each ream's floor and drawn on the ream's axis: the ream's floor centre
# stands off its station by the ream's own drift there, the knockout off
# that centre by the drawn coaxiality's implied ±.005 along each axis
# (owner ruling 2026-10-27, no setup note), and it drifts further over its
# longest printed run, so it stands farthest off its station where it
# leaves the faced top.  Each wall here is judged along one axis, the ream
# at its .XXX station limit (HANGER_PIN_X_TOL).  Toward the #10 hole, whose
# underside-entry drift is also greatest at the top, both holes' maxima are
# charged at once.
HANGER_KNOCKOUT_DRIFT = DRILL_DRIFT_PER_MM * HANGER_KNOCKOUT_LENGTH_MAX  # 0.135
HANGER_KNOCKOUT_SHIFT_AT_TOP = (
    HANGER_DRIFT_AT_REAM_FLOOR + HANGER_KNOCKOUT_COAXIAL_TOL + HANGER_KNOCKOUT_DRIFT
)  # 0.332
_KNOCKOUT_MAX_R = HANGER_KNOCKOUT_DIA_MAX / 2.0
_KNOCKOUT_NEAR_AXIS_MIN = (
    HANGER_PIN_X - HANGER_PIN_X_TOL - HANGER_KNOCKOUT_SHIFT_AT_TOP
)  # 7.172
KNOCKOUT_BAR_WALL = (
    _REAM_BAR_FACE_REACH - _KNOCKOUT_MAX_R - HANGER_KNOCKOUT_SHIFT_AT_TOP
)
KNOCKOUT_SCREW_WALL = (
    _KNOCKOUT_NEAR_AXIS_MIN
    - _KNOCKOUT_MAX_R
    - _CLEARANCE_MAX_R
    - HANGER_DRIFT_AT_TOP
)
# Where it leaves the faced top the knockout stays off the crossbar's
# top-rim break at its printed worst leg (the washer stack's bar reach).
KNOCKOUT_TOP_BREAK_LAND = KNOCKOUT_BAR_WALL - EDGE_BREAK_PRINTED_MAX
# The knockout exits under the MHA-SM-VN-54 washer (its reach from the bolt
# axis covers the 7.62 station), so the washer bears on a continuous ring
# INSIDE the knockouts: round the washer's own centre, from the farther of
# its bore and the #10 hole's far edge out to the nearer of its rim and the
# nearest knockout's near edge.  The washer centre wanders from both the
# hole and the nominal axis by HANGER_WASHER_OFFSET_MAX; the knockouts stand
# at their station limits from that axis.
HANGER_WASHER_KNOCKOUT_RING_MIN = min(
    HANGER_WASHER.OD_MIN / 2.0,
    _KNOCKOUT_NEAR_AXIS_MIN - _KNOCKOUT_MAX_R - HANGER_WASHER_OFFSET_MAX,
) - max(
    HANGER_WASHER.ID_MAX / 2.0,
    _CLEARANCE_MAX_R + HANGER_WASHER_OFFSET_MAX,
)
for _label, _value in (
    ("knockout wall to the crossbar side face", KNOCKOUT_BAR_WALL),
    ("knockout wall to the screw clearance hole", KNOCKOUT_SCREW_WALL),
):
    if _value < WALL_TARGET_MM:
        raise AssertionError(
            f"knife-mount dowel {_label}: {_value:.3f} after drill drift"
        )
for _label, _value in (
    ("knockout land inside the crossbar top-rim break", KNOCKOUT_TOP_BREAK_LAND),
    ("washer bearing ring inside the knockouts", HANGER_WASHER_KNOCKOUT_RING_MIN),
):
    if _value <= 0.0:
        raise AssertionError(
            f"knife-mount dowel {_label}: {_value:.3f}, no positive margin"
        )
BAR_POCKET_HOLE_WALLS = {
    "hanger clearance hole": _POCKET_STATION
    - _CLEARANCE_MAX_R
    - DRILL_DRIFT_PER_MM
    * (HANGER_GRIP + HANGER_GRIP_TOL - _cast_limit(FLANGE, -1.0))
    - _POCKET_END,
    "dowel ream": _POCKET_STATION
    - HANGER_PIN_X_TOL  # SAME Z at the ream's general .XXX band
    - _PIN_HOLE_MAX_R
    - HANGER_DRIFT_AT_REAM_FLOOR
    - _POCKET_END,
    # The knockout passes the pocket end above the ream floor, at most its
    # shift at the top off its ream's station.
    "dowel knockout": _POCKET_STATION
    - HANGER_PIN_X_TOL
    - _KNOCKOUT_MAX_R
    - HANGER_KNOCKOUT_SHIFT_AT_TOP
    - _POCKET_END,
}
for _label, _value in BAR_POCKET_HOLE_WALLS.items():
    if _value < WALL_TARGET_MM:
        raise AssertionError(
            f"crossbar pocket leaves {_value:.3f} mm to the {_label} at the printed bands"
        )


# Knife-mount top seats (drawing-guidelines.md rule 17 (walls and webs), print-worst): each block's footprint on
# the faced crossbar underside, (x, z), is the convex hull of its corners over
# every printed extreme -- its round dowel hole at datum D's x and the
# hanger's z stations from the sockets (D from the left bosses' tangent,
# sheet 3's boss-corner origin), the #10 axis off D by its ⌖.010|D
# centring, the round-hole pin off that axis by its .XXX station along the
# line and its implied-zero .XXX "SAME Z" across it, and half the dowel
# slip (codjiflo round 2); the block's +X face 5.65 (.XX) off its round
# hole, its widest .X width, the worse .X row-to-face reach either side;
# the whole turned through the title-block angle about the round dowel,
# which also covers the yaw the MHA-SM-00 gauge bar sets
# (HANGER_BAR_YAW_SHIFT's turn with the bar's play, under 0.5 deg).  Owner ruling 2026-11-08
# (Pedro), #2144 item 11.3: one dowel, so the block fits one way round
# only, its round hole (datum B) on the ream's pin.
# _external_edge_breaks keeps every finished edge-break band 0.5 off both hulls.
# The front hull overhangs the crossbar's side bottoms short of the gusset
# legs (the 25.4-wide block on the 25.146-wide bar); the model leaves those
# unbroken at .06 and the title block's .010 break applies
# (TITLE_BLOCK_EDGE_BREAK_MAX, inside the 0.5 clearance).
def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Counter-clockwise convex hull (monotone chain) of plan points."""
    ordered = sorted(set(points))

    def turn(o, a, b) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    upper: list[tuple[float, float]] = []
    for point in ordered:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    for point in reversed(ordered):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _knife_seat_footprint(station_z: float) -> list[tuple[float, float]]:
    """Print-worst (x, z) hull of one knife-mount block's top seat on its
    one pin."""
    slip = KNIFE_DOWEL.SLIP_CLEARANCE_MAX / 2.0
    # Along the line: D from the west bosses' tangent (its as-cast band,
    # owner ruling D2), the #10 axis off D by its centring, the ream off that
    # axis; across it: the screw axis's .XXX station from the socket axes,
    # the ream off its line.
    x_band = AS_CAST_BAND + HANGER_CROSSBAR_CENTER_TOL + HANGER_PIN_X_TOL + slip
    z_band = HANGER_STATION_BAND + HANGER_PIN_X_TOL + slip
    reach = max(
        KNIFE_MOUNT.HOLE_ROW_FACE_DISTANCE + KNIFE_MOUNT.HOLE_ROW_FACE_TOL,
        (KNIFE_MOUNT.SUPPORT_Z_THICK + KNIFE_MOUNT.BLOCK_SIZE_TOL)
        - (KNIFE_MOUNT.HOLE_ROW_FACE_DISTANCE - KNIFE_MOUNT.HOLE_ROW_FACE_TOL),
    )
    width = 2.0 * KNIFE_MOUNT.BLK_HALF_X + KNIFE_MOUNT.BLOCK_SIZE_TOL
    turn = math.radians(angular_band_deg())
    corners = []
    for dx in (-x_band, x_band):
        for dz in (-z_band, z_band):
            for side in (
                KNIFE_MOUNT.PIN_HOLE_SIDE_DISTANCE - KNIFE_MOUNT.PIN_HOLE_SIDE_TOL,
                KNIFE_MOUNT.PIN_HOLE_SIDE_DISTANCE + KNIFE_MOUNT.PIN_HOLE_SIDE_TOL,
            ):
                for u in (side, side - width):
                    for v in (-reach, reach):
                        for t in (-turn, turn):
                            corners.append(
                                (
                                    PIN_HOLE_X + dx + u * math.cos(t) - v * math.sin(t),
                                    station_z + dz + u * math.sin(t) + v * math.cos(t),
                                )
                            )
    return _convex_hull(corners)


KNIFE_SEAT_FOOTPRINTS = {
    "front": _knife_seat_footprint(STUD_Z_FRONT),
    "rear": _knife_seat_footprint(STUD_Z_REAR),
}
if HUB_GUSSET_T / 2.0 > WEB_T / 2.0:
    raise AssertionError("hub V-gussets escape the east-rail web")
# The hub boss's chord at each rib side face stays inside the east-rail web,
# so each rib-side bottom and its web bottom meet at one clean vertex that a
# single edge-break feature blends, with no boss-top sliver between their ends (at
# 27 wide the boss poked 0.038 past the web there).  NOMINAL, on purpose:
# this is a native-modelling guard on the CAD's topology, not a fit -- on a
# real casting the printed bands only move where the hand-broken edges blend.
HUB_BOSS_RIB_CHORD_MIN_MARGIN = 0.5
HUB_BOSS_RIB_CHORD_MARGIN = WEB_T / 2.0 - math.sqrt(
    max((HUB_BOSS_DIA / 2.0) ** 2 - (HUB_RIB_W / 2.0) ** 2, 0.0)
)
if HUB_BOSS_RIB_CHORD_MARGIN < HUB_BOSS_RIB_CHORD_MIN_MARGIN:
    raise AssertionError(
        f"hub boss chord at the rib sides leaves {HUB_BOSS_RIB_CHORD_MARGIN:.3f}"
        f" mm inside the east-rail web (needs {HUB_BOSS_RIB_CHORD_MIN_MARGIN:g})"
    )
# The unified tap table rounds its nominal major; the actual stock major
# must also fit. Use the larger diameter for every receiver-wall guard.
KEEPER_TAP_THREAD_MAJOR_DIA = max(
    THREAD_MAJOR_MM[KEEPER_TAP_SPEC.size], KEEPER_SCREW_MAJOR_DIA
)
if abs(KEEPER_TAP_X - COLUMN_X) + KEEPER_TAP_THREAD_MAJOR_DIA / 2.0 > WEB_T / 2.0:
    raise AssertionError("keeper taps break out of the west-rail web")
# Flush counterbore (drawing-guidelines.md rule 17 (walls and webs),
# print-worst).  The barrel is taken out (owner ruling B1): it narrows below
# the faced top, so the mouth's lowest point is where the narrowest barrel
# section meets the counterbore's rim, searched round the rim.  The head top
# must stay below it.  The barrel prints Ø1.77 ±.03 on the faced top, the
# counterbore .X, the floor offset from the socket axis and the axis below
# the boss top .XX (machined to machined, B3): the shallowest recess takes
# the smallest barrel at the steepest draft, the largest counterbore, the
# lowest axis and the most-outboard floor; the head clearance takes the
# smallest counterbore.  The offset is from the same socket axis, so socket
# position does not enter this local stack.  Owner ruling (#2333): the floor
# moved .03 deeper, .65 -> .62, to hold this at 3°.
def _counterbore_mouth_low_z(
    boss_r_top: float, draft_t: float, counterbore_r: float, axis_y: float
) -> float:
    low = math.inf
    for k in range(720):
        theta = 2.0 * math.pi * k / 720.0
        u = counterbore_r * math.cos(theta)
        r = boss_r_top - (HALF_H - (axis_y + counterbore_r * math.sin(theta))) * draft_t
        low = min(low, math.sqrt(r * r - u * u))
    return abs(FRONT_COLUMN_Z) + low


COUNTERBORE_MOUTH_LOW_Z = _counterbore_mouth_low_z(
    BOSS_DIA / 2.0, DRAFT_T, COUNTERBORE_DIA / 2.0, SCREW_AXIS_Y
)
COUNTERBORE_HEAD_RECESS = COUNTERBORE_MOUTH_LOW_Z - (
    COUNTERBORE_FLOOR + CROSS_SCREW_HEAD_H
)  # 1.050 nominal
_COUNTERBORE_DIA_PLACES = DRAWING_PRECISION["CounterboreRearProfile"]["CB1Dia"]
_COUNTERBORE_FLOOR_PLACES = DRAWING_REFERENCE_PRECISION[
    "counterbore floor from socket axis"
]
_AXIS_PLACES = DRAWING_REFERENCE_PRECISION["cross screw axis from boss top"]
COUNTERBORE_MIN_BOSS_RADIUS = _cast_limit(BOSS_DIA, -1.0) / 2.0
COUNTERBORE_MAX_RADIUS = (
    _printed_limit(COUNTERBORE_DIA, _COUNTERBORE_DIA_PLACES, 1.0) / 2.0
)
COUNTERBORE_MIN_RADIUS = (
    _printed_limit(COUNTERBORE_DIA, _COUNTERBORE_DIA_PLACES, -1.0) / 2.0
)
COUNTERBORE_MAX_FLOOR_OFFSET = _printed_limit(
    COUNTERBORE_FLOOR - abs(FRONT_COLUMN_Z), _COUNTERBORE_FLOOR_PLACES, 1.0
)
COUNTERBORE_MIN_FLOOR_OFFSET = _printed_limit(
    COUNTERBORE_FLOOR - abs(FRONT_COLUMN_Z), _COUNTERBORE_FLOOR_PLACES, -1.0
)
COUNTERBORE_PRINTED_HEAD_RECESS = _counterbore_mouth_low_z(
    COUNTERBORE_MIN_BOSS_RADIUS,
    DRAFT_T_MAX,
    COUNTERBORE_MAX_RADIUS,
    SCREW_AXIS_Y - PRINTED_LINEAR_BAND_MM[_AXIS_PLACES],
) - (abs(FRONT_COLUMN_Z) + COUNTERBORE_MAX_FLOOR_OFFSET + CROSS_SCREW_HEAD_H)
COUNTERBORE_PRINTED_HEAD_CLEARANCE = (
    COUNTERBORE_MIN_RADIUS - CROSS_SCREW_HEAD_DIA / 2.0
)  # 0.343 radial
if (
    min(COUNTERBORE_HEAD_RECESS, COUNTERBORE_PRINTED_HEAD_RECESS) <= 0.0
    or COUNTERBORE_PRINTED_HEAD_CLEARANCE <= 0.0
    or COUNTERBORE_PLANE <= COUNTERBORE_FLOOR
):
    raise AssertionError(
        "top cross-screw head stands proud of its counterbore at the printed bands"
    )
# The near casting wall between the counterbore floor and the socket bore,
# which the #10 clearance crosses: the most-inboard printed floor against
# the largest printed bore.
COUNTERBORE_PRINTED_NEAR_WALL = (
    COUNTERBORE_MIN_FLOOR_OFFSET
    - _printed_limit(BORE_DIA, DRAWING_PRECISION["BoreProfile"]["B0Dia"], 1.0) / 2.0
)  # 2.680, .105
# Cap recess to counterbore ligament: the recess's deepest, widest printed
# corner against the counterbore's outboard-most floor rim, with the tap
# axis at the high end of its station below the boss top.  The floor's
# station prints .XX and stands at .62 (TOP_SCREW_SEAT_Z): .088 over
# drawing-guidelines.md rule 17 (walls and webs)'s .080 target, as is the
# near wall's .105.  At 16.1 it left 1.518 at .X (codex review of 67d8b2c6)
# and 1.80 at .XX (080fda97).
_CAP_LIGAMENT_VERTICAL = (CAP_RECESS_FLOOR_Y - CAP_RECESS_DEPTH_BAND[0]) - (
    SCREW_AXIS_Y + PRINTED_LINEAR_BAND_MM[_AXIS_PLACES] + COUNTERBORE_MAX_RADIUS
)
if _CAP_LIGAMENT_VERTICAL < 0.0:
    raise AssertionError("the cap recess floor drops past the counterbore's top rim")
COUNTERBORE_PRINTED_CAP_LIGAMENT = math.hypot(
    COUNTERBORE_MIN_FLOOR_OFFSET - CAP_RECESS_DIAMETER_MAX / 2.0,
    _CAP_LIGAMENT_VERTICAL,
)
if min(COUNTERBORE_PRINTED_NEAR_WALL, COUNTERBORE_PRINTED_CAP_LIGAMENT) < WALL_TARGET_MM:
    raise AssertionError(
        "top cross-screw counterbore leaves under .080 to the bore or cap recess"
    )
# The machined socket and cap recess inside the as-cast barrel (owner rulings
# B1/B2, D6): the smallest barrel at its narrowest -- the lower barrel's
# bottom, the cap recess's mouth on the upper barrel's top, each at the
# steepest taken-out draft -- against the largest printed bore, its axis off
# the barrel's by the socket pattern's Ø.06 location to the cast datums.
_SOCKET_BARREL_OFFSET = SOCKET_PATTERN_LOCATION_ZONE / 2.0
SOCKET_BOSS_WALL = (
    COUNTERBORE_MIN_BOSS_RADIUS
    - (RING_HEIGHT + BOSS_BELOW) * DRAFT_T_MAX
    - _printed_limit(BORE_DIA, DRAWING_PRECISION["BoreProfile"]["B0Dia"], 1.0) / 2.0
    - _SOCKET_BARREL_OFFSET
)  # 6.272, .247
CAP_RECESS_BOSS_WALL = (
    COUNTERBORE_MIN_BOSS_RADIUS
    - BOSS_ABOVE * DRAFT_T_MAX
    - CAP_RECESS_DIAMETER_MAX / 2.0
    - _SOCKET_BARREL_OFFSET
)  # 7.278, .287
if min(SOCKET_BOSS_WALL, CAP_RECESS_BOSS_WALL) < WALL_TARGET_MM:
    raise AssertionError(
        "socket or cap recess leaves under .080 of as-cast barrel at the print's limits"
    )
# The near-wall clearance, print-worst (drawing-guidelines.md rule 17
# (walls and webs)): its largest drilled size keeps a land inside the
# smallest printed counterbore floor, and where it crosses under the cap
# recess (between the bore and the recess wall) the recess's deepest printed
# floor stays .080 above its highest crown, the axis at the high end of its
# station: land 1.65, ligament 3.38.
SIDE_CLEARANCE_MAX_RADIUS = (
    NEAR_WALL_CLEARANCE_DIAMETER + PRINTED_DRILLED_HOLE_PLUS_MM
) / 2.0
SIDE_CLEARANCE_FLOOR_LAND = COUNTERBORE_MIN_RADIUS - SIDE_CLEARANCE_MAX_RADIUS
SIDE_CLEARANCE_CAP_LIGAMENT = (CAP_RECESS_FLOOR_Y - CAP_RECESS_DEPTH_BAND[0]) - (
    SCREW_AXIS_Y + PRINTED_LINEAR_BAND_MM[_AXIS_PLACES] + SIDE_CLEARANCE_MAX_RADIUS
)
if SIDE_CLEARANCE_FLOOR_LAND <= 0.0:
    raise AssertionError("top near-wall clearance outgrows its counterbore floor")
if SIDE_CLEARANCE_CAP_LIGAMENT < WALL_TARGET_MM:
    raise AssertionError("top near-wall clearance leaves under .080 to the cap recess")
# Far-wall engagement (rule 18, print worst): fr_top_frame_spec's
# TOP_CROSS_SCREW_FAR_WALL_START_MAX is this counterbore floor's printed
# seat-to-axis stack plus the match-bored socket ceiling and the far mouth's
# edge break; the joint books the shortest stock screw and its 0.7-pitch tip.
if TOP_CROSS_SCREW_FAR_WALL_START_MAX != far_wall_start_max_mm(
    COUNTERBORE_MAX_FLOOR_OFFSET, unit=UNIT
):
    raise AssertionError("the spec's far-wall start is not this counterbore floor's")
TOP_CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT = far_wall_full_thread_min_mm(
    TOP_CROSS_SCREW_FAR_WALL_START_MAX
)  # 12.35 (2.56D); 11.72 (2.43D) at a 1.5-pitch tip
if TOP_CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT < FAR_WALL_ENGAGEMENT_FLOOR_MM:
    raise AssertionError(
        "top far casting wall engages MHA-FR-VN-53 "
        f"{TOP_CROSS_SCREW_FAR_WALL_MIN_ENGAGEMENT:.3f} mm < 1.5D at the printed bands"
    )
SIDE_TAP_THREAD_MAJOR_DIA = THREAD_MAJOR_MM[SIDE_TAP_SPEC.size]
SIDE_TAP_THREAD_END_Z = COUNTERBORE_FLOOR - CASTING_FULL_THREAD_DEPTH
SIDE_TAP_DRILL_POINT_Z = (
    COUNTERBORE_FLOOR
    - TOP_CASTING_TAP_DRILL_DEPTH
    - SIDE_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
)
# The boss's inward edge is NOT a free wall: the centred side-rail web
# continues inward at full height. For the whole far tap/drill envelope,
# |x - ColumnX| <= radius < WebT/2 and |y - axis| <= radius < HalfH - |axis|,
# so boss ∪ web supplies uninterrupted metal beyond both ends. The actual
# limiting walls are the web's x faces (and its y faces), not z=112-R22.5.
# Nominal lateral ligaments: thread major 6.477-2.413=4.064; drill
# 6.477-2.0193=4.458.
SIDE_TAP_THREAD_WALL_MARGIN = WEB_T / 2.0 - SIDE_TAP_THREAD_MAJOR_DIA / 2.0
SIDE_TAP_DRILL_WALL_MARGIN = WEB_T / 2.0 - SIDE_TAP_DRILL_DIA / 2.0
if min(SIDE_TAP_THREAD_WALL_MARGIN, SIDE_TAP_DRILL_WALL_MARGIN) < WALL_TARGET_MM:
    raise AssertionError("top cross-tap leaves less than .080 of side-rail web")
if not (
    0.0 < SIDE_TAP_DRILL_POINT_Z < SIDE_TAP_THREAD_END_Z < WEB_IN_Z
    and max(SIDE_TAP_THREAD_MAJOR_DIA, SIDE_TAP_DRILL_DIA) / 2.0
    < HALF_H - abs(SCREW_AXIS_Y)
):
    raise AssertionError(
        "top cross-tap ends are not contained in the far side-rail web"
    )
# Both complete 14-wide feet clear the proud barrels, not just the tap
# centres. The bank is centred at -0.504: front is now the tighter end.
KEEPER_FOOT_TIP_Z_FRONT = FULCRUM_KEEPER_CENTRE_Z - KEEPER_Z_OFF - FOOT_TIP_X
KEEPER_FOOT_TIP_Z_REAR = FULCRUM_KEEPER_CENTRE_Z + KEEPER_Z_OFF + FOOT_TIP_X
KEEPER_FOOT_NEAREST_BOSS_X = max(0.0, abs(KEEPER_TAP_X - COLUMN_X) - KEEPER_WIDTH / 2.0)
KEEPER_FOOT_BOSS_MARGINS = tuple(
    math.hypot(KEEPER_FOOT_NEAREST_BOSS_X, boss_z - tip_z) - BOSS_DIA / 2.0
    for boss_z, tip_z in (
        (FRONT_COLUMN_Z, KEEPER_FOOT_TIP_Z_FRONT),
        (REAR_COLUMN_Z, KEEPER_FOOT_TIP_Z_REAR),
    )
)
# The bench-pair-reamed keeper INNER faces are DRO-located from the front
# socket at fit-up, then the frame taps are transferred through their feet.
# Neither the foot-hole position nor a separate frame-tap station band
# reaches the foot tip. The real stack is the printed INNER-face station
# plus its DRO band, the keeper's printed overall length (inner lug face to
# foot tip) and boss OD; the rear also loses the printed socket-pitch band.
# Taking zero nearest-X distance is conservative for the complete foot,
# whatever its X position.  The keeper's numbers print in its own sheet's
# unit (MHA-CH-07 and its fit-up), read off its row.
_KEEPER_UNIT = drawing_unit("parts/ch-fulcrum-keeper", _config.parts("ch-fulcrum-keeper"))


def _keeper_printed(value: float, places: int, sign: float = 0.0) -> float:
    """A keeper-owned ``value`` as its sheet prints it at ``places`` (``sign``
    0), or at its general band's far (+1) or near (-1) limit."""
    lower, upper = printed_deviations(value, places, unit=_KEEPER_UNIT)
    if sign > 0.0:
        return value + upper
    if sign < 0.0:
        return value + lower
    return value + (lower + upper) / 2.0


KEEPER_OVERALL_LENGTH_PLACES = KEEPER_DRAWING_PRECISION["OverallLengthReference"][
    "OverallLength"
]
BOSS_DIA_BAND_MM = AS_CAST_BAND
KEEPER_PRINTED_MAX_OUTBOARD_REACH = _keeper_printed(
    KEEPER_OVERALL_LENGTH, KEEPER_OVERALL_LENGTH_PLACES, 1.0
)
# The upper barrel is taken out: its largest Ø1.77 stands on the faced top
# the feet sit on and narrows above it.  The feet are DRO-located from the
# front socket, and the barrel's axis may stand off its socket's by the
# socket pattern's Ø.06 location to the cast datums (owner rulings D2, D6).
KEEPER_PRINTED_MAX_BOSS_RADIUS = (
    _cast_limit(BOSS_DIA, 1.0) / 2.0 + SOCKET_PATTERN_LOCATION_ZONE / 2.0
)
KEEPER_PRINTED_MIN_SOCKET_PITCH = (
    REAR_COLUMN_Z - FRONT_COLUMN_Z
) - SOCKET_PATTERN_REFINEMENT_ZONE
KEEPER_FOOT_PRINTED_BOSS_MARGINS = (
    _keeper_printed(KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0], KEEPER_FITUP_PLACES)
    - KEEPER_FITUP_LOCATION_BAND_MM
    - KEEPER_PRINTED_MAX_OUTBOARD_REACH
    - KEEPER_PRINTED_MAX_BOSS_RADIUS,
    KEEPER_PRINTED_MIN_SOCKET_PITCH
    - _keeper_printed(KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[1], KEEPER_FITUP_PLACES)
    - KEEPER_FITUP_LOCATION_BAND_MM
    - KEEPER_PRINTED_MAX_OUTBOARD_REACH
    - KEEPER_PRINTED_MAX_BOSS_RADIUS,
)
KEEPER_FOOT_RAIL_MARGINS = (
    KEEPER_FOOT_TIP_Z_FRONT + INNER_Z,
    INNER_Z - KEEPER_FOOT_TIP_Z_REAR,
)
KEEPER_TAP_BOSS_MARGINS = tuple(
    math.hypot(KEEPER_TAP_X - COLUMN_X, boss_z - tap_z)
    - BOSS_DIA / 2.0
    - KEEPER_TAP_THREAD_MAJOR_DIA / 2.0
    for boss_z, tap_z in (
        (FRONT_COLUMN_Z, KEEPER_TAP_Z_FRONT),
        (REAR_COLUMN_Z, KEEPER_TAP_Z_REAR),
    )
)
if min(KEEPER_FOOT_BOSS_MARGINS) < 1.0:
    raise AssertionError("keeper foot-tip-to-boss clearance is below 1 mm")
if min(KEEPER_FOOT_PRINTED_BOSS_MARGINS) <= 0.0:
    raise AssertionError("fit-up keeper foot hits a boss at the printed bands")
if min(*KEEPER_FOOT_RAIL_MARGINS, *KEEPER_TAP_BOSS_MARGINS) <= 0.0:
    raise AssertionError("keeper foot/tap does not clear the rail corner and boss")

# X is set from the ACTUAL receiver web centre, not the opposite socket;
# horizontal socket-pitch error therefore does not reach this ligament.
# The hole is located from a SIDE face: its .XXX band plus half the .X
# foot-width band both reach the transferred tap centre.
KEEPER_MIN_FOOT_WIDTH = _keeper_printed(
    KEEPER_WIDTH, KEEPER_DRAWING_PRECISION["Foot"]["Depth"], -1.0
)
KEEPER_MAX_FOOT_WIDTH = _keeper_printed(
    KEEPER_WIDTH, KEEPER_DRAWING_PRECISION["Foot"]["Depth"], 1.0
)

# The whole keeper-rail top between the bosses is faced (user ruling
# 2026-10-11), so the ACTUAL foot, anywhere its printed fit-up band puts it,
# must stand on that flat face: clear of the bosses (above) and of the
# printed worst top-rim break leg on either side of the rail.
# The keeper is set from the receiver web, whose median stands within ±.03 of
# its socket-axis line (⌖.06), and the taken-out rims stand at their
# nominal on the faced top, each face half the as-cast band off it.
KEEPER_FOOT_PRINTED_FLAT_TOP_SIDE_MARGIN = (
    _cast_limit(RAIL_W_SIDE, -1.0) / 2.0
    - _RAIL_WEB_MEDIAN_OFFSET
    - (
        abs(_keeper_printed(KEEPER_FITUP_X_FROM_WEB_MM, KEEPER_FITUP_PLACES))
        + KEEPER_FITUP_X_BAND_MM
    )
    - KEEPER_MAX_FOOT_WIDTH / 2.0
    - EDGE_BREAK_PRINTED_MAX
)
if KEEPER_FOOT_PRINTED_FLAT_TOP_SIDE_MARGIN <= 0.0:
    raise AssertionError("keeper foot leaves the flat keeper-rail top")

KEEPER_PRINTED_SIDE_STATION = _keeper_printed(
    SCREW_FROM_SIDE,
    KEEPER_DRAWING_PRECISION["FootScrewSideReference"]["ScrewFromSide"],
)
KEEPER_MAX_TRANSVERSE_OFFSET = max(
    abs(
        KEEPER_PRINTED_SIDE_STATION
        - KEEPER_SCREW_TRANSVERSE_BAND_MM
        - KEEPER_MAX_FOOT_WIDTH / 2.0
    ),
    abs(
        KEEPER_PRINTED_SIDE_STATION
        + KEEPER_SCREW_TRANSVERSE_BAND_MM
        - KEEPER_MIN_FOOT_WIDTH / 2.0
    ),
)
# The fitter sets the keeper from the web's median line, which the print
# holds within ±.03 of the socket-axis line (owner ruling D3): charged.
KEEPER_MAX_WEB_CENTRE_OFFSET = (
    abs(_keeper_printed(KEEPER_FITUP_X_FROM_WEB_MM, KEEPER_FITUP_PLACES))
    + KEEPER_FITUP_X_BAND_MM
    + KEEPER_MAX_TRANSVERSE_OFFSET
    + RAIL_WEB_POSITION_ZONE / 2.0
)
# H-H prints the top flange thickness TYP from the faced top to the cast
# underside (its as-cast band): one FINAL dimension binds every rail, the
# faced keeper-rail top included, so facing cannot subtract a second
# allowance from its printed minimum, and cap-floor and boss-height bands do
# not enter.
KEEPER_MIN_FLANGE_THICKNESS = _cast_limit(FLANGE, -1.0)
KEEPER_MIN_ROOT_RADIUS = _cast_limit(ROOT_FILLET_R, -1.0)
KEEPER_MAX_FULL_THREAD_DEPTH = _printed_limit(
    KEEPER_TAP_SPEC.overrides_mm["ThreadDepth"],
    KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"],
    1.0,
)
KEEPER_MAX_TAP_DRILL_DEPTH = _printed_limit(
    KEEPER_TAP_SPEC.depth_mm, KEEPER_TAP_CALLOUT_PRECISION["hw-tapdrldepth"], 1.0
)
# drawing-guidelines.md rule 17 (walls and webs): budget realistic deep-drill wander over the FULL allowed
# cylindrical depth, not only the shorter threaded region. Its displacement
# disk conservatively covers every pilot/thread section and every direction;
# subtracting its radius from the normal wall distance handles the T-root
# without an optimistic horizontal projection or a claimed guide operation.
KEEPER_TAP_AXIS_WANDER_MM = KEEPER_MAX_TAP_DRILL_DEPTH * math.tan(
    math.radians(KEEPER_TAP_DRILL_WANDER_DEG)
)
_KEEPER_DRILL_BOTTOM_Y = HALF_H - KEEPER_MAX_TAP_DRILL_DEPTH


def _keeper_web_half_width_min(y: float) -> float:
    """The thinnest printed web's half width at height ``y``: its as-cast
    minimum on the underside, thickened by its least (2°) added draft."""
    return _cast_limit(WEB_T, -1.0) / 2.0 + (y + HALF_H) * DRAFT_T_ADDED_MIN


# The drill's cylinder is narrowest-walled at its bottom; the thread's
# limiting corner sits at the T-root's lower tangent.
KEEPER_MIN_WEB_HALF_WIDTH = _keeper_web_half_width_min(_KEEPER_DRILL_BOTTOM_Y)
_KEEPER_ROOT_WEB_HALF_WIDTH = _keeper_web_half_width_min(
    FLANGE_BOT_Y - KEEPER_MIN_ROOT_RADIUS
)
# The limiting full-thread corner lies next to the quarter-circle T-root.
# Use its shortest NORMAL distance to that arc, not the larger horizontal
# section width. Below the arc the same expression becomes the bare web.
KEEPER_TAP_THREAD_WALL_MARGIN_NO_WANDER = (
    math.hypot(
        _KEEPER_ROOT_WEB_HALF_WIDTH
        + KEEPER_MIN_ROOT_RADIUS
        - KEEPER_MAX_WEB_CENTRE_OFFSET
        - KEEPER_TAP_THREAD_MAJOR_DIA / 2.0,
        max(
            0.0,
            KEEPER_MIN_FLANGE_THICKNESS
            + KEEPER_MIN_ROOT_RADIUS
            - KEEPER_MAX_FULL_THREAD_DEPTH,
        ),
    )
    - KEEPER_MIN_ROOT_RADIUS
)
KEEPER_TAP_THREAD_WALL_MARGIN = (
    KEEPER_TAP_THREAD_WALL_MARGIN_NO_WANDER - KEEPER_TAP_AXIS_WANDER_MM
)
KEEPER_MAX_TAP_DRILL_RADIUS = (
    _printed_nominal(
        TAP_DRILL_MM[KEEPER_TAP_SPEC.size],
        KEEPER_TAP_CALLOUT_PRECISION["hw-tapdrldia"],
    )
    + PRINTED_DRILLED_HOLE_PLUS_MM
) / 2.0
KEEPER_TAP_DRILL_WALL_MARGIN_NO_WANDER = (
    KEEPER_MIN_WEB_HALF_WIDTH
    - KEEPER_MAX_WEB_CENTRE_OFFSET
    - KEEPER_MAX_TAP_DRILL_RADIUS
)
KEEPER_TAP_DRILL_WALL_MARGIN = (
    KEEPER_TAP_DRILL_WALL_MARGIN_NO_WANDER - KEEPER_TAP_AXIS_WANDER_MM
)
# Owner rulings D3/D4 (#2333): the drill wall holds the .080 target at the 2°
# minimum added draft (.0807 MIN); the owner's floor is .060.
if min(KEEPER_TAP_THREAD_WALL_MARGIN, KEEPER_TAP_DRILL_WALL_MARGIN) < WALL_TARGET_MM:
    raise AssertionError("keeper receiver leaves less than .080 with drill wander")
KEEPER_MAX_STOCK_ENTRY = FOOT_SCREW_LENGTH_MM - (
    _keeper_printed(FOOT_H, KEEPER_DRAWING_PRECISION["FootProfile"]["FootRise"], -1.0)
    - _keeper_printed(CBORE_DEPTH_MM, FOOT_COUNTERBORE_DEPTH_PLACES, 1.0)
)
KEEPER_MIN_THREAD_TIP_RESERVE = (
    _printed_limit(
        KEEPER_TAP_SPEC.overrides_mm["ThreadDepth"],
        KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"],
        -1.0,
    )
    - KEEPER_MAX_STOCK_ENTRY
)
if KEEPER_MIN_THREAD_TIP_RESERVE < 0.25:
    raise AssertionError("keeper foot screw loses its 0.25 mm blind-thread clearance")

# The deeper counterbore carries the west cross taps past both keeper
# stations, so the #10-32 thread now runs under the #2-56 tap drills. The
# wall is the keeper drill's cylinder-plus-cone profile (deepest printed
# drill, largest drilled radius, nearest printed transverse offset) against
# the thread major with its axis at the top of the stacked .X bands (axis
# below boss top, boss top above rail top), less both axes' wander. The
# cross-tap axis lies on the receiver web centre (the socket axis), and its
# wander uses the same angular drift over the run from the counterbore floor.
KEEPER_MIN_WEB_CENTRE_OFFSET = (
    abs(_keeper_printed(KEEPER_FITUP_X_FROM_WEB_MM, KEEPER_FITUP_PLACES))
    - KEEPER_FITUP_X_BAND_MM
    - KEEPER_MAX_TRANSVERSE_OFFSET
    - RAIL_WEB_POSITION_ZONE / 2.0
)
_KEEPER_DRILL_TIP_Y = (
    _KEEPER_DRILL_BOTTOM_Y - KEEPER_MAX_TAP_DRILL_RADIUS * DRILL_POINT_H
)
_CROSS_AXIS_MAX_Y = (
    SCREW_AXIS_Y
    + PRINTED_LINEAR_BAND_MM[
        DRAWING_REFERENCE_PRECISION["cross screw axis from boss top"]
    ]
    + PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["boss top above rail top"]]
)
_CROSS_TAP_WANDER_MM = (
    COUNTERBORE_FLOOR - min(abs(KEEPER_TAP_Z_FRONT), abs(KEEPER_TAP_Z_REAR))
) * math.tan(math.radians(KEEPER_TAP_DRILL_WANDER_DEG))


def _point_segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, t))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


_KEEPER_DRILL_NEAR_SIDE_X = KEEPER_MIN_WEB_CENTRE_OFFSET - KEEPER_MAX_TAP_DRILL_RADIUS
KEEPER_CROSS_TAP_WALL = (
    min(
        # the drill's inboard wall above its bottom corner, then its cone
        _point_segment_distance(
            (0.0, _CROSS_AXIS_MAX_Y),
            (_KEEPER_DRILL_NEAR_SIDE_X, HALF_H),
            (_KEEPER_DRILL_NEAR_SIDE_X, _KEEPER_DRILL_BOTTOM_Y),
        ),
        _point_segment_distance(
            (0.0, _CROSS_AXIS_MAX_Y),
            (_KEEPER_DRILL_NEAR_SIDE_X, _KEEPER_DRILL_BOTTOM_Y),
            (KEEPER_MIN_WEB_CENTRE_OFFSET, _KEEPER_DRILL_TIP_Y),
        ),
    )
    - SIDE_TAP_THREAD_MAJOR_DIA / 2.0
    - _CROSS_TAP_WANDER_MM
    - KEEPER_TAP_AXIS_WANDER_MM
)  # 3.31: over the .080 target
if KEEPER_CROSS_TAP_WALL < WALL_FLOOR_MM:
    raise AssertionError("top cross-tap thread leaves under .060 to a keeper drill")


# --------------------------------------------------------------------------
# Analytic expectations.  Every drafted prism's plan section is a polynomial
# in its height, so Simpson's rule integrates it exactly; where a section
# meets a barrel its plan area is a one-dimensional chord integral.
# --------------------------------------------------------------------------


def _simpson(f, a: float, b: float, n: int = 8) -> float:
    """Simpson's rule for ``f`` over [a, b] in ``n`` (even) panels."""
    h = (b - a) / n
    total = f(a) + f(b)
    for k in range(1, n):
        total += (4.0 if k % 2 else 2.0) * f(a + k * h)
    return total * h / 3.0


def _circle_cap_area(radius: float, offset: float) -> float:
    """Area beyond a chord ``offset`` from the circle centre."""
    if offset >= radius:
        return 0.0
    return radius**2 * math.acos(offset / radius) - offset * math.sqrt(
        radius**2 - offset**2
    )


def _chord_area(radius: float, u_lo: float, u_hi: float, clip, n: int = 400) -> float:
    """Plan area of a disc (centred on the origin) over u in [u_lo, u_hi]
    where, at each u, ``clip(u, c)`` bounds the disc's chord [-c, c] to
    (low, high)."""
    u_lo, u_hi = max(u_lo, -radius), min(u_hi, radius)
    if u_hi <= u_lo:
        return 0.0

    def length(u: float) -> float:
        low, high = clip(u, math.sqrt(max(0.0, radius * radius - u * u)))
        return max(0.0, high - low)

    return _simpson(length, u_lo, u_hi, n)


def _web_ring_area(rise: float) -> float:
    """The web ring's plan area ``rise`` above the underside (added draft)."""
    d = rise * DRAFT_T
    return 4.0 * ((WEB_OUT_X + d) * (WEB_OUT_Z + d) - (WEB_IN_X - d) * (WEB_IN_Z - d))


def _web_ring_volume() -> float:
    return _simpson(_web_ring_area, 0.0, RING_HEIGHT, 2)


def _flange_add_volume() -> float:
    """The taken-out flange band less the web ring already inside it."""

    def added(depth: float) -> float:
        d = depth * DRAFT_T
        band = 4.0 * ((OUTER_X - d) * (OUTER_Z - d) - (INNER_X + d) * (INNER_Z + d))
        return band - _web_ring_area(RING_HEIGHT - depth)

    return _simpson(added, 0.0, FLANGE, 2)


def _hub_rib_add_volume() -> float:
    """The rib's faces continue the rims' planes and the web leans as far the
    other way, so under the flange each side adds a constant width."""
    width = 2.0 * (RECESS_SIDE - RIM_RECEDE)
    return width * (HUB_RIB_W * POCKET_H + DRAFT_T * POCKET_H**2)


def _gusset_leg(d: float) -> float:
    """A plan gusset's leg at outward draft offset ``d``: its hypotenuse moves
    out while the bar side and the land face close in on its corner."""
    return GUSSET - (2.0 - math.sqrt(2.0)) * d


def _crossbar_add_volume() -> float:
    """The crossbar, its plan gussets and the junction lands, one polygon:
    the part in the window over the whole band, the lands under the flange."""

    def in_window(rise: float) -> float:
        d = rise * DRAFT_T
        bar = (BAR_X1 - BAR_X0 + 2.0 * d) * 2.0 * (LAND_FACE_Z0 - d)
        return bar + 2.0 * _gusset_leg(d) ** 2

    lands = (
        2.0
        * (WEB_IN_Z - LAND_FACE_Z0)
        * ((LAND_X1 - LAND_X0) * POCKET_H + DRAFT_T * POCKET_H**2)
    )
    return _simpson(in_window, 0.0, RING_HEIGHT, 2) + lands


def _bar_pocket_removal() -> float:
    """Both pockets: each removes the bar between its side and the web, whose
    faces lean alike, over the pocket's length closing in toward its roof."""
    width = (BAR_X1 - BAR_X0) - WEB_T
    return width * 2.0 * (BAR_POCKET_Z * POCKET_H - DRAFT_T * POCKET_H**2 / 2.0)


def _corner_crop_removal() -> float:
    """The four corner triangles' cut through the taken-out flange band: each
    the right triangle the chord leaves in the plan corner at that depth."""

    def area(depth: float) -> float:
        d = depth * DRAFT_T
        ox, oz = RAIL_W_SIDE / 2.0 - d, RAIL_W_FR / 2.0 - d
        return (
            max(0.0, ox - _crop_chord_x(oz)) * max(0.0, oz - _crop_chord_z(ox)) / 2.0
        )

    return 4.0 * _simpson(area, 0.0, FLANGE, 2)


def _corner_rail_area(radius: float, y: float, in_flange: bool) -> float:
    """Rail plan area inside a corner barrel of ``radius`` at height ``y``,
    in the barrel's frame (u, v outward along x, z): the cropped flange band
    (``in_flange``), or under it the L of the two webs.  The caller names the
    side, so an integral ending on the flange underside reads its own."""
    if in_flange:
        d = (HALF_H - y) * DRAFT_T
        ox, oz = RAIL_W_SIDE / 2.0 - d, RAIL_W_FR / 2.0 - d
        band = _chord_area(radius, -radius, ox, lambda u, c: (-c, min(oz, c)))
        window = _chord_area(radius, -radius, -ox, lambda u, c: (-c, min(-oz, c)))
        crop = _chord_area(
            radius,
            _crop_chord_x(oz),
            ox,
            lambda u, c: (max(_crop_chord_z(u), -c), min(oz, c)),
        )
        return band - window - crop
    a = WEB_T / 2.0 + (y + HALF_H) * DRAFT_T
    strip = _chord_area(radius, -a, a, lambda u, c: (-c, min(a, c)))
    return 2.0 * strip - (2.0 * a) ** 2


def _boss_radius(y: float) -> float:
    """A corner barrel's radius at height ``y``: taken out from the faced top
    both ways."""
    return BOSS_DIA / 2.0 - abs(HALF_H - y) * DRAFT_T


def _boss_add_volumes() -> tuple[float, float]:
    """(upper, lower) additions of ONE corner boss: the upper barrel above the
    faced top, the lower from it to the boss bottom less the rail already
    there.  All four corners match by symmetry."""

    def disc(y: float) -> float:
        return math.pi * _boss_radius(y) ** 2

    def lower(y: float, in_flange: bool) -> float:
        return disc(y) - _corner_rail_area(_boss_radius(y), y, in_flange)

    upper = _simpson(disc, HALF_H, HALF_H + BOSS_ABOVE, 2)
    down = (
        _simpson(lambda y: lower(y, True), FLANGE_BOT_Y, HALF_H, 8)
        + _simpson(lambda y: lower(y, False), -HALF_H, FLANGE_BOT_Y, 8)
        + _simpson(disc, -HALF_H - BOSS_BELOW, -HALF_H, 2)
    )
    return upper, down


def _hub_gusset_ramp_half(rise: float) -> float:
    """The V-gussets' half span along z ``rise`` above their bottom flat."""
    return HUB_GUSSET_HALF_IN + rise * (
        HUB_GUSSET_HALF_OUT - HUB_GUSSET_HALF_IN
    ) / HUB_BOSS_DROP


def _hub_gusset_thickness(rise: float) -> float:
    """The V-gussets' thickness along x ``rise`` above their bottom flat."""
    return HUB_GUSSET_T + 2.0 * rise * DRAFT_T


def _hub_gusset_volumes() -> tuple[float, float]:
    """(plate, ramp cuts): the drafted plate from the bottom flat up to the
    underside, then what the two ramp cuts take back off it."""
    plate = _simpson(
        lambda s: _hub_gusset_thickness(s)
        * 2.0
        * (HUB_GUSSET_PLATE_HALF + s * DRAFT_T),
        0.0,
        HUB_BOSS_DROP,
        2,
    )
    kept = _simpson(
        lambda s: _hub_gusset_thickness(s) * 2.0 * _hub_gusset_ramp_half(s),
        0.0,
        HUB_BOSS_DROP,
        2,
    )
    return plate, plate - kept


def _hub_boss_add_volume() -> float:
    """The hub barrel below the underside (nominal there, narrowing down)
    less the V-gussets already through it."""

    def added(depth: float) -> float:
        r = HUB_BOSS_DIA / 2.0 - depth * DRAFT_T
        rise = HUB_BOSS_DROP - depth
        w = _hub_gusset_thickness(rise) / 2.0
        span = _hub_gusset_ramp_half(rise)
        plate = _chord_area(r, -w, w, lambda u, c: (-min(span, c), min(span, c)))
        return math.pi * r * r - plate

    return _simpson(added, 0.0, HUB_BOSS_DROP, 8)


def _set_boss_add_volume() -> float:
    """The set-screw boss proud of the rail's outer face: its face and that
    face lean alike, so it stands a constant SET_BOSS_PROUD out over a span
    widening up at its added sides."""
    return SET_BOSS_PROUD * (
        HUB_SET_BOSS_W * RING_HEIGHT + DRAFT_T * RING_HEIGHT**2
    )


def _set_spot_removal() -> float:
    """The spot face from its floor out to the leaning cast face: linear
    across the round spot, so its axis height gives the mean depth."""
    face = -SET_BOSS_FACE_X - (HALF_H - SCREW_AXIS_Y) * DRAFT_T
    return math.pi * (HUB_SET_SPOT_DIA / 2.0) ** 2 * (face + SET_SPOT_FACE_X)


def _counterbore_removal() -> float:
    """Material one Ø.35 counterbore removes from its taken-out barrel: the
    floor-to-surface length over the bore's disc, summed in polar rings so
    the round rim is exact."""
    r_d = COUNTERBORE_DIA / 2.0
    rings, spokes = 400, 720
    total = 0.0
    for i in range(rings):
        rho = (i + 0.5) * r_d / rings
        for j in range(spokes):
            phi = (j + 0.5) * 2.0 * math.pi / spokes
            u, v = rho * math.cos(phi), rho * math.sin(phi)
            r = _boss_radius(SCREW_AXIS_Y + v)
            surf = abs(FRONT_COLUMN_Z) + math.sqrt(max(0.0, r * r - u * u))
            total += max(0.0, min(surf, COUNTERBORE_PLANE) - COUNTERBORE_FLOOR) * rho
    return total * (r_d / rings) * (2.0 * math.pi / spokes)


def _side_tap_removal() -> float:
    """Casting removed by one blind tap continued across the column bore."""
    r_h = SIDE_TAP_DRILL_DIA / 2.0
    r_v = BORE_DIA / 2.0
    step = 0.001
    vol = 0.0
    d = -r_h
    while d < r_h:
        dd = d + 0.5 * step
        chord = 2.0 * math.sqrt(max(0.0, r_h * r_h - dd * dd))
        bore_span = 2.0 * math.sqrt(max(0.0, r_v * r_v - dd * dd))
        vol += chord * (TOP_CASTING_TAP_DRILL_DEPTH - bore_span) * step
        d += step
    # The 118-degree point is wholly beyond the bore in the far wall.
    vol += math.pi / 3.0 * r_h**3 * DRILL_POINT_H
    return vol


def _set_tap_removal() -> float:
    """Material removed by the 1/4-20 tap from the spot face to the bore."""
    r_h = TAP_DRILL_MM[SET_SCREW_THREAD] / 2.0
    r_v = GOOSENECK_BORE_DIA / 2.0
    floor_x = -SET_SPOT_FACE_X  # 218.0 (magnitudes, east side)
    step = 0.005
    vol = 0.0
    d = -r_h
    while d < r_h:
        dd = d + 0.5 * step
        chord = 2.0 * math.sqrt(max(0.0, r_h * r_h - dd * dd))
        void = COLUMN_X + math.sqrt(max(0.0, r_v * r_v - dd * dd))
        length = max(0.0, floor_x - void)
        vol += chord * length * step
        d += step
    return vol


def _fillet_section_area(r: float, corner_deg: float = 90.0) -> float:
    """Cross-section a radius-r fillet adds to a reentrant corner whose air
    wedge spans ``corner_deg`` (or a round removes from a convex edge)."""
    beta = math.radians(corner_deg)
    return r * r * (1.0 / math.tan(beta / 2.0) - (math.pi - beta) / 2.0)


def _chamfer_section_area(c: float, angle_deg: float) -> float:
    """Cross-section an angle-distance c x 45 chamfer removes from a convex
    edge whose solid spans ``angle_deg`` (either face may take the leg)."""
    a = math.radians(angle_deg)
    return (
        0.5 * c * c * math.sin(a) * math.sin(math.pi / 4.0)
        / math.sin(3.0 * math.pi / 4.0 - a)
    )


# Every face meeting the faced top leans out 2° toward it (added and taken-out
# draft alike), and every face meeting the underside or a boss end leans in.
TOP_EDGE_DEG = 90.0 - DRAFT_DEG
BOTTOM_EDGE_DEG = 90.0 + DRAFT_DEG


def _top_rim_removal() -> tuple[float, float]:
    """(outer, window) EDGE_CHAMFER x 45 removals round the faced top's rims.

    R22.479 < hypot(17.094, 19.05) = 25.60: neither window corner nor outer rail
    corner reaches a boss, and the flange corner crops leave no flange
    outside the barrels, so each outer face runs barrel to barrel: four
    runs, each the boss-centre to boss-centre strip less the half of each
    barrel's chamfer cap on its side, the east one less the set-screw boss's
    width there (its own top edges stay unbroken).  The window rims are
    uninterrupted up to their square corners; on the top the crossbar's sides
    and its gussets stand at their 2° lean.  Outer strip areas exclude the
    proud cylinders analytically; the windows' 90/135-degree mitres are
    included.  Every top edge is 88°.
    """
    radius = BOSS_DIA / 2.0
    chamfer = EDGE_CHAMFER
    a, b = RAIL_W_SIDE / 2.0, RAIL_W_FR / 2.0
    if not max(a, b) < radius < math.hypot(a - chamfer, b - chamfer):
        raise AssertionError("top-rim formula requires separate rail/boss plan corners")
    factor = _chamfer_section_area(chamfer, TOP_EDGE_DEG) / (chamfer**2 / 2.0)

    def cap_integral(offset: float) -> float:
        def primitive(distance: float) -> float:
            chord = math.sqrt(radius**2 - distance**2)
            return (
                radius**2 * (distance * math.acos(distance / radius) - chord)
                + chord**3 / 3.0
            )

        return (
            primitive(offset)
            - primitive(offset - chamfer)
            - chamfer * _circle_cap_area(radius, offset)
        )

    set_boss_top = HUB_SET_BOSS_W + 2.0 * RIM_RECEDE
    outer = factor * (
        4.0 * (abs(FRONT_COLUMN_Z) + COLUMN_X) * chamfer**2 / 2.0
        - 2.0 * (cap_integral(a) + cap_integral(b))
        - set_boss_top * chamfer**2 / 2.0
    )
    leg = _gusset_leg(RIM_RECEDE)
    foot = RIM_RECEDE + leg  # gusset foot off its bar side, on the top
    side_run = 2.0 * INNER_Z
    east_fr = INNER_X - (abs(BAR_X0) + foot)
    west_fr = INNER_X - (BAR_X1 + foot)
    hyp = leg * math.sqrt(2.0)
    flank = 2.0 * (INNER_Z - leg)
    window_perimeter = (
        2.0 * side_run + 2.0 * east_fr + 2.0 * west_fr + 4.0 * hyp + 2.0 * flank
    )
    # Each six-sided window has two 90-degree and four 135-degree corners.
    window_mitres = 2.0 * (2.0 + 4.0 * (math.sqrt(2.0) - 1.0))
    window = factor * window_perimeter * chamfer**2 / 2.0 + window_mitres * chamfer**3 / 3.0
    return outer, window


def _t_root_add() -> float:
    """Volume the R3 internal T-root fillets add along the web-flange shelf.

    The reentrant junction where each web face meets the flange underside
    (y +10.25), on BOTH the outer and the window side of every rail; there
    every web face leans 2° out, so each root fills a 92° corner.  The hub
    rib interrupts both east-rail runs, the junction lands interrupt both
    front/rear WINDOW runs, each as wide as it stands at the flange
    underside.  The crossbar web adds its two roots between the pocket ends.
    The fillet ends dying into boss barrels / rib / land / pocket-end walls
    and the small vertical junction coves at those walls are not modeled --
    the check tolerance absorbs the ends; the vertical coves stay sharp.
    """
    area = _fillet_section_area(ROOT_FILLET_R, BOTTOM_EDGE_DEG)
    d = POCKET_H * DRAFT_T
    a = WEB_T / 2.0 + d
    cut = math.sqrt(_boss_radius(FLANGE_BOT_Y) ** 2 - a * a)
    rib = HUB_RIB_W + 2.0 * d
    side = 2.0 * (abs(FRONT_COLUMN_Z) - cut)  # one side-rail run, west
    fr = 2.0 * (COLUMN_X - cut)  # one front/rear run, uninterrupted
    outer = side + (side - rib) + 2.0 * fr
    window = side + (side - rib) + 2.0 * (fr - (LAND_X1 - LAND_X0 + 2.0 * d))
    crossbar = 2.0 * 2.0 * (BAR_POCKET_Z - d)
    return area * (outer + window + crossbar)


def _bore_chamfer_removal() -> float:
    """Volume the C1 x 45 breaks remove from the five top bore rims."""

    def ring(bore_dia: float) -> float:
        return math.pi * BORE_CHAMFER**2 * (bore_dia / 2.0 + BORE_CHAMFER / 3.0)

    return 4.0 * ring(CAP_RECESS_DIAMETER) + ring(GOOSENECK_BORE_DIA)


def _casting_occupies(x: float, y: float, z: float) -> bool:
    """Whether the solid casting, as the edge breaks find it, holds (x, y, z).

    The drafted rail T-ring with its flange corners cropped to the barrels,
    hub rib with its full-height set-screw boss (spot face out), the crossbar
    polygon (bar, plan gussets, junction lands) with its T pockets, the
    taken-out corner barrels and hub barrel and the V-gussets -- exact around
    every edge-break pick (bores, holes and the earlier top breaks lie clear
    of them).
    """
    ax, az = abs(x), abs(z)
    drop = HALF_H - y  # below the faced top: taken-out faces recede
    d = (y + HALF_H) * DRAFT_T  # above the underside: added faces lean out
    if FLANGE_BOT_Y <= y <= HALF_H:
        recede = drop * DRAFT_T
        if (
            ax <= OUTER_X - recede
            and az <= OUTER_Z - recede
            and not (ax < INNER_X + recede and az < INNER_Z + recede)
        ):
            u, v = ax - COLUMN_X, az - abs(FRONT_COLUMN_Z)
            cropped = (
                u <= _CROP_APEX[0] and v <= _CROP_APEX[1] and v >= _crop_chord_z(u)
            )
            if not cropped:
                return True
    if -HALF_H <= y <= HALF_H:
        if WEB_IN_X - d <= ax <= WEB_OUT_X + d and az <= WEB_OUT_Z + d:
            return True
        if WEB_IN_Z - d <= az <= WEB_OUT_Z + d and ax <= WEB_OUT_X + d:
            return True
        if y <= FLANGE_BOT_Y:
            if (
                LAND_X0 - d <= x <= LAND_X1 + d
                and LAND_FACE_Z0 - d <= az <= WEB_IN_Z + LAND_WEB_BURY + d
            ):
                return True
            if (
                -RIB_OUT_X0 - d <= x <= -RIB_IN_X0 + d
                and abs(z - GOOSENECK_Z) <= HUB_RIB_W / 2.0 + d
            ):
                return True
        if (
            SET_BOSS_FACE_X0 - d <= x <= -RIB_OUT_X0
            and abs(z - GOOSENECK_Z) <= HUB_SET_BOSS_W / 2.0 + d
            and not (
                x < SET_SPOT_FACE_X
                and math.hypot(y - SCREW_AXIS_Y, z - GOOSENECK_Z)
                < HUB_SET_SPOT_DIA / 2.0
            )
        ):
            return True
        if az <= LAND_FACE_Z0 - d:
            in_bar = BAR_X0 - d <= x <= BAR_X1 + d
            # Each plan gusset's hypotenuse moves its own d outward.
            spread = az - (LAND_FACE_Z0 - GUSSET - d * math.sqrt(2.0))
            in_gusset = spread >= 0.0 and BAR_X0 - spread <= x <= BAR_X1 + spread
            pocket = (
                y < FLANGE_BOT_Y
                and az < BAR_POCKET_Z - d
                and (BAR_X0 - BAR_POCKET_OVERRUN + d < x < BAR_WEB_X0 - d
                     or BAR_WEB_X1 + d < x < BAR_X1 + BAR_POCKET_OVERRUN - d)
            )
            if (in_bar or in_gusset) and not pocket:
                return True
    if -(HALF_H + BOSS_BELOW) <= y <= HALF_H + BOSS_ABOVE:
        if math.hypot(ax - COLUMN_X, az - abs(FRONT_COLUMN_Z)) <= _boss_radius(y):
            return True
    if HUB_GUSSET_BOTTOM_Y <= y <= -HALF_H:
        if math.hypot(x - GOOSENECK_X, z - GOOSENECK_Z) <= (
            HUB_BOSS_DIA / 2.0 - (-HALF_H - y) * DRAFT_T
        ):
            return True
        rise = y - HUB_GUSSET_BOTTOM_Y
        if (
            abs(x - GOOSENECK_X) <= _hub_gusset_thickness(rise) / 2.0
            and abs(z - GOOSENECK_Z) <= _hub_gusset_ramp_half(rise)
        ):
            return True
    return False


def _interior_angle(
    point: tuple[float, float, float], axis: tuple[float, float, float]
) -> float:
    """The solid's angle (deg) about the edge through ``point`` along ``axis``:
    the share of 72 rays round it, a hair long, that land in the casting."""
    norm = math.sqrt(sum(a * a for a in axis))
    a = tuple(value / norm for value in axis)
    ref = (0.0, 1.0, 0.0) if abs(a[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = (
        a[1] * ref[2] - a[2] * ref[1],
        a[2] * ref[0] - a[0] * ref[2],
        a[0] * ref[1] - a[1] * ref[0],
    )
    u_norm = math.sqrt(sum(value * value for value in u))
    u = tuple(value / u_norm for value in u)
    w = (
        a[1] * u[2] - a[2] * u[1],
        a[2] * u[0] - a[0] * u[2],
        a[0] * u[1] - a[1] * u[0],
    )
    rays, reach = 72, 1e-3
    inside = 0
    for k in range(rays):
        theta = 2.0 * math.pi * (k + 0.5) / rays
        c, s = math.cos(theta), math.sin(theta)
        inside += _casting_occupies(
            *(point[i] + reach * (c * u[i] + s * w[i]) for i in range(3))
        )
    return 360.0 * inside / rays


def _plan_gap(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    """Distance between two convex plan polygons; 0.0 when they overlap."""

    def separated(p: list[tuple[float, float]], q: list[tuple[float, float]]) -> bool:
        for i, (x0, z0) in enumerate(p):
            x1, z1 = p[(i + 1) % len(p)]
            nx, nz = z1 - z0, x0 - x1
            p_dots = [nx * x + nz * z for x, z in p]
            q_dots = [nx * x + nz * z for x, z in q]
            if max(p_dots) < min(q_dots) or max(q_dots) < min(p_dots):
                return True
        return False

    if not (separated(a, b) or separated(b, a)):
        return 0.0

    def to_segment(point, s0, s1) -> float:
        dx, dz = s1[0] - s0[0], s1[1] - s0[1]
        t = ((point[0] - s0[0]) * dx + (point[1] - s0[1]) * dz) / (dx * dx + dz * dz)
        t = min(1.0, max(0.0, t))
        return math.hypot(point[0] - s0[0] - t * dx, point[1] - s0[1] - t * dz)

    return min(
        to_segment(point, poly[i], poly[(i + 1) % len(poly)])
        for point_set, poly in ((a, b), (b, a))
        for point in point_set
        for i in range(len(poly))
    )


def _segment_gap(
    p0: tuple[float, ...],
    p1: tuple[float, ...],
    q0: tuple[float, ...],
    q1: tuple[float, ...],
) -> float:
    """Least distance between 3D segments p0-p1 and q0-q1 (both non-degenerate)."""
    d1 = [b - a for a, b in zip(p0, p1)]
    d2 = [b - a for a, b in zip(q0, q1)]
    r = [a - b for a, b in zip(p0, q0)]
    a = sum(v * v for v in d1)
    e = sum(v * v for v in d2)
    f = sum(u * v for u, v in zip(d2, r))
    b = sum(u * v for u, v in zip(d1, d2))
    c = sum(u * v for u, v in zip(d1, r))
    denom = a * e - b * b
    s = min(max((b * f - c * e) / denom, 0.0), 1.0) if denom > 1e-12 else 0.0
    t = (b * s + f) / e
    if t < 0.0:
        t, s = 0.0, min(max(-c / a, 0.0), 1.0)
    elif t > 1.0:
        t, s = 1.0, min(max((b - c) / a, 0.0), 1.0)
    return math.dist(
        [p + s * d for p, d in zip(p0, d1)], [q + t * d for q, d in zip(q0, d2)]
    )


def _external_edge_breaks() -> tuple[
    dict[str, tuple[list[list[float]], float, int]], dict[str, float]
]:
    """The external edge breaks (EDGE_CHAMFER x 45) as one chamfer feature per
    edge group, in build order (feature name -> picks, analytic removal,
    shared vertices), and each knife seat's least clearance to them.

    Every external convex edge the top-rim and bore-top breaks left, once
    the T-section crossbar exists: the outer and window flange undersides
    (the corner crops leave no outer-corner runs or vertical corners, every
    outer run dying into a boss barrel at both ends), the web bottoms, the
    junction lands' free edges, the crossbar web bottoms, pocket-end bottoms
    and outer corners, the rear full-depth bar-side bottoms, the hub rib's
    free corners and side bottoms, the set-screw boss's edges, and the
    corner/hub boss rims.
    Straight edges remove ``_chamfer_section_area`` per mm over their run to
    the face that ends them; outer rims remove that section round their
    circumference (c the model's EDGE_CHAMFER).  The drafted casting's
    underside and boss-end edges are 92°, its flange-underside edges 92°
    and its near-vertical corners 90°, each pick at its drafted station.
    Corner patches and the ends dying into boss barrels are left to the
    tolerance.

    Groups are the connected chains of breaks, long simple runs first and
    the boss rims last, so a native failure names its
    chain and each chain's volume is proved on its own. Breaks that share a
    vertex must sit in one group (SolidWorks blends that corner only within
    a feature); any other two breaks keep ``2 EDGE_BREAK_PRINTED_MAX +
    EDGE_BREAK_SLIVER_MIN`` apart and every straight break runs longer than
    ``2 EDGE_BREAK_PRINTED_MAX``, or the module fails to import. ``shared``
    counts the pairs of a group's breaks that meet at a vertex.

    Eligibility is judged at the print's limits, since a conforming casting
    may carry any printed size: an edge whose printed worst length
    (``printed_length``) cannot hold the printed worst legs at both its
    ends, or whose flange shelf at its printed worst
    (``T_FLANGE_SHELF_PRINTED_MIN``) cannot hold one leg and the sliver
    land, is left unbroken at .06 instead of being picked.

    Every pick must be the convex edge it claims: its solid angle, measured
    on ``_casting_occupies``, is below 180 degrees and equals the angle its
    removal uses, or the module fails to import. Every break reaching the
    underside keeps its print-worst band (``_EDGE_LOCATION_BAND`` off the
    edge, ``EDGE_BREAK_PRINTED_MAX`` into the face) at least
    ``KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE`` off both print-worst knife-seat
    hulls; the returned dict is each seat's least clearance.

    The hub rib's outer bottom either side of the set-screw boss
    (``HUB_RIB_STUB_PRINTED_MIN`` at the as-cast limits) holds the printed
    worst legs, so it is picked; the crossbar T flange's underside edges do
    not (the pockets' and bar sides' lean leaves no printed shelf there).
    Left unbroken at .06, the title block's .010 break applying (owner
    ruling 2026-11-07, TITLE_BLOCK_EDGE_BREAK_MAX): the crossbar's front
    full-depth side bottoms from the pocket end to the gusset leg and all
    four gusset hypotenuse bottoms (a knife-mount seat sits over each), the
    hub rib's inner bottom edge (beside the hub boss barrel), the tapered hub
    V-gusset edges (they feather into the underside), the set-screw boss's
    edges on the faced top (machined there, and the top-rim chamfer feature
    would meet its vertical breaks), and every hole, bore, counterbore,
    spot-face, tap and slot edge. The vertical junctions of the bar sides
    with the gusset hypotenuses are re-entrant (225 degrees), not edges to
    break.
    """
    c = EDGE_CHAMFER
    z_col = abs(FRONT_COLUMN_Z)
    lean = POCKET_H * DRAFT_T  # an added face's lean at the flange underside
    recede = FLANGE * DRAFT_T  # a rim's recession at the flange underside
    r_under = _boss_radius(FLANGE_BOT_Y)
    r_bottom = _boss_radius(-HALF_H)
    side_cut = math.sqrt(r_under**2 - (RAIL_W_SIDE / 2.0 - recede) ** 2)  # 14.43
    fr_cut = math.sqrt(r_under**2 - (RAIL_W_FR / 2.0 - recede) ** 2)  # 11.85
    web_cut = math.sqrt(r_bottom**2 - (WEB_T / 2.0) ** 2)  # 20.19
    rib_lo = GOOSENECK_Z - HUB_RIB_W / 2.0  # on the underside
    rib_hi = GOOSENECK_Z + HUB_RIB_W / 2.0
    rib_lo_u, rib_hi_u = rib_lo - lean, rib_hi + lean  # at the flange underside
    out_x_u, in_x_u = OUTER_X - recede, INNER_X + recede
    out_z_u, in_z_u = OUTER_Z - recede, INNER_Z + recede
    y_under = FLANGE_BOT_Y
    y_bottom = -HALF_H
    under = BOTTOM_EDGE_DEG
    # Each flange underside's printed worst shelf, by T family.
    side_shelf = T_FLANGE_SHELF_PRINTED_MIN["side rail"]
    fr_shelf = T_FLANGE_SHELF_PRINTED_MIN["front/rear rail"]
    bar_shelf = T_FLANGE_SHELF_PRINTED_MIN["crossbar"]
    # feature name -> (picks, analytic removal, shared vertices), build order
    groups: dict[str, tuple[list[list[float]], float, int]] = {}
    segments: list[tuple[str, tuple[float, ...], tuple[float, ...]]] = []
    group = ""

    def start(name: str) -> None:
        nonlocal group
        group = name
        groups[name] = ([], 0.0, 0)

    # (edge, plan polygon of its print-worst band on the underside)
    underside_bands: list[
        tuple[tuple[float, float, float], list[tuple[float, float]]]
    ] = []
    band_in = _EDGE_LOCATION_BAND + EDGE_BREAK_PRINTED_MAX

    def convex(point: tuple[float, float, float], axis, angle: float) -> None:
        measured = _interior_angle(point, axis)
        if measured >= 180.0 or abs(measured - angle) > 5.0:
            raise AssertionError(
                f"edge-break pick at {point} claims a convex {angle:g}-degree edge;"
                f" the casting holds {measured:g} degrees round it"
            )

    def edge(
        point: tuple[float, float, float],
        length: float,
        angle: float,
        axis: tuple[float, float, float],
        *,
        printed_length: float | None = None,
        printed_shelf: float | None = None,
    ) -> bool:
        # At the print's limits an edge too short for the printed worst legs
        # at both its ends, or on a flange shelf too narrow for one leg and
        # the sliver land, is left unbroken at .06: no pick.
        if (
            printed_length is not None
            and printed_length <= 2.0 * EDGE_BREAK_PRINTED_MAX
        ) or (
            printed_shelf is not None
            and printed_shelf < EDGE_BREAK_PRINTED_MAX + EDGE_BREAK_SLIVER_MIN
        ):
            return False
        if length <= 2.0 * EDGE_BREAK_PRINTED_MAX:
            raise AssertionError(
                f"edge at {point} is too short for a {EDGE_BREAK_PRINTED_MAX:g}"
                f" printed worst edge break at both ends: {length:.3f}"
            )
        convex(point, axis, angle)
        picks, volume, _ = groups[group]
        picks.append(list(point))
        removal = _chamfer_section_area(c, angle) * length
        groups[group] = (picks, volume + removal, 0)
        segments.append(
            (
                group,
                tuple(point[i] - axis[i] * length / 2.0 for i in range(3)),
                tuple(point[i] + axis[i] * length / 2.0 for i in range(3)),
            )
        )
        x, y, z = point
        low = min(
            (
                tuple(point[i] + s * axis[i] * length / 2.0 for i in range(3))
                for s in (-1.0, 1.0)
            ),
            key=lambda p: p[1],
        )
        if axis[1] == 0.0 and y == y_bottom:
            # Its band runs the edge's length and the location band past
            # each end, the location band outboard and band_in into the face.
            half = length / 2.0 + _EDGE_LOCATION_BAND
            dx, dz = axis[0], axis[2]
            nx, nz = dz, -dx
            if not _casting_occupies(x + 0.01 * nx, y_bottom + 0.01, z + 0.01 * nz):
                nx, nz = -nx, -nz
            underside_bands.append(
                (
                    point,
                    [
                        (x + s * half * dx + t * nx, z + s * half * dz + t * nz)
                        for s, t in (
                            (-1.0, -_EDGE_LOCATION_BAND),
                            (1.0, -_EDGE_LOCATION_BAND),
                            (1.0, band_in),
                            (-1.0, band_in),
                        )
                    ],
                )
            )
        elif abs(axis[1]) > 0.9 and abs(low[1] - y_bottom) < 1e-9:
            # A near-vertical break bevels the underside's corner at its
            # lower end: a band_in square there.
            underside_bands.append(
                (
                    point,
                    [
                        (low[0] + sx * band_in, low[2] + sz * band_in)
                        for sx, sz in (
                            (-1.0, -1.0),
                            (1.0, -1.0),
                            (1.0, 1.0),
                            (-1.0, 1.0),
                        )
                    ],
                )
            )
        return True

    def along_x(
        z: float, y: float, x0: float, x1: float, angle: float = 90.0, **printed: float
    ) -> bool:
        lo, hi = sorted((x0, x1))
        point = ((lo + hi) / 2.0, y, z)
        return edge(point, hi - lo, angle, (1.0, 0.0, 0.0), **printed)

    def along_z(
        x: float, y: float, z0: float, z1: float, angle: float = 90.0, **printed: float
    ) -> bool:
        lo, hi = sorted((z0, z1))
        point = (x, y, (lo + hi) / 2.0)
        return edge(point, hi - lo, angle, (0.0, 0.0, 1.0), **printed)

    def between(
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        angle: float = 90.0,
        **printed: float,
    ) -> bool:
        """A straight edge leaning off the axes: picked at its midpoint."""
        length = math.dist(p0, p1)
        axis = tuple((b - a) / length for a, b in zip(p0, p1))
        point = tuple((a + b) / 2.0 for a, b in zip(p0, p1))
        return edge(point, length, angle, axis, **printed)

    start("RailRunBreaks")
    # Long single runs whose both ends die into corner-boss barrels: the
    # west and front/rear outer flange undersides, the west web bottoms and
    # the front/rear outer web bottoms.
    along_z(
        out_x_u,
        y_under,
        -(z_col - side_cut),
        z_col - side_cut,
        under,
        printed_shelf=side_shelf,
    )
    for sz in (-1.0, 1.0):
        along_x(
            sz * out_z_u,
            y_under,
            -(COLUMN_X - fr_cut),
            COLUMN_X - fr_cut,
            under,
            printed_shelf=fr_shelf,
        )
    for x_web in (WEB_OUT_X, WEB_IN_X):
        along_z(x_web, y_bottom, -(z_col - web_cut), z_col - web_cut, under)
    for sz in (-1.0, 1.0):
        along_x(
            sz * WEB_OUT_Z, y_bottom, -(COLUMN_X - web_cut), COLUMN_X - web_cut, under
        )
    start("CrossbarBreaks")
    # Crossbar: web bottoms; per pocket end its bottom and its outer
    # vertical corner; the rear full-depth side bottoms from the pocket ends
    # to the gusset legs. The T flange's underside edges are picked only on
    # a printed shelf that holds a break (T_FLANGE_SHELF_PRINTED_MIN). The
    # knife-mount seats sit over the front side bottoms and every gusset
    # hypotenuse, whose bottoms take the title block's .010 break instead.
    for x_web in (BAR_WEB_X0, BAR_WEB_X1):
        along_z(x_web, y_bottom, -BAR_POCKET_Z, BAR_POCKET_Z, under)
    for x_bar, out in ((BAR_X0, -1.0), (BAR_X1, 1.0)):
        along_z(
            x_bar + out * lean,
            y_under,
            -(BAR_POCKET_Z - lean),
            BAR_POCKET_Z - lean,
            under,
            printed_shelf=bar_shelf,
        )
        along_z(x_bar, y_bottom, BAR_POCKET_Z, LAND_FACE_Z0 - GUSSET, under)
    for sz in (-1.0, 1.0):
        along_x(sz * BAR_POCKET_Z, y_bottom, BAR_X0, BAR_WEB_X0, under)
        along_x(sz * BAR_POCKET_Z, y_bottom, BAR_WEB_X1, BAR_X1, under)
        for x_bar, out in ((BAR_X0, -1.0), (BAR_X1, 1.0)):
            between(
                (x_bar, y_bottom, sz * BAR_POCKET_Z),
                (x_bar + out * lean, y_under, sz * (BAR_POCKET_Z - lean)),
            )
    start("WestWindowBreaks")
    # The west window's flange underside, round its corners into the
    # front/rear runs to the junction lands, the lands' free vertical
    # corners, end bottoms and short window-face bottoms (to the gusset
    # hypotenuse, unbroken at .06), and the front/rear window web bottoms the land
    # ends meet.
    along_z(in_x_u, y_under, -in_z_u, in_z_u, under, printed_shelf=side_shelf)
    for sz in (-1.0, 1.0):
        along_x(
            sz * in_z_u, y_under, LAND_X1 + lean, in_x_u, under, printed_shelf=fr_shelf
        )
        between(
            (LAND_X1, y_bottom, sz * LAND_FACE_Z0),
            (LAND_X1 + lean, y_under, sz * in_z_u),
        )
        along_z(LAND_X1, y_bottom, sz * LAND_FACE_Z0, sz * WEB_IN_Z, under)
        along_x(sz * LAND_FACE_Z0, y_bottom, BAR_X1 + GUSSET, LAND_X1, under)
        along_x(sz * WEB_IN_Z, y_bottom, LAND_X1, COLUMN_X - web_cut, under)
    start("HubRailBreaks")
    # The east (hub) side, all one chain: the outer and window flange
    # undersides split by the hub rib, the rib's four free vertical
    # corners, its side bottoms out to the web faces (each meeting its web
    # bottom at one vertex: the boss chord stays inside the web), the east
    # web bottoms, and the east window's front/rear runs, land edges and
    # window web bottoms as on the west.
    along_z(-out_x_u, y_under, -(z_col - side_cut), rib_lo_u, under, printed_shelf=side_shelf)
    along_z(-out_x_u, y_under, rib_hi_u, z_col - side_cut, under, printed_shelf=side_shelf)
    along_z(-in_x_u, y_under, -in_z_u, rib_lo_u, under, printed_shelf=side_shelf)
    along_z(-in_x_u, y_under, rib_hi_u, in_z_u, under, printed_shelf=side_shelf)
    for z_rib, z_rib_u in ((rib_lo, rib_lo_u), (rib_hi, rib_hi_u)):
        for x_face, x_face_u in ((-RIB_OUT_X0, -out_x_u), (-RIB_IN_X0, -in_x_u)):
            between((x_face, y_bottom, z_rib), (x_face_u, y_under, z_rib_u))
        along_x(z_rib, y_bottom, -RIB_OUT_X0, -WEB_OUT_X, under)
        along_x(z_rib, y_bottom, -WEB_IN_X, -RIB_IN_X0, under)
    for x_web in (WEB_OUT_X, WEB_IN_X):
        along_z(-x_web, y_bottom, -(z_col - web_cut), rib_lo, under)
        along_z(-x_web, y_bottom, rib_hi, z_col - web_cut, under)
    for sz in (-1.0, 1.0):
        along_x(
            sz * in_z_u, y_under, -in_x_u, LAND_X0 - lean, under, printed_shelf=fr_shelf
        )
        between(
            (LAND_X0, y_bottom, sz * LAND_FACE_Z0),
            (LAND_X0 - lean, y_under, sz * in_z_u),
        )
        along_z(LAND_X0, y_bottom, sz * LAND_FACE_Z0, sz * WEB_IN_Z, under)
        along_x(sz * LAND_FACE_Z0, y_bottom, LAND_X0, BAR_X0 - GUSSET, under)
        along_x(sz * WEB_IN_Z, y_bottom, -(COLUMN_X - web_cut), LAND_X0, under)
    # The set-screw boss proud of the rib's outer face, full height: the
    # vertical corners of its cast face up to the faced top, and its bottom
    # edges round the face and back to the rib, meeting at the face's
    # corners. The breaks leave the Ø10 spot face SET_SPOT_LAND_MIN
    # (print-worst). The rib's outer bottom either side of it joins the
    # boss's breaks to the rib's when its printed worst length
    # (HUB_RIB_STUB_PRINTED_MIN) holds both legs, as it does; else the
    # boss's breaks are a chain of their own.
    boss_lo = GOOSENECK_Z - HUB_SET_BOSS_W / 2.0
    boss_hi = GOOSENECK_Z + HUB_SET_BOSS_W / 2.0
    stubs = (
        along_z(
            -RIB_OUT_X0,
            y_bottom,
            rib_lo,
            boss_lo,
            under,
            printed_length=HUB_RIB_STUB_PRINTED_MIN,
        ),
        along_z(
            -RIB_OUT_X0,
            y_bottom,
            boss_hi,
            rib_hi,
            under,
            printed_length=HUB_RIB_STUB_PRINTED_MIN,
        ),
    )
    if not any(stubs):
        start("HubSetBossBreaks")
    for z_side, out in ((boss_lo, -1.0), (boss_hi, 1.0)):
        between(
            (SET_BOSS_FACE_X0, y_bottom, z_side),
            (SET_BOSS_FACE_X, HALF_H, z_side + out * RIM_RECEDE),
        )
        along_x(z_side, y_bottom, SET_BOSS_FACE_X0, -RIB_OUT_X0, under)
    along_z(SET_BOSS_FACE_X0, y_bottom, boss_lo, boss_hi, under)
    # Boss rims: the four corner bosses top and bottom, and the hub boss --
    # closed circles that meet no other break.
    start("BossRimBreaks")
    rims: list[tuple[tuple[float, float, float], float]] = []

    def rim(centre: tuple[float, float, float], radius: float, sx: float) -> None:
        # Picked on the outboard (sx) side of the circle.
        point = (centre[0] + sx * radius, centre[1], centre[2])
        convex(point, (0.0, 0.0, 1.0), under)
        picks, volume, _ = groups[group]
        picks.append(list(point))
        removal = 2.0 * math.pi * (radius - c / 3.0) * _chamfer_section_area(c, under)
        groups[group] = (picks, volume + removal, 0)
        rims.append((centre, radius))

    for sx in (-1.0, 1.0):
        for z_world in (FRONT_COLUMN_Z, REAR_COLUMN_Z):
            for y_rim in (HALF_H + BOSS_ABOVE, -(HALF_H + BOSS_BELOW)):
                rim((sx * COLUMN_X, y_rim, z_world), _boss_radius(y_rim), sx)
    rim(
        (GOOSENECK_X, HUB_GUSSET_BOTTOM_Y, GOOSENECK_Z),
        HUB_BOSS_DIA / 2.0 - HUB_BOSS_DROP * DRAFT_T,
        -1.0,
    )
    # Any two breaks either share a vertex -- then one feature must cut both,
    # so SolidWorks blends that corner -- or stay 2 EDGE_BREAK_PRINTED_MAX +
    # EDGE_BREAK_SLIVER_MIN apart, so no two breaks at their printed worst
    # legs leave a sliver between them. Each group's shared vertices size
    # its volume tolerance.
    reach = 2.0 * EDGE_BREAK_PRINTED_MAX + EDGE_BREAK_SLIVER_MIN
    for i, (group_a, p0, p1) in enumerate(segments):
        for group_b, q0, q1 in segments[i + 1 :]:
            gap = _segment_gap(p0, p1, q0, q1)
            if gap < 1e-9:
                if group_a != group_b:
                    raise AssertionError(
                        f"edge breaks in {group_a} and {group_b} meet at a vertex"
                        f" near {p0}..{p1}; one feature must cut both"
                    )
                picks, volume, shared = groups[group_a]
                groups[group_a] = (picks, volume, shared + 1)
            elif gap < reach - 1e-9:
                raise AssertionError(
                    f"edge breaks {p0}..{p1} ({group_a}) and {q0}..{q1}"
                    f" ({group_b}) stop {gap:.3f} mm apart; their printed worst"
                    f" faces would leave a sliver under {EDGE_BREAK_SLIVER_MIN:g}"
                )
        for centre, radius in rims:
            gap = min(
                math.hypot(
                    math.hypot(p[0] - centre[0], p[2] - centre[2]) - radius,
                    p[1] - centre[1],
                )
                for k in range(201)
                for p in [tuple(p0[j] + (p1[j] - p0[j]) * k / 200.0 for j in range(3))]
            )
            if gap < reach - 1e-9:
                raise AssertionError(
                    f"edge break {p0}..{p1} comes {gap:.3f} mm from a boss rim"
                )
    # Neither knife-mount seat may sit on, or within the clearance of, a
    # finished edge-break band.
    seat_clearance = {}
    for mount, footprint in KNIFE_SEAT_FOOTPRINTS.items():
        gap, nearest = min(
            (_plan_gap(band, footprint), where) for where, band in underside_bands
        )
        if gap < KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE:
            raise AssertionError(
                f"edge break at {nearest} comes within {gap:.3f} mm of the "
                f"print-worst {mount} knife-mount seat (needs "
                f"{KNIFE_SEAT_EDGE_BREAK_MIN_CLEARANCE:g})"
            )
        seat_clearance[mount] = gap
    return groups, seat_clearance


EXTERNAL_EDGE_BREAKS, KNIFE_SEAT_EDGE_BREAK_CLEARANCE = _external_edge_breaks()


def _open_underside_sketch(
    adapter, centres: list[tuple[float, float, float]]
) -> tuple[list[tuple[float, float]], bool, bool]:
    """Open a sketch ON the crossbar underside; map the dowel ream centres in.

    A face sketch anchors the blind depth on the real underside (the
    pd_transgear_arm latch-pin precedent): a negative Top-plane offset would
    leave its sketch handedness to SolidWorks.  The face's sketch axes are
    SolidWorks' choice too, so the centres map through
    ``ModelToSketchTransform``.  Returns each centre's sketch ``(u, v)``,
    whether sketch u carries model X, and whether the sketch normal points
    OUT of the underside (-Y).
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    face = find_planar_face(model, (0.0, -1.0, 0.0), [list(c) for c in centres])
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError("dowel reams: crossbar underside Select2 failed")
    adapter.currentSketchManager = model.SketchManager
    adapter._reset_sketch_entity_registry()
    model.SketchManager.InsertSketch(True)
    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("dowel reams: no active sketch on the underside")
    adapter.currentSketch = active
    adapter._sketch_count += 1
    adapter._last_sketch_name = str(active.Name)
    sketch = _early_bound(active, "ISketch")
    to_sketch = _model_to_sketch(adapter, sketch)

    mapped = [to_sketch(centre) for centre in centres]
    for centre, (_u, _v, w) in zip(centres, mapped):
        if abs(w) > 1e-4:
            raise RuntimeError(
                f"dowel ream {centre} is {w:g} mm off the underside sketch"
            )
    x0, y0, z0 = centres[0]
    du, dv, _dw = (a - b for a, b in zip(to_sketch((x0 + 1.0, y0, z0)), mapped[0]))
    if abs(abs(du) - 1.0) < 1e-4 and abs(dv) < 1e-4:
        u_is_x = True
    elif abs(abs(dv) - 1.0) < 1e-4 and abs(du) < 1e-4:
        u_is_x = False
    else:
        raise RuntimeError(f"underside sketch axes are not along X/Z ({du:g}, {dv:g})")
    w_out = to_sketch((x0, y0 - 1.0, z0))[2]
    if abs(abs(w_out) - 1.0) > 1e-4:
        raise RuntimeError(f"underside sketch normal is not along Y (w {w_out:g})")
    return [(u, v) for u, v, _w in mapped], u_is_x, w_out > 0.0


def _model_to_sketch(adapter, sketch):
    """Map model mm into ``sketch``'s own ``(u, v, w)`` mm.

    Face and offset-plane sketch axes are SolidWorks' choice, so callers map
    model points through the live ``ModelToSketchTransform`` rather than
    assume a handedness; ``w`` is the distance off the sketch plane.
    """
    import pythoncom
    from win32com.client import VARIANT

    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    return to_sketch


# The finished solid's outermost point along each plan diagonal is its corner
# boss barrel; a flange corner left outside the barrel reached 345.1 less its
# vertical edge break. IBody2::GetExtremePoint returns the solid's furthest point.
CORNER_BOSS_SUPPORT = COLUMN_X + abs(FRONT_COLUMN_Z) + _BOSS_R * math.sqrt(2.0)
CORNER_SUPPORT_TOL_MM = 1e-3  # far inside the nib's 2.69 mm excess


def _corner_support_problems(
    extremes: dict[tuple[float, float], tuple],
) -> list[str]:
    """Why the finished solid reaches past a corner boss barrel.

    ``extremes`` maps each plan diagonal ``(sx, sz)`` to
    ``IBody2::GetExtremePoint(sx, 0, sz)``'s ``(ok, x, y, z)`` in metres; its
    support ``sx * x + sz * z`` must be the barrel's CORNER_BOSS_SUPPORT.
    """
    problems = []
    for (sx, sz), result in extremes.items():
        if not result or len(result) < 4 or not result[0]:
            problems.append(f"({sx:+.0f}, {sz:+.0f}): GetExtremePoint failed")
            continue
        support = (sx * float(result[1]) + sz * float(result[3])) * 1000.0
        if abs(support - CORNER_BOSS_SUPPORT) > CORNER_SUPPORT_TOL_MM:
            problems.append(
                f"({sx:+.0f}, {sz:+.0f}): reaches {support:.4f} mm, the boss"
                f" barrel {CORNER_BOSS_SUPPORT:.4f} mm"
            )
    return problems


def _assert_flange_corners_cropped(adapter) -> None:
    """Prove on the finished solid that no flange corner stands outside its
    boss barrel: along every plan diagonal the barrel is outermost."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"top frame must be one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    extremes = {
        (sx, sz): body.GetExtremePoint(sx, 0.0, sz)
        for sx in (-1.0, 1.0)
        for sz in (-1.0, 1.0)
    }
    problems = _corner_support_problems(extremes)
    if problems:
        raise RuntimeError("flange corner outside its boss barrel: " + "; ".join(problems))
    _telemetry.success(
        f"all four flange corners end on their barrels ({CORNER_BOSS_SUPPORT:.4f} mm)"
    )


def _qualify_machined_faces(adapter) -> None:
    """Area-check every face the surface-finish spec owns.

    ``resolve_faces`` already proves each spec names exactly ONE face; the
    area proves it named the RIGHT one, so a station typo ships a build failure
    instead of a roughness symbol on the wrong surface (build_fr_harmonic_base's
    _paint_machined_faces_black precedent). Each socket wall's expectation is
    the full analytic cylinder; the 5% band absorbs the cross-screw clearance
    and tap windows that break into the bores (~1.4% together) and the C1
    bore-top breaks.  Each boss top's is the annulus between its barrel's rim
    break and its cap recess's mouth chamfer; the band absorbs which face of
    the drafted rim takes the break's leg.
    """
    faces = resolve_faces(
        adapter.currentModel,
        {control.key: control.face for control in SURFACE_FINISHES},
    )
    socket_wall = math.pi * BORE_DIA * (CAP_RECESS_FLOOR_Y + HALF_H + BOSS_BELOW)
    boss_top = math.pi * (
        (_boss_radius(HALF_H + BOSS_ABOVE) - EDGE_CHAMFER) ** 2
        - (CAP_RECESS_DIAMETER / 2.0 + BORE_CHAMFER) ** 2
    )
    for key, face in faces.items():
        expected = boss_top if key.startswith("boss_top_") else socket_wall
        area = float(face.GetArea()) * 1e6
        if abs(area - expected) > 0.05 * expected:
            raise RuntimeError(
                f"{key} face area {area:.0f} mm^2 != {expected:.0f} "
                "(minus tap windows and edge breaks)"
            )
        _telemetry.info(f"{key} face qualified ({area:.0f} mm^2)")


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (the setter is
    on ISketchSegment, not the ISketchLine the registry binds)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _carrier(adapter, start, end) -> str:
    """One construction line for a printed dimension to stand on.  Its ends
    are drawn clear of every profile vertex, so relations place them."""
    (line,) = await add_line_chain(adapter, [start, end], close=False)
    _as_construction(adapter, line)
    return line


async def _relate(adapter, label: str, first: str, second: str | None, relation: str):
    check(label, await adapter.add_sketch_constraint(first, second, relation))


async def _plain_rectangle(adapter, points, label: str) -> list[str]:
    """A closed axis-parallel chain with its horizontal/vertical relations
    and no dimension: line i runs points[i] -> points[i + 1]."""
    lines = await add_line_chain(adapter, points)
    for i, line in enumerate(lines):
        (_x1, y1), (_x2, y2) = points[i], points[(i + 1) % len(points)]
        await _relate(
            adapter,
            f"{label} {line}",
            line,
            None,
            "horizontal" if y1 == y2 else "vertical",
        )
    return lines


async def _centred_rectangle(adapter, half_x: float, half_z: float, label: str):
    """An origin-centred rectangle left for its caller to size (the
    ``define_centered_rectangle`` recipe without its two dimensions): lines
    0..3 are the rear (+Z), west (+X), front and east edges under the Top
    plane's (x, y) -> (X, -Z)."""
    points = [
        (-half_x, -half_z),
        (half_x, -half_z),
        (half_x, half_z),
        (-half_x, half_z),
    ]
    lines = await _plain_rectangle(adapter, points, label)
    # Corner to corner: the diagonal's ends merge with the corners they are
    # drawn on, so its midpoint centres the rectangle.
    (diagonal,) = await add_line_chain(adapter, [points[0], points[2]], close=False)
    _as_construction(adapter, diagonal)
    await _relate(adapter, f"{label} centre -> origin", "origin", diagonal, "midpoint")
    return lines


def _extreme_point(adapter, direction: tuple[float, float, float]) -> tuple:
    """The one solid's furthest point (mm) along ``direction``."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"top frame must be one solid body, found {len(bodies)}")
    result = _early_bound(bodies[0], "IBody2").GetExtremePoint(*direction)
    if not result or len(result) < 4 or not result[0]:
        raise RuntimeError(f"GetExtremePoint{direction} failed: {result!r}")
    return tuple(float(value) * 1000.0 for value in result[1:4])


STATION_TOL_MM = 1e-3


def _assert_station(
    adapter, label: str, direction: tuple[float, float, float], expected: dict
) -> None:
    """Prove where a drafted feature landed: the solid's furthest point along
    ``direction`` reads ``expected`` ({axis index: mm}).  A drafted prism's
    volume cannot tell which side of its sketch plane it stands on."""
    point = _extreme_point(adapter, direction)
    off = {
        "xyz"[axis]: (point[axis], value)
        for axis, value in expected.items()
        if abs(point[axis] - value) > STATION_TOL_MM
    }
    if off:
        raise RuntimeError(
            f"{label}: furthest point along {direction} is {point}; (found, expected)"
            f" {off}"
        )
    _telemetry.success(f"{label}: furthest point along {direction} at {point}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs: named equation-manager globals (mm) drive the primary
    # envelope sketches. A GUI fine-tune edits THESE -- e.g. RailWSide or
    # BossDia -- never an auto "D7@Sketch3". Explicit `mm`: inch document,
    # bare equation numbers evaluate in document units.
    await set_global(adapter, "ColumnX", f"{COLUMN_X}mm")
    await set_global(adapter, "ColumnZ", f"{abs(FRONT_COLUMN_Z)}mm")
    await set_global(adapter, "RailWSide", f"{RAIL_W_SIDE}mm")
    await set_global(adapter, "RailWFR", f"{RAIL_W_FR}mm")
    await set_global(adapter, "BossDia", f"{BOSS_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "CapRecessDia", f"{CAP_RECESS_DIAMETER}mm")
    await set_global(adapter, "CapRecessDepth", f"{CAP_RECESS_DEPTH}mm")
    await set_global(adapter, "GooseneckZ", f"{GOOSENECK_Z}mm")
    await set_global(adapter, "GooseneckBoreDia", f"{GOOSENECK_BORE_DIA}mm")
    await set_global(adapter, "RingHeight", f"{RING_HEIGHT}mm")
    await set_global(adapter, "BossAbove", f"{BOSS_ABOVE}mm")
    await set_global(adapter, "BossBelowTop", f"{RING_HEIGHT + BOSS_BELOW}mm")
    await set_global(adapter, "HubBossDrop", f"{HUB_BOSS_DROP}mm")
    await set_global(adapter, "HubBossDia", f"{HUB_BOSS_DIA}mm")
    await set_global(adapter, "WebT", f"{WEB_T}mm")
    await set_global(adapter, "Flange", f"{FLANGE}mm")
    await set_global(adapter, "HangerPinHoleDia", f"{HANGER_PIN_HOLE_DIA}mm")
    await set_global(adapter, "HangerPinHoleDepth", f"{HANGER_PIN_HOLE_DEPTH}mm")
    await set_global(adapter, "OuterX", '"ColumnX" + "RailWSide" / 2')
    await set_global(adapter, "OuterZ", '"ColumnZ" + "RailWFR" / 2')
    await set_global(adapter, "InnerX", '"ColumnX" - "RailWSide" / 2')
    await set_global(adapter, "InnerZ", '"ColumnZ" - "RailWFR" / 2')

    drive_jobs: list[tuple[str, str]] = []
    ref_planes: list[str] = []  # created offset planes, blanked before save

    # Every cast wall is a blind extrude drafted from the faced plane its
    # nominal stands on (_drafted_extrude): added draft starts on the
    # underside and widens up, taken-out draft starts on the faced top (the
    # hub barrel on the underside) and narrows away from it.  Each is accepted
    # by its drafted prism's volume and named with its depth, its start and
    # its draft angle.
    volume = 0.0
    drafted_depths: dict[str, float] = {}
    if not DRAFT_TAKEN_OUT_ON_UNNAMED_FACES:
        raise AssertionError(
            "owner ruling D1 (#2333) takes the draft out on the flange rims, the"
            " hub boss barrel and the set-screw boss face; this recipe builds and"
            " proves that sense only"
        )

    async def drafted(
        sketch: str,
        feature: str,
        label: str,
        *,
        depth: float,
        depth_name: str,
        start: float,
        up: bool,
        narrowing: bool,
        change: float,
        tol: float,
        cut: bool = False,
    ) -> None:
        nonlocal volume
        volume = await drafted_extrude(
            adapter,
            sketch,
            feature,
            label,
            cut=cut,
            depth=depth,
            angle_deg=DRAFT_DEG,
            forms=drafted_forms(
                cut=cut, start=start, along_normal=up, narrowing=narrowing
            ),
            volume=volume,
            change=change,
            tol=tol,
        )
        drafted_depths[feature] = depth
        name_feature_dimensions(
            adapter,
            feature,
            lengths={depth_name: depth, f"{feature}Start": start},
            angles={f"{feature}Draft": DRAFT_DEG},
        )

    async def across(
        sketch_dims: SketchDims,
        label: str,
        first: str,
        second: str,
        kind: str,
        value: float,
        name: str,
        drive: str | None = None,
    ) -> None:
        await dimension_between(adapter, first, second, kind, value, label)
        sketch_dims.record(name, drive)

    # 1. Web ring: the full-height THIN section (T-rail web) as one annular
    #    extrude -- two nested origin-centred rectangles, the WEB_T-wide web
    #    centred on each rail's centreline (per-face setback: side rails
    #    10.6, front/rear 12.5), drafted out from the underside.  The inner
    #    rectangle is sized by the two printed web thicknesses, each on a
    #    construction line across its web at the station its section cuts.
    #    Sketch z flipped: (x, y) -> (X, -Z).
    web = SketchDims()
    check("create_sketch web ring", await adapter.create_sketch("Top"))
    web_outer = await _centred_rectangle(
        adapter, WEB_OUT_X, WEB_OUT_Z, "web outer rectangle"
    )
    await across(
        web,
        "web outer width",
        f"{web_outer[0]}.start",
        f"{web_outer[0]}.end",
        "horizontal_distance",
        2.0 * WEB_OUT_X,
        "WebOuterWidth",
        '2 * "ColumnX" + "WebT"',
    )
    await across(
        web,
        "web outer depth",
        f"{web_outer[1]}.start",
        f"{web_outer[1]}.end",
        "vertical_distance",
        2.0 * WEB_OUT_Z,
        "WebOuterDepth",
        '2 * "ColumnZ" + "WebT"',
    )
    web_inner = await _centred_rectangle(
        adapter, WEB_IN_X, WEB_IN_Z, "web inner rectangle"
    )
    side_web = await _carrier(
        adapter, (-WEB_OUT_X, -SIDE_SECTION_Z), (-WEB_IN_X, -SIDE_SECTION_Z)
    )
    await _relate(adapter, "side web line level", side_web, None, "horizontal")
    await _relate(
        adapter,
        "side web line on the outer face",
        f"{side_web}.start",
        f"{web_outer[3]}.start",
        "vertical_points",
    )
    await _relate(
        adapter,
        "side web line on the inner face",
        f"{side_web}.end",
        f"{web_inner[3]}.start",
        "vertical_points",
    )
    await across(
        web,
        "side web station",
        f"{side_web}.start",
        "origin",
        "vertical_distance",
        abs(SIDE_SECTION_Z),
        "SideWebStation",
    )
    await across(
        web,
        "side web thickness",
        f"{side_web}.start",
        f"{side_web}.end",
        "horizontal_distance",
        WEB_T,
        "SideWebT",
        '"WebT"',
    )
    fr_web = await _carrier(
        adapter, (RAIL_SECTION_X, -WEB_IN_Z), (RAIL_SECTION_X, -WEB_OUT_Z)
    )
    await _relate(adapter, "rear web line plumb", fr_web, None, "vertical")
    await _relate(
        adapter,
        "rear web line on the inner face",
        f"{fr_web}.start",
        f"{web_inner[0]}.start",
        "horizontal_points",
    )
    await _relate(
        adapter,
        "rear web line on the outer face",
        f"{fr_web}.end",
        f"{web_outer[0]}.start",
        "horizontal_points",
    )
    await across(
        web,
        "rear web station",
        f"{fr_web}.start",
        "origin",
        "horizontal_distance",
        RAIL_SECTION_X,
        "FrWebStation",
    )
    await across(
        web,
        "rear web thickness",
        f"{fr_web}.start",
        f"{fr_web}.end",
        "vertical_distance",
        WEB_T,
        "FrWebT",
        '"WebT"',
    )
    await ensure_fully_defined(adapter, "web ring sketch")
    check("exit_sketch web ring", await adapter.exit_sketch())
    name_last_feature(adapter, "WebProfile")
    drive_jobs += web.apply(adapter, "WebProfile")
    v_web = _web_ring_volume()
    await drafted(
        "WebProfile",
        "WebRing",
        "web ring",
        depth=RING_HEIGHT,
        depth_name="RingHeight",
        start=-HALF_H,
        up=True,
        narrowing=False,
        change=v_web,
        tol=0.001 * v_web,
    )
    drive_jobs.append(("RingHeight@WebRing", '"RingHeight"'))
    _assert_station(adapter, "web ring top", (0.0, 1.0, 0.0), {1: HALF_H})
    _assert_station(adapter, "web ring underside", (0.0, -1.0, 0.0), {1: -HALF_H})
    _assert_station(
        adapter,
        "web ring widest on the top",
        (1.0, 0.0, 0.0),
        {0: WEB_OUT_X + RIM_RECEDE, 1: HALF_H},
    )

    # 2. Top flange ring: the full-width .32 band, drafted in from the faced
    #    top, where both rims stand at their nominal.  The OUTER rectangle
    #    carries the print's marked Width/Depth dims (OuterProfile contract);
    #    the window is sized by the two printed flange widths, each on a
    #    construction line across its rail.
    outer = SketchDims()
    check("create_sketch flange ring", await adapter.create_sketch("Top"))
    rim = await _centred_rectangle(adapter, OUTER_X, OUTER_Z, "flange outer rectangle")
    await across(
        outer,
        "flange width",
        f"{rim[0]}.start",
        f"{rim[0]}.end",
        "horizontal_distance",
        2.0 * OUTER_X,
        "Width",
        '2 * "OuterX"',
    )
    await across(
        outer,
        "flange depth",
        f"{rim[1]}.start",
        f"{rim[1]}.end",
        "vertical_distance",
        2.0 * OUTER_Z,
        "Depth",
        '2 * "OuterZ"',
    )
    window = await _centred_rectangle(
        adapter, INNER_X, INNER_Z, "flange window rectangle"
    )
    side_flange = await _carrier(adapter, (INNER_X, 0.0), (OUTER_X, 0.0))
    for end, edge, face in (("start", window[1], "window"), ("end", rim[1], "outer")):
        await _relate(
            adapter,
            f"side flange line on the rail centre ({face})",
            f"{side_flange}.{end}",
            "origin",
            "horizontal_points",
        )
        await _relate(
            adapter,
            f"side flange line on the {face} rim",
            f"{side_flange}.{end}",
            f"{edge}.start",
            "vertical_points",
        )
    await across(
        outer,
        "side flange width",
        f"{side_flange}.start",
        f"{side_flange}.end",
        "horizontal_distance",
        RAIL_W_SIDE,
        "SideFlangeWidth",
        '"RailWSide"',
    )
    fr_flange = await _carrier(
        adapter, (RAIL_SECTION_X, -INNER_Z), (RAIL_SECTION_X, -OUTER_Z)
    )
    await _relate(adapter, "rear flange line plumb", fr_flange, None, "vertical")
    await _relate(
        adapter,
        "rear flange line on the window rim",
        f"{fr_flange}.start",
        f"{window[0]}.start",
        "horizontal_points",
    )
    await _relate(
        adapter,
        "rear flange line on the outer rim",
        f"{fr_flange}.end",
        f"{rim[0]}.start",
        "horizontal_points",
    )
    await across(
        outer,
        "rear flange station",
        f"{fr_flange}.start",
        "origin",
        "horizontal_distance",
        RAIL_SECTION_X,
        "FrFlangeStation",
    )
    await across(
        outer,
        "rear flange width",
        f"{fr_flange}.start",
        f"{fr_flange}.end",
        "vertical_distance",
        RAIL_W_FR,
        "FrFlangeWidth",
        '"RailWFR"',
    )
    await ensure_fully_defined(adapter, "flange ring sketch")
    check("exit_sketch flange ring", await adapter.exit_sketch())
    name_last_feature(adapter, "OuterProfile")
    drive_jobs += outer.apply(adapter, "OuterProfile")
    # New material only where the flange band is not already web solid.
    await drafted(
        "OuterProfile",
        "TopFlange",
        "top flange",
        depth=FLANGE,
        depth_name="FlangeT",
        start=HALF_H,
        up=False,
        narrowing=True,
        change=_flange_add_volume(),
        tol=100.0,
    )
    drive_jobs.append(("FlangeT@TopFlange", '"Flange"'))
    _assert_station(
        adapter,
        "flange rim nominal on the top",
        (1.0, 0.0, 0.0),
        {0: OUTER_X, 1: HALF_H},
    )

    # 3. Hub rib restore: full rail thickness across the east rail at the
    #    gooseneck station, from the underside to the flange (the web setback
    #    comes back).  Its faces continue the rims' planes down, so it starts
    #    RIM_RECEDE inside them on the underside.
    rib = SketchDims()
    check("create_sketch hub rib", await adapter.create_sketch("Top"))
    rib_pts = [
        (-RIB_OUT_X0, -(GOOSENECK_Z + HUB_RIB_W / 2.0)),
        (-RIB_IN_X0, -(GOOSENECK_Z + HUB_RIB_W / 2.0)),
        (-RIB_IN_X0, -(GOOSENECK_Z - HUB_RIB_W / 2.0)),
        (-RIB_OUT_X0, -(GOOSENECK_Z - HUB_RIB_W / 2.0)),
    ]
    rib_lines = await add_line_chain(adapter, rib_pts)
    await define_rectilinear_chain(
        adapter,
        rib_lines,
        rib_pts,
        label="hub rib",
        dims=rib,
        names=["RibRun", "RibWidth", "RibOffX", "RibOffZ"],
    )
    await ensure_fully_defined(adapter, "hub rib sketch")
    check("exit_sketch hub rib", await adapter.exit_sketch())
    name_last_feature(adapter, "RibProfile")
    drive_jobs += rib.apply(adapter, "RibProfile")
    await drafted(
        "RibProfile",
        "HubRib",
        "hub rib",
        depth=POCKET_H,
        depth_name="RibHeight",
        start=-HALF_H,
        up=True,
        narrowing=False,
        change=_hub_rib_add_volume(),
        tol=30.0,
    )

    # 4. Integral crossbar, its four plan gussets and both junction lands:
    #    ONE 16-vertex polygon drafted out from the underside, so the printed
    #    widths are its own vertices' -- the bar across its sides (datum D),
    #    a gusset's run and a land's end off the bar.  Each land's window face
    #    continues its rim's plane down (LAND_FACE_Z0) and its back is buried
    #    LAND_WEB_BURY in the web.  Sketch z flipped: (x, y) -> (X, -Z).
    z_land, z_bury = LAND_FACE_Z0, WEB_IN_Z + LAND_WEB_BURY
    bar_pts_part = [
        (BAR_X0, -z_land + GUSSET),  # 0 east side, front gusset
        (BAR_X0 - GUSSET, -z_land),  # 1 its foot on the front land
        (LAND_X0, -z_land),  # 2 front land, east end
        (LAND_X0, -z_bury),  # 3
        (LAND_X1, -z_bury),  # 4
        (LAND_X1, -z_land),  # 5 front land, west end
        (BAR_X1 + GUSSET, -z_land),  # 6 west gusset's foot
        (BAR_X1, -z_land + GUSSET),  # 7 west side, front gusset
        (BAR_X1, z_land - GUSSET),  # 8 west side, rear gusset
        (BAR_X1 + GUSSET, z_land),  # 9
        (LAND_X1, z_land),  # 10 rear land, west end
        (LAND_X1, z_bury),  # 11
        (LAND_X0, z_bury),  # 12
        (LAND_X0, z_land),  # 13 rear land, east end
        (BAR_X0 - GUSSET, z_land),  # 14
        (BAR_X0, z_land - GUSSET),  # 15 east side, rear gusset
    ]
    bar_pts = [(x, -z) for x, z in bar_pts_part]
    bar = SketchDims()
    check("create_sketch crossbar", await adapter.create_sketch("Top"))
    bar_lines = await add_line_chain(adapter, bar_pts)
    at = [f"{line}.start" for line in bar_lines]  # at[i] is vertex i
    for i, relation in (
        (1, "horizontal"),
        (2, "vertical"),
        (3, "horizontal"),
        (4, "vertical"),
        (5, "horizontal"),
        (7, "vertical"),
        (9, "horizontal"),
        (10, "vertical"),
        (11, "horizontal"),
        (12, "vertical"),
        (13, "horizontal"),
        (15, "vertical"),
    ):
        await _relate(
            adapter, f"crossbar {bar_lines[i]} {relation}", bar_lines[i], None, relation
        )
    for label, first, second, kind, value, name in (
        ("crossbar east side", at[0], "origin", "horizontal_distance", abs(BAR_X0), "BarAnchorX"),
        ("crossbar width", at[0], at[7], "horizontal_distance", BAR_X1 - BAR_X0, "BarWidth"),
        ("gusset run", at[7], at[6], "horizontal_distance", GUSSET, "GussetRunE"),
        ("east gusset run", at[0], at[1], "horizontal_distance", GUSSET, "GussetRunE2"),
        ("land end", at[0], at[2], "horizontal_distance", BAR_X0 - LAND_X0, "LandEnd"),
        ("west land end", at[7], at[5], "horizontal_distance", LAND_X1 - BAR_X1, "LandEndW"),
    ):
        await across(bar, label, first, second, kind, value, name)
    for label, first, second in (
        ("rear west foot over the front one", at[9], at[6]),
        ("rear land west end over the front one", at[10], at[5]),
        ("rear land east end over the front one", at[13], at[2]),
        ("rear east foot over the front one", at[14], at[1]),
    ):
        await _relate(adapter, f"crossbar {label}", first, second, "vertical_points")
    await across(
        bar, "front land face", at[1], "origin", "vertical_distance", z_land, "LandFaceZ"
    )
    await _relate(
        adapter, "crossbar front land ends level", at[5], at[2], "horizontal_points"
    )
    await across(
        bar, "gusset rise", at[0], at[1], "vertical_distance", GUSSET, "GussetRise"
    )
    await _relate(
        adapter, "crossbar front gusset heads level", at[7], at[0], "horizontal_points"
    )
    await across(
        bar, "land depth", at[2], at[3], "vertical_distance", z_bury - z_land, "LandDepth"
    )
    await across(
        bar, "rear land face", at[14], "origin", "vertical_distance", z_land, "LandFaceZRear"
    )
    await _relate(
        adapter, "crossbar rear feet level", at[9], at[14], "horizontal_points"
    )
    await across(
        bar, "rear gusset rise", at[15], at[14], "vertical_distance", GUSSET, "GussetRiseRear"
    )
    await _relate(
        adapter, "crossbar rear gusset heads level", at[8], at[15], "horizontal_points"
    )
    await across(
        bar,
        "rear land depth",
        at[13],
        at[12],
        "vertical_distance",
        z_bury - z_land,
        "LandDepthRear",
    )
    # Datum D's station (owner ruling D2).  Two equal construction halves
    # span the bar from side to side, so the point they share stands on its
    # median; a third line carries the printed station to that median from
    # the G plane, the rear-west barrel's datum-target tangent.  Both stand
    # in front of the front bosses, so the dimension's extension lines start
    # clear of the casting.
    span_y, station_y = -(D_STATION_LINE_Z - D_STATION_SPAN_STEP), -D_STATION_LINE_Z
    half_east, half_west = await add_line_chain(
        adapter, [(BAR_X0, span_y), (HANGER_X, span_y), (BAR_X1, span_y)], close=False
    )
    for half in (half_east, half_west):
        _as_construction(adapter, half)
        await _relate(adapter, f"crossbar span {half} level", half, None, "horizontal")
    await _relate(
        adapter, "crossbar span on the east side", f"{half_east}.start", at[0],
        "vertical_points",
    )
    await _relate(
        adapter, "crossbar span on the west side", f"{half_west}.end", at[7],
        "vertical_points",
    )
    await _relate(adapter, "crossbar span halves equal", half_east, half_west, "equal")
    await across(
        bar, "crossbar span level", f"{half_east}.start", "origin",
        "vertical_distance", abs(span_y), "DSpanLevel",
    )
    station = await _carrier(
        adapter, (CAST_DATUM_ORIGIN_XZ[0], station_y), (HANGER_X, station_y)
    )
    await _relate(adapter, "datum D station line level", station, None, "horizontal")
    await _relate(
        adapter, "datum D station line on the median", f"{station}.end",
        f"{half_east}.end", "vertical_points",
    )
    await across(
        bar, "datum D station level", f"{station}.start", "origin",
        "vertical_distance", abs(station_y), "DStationLevel",
    )
    await across(
        bar, "datum D station from G", f"{station}.start", f"{station}.end",
        "horizontal_distance", D_STATION, "DStation",
    )
    await ensure_fully_defined(adapter, "crossbar sketch")
    check("exit_sketch crossbar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    v_bar = _crossbar_add_volume()
    # The full-height extrude depth is the finished top-to-underside grip at
    # the hanger holes; RingHeight drives it with the ring.
    await drafted(
        "BarProfile",
        "Crossbar",
        "crossbar",
        depth=RING_HEIGHT,
        depth_name="HangerGrip",
        start=-HALF_H,
        up=True,
        narrowing=False,
        change=v_bar,
        tol=0.001 * v_bar,
    )
    drive_jobs.append(("HangerGrip@Crossbar", '"RingHeight"'))

    # 5. Crossbar T-section: two pockets either side of the WEB_T web, cut
    #    up from the underside to the flange and drafted in, over |z| <= 69
    #    (6 short of the gusset legs, clear of the knife-mount seats).  Each
    #    overruns its bar side by BAR_POCKET_OVERRUN so the leaning side stays
    #    inside it.  The web is the gap between the pockets, and they stand
    #    off the front socket axis on a construction line down the knife
    #    line.  Sketch z flipped: (x, y) -> (X, -Z).
    y_front, y_rear = BAR_POCKET_Z, -BAR_POCKET_Z
    pocket_east = [
        (BAR_X0 - BAR_POCKET_OVERRUN, y_rear),
        (BAR_WEB_X0, y_rear),
        (BAR_WEB_X0, y_front),
        (BAR_X0 - BAR_POCKET_OVERRUN, y_front),
    ]
    pocket_west = [
        (BAR_WEB_X1, y_rear),
        (BAR_X1 + BAR_POCKET_OVERRUN, y_rear),
        (BAR_X1 + BAR_POCKET_OVERRUN, y_front),
        (BAR_WEB_X1, y_front),
    ]
    bar_pockets = SketchDims()
    check("create_sketch crossbar pockets", await adapter.create_sketch("Top"))
    east = await _plain_rectangle(adapter, pocket_east, "crossbar pocket east")
    west = await _plain_rectangle(adapter, pocket_west, "crossbar pocket west")
    await across(
        bar_pockets,
        "east pocket run",
        f"{east[0]}.start",
        f"{east[0]}.end",
        "horizontal_distance",
        BAR_WEB_X0 - BAR_X0 + BAR_POCKET_OVERRUN,
        "BP0Run",
    )
    await across(
        bar_pockets,
        "pocket length",
        f"{east[1]}.start",
        f"{east[1]}.end",
        "vertical_distance",
        2.0 * BAR_POCKET_Z,
        "PocketLength",
    )
    await across(
        bar_pockets,
        "east web face",
        f"{east[1]}.start",
        "origin",
        "horizontal_distance",
        abs(BAR_WEB_X0),
        "BP0WebX",
    )
    socket_line = await _carrier(
        adapter, (HANGER_X, y_front), (HANGER_X, abs(FRONT_COLUMN_Z))
    )
    await _relate(adapter, "pocket station line plumb", socket_line, None, "vertical")
    await _relate(
        adapter,
        "pocket station line on the pockets' front end",
        f"{socket_line}.start",
        f"{east[2]}.start",
        "horizontal_points",
    )
    await across(
        bar_pockets,
        "pocket station",
        f"{socket_line}.start",
        "origin",
        "horizontal_distance",
        abs(HANGER_X),
        "PocketStationX",
    )
    await across(
        bar_pockets,
        "front socket axis",
        f"{socket_line}.end",
        "origin",
        "vertical_distance",
        abs(FRONT_COLUMN_Z),
        "PocketSocketZ",
        '"ColumnZ"',
    )
    await across(
        bar_pockets,
        "pocket from front socket",
        f"{socket_line}.start",
        f"{socket_line}.end",
        "vertical_distance",
        abs(FRONT_COLUMN_Z) - BAR_POCKET_Z,
        "PocketFromSocket",
    )
    await across(
        bar_pockets,
        "crossbar web",
        f"{east[1]}.start",
        f"{west[0]}.start",
        "horizontal_distance",
        WEB_T,
        "CrossbarWebT",
        '"WebT"',
    )
    await across(
        bar_pockets,
        "west pocket run",
        f"{west[0]}.start",
        f"{west[0]}.end",
        "horizontal_distance",
        BAR_X1 + BAR_POCKET_OVERRUN - BAR_WEB_X1,
        "BP1Run",
    )
    await _relate(
        adapter,
        "pockets' rear ends level",
        f"{west[0]}.start",
        f"{east[1]}.start",
        "horizontal_points",
    )
    await _relate(
        adapter,
        "pockets' front ends level",
        f"{west[2]}.start",
        f"{east[2]}.start",
        "horizontal_points",
    )
    await ensure_fully_defined(adapter, "crossbar pockets sketch")
    check("exit_sketch crossbar pockets", await adapter.exit_sketch())
    name_last_feature(adapter, "BarPocketProfile")
    drive_jobs += bar_pockets.apply(adapter, "BarPocketProfile")
    await drafted(
        "BarPocketProfile",
        "BarPockets",
        "crossbar pockets",
        cut=True,
        depth=POCKET_H,
        depth_name="PocketDepth",
        start=-HALF_H,
        up=True,
        narrowing=True,
        change=-_bar_pocket_removal(),  # 47278
        tol=50.0,
    )

    # 5c. Flange corner crops: one triangle per plan corner, cut through the
    #     band before the bosses (CORNER_CROP_TRIANGLE), so the boss union
    #     leaves no flange nib outside any barrel.  Each chord lies inside
    #     its barrel, so the cut's plumb walls are buried.  Sketch z flipped:
    #     (x, y) -> (X, -Z).
    crops = SketchDims()
    check("create_sketch corner crops", await adapter.create_sketch("Top"))
    for k, (sx, sz) in enumerate(((1.0, 1.0), (1.0, -1.0), (-1.0, -1.0), (-1.0, 1.0))):
        crop_pts = [
            (sx * (COLUMN_X + px), -sz * (abs(FRONT_COLUMN_Z) + pz))
            for px, pz in CORNER_CROP_TRIANGLE
        ]
        crop_lines = await add_line_chain(adapter, crop_pts)
        await define_polygon_chain(
            adapter,
            crop_lines,
            crop_pts,
            anchor=0,
            label=f"corner crop {k}",
            dims=crops,
            names=[
                f"CC{k}X",
                f"CC{k}Z",
                f"CC{k}Leg",
                f"CC{k}ChordRun",
                f"CC{k}ChordRise",
            ],
        )
    await ensure_fully_defined(adapter, "corner crops sketch")
    check("exit_sketch corner crops", await adapter.exit_sketch())
    name_last_feature(adapter, "CornerCropProfile")
    drive_jobs += crops.apply(adapter, "CornerCropProfile")
    check(
        "cut corner crops",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CornerCrop")
    v_crops = _corner_crop_removal()  # 666.5
    volume = await volume_check(adapter, "flange corner crops", volume - v_crops, 1.0)

    # 6. Corner bosses: one circle set drafted in UP from the faced top to
    #    the boss top, a second identical set drafted in DOWN from it to the
    #    boss bottom, so Ø1.77 stands on the faced top plane and both barrels
    #    narrow away from it.
    v_boss_up, v_boss_down = _boss_add_volumes()
    r_boss = BOSS_DIA / 2.0
    for updown, depth, depth_name, feat, v_one in (
        ("up", BOSS_ABOVE, "BossAbove", "BossesUpper", v_boss_up),
        ("down", RING_HEIGHT + BOSS_BELOW, "BossBelowTop", "BossesLower", v_boss_down),
    ):
        bosses = SketchDims()
        check(f"create_sketch bosses {updown}", await adapter.create_sketch("Top"))
        n = 0
        for sx in (-1.0, 1.0):
            for z_world in (FRONT_COLUMN_Z, REAR_COLUMN_Z):
                await define_circle(
                    adapter,
                    sx * COLUMN_X,
                    -z_world,
                    r_boss,
                    f"boss {updown} ({sx:+.0f}, z={z_world:+.0f})",
                    dims=bosses,
                    names=(f"C{n}X", f"C{n}Z", f"C{n}Dia"),
                    drives=('"ColumnX"', '"ColumnZ"', '"BossDia"'),
                )
                n += 1
        await ensure_fully_defined(adapter, f"bosses {updown} sketch")
        check(f"exit_sketch bosses {updown}", await adapter.exit_sketch())
        profile = f"Boss{updown.capitalize()}Profile"
        name_last_feature(adapter, profile)
        drive_jobs += bosses.apply(adapter, profile)
        v_add = 4.0 * v_one
        await drafted(
            profile,
            feat,
            f"bosses {updown}",
            depth=depth,
            depth_name=depth_name,
            start=HALF_H,
            up=updown == "up",
            narrowing=True,
            change=v_add,
            tol=0.002 * v_add + 20.0,
        )
        drive_jobs.append((f"{depth_name}@{feat}", f'"{depth_name}"'))
    _assert_station(
        adapter, "boss tops", (0.0, 1.0, 0.0), {1: HALF_H + BOSS_ABOVE}
    )
    _assert_station(
        adapter, "boss bottoms", (0.0, -1.0, 0.0), {1: -(HALF_H + BOSS_BELOW)}
    )

    # 7. Gooseneck hub, below the underside.  First the twin V-gussets: one
    #    plate across the hub drafted out from its bottom flat up to the
    #    underside, so its two faces lean; then the two ramps cut plumb
    #    through it along X, feathering it from the full drop at
    #    |z-3.088| <= 8 to the underside at |z-3.088| = 30 ...
    half_t = HUB_GUSSET_T / 2.0
    plate_pts = [
        (GOOSENECK_X - half_t, -(GOOSENECK_Z + HUB_GUSSET_PLATE_HALF)),
        (GOOSENECK_X + half_t, -(GOOSENECK_Z + HUB_GUSSET_PLATE_HALF)),
        (GOOSENECK_X + half_t, -(GOOSENECK_Z - HUB_GUSSET_PLATE_HALF)),
        (GOOSENECK_X - half_t, -(GOOSENECK_Z - HUB_GUSSET_PLATE_HALF)),
    ]
    plate = SketchDims()
    check("create_sketch hub gusset plate", await adapter.create_sketch("Top"))
    plate_lines = await add_line_chain(adapter, plate_pts)
    await define_rectilinear_chain(
        adapter,
        plate_lines,
        plate_pts,
        label="hub gusset plate",
        dims=plate,
        names=["GussetT", "GusPlateSpan", "GusPlateX", "GusPlateZ"],
    )
    await ensure_fully_defined(adapter, "hub gusset plate sketch")
    check("exit_sketch hub gusset plate", await adapter.exit_sketch())
    name_last_feature(adapter, "HubGussetPlateProfile")
    plate.apply(adapter, "HubGussetPlateProfile")
    v_plate, v_ramps = _hub_gusset_volumes()
    await drafted(
        "HubGussetPlateProfile",
        "HubGussetPlate",
        "hub gusset plate",
        depth=HUB_BOSS_DROP,
        depth_name="GusDrop",
        start=HUB_GUSSET_BOTTOM_Y,
        up=True,
        narrowing=False,
        change=v_plate,
        tol=20.0,
    )
    _assert_station(
        adapter, "hub gusset bottom flat", (0.0, -1.0, 0.0), {1: HUB_GUSSET_BOTTOM_Y}
    )
    # The ramp cuts' sketch stands on a Right-plane offset just east of the
    # plate: a negative offset, so sketch x = -(model Z) (negative-offset
    # plane mirror -- see the module docstring) and the reversed cut runs
    # toward +X through the plate.  Each polygon starts on its ramp's feather
    # point on the underside, runs down the ramp past the bottom flat, out
    # past the plate's end and back up to the underside.
    ramp_reach = half_t + HUB_BOSS_DROP * DRAFT_T + 1.0
    gusset_plane = check(
        "create_plane hub gusset ramps",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Right Plane",
                offset=GOOSENECK_X - ramp_reach,
            )
        ),
    )
    gusset_plane_name = str(getattr(gusset_plane, "name", gusset_plane))
    ref_planes.append(gusset_plane_name)
    ramp_slope = (HUB_GUSSET_HALF_OUT - HUB_GUSSET_HALF_IN) / HUB_BOSS_DROP
    ramp_below = 1.0
    ramp_far = HUB_GUSSET_PLATE_HALF + HUB_BOSS_DROP * DRAFT_T + 1.0

    def ramp_polygon(side: float) -> list[tuple[float, float]]:
        return [
            (-(GOOSENECK_Z + side * HUB_GUSSET_HALF_OUT), -HALF_H),
            (
                -(GOOSENECK_Z + side * (HUB_GUSSET_HALF_IN - ramp_below * ramp_slope)),
                HUB_GUSSET_BOTTOM_Y - ramp_below,
            ),
            (-(GOOSENECK_Z + side * ramp_far), HUB_GUSSET_BOTTOM_Y - ramp_below),
            (-(GOOSENECK_Z + side * ramp_far), -HALF_H),
        ]

    gus = SketchDims()
    check("create_sketch hub gusset ramps", await adapter.create_sketch(gusset_plane_name))
    rear_pts = ramp_polygon(1.0)
    rear_ramp = await add_line_chain(adapter, rear_pts)
    await define_polygon_chain(
        adapter,
        rear_ramp,
        rear_pts,
        anchor=0,
        label="hub gusset rear ramp",
        dims=gus,
        names=[
            "GusFeatherZ",
            "GusFeatherY",
            "GusRampRun",
            "GusRampRise",
            "GusCutRun",
            "GusCutRise",
        ],
    )
    front_pts = ramp_polygon(-1.0)
    front_ramp = await add_line_chain(adapter, front_pts)
    await _relate(
        adapter,
        "hub gusset feather points level",
        f"{front_ramp[0]}.start",
        f"{rear_ramp[0]}.start",
        "horizontal_points",
    )
    await across(
        gus,
        "hub gusset feather span",
        f"{rear_ramp[0]}.start",
        f"{front_ramp[0]}.start",
        "horizontal_distance",
        2.0 * HUB_GUSSET_HALF_OUT,
        "GussetSpan",
    )
    for line, (x1, y1), (x2, y2), names in zip(
        front_ramp[:3],
        front_pts[:3],
        front_pts[1:],
        (("GusRampRunF", "GusRampRiseF"), ("GusCutRunF",), ("GusCutRiseF",)),
        strict=True,
    ):
        await anchor_point_to_point(
            adapter,
            f"{line}.start",
            f"{line}.end",
            x2 - x1,
            y2 - y1,
            f"hub gusset front ramp {line}",
        )
        for name in names:
            gus.record(name)
    await ensure_fully_defined(adapter, "hub gusset ramps sketch")
    check("exit_sketch hub gusset ramps", await adapter.exit_sketch())
    name_last_feature(adapter, "HubGussetProfile")
    gus.apply(adapter, "HubGussetProfile")
    check(
        "cut hub gusset ramps",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * ramp_reach, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "HubGussetRamps")
    volume = await volume_check(adapter, "hub gusset ramps", volume - v_ramps, 15.0)

    #    ... then the underside boss through them, drafted in DOWN from the
    #    underside, where its Ø1.18 stands.
    hub = SketchDims()
    check("create_sketch hub boss", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        GOOSENECK_X,
        -GOOSENECK_Z,
        HUB_BOSS_DIA / 2.0,
        "hub boss",
        dims=hub,
        names=("HubX", "HubZ", "HubDia"),
        drives=('"ColumnX"', '"GooseneckZ"', '"HubBossDia"'),
    )
    await ensure_fully_defined(adapter, "hub boss sketch")
    check("exit_sketch hub boss", await adapter.exit_sketch())
    name_last_feature(adapter, "HubBossProfile")
    drive_jobs += hub.apply(adapter, "HubBossProfile")
    await drafted(
        "HubBossProfile",
        "HubBoss",
        "hub boss",
        depth=HUB_BOSS_DROP,
        depth_name="HubBossDrop",
        start=-HALF_H,
        up=False,
        narrowing=True,
        change=_hub_boss_add_volume(),
        tol=30.0,
    )
    drive_jobs.append(("HubBossDrop@HubBoss", '"HubBossDrop"'))

    # 8. Set-screw boss on the hub rib (east outer face, -X): the full rail
    #    height, flush with the faced top (owner ruling B4), drafted out from
    #    the underside so its side walls widen up (B1).  Its cast face stands
    #    HUB_SET_BOSS_FROM_AXIS off the bore axis on the faced top (owner
    #    ruling D1): that distance is a construction line from the axis, and
    #    the face starts SetBossFaceDraftRun short of its end on the
    #    underside.  Sketch z flipped: (x, y) -> (X, -Z).
    half_w = HUB_SET_BOSS_W / 2.0
    sb_pts = [
        (SET_BOSS_FACE_X0, -(GOOSENECK_Z - half_w)),
        (SET_BOSS_INNER_X0, -(GOOSENECK_Z - half_w)),
        (SET_BOSS_INNER_X0, -(GOOSENECK_Z + half_w)),
        (SET_BOSS_FACE_X0, -(GOOSENECK_Z + half_w)),
    ]
    set_boss = SketchDims()
    check("create_sketch set boss", await adapter.create_sketch("Top"))
    sb_lines = await _plain_rectangle(adapter, sb_pts, "set boss")
    face_line = await _carrier(
        adapter, (GOOSENECK_X, -GOOSENECK_Z), (SET_BOSS_FACE_X, -GOOSENECK_Z)
    )
    await _relate(adapter, "set boss face line level", face_line, None, "horizontal")
    for label, first, second, kind, value, name, drive in (
        ("hub axis x", f"{face_line}.start", "origin", "horizontal_distance",
         COLUMN_X, "SetBossAxisX", '"ColumnX"'),
        ("hub axis z", f"{face_line}.start", "origin", "vertical_distance",
         abs(GOOSENECK_Z), "SetBossAxisZ", '"GooseneckZ"'),
        ("set boss face from the bore axis", f"{face_line}.start", f"{face_line}.end",
         "horizontal_distance", HUB_SET_BOSS_FROM_AXIS, "SetBossFace", None),
        ("set boss face draft run", f"{face_line}.end", f"{sb_lines[0]}.start",
         "horizontal_distance", RIM_RECEDE, "SetBossFaceDraftRun", None),
        ("set boss run", f"{sb_lines[0]}.start", f"{sb_lines[0]}.end",
         "horizontal_distance", SET_BOSS_INNER_X0 - SET_BOSS_FACE_X0, "SetBossRun", None),
        ("set boss width", f"{sb_lines[3]}.start", f"{sb_lines[3]}.end",
         "vertical_distance", HUB_SET_BOSS_W, "SetBossWidth", None),
        ("set boss half width", f"{face_line}.start", f"{sb_lines[0]}.start",
         "vertical_distance", half_w, "SetBossHalfWidth", None),
    ):
        await across(set_boss, label, first, second, kind, value, name, drive)
    await ensure_fully_defined(adapter, "set boss sketch")
    check("exit_sketch set boss", await adapter.exit_sketch())
    name_last_feature(adapter, "SetBossProfile")
    drive_jobs += set_boss.apply(adapter, "SetBossProfile")
    await drafted(
        "SetBossProfile",
        "SetBoss",
        "set boss",
        depth=RING_HEIGHT,
        depth_name="SetBossHeight",
        start=-HALF_H,
        up=True,
        narrowing=False,
        change=_set_boss_add_volume(),
        tol=20.0,
    )
    _assert_station(
        adapter,
        "set boss face nominal on the top",
        (-1.0, 0.0, 0.0),
        {0: SET_BOSS_FACE_X, 1: HALF_H},
    )
    # The spot face, from a Right-plane offset at the cast face's top station
    # (negative offset: sketch x = -(model Z), the reversed cut runs toward
    # +X), in to its floor.
    boss_plane = check(
        "create_plane set spot face",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=SET_BOSS_FACE_X
            )
        ),
    )
    boss_plane_name = getattr(boss_plane, "name", boss_plane)
    ref_planes.append(str(boss_plane_name))
    spot = SketchDims()
    check("create_sketch set spot face", await adapter.create_sketch(boss_plane_name))
    await define_circle(
        adapter,
        -GOOSENECK_Z,
        SCREW_AXIS_Y,
        HUB_SET_SPOT_DIA / 2.0,
        "set-screw spot face",
        dims=spot,
        names=("SetSpotZ", "SetSpotY", "SetSpotDia"),
    )
    await ensure_fully_defined(adapter, "set spot face sketch")
    check("exit_sketch set spot face", await adapter.exit_sketch())
    name_last_feature(adapter, "SetSpotProfile")
    spot.apply(adapter, "SetSpotProfile")
    check(
        "cut set spot face",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=SET_SPOT_FACE_X - SET_BOSS_FACE_X, reverse_direction=True
            )
        ),
    )
    name_last_feature(adapter, "SetSpotFace")
    volume = await volume_check(
        adapter, "set spot face", volume - _set_spot_removal(), 5.0
    )

    # 9. Side-screw counterbores: O9 x 6.55 from the 134.9 cut plane to the
    #    |z|=128.35 floor (6.15 below the boss crown), deep enough that the
    #    stock fillister head sits below the mouth on the curved boss.
    v_cbore = _counterbore_removal()
    for side, sign, reverse in SIDE_SCREW_FACES:
        cb_plane = check(
            f"create_plane counterbore {side}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset",
                    base_plane="Front Plane",
                    offset=sign * COUNTERBORE_PLANE,
                )
            ),
        )
        cbore = SketchDims()
        check(
            f"create_sketch counterbore {side}",
            await adapter.create_sketch(getattr(cb_plane, "name", cb_plane)),
        )
        ref_planes.append(str(getattr(cb_plane, "name", cb_plane)))
        for k, x in enumerate(SIDE_SCREW_XS):
            await define_circle(
                adapter,
                x,
                SCREW_AXIS_Y,
                COUNTERBORE_DIA / 2.0,
                f"counterbore {side} (x={x:+.0f})",
                dims=cbore,
                names=(f"CB{k}X", f"CB{k}Y", f"CB{k}Dia"),
            )
        await ensure_fully_defined(adapter, f"counterbore {side} sketch")
        check(f"exit_sketch counterbore {side}", await adapter.exit_sketch())
        name_last_feature(adapter, f"Counterbore{side.capitalize()}Profile")
        cbore.apply(adapter, f"Counterbore{side.capitalize()}Profile")
        check(
            f"cut counterbore {side}",
            await adapter.create_cut_extrude(
                ExtrusionParameters(
                    depth=COUNTERBORE_PLANE - COUNTERBORE_FLOOR,
                    reverse_direction=reverse,
                )
            ),
        )
        name_last_feature(adapter, f"Counterbore{side.capitalize()}")
        volume = await volume_check(
            adapter,
            f"counterbore {side}",
            volume - len(SIDE_SCREW_XS) * v_cbore,
            0.2 * v_cbore + 15.0,
        )

    # 10. Column bores (through the boss stacks).
    bores = SketchDims()
    check("create_sketch bores", await adapter.create_sketch("Top"))
    n = 0
    for sx in (-1.0, 1.0):
        for z_world in (FRONT_COLUMN_Z, REAR_COLUMN_Z):
            await define_circle(
                adapter,
                sx * COLUMN_X,
                -z_world,
                BORE_DIA / 2.0,
                f"bore ({sx:+.0f}, z={z_world:+.0f})",
                dims=bores,
                names=(f"B{n}X", f"B{n}Z", f"B{n}Dia"),
                drives=('"ColumnX"', '"ColumnZ"', '"BoreDia"'),
            )
            n += 1
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bores.apply(adapter, "BoreProfile")
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ColumnBores")
    boss_h = RING_HEIGHT + BOSS_ABOVE + BOSS_BELOW
    v_bores = 4.0 * math.pi * (BORE_DIA / 2.0) ** 2 * boss_h
    volume = await volume_check(adapter, "column bores", volume - v_bores, 100.0)

    # Four recessed seats hide the purchased cap skirts while leaving the
    # cross-screw station intact below. The positive-offset Top plane's default
    # cut direction is toward the casting, opposite its +Y sketch normal.
    recess_plane = check(
        "create_plane cap recess mouths",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=HALF_H + BOSS_ABOVE,
            )
        ),
    )
    recess_plane_name = str(getattr(recess_plane, "name", recess_plane))
    ref_planes.append(recess_plane_name)
    recesses = SketchDims()
    check("create_sketch cap recesses", await adapter.create_sketch(recess_plane_name))
    n = 0
    for sx in (-1.0, 1.0):
        for z_world in (FRONT_COLUMN_Z, REAR_COLUMN_Z):
            await define_circle(
                adapter,
                sx * COLUMN_X,
                -z_world,
                CAP_RECESS_DIAMETER / 2.0,
                f"cap recess ({sx:+.0f}, z={z_world:+.0f})",
                dims=recesses,
                names=(
                    f"CR{n}X",
                    f"CR{n}Z",
                    "CapRecessDia" if n == 0 else f"CapRecess{n}Dia",
                ),
                drives=('"ColumnX"', '"ColumnZ"', '"CapRecessDia"'),
            )
            n += 1
    await ensure_fully_defined(adapter, "cap recess sketch")
    check("exit_sketch cap recesses", await adapter.exit_sketch())
    name_last_feature(adapter, "CapRecessProfile")
    drive_jobs += recesses.apply(adapter, "CapRecessProfile")
    check(
        "cut cap recesses",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=CAP_RECESS_DEPTH,
                reverse_direction=False,
            )
        ),
    )
    name_last_feature(adapter, "CapRecesses")
    recess_depth_dim = name_dimensions(adapter, "CapRecesses", ["CapRecessDepth"])
    drive_jobs.append((recess_depth_dim[0], '"CapRecessDepth"'))
    v_recess = (
        4.0
        * math.pi
        * ((CAP_RECESS_DIAMETER / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2)
        * CAP_RECESS_DEPTH
    )
    volume = await volume_check(
        adapter, "cap recesses", volume - v_recess, 0.005 * v_recess + 5.0
    )

    # 11. Gooseneck clearance bore (through the rib + hub boss).
    gneck = SketchDims()
    check("create_sketch gooseneck bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        GOOSENECK_X,
        -GOOSENECK_Z,
        GOOSENECK_BORE_DIA / 2.0,
        "gooseneck bore",
        dims=gneck,
        names=("GnX", "GnZ", "GnDia"),
        drives=('"ColumnX"', '"GooseneckZ"', '"GooseneckBoreDia"'),
    )
    await ensure_fully_defined(adapter, "gooseneck bore sketch")
    check("exit_sketch gooseneck bore", await adapter.exit_sketch())
    name_last_feature(adapter, "GooseneckProfile")
    drive_jobs += gneck.apply(adapter, "GooseneckProfile")
    check(
        "cut gooseneck bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "GooseneckBore")
    v_gn = math.pi * (GOOSENECK_BORE_DIA / 2.0) ** 2 * (RING_HEIGHT + HUB_BOSS_DROP)
    volume = await volume_check(adapter, "gooseneck bore", volume - v_gn, 60.0)

    # 12. Native #10 plain clearance holes pinned to the C drill, both stations in one
    #     underside-entry wizard feature (the shop drills them from the
    #     underside, so drift grows toward the faced top; HANGER_HOLE_SPEC).
    #     The washers bear on the faced top plane round each hole.
    wizard_holes(
        adapter,
        HANGER_HOLE_SPEC,
        [[HANGER_X, -HALF_H, STUD_Z_FRONT], [HANGER_X, -HALF_H, STUD_Z_REAR]],
        (0.0, -1.0, 0.0),
        "knife-hanger clearance holes",
        name="StudHoles",
        expect_dia_mm=HANGER_CLEARANCE_DIA,
        placement_dims=[
            (("StudFrontX", None), ("StudFrontZ", None)),
            (("StudRearX", None), ("StudRearZ", None)),
        ],
    )
    v_hangers = 2.0 * math.pi * (HANGER_CLEARANCE_DIA / 2.0) ** 2 * RING_HEIGHT
    volume = await volume_check(
        adapter, "knife-hanger clearance holes", volume - v_hangers, 10.0
    )

    # 12b. Dowel press reams (owner ruling 2026-10-24, T+H3): blind and
    #      flat-floored (a plain cut-extrude -- a wizard drill point would
    #      leave a cone under the pressed dowel's end), cut HangerPinHoleDepth
    #      up from the crossbar underside, HANGER_PIN_X +X of each screw axis
    #      (Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: one per
    #      station): two circles, one sketch.  The rear circle owns the
    #      marked HangerPinHoleDia, which the underside locator dimensions.
    pins = SketchDims()
    pin_stations = [
        (station, PIN_HOLE_X, z)
        for station, z in (("Front", STUD_Z_FRONT), ("Rear", STUD_Z_REAR))
    ]
    pin_dia_names = {"Rear": "HangerPinHoleDia", "Front": "HangerPinHole1Dia"}
    sketch_centres, u_is_x, normal_out = _open_underside_sketch(
        adapter, [(x, -HALF_H, z) for _station, x, z in pin_stations]
    )
    for (u, v), (station, _x, _z) in zip(sketch_centres, pin_stations, strict=True):
        x_name, z_name = f"Pin{station}X", f"Pin{station}Z"
        await define_circle(
            adapter,
            u,
            v,
            HANGER_PIN_HOLE_DIA / 2.0,
            f"dowel ream ({station.lower()})",
            dims=pins,
            names=(
                (x_name, z_name, pin_dia_names[station])
                if u_is_x
                else (z_name, x_name, pin_dia_names[station])
            ),
            drives=(None, None, '"HangerPinHoleDia"'),
        )
    await ensure_fully_defined(adapter, "dowel ream sketch")
    check("exit_sketch dowel reams", await adapter.exit_sketch())
    name_last_feature(adapter, "HangerPinProfile")
    drive_jobs += pins.apply(adapter, "HangerPinProfile")
    # A cut runs opposite the sketch normal unless reversed.
    check(
        "cut dowel reams",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=HANGER_PIN_HOLE_DEPTH, reverse_direction=not normal_out
            )
        ),
    )
    name_last_feature(adapter, "HangerPinHoles")
    drive_jobs.append(
        (
            name_dimensions(adapter, "HangerPinHoles", ["HangerPinHoleDepth"])[0],
            '"HangerPinHoleDepth"',
        )
    )
    # A cut the wrong way leaves the solid untouched and fails here.
    v_pins = (
        len(HANGER_PIN_CONTOURS)
        * math.pi
        * (HANGER_PIN_HOLE_DIA / 2.0) ** 2
        * HANGER_PIN_HOLE_DEPTH
    )
    volume = await volume_check(adapter, "dowel reams", volume - v_pins, 0.01 * v_pins)

    # 12c. The reams' knockouts (fr_top_frame_spec.HANGER_KNOCKOUT_SPEC): ONE
    #      native #51 Hole Wizard feature through-all on each ream's axis
    #      (the dt_crankshaft DrivePinKnockouts precedent).  The shop drills
    #      it up from the ream's floor on the ream's drawn axis (the print's
    #      callout; its coaxiality, the title block's implied ±.005, is what
    #      the floor land (.0124, RV-06) and the walls above charge); the
    #      model places it on the faced top, where the wizard has a whole
    #      face, and cuts the same cylinder: below the ream's floor it runs
    #      in the ream's own air, so it removes only the crossbar between
    #      the floor and the top.
    wizard_holes(
        adapter,
        HANGER_KNOCKOUT_SPEC,
        [[x, HALF_H, z] for _station, x, z in pin_stations],
        (0.0, 1.0, 0.0),
        "dowel ream knockouts (#51 drill)",
        name="HangerKnockouts",
        expect_dia_mm=HANGER_KNOCKOUT_DIA,
        placement_dims=[
            ((f"Knockout{station}X", None), (f"Knockout{station}Z", None))
            for station, _x, _z in pin_stations
        ],
    )
    v_knockouts = (
        len(pin_stations)
        * math.pi
        * (HANGER_KNOCKOUT_DIA / 2.0) ** 2
        * HANGER_KNOCKOUT_LENGTH
    )
    volume = await volume_check(
        adapter, "dowel ream knockouts", volume - v_knockouts, 0.02 * v_knockouts
    )

    # 13. Cross-screw taps (#10-32 UNF-2B bottoming): one per boss,
    #     46.0 mm full thread in a 49.2 mm cylindrical drill. Each path
    #     starts on its counterbore floor, crosses the near casting wall and column
    #     bore, then continues into the far boss/centred side-rail web.
    #     Opposed holes remain one two-position Hole Wizard feature per side.
    #     The #10 close clearance is then cut from the same floor, so only
    #     the far wall keeps thread (owner ruling 2026-11-05).
    v_side_tap = _side_tap_removal()
    v_side_clear = near_wall_hole_volume_mm3(
        NEAR_WALL_CLEARANCE_DIAMETER, SIDE_CLEARANCE_DEPTH
    ) - near_wall_hole_volume_mm3(SIDE_TAP_DRILL_DIA, SIDE_CLEARANCE_DEPTH)
    for side, sign, _reverse in SIDE_SCREW_FACES:
        feat = f"SideTaps{side.capitalize()}"
        z_face = sign * COUNTERBORE_FLOOR
        normal = (0.0, 0.0, sign)
        tap_points = [[x, SCREW_AXIS_Y, z_face] for x in SIDE_SCREW_XS]
        wizard_holes(
            adapter,
            SIDE_TAP_SPEC,
            tap_points,
            normal,
            f"frame cross-screw taps {feat}",
            name=feat,
            expect_dia_mm=SIDE_TAP_DRILL_DIA,
        )
        volume = await volume_check(
            adapter,
            f"side taps {feat}",
            volume - len(tap_points) * v_side_tap,
            0.1 * v_side_tap + 15.0,
        )
        clearance = f"SideClearance{side.capitalize()}"
        wizard_holes(
            adapter,
            SIDE_CLEARANCE_SPEC,
            tap_points,
            normal,
            f"frame cross-screw near-wall clearance {clearance}",
            name=clearance,
            expect_dia_mm=NEAR_WALL_CLEARANCE_DIAMETER,
        )
        volume = await volume_check(
            adapter,
            f"side near-wall clearance {clearance}",
            volume - len(tap_points) * v_side_clear,
            0.05 * v_side_clear + 2.0,
        )

    v_set_tap = _set_tap_removal()
    wizard_holes(
        adapter,
        SET_TAP_SPEC,
        [[SET_SPOT_FACE_X, SCREW_AXIS_Y, GOOSENECK_Z]],
        (-1.0, 0.0, 0.0),
        "gooseneck set-screw tap",
        name="GooseneckTap",
        placement_dims=[(("SetTapZ", None), ("SetTapY", None))],
    )
    volume = await volume_check(
        adapter, "gooseneck set tap", volume - v_set_tap, 0.1 * v_set_tap + 10.0
    )

    # 15. Fulcrum-keeper taps from the shared keeper spec into the west rail TOP
    wizard_holes(
        adapter,
        KEEPER_TAP_SPEC,
        [
            [KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_FRONT],
            [KEEPER_TAP_X, HALF_H, KEEPER_TAP_Z_REAR],
        ],
        (0.0, 1.0, 0.0),
        "fulcrum keeper taps",
        name="KeeperTaps",
        placement_dims=[
            (("KeeperFrontX", None), ("KeeperFrontZ", None)),
            (("KeeperRearX", None), ("KeeperRearZ", None)),
        ],
    )
    v_keeper = 2.0 * blind_hole_volume_mm3(
        TAP_DRILL_MM[KEEPER_TAP_SPEC.size], KEEPER_TAP_SPEC.depth_mm
    )
    volume = await volume_check(adapter, "keeper taps", volume - v_keeper, 10.0)

    # 16. Internal T-root fillets: R3 along the reentrant junction where
    #     each recessed web face meets the flange underside (y +10.12) --
    #     the cast root blend ch19 img04 shows on every panel. One edge
    #     per uninterrupted run: the hub rib splits both east-rail runs,
    #     the junction lands split both front/rear window runs; the crossbar
    #     web's two roots run between its pocket ends.  Every added face
    #     stands root_lean out of its underside station there.
    root_lean = POCKET_H * DRAFT_T  # 0.991
    x_shelf_out = WEB_OUT_X + root_lean
    x_shelf_in = WEB_IN_X - root_lean
    z_shelf_out = WEB_OUT_Z + root_lean
    z_shelf_in = WEB_IN_Z - root_lean
    rib_lo = GOOSENECK_Z - HUB_RIB_W / 2.0 - root_lean
    rib_hi = GOOSENECK_Z + HUB_RIB_W / 2.0 + root_lean
    root_cut = math.sqrt(
        _boss_radius(FLANGE_BOT_Y) ** 2 - (WEB_T / 2.0 + root_lean) ** 2
    )
    east_mid_lo = (-abs(FRONT_COLUMN_Z) + root_cut + rib_lo) / 2.0
    east_mid_hi = (rib_hi + abs(FRONT_COLUMN_Z) - root_cut) / 2.0
    land_mid_w = (LAND_X0 - root_lean - COLUMN_X + root_cut) / 2.0
    land_mid_e = (LAND_X1 + root_lean + COLUMN_X - root_cut) / 2.0
    check(
        "fillet T-roots",
        await adapter.add_fillet(
            ROOT_FILLET_R,
            [
                # outer shelf: west rail, east rail (rib-split), front, rear
                [x_shelf_out, FLANGE_BOT_Y, 0.0],
                [-x_shelf_out, FLANGE_BOT_Y, east_mid_lo],
                [-x_shelf_out, FLANGE_BOT_Y, east_mid_hi],
                [0.0, FLANGE_BOT_Y, -z_shelf_out],
                [0.0, FLANGE_BOT_Y, z_shelf_out],
                # window shelf: west rail, east rail (rib-split),
                # front/rear (land-split)
                [x_shelf_in, FLANGE_BOT_Y, 0.0],
                [-x_shelf_in, FLANGE_BOT_Y, east_mid_lo],
                [-x_shelf_in, FLANGE_BOT_Y, east_mid_hi],
                [land_mid_w, FLANGE_BOT_Y, -z_shelf_in],
                [land_mid_w, FLANGE_BOT_Y, z_shelf_in],
                [land_mid_e, FLANGE_BOT_Y, -z_shelf_in],
                [land_mid_e, FLANGE_BOT_Y, z_shelf_in],
                # crossbar web, both sides
                [BAR_WEB_X0 - root_lean, FLANGE_BOT_Y, 0.0],
                [BAR_WEB_X1 + root_lean, FLANGE_BOT_Y, 0.0],
            ],
        ),
    )
    name_last_feature(adapter, "TRootFillets")
    name_feature_dimensions(
        adapter, "TRootFillets", lengths={"RootR": ROOT_FILLET_R}, angles={}
    )
    v_root = _t_root_add()
    volume = await volume_check(
        adapter, "T-root fillets", volume + v_root, 0.03 * v_root + 80.0
    )

    # 17. External top-face rim breaks: EDGE_CHAMFER x 45 on the outer rail rim and
    #     both windows' rims. The Ø1.77 bosses no longer reach the rail plan
    #     corners: window rims meet at real square corners, and the corner
    #     crops leave each outer face one run from barrel to barrel -- the
    #     east one two runs, either side of the set-screw boss's flush top.
    #     The rims stand at their nominal on the faced top; the crossbar's
    #     sides and gussets stand RIM_RECEDE out of their underside stations.
    v_outer, v_window = _top_rim_removal()
    rim_cut = math.sqrt((BOSS_DIA / 2.0) ** 2 - (RAIL_W_SIDE / 2.0) ** 2)
    set_boss_reach = HUB_SET_BOSS_W / 2.0 + RIM_RECEDE
    east_rim_lo = (-abs(FRONT_COLUMN_Z) + rim_cut + GOOSENECK_Z - set_boss_reach) / 2.0
    east_rim_hi = (GOOSENECK_Z + set_boss_reach + abs(FRONT_COLUMN_Z) - rim_cut) / 2.0
    top_leg = _gusset_leg(RIM_RECEDE)
    top_foot = RIM_RECEDE + top_leg  # a gusset's foot off its bar side
    bar_top_e, bar_top_w = BAR_X0 - RIM_RECEDE, BAR_X1 + RIM_RECEDE
    check(
        "chamfer top rims",
        await adapter.add_chamfer(
            EDGE_CHAMFER,
            [
                [OUTER_X, HALF_H, 0.0],
                [-OUTER_X, HALF_H, east_rim_lo],
                [-OUTER_X, HALF_H, east_rim_hi],
                [0.0, HALF_H, OUTER_Z],
                [0.0, HALF_H, -OUTER_Z],
                [-INNER_X, HALF_H, 0.0],
                [INNER_X, HALF_H, 0.0],
                [bar_top_e, HALF_H, 0.0],
                [bar_top_w, HALF_H, 0.0],
                # front/rear inner-face runs, east + west of the crossbar
                [(BAR_X0 - top_foot - INNER_X) / 2.0, HALF_H, INNER_Z],
                [(BAR_X0 - top_foot - INNER_X) / 2.0, HALF_H, -INNER_Z],
                [(BAR_X1 + top_foot + INNER_X) / 2.0, HALF_H, INNER_Z],
                [(BAR_X1 + top_foot + INNER_X) / 2.0, HALF_H, -INNER_Z],
                # gusset hypotenuse midpoints
                [bar_top_e - top_leg / 2.0, HALF_H, INNER_Z - top_leg / 2.0],
                [bar_top_e - top_leg / 2.0, HALF_H, -(INNER_Z - top_leg / 2.0)],
                [bar_top_w + top_leg / 2.0, HALF_H, INNER_Z - top_leg / 2.0],
                [bar_top_w + top_leg / 2.0, HALF_H, -(INNER_Z - top_leg / 2.0)],
            ],
        ),
    )
    name_last_feature(adapter, "TopRimBreaks")
    v_rims = v_outer + v_window
    volume = await volume_check(
        adapter, "top rim breaks", volume - v_rims, 0.03 * v_rims + 100.0
    )

    # 18. .03 x 45 lead-ins on the four cap-recess mouths and gooseneck bore
    # top; bore and counterbore low ends take the title block's .010 break.
    boss_top_y = HALF_H + BOSS_ABOVE
    r_gn = GOOSENECK_BORE_DIA / 2.0
    check(
        "chamfer bore tops",
        await adapter.add_chamfer(
            BORE_CHAMFER,
            [
                [sx * COLUMN_X, boss_top_y, z_world + CAP_RECESS_DIAMETER / 2.0]
                for sx in (-1.0, 1.0)
                for z_world in (FRONT_COLUMN_Z, REAR_COLUMN_Z)
            ]
            + [[GOOSENECK_X, HALF_H, GOOSENECK_Z + r_gn]],
        ),
    )
    name_last_feature(adapter, "BoreTopBreaks")
    v_breaks = _bore_chamfer_removal()
    volume = await volume_check(
        adapter, "bore top breaks", volume - v_breaks, 0.02 * v_breaks + 10.0
    )

    # 18b. EDGE_CHAMFER x 45 on every remaining external convex edge (64 edges and 9
    #      boss rims), one chamfer feature per connected chain so a native
    #      failure names its chain and each chain's volume is proved on its
    #      own (see _external_edge_breaks for the chains and the edges left
    #      unbroken).
    #      Each pair of breaks meeting at a vertex adds half a c^3 corner
    #      patch to the tolerance; barrel-end error sits inside the 3%.
    for feature, (picks, v_chain, shared) in EXTERNAL_EDGE_BREAKS.items():
        check(f"chamfer {feature}", await adapter.add_chamfer(EDGE_CHAMFER, picks))
        name_last_feature(adapter, feature)
        volume = await volume_check(
            adapter,
            f"external edge breaks {feature}",
            volume - v_chain,
            0.03 * v_chain + 0.5 * EDGE_CHAMFER**3 * shared + 10.0,
        )

    # Deferred drive equations: after the whole model + a rebuild exist so
    # every target resolves; the re-check proves the equations are neutral.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    # Every drafted feature still reads its depth and its draft once the
    # equations drive it.  Then the model carries the bands the sheet prints:
    # owner ruling D4's on each draft angle, B2's on each as-cast dimension.
    if set(drafted_depths) != set(DRAFT_ANGLE_DIMENSIONS):
        raise AssertionError(
            "drafted features and the spec's draft-angle table differ:"
            f" {sorted(set(drafted_depths) ^ set(DRAFT_ANGLE_DIMENSIONS))}"
        )
    for feature_name, depth in drafted_depths.items():
        assert_drafted(adapter, feature_name, depth, DRAFT_DEG)
        angle_name, (upper_deg, lower_deg) = DRAFT_ANGLE_DIMENSIONS[feature_name]
        set_draft_angle_tolerance(
            adapter, feature_name, angle_name, lower_deg, upper_deg
        )
    for feature_name, dimension_names in AS_CAST_DIMENSIONS.items():
        for dimension_name in dimension_names:
            set_dimension_symmetric_tolerance(
                adapter,
                feature_name,
                dimension_name,
                AS_CAST_BAND,
                places=DRAWING_PRECISION[feature_name][dimension_name],
                display_unit=UNIT,
            )
    # The cap recess diameter carries no explicit band: the title block's
    # .XXX governs it at the places apply_drawing_precision authors.
    set_dimension_bilateral_tolerance(
        adapter,
        "CapRecesses",
        "CapRecessDepth",
        *deviations(CAP_RECESS_DEPTH_BAND),
        places=DRAWING_PRECISION["CapRecesses"]["CapRecessDepth"],
        display_unit=UNIT,
    )
    # Explicit press band on both dowel reams (the dowel spec's
    # REAM_H7 +.0005/0), printed at the nominal's four places.
    for pin_dia_name in ("HangerPinHoleDia", "HangerPinHole1Dia"):
        set_dimension_bilateral_tolerance(
            adapter,
            "HangerPinProfile",
            pin_dia_name,
            *deviations(HANGER_PIN_HOLE_DIA_BAND),
            places=HANGER_PIN_HOLE_DIA_PLACES,
            display_unit=UNIT,
        )
    volume = await volume_check(
        adapter, "driven casting (equations neutral)", volume, 200.0
    )
    _assert_flange_corners_cropped(adapter)

    # Hide the construction offset planes -- shown reference geometry renders
    # in the part PNG and every assembly instance (fix_shown_sketches idiom).
    blank_reference_geometry(adapter, tuple((name, "PLANE") for name in ref_planes))

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The decimal places travel WITH the dimension: the drawing imports each
    # marked dimension and only reads its precision back, so the part is the
    # single place a place count is authored (drawing-simplicity-policy.md `How the repository implements the guidelines`).
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _qualify_machined_faces(adapter)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Manufacturing Notes B": DRAWING_NOTES_B,
            "Manufacturing Notes C": DRAWING_NOTES_C,
        },
    )
    # The print opens on two octant pictorials (front-top-left, front-bottom-
    # right) to prime the reader before the orthographic sheets; all eight are
    # named here so any print of this part can place any of them by name.
    name_octant_views(adapter, label=PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
