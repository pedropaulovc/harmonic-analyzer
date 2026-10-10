r"""Reproduction script: top frame casting (2026-08-02 rederive; 1 used).

ONE green cast iron piece that absorbed the old separate top-crossbar
(full-height integral bar) and gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side). Derived from the ch30 eight views (px
measurement anchored on the 394 x 224 column pitch), the GT bundle solve
rescaled onto the model column grid, and ch19 close-ups (webbing, hub, screw):

* Rail band y 999.7..1036.2 (H 36.5; the old 41-tall band top 1040.7 was
  the BOSS top -- the rail top face is 4.5 lower). Assembly inserts the
  part at ring mid-plane TOP_FRAME_MID_Y = 1017.95.
* Side rails (along Z at x +/-197) 34.2 wide -> outer faces x +/-214.1,
  window x +/-179.9. Front/rear rails (along X at z -/+112) 38.0 wide ->
  outer faces z -/+131, window z -/+93.
* Corner bosses O45 spanning y 993.4..1040.7 (proud 4.5 above the rail
  top, hanging 6.3 below the underside). All four upper/lower bosses use
  the smaller user-ruled diameter so the outward keeper feet sit flat.
  The O25.5 column bores and O27.5 cap recesses stay unchanged. Four
  stock 1-3/4 in cross screws enter the front/rear spot seats and clear
  both tube walls into the far casting wall/web through #10-32 taps.
* Two bounded keeper-seat regions on the side-rail TOP FLANGE are faced
  together in one setup, within the keeper-owned common 0.04 flatness zone.
  Each covers the actual 14 x 16.5 complete contact plus 0.10 at each edge;
  split-line footprints are nominal 14.2 x 16.7 references. The finished
  local flange below both seats is controlled at 8.0 (.X, minimum 7.2),
  with Ra 3.2 locating-seat finish; the nominal rail-top plane stays fixed.
* Integral crossbar 22 wide at x -26..-4 spanning the window along Z,
  flush with BOTH faces (its underside 999.7 is the knife-mount seat
  plane), with 18 x 18 plan gussets at all four rail junctions and, at
  z 3.088 -/+ 87.06, a #6 SHCS counterbore + dowel slip hole per knife
  mount: the MHA-VN-024 screw drops through the counterbore into the
  mount's tap, the MHA-VN-051 dowel slips into the blind underside hole.
* Gooseneck hub on the east rail (-X) at z +3.088: full-height rib 27 wide,
  O17 clearance bore for the O16 counter-spring post, underside boss
  O30 x 8 with twin V-gussets (ch30 p004), a 16 x 16 x 2 cast pocket and
  a 1/4-20 tap through the rib to the bore for the square-head set screw
  (book p.45: "a square-head screw pinches the post in its socket").
* Webbed faces (T-rail section): an 8-tall full-thickness top flange, then
  the web thins to 13.0 centred on each rail and STAYS thin through the
  bottom edge. The former photo-read 12.7 web is thickened for the keeper
  receivers' printed-band plus drill-wander stack; full-thickness lands remain
  at the bosses, hub rib and crossbar junctions.
* Finishing (chamfer external, fillet internal): R3 cast fillets along
  the internal web/flange T-roots (both shelves of every rail, ch19
  img04's panel blends), C2 x 45 breaks on the top-face rims -- outer
  rail rim and both window rims -- and C1 x 45 lead-ins on the bore
  TOP ends only. The R22.5 bosses bulge 5.4 beyond the side rails and
  3.5 beyond the front/rear rails, but no longer reach the plan corners
  (25.56 from their centres): window corners and short outer-corner
  rim runs remain. The web bottom rim and boss undersides stay sharp.

Layout: plan profile in XZ, ring mid-plane extruded symmetrically in Y
(rails y -18.25..+18.25 local). Sketches on the Top plane use the
(x, y) -> (X, -Z) handedness; sketches on Right-plane offsets map
(x, y) -> (Z, Y) (build_fr_rocker_arm_support precedent; NEGATIVE-offset
planes mirror sketch x -- see the gusset/pocket sites). Build order
(ADDITIVE T-section -- the web/flange rings are extruded, not pocketed):
web ring -> crossbar junction lands -> top-flange ring -> hub rib
restore -> crossbar+gussets -> corner bosses (up/down pair) -> hub boss
+ V-gussets -> set-screw pocket -> spot-faces -> column bores ->
gooseneck bore -> wizard holes (#6 SHCS hanger counterbores) -> dowel
slip holes -> wizard holes (side-screw taps, set-screw tap, keeper taps)
-> internal T-root fillets (R3) -> external
top-rim breaks (C2) -> C1 bore top lead-ins -> keeper-seat split lines.
Wizard holes come after the face cuts so every seat face is final; the
edge breaks and zero-volume split lines follow the solid features.
Analytic volume checks after every feature; boss additions and top-rim
breaks use circle-segment formulas, while hub/spot-face/tap expectations
use small grid integrals against the webbed solid.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fr_top_frame.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    _early_bound,
    CASTING_GREEN,
    SketchDims,
    _feature_by_name,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    define_polygon_chain,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    feature_name_by_type,
    name_last_feature,
    name_dimensions,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
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
from _part_pmi import _resolve_faces, author_part_pmi
from _named_views import name_octant_views
from _gtol_spec import PlanarFace
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from fr_top_frame_spec import (
    BORE_DIA,
    BOSS_ABOVE,
    BOSS_DIA,
    CAP_RECESS_FLOOR_Y,
    COLUMN_X,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_NOTES_B,
    DRAWING_PRECISION,
    DRILL_OVERSIZE,
    DRAWING_REFERENCE_PRECISION,
    FLANGE_THICKNESS_MM,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    HALF_H,
    HANGER_CBORE_DEPTH,
    HANGER_CBORE_DIA,
    HANGER_CLEARANCE_DIA,
    HANGER_GRIP,
    HANGER_HOLE_SPEC,
    HANGER_PIN_HOLE_DEPTH,
    HANGER_PIN_HOLE_DIA,
    HANGER_PIN_HOLE_DIA_BAND,
    HANGER_PIN_X_TOL,
    HANGER_ROUND_X,
    HANGER_SLOT_DEPTH,
    HANGER_SLOT_LENGTH,
    HANGER_SLOT_LENGTH_TOL,
    HANGER_SLOT_STATION_TOL,
    HANGER_SLOT_WIDTH,
    HANGER_SLOT_WIDTH_BAND,
    HANGER_SLOT_X,
    KEEPER_TAP_CALLOUT_PRECISION,
    KEEPER_TAP_DRILL_WANDER_DEG,
    KEEPER_SEAT_BOUNDS_XZ,
    KEEPER_SEAT_CENTRES_XZ,
    KEEPER_SEAT_EDGE_MARGIN_MM,
    KEEPER_SEAT_LENGTH_MM,
    KEEPER_SEAT_WIDTH_MM,
    PRINTED_DRILLED_HOLE_PLUS_MM,
    PRINTED_LINEAR_BAND_MM,
    REAR_COLUMN_Z,
    RING_HEIGHT,
    SURFACE_FINISHES,
)
from dt_cone_pivot_post_installation import (
    FRAME_COLUMN_Z_CENTER,
    SUMMING_Z,
)
from fr_frame_attachment_spec import (
    CAP_RECESS_DEPTH,
    CAP_RECESS_DIAMETER,
    CASTING_FULL_THREAD_DEPTH,
    TOP_CASTING_TAP_DRILL_DEPTH,
    SCREW_SPOTFACE_DIAMETER,
    TOP_SCREW_SEAT_Z,
)
from _fit_limits import deviations
from vn_tube_frame_cap_spec import MAX_OUTER_DIAMETER as CAP_MAX_OUTER_DIAMETER
from vn_frame_side_screw_spec import SHANK_DIA as KEEPER_SCREW_MAJOR_DIA
from ch_fulcrum_keeper_spec import (
    DRAWING_PRECISION as KEEPER_DRAWING_PRECISION,
    FOOT_L,
    FOOT_COUNTERBORE_DEPTH_PLACES,
    FOOT_H,
    FOOT_SCREW_LENGTH_MM,
    CBORE_DEPTH_MM,
    KEEPER_FITUP_X_FROM_WEB_MM,
    KEEPER_SCREW_TRANSVERSE_BAND_MM,
    SCREW_FROM_SIDE,
    KEEPER_FITUP_LOCATION_BAND_MM,
    KEEPER_FITUP_PLACES,
    KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM,
    LUG_HALF_T,
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

# --- Plan geometry (machine == part-local x/z; part y = machine y - 1017.95) --
#
# COLUMN_X, FRONT/REAR_COLUMN_Z, RING_HEIGHT, HALF_H, BOSS_ABOVE, BORE_DIA,
# CAP_RECESS_FLOOR_Y, GOOSENECK_X and GOOSENECK_BORE_DIA are imported from
# fr_top_frame_spec: the machined-surface face specs are keyed off those stations,
# and the spec is the COM-free contract the drawing's finish symbols are
# provenance-checked against.
FRAME_CENTER_Z = FRAME_COLUMN_Z_CENTER  # 0.0

RAIL_W_SIDE = 34.2  # side rails, along Z (GT corner rescale 221.5 -> 214.1)
RAIL_W_FR = 38.0  # front/rear rails, along X (GT z-corner rescale 137.4 -> 131)

BOSS_BELOW = 6.3  # boss hang below the underside (p006 read 5.7-7)
CAP_RECESS_DIAMETER_BAND = (0.20, 0.0)
CAP_RECESS_DEPTH_BAND = (0.30, 0.0)
CAP_RECESS_DIAMETRAL_CLEARANCE = CAP_RECESS_DIAMETER - CAP_MAX_OUTER_DIAMETER
if CAP_RECESS_DIAMETRAL_CLEARANCE <= 0.0:
    raise AssertionError("purchased cap does not clear the top-frame recess")

OUTER_X = COLUMN_X + RAIL_W_SIDE / 2.0  # 214.1
INNER_X = COLUMN_X - RAIL_W_SIDE / 2.0  # 179.9
OUTER_Z = abs(FRONT_COLUMN_Z) + RAIL_W_FR / 2.0  # 131.0
INNER_Z = abs(FRONT_COLUMN_Z) - RAIL_W_FR / 2.0  # 93.0

# --- Integral crossbar (old top-crossbar, merged) ---------------------------
BAR_X0, BAR_X1 = -26.0, -4.0  # 22 wide, centred on KNIFE x = -15
GUSSET = 18.0  # plan gusset legs at the four rail junctions
HEX_Z_MID = 87.06  # knife-mount trunnion mid offset (build_sm_summing_assembly)
STUD_Z_FRONT = SUMMING_Z - HEX_Z_MID  # -83.972
STUD_Z_REAR = SUMMING_Z + HEX_Z_MID  # +90.148
HANGER_X = BAR_X0 + 11.0  # -15.0: the crossbar centreline, KNIFE x
PIN_HOLE_X = HANGER_X + HANGER_ROUND_X  # -8.65: round dowel slip holes, +X
SLOT_X = HANGER_X + HANGER_SLOT_X  # -21.35: dowel slots, -X of the screw
SLOT_FLAT = HANGER_SLOT_LENGTH - HANGER_SLOT_WIDTH  # 1.06: straight run
HANGER_SLOT_AREA = (
    SLOT_FLAT * HANGER_SLOT_WIDTH + math.pi * (HANGER_SLOT_WIDTH / 2.0) ** 2
)


def slot_stadium_points(
    centre: tuple[float, float], *, along_u: bool, half_flat: float, half_w: float
) -> tuple[tuple[float, float], ...]:
    """One slot's stadium in sketch ``(u, v)``, counter-clockwise.

    Returns ``(p1, p2, p3, p4, centre_b, centre_a)``: side a runs p1 -> p2,
    end b arcs (CCW, the ``add_arc`` sense) about centre_b from p2 to p3,
    side b runs p3 -> p4 and end a arcs about centre_a from p4 back to p1.
    The slot runs along sketch u when ``along_u``, else along v (the same
    shape turned a quarter, which keeps it counter-clockwise).
    """
    u0, v0 = centre

    def at(du: float, dv: float) -> tuple[float, float]:
        return (u0 + du, v0 + dv) if along_u else (u0 - dv, v0 + du)

    return (
        at(-half_flat, -half_w),
        at(half_flat, -half_w),
        at(half_flat, half_w),
        at(-half_flat, half_w),
        at(half_flat, 0.0),
        at(-half_flat, 0.0),
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


# Each underside cut's sketch contours in model (x, z): the round dowel holes
# (circles) and the dowel slots (stadiums), one per station.
HANGER_PIN_CONTOURS = tuple(
    ((PIN_HOLE_X, z), (PIN_HOLE_X, z), HANGER_PIN_HOLE_DIA / 2.0)
    for z in (STUD_Z_FRONT, STUD_Z_REAR)
)
HANGER_SLOT_CONTOURS = tuple(
    (
        (SLOT_X - SLOT_FLAT / 2.0, z),
        (SLOT_X + SLOT_FLAT / 2.0, z),
        HANGER_SLOT_WIDTH / 2.0,
    )
    for z in (STUD_Z_FRONT, STUD_Z_REAR)
)
for _cut, _contours in (
    ("dowel slip holes", HANGER_PIN_CONTOURS),
    ("dowel slots", HANGER_SLOT_CONTOURS),
):
    if not swept_contours_disjoint(_contours):
        raise AssertionError(f"the {_cut} sketch's contours overlap: {_contours}")

# --- Gooseneck hub (old gooseneck-clamp function, merged) -------------------
GOOSENECK_Z = SUMMING_Z
HUB_RIB_W = 27.0  # full-height rib band across the east rail
HUB_BOSS_DIA = 30.0  # underside boss around the bore exit
HUB_BOSS_DROP = 8.0  # boss bottom local -26.25
HUB_GUSSET_T = 7.0  # V-gusset thickness along X (x -200.5..-193.5)
HUB_GUSSET_HALF_IN = 8.0  # full-depth span |z - 3.088| <= 8
HUB_GUSSET_HALF_OUT = 30.0  # feathers to the underside at |z - 3.088| = 30
SET_POCKET = 16.0  # cast pocket (square) around the set-screw tap
SET_POCKET_DEPTH = 2.0
# The tap opens into the gooseneck bore; it has no blind thread-depth limit.
SET_TAP_SPEC = HoleSpec("tapped", "1/4-20", end="through_next")

# --- Cross screws (frame -> tube-frame columns -> far casting wall) ----------
SPOTFACE_DIA = SCREW_SPOTFACE_DIAMETER
SPOTFACE_PLANE = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0 + 0.4
SPOTFACE_FLOOR = TOP_SCREW_SEAT_Z
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
if CAP_RECESS_FLOOR_Y - SIDE_TAP_DRILL_DIA / 2.0 <= 0.0:
    raise AssertionError("cap recess breaks into the cross-screw drill")

# --- Fulcrum keepers (west rail top face; shaft-end brackets, ch17 p.40) ----
# The keeper's pure spec owns both screw station and receiver geometry:
# #2-56 with 7.6 full thread and 11.5 drill retains a five-pitch plug
# lead at the sheet's general .X depth band. No assembly recipe dependency.
KEEPER_TAP_X = COLUMN_X + KEEPER_FITUP_X_FROM_WEB_MM  # nominal fulcrum line
KEEPER_TAP_Z_FRONT = FULCRUM_KEEPER_CENTRE_Z - KEEPER_SCREW_Z_OFF  # -82.754
KEEPER_TAP_Z_REAR = FULCRUM_KEEPER_CENTRE_Z + KEEPER_SCREW_Z_OFF  # +81.746

# --- Webbing ----------------------------------------------------------------
# T-rail section (user-corrected vs ch19 img04): an 8-tall full-thickness top
# flange, below which the web thins to WEB_T centred on each rail's centreline
# and STAYS thin through the bottom edge (no bottom flange). Built ADDITIVELY:
# a full-height thin web ring + an 8-tall full-width flange ring (two
# nested-rectangle sketches), plus full-thickness restore pads at the hub rib
# and the crossbar junctions. The corner bosses supply the corner lands. The
# per-face setback differs by rail family (the rails are 34.2/38.0 wide but
# share one web thickness).
FLANGE = FLANGE_THICKNESS_MM  # final top flange, also below the faced seats
WEB_T = 13.0  # user ruling: retain loose bands plus realistic deep-drill wander
RECESS_SIDE = (RAIL_W_SIDE - WEB_T) / 2.0  # 10.6 setback per side-rail face
RECESS_FR = (RAIL_W_FR - WEB_T) / 2.0  # 12.5 setback per front/rear-rail face
FLANGE_BOT_Y = RING_HEIGHT / 2.0 - FLANGE  # +10.25 (flange underside)
WEB_OUT_X = COLUMN_X + WEB_T / 2.0  # 203.5
WEB_IN_X = COLUMN_X - WEB_T / 2.0  # 190.5
WEB_OUT_Z = abs(FRONT_COLUMN_Z) + WEB_T / 2.0  # 118.5
WEB_IN_Z = abs(FRONT_COLUMN_Z) - WEB_T / 2.0  # 105.5
LAND_X0 = BAR_X0 - GUSSET - 6.0  # -50; crossbar-junction land pads on the
LAND_X1 = BAR_X1 + GUSSET + 6.0  # +20; front/rear inner faces (6 margin)

THROUGH_CUT_DEPTH = 110.0  # mid-plane total; > boss stack (47.3)

# --- Edge finishing ----------------------------------------------------------
# Convention (2026-08-03): CHAMFER external edges, FILLET internal wall
# junctions. The web ring's bottom rim and the boss undersides keep sharp
# edges (no low-side breaks -- explicit instruction).
ROOT_FILLET_R = 3.0  # internal web/flange T-root blends (cast root, ch19 img04)
EDGE_CHAMFER = 2.0  # external top-face rim breaks, 45 deg (one grinding pass)
BORE_CHAMFER = 1.0  # note 9: C1 x 45 TOP-end bore breaks; low ends stay sharp

if abs(FRONT_COLUMN_Z + REAR_COLUMN_Z) > 1e-12 or abs(FRAME_CENTER_Z) > 1e-12:
    raise AssertionError("top-frame assumes a symmetric column span about z 0")
if STUD_Z_REAR + HANGER_CBORE_DIA / 2.0 >= INNER_Z + GUSSET:
    raise AssertionError("rear hanger counterbore escapes the junction material")
# Dowel slip holes and slots (rule 12, print-worst): the largest reamed hole
# and the longest slot keep a wall to the crossbar's +X / -X face and to the
# largest drilled screw clearance hole with the round hole's station at its
# .XXX limit and the slot's at that plus its zone radius off the BASIC 12.700
# (0.155); their blind floors stay below the counterbore floor, so neither
# meets the screw's bearing face.  The slot's screw-side wall (1.581) sits
# under the 2.0 target, over the 1.5 floor.
_PIN_HOLE_MAX_R = (HANGER_PIN_HOLE_DIA + max(HANGER_PIN_HOLE_DIA_BAND)) / 2.0
_CLEARANCE_MAX_R = (HANGER_CLEARANCE_DIA + DRILL_OVERSIZE) / 2.0
_SLOT_MAX_HALF_L = (HANGER_SLOT_LENGTH + HANGER_SLOT_LENGTH_TOL) / 2.0
PIN_HOLE_BAR_WALL = BAR_X1 - (PIN_HOLE_X + HANGER_PIN_X_TOL) - _PIN_HOLE_MAX_R  # 2.885
PIN_HOLE_SCREW_WALL = (
    HANGER_ROUND_X - HANGER_PIN_X_TOL - _PIN_HOLE_MAX_R - _CLEARANCE_MAX_R
)  # 2.376
SLOT_BAR_WALL = (SLOT_X - HANGER_SLOT_STATION_TOL - _SLOT_MAX_HALF_L) - BAR_X0  # 2.09
SLOT_SCREW_WALL = (
    -HANGER_SLOT_X - HANGER_SLOT_STATION_TOL - _SLOT_MAX_HALF_L - _CLEARANCE_MAX_R
)  # 1.581
PIN_HOLE_FLOOR_MARGIN = HANGER_GRIP - HANGER_PIN_HOLE_DEPTH  # 18.0
SLOT_FLOOR_MARGIN = HANGER_GRIP - HANGER_SLOT_DEPTH  # 18.0
for _label, _value in (
    ("hole wall to the crossbar +X face", PIN_HOLE_BAR_WALL),
    ("hole wall to the screw clearance hole", PIN_HOLE_SCREW_WALL),
    ("slot wall to the crossbar -X face", SLOT_BAR_WALL),
    ("slot wall to the screw clearance hole", SLOT_SCREW_WALL),
    ("hole floor below the counterbore floor", PIN_HOLE_FLOOR_MARGIN),
    ("slot floor below the counterbore floor", SLOT_FLOOR_MARGIN),
):
    if _value <= 0.0:
        raise AssertionError(f"knife-mount dowel slip {_label}: {_value:.3f}")
if HUB_GUSSET_T / 2.0 > WEB_T / 2.0:
    raise AssertionError("hub V-gussets escape the east-rail web")
# The unified tap table rounds its nominal major; the actual stock major
# must also fit. Use the larger diameter for every receiver-wall guard.
KEEPER_TAP_THREAD_MAJOR_DIA = max(
    THREAD_MAJOR_MM[KEEPER_TAP_SPEC.size], KEEPER_SCREW_MAJOR_DIA
)
if abs(KEEPER_TAP_X - COLUMN_X) + KEEPER_TAP_THREAD_MAJOR_DIA / 2.0 > WEB_T / 2.0:
    raise AssertionError("keeper taps break out of the west-rail web")
SPOTFACE_FULL_SEAT_LIMIT_Z = abs(FRONT_COLUMN_Z) + math.sqrt(
    (BOSS_DIA / 2.0) ** 2 - (SPOTFACE_DIA / 2.0) ** 2
)
SPOTFACE_SEAT_MARGIN = SPOTFACE_FULL_SEAT_LIMIT_Z - SPOTFACE_FLOOR
# Prove the complete spotface at the PRINTED bands, not only nominal geometry.
# Boss diameter, spotface diameter and floor offset all print .X: use the
# smallest barrel, largest seat and most-outboard floor. The offset is from
# the same socket axis, so socket pitch does not enter this local stack.
SPOTFACE_MIN_BOSS_RADIUS = (
    round(BOSS_DIA, DRAWING_PRECISION["BossUpProfile"]["C0Dia"])
    - PRINTED_LINEAR_BAND_MM[DRAWING_PRECISION["BossUpProfile"]["C0Dia"]]
) / 2.0
SPOTFACE_MAX_SEAT_RADIUS = (
    round(SPOTFACE_DIA, DRAWING_PRECISION["SpotFaceRearProfile"]["S1Dia"])
    + PRINTED_LINEAR_BAND_MM[DRAWING_PRECISION["SpotFaceRearProfile"]["S1Dia"]]
) / 2.0
SPOTFACE_MAX_FLOOR_OFFSET = (
    round(
        SPOTFACE_FLOOR - abs(FRONT_COLUMN_Z),
        DRAWING_REFERENCE_PRECISION["spotface floor from socket axis"],
    )
    + PRINTED_LINEAR_BAND_MM[
        DRAWING_REFERENCE_PRECISION["spotface floor from socket axis"]
    ]
)
SPOTFACE_PRINTED_SEAT_MARGIN = (
    math.sqrt(SPOTFACE_MIN_BOSS_RADIUS**2 - SPOTFACE_MAX_SEAT_RADIUS**2)
    - SPOTFACE_MAX_FLOOR_OFFSET
)
if (
    min(SPOTFACE_SEAT_MARGIN, SPOTFACE_PRINTED_SEAT_MARGIN) < 0.1
    or SPOTFACE_PLANE <= SPOTFACE_FLOOR
):
    raise AssertionError(
        "top cross-screw spotface loses its full seat at the printed bands"
    )
SIDE_TAP_THREAD_MAJOR_DIA = THREAD_MAJOR_MM[SIDE_TAP_SPEC.size]
SIDE_TAP_THREAD_END_Z = SPOTFACE_FLOOR - CASTING_FULL_THREAD_DEPTH
SIDE_TAP_DRILL_POINT_Z = (
    SPOTFACE_FLOOR
    - TOP_CASTING_TAP_DRILL_DEPTH
    - SIDE_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
)
# The boss's inward edge is NOT a free wall: the centred side-rail web
# continues inward at full height. For the whole far tap/drill envelope,
# |x - ColumnX| <= radius < WebT/2 and |y| <= radius < HalfH, so boss ∪
# web supplies uninterrupted metal beyond both ends. The actual limiting
# walls are the web's x faces (and its y faces), not z=112-R22.5. Nominal
# lateral ligaments: thread major 6.5-2.413=4.087; drill 6.5-2.0193=4.4807.
SIDE_TAP_THREAD_WALL_MARGIN = WEB_T / 2.0 - SIDE_TAP_THREAD_MAJOR_DIA / 2.0
SIDE_TAP_DRILL_WALL_MARGIN = WEB_T / 2.0 - SIDE_TAP_DRILL_DIA / 2.0
if min(SIDE_TAP_THREAD_WALL_MARGIN, SIDE_TAP_DRILL_WALL_MARGIN) < 2.0:
    raise AssertionError("top cross-tap leaves less than 2 mm of side-rail web")
if not (
    0.0 < SIDE_TAP_DRILL_POINT_Z < SIDE_TAP_THREAD_END_Z < WEB_IN_Z
    and max(SIDE_TAP_THREAD_MAJOR_DIA, SIDE_TAP_DRILL_DIA) / 2.0 < HALF_H
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
# plus its DRO band, full lug thickness, foot length and boss OD; the rear
# also loses the printed socket-pitch band. Taking zero nearest-X distance
# is conservative for the complete foot, whatever its X position.
KEEPER_FOOT_LENGTH_BAND_MM = PRINTED_LINEAR_BAND_MM[
    KEEPER_DRAWING_PRECISION["FootProfile"]["FootLength"]
]
BOSS_DIA_BAND_MM = PRINTED_LINEAR_BAND_MM[DRAWING_PRECISION["BossUpProfile"]["C0Dia"]]
KEEPER_PRINTED_MAX_OUTBOARD_REACH = (
    round(2.0 * LUG_HALF_T, KEEPER_DRAWING_PRECISION["LugBody"]["LugThickness"])
    + PRINTED_LINEAR_BAND_MM[KEEPER_DRAWING_PRECISION["LugBody"]["LugThickness"]]
    + round(FOOT_L, KEEPER_DRAWING_PRECISION["FootProfile"]["FootLength"])
    + KEEPER_FOOT_LENGTH_BAND_MM
)
KEEPER_PRINTED_MAX_BOSS_RADIUS = (
    round(BOSS_DIA, DRAWING_PRECISION["BossUpProfile"]["C0Dia"]) + BOSS_DIA_BAND_MM
) / 2.0
KEEPER_PRINTED_MIN_SOCKET_PITCH = (
    round(
        REAR_COLUMN_Z - FRONT_COLUMN_Z,
        DRAWING_REFERENCE_PRECISION["socket vertical pitch"],
    )
    - PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["socket vertical pitch"]]
)
KEEPER_FOOT_PRINTED_BOSS_MARGINS = (
    round(KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0], KEEPER_FITUP_PLACES)
    - KEEPER_FITUP_LOCATION_BAND_MM
    - KEEPER_PRINTED_MAX_OUTBOARD_REACH
    - KEEPER_PRINTED_MAX_BOSS_RADIUS,
    KEEPER_PRINTED_MIN_SOCKET_PITCH
    - round(KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[1], KEEPER_FITUP_PLACES)
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
KEEPER_MIN_FOOT_WIDTH = (
    round(KEEPER_WIDTH, KEEPER_DRAWING_PRECISION["Foot"]["Depth"])
    - PRINTED_LINEAR_BAND_MM[KEEPER_DRAWING_PRECISION["Foot"]["Depth"]]
)
KEEPER_MAX_FOOT_WIDTH = (
    round(KEEPER_WIDTH, KEEPER_DRAWING_PRECISION["Foot"]["Depth"])
    + PRINTED_LINEAR_BAND_MM[KEEPER_DRAWING_PRECISION["Foot"]["Depth"]]
)

# Facing covers the ACTUAL complete contact plus its 0.10 edge allowance;
# the split-line model rectangles are nominal references, not fixed tooling.
KEEPER_SEAT_PRINTED_BOSS_MARGINS = tuple(
    margin - KEEPER_SEAT_EDGE_MARGIN_MM for margin in KEEPER_FOOT_PRINTED_BOSS_MARGINS
)
KEEPER_SEAT_PRINTED_FLANGE_SIDE_MARGIN = (
    (
        round(RAIL_W_SIDE, DRAWING_REFERENCE_PRECISION["side flange width"])
        - PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["side flange width"]]
    )
    / 2.0
    - (
        abs(round(KEEPER_FITUP_X_FROM_WEB_MM, KEEPER_FITUP_PLACES))
        + KEEPER_FITUP_LOCATION_BAND_MM
    )
    - KEEPER_MAX_FOOT_WIDTH / 2.0
    - KEEPER_SEAT_EDGE_MARGIN_MM
)
# Only the flat portion can carry a faced contact: remove the maximum
# printed C2 top-rim leg as well as the actual-foot edge allowance.
KEEPER_SEAT_PRINTED_FLAT_TOP_SIDE_MARGIN = KEEPER_SEAT_PRINTED_FLANGE_SIDE_MARGIN - (
    round(EDGE_CHAMFER, DRAWING_REFERENCE_PRECISION["top rim chamfer"])
    + PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["top rim chamfer"]]
)
if (
    min(*KEEPER_SEAT_PRINTED_BOSS_MARGINS, KEEPER_SEAT_PRINTED_FLAT_TOP_SIDE_MARGIN)
    <= 0.0
):
    raise AssertionError("keeper faced region escapes the flat top flange")

KEEPER_PRINTED_SIDE_STATION = round(
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
KEEPER_MAX_WEB_CENTRE_OFFSET = (
    abs(round(KEEPER_FITUP_X_FROM_WEB_MM, KEEPER_FITUP_PLACES))
    + KEEPER_FITUP_LOCATION_BAND_MM
    + KEEPER_MAX_TRANSVERSE_OFFSET
)
KEEPER_MIN_WEB_HALF_WIDTH = (
    round(WEB_T, DRAWING_REFERENCE_PRECISION["side rail web thickness"])
    - PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["side rail web thickness"]]
) / 2.0
# The controlling .X dimension on KEEPER-SEATS measures the FINAL local
# flange under each faced contact. Cap-floor and boss-height bands cannot
# subtract a second facing allowance from this directly printed minimum.
KEEPER_MIN_FLANGE_THICKNESS = (
    round(FLANGE, DRAWING_REFERENCE_PRECISION["keeper seat flange thickness"])
    - PRINTED_LINEAR_BAND_MM[
        DRAWING_REFERENCE_PRECISION["keeper seat flange thickness"]
    ]
)
KEEPER_MIN_ROOT_RADIUS = (
    round(ROOT_FILLET_R, DRAWING_REFERENCE_PRECISION["T rail root radius"])
    - PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["T rail root radius"]]
)
KEEPER_MAX_FULL_THREAD_DEPTH = (
    round(
        KEEPER_TAP_SPEC.overrides_mm["ThreadDepth"],
        KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"],
    )
    + PRINTED_LINEAR_BAND_MM[KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]]
)
KEEPER_MAX_TAP_DRILL_DEPTH = (
    round(KEEPER_TAP_SPEC.depth_mm, KEEPER_TAP_CALLOUT_PRECISION["hw-tapdrldepth"])
    + PRINTED_LINEAR_BAND_MM[KEEPER_TAP_CALLOUT_PRECISION["hw-tapdrldepth"]]
)
# Rule 12: budget realistic deep-drill wander over the FULL allowed
# cylindrical depth, not only the shorter threaded region. Its displacement
# disk conservatively covers every pilot/thread section and every direction;
# subtracting its radius from the normal wall distance handles the T-root
# without an optimistic horizontal projection or a claimed guide operation.
KEEPER_TAP_AXIS_WANDER_MM = KEEPER_MAX_TAP_DRILL_DEPTH * math.tan(
    math.radians(KEEPER_TAP_DRILL_WANDER_DEG)
)
# The limiting full-thread corner lies next to the quarter-circle T-root.
# Use its shortest NORMAL distance to that arc, not the larger horizontal
# section width. Below the arc the same expression becomes the bare web.
KEEPER_TAP_THREAD_WALL_MARGIN_NO_WANDER = (
    math.hypot(
        KEEPER_MIN_WEB_HALF_WIDTH
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
    round(
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
if min(KEEPER_TAP_THREAD_WALL_MARGIN, KEEPER_TAP_DRILL_WALL_MARGIN) < 1.5:
    raise AssertionError("keeper receiver leaves less than 1.5 mm with drill wander")
KEEPER_MAX_STOCK_ENTRY = FOOT_SCREW_LENGTH_MM - (
    (
        round(FOOT_H, KEEPER_DRAWING_PRECISION["FootProfile"]["FootRise"])
        - PRINTED_LINEAR_BAND_MM[KEEPER_DRAWING_PRECISION["FootProfile"]["FootRise"]]
    )
    - (
        round(CBORE_DEPTH_MM, FOOT_COUNTERBORE_DEPTH_PLACES)
        + PRINTED_LINEAR_BAND_MM[FOOT_COUNTERBORE_DEPTH_PLACES]
    )
)
KEEPER_MIN_THREAD_TIP_RESERVE = (
    round(
        KEEPER_TAP_SPEC.overrides_mm["ThreadDepth"],
        KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"],
    )
    - PRINTED_LINEAR_BAND_MM[KEEPER_TAP_CALLOUT_PRECISION["hw-threaddepth"]]
    - KEEPER_MAX_STOCK_ENTRY
)
if KEEPER_MIN_THREAD_TIP_RESERVE < 0.25:
    raise AssertionError("keeper foot screw loses its 0.25 mm blind-thread clearance")


# --------------------------------------------------------------------------
# Analytic expectations. The webbed casting has no tidy closed form at the
# bosses/hub/tap break-ins, so those pieces integrate on fine grids (0.02 mm
# cells) exactly like the old _boss_extra_area did.
# --------------------------------------------------------------------------


def _in_web_plan(x: float, z: float) -> bool:
    """Full-height web-ring plan membership (NE-quadrant symmetric test)."""
    ax, az = abs(x), abs(z)
    return (WEB_IN_X <= ax <= WEB_OUT_X and az <= WEB_OUT_Z) or (
        WEB_IN_Z <= az <= WEB_OUT_Z and ax <= WEB_OUT_X
    )


def _in_flange_plan(x: float, z: float) -> bool:
    """Top-flange ring plan membership."""
    ax, az = abs(x), abs(z)
    return (INNER_X <= ax <= OUTER_X and az <= OUTER_Z) or (
        INNER_Z <= az <= OUTER_Z and ax <= OUTER_X
    )


def _circle_cap_area(radius: float, offset: float) -> float:
    """Area beyond a chord ``offset`` from the circle centre."""
    if offset >= radius:
        return 0.0
    return radius**2 * math.acos(offset / radius) - offset * math.sqrt(
        radius**2 - offset**2
    )


def _boss_add_volumes() -> tuple[float, float]:
    """Exact (up, down) additions of ONE corner boss to the T-section.

    The centred ring's outer rectangle clips the NE circle quadrant; its
    inner window clips the equal SW quadrant. Their corner overlaps cancel,
    leaving circle area minus the two outer-face circular caps. Web material
    spans the full band, flange-only material spans its top 8 mm, and the
    remaining caps have no rail material. All four corners match by symmetry.
    """
    radius = BOSS_DIA / 2.0
    circle = math.pi * radius**2
    web = circle - 2.0 * _circle_cap_area(radius, WEB_T / 2.0)
    flange = (
        circle
        - _circle_cap_area(radius, RAIL_W_SIDE / 2.0)
        - _circle_cap_area(radius, RAIL_W_FR / 2.0)
    )
    up = (
        BOSS_ABOVE * web
        + (HALF_H + BOSS_ABOVE - FLANGE) * (flange - web)
        + (HALF_H + BOSS_ABOVE) * (circle - flange)
    )
    down = BOSS_BELOW * web + (HALF_H + BOSS_BELOW) * (circle - web)
    return up, down


def _hub_boss_add_volume() -> float:
    """Volume the hub under-boss extrude (circle, y 0..-26.25) adds.

    Covered cells (hub rib plan or web ring) already hold -18.25..0, so the
    boss adds only the 8 below; the web-setback slivers (circle past the web
    faces, under the flange) are empty below +10.25 and gain the full 26.25.
    """
    r = HUB_BOSS_DIA / 2.0
    rib_lo = GOOSENECK_Z - HUB_RIB_W / 2.0
    rib_hi = GOOSENECK_Z + HUB_RIB_W / 2.0
    step = 0.02
    vol = 0.0
    x = GOOSENECK_X - r
    while x < GOOSENECK_X + r:
        xx = x + 0.5 * step
        dx2 = (xx - GOOSENECK_X) ** 2
        if dx2 > r * r:
            x += step
            continue
        half = math.sqrt(r * r - dx2)
        z = GOOSENECK_Z - half
        z_hi = GOOSENECK_Z + half
        while z < z_hi:
            zz = z + 0.5 * step
            if zz < z_hi:
                in_rib = rib_lo <= zz <= rib_hi and INNER_X <= abs(xx) <= OUTER_X
                covered = in_rib or _in_web_plan(xx, zz)
                vol += (
                    (HUB_BOSS_DROP if covered else HALF_H + HUB_BOSS_DROP) * step * step
                )
            z += step
        x += step
    return vol


def _hub_underhang_volume() -> float:
    """Volume of the hub boss + V-gussets union hanging below the underside."""
    step = 0.05
    r = HUB_BOSS_DIA / 2.0
    vol = 0.0
    x = -212.6
    while x < -181.4:
        xx = x + 0.5 * step
        z = GOOSENECK_Z - HUB_GUSSET_HALF_OUT - 0.6
        z_end = GOOSENECK_Z + HUB_GUSSET_HALF_OUT + 0.6
        while z < z_end:
            zz = z + 0.5 * step
            h = 0.0
            if (xx - GOOSENECK_X) ** 2 + (zz - GOOSENECK_Z) ** 2 <= r * r:
                h = HUB_BOSS_DROP
            elif -200.5 <= xx <= -193.5:
                t = abs(zz - GOOSENECK_Z)
                if t <= HUB_GUSSET_HALF_IN:
                    h = HUB_BOSS_DROP
                elif t <= HUB_GUSSET_HALF_OUT:
                    h = (
                        HUB_BOSS_DROP
                        * (HUB_GUSSET_HALF_OUT - t)
                        / (HUB_GUSSET_HALF_OUT - HUB_GUSSET_HALF_IN)
                    )
            vol += h * step * step
            z += step
        x += step
    return vol


def _spotface_removal() -> float:
    """Material one O9 spot-face removes from the Ø45 curved boss."""
    r_d = SPOTFACE_DIA / 2.0
    r_b = BOSS_DIA / 2.0
    step = 0.01
    vol = 0.0
    d = -r_d
    while d < r_d:
        dd = d + 0.5 * step
        chord = 2.0 * math.sqrt(max(0.0, r_d * r_d - dd * dd))
        surf = abs(FRONT_COLUMN_Z) + math.sqrt(max(0.0, r_b * r_b - dd * dd))
        length = max(0.0, min(surf, SPOTFACE_PLANE) - SPOTFACE_FLOOR)
        vol += chord * length * step
        d += step
    return vol


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
    """Material removed by the 1/4-20 tap through to the gooseneck bore."""
    r_h = TAP_DRILL_MM["1/4-20"] / 2.0
    r_v = GOOSENECK_BORE_DIA / 2.0
    floor_x = OUTER_X - SET_POCKET_DEPTH  # 212.1 (magnitudes, east side)
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


def _fillet_section_area(r: float) -> float:
    """Cross-section a radius-r fillet adds to (or a round removes from) a
    square 90-degree edge."""
    return (1.0 - math.pi / 4.0) * r * r


def _top_rim_removal() -> tuple[float, float]:
    """Exact (outer, window) C2 x 45 removals for the smaller-boss topology.

    R22.5 < hypot(17.1, 19) = 25.56: neither window corner nor outer rail
    corner ends on a boss. Outer faces intersect the barrel only near its
    centre, leaving four central runs PLUS eight short corner runs. The
    window rims are uninterrupted up to their square corners. Even their
    2 mm expanded chamfer corners miss the boss: hypot(15.1, 17) > R22.5.
    Outer strip areas exclude the proud cylinders analytically; the square
    outer corners and the windows' 90/135-degree mitres are included.
    """
    radius = BOSS_DIA / 2.0
    chamfer = EDGE_CHAMFER
    a, b = RAIL_W_SIDE / 2.0, RAIL_W_FR / 2.0
    if not max(a, b) < radius < math.hypot(a - chamfer, b - chamfer):
        raise AssertionError("top-rim formula requires separate rail/boss plan corners")

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

    outer_perimeter = 4.0 * (OUTER_X + OUTER_Z)
    outer = (
        outer_perimeter * chamfer**2 / 2.0
        - 4.0 * chamfer**3 / 3.0
        - 4.0 * (cap_integral(a) + cap_integral(b))
    )
    side_run = 2.0 * INNER_Z
    east_fr = INNER_X - (abs(BAR_X0) + GUSSET)
    west_fr = INNER_X - (BAR_X1 + GUSSET)
    hyp = GUSSET * math.sqrt(2.0)
    flank = 2.0 * (INNER_Z - GUSSET)
    window_perimeter = (
        2.0 * side_run + 2.0 * east_fr + 2.0 * west_fr + 4.0 * hyp + 2.0 * flank
    )
    # Each six-sided window has two 90-degree and four 135-degree corners.
    window_mitres = 2.0 * (2.0 + 4.0 * (math.sqrt(2.0) - 1.0))
    return outer, window_perimeter * chamfer**2 / 2.0 + window_mitres * chamfer**3 / 3.0


def _outer_corner_top_edges() -> list[list[float]]:
    """Midpoints of the eight rim edges outside the Ø45 boss barrels."""
    side_cut = math.sqrt((BOSS_DIA / 2.0) ** 2 - (RAIL_W_SIDE / 2.0) ** 2)
    fr_cut = math.sqrt((BOSS_DIA / 2.0) ** 2 - (RAIL_W_FR / 2.0) ** 2)
    return [
        point
        for sx in (-1.0, 1.0)
        for sz in (-1.0, 1.0)
        for point in (
            [
                sx * OUTER_X,
                HALF_H,
                sz * (abs(FRONT_COLUMN_Z) + side_cut + OUTER_Z) / 2.0,
            ],
            [sx * (COLUMN_X + fr_cut + OUTER_X) / 2.0, HALF_H, sz * OUTER_Z],
        )
    ]


def _t_root_add() -> float:
    """Volume the R3 internal T-root fillets add along the web-flange shelf.

    The reentrant junction where each recessed web face meets the flange
    underside (y +10.25), on BOTH the outer and the window side of every
    rail. Every web face sits WEB_T/2 = 6.5 off its rail centreline, so
    one boss chord covers all four families; the hub rib interrupts both
    east-rail runs, the junction lands interrupt both front/rear WINDOW
    runs. The fillet ends dying into boss barrels / rib / land walls and
    the small vertical junction coves at those walls are not modeled --
    the check tolerance absorbs the ends; the vertical coves stay sharp.
    """
    area = _fillet_section_area(ROOT_FILLET_R)
    cut = math.sqrt((BOSS_DIA / 2.0) ** 2 - (WEB_T / 2.0) ** 2)
    side = 2.0 * (abs(FRONT_COLUMN_Z) - cut)  # one side-rail run, west
    fr = 2.0 * (COLUMN_X - cut)  # one front/rear run, uninterrupted
    outer = side + (side - HUB_RIB_W) + 2.0 * fr
    window = side + (side - HUB_RIB_W) + 2.0 * (fr - (LAND_X1 - LAND_X0))
    return area * (outer + window)


def _bore_chamfer_removal() -> float:
    """Volume the C1 x 45 breaks remove from the five top bore rims."""

    def ring(bore_dia: float) -> float:
        return math.pi * BORE_CHAMFER**2 * (bore_dia / 2.0 + BORE_CHAMFER / 3.0)

    return 4.0 * ring(CAP_RECESS_DIAMETER) + ring(GOOSENECK_BORE_DIA)


def _open_underside_sketch(
    adapter, centres: list[tuple[float, float, float]]
) -> tuple[list[tuple[float, float]], bool, bool]:
    """Open a sketch ON the crossbar underside; map the slip-hole centres in.

    A face sketch anchors the blind depth on the real underside (the
    pd_transgear_arm latch-pin precedent): a negative Top-plane offset would
    leave its sketch handedness to SolidWorks.  The face's sketch axes are
    SolidWorks' choice too, so the centres map through
    ``ModelToSketchTransform``.  Returns each centre's sketch ``(u, v)``,
    whether sketch u carries model X, and whether the sketch normal points
    OUT of the underside (-Y).
    """
    import pythoncom
    from win32com.client import VARIANT

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    face = find_planar_face(model, (0.0, -1.0, 0.0), [list(c) for c in centres])
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError("dowel slip holes: crossbar underside Select2 failed")
    adapter.currentSketchManager = model.SketchManager
    adapter._reset_sketch_entity_registry()
    model.SketchManager.InsertSketch(True)
    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("dowel slip holes: no active sketch on the underside")
    adapter.currentSketch = active
    adapter._sketch_count += 1
    adapter._last_sketch_name = str(active.Name)
    sketch = _early_bound(active, "ISketch")
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

    mapped = [to_sketch(centre) for centre in centres]
    for centre, (_u, _v, w) in zip(centres, mapped):
        if abs(w) > 1e-4:
            raise RuntimeError(
                f"dowel slip hole {centre} is {w:g} mm off the underside sketch"
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


def _qualify_machined_faces(adapter) -> None:
    """Area-check every face the surface-finish spec owns.

    ``_resolve_faces`` already proves each spec names exactly ONE face; the
    area proves it named the RIGHT one, so a station typo ships a build failure
    instead of a roughness symbol on the wrong surface (build_fr_harmonic_base's
    _paint_machined_faces_black precedent). Expectations are the full analytic
    wall/annulus areas; the 5% band absorbs the cross-screw and set-screw tap
    windows that break into the bores (~1% each) and the C1 bore-top breaks.
    """
    faces = _resolve_faces(
        adapter.currentModel,
        {control.key: control.face for control in SURFACE_FINISHES},
    )
    socket_wall = math.pi * BORE_DIA * (CAP_RECESS_FLOOR_Y + HALF_H + BOSS_BELOW)
    cap_seat = math.pi / 4.0 * (CAP_RECESS_DIAMETER**2 - BORE_DIA**2)
    hub_wall = (
        math.pi * GOOSENECK_BORE_DIA * (HUB_BOSS_DROP + 2.0 * HALF_H - BORE_CHAMFER)
    )
    for key, face in faces.items():
        if key.startswith("cap_seat"):
            expected = cap_seat
        elif key == "hub_bore":
            expected = hub_wall
        else:
            expected = socket_wall
        area = float(face.GetArea()) * 1e6
        if abs(area - expected) > 0.05 * expected:
            raise RuntimeError(
                f"{key} face area {area:.0f} mm^2 != {expected:.0f} "
                "(minus tap windows and edge breaks)"
            )
        _telemetry.info(f"{key} face qualified ({area:.0f} mm^2)")


async def _split_keeper_seats(adapter) -> None:
    """Bound two faced regions without changing final height or material.

    Reuse the pinion-arbor's projected split-line convention: sketch mark 4,
    exact parent face mark 1. Finished-part CAD specifies the seat plane;
    it does not model a cast machining allowance or cut that plane lower.
    """
    x, z = KEEPER_SEAT_CENTRES_XZ[0]
    target = _resolve_faces(
        adapter.currentModel,
        {
            "keeper_top": PlanarFace(
                (0.0, 1.0, 0.0), HALF_H, contains_x_mm=x, contains_z_mm=z
            )
        },
    )["keeper_top"]
    dims = SketchDims()
    check("create keeper seat profile", await adapter.create_sketch("Top"))
    for index, (x0, x1, z0, z1) in enumerate(KEEPER_SEAT_BOUNDS_XZ):
        points = [(x0, -z1), (x1, -z1), (x1, -z0), (x0, -z0)]
        lines = await add_line_chain(adapter, points)
        await define_rectilinear_chain(
            adapter,
            lines,
            points,
            label=f"keeper seat {index}",
            dims=dims,
            names=[
                f"Seat{index}Width",
                f"Seat{index}Length",
                f"Seat{index}X",
                f"Seat{index}Z",
            ],
        )
    await ensure_fully_defined(adapter, "keeper seat profile")
    check("exit keeper seat profile", await adapter.exit_sketch())
    name_last_feature(adapter, "KeeperSeatProfile")
    dims.apply(adapter, "KeeperSeatProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    if (
        model.Extension.SelectByID2(
            "KeeperSeatProfile", "SKETCH", 0.0, 0.0, 0.0, False, 4, null_callout(), 0
        )
        is not True
    ):
        raise RuntimeError("keeper seats: failed to select the split sketch")
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    selection = _early_bound(manager.CreateSelectData(), "ISelectData")
    selection.Mark = 1
    if _early_bound(target, "IEntity").Select4(True, selection) is not True:
        raise RuntimeError("keeper seats: failed to select the rail top")
    previous = feature_name_by_type(adapter, "PLine")
    model.InsertSplitLineProject(False, False)
    model.ClearSelection2(True)
    split = feature_name_by_type(adapter, "PLine")
    if not split or split == previous:
        raise RuntimeError("keeper seats: projected split line was not created")
    name_last_feature(adapter, "KeeperSeatFaces")
    await force_rebuild(adapter)


def _qualify_keeper_seat_faces(adapter) -> None:
    """Prove two coplanar rectangles minus their existing tap openings.

    Face boxes are only coarse station filters (GetBox is approximate);
    area rejects the residual rail face and the exact-one count proves both
    local regions exist. No shared planar-selector or PMI changes are needed.
    """
    feature = _early_bound(_feature_by_name(adapter, "KeeperSeatFaces"), "IFeature")
    expected_area = (
        KEEPER_SEAT_WIDTH_MM * KEEPER_SEAT_LENGTH_MM
        - math.pi * (TAP_DRILL_MM[KEEPER_TAP_SPEC.size] / 2.0) ** 2
    )
    counts = [0, 0]
    for raw in feature.GetFaces() or ():
        face = _early_bound(raw, "IFace2")
        box = tuple(float(value) * 1000.0 for value in face.GetBox() or ())
        if len(box) != 6 or max(abs(box[1] - HALF_H), abs(box[4] - HALF_H)) > 0.1:
            continue
        area = float(face.GetArea()) * 1e6
        if abs(area - expected_area) > 0.01 * expected_area:
            continue
        for index, (x, z) in enumerate(KEEPER_SEAT_CENTRES_XZ):
            if box[0] - 0.1 <= x <= box[3] + 0.1 and box[2] - 0.1 <= z <= box[5] + 0.1:
                counts[index] += 1
    if counts != [1, 1]:
        raise RuntimeError(
            f"keeper seats: expected one {expected_area:.3f} mm^2 face per seat; got {counts}"
        )
    _telemetry.info(f"two keeper seat faces qualified ({expected_area:.3f} mm^2 each)")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

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
    await set_global(adapter, "BossTopExtent", f"{HALF_H + BOSS_ABOVE}mm")
    await set_global(adapter, "BossBottomExtent", f"{HALF_H + BOSS_BELOW}mm")
    await set_global(adapter, "HubBossExtent", f"{HALF_H + HUB_BOSS_DROP}mm")
    await set_global(adapter, "HubBossDia", f"{HUB_BOSS_DIA}mm")
    await set_global(adapter, "WebT", f"{WEB_T}mm")
    await set_global(adapter, "Flange", f"{FLANGE}mm")
    await set_global(adapter, "HangerPinHoleDia", f"{HANGER_PIN_HOLE_DIA}mm")
    await set_global(adapter, "HangerPinHoleDepth", f"{HANGER_PIN_HOLE_DEPTH}mm")
    await set_global(adapter, "HangerSlotWidth", f"{HANGER_SLOT_WIDTH}mm")
    await set_global(adapter, "HangerSlotLength", f"{HANGER_SLOT_LENGTH}mm")
    await set_global(adapter, "HangerSlotDepth", f"{HANGER_SLOT_DEPTH}mm")
    await set_global(adapter, "OuterX", '"ColumnX" + "RailWSide" / 2')
    await set_global(adapter, "OuterZ", '"ColumnZ" + "RailWFR" / 2')
    await set_global(adapter, "InnerX", '"ColumnX" - "RailWSide" / 2')
    await set_global(adapter, "InnerZ", '"ColumnZ" - "RailWFR" / 2')

    drive_jobs: list[tuple[str, str]] = []
    ref_planes: list[str] = []  # created offset planes, blanked before save

    # 1. Web ring: the full-height THIN section (T-rail web) as one annular
    #    extrude -- two nested origin-centred rectangles, the WEB_T-wide web
    #    centred on each rail's centreline (per-face setback: side rails
    #    10.6, front/rear 12.5).
    web = SketchDims()
    check("create_sketch web ring", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter,
        WEB_OUT_X,
        WEB_OUT_Z,
        "web outer rectangle",
        dims=web,
        name_width="WebOuterWidth",
        name_depth="WebOuterDepth",
        drive_width='2 * "ColumnX" + "WebT"',
        drive_depth='2 * "ColumnZ" + "WebT"',
    )
    await define_centered_rectangle(
        adapter,
        WEB_IN_X,
        WEB_IN_Z,
        "web inner rectangle",
        dims=web,
        name_width="WebInnerWidth",
        name_depth="WebInnerDepth",
        drive_width='2 * "ColumnX" - "WebT"',
        drive_depth='2 * "ColumnZ" - "WebT"',
    )
    await ensure_fully_defined(adapter, "web ring sketch")
    check("exit_sketch web ring", await adapter.exit_sketch())
    name_last_feature(adapter, "WebProfile")
    drive_jobs += web.apply(adapter, "WebProfile")
    check(
        "extrude web ring",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "WebRing")
    ring_height_dim = name_dimensions(adapter, "WebRing", ["RingHeight"])
    drive_jobs.append((ring_height_dim[0], '"RingHeight"'))
    v_web = 4.0 * (WEB_OUT_X * WEB_OUT_Z - WEB_IN_X * WEB_IN_Z) * RING_HEIGHT
    volume = await volume_check(adapter, "web ring", v_web, 0.001 * v_web)

    # 2. Crossbar junction lands: full-thickness pads on the front/rear
    #    inner faces where the crossbar + gussets butt in (x -50..20,
    #    z +/-(93..105.5)), full height. Sketch z flipped: (x, y) -> (X, -Z).
    lands = SketchDims()
    check("create_sketch junction lands", await adapter.create_sketch("Top"))
    for k, (z_lo, z_hi) in enumerate(((-WEB_IN_Z, -INNER_Z), (INNER_Z, WEB_IN_Z))):
        pts = [
            (LAND_X0, -z_hi),
            (LAND_X1, -z_hi),
            (LAND_X1, -z_lo),
            (LAND_X0, -z_lo),
        ]
        land_lines = await add_line_chain(adapter, pts)
        await define_rectilinear_chain(
            adapter,
            land_lines,
            pts,
            label=f"junction land {k}",
            dims=lands,
            names=[f"L{k}Run", f"L{k}Rise", f"L{k}OffX", f"L{k}OffZ"],
        )
    await ensure_fully_defined(adapter, "junction lands sketch")
    check("exit_sketch junction lands", await adapter.exit_sketch())
    name_last_feature(adapter, "LandProfile")
    drive_jobs += lands.apply(adapter, "LandProfile")
    check(
        "extrude junction lands",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "JunctionLands")
    v_lands = 2.0 * (LAND_X1 - LAND_X0) * RECESS_FR * RING_HEIGHT
    volume = await volume_check(adapter, "junction lands", volume + v_lands, 50.0)

    # 3. Top flange ring: the full-width 8-tall band, extruded from the
    #    flange underside plane up to the rail top (extrude_at_offset,
    #    positive offset -- proven helper). The OUTER rectangle carries the
    #    print's marked Width/Depth dims (OuterProfile contract).
    outer = SketchDims()
    check("create_sketch flange ring", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter,
        OUTER_X,
        OUTER_Z,
        "flange outer rectangle",
        dims=outer,
        name_width="Width",
        name_depth="Depth",
        drive_width='2 * "OuterX"',
        drive_depth='2 * "OuterZ"',
    )
    await define_centered_rectangle(
        adapter,
        INNER_X,
        INNER_Z,
        "flange window rectangle",
        dims=outer,
        name_width="WinWidth",
        name_depth="WinDepth",
        drive_width='2 * "InnerX"',
        drive_depth='2 * "InnerZ"',
    )
    await ensure_fully_defined(adapter, "flange ring sketch")
    check("exit_sketch flange ring", await adapter.exit_sketch())
    name_last_feature(adapter, "OuterProfile")
    drive_jobs += outer.apply(adapter, "OuterProfile")
    extrude_at_offset(adapter, FLANGE, FLANGE_BOT_Y)
    name_last_feature(adapter, "TopFlange")
    # New material only where the flange band is not already web/land solid.
    v_flange = (
        4.0 * (OUTER_X * OUTER_Z - INNER_X * INNER_Z)
        - 4.0 * (WEB_OUT_X * WEB_OUT_Z - WEB_IN_X * WEB_IN_Z)
        - 2.0 * (LAND_X1 - LAND_X0) * RECESS_FR
    ) * FLANGE
    volume = await volume_check(adapter, "top flange", volume + v_flange, 100.0)

    # 4. Hub rib restore: full rail thickness across the east rail at the
    #    gooseneck station, full height (the web setback comes back).
    rib = SketchDims()
    check("create_sketch hub rib", await adapter.create_sketch("Top"))
    rib_pts = [
        (-OUTER_X, -(GOOSENECK_Z + HUB_RIB_W / 2.0)),
        (-INNER_X, -(GOOSENECK_Z + HUB_RIB_W / 2.0)),
        (-INNER_X, -(GOOSENECK_Z - HUB_RIB_W / 2.0)),
        (-OUTER_X, -(GOOSENECK_Z - HUB_RIB_W / 2.0)),
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
    check(
        "extrude hub rib",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "HubRib")
    v_rib = 2.0 * RECESS_SIDE * HUB_RIB_W * (RING_HEIGHT - FLANGE)
    volume = await volume_check(adapter, "hub rib", volume + v_rib, 30.0)

    # 5. Integral crossbar + plan gussets (one 8-vertex polygon, sketch z
    #    flipped: (x, y) -> (X, -Z)).
    bar_pts_part = [
        (BAR_X0 - GUSSET, -INNER_Z),
        (BAR_X1 + GUSSET, -INNER_Z),
        (BAR_X1, -INNER_Z + GUSSET),
        (BAR_X1, INNER_Z - GUSSET),
        (BAR_X1 + GUSSET, INNER_Z),
        (BAR_X0 - GUSSET, INNER_Z),
        (BAR_X0, INNER_Z - GUSSET),
        (BAR_X0, -INNER_Z + GUSSET),
    ]
    bar_pts = [(x, -z) for x, z in bar_pts_part]
    bar = SketchDims()
    check("create_sketch crossbar", await adapter.create_sketch("Top"))
    bar_lines = await add_line_chain(adapter, bar_pts)
    await define_polygon_chain(
        adapter,
        bar_lines,
        bar_pts,
        anchor=0,
        label="crossbar",
        dims=bar,
        names=[
            "BarAnchorX",
            "BarAnchorZ",
            "BarFootSpan",
            "GussetRunE",
            "GussetRiseE",
            "BarSideE",
            "GussetRunE2",
            "GussetRiseE2",
            "BarHeadSpan",
            "GussetRunW",
            "GussetRiseW",
            "BarSideW",
        ],
    )
    await ensure_fully_defined(adapter, "crossbar sketch")
    check("exit_sketch crossbar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude crossbar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Crossbar")
    bar_area = (BAR_X1 - BAR_X0) * 2.0 * INNER_Z + 4.0 * GUSSET * GUSSET / 2.0
    v_bar = bar_area * RING_HEIGHT
    volume = await volume_check(adapter, "crossbar", volume + v_bar, 500.0)

    # 6. Corner bosses: one circle set extruded UP to the boss top, a second
    #    identical set extruded DOWN to the boss bottom (one-direction pair;
    #    a mid-plane extrude cannot land the asymmetric 22.75/24.55 split).
    #    Expected adds come from the T-section grid (web/flange/empty cells).
    v_boss_up, v_boss_down = _boss_add_volumes()
    r_boss = BOSS_DIA / 2.0
    for updown, depth, feat in (
        ("up", HALF_H + BOSS_ABOVE, "BossesUpper"),
        ("down", HALF_H + BOSS_BELOW, "BossesLower"),
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
        name_last_feature(adapter, f"Boss{updown.capitalize()}Profile")
        drive_jobs += bosses.apply(adapter, f"Boss{updown.capitalize()}Profile")
        check(
            f"extrude bosses {updown}",
            await adapter.create_extrusion(
                ExtrusionParameters(depth=depth, reverse_direction=(updown == "down"))
            ),
        )
        name_last_feature(adapter, feat)
        extent_name = "BossTopExtent" if updown == "up" else "BossBottomExtent"
        boss_extent_dim = name_dimensions(adapter, feat, [extent_name])
        drive_jobs.append((boss_extent_dim[0], f'"{extent_name}"'))
        v_add = 4.0 * (v_boss_up if updown == "up" else v_boss_down)
        volume = await volume_check(
            adapter,
            f"bosses {updown}",
            volume + v_add,
            0.005 * v_add + 50.0,
        )

    # 7. Gooseneck hub: underside boss (extruded down 26.25 from the Top
    #    plane; the covered plan adds the 8 below the underside, the web
    #    setback slivers fill their full 26.25) ...
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
    check(
        "extrude hub boss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HALF_H + HUB_BOSS_DROP, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "HubBoss")
    hub_boss_extent_dim = name_dimensions(adapter, "HubBoss", ["HubBossExtent"])
    drive_jobs.append((hub_boss_extent_dim[0], '"HubBossExtent"'))
    v_hub_boss_add = _hub_boss_add_volume()
    volume = await volume_check(
        adapter, "hub boss", volume + v_hub_boss_add, 0.01 * v_hub_boss_add + 20.0
    )

    # ... and the twin V-gussets: one trapezoid on a Right-plane offset at
    # x -200.5 ((x, y) -> (Z, Y)), extruded 7 toward +X, feathering from
    # full drop at |z-3.088| <= 8 to the underside at |z-3.088| = 30. The
    # expected volume is the grid union with the boss minus the boss.
    v_hub_union = _hub_underhang_volume()
    gusset_plane = check(
        "create_plane hub gussets",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Right Plane",
                offset=GOOSENECK_X - HUB_GUSSET_T / 2.0,
            )
        ),
    )
    # Negative-offset plane: sketch x = -(model Z) (negative-offset plane mirror -- see the module docstring). The
    # trapezoid is authored mirrored so it lands centred on GOOSENECK_Z.
    gus_pts = [
        (-(GOOSENECK_Z - HUB_GUSSET_HALF_OUT), -HALF_H),
        (-(GOOSENECK_Z - HUB_GUSSET_HALF_IN), -HALF_H - HUB_BOSS_DROP),
        (-(GOOSENECK_Z + HUB_GUSSET_HALF_IN), -HALF_H - HUB_BOSS_DROP),
        (-(GOOSENECK_Z + HUB_GUSSET_HALF_OUT), -HALF_H),
    ]
    gus = SketchDims()
    check(
        "create_sketch hub gussets",
        await adapter.create_sketch(getattr(gusset_plane, "name", gusset_plane)),
    )
    ref_planes.append(str(getattr(gusset_plane, "name", gusset_plane)))
    gus_lines = await add_line_chain(adapter, gus_pts)
    await define_polygon_chain(
        adapter,
        gus_lines,
        gus_pts,
        anchor=0,
        label="hub gussets",
        dims=gus,
        names=[
            "GusAnchorZ",
            "GusAnchorY",
            "GusDropRun",
            "GusDrop",
            "GusFlat",
            "GusRiseRun",
            "GusRise",
        ],
    )
    await ensure_fully_defined(adapter, "hub gussets sketch")
    check("exit_sketch hub gussets", await adapter.exit_sketch())
    name_last_feature(adapter, "HubGussetProfile")
    drive_jobs += gus.apply(adapter, "HubGussetProfile")
    check(
        "extrude hub gussets",
        await adapter.create_extrusion(ExtrusionParameters(depth=HUB_GUSSET_T)),
    )
    name_last_feature(adapter, "HubGussets")
    v_gus_extra = v_hub_union - math.pi * (HUB_BOSS_DIA / 2.0) ** 2 * HUB_BOSS_DROP
    volume = await volume_check(
        adapter, "hub gussets", volume + v_gus_extra, 0.01 * v_gus_extra + 30.0
    )

    # 8. Set-screw cast pocket on the hub rib (east outer face, -X).
    pocket_plane = check(
        "create_plane set pocket",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=-OUTER_X
            )
        ),
    )
    pocket = SketchDims()
    check(
        "create_sketch set pocket",
        await adapter.create_sketch(getattr(pocket_plane, "name", pocket_plane)),
    )
    ref_planes.append(str(getattr(pocket_plane, "name", pocket_plane)))
    half_p = SET_POCKET / 2.0
    # Negative-offset plane: sketch x = -(model Z) (negative-offset plane mirror -- see the module docstring).
    pk_pts = [
        (-(GOOSENECK_Z - half_p), -half_p),
        (-(GOOSENECK_Z + half_p), -half_p),
        (-(GOOSENECK_Z + half_p), half_p),
        (-(GOOSENECK_Z - half_p), half_p),
    ]
    pk_lines = await add_line_chain(adapter, pk_pts)
    await define_rectilinear_chain(
        adapter,
        pk_lines,
        pk_pts,
        label="set pocket",
        dims=pocket,
        names=["PocketRun", "PocketRise", "PocketOffZ", "PocketOffY"],
    )
    await ensure_fully_defined(adapter, "set pocket sketch")
    check("exit_sketch set pocket", await adapter.exit_sketch())
    name_last_feature(adapter, "SetPocketProfile")
    pocket.apply(adapter, "SetPocketProfile")
    check(
        "cut set pocket",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SET_POCKET_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "SetScrewPocket")
    v_pocket = SET_POCKET * SET_POCKET * SET_POCKET_DEPTH
    volume = await volume_check(adapter, "set pocket", volume - v_pocket, 20.0)

    # 9. Side-screw spot-faces: O9 flats at |z|=132.6 on the curved boss
    #    (1.9 removal on axis; cut plane 134.9 gives a positive 2.3 depth).
    v_spot = _spotface_removal()
    for side, sign, reverse in SIDE_SCREW_FACES:
        spot_plane = check(
            f"create_plane spotface {side}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset",
                    base_plane="Front Plane",
                    offset=sign * SPOTFACE_PLANE,
                )
            ),
        )
        spot = SketchDims()
        check(
            f"create_sketch spotface {side}",
            await adapter.create_sketch(getattr(spot_plane, "name", spot_plane)),
        )
        ref_planes.append(str(getattr(spot_plane, "name", spot_plane)))
        for k, x in enumerate(SIDE_SCREW_XS):
            await define_circle(
                adapter,
                x,
                0.0,
                SPOTFACE_DIA / 2.0,
                f"spotface {side} (x={x:+.0f})",
                dims=spot,
                names=(f"S{k}X", None, f"S{k}Dia"),
            )
        await ensure_fully_defined(adapter, f"spotface {side} sketch")
        check(f"exit_sketch spotface {side}", await adapter.exit_sketch())
        name_last_feature(adapter, f"SpotFace{side.capitalize()}Profile")
        spot.apply(adapter, f"SpotFace{side.capitalize()}Profile")
        check(
            f"cut spotface {side}",
            await adapter.create_cut_extrude(
                ExtrusionParameters(
                    depth=SPOTFACE_PLANE - SPOTFACE_FLOOR, reverse_direction=reverse
                )
            ),
        )
        name_last_feature(adapter, f"SpotFace{side.capitalize()}")
        volume = await volume_check(
            adapter,
            f"spotface {side}",
            volume - len(SIDE_SCREW_XS) * v_spot,
            0.2 * v_spot + 15.0,
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

    # 12. Knife-hanger #6 SHCS counterbores, drilled from the crossbar top
    #     (one wizard feature, both stations). The rear counterbore reaches
    #     0.65 past the window face into the rail flange -- material
    #     continues, so each removal is a full clearance cylinder through the
    #     ring plus a full counterbore annulus either way.
    wizard_holes(
        adapter,
        HANGER_HOLE_SPEC,
        [[HANGER_X, HALF_H, STUD_Z_FRONT], [HANGER_X, HALF_H, STUD_Z_REAR]],
        (0.0, 1.0, 0.0),
        "knife-hanger counterbores",
        name="StudHoles",
        expect_dia_mm=HANGER_CLEARANCE_DIA,
        placement_dims=[
            (("StudFrontX", None), ("StudFrontZ", None)),
            (("StudRearX", None), ("StudRearZ", None)),
        ],
    )
    v_hangers = 2.0 * (
        math.pi * (HANGER_CLEARANCE_DIA / 2.0) ** 2 * RING_HEIGHT
        + math.pi
        * ((HANGER_CBORE_DIA / 2.0) ** 2 - (HANGER_CLEARANCE_DIA / 2.0) ** 2)
        * HANGER_CBORE_DEPTH
    )
    volume = await volume_check(
        adapter, "knife-hanger counterbores", volume - v_hangers, 10.0
    )

    # 12b. Round dowel slip holes: blind, flat-bottomed (a plain cut-extrude
    #      -- a wizard drill point would leave a cone where the reamer
    #      finishes), cut HangerPinHoleDepth up from the crossbar underside,
    #      HANGER_PIN_X +X of each screw axis. The rear circle owns the marked
    #      HangerPinHoleDia: section F-F cuts the rear station.
    pins = SketchDims()
    pin_centres = [(PIN_HOLE_X, -HALF_H, z) for z in (STUD_Z_FRONT, STUD_Z_REAR)]
    sketch_centres, u_is_x, normal_out = _open_underside_sketch(adapter, pin_centres)
    for (u, v), station, dia_name in zip(
        sketch_centres, ("Front", "Rear"), ("HangerPinHole1Dia", "HangerPinHoleDia")
    ):
        x_name, z_name = f"Pin{station}X", f"Pin{station}Z"
        await define_circle(
            adapter,
            u,
            v,
            HANGER_PIN_HOLE_DIA / 2.0,
            f"dowel slip hole ({station.lower()})",
            dims=pins,
            names=(x_name, z_name, dia_name) if u_is_x else (z_name, x_name, dia_name),
            drives=(None, None, '"HangerPinHoleDia"'),
        )
    await ensure_fully_defined(adapter, "dowel slip hole sketch")
    check("exit_sketch dowel slip holes", await adapter.exit_sketch())
    name_last_feature(adapter, "HangerPinProfile")
    drive_jobs += pins.apply(adapter, "HangerPinProfile")
    # A cut runs opposite the sketch normal unless reversed.
    check(
        "cut dowel slip holes",
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
    v_pins = 2.0 * math.pi * (HANGER_PIN_HOLE_DIA / 2.0) ** 2 * HANGER_PIN_HOLE_DEPTH
    volume = await volume_check(
        adapter, "dowel slip holes", volume - v_pins, 0.01 * v_pins
    )

    # 12c. Dowel slots, HANGER_PIN_X -X of each screw axis, as blind and
    #      flat-floored as the round holes: ONE closed stadium per slot (two
    #      straight sides HangerSlotLength - HangerSlotWidth long joined by
    #      two tangent half-round ends), so the cut takes each slot as one
    #      region.  Separate end circles 1.36 apart overlap, and SOLIDWORKS
    #      rejects a cut whose sketch contours intersect (farm run
    #      20261009T155421516Z: FeatureCut3 "Type mismatch").  The FRONT slot
    #      owns the marked HangerSlotWidth (the side-to-side distance) -- the
    #      underside locator carries it there, clear of F-F's cutting line
    #      along the rear station.  Section F-F cuts the rear slot along its
    #      length.
    slot_dims = SketchDims()
    mapped, u_is_x, normal_out = _open_underside_sketch(
        adapter, [(SLOT_X, -HALF_H, z) for z in (STUD_Z_FRONT, STUD_Z_REAR)]
    )
    half_flat, half_w = SLOT_FLAT / 2.0, HANGER_SLOT_WIDTH / 2.0
    for (u, v), station in zip(mapped, ("Front", "Rear"), strict=True):
        prefix = "HangerSlot" if station == "Front" else "HangerSlot1"
        where = station.lower()
        p1, p2, p3, p4, c_end_b, c_end_a = slot_stadium_points(
            (u, v), along_u=u_is_x, half_flat=half_flat, half_w=half_w
        )
        set_sketch_direct_db(adapter, True)
        side_a = check(f"dowel slot side a ({where})", await adapter.add_line(*p1, *p2))
        end_b = check(
            f"dowel slot end b ({where})", await adapter.add_arc(*c_end_b, *p2, *p3)
        )
        side_b = check(f"dowel slot side b ({where})", await adapter.add_line(*p3, *p4))
        end_a = check(
            f"dowel slot end a ({where})", await adapter.add_arc(*c_end_a, *p4, *p1)
        )
        set_sketch_direct_db(adapter, False)
        for join, a, b in (
            ("side a - end b", f"{side_a}.end", f"{end_b}.start"),
            ("end b - side b", f"{end_b}.end", f"{side_b}.start"),
            ("side b - end a", f"{side_b}.end", f"{end_a}.start"),
            ("end a - side a", f"{end_a}.end", f"{side_a}.start"),
        ):
            check(
                f"dowel slot {join} ({where})",
                await adapter.add_sketch_constraint(a, b, "coincident"),
            )
        along = "horizontal" if u_is_x else "vertical"
        for side in (side_a, side_b):
            check(
                f"dowel slot {side} {along} ({where})",
                await adapter.add_sketch_constraint(side, None, along),
            )
        # Tangency closes the shape: both ends' radii follow from the sides'
        # spacing, the far side's length from the near side's.
        for a, b in (
            (side_a, end_b),
            (end_b, side_b),
            (side_b, end_a),
            (end_a, side_a),
        ):
            check(
                f"dowel slot {a} tangent {b} ({where})",
                await adapter.add_sketch_constraint(a, b, "tangent"),
            )
        # Emission order: the width across the sides, the near side's
        # straight run, then end a's centre anchors.
        await dimension_between(
            adapter,
            f"{side_a}.start",
            f"{side_b}.end",
            "vertical_distance" if u_is_x else "horizontal_distance",
            HANGER_SLOT_WIDTH,
            f"dowel slot width ({where})",
        )
        slot_dims.record(f"{prefix}Width", '"HangerSlotWidth"')
        await dimension_between(
            adapter,
            f"{side_a}.start",
            f"{side_a}.end",
            "horizontal_distance" if u_is_x else "vertical_distance",
            SLOT_FLAT,
            f"dowel slot run ({where})",
        )
        slot_dims.record(f"{prefix}Flat", '"HangerSlotLength" - "HangerSlotWidth"')
        if min(abs(c_end_a[0]), abs(c_end_a[1])) < 1e-6:
            raise RuntimeError(
                f"dowel slot ({where}): end centre {c_end_a} on a sketch axis"
                " anchors with one dimension, not two"
            )
        await anchor_point_to_origin(
            adapter, f"{end_a}.center", *c_end_a, f"dowel slot end a ({where})"
        )
        for axis_name in ("X", "Z") if u_is_x else ("Z", "X"):
            slot_dims.record(f"Slot{station}{axis_name}")
    await ensure_fully_defined(adapter, "dowel slot sketch")
    check("exit_sketch dowel slots", await adapter.exit_sketch())
    name_last_feature(adapter, "HangerSlotProfile")
    drive_jobs += slot_dims.apply(adapter, "HangerSlotProfile")
    check(
        "cut dowel slots",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=HANGER_SLOT_DEPTH, reverse_direction=not normal_out
            )
        ),
    )
    name_last_feature(adapter, "HangerSlots")
    drive_jobs.append(
        (
            name_dimensions(adapter, "HangerSlots", ["HangerSlotDepth"])[0],
            '"HangerSlotDepth"',
        )
    )
    v_slots = len(HANGER_SLOT_CONTOURS) * HANGER_SLOT_AREA * HANGER_SLOT_DEPTH
    volume = await volume_check(
        adapter, "dowel slots", volume - v_slots, 0.01 * v_slots
    )

    # 13. Cross-screw taps (#10-32 UNF-2B bottoming): one per boss,
    #     46.0 mm full thread in a 49.2 mm cylindrical drill. Each path
    #     starts on its spot seat, crosses the near casting wall and column
    #     bore, then continues into the far boss/centred side-rail web.
    #     Opposed holes remain one two-position Hole Wizard feature per side.
    v_side_tap = _side_tap_removal()
    for side, sign, _reverse in SIDE_SCREW_FACES:
        feat = f"SideTaps{side.capitalize()}"
        z_face = sign * SPOTFACE_FLOOR
        normal = (0.0, 0.0, sign)
        tap_points = [[x, 0.0, z_face] for x in SIDE_SCREW_XS]
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

    v_set_tap = _set_tap_removal()
    wizard_holes(
        adapter,
        SET_TAP_SPEC,
        [[-(OUTER_X - SET_POCKET_DEPTH), 0.0, GOOSENECK_Z]],
        (-1.0, 0.0, 0.0),
        "gooseneck set-screw tap",
        name="GooseneckTap",
        placement_dims=[(("SetTapZ", None), (None, None))],
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
    #     each recessed web face meets the flange underside (y +10.25) --
    #     the cast root blend ch19 img04 shows on every panel. One edge
    #     per uninterrupted run: the hub rib splits both east-rail runs,
    #     the junction lands split both front/rear window runs. The web
    #     ring's BOTTOM rim stays sharp (no low-side breaks).
    x_shelf_out = COLUMN_X + WEB_T / 2.0  # 203.5
    x_shelf_in = COLUMN_X - WEB_T / 2.0  # 190.5
    z_shelf_out = abs(FRONT_COLUMN_Z) + WEB_T / 2.0  # 118.5
    z_shelf_in = abs(FRONT_COLUMN_Z) - WEB_T / 2.0  # 105.5
    rib_lo = GOOSENECK_Z - HUB_RIB_W / 2.0  # -10.41
    rib_hi = GOOSENECK_Z + HUB_RIB_W / 2.0  # +16.59
    root_cut = math.sqrt((BOSS_DIA / 2.0) ** 2 - (WEB_T / 2.0) ** 2)
    east_mid_lo = (-abs(FRONT_COLUMN_Z) + root_cut + rib_lo) / 2.0
    east_mid_hi = (rib_hi + abs(FRONT_COLUMN_Z) - root_cut) / 2.0
    land_mid_w = (LAND_X0 - COLUMN_X + root_cut) / 2.0
    land_mid_e = (LAND_X1 + COLUMN_X - root_cut) / 2.0
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
            ],
        ),
    )
    name_last_feature(adapter, "TRootFillets")
    v_root = _t_root_add()
    volume = await volume_check(
        adapter, "T-root fillets", volume + v_root, 0.03 * v_root + 80.0
    )

    # 17. External top-face rim breaks: C2 x 45 on the outer rail rim and
    #     both windows' rims. The Ø45 bosses no longer reach the rail plan
    #     corners: window rims meet at real square corners, and each outer
    #     corner has two short rim edges outside the boss barrel. Select
    #     those eight edges explicitly as well as the four central runs.
    v_outer, v_window = _top_rim_removal()
    outer_corner_edges = _outer_corner_top_edges()
    check(
        "chamfer top rims",
        await adapter.add_chamfer(
            EDGE_CHAMFER,
            [
                [OUTER_X, HALF_H, 0.0],
                [-OUTER_X, HALF_H, 0.0],
                [0.0, HALF_H, OUTER_Z],
                [0.0, HALF_H, -OUTER_Z],
                [-INNER_X, HALF_H, 0.0],
                [INNER_X, HALF_H, 0.0],
                [BAR_X0, HALF_H, 0.0],
                [BAR_X1, HALF_H, 0.0],
                # front/rear inner-face runs, east + west of the crossbar
                [-(abs(BAR_X0) + GUSSET + INNER_X) / 2.0, HALF_H, INNER_Z],
                [-(abs(BAR_X0) + GUSSET + INNER_X) / 2.0, HALF_H, -INNER_Z],
                [(BAR_X1 + GUSSET + INNER_X) / 2.0, HALF_H, INNER_Z],
                [(BAR_X1 + GUSSET + INNER_X) / 2.0, HALF_H, -INNER_Z],
                # gusset hypotenuse midpoints
                [BAR_X0 - GUSSET / 2.0, HALF_H, INNER_Z - GUSSET / 2.0],
                [BAR_X0 - GUSSET / 2.0, HALF_H, -(INNER_Z - GUSSET / 2.0)],
                [BAR_X1 + GUSSET / 2.0, HALF_H, INNER_Z - GUSSET / 2.0],
                [BAR_X1 + GUSSET / 2.0, HALF_H, -(INNER_Z - GUSSET / 2.0)],
            ]
            + outer_corner_edges,
        ),
    )
    name_last_feature(adapter, "TopRimBreaks")
    v_rims = v_outer + v_window
    volume = await volume_check(
        adapter, "top rim breaks", volume - v_rims, 0.03 * v_rims + 100.0
    )

    # 18. C1 x 45 lead-ins on the four cap-recess mouths and gooseneck bore
    # top. Boss undersides remain sharp.
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

    # 19. Machined keeper-seat regions on the unchanged rail-top plane.
    # Split boundaries, not a cut or raised pad: volume and all stacks stay fixed.
    await _split_keeper_seats(adapter)
    volume = await volume_check(
        adapter, "keeper seat split (no material change)", volume, 0.05
    )

    # Deferred drive equations: after the whole model + a rebuild exist so
    # every target resolves; the re-check proves the equations are neutral.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    for recess_dia_name in (
        "CapRecessDia",
        "CapRecess1Dia",
        "CapRecess2Dia",
        "CapRecess3Dia",
    ):
        set_dimension_bilateral_tolerance(
            adapter,
            "CapRecessProfile",
            recess_dia_name,
            *deviations(CAP_RECESS_DIAMETER_BAND),
        )
    set_dimension_bilateral_tolerance(
        adapter,
        "CapRecesses",
        "CapRecessDepth",
        *deviations(CAP_RECESS_DEPTH_BAND),
    )
    for pin_dia_name in ("HangerPinHoleDia", "HangerPinHole1Dia"):
        set_dimension_bilateral_tolerance(
            adapter,
            "HangerPinProfile",
            pin_dia_name,
            *deviations(HANGER_PIN_HOLE_DIA_BAND),
        )
    for slot_width_name in ("HangerSlotWidth", "HangerSlot1Width"):
        set_dimension_bilateral_tolerance(
            adapter,
            "HangerSlotProfile",
            slot_width_name,
            *deviations(HANGER_SLOT_WIDTH_BAND),
        )
    await volume_check(adapter, "driven casting (equations neutral)", volume, 200.0)

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
    # single place a place count is authored (drawing-simplicity rule 2).
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    _qualify_machined_faces(adapter)
    _qualify_keeper_seat_faces(adapter)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Manufacturing Notes B": DRAWING_NOTES_B,
        },
    )
    # The print opens on two octant pictorials (front-top-left, front-bottom-
    # right) to prime the reader before the orthographic sheets; all eight are
    # named here so any print of this part can place any of them by name.
    name_octant_views(adapter, label=PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
