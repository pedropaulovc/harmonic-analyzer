r"""Reproduction script: top frame casting (2026-08-02 rederive; 1 used).

ONE green cast iron piece that absorbed the old separate top-crossbar
(full-height integral bar) and gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side). Derived from the ch30 eight views (px
measurement anchored on the 394 x 224 column pitch), the GT bundle solve
rescaled onto the model column grid, and ch19 close-ups (webbing, hub, screw):

* All-inch experiment: every independent length is an inch fraction
  (fr_top_frame_spec / constants below carry the old mm values).
* Rail band y 999.33125..1035.84375 (H 1-7/16; the boss top stands 3/16
  above the rail top). Assembly inserts the part at ring mid-plane
  TOP_FRAME_MID_Y = TOP_SCREW_Y = 1017.5875.
* Side rails (along Z at x +/-196.85) 1-3/8 wide -> outer faces x
  +/-214.31, window x +/-179.39. Front/rear rails (along X at z
  -/+112.71) 1-1/2 wide -> outer faces z -/+131.76, window z -/+93.66.
* Corner bosses O1-3/4 spanning y 992.98..1040.61 (proud 3/16 above the
  rail top, hanging 1/4 below the underside). All four upper/lower bosses
  use the smaller user-ruled diameter so the outward keeper feet sit flat.
  The O25.5 column bores and O27.5 cap recesses (vendor fits) stay. Four
  stock 1-3/4 in cross screws seat flush in front/rear O3/8 counterbores
  and clear both tube walls into the far casting wall/web through #10-32
  taps.
* The whole side-rail TOP FLANGE top of the keeper rail, between its two
  corner bosses, is faced flat within the keeper-owned 0.04 zone at the
  Ra 3.2 locating-seat finish (user ruling 2026-10-11), so both keeper feet
  land on one face wherever fit-up puts them. The nominal rail-top plane
  stays fixed; the B-B top flange thickness (TYP, .X, 5/16) is the
  finished flange under it.
* Integral crossbar 1 in wide centred on the knife line x -15.0 spanning
  the window along Z, flush with BOTH faces at its junctions (the faced
  underside 999.33 is the knife-mount seat plane), with 11/16 x 11/16 plan
  gussets at all four rail junctions and, at z 3.088 -/+ 87.3125, a #10
  loose through-hole with a washer spotface per knife mount. The
  cut-to-length #10-24 hex bolt bears on a 96659A104 washer; the unchanged
  98381A473 dowel slips into the blind underside hole/slot. Over its middle
  (pocket length 5-7/16, short of the knife-mount seats) the bar is a T
  like the rails: the 1 in wide, 5/16-tall top flange over a 17/32 web
  centred on the knife line through the underside, with R1/8 roots.
* Every face on the underside plane between the bosses -- rail web
  bottoms, junction lands, plan gussets and the crossbar's full-depth ends
  under both knife mounts -- is faced at the Ra 3.2 seat finish (user
  ruling 2026-10-12, one linked manufacturing note); the corner-boss
  bottoms 1/4 below it and the hub boss and V-gussets 5/16 below stay off
  it. The underside is the FINISHED plane: the cut comes out of casting allowance,
  so the model, its bands and every stack read from it unchanged. It is
  faced first. The #10 clearance holes are drilled through from it (Q7
  option C); the slip holes and slots are cut blind from it and located
  from each #10 hole's axis there (sheet 6
  dimensions them in the underside view). Each axis is therefore true at
  the knife-mount seat and its drift grows toward the top. The frame is
  then turned over and each washer spotface is cut from the top, piloted
  on its drilled hole (sheet 3 states both entries). The native spotfloor
  grip is 1-3/8 +/-0.05 from the FINISHED underside, not from the cast top:
  HangerGrip, a driving dimension in the hidden HangerGripReference sketch,
  sets the spotface wizard's depth ("RingHeight" - HangerGrip) and carries
  the band the sheet imports.
  Datum D on the native crossbar width establishes BOTH-face median plane;
  the hanger axes' linear position zone centres them within +/-0.05 of it.
* Gooseneck hub on the east rail (-X) at z +3.088: full-height rib 1-1/8
  wide, 43/64 clearance bore for the 5/8 counter-spring post, underside
  boss O1-3/16 x 5/16 with twin V-gussets (ch30 p004), a square-sided cast
  boss under the top flange on the rib's outer face (ch19 img04; user
  ruling 2026-10-12), spot-faced 27/32 from the bore axis, and a 1/4-20
  tap from the spot face to the bore for the square-head set screw (book
  p.45: "a square-head screw pinches the post in its socket").
* Webbed faces (T-rail section): a 5/16-tall full-thickness top flange,
  then the web thins to 17/32 centred on each rail and STAYS thin through
  the bottom edge. The former photo-read 12.7 web is thickened for the keeper
  receivers' printed-band plus drill-wander stack; full-thickness lands remain
  at the bosses, hub rib and crossbar junctions.
* Finishing (chamfer external, fillet internal): R1/8 cast fillets along
  the internal web/flange T-roots (both shelves of every rail and the
  crossbar web, ch19 img04's panel blends), 1/16 x 45 breaks (the "C2"
  family) on the top-face rims -- outer rail rim and both window rims --
  then the same break on every other external convex edge (flange
  undersides, web bottoms, lands, crossbar, hub rib, boss rims), and 1/32
  x 45 lead-ins (the "C1" family) on the bore TOP ends only. The R7/8
  bosses bulge beyond the side and front/rear rails, but do not reach the
  plan corners: window corners and short outer-corner rim runs remain.
  Edges too short, too close to a feature or under a knife-mount seat for
  C2 stay sharp (listed in _external_edge_breaks); hole and bore low ends
  stay sharp.

Layout: plan profile in XZ, ring mid-plane extruded symmetrically in Y
(rails y -18.25..+18.25 local). Sketches on the Top plane use the
(x, y) -> (X, -Z) handedness; sketches on Right-plane offsets map
(x, y) -> (Z, Y) (build_fr_rocker_arm_support precedent; NEGATIVE-offset
planes mirror sketch x -- see the gusset/boss sites). Build order
(ADDITIVE T-section -- the web/flange rings are extruded, not pocketed):
web ring -> crossbar junction lands -> top-flange ring -> hub rib
restore -> crossbar+gussets -> crossbar T pockets -> corner bosses
(up/down pair) -> hub boss + V-gussets -> set-screw boss + spot face ->
counterbores -> column bores -> gooseneck bore -> wizard holes (#10 loose
hanger holes / washer spotfaces) -> HangerGrip reference -> dowel slip
holes -> wizard holes (side-screw
taps, set-screw tap, keeper taps) -> internal T-root fillets (R3) ->
external top-rim breaks (C2) -> C1 bore top lead-ins -> remaining
external edge breaks (C2, one feature per connected chain: rail runs,
crossbar, west window, hub rail, outer corners, boss rims).
Wizard holes come after the face cuts so every seat face is final; the
edge breaks follow the solid features.
Analytic volume checks after every feature; boss additions and top-rim
breaks use circle-segment formulas, the remaining edge breaks sum
per-edge chamfer sections, while hub/counterbore/tap expectations
use small grid integrals against the webbed solid.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fr_top_frame.py
"""

from __future__ import annotations

import math
import sys

from _appearance import CASTING_GREEN, apply_color, apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _inch import inch
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
from _sketch_rectangle import define_centered_rectangle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    _set_tolerance_precision,
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
    FLANGE_THICKNESS_MM,
    FLANGE_THICKNESS_PLACES,
    HANGER_CROSSBAR_WIDTH,
    HANGER_CROSSBAR_WIDTH_PLACES,
    HANGER_CROSSBAR_CENTER_TOL,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    HALF_H,
    HUB_SET_BOSS_FROM_AXIS,
    HUB_SET_BOSS_W,
    HUB_SET_SPOT_DIA,
    HUB_SET_SPOT_FROM_AXIS,
    HANGER_SPOTFACE_DEPTH,
    HANGER_SPOTFACE_DIA,
    HANGER_SPOTFACE_DIA_MIN,
    HANGER_SPOTFACE_DIA_MAX,
    HANGER_WASHER,
    HANGER_WASHER_FLOAT_MAX,
    HANGER_WASHER_CONCENTRIC_ANNULUS_MIN,
    HANGER_CLEARANCE_DIA,
    HANGER_CLEARANCE_DIA_MAX,
    HANGER_CLEARANCE_DIA_BAND,
    HANGER_CLEARANCE_DIA_PLACES,
    HANGER_GRIP,
    HANGER_GRIP_TOL,
    HANGER_GRIP_SKETCH,
    HANGER_HOLE_SPEC,
    HANGER_PIN_HOLE_DEPTH,
    HANGER_PIN_HOLE_DEPTH_PLACES,
    HANGER_PIN_HOLE_DIA,
    HANGER_PIN_HOLE_DIA_BAND,
    HANGER_PIN_X_TOL,
    HANGER_SLOT_POSITION_TOL,
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
    DRILL_DRIFT_PER_MM,
    PRINTED_DRILLED_HOLE_PLUS_MM,
    PRINTED_LINEAR_BAND_MM,
    HANGER_PIN_SLIP_CLEARANCE_MAX,
    REAR_COLUMN_Z,
    REFERENCE_SKETCHES,
    SET_SCREW_THREAD,
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
    TOP_SCREW_COUNTERBORE_DIAMETER,
    TOP_SCREW_SEAT_Z,
)
from _fit_deviations import deviations
from vn_tube_frame_cap_spec import MAX_OUTER_DIAMETER as CAP_MAX_OUTER_DIAMETER
import sm_knife_mount_spec as KNIFE_MOUNT
from _printed_tolerance import angular_band_deg
from vn_frame_side_screw_spec import SHANK_DIA as KEEPER_SCREW_MAJOR_DIA
from _mcmaster_90280a837 import (
    HEAD_DIA as CROSS_SCREW_HEAD_DIA,
    HEAD_H as CROSS_SCREW_HEAD_H,
)
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

# Side rails, along Z (GT corner rescale 221.5 -> 214.1).
RAIL_W_SIDE = inch(1.375)  # 34.925 (was 34.2)
# Front/rear rails, along X (GT z-corner rescale 137.4 -> 131).
RAIL_W_FR = inch(1.5)  # 38.1 (was 38.0)

BOSS_BELOW = inch(1, 4)  # 6.35 (was 6.3): boss hang below the underside (p006 5.7-7)
CAP_RECESS_DIAMETER_BAND = (0.20, 0.0)
CAP_RECESS_DEPTH_BAND = (0.30, 0.0)
CAP_RECESS_DIAMETRAL_CLEARANCE = CAP_RECESS_DIAMETER - CAP_MAX_OUTER_DIAMETER
if CAP_RECESS_DIAMETRAL_CLEARANCE <= 0.0:
    raise AssertionError("purchased cap does not clear the top-frame recess")

OUTER_X = COLUMN_X + RAIL_W_SIDE / 2.0  # 214.3125
INNER_X = COLUMN_X - RAIL_W_SIDE / 2.0  # 179.3875
OUTER_Z = abs(FRONT_COLUMN_Z) + RAIL_W_FR / 2.0  # 131.7625
INNER_Z = abs(FRONT_COLUMN_Z) - RAIL_W_FR / 2.0  # 93.6625

# --- Integral crossbar (old top-crossbar, merged) ---------------------------
# The crossbar centreline is the KNIFE x, restated from the summing knife
# station (build_sm_summing_assembly; spring-calibration station, exempt).
HANGER_X = -15.0
BAR_X0, BAR_X1 = (
    HANGER_X - HANGER_CROSSBAR_WIDTH / 2.0,
    HANGER_X + HANGER_CROSSBAR_WIDTH / 2.0,
)
GUSSET = inch(11, 16)  # 17.4625 (was 18.0): plan gusset legs at the rail junctions
# Knife-mount trunnion mid offset, restated from build_sm_summing_assembly.
HEX_Z_MID = inch(55, 16)  # 3-7/16 = 87.3125 (was 87.06)
STUD_Z_FRONT = SUMMING_Z - HEX_Z_MID  # -84.225
STUD_Z_REAR = SUMMING_Z + HEX_Z_MID  # +90.400
PIN_HOLE_X = HANGER_X + HANGER_ROUND_X  # round dowel slip holes, +X
SLOT_X = HANGER_X + HANGER_SLOT_X  # dowel slots, -X of the bolt
SLOT_FLAT = HANGER_SLOT_LENGTH - HANGER_SLOT_WIDTH  # 0.71: straight run
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
HUB_RIB_W = inch(1.125)  # 28.575 (was 28.0): full-height rib band across the east rail
HUB_BOSS_DIA = inch(19, 16)  # 30.1625 (was 30.0): underside boss around the bore exit
HUB_BOSS_DROP = inch(5, 16)  # 7.9375 (was 8.0): boss bottom local -26.19375
HUB_GUSSET_T = inch(1, 4)  # 6.35 (was 7.0): V-gusset thickness along X
HUB_GUSSET_HALF_IN = inch(5, 16)  # 7.9375 (was 8.0): full-depth |z - GooseneckZ|
HUB_GUSSET_HALF_OUT = inch(19, 16)  # 30.1625 (was 30.0): feathers to the underside
# Set-screw boss (fr_top_frame_spec): its cast face and its spot face, as
# model X on the east side.
SET_BOSS_FACE_X = GOOSENECK_X - HUB_SET_BOSS_FROM_AXIS  # -219.225
SET_SPOT_FACE_X = GOOSENECK_X - HUB_SET_SPOT_FROM_AXIS  # -218.43125
# The tap opens into the gooseneck bore; it has no blind thread-depth limit.
SET_TAP_SPEC = HoleSpec("tapped", SET_SCREW_THREAD, end="through_next")

# --- Cross screws (frame -> tube-frame columns -> far casting wall) ----------
# Flush counterbores: the O3/8 cut starts 0.4 outside the boss crown and stops
# at the screw seat, deep enough that the stock fillister head sits below
# the mouth's lowest barrel point (guards below).
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
if CAP_RECESS_FLOOR_Y - SIDE_TAP_DRILL_DIA / 2.0 <= 0.0:
    raise AssertionError("cap recess breaks into the cross-screw drill")

# --- Fulcrum keepers (west rail top face; shaft-end brackets, ch17 p.40) ----
# The keeper's pure spec owns both screw station and receiver geometry:
# #2-56 with 7.6 full thread and 11.5 drill retains a five-pitch plug
# lead at the sheet's general .X depth band. No assembly recipe dependency.
KEEPER_TAP_X = COLUMN_X + KEEPER_FITUP_X_FROM_WEB_MM  # nominal fulcrum line
KEEPER_TAP_Z_FRONT = FULCRUM_KEEPER_CENTRE_Z - KEEPER_SCREW_Z_OFF  # -83.054
KEEPER_TAP_Z_REAR = FULCRUM_KEEPER_CENTRE_Z + KEEPER_SCREW_Z_OFF  # +82.046

# --- Webbing ----------------------------------------------------------------
# T-rail section (user-corrected vs ch19 img04): an 8-tall full-thickness top
# flange, below which the web thins to WEB_T centred on each rail's centreline
# and STAYS thin through the bottom edge (no bottom flange). Built ADDITIVELY:
# a full-height thin web ring + an 8-tall full-width flange ring (two
# nested-rectangle sketches), plus full-thickness restore pads at the hub rib
# and the crossbar junctions. The corner bosses supply the corner lands. The
# per-face setback differs by rail family (the rails are 1-3/8 / 1-1/2 wide
# but share one web thickness).
FLANGE = FLANGE_THICKNESS_MM  # final top flange, also below the faced rail top
# User ruling: retain loose bands plus realistic deep-drill wander. 17/32
# (1/32): the 1/2 web leaves the keeper receiver under its 1.5 wall.
WEB_T = inch(17, 32)  # 13.49375 (was 13.0)
RECESS_SIDE = (RAIL_W_SIDE - WEB_T) / 2.0  # 10.715625 setback per side-rail face
RECESS_FR = (RAIL_W_FR - WEB_T) / 2.0  # 12.303125 setback per front/rear-rail face
FLANGE_BOT_Y = RING_HEIGHT / 2.0 - FLANGE  # +10.31875 (flange underside)
WEB_OUT_X = COLUMN_X + WEB_T / 2.0  # 203.596875
WEB_IN_X = COLUMN_X - WEB_T / 2.0  # 190.103125
WEB_OUT_Z = abs(FRONT_COLUMN_Z) + WEB_T / 2.0  # 119.459375
WEB_IN_Z = abs(FRONT_COLUMN_Z) - WEB_T / 2.0  # 105.965625
LAND_MARGIN = inch(1, 4)  # 6.35 (was 6.0): land pad beyond each gusset leg
LAND_X0 = BAR_X0 - GUSSET - LAND_MARGIN  # -51.59375; crossbar junction land pads
LAND_X1 = BAR_X1 + GUSSET + LAND_MARGIN  # +21.43125; front/rear inner faces
# Crossbar T-section: over the middle of the bar (|z| <= BAR_POCKET_Z) the
# crossbar keeps its 1 in wide, FLANGE-tall top flange and below it thins to a
# WEB_T web centred on the knife line, through the underside. Two flanking
# pockets cut it out of the full-height bar; they stop short of the gusset
# legs so the full-depth ends, which carry every hanger hole, keep
# the whole knife-mount top seat clear of the pocket-end C2 breaks.
BAR_WEB_X0 = HANGER_X - WEB_T / 2.0  # -21.828125
BAR_WEB_X1 = HANGER_X + WEB_T / 2.0  # -8.334375
# Pocket length 5-7/16 = 138.1125 (was 138.0), centred on the crossbar.
BAR_POCKET_Z = inch(87, 32)  # half-length 69.05625 (was 69.0)

THROUGH_CUT_DEPTH = 110.0  # mid-plane total; > boss stack (47.3)

# --- Edge finishing ----------------------------------------------------------
# Convention (2026-08-03): CHAMFER external edges, FILLET internal wall
# junctions. User ruling: C2 x 45 on EVERY external convex edge, top and
# bottom, except where an edge cannot take it (_external_edge_breaks).
# Internal web/flange T-root blends (cast root, ch19 img04).
ROOT_FILLET_R = inch(1, 8)  # 3.175 (was 3.0)
# External edge breaks, 45 deg (one grinding pass): 1/16 = 1.5875 (was 2.0).
EDGE_CHAMFER = inch(1, 16)
# Least land two separate C2 features may leave between their faces.
C2_SLIVER_MIN = 0.1
# Print-worst reach of a finished C2 band into the underside: the edge off
# its nominal by two .X bands (as the pocket end) and the whole-mm note's
# leg at the loosest printed row.
_EDGE_LOCATION_BAND = 2.0 * PRINTED_LINEAR_BAND_MM[1]
_C2_LEG_BAND = PRINTED_LINEAR_BAND_MM[1]
KNIFE_SEAT_C2_MIN_CLEARANCE = 0.5
# Note 9: TOP-end bore breaks; low ends stay sharp. 1/32 (was 1.0): the
# 1/16 grid would grow this sub-1/4 break by 59%.
BORE_CHAMFER = inch(1, 32)  # 0.79375
# The set boss's spot face keeps a land inside its cast face's C2 breaks at
# the print-worst corner (drawing-guidelines.md rule 17 (walls and webs)): the shallowest spot (its .X station
# against the cast face) leaves the most of each break's leg, at its loosest
# row, on the spot's floor; the widest .X spot then stands that far inside
# the narrowest .X boss and, up the boss, under the flange underside with the
# 18.2 tap axis high and the 8.0 flange thick.  The O12 spot's 0.4 breakout
# (local codex review of 4faacfab) is what this rejects.
_SET_SPOT_BREAK_REACH = (
    EDGE_CHAMFER
    + _C2_LEG_BAND
    - (HUB_SET_BOSS_FROM_AXIS - HUB_SET_SPOT_FROM_AXIS - PRINTED_LINEAR_BAND_MM[1])
)  # 2.6
_SET_SPOT_R_MAX = (HUB_SET_SPOT_DIA + PRINTED_LINEAR_BAND_MM[1]) / 2.0  # 5.4
SET_SPOT_LAND_MIN = {
    "across the boss": (HUB_SET_BOSS_W - PRINTED_LINEAR_BAND_MM[1]) / 2.0
    - _SET_SPOT_BREAK_REACH
    - _SET_SPOT_R_MAX,  # 0.6
    "under the flange": (HALF_H - PRINTED_LINEAR_BAND_MM[1])
    - (FLANGE + PRINTED_LINEAR_BAND_MM[1])
    - _SET_SPOT_BREAK_REACH
    - _SET_SPOT_R_MAX,  # 0.65
}
for _label, _land in SET_SPOT_LAND_MIN.items():
    if _land < C2_SLIVER_MIN:
        raise AssertionError(
            f"set-screw spot face breaks into the boss C2 {_label}: land {_land:.3f}"
        )

if abs(FRONT_COLUMN_Z + REAR_COLUMN_Z) > 1e-12 or abs(FRAME_CENTER_Z) > 1e-12:
    raise AssertionError("top-frame assumes a symmetric column span about z 0")
if STUD_Z_REAR + HANGER_SPOTFACE_DIA_MAX / 2.0 >= INNER_Z + GUSSET:
    raise AssertionError("rear hanger spotface escapes the junction material")
# Dowel slip holes and slots (drawing-guidelines.md rule 17 (walls and webs),
# print-worst): the largest reamed hole
# and the longest slot keep a wall to the crossbar's +X / -X face and to the
# largest drilled screw clearance hole with the round hole's station at its
# .XXX limit and the slot's at that plus its own .XXX from the round hole
# (0.26); their blind floors stay below the spotface floor, so neither
# meets the washer seat. The #10 holes are drilled from the faced underside
# and the dowel holes/slots cut from it. Every hole's drift is greatest at
# the deepest printed blind floor; charge both axes toward each other.
_PIN_HOLE_MAX_R = (HANGER_PIN_HOLE_DIA + max(HANGER_PIN_HOLE_DIA_BAND)) / 2.0
_CLEARANCE_MAX_R = HANGER_CLEARANCE_DIA_MAX / 2.0
_SLOT_MAX_HALF_L = (HANGER_SLOT_LENGTH + HANGER_SLOT_LENGTH_TOL) / 2.0
# Holes and slots floor at one height (HANGER_SLOT_DEPTH is the hole's).
_SLIP_FLOOR_DEPTH_MAX = (
    HANGER_PIN_HOLE_DEPTH + PRINTED_LINEAR_BAND_MM[HANGER_PIN_HOLE_DEPTH_PLACES]
)  # 12.8
HANGER_DRIFT_AT_SLIP_FLOOR = DRILL_DRIFT_PER_MM * _SLIP_FLOOR_DEPTH_MAX  # 0.067
# Datum D is the median plane of BOTH printed crossbar side faces. The
# native 0.10 linear position zone centres the two bolt axes on it; dowel
# locations are relative to those axes. Thus the socket-to-bar and
# socket-to-hanger X bands share this functional centre, not independent
# wall losses. Only half the actual width band and the 0.05 centring remain.
HANGER_BAR_HALF_WIDTH_MIN = (
    (BAR_X1 - BAR_X0) - PRINTED_LINEAR_BAND_MM[HANGER_CROSSBAR_WIDTH_PLACES]
) / 2.0
PIN_HOLE_BAR_WALL = (
    HANGER_BAR_HALF_WIDTH_MIN
    - HANGER_CROSSBAR_CENTER_TOL
    - HANGER_ROUND_X
    - HANGER_PIN_X_TOL
    - _PIN_HOLE_MAX_R
    - HANGER_DRIFT_AT_SLIP_FLOOR
)
PIN_HOLE_SCREW_WALL = (
    HANGER_ROUND_X
    - HANGER_PIN_X_TOL
    - _PIN_HOLE_MAX_R
    - _CLEARANCE_MAX_R
    - 2.0 * HANGER_DRIFT_AT_SLIP_FLOOR
)
SLOT_BAR_WALL = (
    HANGER_BAR_HALF_WIDTH_MIN
    - HANGER_CROSSBAR_CENTER_TOL
    + HANGER_SLOT_X
    - HANGER_SLOT_STATION_TOL
    - _SLOT_MAX_HALF_L
    - HANGER_DRIFT_AT_SLIP_FLOOR
)
SLOT_SCREW_WALL = (
    -HANGER_SLOT_X
    - HANGER_SLOT_STATION_TOL
    - _SLOT_MAX_HALF_L
    - _CLEARANCE_MAX_R
    - 2.0 * HANGER_DRIFT_AT_SLIP_FLOOR
)
PIN_HOLE_FLOOR_MARGIN = HANGER_GRIP - HANGER_GRIP_TOL - _SLIP_FLOOR_DEPTH_MAX
SLOT_FLOOR_MARGIN = PIN_HOLE_FLOOR_MARGIN
for _label, _value in (
    ("hole wall to the crossbar +X face", PIN_HOLE_BAR_WALL),
    ("hole wall to the screw clearance hole", PIN_HOLE_SCREW_WALL),
    ("slot wall to the crossbar -X face", SLOT_BAR_WALL),
    ("slot wall to the screw clearance hole", SLOT_SCREW_WALL),
):
    if _value < 2.0:
        raise AssertionError(
            f"knife-mount dowel slip {_label}: {_value:.3f} after drill drift"
        )
for _label, _value in (
    ("hole floor below the spotface floor", PIN_HOLE_FLOOR_MARGIN),
    ("slot floor below the spotface floor", SLOT_FLOOR_MARGIN),
):
    if _value < 2.0:
        raise AssertionError(f"knife-mount dowel slip {_label}: {_value:.3f}")
# Crossbar pockets (drawing-guidelines.md rule 17 (walls and webs), print-worst): every hanger hole stays in the
# full-depth junction beyond the pocket end. The nearer (front) station
# keeps its wall in z with the station at its .X band from the socket axis,
# each pocket end a full band of its printed .X length out (the length's
# band, then as much again for the pocket's centring), the largest printed
# hole and the 0.3 deg drill drift from the faced underside. The through
# hole's longest path to the highest pocket roof is charged; the top
# spotface is piloted on the hole after its full as-cast-height drift.
_POCKET_STATION = min(abs(STUD_Z_FRONT), abs(STUD_Z_REAR)) - PRINTED_LINEAR_BAND_MM[1]
_POCKET_LENGTH_PLACES = DRAWING_REFERENCE_PRECISION["crossbar pocket length"]
_POCKET_END = (
    round(2.0 * BAR_POCKET_Z, _POCKET_LENGTH_PLACES) / 2.0
    + 2.0 * PRINTED_LINEAR_BAND_MM[_POCKET_LENGTH_PLACES]
)  # 70.65625
HANGER_DRIFT_AT_TOP = DRILL_DRIFT_PER_MM * (RING_HEIGHT + PRINTED_LINEAR_BAND_MM[1])
HANGER_SPOTFACE_BAR_WALL = (
    HANGER_BAR_HALF_WIDTH_MIN
    - HANGER_CROSSBAR_CENTER_TOL
    - HANGER_SPOTFACE_DIA_MAX / 2.0
    - HANGER_DRIFT_AT_TOP
)
# Fore/aft outer rail faces: charge the half-width band and, conservatively,
# the full socket-pitch band for the far face measured from the upper socket.
_FR_RAIL_HALF_WIDTH_MIN = (
    RAIL_W_FR
    - PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["front rear flange width"]]
) / 2.0
_HANGER_Z_RADIAL_ENVELOPE = (
    PRINTED_LINEAR_BAND_MM[1] + HANGER_SPOTFACE_DIA_MAX / 2.0 + HANGER_DRIFT_AT_TOP
)
_HANGER_SPOTFACE_FRONT_END_WALL = min(
    station - FRONT_COLUMN_Z + _FR_RAIL_HALF_WIDTH_MIN - _HANGER_Z_RADIAL_ENVELOPE
    for station in (STUD_Z_FRONT, STUD_Z_REAR)
)
HANGER_SPOTFACE_OUTER_END_WALL = min(
    _HANGER_SPOTFACE_FRONT_END_WALL,
    *(
        REAR_COLUMN_Z
        - station
        + _FR_RAIL_HALF_WIDTH_MIN
        - PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["socket vertical pitch"]]
        - _HANGER_Z_RADIAL_ENVELOPE
        for station in (STUD_Z_FRONT, STUD_Z_REAR)
    ),
)
# The blind dowels overlap the spotface in plan only; the axial floor web
# above them is proven separately. The pockets also stay below the seat.
HANGER_SPOTFACE_POCKET_ROOF_WEB = (
    HANGER_GRIP
    - HANGER_GRIP_TOL
    - (
        RING_HEIGHT
        + PRINTED_LINEAR_BAND_MM[1]
        - (FLANGE - PRINTED_LINEAR_BAND_MM[FLANGE_THICKNESS_PLACES])
    )
)
# Match the assembly's tap/dowel mismatch without importing a COM recipe.
_HANGER_PAIR_SHIFT = HANGER_PIN_SLIP_CLEARANCE_MAX + HANGER_SLOT_POSITION_TOL / 2.0
HANGER_SEAT_BOLT_MISMATCH = math.hypot(
    HANGER_PIN_X_TOL
    + KNIFE_MOUNT.PIN_HOLE_HALF_SPAN_TOL
    + KNIFE_MOUNT.STUD_TAP_POSITION_TOL / 2.0
    + HANGER_PIN_SLIP_CLEARANCE_MAX / 2.0,
    HANGER_PIN_X_TOL
    + KNIFE_MOUNT.STUD_TAP_POSITION_TOL / 2.0
    + _HANGER_PAIR_SHIFT / 2.0,
)
HANGER_SPOTFACE_WASHER_OFFSET_MAX = (
    HANGER_WASHER_FLOAT_MAX
    + HANGER_SEAT_BOLT_MISMATCH
    + HANGER_DRIFT_AT_TOP
    + HANGER_WASHER.OD_ID_RUNOUT_MAX
)
HANGER_SPOTFACE_WASHER_SUPPORT_MIN = (
    HANGER_SPOTFACE_DIA_MIN - HANGER_WASHER.OD_MAX
) / 2.0 - HANGER_SPOTFACE_WASHER_OFFSET_MAX
# Pure full-annulus contact geometry, not a preload/material strength claim.
HANGER_WASHER_BEARING_MIN = (
    HANGER_WASHER_CONCENTRIC_ANNULUS_MIN - HANGER_SPOTFACE_WASHER_OFFSET_MAX
)
for _label, _value, _minimum in (
    ("spotface to crossbar faces", HANGER_SPOTFACE_BAR_WALL, 2.0),
    ("spotface to outer rail ends", HANGER_SPOTFACE_OUTER_END_WALL, 2.0),
    ("spotface over pocket roof", HANGER_SPOTFACE_POCKET_ROOF_WEB, 2.0),
    (
        "washer full support on smallest spotface",
        HANGER_SPOTFACE_WASHER_SUPPORT_MIN,
        0.0,
    ),
    ("washer continuous bearing annulus", HANGER_WASHER_BEARING_MIN, 0.0),
):
    if _value < _minimum:
        raise AssertionError(f"knife-hanger {_label}: {_value:.3f} below {_minimum:g}")
BAR_POCKET_HOLE_WALLS = {
    "hanger spotface": _POCKET_STATION
    - HANGER_SPOTFACE_DIA_MAX / 2.0
    - HANGER_DRIFT_AT_TOP
    - _POCKET_END,
    "hanger clearance hole": _POCKET_STATION
    - _CLEARANCE_MAX_R
    - DRILL_DRIFT_PER_MM
    * (RING_HEIGHT + PRINTED_LINEAR_BAND_MM[1] - (FLANGE - PRINTED_LINEAR_BAND_MM[1]))
    - _POCKET_END,
    "dowel slip hole": _POCKET_STATION
    - HANGER_PIN_X_TOL  # SAME Z at the round hole's general .XXX band
    - _PIN_HOLE_MAX_R
    - HANGER_DRIFT_AT_SLIP_FLOOR
    - _POCKET_END,
    "dowel slot": _POCKET_STATION
    - HANGER_PIN_X_TOL
    - HANGER_SLOT_POSITION_TOL / 2.0  # slot normal-to-length position radius
    - (HANGER_SLOT_WIDTH + max(HANGER_SLOT_WIDTH_BAND)) / 2.0
    - HANGER_DRIFT_AT_SLIP_FLOOR
    - _POCKET_END,
}
for _label, _value in BAR_POCKET_HOLE_WALLS.items():
    if _value < 2.0:
        raise AssertionError(
            f"crossbar pocket leaves {_value:.3f} mm to the {_label} at the printed bands"
        )


# Knife-mount top seats (drawing-guidelines.md rule 17 (walls and webs), print-worst): each block's footprint on
# the faced crossbar underside, (x, z), is the convex hull of its corners over
# every printed extreme -- its round dowel hole at the hanger's .X x and z
# stations from the sockets, the .XXX dowel-hole offset from the hanger
# axis and half the dowel slip; the block's +X face 5.65 (.XX) off its round
# hole, its widest .X width, the worse .X row-to-face reach either side; the
# whole turned through the title-block angle about the round dowel.
# _external_edge_breaks keeps every finished C2 band 0.5 off both hulls.
# The front hull overhangs the crossbar's sharp sides short of the gusset
# legs (the 25.4-wide block on the 25-wide bar); that overhang is not a break.
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


def _knife_seat_footprint(station_z: float, z_label: str) -> list[tuple[float, float]]:
    """Print-worst (x, z) hull of one knife-mount block's top seat."""
    slip = HANGER_PIN_SLIP_CLEARANCE_MAX / 2.0
    x_band = (
        PRINTED_LINEAR_BAND_MM[
            DRAWING_REFERENCE_PRECISION["hanger x from left sockets"]
        ]
        + HANGER_CROSSBAR_CENTER_TOL
        + HANGER_PIN_X_TOL
        + slip
    )
    z_band = PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION[z_label]] + slip
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
    "front": _knife_seat_footprint(STUD_Z_FRONT, "front hanger z from upper sockets"),
    "rear": _knife_seat_footprint(STUD_Z_REAR, "rear hanger z from upper sockets"),
}
# The hub stands at the spring-stamped post station, HUB_WEB_OFFSET (0.15)
# outboard of the east-rail web centre; every hub-to-web guard charges it.
HUB_WEB_OFFSET = abs(GOOSENECK_X + COLUMN_X)
if HUB_WEB_OFFSET + HUB_GUSSET_T / 2.0 > WEB_T / 2.0:
    raise AssertionError("hub V-gussets escape the east-rail web")
# The hub boss's chord at each rib side face stays inside the east-rail web,
# so each rib-side bottom and its web bottom meet at one clean vertex that a
# single C2 feature blends, with no boss-top sliver between their ends (at
# 27 wide the boss poked 0.038 past the web there).  NOMINAL, on purpose:
# this is a native-modelling guard on the CAD's topology, not a fit -- on a
# real casting the printed bands only move where the hand-broken edges blend.
HUB_BOSS_RIB_CHORD_MIN_MARGIN = 0.5
HUB_BOSS_RIB_CHORD_MARGIN = (
    WEB_T / 2.0
    - HUB_WEB_OFFSET
    - math.sqrt(max((HUB_BOSS_DIA / 2.0) ** 2 - (HUB_RIB_W / 2.0) ** 2, 0.0))
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
# Flush counterbore (drawing-guidelines.md rule 17 (walls and webs), print-worst). The mouth's lowest point on the
# Y-axis barrel is at its widest |x| = Dcb/2, so the head top must stay below
# |Zcol| + sqrt(R^2 - (Dcb/2)^2). Boss diameter and counterbore diameter
# print .X, the floor offset from the socket axis .XX: the shallowest recess
# takes the smallest barrel, the largest counterbore and the most-outboard
# floor; the head clearance takes the smallest counterbore. The offset is
# from the same socket axis, so socket pitch does not enter this local stack.
COUNTERBORE_MOUTH_LOW_Z = abs(FRONT_COLUMN_Z) + math.sqrt(
    (BOSS_DIA / 2.0) ** 2 - (COUNTERBORE_DIA / 2.0) ** 2
)
COUNTERBORE_HEAD_RECESS = COUNTERBORE_MOUTH_LOW_Z - (
    COUNTERBORE_FLOOR + CROSS_SCREW_HEAD_H
)  # 1.262 nominal
_BOSS_DIA_PLACES = DRAWING_PRECISION["BossUpProfile"]["C0Dia"]
_COUNTERBORE_DIA_PLACES = DRAWING_PRECISION["CounterboreRearProfile"]["CB1Dia"]
_COUNTERBORE_FLOOR_PLACES = DRAWING_REFERENCE_PRECISION[
    "counterbore floor from socket axis"
]
COUNTERBORE_MIN_BOSS_RADIUS = (
    round(BOSS_DIA, _BOSS_DIA_PLACES) - PRINTED_LINEAR_BAND_MM[_BOSS_DIA_PLACES]
) / 2.0
COUNTERBORE_MAX_RADIUS = (
    round(COUNTERBORE_DIA, _COUNTERBORE_DIA_PLACES)
    + PRINTED_LINEAR_BAND_MM[_COUNTERBORE_DIA_PLACES]
) / 2.0
COUNTERBORE_MIN_RADIUS = (
    round(COUNTERBORE_DIA, _COUNTERBORE_DIA_PLACES)
    - PRINTED_LINEAR_BAND_MM[_COUNTERBORE_DIA_PLACES]
) / 2.0
COUNTERBORE_MAX_FLOOR_OFFSET = (
    round(COUNTERBORE_FLOOR - abs(FRONT_COLUMN_Z), _COUNTERBORE_FLOOR_PLACES)
    + PRINTED_LINEAR_BAND_MM[_COUNTERBORE_FLOOR_PLACES]
)
COUNTERBORE_MIN_FLOOR_OFFSET = (
    round(COUNTERBORE_FLOOR - abs(FRONT_COLUMN_Z), _COUNTERBORE_FLOOR_PLACES)
    - PRINTED_LINEAR_BAND_MM[_COUNTERBORE_FLOOR_PLACES]
)
COUNTERBORE_PRINTED_HEAD_RECESS = math.sqrt(
    COUNTERBORE_MIN_BOSS_RADIUS**2 - COUNTERBORE_MAX_RADIUS**2
) - (COUNTERBORE_MAX_FLOOR_OFFSET + CROSS_SCREW_HEAD_H)  # 0.272
COUNTERBORE_PRINTED_HEAD_CLEARANCE = (
    COUNTERBORE_MIN_RADIUS - CROSS_SCREW_HEAD_DIA / 2.0
)  # 0.375 radial
if (
    min(COUNTERBORE_HEAD_RECESS, COUNTERBORE_PRINTED_HEAD_RECESS) <= 0.0
    or COUNTERBORE_PRINTED_HEAD_CLEARANCE <= 0.0
    or COUNTERBORE_PLANE <= COUNTERBORE_FLOOR
):
    raise AssertionError(
        "top cross-screw head stands proud of its counterbore at the printed bands"
    )
# The near casting wall between the counterbore floor and the socket bore
# carries the screw's near thread: the most-inboard printed floor against
# the largest printed bore.
COUNTERBORE_PRINTED_NEAR_WALL = (
    COUNTERBORE_MIN_FLOOR_OFFSET
    - (
        round(BORE_DIA, DRAWING_PRECISION["BoreProfile"]["B0Dia"])
        + PRINTED_LINEAR_BAND_MM[DRAWING_PRECISION["BoreProfile"]["B0Dia"]]
    )
    / 2.0
)  # 2.22
# Cap recess to counterbore ligament: the recess's deepest, widest printed
# corner against the counterbore's outboard-most floor rim, with the tap
# axis at the high end of its .X station below the boss top.  The floor's
# station prints .XX and stands at 15.875 (TOP_SCREW_SEAT_Z 5-1/16), so this
# meets drawing-guidelines.md rule 17 (walls and webs)'s 2.0 target: 2.27 with the
# 19/32 recess (1.76 at 5/8).  At 16.1 it left 1.518 at .X
# (codex review of 67d8b2c6) and 1.80 at .XX (080fda97).
_AXIS_PLACES = DRAWING_REFERENCE_PRECISION["cross screw axis from boss top"]
COUNTERBORE_PRINTED_CAP_LIGAMENT = math.hypot(
    COUNTERBORE_MIN_FLOOR_OFFSET
    - (CAP_RECESS_DIAMETER + CAP_RECESS_DIAMETER_BAND[0]) / 2.0,
    (CAP_RECESS_FLOOR_Y - CAP_RECESS_DEPTH_BAND[0])
    - (PRINTED_LINEAR_BAND_MM[_AXIS_PLACES] + COUNTERBORE_MAX_RADIUS),
)
if min(COUNTERBORE_PRINTED_NEAR_WALL, COUNTERBORE_PRINTED_CAP_LIGAMENT) < 2.0:
    raise AssertionError(
        "top cross-screw counterbore leaves under 2.0 mm to the bore or cap recess"
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

# The whole keeper-rail top between the bosses is faced (user ruling
# 2026-10-11), so the ACTUAL foot, anywhere its printed fit-up band puts it,
# must stand on that flat face: clear of the bosses (above) and of the
# maximum printed C2 top-rim leg on either side of the rail.
KEEPER_FOOT_PRINTED_FLAT_TOP_SIDE_MARGIN = (
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
    - (
        round(EDGE_CHAMFER, DRAWING_REFERENCE_PRECISION["top rim chamfer"])
        + PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["top rim chamfer"]]
    )
)
if KEEPER_FOOT_PRINTED_FLAT_TOP_SIDE_MARGIN <= 0.0:
    raise AssertionError("keeper foot leaves the flat keeper-rail top")

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
# B-B prints the top flange thickness TYP: one .X FINAL dimension binds
# every rail, the faced keeper-rail top included, so facing cannot subtract
# a second allowance from its printed minimum, and cap-floor and boss-height
# bands do not enter. (An untyped flange would need its own facing
# allowance; this wall stays >= 1.5 only for one below about 0.77.)
KEEPER_MIN_FLANGE_THICKNESS = (
    round(FLANGE, DRAWING_REFERENCE_PRECISION["top flange thickness"])
    - PRINTED_LINEAR_BAND_MM[DRAWING_REFERENCE_PRECISION["top flange thickness"]]
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
# drawing-guidelines.md rule 17 (walls and webs): budget realistic deep-drill wander over the FULL allowed
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

# The deeper counterbore carries the west cross taps past both keeper
# stations, so the #10-32 thread now runs under the #2-56 tap drills. The
# wall is the keeper drill's cylinder-plus-cone profile (deepest printed
# drill, largest drilled radius, nearest printed transverse offset) against
# the thread major with its axis at the top of the stacked .X bands (axis
# below boss top, boss top above rail top), less both axes' wander. The
# cross-tap axis lies on the receiver web centre (the socket axis), and its
# wander uses the same angular drift over the run from the counterbore floor.
KEEPER_MIN_WEB_CENTRE_OFFSET = (
    abs(round(KEEPER_FITUP_X_FROM_WEB_MM, KEEPER_FITUP_PLACES))
    - KEEPER_FITUP_LOCATION_BAND_MM
    - KEEPER_MAX_TRANSVERSE_OFFSET
)  # 2.35
_KEEPER_DRILL_BOTTOM_Y = HALF_H - KEEPER_MAX_TAP_DRILL_DEPTH
_KEEPER_DRILL_TIP_Y = (
    _KEEPER_DRILL_BOTTOM_Y - KEEPER_MAX_TAP_DRILL_RADIUS * DRILL_POINT_H
)
_CROSS_AXIS_MAX_Y = (
    PRINTED_LINEAR_BAND_MM[
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
)  # 1.53: under the 2.0 target, over the 1.5 floor
if KEEPER_CROSS_TAP_WALL < 1.5:
    raise AssertionError("top cross-tap thread leaves under 1.5 mm to a keeper drill")


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
    boss adds only the 8 below; a cell past the web faces, under the flange,
    would be empty below +10.25 and gain the full 26.25 (none while
    HUB_BOSS_RIB_CHORD_MARGIN holds: the circle leaves the rib inside the web).
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
    x = GOOSENECK_X - r - 0.6
    while x < GOOSENECK_X + r + 0.6:
        xx = x + 0.5 * step
        z = GOOSENECK_Z - HUB_GUSSET_HALF_OUT - 0.6
        z_end = GOOSENECK_Z + HUB_GUSSET_HALF_OUT + 0.6
        while z < z_end:
            zz = z + 0.5 * step
            h = 0.0
            if (xx - GOOSENECK_X) ** 2 + (zz - GOOSENECK_Z) ** 2 <= r * r:
                h = HUB_BOSS_DROP
            elif abs(xx - GOOSENECK_X) <= HUB_GUSSET_T / 2.0:
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


def _counterbore_removal() -> float:
    """Material one O9 counterbore removes from the Ø45 curved boss."""
    r_d = COUNTERBORE_DIA / 2.0
    r_b = BOSS_DIA / 2.0
    step = 0.01
    vol = 0.0
    d = -r_d
    while d < r_d:
        dd = d + 0.5 * step
        chord = 2.0 * math.sqrt(max(0.0, r_d * r_d - dd * dd))
        surf = abs(FRONT_COLUMN_Z) + math.sqrt(max(0.0, r_b * r_b - dd * dd))
        length = max(0.0, min(surf, COUNTERBORE_PLANE) - COUNTERBORE_FLOOR)
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
    """Material removed by the 1/4-20 tap from the spot face to the bore."""
    r_h = TAP_DRILL_MM[SET_SCREW_THREAD] / 2.0
    r_v = GOOSENECK_BORE_DIA / 2.0
    floor_x = -SET_SPOT_FACE_X  # 218.43125 (magnitudes, east side)
    step = 0.005
    vol = 0.0
    d = -r_h
    while d < r_h:
        dd = d + 0.5 * step
        chord = 2.0 * math.sqrt(max(0.0, r_h * r_h - dd * dd))
        void = -GOOSENECK_X + math.sqrt(max(0.0, r_v * r_v - dd * dd))
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
    runs. The crossbar web adds its two roots between the pocket ends
    (|z| <= 69). The fillet ends dying into boss barrels / rib / land /
    pocket-end walls and the small vertical junction coves at those walls
    are not modeled -- the check tolerance absorbs the ends; the vertical
    coves stay sharp.
    """
    area = _fillet_section_area(ROOT_FILLET_R)
    cut = math.sqrt((BOSS_DIA / 2.0) ** 2 - (WEB_T / 2.0) ** 2)
    side = 2.0 * (abs(FRONT_COLUMN_Z) - cut)  # one side-rail run, west
    fr = 2.0 * (COLUMN_X - cut)  # one front/rear run, uninterrupted
    outer = side + (side - HUB_RIB_W) + 2.0 * fr
    window = side + (side - HUB_RIB_W) + 2.0 * (fr - (LAND_X1 - LAND_X0))
    crossbar = 2.0 * 2.0 * BAR_POCKET_Z
    return area * (outer + window + crossbar)


def _bore_chamfer_removal() -> float:
    """Volume the C1 x 45 breaks remove from the five top bore rims."""

    def ring(bore_dia: float) -> float:
        return math.pi * BORE_CHAMFER**2 * (bore_dia / 2.0 + BORE_CHAMFER / 3.0)

    return 4.0 * ring(CAP_RECESS_DIAMETER) + ring(GOOSENECK_BORE_DIA)


def _casting_occupies(x: float, y: float, z: float) -> bool:
    """Whether the solid casting, as the C2 breaks find it, holds (x, y, z).

    The rail T-ring, hub rib with its set-screw boss (spot face out),
    junction lands, crossbar with its gussets and T pockets, corner bosses
    and hub boss -- exact around every C2 pick (bores, holes, V-gussets and
    the earlier top breaks lie clear of them).
    """
    ax, az = abs(x), abs(z)
    in_ring_height = -HALF_H <= y <= HALF_H
    if FLANGE_BOT_Y <= y <= HALF_H and ax <= OUTER_X and az <= OUTER_Z:
        if not (ax < INNER_X and az < INNER_Z):
            return True
    if in_ring_height:
        if WEB_IN_X <= ax <= WEB_OUT_X and az <= WEB_OUT_Z:
            return True
        if WEB_IN_Z <= az <= WEB_OUT_Z and ax <= WEB_OUT_X:
            return True
        if LAND_X0 <= x <= LAND_X1 and INNER_Z <= az <= WEB_IN_Z:
            return True
        if (
            -OUTER_X <= x <= -INNER_X
            and GOOSENECK_Z - HUB_RIB_W / 2.0 <= z <= GOOSENECK_Z + HUB_RIB_W / 2.0
        ):
            return True
        if (
            SET_BOSS_FACE_X <= x <= -OUTER_X
            and y <= FLANGE_BOT_Y
            and abs(z - GOOSENECK_Z) <= HUB_SET_BOSS_W / 2.0
            and not (
                x < SET_SPOT_FACE_X
                and math.hypot(y, z - GOOSENECK_Z) < HUB_SET_SPOT_DIA / 2.0
            )
        ):
            return True
        if BAR_X0 <= x <= BAR_X1 and az <= INNER_Z:
            pocket = (
                y < FLANGE_BOT_Y
                and az < BAR_POCKET_Z
                and (x < BAR_WEB_X0 or x > BAR_WEB_X1)
            )
            if not pocket:
                return True
        spread = az - (INNER_Z - GUSSET)
        if 0.0 <= spread and az <= INNER_Z and BAR_X0 - spread <= x <= BAR_X1 + spread:
            return True
    if -(HALF_H + BOSS_BELOW) <= y <= HALF_H + BOSS_ABOVE:
        if math.hypot(ax - COLUMN_X, az - abs(FRONT_COLUMN_Z)) <= BOSS_DIA / 2.0:
            return True
    if -(HALF_H + HUB_BOSS_DROP) <= y <= -HALF_H:
        if math.hypot(x - GOOSENECK_X, z - GOOSENECK_Z) <= HUB_BOSS_DIA / 2.0:
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
    """The C2 external edge breaks as one chamfer feature per edge group, in
    build order (feature name -> picks, analytic removal, shared vertices),
    and each knife seat's least clearance to them.

    Every external convex edge the top-rim and bore-top breaks left, once
    the T-section crossbar exists: the flange undersides (outer, window and
    the eight short outer-corner runs), the four outer vertical corners, the
    web bottoms, the junction lands' free edges, the crossbar web bottoms,
    pocket-end bottoms and outer corners, the hub rib's free corners and
    side bottoms, and the corner/hub boss rims.
    Straight edges remove ``c^2 sin(angle) / 2`` per mm over their run to the
    face that ends them; outer rims remove ``pi c^2 (R - c/3)``. Corner
    patches and the ends dying into boss barrels are left to the tolerance.

    Groups are the connected chains of breaks, long simple runs first and
    the outer corners and boss rims last, so a native failure names its
    chain and each chain's volume is proved on its own. Breaks that share a
    vertex must sit in one group (SolidWorks blends that corner only within
    a feature); any other two breaks keep ``2c + C2_SLIVER_MIN`` apart, or
    the module fails to import. ``shared`` counts the pairs of a group's
    breaks that meet at a vertex.

    Every pick must be the convex edge it claims: its solid angle, measured
    on ``_casting_occupies``, is below 180 degrees and equals the angle its
    removal uses, or the module fails to import. Every break reaching the
    underside keeps its print-worst band (``_EDGE_LOCATION_BAND`` off the
    edge, ``EDGE_CHAMFER + _C2_LEG_BAND`` into the face) at least
    ``KNIFE_SEAT_C2_MIN_CLEARANCE`` off both print-worst knife-seat hulls;
    the returned dict is each seat's least clearance.

    Not broken C2: the crossbar flange's underside edges (only a 1.5 flat
    beside the R3 web root), the crossbar's full-depth side bottoms from
    each pocket end to its gusset leg and the gusset hypotenuse bottoms
    (both knife-mount seats sit over them at the printed bands), the hub
    rib's outer and inner bottom edges (2.1 to the Ø30 hub boss, so C2
    leaves a 0.1 land), the tapered hub V-gusset edges (they feather into
    the underside), and every hole, bore, counterbore, spot-face, tap and
    slot edge. The vertical junctions of the bar sides with
    the gusset hypotenuses are re-entrant (225 degrees), not edges to break.
    """
    c = EDGE_CHAMFER
    z_col = abs(FRONT_COLUMN_Z)
    r_boss = BOSS_DIA / 2.0
    r_hub = HUB_BOSS_DIA / 2.0
    side_cut = math.sqrt(r_boss**2 - (RAIL_W_SIDE / 2.0) ** 2)  # 14.624
    fr_cut = math.sqrt(r_boss**2 - (RAIL_W_FR / 2.0) ** 2)  # 12.052
    web_cut = math.sqrt(r_boss**2 - (WEB_T / 2.0) ** 2)  # 21.540
    rib_lo = GOOSENECK_Z - HUB_RIB_W / 2.0
    rib_hi = GOOSENECK_Z + HUB_RIB_W / 2.0
    y_under = FLANGE_BOT_Y
    y_bottom = -HALF_H
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
    band_in = _EDGE_LOCATION_BAND + c + _C2_LEG_BAND

    def convex(point: tuple[float, float, float], axis, angle: float) -> None:
        measured = _interior_angle(point, axis)
        if measured >= 180.0 or abs(measured - angle) > 5.0:
            raise AssertionError(
                f"C{c:g} pick at {point} claims a convex {angle:g}-degree edge;"
                f" the casting holds {measured:g} degrees round it"
            )

    def edge(
        point: tuple[float, float, float],
        length: float,
        angle: float,
        axis: tuple[float, float, float],
    ) -> None:
        if length <= 2.0 * c:
            raise AssertionError(
                f"edge at {point} is too short for C{c:g}: {length:.3f}"
            )
        convex(point, axis, angle)
        picks, volume, _ = groups[group]
        picks.append(list(point))
        removal = 0.5 * c * c * math.sin(math.radians(angle)) * length
        groups[group] = (picks, volume + removal, 0)
        segments.append(
            (
                group,
                tuple(point[i] - axis[i] * length / 2.0 for i in range(3)),
                tuple(point[i] + axis[i] * length / 2.0 for i in range(3)),
            )
        )
        x, y, z = point
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
        elif axis[1] == 1.0 and abs(y - length / 2.0 - y_bottom) < 1e-9:
            # A vertical break bevels the underside's corner: a band_in square.
            underside_bands.append(
                (
                    point,
                    [
                        (x + sx * band_in, z + sz * band_in)
                        for sx, sz in (
                            (-1.0, -1.0),
                            (1.0, -1.0),
                            (1.0, 1.0),
                            (-1.0, 1.0),
                        )
                    ],
                )
            )

    def along_x(z: float, y: float, x0: float, x1: float, angle: float = 90.0) -> None:
        lo, hi = sorted((x0, x1))
        edge(((lo + hi) / 2.0, y, z), hi - lo, angle, (1.0, 0.0, 0.0))

    def along_y(x: float, z: float, y0: float, y1: float, angle: float = 90.0) -> None:
        lo, hi = sorted((y0, y1))
        edge((x, (lo + hi) / 2.0, z), hi - lo, angle, (0.0, 1.0, 0.0))

    def along_z(x: float, y: float, z0: float, z1: float, angle: float = 90.0) -> None:
        lo, hi = sorted((z0, z1))
        edge((x, y, (lo + hi) / 2.0), hi - lo, angle, (0.0, 0.0, 1.0))

    start("RailRunBreaks")
    # Long single runs whose both ends die into corner-boss barrels: the
    # west and front/rear outer flange undersides, the west web bottoms and
    # the front/rear outer web bottoms.
    along_z(OUTER_X, y_under, -(z_col - side_cut), z_col - side_cut)
    for sz in (-1.0, 1.0):
        along_x(sz * OUTER_Z, y_under, -(COLUMN_X - fr_cut), COLUMN_X - fr_cut)
    for x_web in (WEB_OUT_X, WEB_IN_X):
        along_z(x_web, y_bottom, -(z_col - web_cut), z_col - web_cut)
    for sz in (-1.0, 1.0):
        along_x(sz * WEB_OUT_Z, y_bottom, -(COLUMN_X - web_cut), COLUMN_X - web_cut)
    start("CrossbarBreaks")
    # Crossbar: web bottoms; per pocket end its bottom and its outer vertical
    # corner. Beyond the pocket ends the knife-mount seats sit over the bar
    # sides and gusset hypotenuses, whose bottoms stay sharp.
    for x_web in (BAR_WEB_X0, BAR_WEB_X1):
        along_z(x_web, y_bottom, -BAR_POCKET_Z, BAR_POCKET_Z)
    for sz in (-1.0, 1.0):
        along_x(sz * BAR_POCKET_Z, y_bottom, BAR_X0, BAR_WEB_X0)
        along_x(sz * BAR_POCKET_Z, y_bottom, BAR_WEB_X1, BAR_X1)
        for x_bar in (BAR_X0, BAR_X1):
            along_y(x_bar, sz * BAR_POCKET_Z, y_bottom, y_under)
    start("WestWindowBreaks")
    # The west window's flange underside, round its corners into the
    # front/rear runs to the junction lands, the lands' free vertical
    # corners, end bottoms and short window-face bottoms (to the sharp
    # gusset hypotenuse), and the front/rear window web bottoms the land
    # ends meet.
    along_z(INNER_X, y_under, -INNER_Z, INNER_Z)
    for sz in (-1.0, 1.0):
        along_x(sz * INNER_Z, y_under, LAND_X1, INNER_X)
        along_y(LAND_X1, sz * INNER_Z, y_bottom, y_under)
        along_z(LAND_X1, y_bottom, sz * INNER_Z, sz * WEB_IN_Z)
        along_x(sz * INNER_Z, y_bottom, BAR_X1 + GUSSET, LAND_X1)
        along_x(sz * WEB_IN_Z, y_bottom, LAND_X1, COLUMN_X - web_cut)
    start("HubRailBreaks")
    # The east (hub) side, all one chain: the outer and window flange
    # undersides split by the hub rib, the rib's four free vertical
    # corners, its side bottoms out to the web faces (each meeting its web
    # bottom at one vertex: the boss chord stays inside the web), the east
    # web bottoms, and the east window's front/rear runs, land edges and
    # window web bottoms as on the west.
    along_z(-OUTER_X, y_under, -(z_col - side_cut), rib_lo)
    along_z(-OUTER_X, y_under, rib_hi, z_col - side_cut)
    along_z(-INNER_X, y_under, -INNER_Z, rib_lo)
    along_z(-INNER_X, y_under, rib_hi, INNER_Z)
    for z_rib in (rib_lo, rib_hi):
        for x_face in (-OUTER_X, -INNER_X):
            along_y(x_face, z_rib, y_bottom, y_under)
        along_x(z_rib, y_bottom, -OUTER_X, -WEB_OUT_X)
        along_x(z_rib, y_bottom, -WEB_IN_X, -INNER_X)
    for x_web in (WEB_OUT_X, WEB_IN_X):
        along_z(-x_web, y_bottom, -(z_col - web_cut), rib_lo)
        along_z(-x_web, y_bottom, rib_hi, z_col - web_cut)
    for sz in (-1.0, 1.0):
        along_x(sz * INNER_Z, y_under, -INNER_X, LAND_X0)
        along_y(LAND_X0, sz * INNER_Z, y_bottom, y_under)
        along_z(LAND_X0, y_bottom, sz * INNER_Z, sz * WEB_IN_Z)
        along_x(sz * INNER_Z, y_bottom, LAND_X0, BAR_X0 - GUSSET)
        along_x(sz * WEB_IN_Z, y_bottom, -(COLUMN_X - web_cut), LAND_X0)
    start("HubSetBossBreaks")
    # The set-screw boss proud of the rib's outer face: the four edges of its
    # cast face and its four runs back to the rib, meeting at the face's
    # corners. The breaks leave the O10 spot face a 2.0 land across the
    # boss and 3.25 under the flange (SET_SPOT_LAND_MIN: print-worst).
    boss_lo = GOOSENECK_Z - HUB_SET_BOSS_W / 2.0
    boss_hi = GOOSENECK_Z + HUB_SET_BOSS_W / 2.0
    for z_side in (boss_lo, boss_hi):
        along_y(SET_BOSS_FACE_X, z_side, y_bottom, y_under)
    for y_side in (y_bottom, y_under):
        along_z(SET_BOSS_FACE_X, y_side, boss_lo, boss_hi)
        for z_side in (boss_lo, boss_hi):
            along_x(z_side, y_side, SET_BOSS_FACE_X, -OUTER_X)
    start("OuterCornerBreaks")
    # Per plan corner: the two short flange-underside runs outside the boss
    # barrel and the vertical corner up to the top-rim break, which all meet
    # at the corner's underside vertex.
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            along_z(sx * OUTER_X, y_under, sz * (z_col + side_cut), sz * OUTER_Z)
            along_x(sz * OUTER_Z, y_under, sx * (COLUMN_X + fr_cut), sx * OUTER_X)
            along_y(sx * OUTER_X, sz * OUTER_Z, y_under, HALF_H - c)
    # Boss rims: the four corner bosses top and bottom, and the hub boss --
    # closed circles that meet no other break.
    start("BossRimBreaks")
    rims: list[tuple[tuple[float, float, float], float]] = []

    def rim(centre: tuple[float, float, float], radius: float, sx: float) -> None:
        # Picked on the outboard (sx) side of the circle.
        point = (centre[0] + sx * radius, centre[1], centre[2])
        convex(point, (0.0, 0.0, 1.0), 90.0)
        picks, volume, _ = groups[group]
        picks.append(list(point))
        groups[group] = (picks, volume + math.pi * c * c * (radius - c / 3.0), 0)
        rims.append((centre, radius))

    for sx in (-1.0, 1.0):
        for z_world in (FRONT_COLUMN_Z, REAR_COLUMN_Z):
            for y_rim in (HALF_H + BOSS_ABOVE, -(HALF_H + BOSS_BELOW)):
                rim((sx * COLUMN_X, y_rim, z_world), r_boss, sx)
    rim((GOOSENECK_X, -(HALF_H + HUB_BOSS_DROP), GOOSENECK_Z), r_hub, -1.0)
    # Any two breaks either share a vertex -- then one feature must cut both,
    # so SolidWorks blends that corner -- or stay 2c + C2_SLIVER_MIN apart, so
    # no two C2 faces leave a sliver between them. Each group's shared
    # vertices size its volume tolerance.
    reach = 2.0 * c + C2_SLIVER_MIN
    for i, (group_a, p0, p1) in enumerate(segments):
        for group_b, q0, q1 in segments[i + 1 :]:
            gap = _segment_gap(p0, p1, q0, q1)
            if gap < 1e-9:
                if group_a != group_b:
                    raise AssertionError(
                        f"C{c:g} breaks in {group_a} and {group_b} meet at a vertex"
                        f" near {p0}..{p1}; one feature must cut both"
                    )
                picks, volume, shared = groups[group_a]
                groups[group_a] = (picks, volume, shared + 1)
            elif gap < reach:
                raise AssertionError(
                    f"C{c:g} breaks {p0}..{p1} ({group_a}) and {q0}..{q1}"
                    f" ({group_b}) stop {gap:.3f} mm apart; C{c:g} faces"
                    f" would leave a sliver under {C2_SLIVER_MIN:g}"
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
            if gap < reach:
                raise AssertionError(
                    f"C{c:g} break {p0}..{p1} comes {gap:.3f} mm from a boss rim"
                )
    # Neither knife-mount seat may sit on, or within the clearance of, a
    # finished C2 band.
    seat_clearance = {}
    for mount, footprint in KNIFE_SEAT_FOOTPRINTS.items():
        gap, nearest = min(
            (_plan_gap(band, footprint), where) for where, band in underside_bands
        )
        if gap < KNIFE_SEAT_C2_MIN_CLEARANCE:
            raise AssertionError(
                f"C{c:g} break at {nearest} comes within {gap:.3f} mm of the "
                f"print-worst {mount} knife-mount seat (needs "
                f"{KNIFE_SEAT_C2_MIN_CLEARANCE:g})"
            )
        seat_clearance[mount] = gap
    return groups, seat_clearance


EXTERNAL_EDGE_BREAKS, KNIFE_SEAT_C2_CLEARANCE = _external_edge_breaks()


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
    to_sketch = _model_to_sketch(adapter, sketch)

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


# The governing grip is the model's own driving dimension; the StudHoles
# wizard's spotface depth is bound to it, so the floor follows it alone.
HANGER_GRIP_DIMENSION = f"HangerGrip@{HANGER_GRIP_SKETCH}"
HANGER_SPOTFACE_DEPTH_DRIVE = f'"RingHeight" - "{HANGER_GRIP_DIMENSION}"'
# A linear global keeps 8 document (inch) places: 5e-9 in, 1.3e-7 mm.
HANGER_GRIP_READBACK_MM = 1e-5
# The live-link probe: a 0.10 shorter grip deepens both spotfaces by 0.10.
HANGER_GRIP_PROBE_MM = 0.10
HANGER_GRIP_PROBE_VOLUME = (
    2.0
    * math.pi
    * ((HANGER_SPOTFACE_DIA / 2.0) ** 2 - (HANGER_CLEARANCE_DIA / 2.0) ** 2)
    * HANGER_GRIP_PROBE_MM
)


def _carries_dimension(feature, full_name: str) -> bool:
    """Whether ``feature``'s own display-dimension walk holds ``full_name``."""
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if str(dimension.FullName) == full_name:
            return True
        display = feature.GetNextDisplayDimension(display)
    return False


def _hanger_spotface_depth_name(feature) -> str:
    """The StudHoles wizard's own spotface-depth dimension, as ``name@owner``.

    The build_mg_magnifying_bracket CounterBoreDepth criterion: the ONE
    display dimension whose native name holds "depth" and whose value is the
    1.0 nominal spotface depth. Both parts of the name are the ones
    SolidWorks reports; no internal dimension name is manufactured.

    IFeature::GetFirstDisplayDimension walks "all dimensions on this feature
    [and] its sub-features"; a Hole Wizard keeps its cut dimensions in its
    internal profile sketch (farm R2e5ad7dcd: ["C'Bore Depth", "Sketch18"]).
    The owner must therefore be StudHoles itself or one of ITS sub-features,
    found by GetFirstSubFeature/GetNextSubFeature, and that sub-feature's own
    walk (the SDK: a sub-feature returns only its sketch's dimensions) must
    hold the same dimension. Any other owner is foreign and fails.
    """
    matches = []
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        full_name = str(dimension.FullName)
        native = full_name.split("@")
        mm = float(dimension.SystemValue) * 1000.0
        if "depth" in native[0].lower() and abs(mm - HANGER_SPOTFACE_DEPTH) < 1e-5:
            matches.append((full_name, native))
        display = feature.GetNextDisplayDimension(display)
    if len(matches) != 1:
        raise RuntimeError(
            f"hanger wizard has {len(matches)} spotface-depth matches: "
            f"{[native for _full, native in matches]}"
        )
    full_name, native = matches[0]
    owner = native[1] if len(native) >= 2 else ""
    if owner != str(feature.Name):
        subs = {}
        sub = feature.GetFirstSubFeature()
        while sub is not None:
            sub = _early_bound(sub, "IFeature")
            subs[str(sub.Name)] = sub
            sub = sub.GetNextSubFeature()
        if owner not in subs or not _carries_dimension(subs[owner], full_name):
            raise RuntimeError(
                f"hanger spotface depth {native} is not owned by {feature.Name} "
                f"or its sub-features {sorted(subs)}"
            )
    return f"{native[0]}@{owner}"


async def _author_hanger_grip_reference(
    adapter, plane_name: str
) -> list[tuple[str, str]]:
    """Author HangerGrip, the underside-to-spotfloor grip, as ONE driving
    model dimension; return the sketch's deferred drive jobs.

    ``plane_name`` is the rear station's Front-offset plane -- section F-F's
    cutting plane -- so the sheet imports the dimension in F-F. A
    construction centreline on the rear screw axis runs from the finished
    underside up to the washer spotface floor; its length is driven by the
    HangerGrip global and, through HANGER_SPOTFACE_DEPTH_DRIVE, drives the
    wizard's spotface depth. The plane's sketch axes are mapped, not assumed.
    """
    check(
        "create_sketch hanger grip reference", await adapter.create_sketch(plane_name)
    )
    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("hanger grip reference: no active sketch")
    to_sketch = _model_to_sketch(adapter, _early_bound(active, "ISketch"))
    underside = to_sketch((HANGER_X, -HALF_H, STUD_Z_REAR))
    floor = to_sketch((HANGER_X, -HALF_H + HANGER_GRIP, STUD_Z_REAR))
    (u0, v0, w0), (u1, v1, w1) = underside, floor
    if (
        max(abs(w0), abs(w1)) > 1e-4
        or abs(u1 - u0) > 1e-4
        or abs(abs(v1 - v0) - HANGER_GRIP) > 1e-4
        or abs(abs(v0) - HALF_H) > 1e-4
        or abs(abs(u0) - abs(HANGER_X)) > 1e-4
    ):
        raise RuntimeError(
            "hanger grip reference plane does not carry the rear screw axis "
            f"along sketch v: underside {underside}, floor {floor}"
        )
    grip = SketchDims()
    set_sketch_direct_db(adapter, True)
    grip_line = check(
        "hanger grip centerline", await adapter.add_centerline(u0, v0, u1, v1)
    )
    set_sketch_direct_db(adapter, False)
    check(
        "hanger grip centerline vertical",
        await adapter.add_sketch_constraint(grip_line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{grip_line}.start",
        "origin",
        "horizontal_distance",
        abs(u0),
        "hanger grip screw axis",
    )
    grip.record("HangerGripAxisX")
    await dimension_between(
        adapter,
        f"{grip_line}.start",
        "origin",
        "vertical_distance",
        abs(v0),
        "hanger grip finished underside",
    )
    grip.record("HangerGripUnderside", '"RingHeight" / 2')
    await dimension_between(
        adapter,
        f"{grip_line}.start",
        f"{grip_line}.end",
        "vertical_distance",
        HANGER_GRIP,
        "hanger grip underside to spotface floor",
    )
    grip.record("HangerGrip", '"HangerGrip"')
    await ensure_fully_defined(adapter, "hanger grip reference sketch")
    check("exit_sketch hanger grip reference", await adapter.exit_sketch())
    name_last_feature(adapter, HANGER_GRIP_SKETCH)
    return grip.apply(adapter, HANGER_GRIP_SKETCH)


def _equations_naming(adapter, lhs: str) -> list[str]:
    """Every equation whose left-hand side is ``lhs`` (whitespace-blind)."""
    from solidworks_mcp.adapters.solidworks.parametrics import (
        _equation_manager,
        _read_member,
    )

    manager = _equation_manager(adapter)
    wanted = "".join(lhs.split())
    matches = []
    for index in range(int(_read_member(manager, "GetCount") or 0)):
        text = str(manager.Equation(index) or "")
        if "".join(text.partition("=")[0].split()) == wanted:
            matches.append(text)
    return matches


def _hanger_grip_problems(adapter, depth_name: str, grip_mm: float) -> list[str]:
    """Why HangerGrip does not singly drive the spotface depth at ``grip_mm``."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    problems = []
    for name, rhs, expected_mm in (
        (HANGER_GRIP_DIMENSION, '"HangerGrip"', grip_mm),
        (depth_name, HANGER_SPOTFACE_DEPTH_DRIVE, RING_HEIGHT - grip_mm),
    ):
        equations = _equations_naming(adapter, f'"{name}"')
        if len(equations) != 1:
            problems.append(f"{name}: expected one equation, found {equations}")
        elif "".join(equations[0].partition("=")[2].split()) != "".join(rhs.split()):
            problems.append(f"{name}: owned by {equations[0]!r}, not {rhs}")
        dimension = model.Parameter(name)
        if dimension is None:
            problems.append(f"{name}: not found")
            continue
        dimension = _early_bound(dimension, "IDimension")
        if bool(dimension.IsReference()):
            problems.append(f"{name}: is a reference dimension")
        value_mm = float(dimension.SystemValue) * 1000.0
        _telemetry.info(f"hanger grip {name} = {value_mm:.6f} mm ({equations})")
        if abs(value_mm - expected_mm) > HANGER_GRIP_READBACK_MM:
            problems.append(f"{name}: reads {value_mm:.6f} mm, expected {expected_mm}")
    return problems


async def _assert_hanger_grip_drives_spotface(
    adapter, depth_name: str, volume: float
) -> None:
    """Prove HangerGrip is the live, single control on the spotface floor.

    After the deferred equations: each of HangerGrip and the wizard depth has
    exactly one equation (global -> grip -> "RingHeight" - grip), neither is a
    reference dimension, and both read nominal. Then the HangerGrip global is
    shortened by HANGER_GRIP_PROBE_MM: the depth must follow and the solid
    must lose both deeper spotface annuli, before the global is restored and
    the as-built state re-proven. A witness that drives nothing fails here.
    """
    problems = _hanger_grip_problems(adapter, depth_name, HANGER_GRIP)
    if problems:
        raise RuntimeError("hanger grip ownership: " + "; ".join(problems))
    probe_mm = HANGER_GRIP - HANGER_GRIP_PROBE_MM
    await set_global(adapter, "HangerGrip", f"{probe_mm}mm")
    await force_rebuild(adapter)
    problems = _hanger_grip_problems(adapter, depth_name, probe_mm)
    if problems:
        raise RuntimeError("hanger grip live link: " + "; ".join(problems))
    await volume_check(
        adapter,
        "hanger grip probe (spotfaces follow HangerGrip)",
        volume - HANGER_GRIP_PROBE_VOLUME,
        0.25 * HANGER_GRIP_PROBE_VOLUME,
    )
    await set_global(adapter, "HangerGrip", f"{HANGER_GRIP}mm")
    await force_rebuild(adapter)
    problems = _hanger_grip_problems(adapter, depth_name, HANGER_GRIP)
    if problems:
        raise RuntimeError("hanger grip restore: " + "; ".join(problems))
    await volume_check(adapter, "hanger grip restored", volume, 1.0)
    _telemetry.success(f"{HANGER_GRIP_DIMENSION} drives {depth_name}")


def _tolerance_hanger_clearance(feature) -> None:
    """Band the through diameter, NOT the spot diameter or the depth.

    Counterbore-shaped wizards have multiple "Dia" dimensions, unlike the
    generic one-diameter hook. Reuse that native name criterion, additionally
    resolving the unique actual 6.045 diameter; never assume dimension order
    or manufacture an internal SOLIDWORKS dimension name.
    """
    matches = []
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if (
            "Dia" in str(dimension.FullName)
            and abs(float(dimension.SystemValue) * 1000.0 - HANGER_CLEARANCE_DIA) < 1e-6
        ):
            matches.append((display, dimension))
        display = feature.GetNextDisplayDimension(display)
    if len(matches) != 1:
        raise RuntimeError(f"hanger wizard has {len(matches)} through-diameter matches")
    display, dimension = matches[0]
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    lower_m, upper_m = (
        value / 1000.0
        for value in (
            min(HANGER_CLEARANCE_DIA_BAND),
            max(HANGER_CLEARANCE_DIA_BAND),
        )
    )
    tolerance.Type = 2  # swTolType_e.swTolBILAT: explicit +0.13/0
    if not tolerance.SetValues(lower_m, upper_m):
        raise RuntimeError("native hanger through-diameter band was rejected")
    if (
        int(tolerance.Type) != 2
        or abs(float(tolerance.GetMinValue()) - lower_m) > 1e-9
        or abs(float(tolerance.GetMaxValue()) - upper_m) > 1e-9
    ):
        raise RuntimeError("native hanger through-diameter band did not persist")
    _set_tolerance_precision(
        display,
        HANGER_CLEARANCE_DIA_BAND,
        label="hanger through diameter",
        places=HANGER_CLEARANCE_DIA_PLACES,
    )


def _qualify_machined_faces(adapter) -> None:
    """Area-check every face the surface-finish spec owns.

    ``resolve_faces`` already proves each spec names exactly ONE face; the
    area proves it named the RIGHT one, so a station typo ships a build failure
    instead of a roughness symbol on the wrong surface (build_fr_harmonic_base's
    _paint_machined_faces_black precedent). Expectations are the full analytic
    wall/annulus areas; the 5% band absorbs the cross-screw and set-screw tap
    windows that break into the bores (~1% each) and the C1 bore-top breaks.
    """
    faces = resolve_faces(
        adapter.currentModel,
        {control.key: control.face for control in SURFACE_FINISHES},
    )
    socket_wall = math.pi * BORE_DIA * (CAP_RECESS_FLOOR_Y + HALF_H + BOSS_BELOW)
    hub_wall = (
        math.pi * GOOSENECK_BORE_DIA * (HUB_BOSS_DROP + 2.0 * HALF_H - BORE_CHAMFER)
    )
    spot_face = (
        math.pi / 4.0 * (HUB_SET_SPOT_DIA**2 - TAP_DRILL_MM[SET_SCREW_THREAD] ** 2)
    )
    for key, face in faces.items():
        if key == "hub_bore":
            expected = hub_wall
        elif key == "hub_set_spot_face":
            expected = spot_face
        else:
            expected = socket_wall
        area = float(face.GetArea()) * 1e6
        if abs(area - expected) > 0.05 * expected:
            raise RuntimeError(
                f"{key} face area {area:.0f} mm^2 != {expected:.0f} "
                "(minus tap windows and edge breaks)"
            )
        _telemetry.info(f"{key} face qualified ({area:.0f} mm^2)")


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
    # The post station is spring-stamped, not the column line (spec).
    await set_global(adapter, "GooseneckX", f"{abs(GOOSENECK_X)}mm")
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
    await set_global(adapter, "HangerGrip", f"{HANGER_GRIP}mm")
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
    #    inner faces where the crossbar + gussets butt in (x -51..21,
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

    # 5b. Crossbar T-section: two pockets either side of the WEB_T web, from
    #     the flange underside through the bottom, over |z| <= 69 (6 short of
    #     the gusset legs, clear of the knife-mount seats). Sketched on a
    #     positive-offset Top plane at the flange underside, (x, y) -> (X, -Z);
    #     its default cut runs toward -Y.
    pocket_roof = check(
        "create_plane crossbar pockets",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=FLANGE_BOT_Y
            )
        ),
    )
    pocket_roof_name = str(getattr(pocket_roof, "name", pocket_roof))
    ref_planes.append(pocket_roof_name)
    bar_pockets = SketchDims()
    check(
        "create_sketch crossbar pockets", await adapter.create_sketch(pocket_roof_name)
    )
    for k, (x_lo, x_hi) in enumerate(((BAR_X0, BAR_WEB_X0), (BAR_WEB_X1, BAR_X1))):
        pts = [
            (x_lo, -BAR_POCKET_Z),
            (x_hi, -BAR_POCKET_Z),
            (x_hi, BAR_POCKET_Z),
            (x_lo, BAR_POCKET_Z),
        ]
        pocket_lines = await add_line_chain(adapter, pts)
        await define_rectilinear_chain(
            adapter,
            pocket_lines,
            pts,
            label=f"crossbar pocket {k}",
            dims=bar_pockets,
            names=[f"BP{k}Run", f"BP{k}Rise", f"BP{k}OffX", f"BP{k}OffZ"],
        )
    await ensure_fully_defined(adapter, "crossbar pockets sketch")
    check("exit_sketch crossbar pockets", await adapter.exit_sketch())
    name_last_feature(adapter, "BarPocketProfile")
    drive_jobs += bar_pockets.apply(adapter, "BarPocketProfile")
    check(
        "cut crossbar pockets",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=RING_HEIGHT - FLANGE, reverse_direction=False)
        ),
    )
    name_last_feature(adapter, "BarPockets")
    v_bar_pockets = (
        (BAR_X1 - BAR_X0 - WEB_T) * 2.0 * BAR_POCKET_Z * (RING_HEIGHT - FLANGE)
    )  # 35397
    volume = await volume_check(
        adapter, "crossbar pockets", volume - v_bar_pockets, 50.0
    )

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
        drives=('"GooseneckX"', '"GooseneckZ"', '"HubBossDia"'),
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

    # 8. Set-screw boss on the hub rib (east outer face, -X): cast proud of
    #    the rib from the underside to the flange underside, then spot-faced
    #    1.0 deep. One Right-plane offset at the cast face x -219 carries both
    #    sketches; the boss extrudes toward +X (the gusset plane's default)
    #    back to the rib face, and the spot face cuts toward +X like the old
    #    rib-face pocket.
    boss_plane = check(
        "create_plane set boss",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=SET_BOSS_FACE_X
            )
        ),
    )
    boss_plane_name = getattr(boss_plane, "name", boss_plane)
    ref_planes.append(str(boss_plane_name))
    set_boss = SketchDims()
    check("create_sketch set boss", await adapter.create_sketch(boss_plane_name))
    half_w = HUB_SET_BOSS_W / 2.0
    # Negative-offset plane: sketch x = -(model Z) (negative-offset plane mirror -- see the module docstring).
    # The chain starts on the top edge, so SetBossWidth's points are the top
    # corners and the hub side view stands it over the rail, its extension
    # lines clear of the boss face and the set tap.
    sb_pts = [
        (-(GOOSENECK_Z - half_w), FLANGE_BOT_Y),
        (-(GOOSENECK_Z + half_w), FLANGE_BOT_Y),
        (-(GOOSENECK_Z + half_w), -HALF_H),
        (-(GOOSENECK_Z - half_w), -HALF_H),
    ]
    sb_lines = await add_line_chain(adapter, sb_pts)
    await define_rectilinear_chain(
        adapter,
        sb_lines,
        sb_pts,
        label="set boss",
        dims=set_boss,
        names=["SetBossWidth", "SetBossHeight", "SetBossOffZ", "SetBossOffY"],
    )
    await ensure_fully_defined(adapter, "set boss sketch")
    check("exit_sketch set boss", await adapter.exit_sketch())
    name_last_feature(adapter, "SetBossProfile")
    set_boss.apply(adapter, "SetBossProfile")
    boss_proud = -SET_BOSS_FACE_X - OUTER_X  # 4.9
    check(
        "extrude set boss",
        await adapter.create_extrusion(ExtrusionParameters(depth=boss_proud)),
    )
    name_last_feature(adapter, "SetBoss")
    v_set_boss = HUB_SET_BOSS_W * (FLANGE_BOT_Y + HALF_H) * boss_proud
    volume = await volume_check(adapter, "set boss", volume + v_set_boss, 20.0)
    spot = SketchDims()
    check("create_sketch set spot face", await adapter.create_sketch(boss_plane_name))
    await define_circle(
        adapter,
        -GOOSENECK_Z,
        0.0,
        HUB_SET_SPOT_DIA / 2.0,
        "set-screw spot face",
        dims=spot,
        names=("SetSpotZ", None, "SetSpotDia"),
    )
    await ensure_fully_defined(adapter, "set spot face sketch")
    check("exit_sketch set spot face", await adapter.exit_sketch())
    name_last_feature(adapter, "SetSpotProfile")
    spot.apply(adapter, "SetSpotProfile")
    spot_depth = SET_SPOT_FACE_X - SET_BOSS_FACE_X  # 1.0
    check(
        "cut set spot face",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=spot_depth, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "SetSpotFace")
    v_spot = math.pi * (HUB_SET_SPOT_DIA / 2.0) ** 2 * spot_depth
    volume = await volume_check(adapter, "set spot face", volume - v_spot, 5.0)

    # 9. Side-screw counterbores: O3/8 from the cut plane 0.4 outside the
    #    boss crown to the |z| = TOP_SCREW_SEAT_Z floor, deep enough that the
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
                0.0,
                COUNTERBORE_DIA / 2.0,
                f"counterbore {side} (x={x:+.0f})",
                dims=cbore,
                names=(f"CB{k}X", None, f"CB{k}Dia"),
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
        drives=('"GooseneckX"', '"GooseneckZ"', '"GooseneckBoreDia"'),
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

    # 12. Native #10 loose clearance plus shallow washer spotfaces, both
    #     stations in one top-face counterbore wizard feature (a #10
    #     socket-head table seed, every cut overridden: HANGER_HOLE_SPEC).
    #     Q7 preserves the shop's underside-entry through drilling and TOP
    #     spotfacing; the finished solid is independent of that sequence.
    #     A full spotface annulus remains inside the bar/rail union, including
    #     the rear rim extending into the rail above its pocket roof.
    hanger_wizard = wizard_holes(
        adapter,
        HANGER_HOLE_SPEC,
        [[HANGER_X, HALF_H, STUD_Z_FRONT], [HANGER_X, HALF_H, STUD_Z_REAR]],
        (0.0, 1.0, 0.0),
        "knife-hanger washer spotfaces",
        name="StudHoles",
        expect_dia_mm=HANGER_CLEARANCE_DIA,
        placement_dims=[
            (("StudFrontX", None), ("StudFrontZ", None)),
            (("StudRearX", None), ("StudRearZ", None)),
        ],
    )
    hanger_feature = _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(
        hanger_wizard.name,
    )
    if hanger_feature is None:
        raise RuntimeError("native hanger wizard feature disappeared")
    _tolerance_hanger_clearance(_early_bound(hanger_feature, "IFeature"))
    v_hangers = 2.0 * (
        math.pi * (HANGER_CLEARANCE_DIA / 2.0) ** 2 * RING_HEIGHT
        + math.pi
        * ((HANGER_SPOTFACE_DIA / 2.0) ** 2 - (HANGER_CLEARANCE_DIA / 2.0) ** 2)
        * HANGER_SPOTFACE_DEPTH
    )
    volume = await volume_check(
        adapter, "knife-hanger washer spotfaces", volume - v_hangers, 10.0
    )

    # 12a. HangerGrip: the governing 35.50 +/-0.05 underside-to-spotfloor
    #      grip is ONE native driving dimension in a hidden reference sketch
    #      on section F-F's cutting plane (the rear station), and the wizard's
    #      own spotface depth is bound to "RingHeight" - HangerGrip, so the
    #      floor follows that dimension alone. Its band is applied below; the
    #      sheet imports it unmodified.
    hanger_depth = _hanger_spotface_depth_name(_early_bound(hanger_feature, "IFeature"))
    grip_plane = check(
        "create_plane hanger grip reference",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=STUD_Z_REAR
            )
        ),
    )
    grip_plane_name = str(getattr(grip_plane, "name", grip_plane))
    ref_planes.append(grip_plane_name)
    drive_jobs += await _author_hanger_grip_reference(adapter, grip_plane_name)
    drive_jobs.append((hanger_depth, HANGER_SPOTFACE_DEPTH_DRIVE))

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
    #     starts on its counterbore floor, crosses the near casting wall and column
    #     bore, then continues into the far boss/centred side-rail web.
    #     Opposed holes remain one two-position Hole Wizard feature per side.
    v_side_tap = _side_tap_removal()
    for side, sign, _reverse in SIDE_SCREW_FACES:
        feat = f"SideTaps{side.capitalize()}"
        z_face = sign * COUNTERBORE_FLOOR
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
        [[SET_SPOT_FACE_X, 0.0, GOOSENECK_Z]],
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
    #     the junction lands split both front/rear window runs; the crossbar
    #     web's two roots run between its pocket ends.
    x_shelf_out = COLUMN_X + WEB_T / 2.0  # 203.5
    x_shelf_in = COLUMN_X - WEB_T / 2.0  # 190.5
    z_shelf_out = abs(FRONT_COLUMN_Z) + WEB_T / 2.0  # 118.5
    z_shelf_in = abs(FRONT_COLUMN_Z) - WEB_T / 2.0  # 105.5
    rib_lo = GOOSENECK_Z - HUB_RIB_W / 2.0  # -10.91
    rib_hi = GOOSENECK_Z + HUB_RIB_W / 2.0  # +17.09
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
                # crossbar web, both sides
                [BAR_WEB_X0, FLANGE_BOT_Y, 0.0],
                [BAR_WEB_X1, FLANGE_BOT_Y, 0.0],
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
    # top; bore and counterbore low ends stay sharp.
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

    # 18b. C2 x 45 on every remaining external convex edge (75 edges), one
    #      chamfer feature per connected chain so a native failure names its
    #      chain and each chain's volume is proved on its own (see
    #      _external_edge_breaks for the chains and the edges left unbroken).
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
    # The governing grip's band lives on the model's own driving dimension.
    set_dimension_symmetric_tolerance(
        adapter, HANGER_GRIP_SKETCH, "HangerGrip", HANGER_GRIP_TOL
    )
    volume = await volume_check(
        adapter, "driven casting (equations neutral)", volume, 200.0
    )
    await _assert_hanger_grip_drives_spotface(adapter, hanger_depth, volume)

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
    # The grip reference sketch is saved hidden (read back); the sheet shows
    # it per view to import HangerGrip.
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
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
