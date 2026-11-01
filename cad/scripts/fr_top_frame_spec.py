r"""Pure-data dimensional contract shared by the top-frame casting and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_fr_top_frame`` imports the marked-
dimension NAME map, notes and the machined-surface geometry from here;
``draw_fr_top_frame`` keeps exactly ``DRAWING_DIMENSIONS`` and imports the rest of
the casting's plan geometry from ``build_fr_top_frame`` for its view math.

2026-08-02 rederive (ch30 px measurement anchored on the 394x224 column pitch
+ GT bundle rescale + ch19 closeups): the ring absorbed the old top-crossbar
(full-height integral bar) and the gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side), grew its rails to 34.2/38.0, gained webbed
faces, proud corner bosses, side-screw taps, hanger-stud holes and the
west-rail fulcrum-keeper taps.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths
stay physical millimetres, each owned nominal the exact decimal of its
printed inch value; stations other subsystems own (the knife line, the
summing axis, the keeper fit-up) flow through unsnapped.
"""

from __future__ import annotations

from math import isclose, radians, sqrt, tan

import _config
import sm_vn_knife_hanger_stud_spec as HANGER_SCREW
import sm_vn_knife_hanger_washer_spec as HANGER_WASHER
import sm_vn_knife_mount_dowel_spec as KNIFE_DOWEL
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from _title_block_units import render_number
from _gtol_cylinder import CylinderFace
from _hole_spec import (
    CLEARANCE_MM,
    THREAD_MAJOR_MM,
    HoleSpec,
    blind_cut_dia_mm,
    drill_process,
)
from _surface_finish import SEAT_UM, SurfaceFinishControl, ra
from _cone_axis_constants import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
    SUMMING_Z,
)
from fr_frame_attachment_spec import CAP_RECESS_DEPTH, COLUMN_SOCKET_DIAMETER
from frame_column_stations import COLUMN_X

UNIT = drawing_unit("parts/fr-top-frame", _config.parts("fr-top-frame"))
IN = 25.4

# --- Machined-surface geometry ------------------------------------------------
#
# The stations and diameters the cut surfaces sit at. They live in the spec (not
# in ``build_fr_top_frame``) because a surface-finish symbol on the sheet has to be
# provenance-checked against the very face spec the casting authors -- see
# ``_drawing_contract``'s drawing-surface-finish-provenance rule. Everything
# else about the plan geometry stays in the build script.
FRONT_COLUMN_Z = FRAME_FRONT_COLUMN_Z  # -112.014
REAR_COLUMN_Z = FRAME_REAR_COLUMN_Z  # +112.014
RING_HEIGHT = 36.4998  # 1.437 rail band (ch30 p002 36.7 / p006 37.0 / ch19 img03 35.6)
HALF_H = RING_HEIGHT / 2.0  # 18.2499; band local y -18.2499..+18.2499
HANGER_CROSSBAR_WIDTH = 25.146  # .99
HANGER_CROSSBAR_WIDTH_PLACES = 2
FLANGE_THICKNESS_MM = 8.128  # .32 final top flange, including the faced right rail top
FLANGE_THICKNESS_PLACES = 2
BOSS_ABOVE = 4.4958  # .177 boss proud of the rail top (corner-crop step)
BOSS_DIA = (
    44.958  # 1.77 user ruling: all four upper/lower bosses clear the outward keeper feet
)
BORE_DIA = COLUMN_SOCKET_DIAMETER
# Every rail's web thickness, centred on its centreline (the keeper plan of
# MHA-CH-00 draws the west rail's web faces from it).
WEB_T = 13.0048  # .512 user ruling: retain loose bands plus realistic deep-drill wander
CAP_RECESS_FLOOR_Y = HALF_H + BOSS_ABOVE - CAP_RECESS_DEPTH  # 6.4389
GOOSENECK_X = -COLUMN_X  # east rail, -X crank side (summing's post station)
GOOSENECK_BORE_DIA = 17.018  # .67 the gooseneck's O15.875 sleeve slides through

# --- Gooseneck set-screw boss (east-rail hub) ---------------------------------
#
# User ruling 2026-10-12 (option (a), no jam nut): the MHA-FR-VN-52 square-head
# cup-point set screw that pinches the gooseneck's O15.875 sleeve enters the hub through a cast
# boss on the hub pad's outer face -- square-sided and blended into the rail
# under the top flange, as the ch19 img04 hub shows it -- spot-faced square
# to the tap. The spot face starts the thread square on a machined face (the
# head stands proud of it: the cup point bites the post first); it prints .XX
# from the bore axis the screw pinches across.
HUB_SET_SPOT_FROM_AXIS = 21.082  # .83
HUB_SET_SPOT_PLACES = 2
HUB_SET_BOSS_FROM_AXIS = 22.098  # .87 cast face: .04 stock over the spot face
HUB_SET_SPOT_DIA = 9.906  # .39 clears the 1/4 square head's 8.98 diagonal at its .XX minimum
HUB_SET_BOSS_W = 18.034  # .71 along the rail, centred on the tap (spot land: build)
SET_SCREW_THREAD = "1/4-20"
SET_SCREW_MAJOR_DIA = THREAD_MAJOR_MM[SET_SCREW_THREAD]  # 6.350
SET_SCREW_PITCH = 25.4 / 20.0
SET_SCREW_MIN_ENGAGEMENT_D = 1.5  # drawing-guidelines.md rule 18 (thread engagement): >= 1.5D of full thread


def _sag(radius: float) -> float:
    """A circle's sag across the set screw's major diameter."""
    return radius - sqrt(radius**2 - (SET_SCREW_MAJOR_DIA / 2.0) ** 2)


# --- Knife-hanger hex-bolt clearance holes and dowel press reams (crossbar) ---
#
# Each MHA-SM-02 knife mount hangs under the integral crossbar on one
# cut-to-length #10-24 plain hex bolt (MHA-SM-VN-52). Its SAE washer bears on
# the FACED top plane; the block's top seat bears on the FINISHED
# underside. Owner ruling 2026-10-24 (T+H3): the two MHA-SM-VN-53 dowels
# PRESS into this soft casting, each to the flat floor of a blind ream cut
# from the faced underside, with a knockout drilled up from that floor on
# the ream's drawn axis to the faced top, its coaxiality the title block's
# implied ±.005, charged in the floor land (.0124, machinist exception
# RV-06, owner ruling 2026-10-27) (drawing-guidelines.md rule 16, a
# pressed dowel needs a way out; the dt_crankshaft K0 precedent).  The
# round slip hole and the slot that absorbs the pair's spacing mismatch
# (rule 19) moved to the hardened MHA-SM-02 block (``sm_knife_mount_spec``).
_XX = printed_band_mm(2, unit=UNIT)
_XXX = printed_band_mm(3, unit=UNIT)
# The title block's DRILLED HOLES row: a drilled hole cuts up to this oversize.
DRILL_OVERSIZE = drilled_oversize_mm(unit=UNIT)
# ASME B18.2.8 Table 2: #10 loose, .238 in = 6.0452 mm, rounded to the
# repository's three-place clearance-table precision.
HANGER_CLEARANCE_DIA = CLEARANCE_MM[("#10", "loose")]  # 6.045
HANGER_CLEARANCE_DIA_PLACES = 3
# Explicit manufactured acceptance: never undersize the ANSI loose minimum.
HANGER_CLEARANCE_DIA_BAND = (0.1016, 0.0)  # +.004/0 (upper, lower), not a supplier guarantee
HANGER_CLEARANCE_DIA_MIN = HANGER_CLEARANCE_DIA + min(HANGER_CLEARANCE_DIA_BAND)
HANGER_CLEARANCE_DIA_MAX = HANGER_CLEARANCE_DIA + max(HANGER_CLEARANCE_DIA_BAND)
# The finished top-to-underside grip. User ruling 2026-10-14: the whole top
# except the four corner bosses is faced on the plane the model already
# carries, so the grip is the crossbar's own full-height extrude,
# HangerGrip@Crossbar, driven by the "RingHeight" global and imported in
# section F-F. Owner ruling 2026-10-18 (machinist review r1, rule 4/19): the
# grip prints under the title block's general band; the MHA-SM-VN-52 bolt is
# cut to the measured grip at MHA-SM-00 fit-up (build_sm_summing_assembly), so
# no tightened band rescues its thread engagement.  #290: 1.437 at .XXX, the
# inch grid's nearest to the 36.5 the summing chain's stations assume.
HANGER_GRIP = RING_HEIGHT
HANGER_GRIP_PLACES = 3
HANGER_GRIP_TOL = printed_band_mm(HANGER_GRIP_PLACES, unit=UNIT)  # 0.127, title block .XXX
# A plain native Hole Wizard clearance row, drilled through from the faced
# underside. A plain hole ignores HoleFit, so _holes.wizard_holes writes the
# pinned #10 loose 6.045 to both diameter knobs whenever the table seeds
# another size; the build reads the exact cut diameter back.
HANGER_HOLE_SPEC = HoleSpec("clearance", "#10", fit="loose")
# Washer bounds are ASME B18.21.1 Table 11, owned by the purchased-part spec.
# Full washer float uses the sourced UNC 2A minimum shank diameter, not
# nominal thread-major geometry, charging the full washer eccentricity.
HANGER_WASHER_FLOAT_MAX = (HANGER_WASHER.ID_MAX - HANGER_SCREW.SHANK_DIA_MIN) / 2.0
HANGER_WASHER_CONCENTRIC_ANNULUS_MIN = (
    HANGER_WASHER.OD_MIN - HANGER_CLEARANCE_DIA_MAX
) / 2.0
if HANGER_WASHER_CONCENTRIC_ANNULUS_MIN <= 0.0:
    raise AssertionError("knife-hanger washer lacks a bearing annulus round its hole")
# The dowel press reams: at each hanger station both dowel holes are blind
# flat-floor reams cut KNIFE_DOWEL.PRESS_DEPTH up from the faced underside
# to the dowel spec's press band, .1240 +.0005/0 printed .XXXX (press
# .0006-.0013 on the catalogue pin), four in all.
HANGER_PIN_X = KNIFE_DOWEL.HANGER_OFFSET  # 7.62 (.300) either side of the bolt axis
# The pair's stations from the screw axis in the dowel spec's order: the -X
# ream, then the +X ream (datum B front, C rear).
HANGER_PIN_XS = (-HANGER_PIN_X, HANGER_PIN_X)
# The hanger stations in part coordinates, which the builder cuts and the
# drawing locates (AGENTS.md: drawings read pure providers, not the
# builder): the crossbar centreline (the knife's x) and the two screw axes
# either side of the summing axis by the knife-mount trunnion mid offset
# (build_sm_summing_assembly); each station's reams, -X then +X.  The knife
# line and the summing stations are the summing subsystem's: they flow
# through unsnapped.
HANGER_X = -15.0
HEX_Z_MID = 87.06
STUD_Z_FRONT = SUMMING_Z - HEX_Z_MID  # -83.972
STUD_Z_REAR = SUMMING_Z + HEX_Z_MID  # +90.148
PIN_HOLE_NEG_X, PIN_HOLE_X = (HANGER_X + x for x in HANGER_PIN_XS)  # -22.62, -7.38
HANGER_PIN_X_PLACES = KNIFE_DOWEL.HANGER_OFFSET_PLACES
HANGER_PIN_X_TOL = KNIFE_DOWEL.HANGER_OFFSET_TOL  # 0.127
HANGER_PIN_HOLE_DIA = KNIFE_DOWEL.PRESS_HOLE_DIA  # 3.1496
HANGER_PIN_HOLE_DIA_BAND = KNIFE_DOWEL.PRESS_HOLE_DIA_BAND  # (0.0127, 0.0)
HANGER_PIN_HOLE_DIA_PLACES = KNIFE_DOWEL.PRESS_HOLE_DIA_PLACES
HANGER_PIN_HOLE_DIA_MIN = HANGER_PIN_HOLE_DIA + min(HANGER_PIN_HOLE_DIA_BAND)
HANGER_PIN_HOLE_DIA_MAX = HANGER_PIN_HOLE_DIA + max(HANGER_PIN_HOLE_DIA_BAND)
HANGER_PIN_HOLE_DEPTH = KNIFE_DOWEL.PRESS_DEPTH  # 11.938, from the underside
HANGER_PIN_HOLE_DEPTH_PLACES = KNIFE_DOWEL.PRESS_DEPTH_PLACES
HANGER_PIN_HOLE_DEPTH_TOL = KNIFE_DOWEL.PRESS_DEPTH_TOL  # 0.254
# Each +X ream (datum B front, C rear) stands .XXX HANGER_PIN_X from its own
# screw axis along the dowel line.  Each -X ream is located from the +X
# ream beside it by a BASIC KNIFE_DOWEL.SPAN (.600) along the line, the
# zero across it implied (both reams drawn on one line), and held there by
# a cylindrical position zone (machinist review, farm run 4: a position
# frame needs a BASIC locating its feature).  The knife mount fits turned
# 180 deg too (its round hole on the -X ream), so that ream's worst station
# from its screw axis is the +X band plus the zone's radius
# (HANGER_NEG_PIN_X_TOL), and the knife mount's slot takes the span's zone
# as travel (KNIFE_DOWEL.SPAN_TOL).
# Manufacturing GD&T limits consumed by the part's drawing projection: each
# -X ream's position, Ø.002, to the +X ream beside it (datum B front, C
# rear) as primary, oriented by the other station's +X ream with its
# location released (translation modifier: the stations' fore/aft spacing is
# toleranced, not BASIC), so the two mounts' dowel lines stay square to the
# B-C line.  All four reams are also perpendicular, Ø.0008, to the faced
# underside (datum A) the knife mounts seat on, so each pressed dowel stands
# square to its block's top seat (owner ruling 2026-10-27 (#2016), option A;
# the block's hole and slot take ⊥Ø.0006|A).  The values stay literals (the
# FCF provenance scan reads them): the inch strings print, the millimetres
# derive from them.
# The keeper seats carry no frame: rule 5 names flatness on a clamp face
# over-specification and no user ruling accepts one (codex review of
# 06d0bbc59); the faced top (RV-03) carries them.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "knife-hanger press ream position": ".002",
    "knife-hanger crossbar centring": ".004",
    "knife-hanger press ream perpendicularity": ".0008",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * IN for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
HANGER_CROSSBAR_CENTER_ZONE = float(
    GEOMETRIC_TOLERANCES_MM["knife-hanger crossbar centring"]
)
HANGER_CROSSBAR_CENTER_TOL = HANGER_CROSSBAR_CENTER_ZONE / 2.0
HANGER_PRESS_HOLE_POSITION_TOL = float(
    GEOMETRIC_TOLERANCES_MM["knife-hanger press ream position"]
)
if not isclose(HANGER_PRESS_HOLE_POSITION_TOL / 2.0, KNIFE_DOWEL.SPAN_TOL):
    raise AssertionError(
        "the -X reams' position zone radius must be MHA-SM-VN-53's span band"
    )
HANGER_NEG_PIN_X_TOL = HANGER_PIN_X_TOL + HANGER_PRESS_HOLE_POSITION_TOL / 2.0  # 0.1524
# The B-C datum line's yaw (codjiflo round 4): the front and rear +X reams'
# own .XXX stations, at opposite limits, turn the line through B and C by
# 2 x .005 over the stations' spacing; each -X ream is located to that line,
# so the pin pair turns with it, and the block's tap, .300 from B along the
# pair, moves across the dowel line by that turn times its reach.
HANGER_DATUM_LINE_YAW_SHIFT = (
    KNIFE_DOWEL.HANGER_OFFSET * 2.0 * HANGER_PIN_X_TOL / (STUD_Z_REAR - STUD_Z_FRONT)
)  # 0.0111
HANGER_PRESS_HOLE_PERPENDICULARITY_TOL = float(
    GEOMETRIC_TOLERANCES_MM["knife-hanger press ream perpendicularity"]
)
# An orientation refinement of a located feature is tighter than its
# location zone (the -X reams' Ø.002 position).
if not HANGER_PRESS_HOLE_PERPENDICULARITY_TOL < HANGER_PRESS_HOLE_POSITION_TOL:
    raise AssertionError("the reams' perpendicularity must refine their position zone")
# The drilled #10 hole's float about the bolt shank is 0.6095 radial.
# The assembly proves the tap/dowel mismatch plus underside-entry drill
# drift stays inside that float.
HANGER_SCREW_FLOAT = (HANGER_CLEARANCE_DIA - HANGER_SCREW.SHANK_DIA) / 2.0
# Each ream's knockout (rule 16): a #51 drill up from the ream's floor,
# drawn on the ream's axis, through to the faced top, so a 1/16 in pin
# punch drives the dowel back out of the underside.  The ream keeps its
# depth, so the dowel still bottoms on the annular floor the knockout
# leaves.  It is pressed chamfer end first, so it bears on that end's flat
# face, at least ASME B18.8.2's smallest point diameter
# (KNIFE_DOWEL.POINT_DIA_MIN, Ø2.794; codjiflo round 4: the vendor model's
# Ø2.921 is that band's middle), and never past the floor's flat, which
# ends at the corner radius the depth's callout limits
# (HANGER_PIN_FLOOR_CORNER_R_MAX): the smaller of the two, less the largest
# printed knockout (its three-place size under the DRILLED HOLES row), less
# the knockout's offset from the ream's axis at the floor
# (HANGER_KNOCKOUT_FLOOR_ECCENTRICITY, the drawn coaxiality's worst case),
# is the contacted land (HANGER_PIN_FLOOR_BEARING_LAND_MIN, .0124, under
# the 0.4 target by owner ruling 2026-10-27); the floor's metal ring, out
# to the smallest ream, is wider (HANGER_PIN_FLOOR_LAND_MIN).  Drilled from
# the top, the two holes' opposing wander (0.135 + 0.067) left a #43
# knockout 0.200 (codjiflo, PR #1978); from the floor a #47 still bore only
# 0.346 on the vendor flat (codjiflo round 3) and a #50 0.391 on B18.8.2's
# smallest (round 4), both with the knockout drilled in the ream's setup,
# so the knockout stepped down to #51.  It runs from the floor at its
# shallowest printed depth to the top at the grip's far limit, its own
# drift greatest at the top (``build_fr_top_frame``).
HANGER_KNOCKOUT_SPEC = HoleSpec("drilled_number", "#51")
HANGER_KNOCKOUT_DIA = blind_cut_dia_mm(HANGER_KNOCKOUT_SPEC)  # 1.702, the model
# The native callout prints the inch sheet's three places, so the DRILLED
# HOLES +.004/0 row governs the printed .067: .067..071, the #51's 1.702
# inside it; the proofs charge the printed maximum.
HANGER_KNOCKOUT_DIA_PLACES = 3
_KNOCKOUT_PRINTED_DEVIATIONS = printed_deviations(
    HANGER_KNOCKOUT_DIA, HANGER_KNOCKOUT_DIA_PLACES, (0.0, DRILL_OVERSIZE), unit=UNIT
)
HANGER_KNOCKOUT_DIA_PRINTED = HANGER_KNOCKOUT_DIA + _KNOCKOUT_PRINTED_DEVIATIONS[0]  # 1.7018
HANGER_KNOCKOUT_DIA_MAX = HANGER_KNOCKOUT_DIA + _KNOCKOUT_PRINTED_DEVIATIONS[1]  # 1.8034
if not HANGER_KNOCKOUT_DIA_PRINTED <= HANGER_KNOCKOUT_DIA <= HANGER_KNOCKOUT_DIA_MAX:
    raise AssertionError("the #51 drill lies outside the knockout's printed band")
HANGER_KNOCKOUT_PUNCH_DIA = KNIFE_DOWEL.MM_PER_IN / 16.0  # 1/16 in pin punch, 1.5875
if HANGER_KNOCKOUT_PUNCH_DIA >= HANGER_KNOCKOUT_DIA_PRINTED:
    raise AssertionError("the 1/16 in pin punch does not pass the knockout")
HANGER_KNOCKOUT_LENGTH = RING_HEIGHT - HANGER_PIN_HOLE_DEPTH  # 24.5618
HANGER_KNOCKOUT_LENGTH_MAX = (
    HANGER_GRIP + HANGER_GRIP_TOL - (HANGER_PIN_HOLE_DEPTH - HANGER_PIN_HOLE_DEPTH_TOL)
)  # 24.9428
# Making it (codjiflo round 6): the #51 reaches its top through the ream's
# air, from the underside to the faced top at the grip's far limit, 36.63,
# its cut a ~15 D run from the shallowest floor; a jobber #51 (3/4 in
# flute) falls short, so the shop's tool is a taper-length #51 pecked in
# the cast iron, 2 in flute and 3-3/4 in overall (Cleveland HSS taper
# length, MSC Direct 63725519:
# https://www.mscdirect.com/product/details/63725519), its flutes clearing
# the whole depth.
HANGER_KNOCKOUT_DRILL_REACH = HANGER_GRIP + HANGER_GRIP_TOL  # 36.6268 from the underside
HANGER_KNOCKOUT_DEPTH_D = HANGER_KNOCKOUT_LENGTH_MAX / HANGER_KNOCKOUT_DIA_PRINTED  # 14.7
HANGER_KNOCKOUT_DRILL_FLUTE_LEN = 2.0 * KNIFE_DOWEL.MM_PER_IN  # 50.8, taper-length #51
if HANGER_KNOCKOUT_DRILL_FLUTE_LEN <= HANGER_KNOCKOUT_DRILL_REACH:
    raise AssertionError("the taper-length #51's flutes do not clear the knockout's depth")
# Removing a dowel: a 1/16 in punch enters the knockout at the faced top and
# drives the pin out until its pressed end leaves the underside, so its
# shank, under the .067 knockout, needs the full top-to-underside reach,
# 36.63 at the grip's far limit: the knockout's run plus the push-out, which
# sum to the grip whatever the floor's depth.  A common 1/16 in pin punch
# carries about 25 mm of tip, so the tool is an extra-long 1/16 in pin punch
# or a 1/16 in drill-rod drift with at least that much free length.
HANGER_KNOCKOUT_PUNCH_REACH_MIN = HANGER_GRIP + HANGER_GRIP_TOL  # 36.6268, no ream depth
# Callouts on the model's own ream size and depth (drawing-guidelines.md
# rule 4: a REAM names its mate and fit; rule 12: count, process and
# purpose; the size and its band print natively).  The underside locator
# carries the ream size, its count, mate and press on one row under it; F-F
# the depth all four share, to a flat floor.  The knockouts' native callout
# reads its drill above the native size and its purpose below
# (dt_crankshaft_notes.KNOCKOUT_CALLOUT_*).
HANGER_PIN_HOLE_CALLOUT = "4X REAM, PRESS MHA-SM-VN-53 DOWEL TO FLOOR"
# The flat floor's corner: the title block's inside-corner radius would
# leave the dowel's end flat bearing on a fillet, so the depth's row limits
# it (numbers in a native dimension's callout row: the knife mount's
# ".0020-.0036 DIAMETRAL CLEARANCE" precedent).  The dowel's spec owns the
# limit with the ream it bounds (codjiflo round 5).
HANGER_PIN_FLOOR_CORNER_R_MAX = KNIFE_DOWEL.PRESS_FLOOR_CORNER_R_MAX
# Three rows: one "CORNER R.003 MAX" row overran F-F's band between the
# depth's line and the title block.
HANGER_PIN_DEPTH_CALLOUT = (
    f"4X FLAT BOTTOM,\nCORNER\nR{render_number(HANGER_PIN_FLOOR_CORNER_R_MAX / IN, UNIT, 3)} MAX"
)
# The knockout's process row names the drill only (machinist review, farm
# run 20261027T175429300Z: "REAM SETUP" was a method, not a requirement;
# owner ruling 2026-10-27); the row under the native size names its start,
# the floor.  The drawn common axis is its only location to the ream.
HANGER_KNOCKOUT_CALLOUT_ABOVE = drill_process(HANGER_KNOCKOUT_SPEC)
HANGER_KNOCKOUT_CALLOUT_BELOW = "FROM REAM FLOOR;\nMHA-SM-VN-53 KNOCKOUT"

# Full thread in the hub at the printed worst case (dt_arbor_pedestal_spec's
# terms): the thread is full only where its major circle lies wholly in metal,
# so the bore's sag across the hole is lost, and so is the one-pitch entry
# chamfer; the flat spot face loses none. The spot face sits at the near end
# of its .XX band, the bore at the larger of its printed .XX band and the title
# block's drilled row.
_GOOSENECK_BORE_RADIUS_MAX = (GOOSENECK_BORE_DIA + max(_XX, DRILL_OVERSIZE)) / 2.0
SET_SCREW_THREAD_TERMS = {
    "spot face from bore axis at its minimum": HUB_SET_SPOT_FROM_AXIS
    - printed_band_mm(HUB_SET_SPOT_PLACES, unit=UNIT),
    "bore radius at its maximum": -_GOOSENECK_BORE_RADIUS_MAX,
    "bore sag across the thread": -_sag(_GOOSENECK_BORE_RADIUS_MAX),
    "one-pitch entry chamfer": -SET_SCREW_PITCH,
}
SET_SCREW_FULL_THREAD_MIN = sum(SET_SCREW_THREAD_TERMS.values())  # 10.32
SET_SCREW_FULL_THREAD_NOMINAL = (
    HUB_SET_SPOT_FROM_AXIS
    - GOOSENECK_BORE_DIA / 2.0
    - _sag(GOOSENECK_BORE_DIA / 2.0)
    - SET_SCREW_PITCH
)  # 10.69
SET_SCREW_ENGAGEMENT_D = SET_SCREW_FULL_THREAD_MIN / SET_SCREW_MAJOR_DIA  # 1.62D
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"hub set screw keeps {SET_SCREW_ENGAGEMENT_D:.2f}D of full thread "
        f"at the printed worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )


# --- Machining-required surfaces ---------------------------------------------
#
# These four faces own native finish controls. The top plane between the
# corner bosses, which seats both MHA-CH-07 keepers on the right (west) rail
# and both MHA-SM-VN-54 washers on the crossbar, and the underside plane between
# the bosses, which seats both MHA-SM-02 knife mounts, carry SEAT_UM in the
# linked facing notes below: each is one plane, so its note names the extent
# instead of a split-line region. The locating-seat finish is not a general
# grade.
#
# * The four tube-socket bores take the MHA-FR-03 columns on a match-fitted close
#   hand-slip; a cast bore wall cannot hold that fit and would score the tube.
# * The four cap-recess floors carry no finish: each MHA-FR-VN-54 cap seats on
#   its tube end (build_fr_frame_assembly asserts it), 1.5 mm above the floor,
#   so the recess only clears the cap skirt.
# * The gooseneck bore (a drilled hole the set screw clamps the post in) and
#   the set-screw spot face (a clamp face) neither run nor locate, so they
#   carry no symbol (machinist review r1, 2026-10-18; drawing-guidelines.md
#   rule 6).
#
# SEAT grade throughout: nothing runs on these surfaces continuously, so the
# commercial machine finish is what the fit needs. Each controlled face has
# a native model symbol; each drawing family appears once with a target label.
SOCKET_BORE_TARGET = "TUBE SOCKET BORES, 4X"
SURFACE_FINISHES = tuple(
    SurfaceFinishControl(
        f"socket_{rail}_{end}",
        SEAT_UM,
        CylinderFace(BORE_DIA, contains_x_mm=x, contains_z_mm=z),
        production_method=SOCKET_BORE_TARGET,
        display_unit=UNIT,
    )
    for rail, x in (("east", GOOSENECK_X), ("west", COLUMN_X))
    for end, z in (("front", FRONT_COLUMN_Z), ("rear", REAR_COLUMN_Z))
)


# --- Marked-dimension contract -------------------------------------------------
#
# The hole sizes remain associative callouts; named Hole Wizard placement
# dimensions expose the stations without duplicating those sizes.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth", "WinWidth", "WinDepth"},
    "WebProfile": {
        "WebOuterWidth",
        "WebOuterDepth",
        "WebInnerWidth",
        "WebInnerDepth",
    },
    # The rail height is the same finished thickness as the grip: the web
    # ring's own depth, printed in the geometry front view as a reference.
    "WebRing": {"RingHeight"},
    "Crossbar": {"HangerGrip"},
    "BossUpProfile": {"C0Dia"},
    "BossesUpper": {"BossTopExtent"},
    "BossesLower": {"BossBottomExtent"},
    "BoreProfile": {"B0X", "B0Z", "B0Dia"},
    "CounterboreRearProfile": {"CB1Dia"},
    "BarProfile": {
        "BarAnchorX",
        "BarAnchorZ",
        "BarFootSpan",
        "GussetRunE",
        "BarSideE",
    },
    "HubBossProfile": {"HubDia"},
    "HubBoss": {"HubBossExtent"},
    "RibProfile": {"RibWidth"},
    "SetBossProfile": {"SetBossWidth"},
    "SetSpotProfile": {"SetSpotDia"},
    "GooseneckTap": {"SetTapZ"},
    "GooseneckProfile": {"GnDia", "GnX", "GnZ"},
    # The hanger-hole and keeper-tap placement dims (StudFrontX ...,
    # KeeperFrontX ...) are NOT marked: a Hole Wizard placement sketch
    # measures from the origin -- mid-air on the print -- so sheet 3
    # dimensions those stations from the socket bore axes with sheet-derived
    # dimensions (DRAWING_REFERENCE_PRECISION below, drawing-guidelines.md rule 10 (dimension from a real feature)).  The
    # dowel reams' stations (the +X ream from the screw axis, the -X ream
    # from the +X ream) are sheet-derived the same way, on section F-F; the
    # ream size is the model's, printed on the underside locator, and the
    # depth the model's, printed on F-F.  The knockouts print their native
    # Hole Wizard callout.
    "CapRecessProfile": {"CapRecessDia"},
    "CapRecesses": {"CapRecessDepth"},
    "HangerPinProfile": {"HangerPinHoleDia"},
    "HangerPinHoles": {"HangerPinHoleDepth"},
}


# --- Decimal places, authored ON THE PART -------------------------------------
#
# drawing-simplicity-policy.md `How the repository implements the guidelines`: the places a dimension prints are part of the tolerance it
# claims, and the model owns both.  ``build_fr_top_frame`` applies this table
# natively (``_drawing_precision.apply_drawing_precision``) right after the drawing
# marks, so ``draw_fr_top_frame`` imports each dimension verbatim and only reads
# ``GetPrimaryPrecision2()`` back off the sheet.
#
# The title block's .XX is this casting's routine band; .XXX appears where a
# wall, fit or stack reads the dimension, or where the X-direction faces
# stand off the 15.512 socket pitch (only a .001 grid closes both the rail
# and window widths on it).  Keeper positions are model-nominal references
# only: the frame taps are transferred from the bench-pair-reamed,
# fit-up-located keeper feet, not independently located to the general band.
# The cap recess diameter and depth carry the bilateral bands above, the
# gooseneck bore prints the clearance a purchased post is set into, the
# finished grip prints .XXX (the rail height, that same thickness, prints its
# reference at the grip's places), and the dowel press ream holds its own
# +.0005/0 band at four places.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OuterProfile": {"Width": 3, "Depth": 2, "WinWidth": 3, "WinDepth": 2},
    "WebRing": {"RingHeight": HANGER_GRIP_PLACES},
    "Crossbar": {"HangerGrip": HANGER_GRIP_PLACES},
    "BossUpProfile": {"C0Dia": 2},
    "BoreProfile": {"B0Dia": 3},
    "CounterboreRearProfile": {"CB1Dia": 3},
    "BarProfile": {"GussetRunE": 2},
    "HubBossProfile": {"HubDia": 2},
    "RibProfile": {"RibWidth": 2},
    "SetBossProfile": {"SetBossWidth": 2},
    "SetSpotProfile": {"SetSpotDia": 2},
    "GooseneckProfile": {"GnDia": 2},
    "CapRecessProfile": {"CapRecessDia": 3},
    "CapRecesses": {"CapRecessDepth": 3},
    "HangerPinProfile": {"HangerPinHoleDia": HANGER_PIN_HOLE_DIA_PLACES},
    "HangerPinHoles": {"HangerPinHoleDepth": HANGER_PIN_HOLE_DEPTH_PLACES},
}

# The drawing reads this flat view back off the sheet: a dimension name is
# unique across the features that expose one, and a marked dimension nobody
# authored places for would otherwise print SolidWorks' template default.
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a drawing-precision dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"{_feature}: precision authored for unmarked dimensions {_unmarked}"
        )


# --- Decimal places for the dimensions the SHEET derives ----------------------
#
# drawing-simplicity-policy.md `How the repository implements the guidelines`'s one exception.  Some numbers on this print are distances between two
# model faces that no single model dimension expresses: a web thickness that is
# the difference of two profile offsets, a flange thickness between two extrude
# extents, a boss stack that sums three, a chamfer leg, a counterbore-floor
# separation, a ramp angle.  Their VALUE is still the model's -- every one is
# measured in the view and the build fails if the geometry moved -- but there is
# no model dimension to carry the places, so the places live here, in the part's
# own contract, instead of as a literal in the drawing script.  Keyed by the
# recipe's own dimension label.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    # Sheet 1, GEOMETRY: envelope, windows, T-rail section H-H and side
    # section E-E with the crossbar T and its pockets -- cast stock under the
    # title block's general band.  The X-direction envelope and windows stand
    # off the 15.512 socket pitch and the knife line, so they print .XXX as
    # those stations flow through; the webs print the receiver walls' .512
    # (KEEPER_TAP_*_WALL_MARGIN reads it), and the pocket depth is the .XXX
    # grip less the flange.
    "overall casting width": 3,
    "overall casting depth": 2,
    "side flange width": 2,
    "left window clear width": 3,
    "right window clear width": 3,
    "crossbar flange width": HANGER_CROSSBAR_WIDTH_PLACES,
    "rail web thickness": 3,
    "front rear flange width": 2,
    "top flange thickness": FLANGE_THICKNESS_PLACES,
    "top rim chamfer": 2,
    "T rail root radius": 2,
    "side rail web thickness": 3,
    "crossbar web thickness": 3,
    "crossbar flange thickness": FLANGE_THICKNESS_PLACES,
    "crossbar pocket depth": 3,
    # Sheet 2, HOLES-SOCKETS: the socket pitches are the setup datums the
    # column plan is drilled from, stated as MHA-FR-01 states them.
    "socket horizontal pitch": 3,
    "socket vertical pitch": 2,
    # Hole stations baseline from socket axes (X from the left pair, Z from
    # the upper pair).  The knife line, summing axis and keeper fit-up are
    # other subsystems' stations: they print .XXX as they flow through.
    # "hanger x" locates datum D (the crossbar median), and the position
    # frame holds the hanger axes BASIC zero on D; keeper coordinates are
    # reference-only guides to assembly-transferred taps.
    "hanger x from left sockets": 3,
    "front hanger z from upper sockets": 3,
    "rear hanger z from upper sockets": 3,
    "keeper x from left sockets": 3,
    "front keeper z from upper sockets": 3,
    "rear keeper z from upper sockets": 3,
    # Sheet 3, CROSS-TAPS: boss stack, cap-mouth chamfer, opposed counterbore
    # floors and the tap axis below the boss top.
    "socket boss overall height": 3,
    "boss top above rail top": 3,
    "top bore mouth chamfer": 2,
    "opposed counterbore floor separation": 2,
    "cross screw axis from boss top": 3,
    # .XX, the floor at .65 (fr_frame_attachment_spec.TOP_SCREW_SEAT_Z):
    # over the .080 target to the cap recess at every printed corner
    # (build_fr_top_frame.COUNTERBORE_PRINTED_CAP_LIGAMENT).
    "counterbore floor from socket axis": 2,
    # Sheet 5, HUB-SET-SCREW: hub station, set-tap axis, gusset ramp and the
    # removed set-screw boss section K-K (spot face, boss face, thread run).
    "hub from left front socket": 3,
    "set screw axis from rail top": 3,
    "hub boss underside drop": 2,
    "hub gusset feather span": 2,
    "hub gusset ramp angle": 1,
    "set-screw spot face from bore axis": HUB_SET_SPOT_PLACES,
    "set-screw thread length": 3,
    "set-screw boss face from bore axis": 2,
    # Sheet 6, UNDERSIDE: junction lands and knife-hanger section F-F.  The
    # native finished-top grip and ream depth are imported; the +X ream's
    # station and the -X ream's BASIC span from it are measured.
    "land end from crossbar face": 2,
    "crossbar pocket length": 2,
    "crossbar pocket from front socket": 2,
    "underside gusset thickness": 2,
    "dowel hole from hanger axis": HANGER_PIN_X_PLACES,
    "-X dowel ream from +X dowel ream": HANGER_PIN_X_PLACES,
}

# Use the canonical printed-band reader, not the unrounded inch grades.
PRINTED_LINEAR_BAND_MM = {
    places: printed_band_mm(places, unit=UNIT) for places in (1, 2, 3)
}
PRINTED_DRILLED_HOLE_PLUS_MM = drilled_oversize_mm(unit=UNIT)


def printed_limit(value: float, places: int, sign: float) -> float:
    """``value`` at the far (``sign`` > 0) or near limit the sheet allows when
    it prints ``value`` at ``places`` under the general band."""
    lower, upper = printed_deviations(value, places, unit=UNIT)
    return value + (upper if sign > 0.0 else lower)


# Native Hole Wizard variables print the inch sheet's three places.
KEEPER_TAP_CALLOUT_PRECISION = {
    "hw-tapdrldia": 3,
    "hw-tapdrldepth": 3,
    "hw-threaddepth": 3,
}
# drawing-guidelines.md rule 17 (walls and webs) receiver-wall stack: realistic angular drift through the FULL
# printed cylindrical pilot depth, without relying on a precision drill jig.
KEEPER_TAP_DRILL_WANDER_DEG = 0.3
# The same allowance as a lateral drift per mm from a hole's entry face: the
# knife-hanger holes and reams, cut from the faced underside, and the
# knockouts, drilled up from the ream floors, charge it at the depth each
# wall is judged (``build_fr_top_frame``).
DRILL_DRIFT_PER_MM = tan(radians(KEEPER_TAP_DRILL_WANDER_DEG))  # 0.00524
# The knockout floor land (see HANGER_KNOCKOUT_SPEC).  The print locates
# each knockout on its ream only by the drawn common axis (owner ruling
# 2026-10-27: no method note, no frame), so its real worst case is the
# title block's implied zero at the .XXX ±.005, per axis, of the knockout's
# axis from the ream's: up to hypot(.005, .005) off the ream's floor centre.
# The ream's own drift moves its floor centre, the pressed dowel's axis and
# its derived axis together, so it adds nothing here; it does add to where
# the knockout stands off its station (``build_fr_top_frame``'s walls).
HANGER_KNOCKOUT_COAXIAL_TOL = _XXX  # per axis, 0.127
HANGER_KNOCKOUT_FLOOR_ECCENTRICITY = sqrt(2.0) * HANGER_KNOCKOUT_COAXIAL_TOL  # 0.180
# The floor's metal ring, out to the smallest ream.
HANGER_PIN_FLOOR_LAND_MIN = (
    HANGER_PIN_HOLE_DIA_MIN - HANGER_KNOCKOUT_DIA_MAX
) / 2.0 - HANGER_KNOCKOUT_FLOOR_ECCENTRICITY  # 0.493
# The land the dowel's end flat bears on: the pressed end's chamfer touches
# nothing, so the smaller of the flat (B18.8.2's smallest point) and the
# floor's flat inside its largest corner radius bounds the contact.
HANGER_PIN_FLOOR_BEARING_R = min(
    KNIFE_DOWEL.POINT_DIA_MIN / 2.0,
    HANGER_PIN_HOLE_DIA_MIN / 2.0 - HANGER_PIN_FLOOR_CORNER_R_MAX,
)  # 1.397, the point
HANGER_PIN_FLOOR_BEARING_LAND_MIN = (
    HANGER_PIN_FLOOR_BEARING_R
    - HANGER_KNOCKOUT_DIA_MAX / 2.0
    - HANGER_KNOCKOUT_FLOOR_ECCENTRICITY
)  # 0.315
# The contacted-land target (dt_crankshaft DRIVE_PIN_FLOOR_LAND_WORST).  The
# owner ruling 2026-10-27 accepts the sub-0.4 land this knockout leaves at
# the drawn coaxiality's worst case (machinist exception RV-06, kind minor,
# in cad/config/parts/fr-top-frame.yaml): the dowel must still bottom on a
# continuous land, so only a positive land is required.
HANGER_PIN_FLOOR_BEARING_LAND_TARGET = 0.4
if HANGER_PIN_FLOOR_BEARING_LAND_MIN <= 0.0:
    raise AssertionError(
        "the knockout leaves the pressed MHA-SM-VN-53's end flat no bearing land"
        f" ({HANGER_PIN_FLOOR_BEARING_LAND_MIN:.3f})"
    )

# B18.8.2's largest point runs past the floor's flat at the smallest ream
# and largest corner (1.524 > 1.4825): its edge meets the fillet and the end
# stands off the floor by about 0.009, which the dowel's spec charges to its
# longest proud length (KNIFE_DOWEL.PROUD_MAX).
HANGER_PIN_FLOOR_FILLET_LIFT_MAX = KNIFE_DOWEL.PRESS_FLOOR_LIFT_MAX

# The nominal socket geometry stays fixed; the assigned actual tube governs fit
# (the socket callout names the mate and the acceptance; the frame assembly
# MHA-FR-00 carries the corner match marks).
# User rulings 2026-10-14 and 2026-10-18 (aesthetics; exception RV-04): the
# base's 1/16 in x 45 general break (printed at the base rim break's one
# place, 1.6) overrides the title block's 0.25 max break on the convex casting
# edges the model chamfers; hole, bore, counterbore, tap and slot mouths keep
# the title-block break (the counterbore and tap walls are proved without a
# chamfer).  The edges too close to a feature, too short or on too narrow a
# flange shelf at the print's limits, or under a knife seat, for it
# (build_fr_top_frame._external_edge_breaks) are the "UNLESS NOTED": E-E's
# note names the crossbar flange's underside, the hub side view's the hub
# rib's inner bottom, its outer bottom beside the set-screw boss and the
# V-gussets, the underside locator's the bar and gusset bottoms at the knife
# seats; they keep the title block break.  The third row says what "SHARP"
# on those notes means (machinist review r1: it read as cancelling the
# title block's burr removal too).
# Owner ruling 2026-10-18 (exception RV-02, #1625): the cast inside corners
# the model leaves sharp (window corners, flange junctions) take the casting's
# own root radius at most; the R.12 T-roots are dimensioned (the "UNLESS
# NOTED").  No geometry change.  #290: the 1/16 in break is non-functional
# stock relief, so it prints .06 at .XX with the model on it (Main's
# fleet-wide ruling; it supersedes B6's .063): every clearance that charges
# its leg holds at .06 + .01 (build_fr_top_frame.EDGE_BREAK_PRINTED_MAX).
EDGE_CHAMFER = 1.524  # .06 legs
INSIDE_CORNER_R_MAX = 3.048  # .12
_EDGE_CHAMFER_TEXT = render_number(
    EDGE_CHAMFER / IN, UNIT, DRAWING_REFERENCE_PRECISION["top rim chamfer"]
)
DRAWING_NOTES = (
    f"CONVEX EDGES {_EDGE_CHAMFER_TEXT}"
    " X 45 DEG UNLESS NOTED; NOT HOLE OR SLOT MOUTHS.\n"
    # TODO(#1625): remove when the title block gains its inside-corner default
    f"INSIDE CORNERS R{render_number(INSIDE_CORNER_R_MAX / IN, UNIT, 2)} MAX UNLESS NOTED.\n"
    f"EDGES NOTED SHARP: NO {_EDGE_CHAMFER_TEXT}"
    " CHAMFER; TITLE-BLOCK EDGE BREAK."
)
# User rulings 2026-10-11, 2026-10-14 and 2026-10-18 (cohesive appearance;
# exception RV-03): the whole top plane between the four corner bosses is
# faced, so both keeper feet land on one flat right-rail face wherever fit-up
# puts them and both washers bear on the crossbar's faced top; no split-line
# regions and no geometry change: the model's top is the finished plane.  Its
# own property, placed beside the keeper callout on HOLES-SOCKETS.  The
# keeper seats carry no flatness frame (rule 5; codex review of PR #1640,
# owner ruling pending in #1659): MHA-CH-00 pair-reams the keepers and sets
# them on this face with the shaft through both.
DRAWING_NOTES_B = f"WHOLE TOP EXCEPT 4 BOSSES:\nRa {ra(SEAT_UM, unit=UNIT)} µIN."
# User ruling 2026-10-12 (reading (i)): every face on the underside
# plane between the bosses is faced at the seat finish -- the rail web
# bottoms, the junction lands and plan gussets, and the crossbar's full-depth
# ends that seat both MHA-SM-02 knife mounts.  The 4X corner-boss bottoms
# (.25 below the plane) and the hub boss and its V-gussets (.31 below) stay
# off it.  No flatness zone (both knife seats lie on the one faced plane; no
# stack spends a form budget on it) and no geometry change: the model's
# underside is the finished plane.  Its own property, on the UNDERSIDE sheet
# beside the enlarged detail of the hub boss and gussets it excludes.
DRAWING_NOTES_C = (
    "UNDERSIDE PLANE BETWEEN BOSSES\n"
    "(MHA-SM-02 KNIFE-MOUNT SEATS):\n"
    f"Ra {ra(SEAT_UM, unit=UNIT)} µIN; BOSS BOTTOMS AND\n"
    "HUB GUSSETS EXCLUDED."
)
