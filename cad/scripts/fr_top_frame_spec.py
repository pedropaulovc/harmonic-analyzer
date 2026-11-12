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

Owner ruling 2026-11-10 (#2333, option a): the frame is a one-off gray-iron
sand casting (ASTM A48 CLASS 25B) poured from a 3D-printed pattern and
machined on its seats only.  Machined: the faced top and underside planes;
the four corner-boss tops; the two west bosses' keeper reliefs (owner ruling
2026-11-11, #1038, K5: ``KEEPER_BOSS_RELIEF_FROM_SOCKET``); the edge breaks
bordering those faced planes (cut
after facing, the stock covers the edge on the pattern); the tube sockets,
cap recesses and their mouth chamfers; the gooseneck bore and its mouth
chamfer; the set-screw tap and its spot face; the cross-screw counterbores,
clearance holes and far-wall taps; the hanger holes, dowel reams and
knockouts; and the keeper taps transferred at assembly.  The drafted walls,
rims, barrels and boss bottoms, and the edge breaks between two of them,
stay as cast.  The registry row (``cad/config/parts/fr-top-frame.yaml``)
carries the material and process.

Owner rulings B1-B6 and D1-D6 (#2333, 2026-11-10) make the model the casting:

* B1, draft: every drag face takes ``DRAFT_DEG``.  Added draft (the nominal
  at the face's end far from the faced top, the wall thickening toward the
  top) on the rail webs, the crossbar web and side walls, the plan gussets,
  junction lands, hub rib, hub V-gussets and the set-screw boss's side walls.
  Taken-out draft (the nominal on the faced top plane) on the corner-boss
  barrels.  Machined faces take none.
* D1: the faces B1 does not name take their draft taken out
  (``DRAFT_TAKEN_OUT_ON_UNNAMED_FACES``): both .32 flange rims, with the
  hub-rib and junction-land strips flush with them, and the set-screw boss
  face keep their nominal on the faced top; the hub boss barrel keeps its
  Ø1.18 on the underside plane.
* B2: every printed dimension with an as-cast end carries ``AS_CAST_BAND``
  natively; machined-to-machined dimensions keep the title block.
* B3: the four corner-boss tops are machined seats (``SURFACE_FINISHES``).
* B4: the set-screw boss runs the full rail height, flush with the faced top.
* B5: datum D, the crossbar's median plane, stays as cast.
* B6: the casting is set up on native datum targets E1-E3 (boss bottoms),
  F1-F2 (rear lower barrels) and G1.
* D2: G1 stands on the west rear lower barrel and the hole table's origin
  is the F-G (west, rear) corner.  The socket coordinates are basic under
  a two-tier position, printed as two single-segment frames; the hanger
  holes leave the table for the socket axes.
* D3: each rail web's median plane holds ``RAIL_WEB_POSITION_ZONE`` to its
  socket axes (datum B, the four-socket pattern).
* D4: added draft prints +1°/-0, taken-out draft ±1°
  (``DRAFT_ADDED_DEVIATIONS_DEG``, ``DRAFT_TAKEN_OUT_DEVIATIONS_DEG``).
* D5: the cross-screw counterbore floors stand .62 from the socket axis
  (``fr_frame_attachment_spec.TOP_SCREW_SEAT_Z``).
* D6: the socket position's upper tier is ``SOCKET_PATTERN_LOCATION_ZONE``.

Main's delegated ruling 2026-11-11 (#2333): each corner boss's Ø1.77 barrel
on the faced top holds ``BOSS_POSITION_ZONE`` to the socket pattern
(⌖Ø.06|A|B), the barrel-to-socket offset the wall, keeper-foot and
head-recess stacks charge.
"""

from __future__ import annotations

from math import radians, sqrt, tan

import _config
import sm_vn_knife_hanger_stud_spec as HANGER_SCREW
import sm_vn_knife_hanger_washer_spec as HANGER_WASHER
import sm_vn_knife_mount_dowel_spec as KNIFE_DOWEL
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm, printed_deviations
from _title_block_units import render_number
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _hole_spec import (
    CLEARANCE_MM,
    THREAD_MAJOR_MM,
    HoleSpec,
    blind_cut_dia_mm,
    drill_process,
)
from _mcmaster_91410a540 import SHANK_LEN as SET_SCREW_LENGTH
from _surface_finish import SEAT_UM, SurfaceFinishControl, ra
from _cone_axis_constants import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
    SUMMING_Z,
)
from fr_frame_attachment_spec import (
    CAP_RECESS_DEPTH,
    COLUMN_SOCKET_DIAMETER,
    TOP_FRAME_MID_Y,
    TOP_FRAME_RAIL_TOP_Y,
    TOP_FRAME_UNDERSIDE_Y,
    TOP_SCREW_SEAT_Z,
    TOP_SCREW_Y,
)
from fr_frame_cross_screw import far_wall_start_max_mm
from frame_column_stations import COLUMN_X
from sm_gooseneck_geom import TUBE_DIA_MAX, TUBE_DIA_MIN

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
if (
    abs(TOP_FRAME_MID_Y - HALF_H - TOP_FRAME_UNDERSIDE_Y) > 1e-9
    or abs(TOP_FRAME_MID_Y + HALF_H - TOP_FRAME_RAIL_TOP_Y) > 1e-9
):
    raise AssertionError("the rail band does not span the attachment's underside..top")
HANGER_CROSSBAR_WIDTH = 25.146  # .99
HANGER_CROSSBAR_WIDTH_PLACES = 2
FLANGE_THICKNESS_MM = 8.128  # .32 final top flange, including the faced right rail top
FLANGE_THICKNESS_PLACES = 2
BOSS_ABOVE = 4.572  # .18 boss proud of the rail top (corner-crop step)
BOSS_DIA = 44.958  # 1.77 user ruling 2026-10-10: all four upper/lower bosses, as cast
# Owner ruling 2026-11-11 (#1038, question 3, option K5) amends that Ø1.77
# ruling on the two WEST (fulcrum-side) bosses only: at the .300 station
# pitch the MHA-CH-07 keepers stand 5.715 further out per side, and their
# outward feet (kept, as on the original) would run into the proud barrels.
# The faced rail top is carried into each of the two barrels to a machined
# step: a pass across the rail, square to it, that removes the proud .18 of
# the barrel inboard of a straight chord.  Its floor IS the faced top, one
# plane with it, because each foot's outboard end rests there (the foot tips
# stand 4.19 / 3.18 inside the barrels' cast edges).  The casting pattern is
# unchanged (all four
# barrels are still cast Ø1.77): a cast-in flat would carry its own draft,
# ±.03 band and position zone, which the foot margin cannot pay at this
# depth, and would change the pattern print.
# The chord stands .67 from the socket axis toward mid-rail, machined to
# machined, so the title block's .XX holds it (the east bosses are not cut).
# ``build_fr_top_frame`` proves the foot, the tap and the wall the step
# leaves round the cap recess at the printed limits; the MHA-CH-00 keeper
# plan (``ch_channel_assembly_spec``) draws the stepped barrel from these.
KEEPER_BOSS_RELIEF_FROM_SOCKET = 17.018  # .67 chord from the socket axis
KEEPER_BOSS_RELIEF_PLACES = 2
KEEPER_BOSS_RELIEF_DEPTH = (
    BOSS_DIA / 2.0 - KEEPER_BOSS_RELIEF_FROM_SOCKET
)  # 5.461, .215
KEEPER_BOSS_RELIEF_HALF_CHORD = sqrt(
    (BOSS_DIA / 2.0) ** 2 - KEEPER_BOSS_RELIEF_FROM_SOCKET**2
)  # 14.687 across the rail, either side of the socket axis, on the faced top
# The step's root: the title block's R.040 inside corner would reach under a
# foot tip that stands .029 off the step at the printed limits and lift it
# off the faced top, so the root prints its own limit (codjiflo, PR #2599;
# ``build_fr_top_frame.KEEPER_FOOT_RELIEF_ROOT_MARGIN``).  The model's root
# is sharp.
KEEPER_BOSS_RELIEF_ROOT_R_MAX = 0.508  # .02
KEEPER_BOSS_RELIEF_ROOT_R_PLACES = 2
# The step's own leader callout on section A-A, two rows of words (rule 7;
# machinist review, farm run 20261112T030307472Z, gated three): the mate by
# its drawing number (farm run 20261111T233555541Z: "KEEPER" alone named
# no drawing), the plane the step runs down to (the faced top the 4X .18
# locates, which the section draws as the one line), and the root's limit.
# It is not the .67 station's text: a location carrying the floor's words
# read as a depth (farm run 20261112T014216327Z).
KEEPER_RELIEF_CALLOUT = (
    "2X MHA-CH-07 FOOT STEP TO\nFACED TOP, ROOT "
    f"R{render_number(KEEPER_BOSS_RELIEF_ROOT_R_MAX / IN, UNIT, KEEPER_BOSS_RELIEF_ROOT_R_PLACES)} MAX"
)
BORE_DIA = COLUMN_SOCKET_DIAMETER
# Every rail's web thickness, centred on its centreline (the keeper plan of
# MHA-CH-00 draws the west rail's web faces from it).  As cast it prints
# .51 ±.03 on the faced underside, its median held to the socket axes by
# RAIL_WEB_POSITION_ZONE (owner rulings B2 and D3, #2333); the keeper and
# cross-tap walls are proved at those limits (build_fr_top_frame).
WEB_T = 12.954  # .51 user ruling: retain loose bands plus realistic deep-drill wander
CAP_RECESS_FLOOR_Y = HALF_H + BOSS_ABOVE - CAP_RECESS_DEPTH  # 6.5151
# The cross-screw and set-screw taps share one axis plane, the attachment's
# TOP_SCREW_Y in the casting's frame: .72 below the rail top, .90 below the
# boss top, both on the .XX grid (machinist review: the mid-plane's .7185
# has no .XX station).
SCREW_AXIS_Y = TOP_SCREW_Y - TOP_FRAME_MID_Y  # -0.0381
SCREW_AXIS_BELOW_RAIL_TOP = HALF_H - SCREW_AXIS_Y  # 18.288, .72
GOOSENECK_X = -COLUMN_X  # east rail, -X crank side (summing's post station)
# Owner ruling 2026-11-08 (Pedro), #2315: the bore takes the gooseneck's
# bare 1/2 x .065 4130-N leg (MHA-SM-01) directly and prints .520
# at .XXX: drill 13 mm, then finish 33/64 or bore.  It leaves .008-.032
# diametral slip over the tube's mill OD band (sm_gooseneck_geom.TUBE_DIA_MIN
# ..MAX) so the gooseneck still slides for height setting (checked below).
GOOSENECK_BORE_DIA = 13.208  # .520
# The hub's underside boss drops below the rail band around the bore exit, so
# the bore runs RING_HEIGHT + HUB_BOSS_DROP (build_fr_top_frame's HubBoss).
HUB_BOSS_DROP = 7.874  # .31 boss bottom local -26.1239

# --- As-cast band and draft (owner rulings B1-B3, D1, D4; #2333) ---------------
#
# B2: a printed dimension with an as-cast end prints this symmetric band,
# authored on its model dimension (``_drawing_tolerances``); every proof that
# reads an as-cast limit charges it.  B1: drag faces take 2°.
# Owner ruling 2026-11-10 (#2333, D4): where the draft is added the angle
# prints +1°/-0 (a wall only ever thickens toward the top), where it is taken
# out ±1° (the faced-top outline is nominal).  Every proof uses the angle
# extreme that binds it.
AS_CAST_BAND = 0.762  # ±.03
DRAFT_DEG = 2.0
DRAFT_ADDED_DEVIATIONS_DEG = (1.0, 0.0)  # (upper, lower)
DRAFT_TAKEN_OUT_DEVIATIONS_DEG = (1.0, 1.0)  # (upper, lower) magnitudes
DRAFT_DEG_MIN = DRAFT_DEG - DRAFT_TAKEN_OUT_DEVIATIONS_DEG[1]  # 1°
DRAFT_DEG_MAX = DRAFT_DEG + DRAFT_TAKEN_OUT_DEVIATIONS_DEG[0]  # 3°
DRAFT_ADDED_DEG_MIN = DRAFT_DEG - DRAFT_ADDED_DEVIATIONS_DEG[1]  # 2°
DRAFT_TAN = tan(radians(DRAFT_DEG))
DRAFT_ANGLE_PLACES = 0
# Owner ruling 2026-11-10 (#2333, D1): the faces B1 leaves unnamed -- the .32
# flange's outer and window rims with the hub-rib and junction-land strips
# flush with them, the hub boss barrel and the set-screw boss face -- take
# their draft TAKEN OUT: each keeps its nominal on the faced plane it meets
# (the hub barrel's Ø1.18 on the underside).  ``build_fr_top_frame`` models
# and proves this sense only, and refuses the other.
DRAFT_TAKEN_OUT_ON_UNNAMED_FACES = True

# Stations the removed rail sections cut at.  The model stands each section's
# as-cast widths on construction lines at these stations, so the dimension a
# section imports lands on the profile it cuts (``draw_fr_top_frame`` cuts
# E-E and M-M at the first and holds H-H to the second).
SIDE_SECTION_Z = -56.0
RAIL_SECTION_X = 44.4

# --- Cast datum targets (owner rulings B6 and D2, #2333) ----------------------
#
# The casting is fixtured on six cast points for its first cut: E1-E3 on three
# corner-boss bottoms, F1 and F2 on the two rear barrels' rear generators and
# G1 on the rear-west barrel's west generator.  A barrel target stands this
# far over the boss bottom, mid-height on the band that hangs below the
# faced underside (the cross-screw counterbore opens the barrel above it);
# a boss-bottom target this far from its socket axis, mid-width on the
# bottom's ring.  Both print BASIC at DATUM_TARGET_PLACES.
# ``build_fr_top_frame.CAST_DATUM_TARGETS`` places the six.
DATUM_TARGET_BARREL_HEIGHT = 3.302  # .13
DATUM_TARGET_BOTTOM_RADIUS = 16.002  # .63
DATUM_TARGET_PLACES = 2

# --- Gooseneck set-screw boss (east-rail hub) ---------------------------------
#
# User ruling 2026-10-12 (option (a), no jam nut): the MHA-FR-VN-52 square-head
# cup-point set screw that pinches the gooseneck's bare leg enters the hub through a cast
# boss on the hub pad's outer face, spot-faced square to the tap. The spot
# face starts the thread square on a machined face (the head stands proud of
# it: the cup point bites the post first); it prints .XX from the bore axis
# the screw pinches across.  Owner ruling B4 (#2333): the boss runs the full
# rail height, flush with the faced top, and its cast face (taken-out draft,
# nominal at the top) stands .95 from the bore axis, .12 over the spot face.
HUB_SET_SPOT_FROM_AXIS = 21.082  # .83
HUB_SET_SPOT_PLACES = 2
HUB_SET_BOSS_FROM_AXIS = 24.13  # .95 cast face at the faced top
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
# underside. Owner ruling 2026-10-24 (T+H3): each MHA-SM-VN-53 dowel
# PRESSES into this soft casting, to the flat floor of a blind ream cut
# from the faced underside, with a knockout drilled up from that floor on
# the ream's drawn axis to the faced top, its coaxiality the title block's
# implied ±.005, charged in the floor land (.0124, machinist exception
# RV-06, owner ruling 2026-10-27) (drawing-guidelines.md rule 16, a
# pressed dowel needs a way out; the dt_crankshaft K0 precedent).  The
# round slip hole is in the hardened MHA-SM-02 block (``sm_knife_mount_spec``).
# Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: one dowel per station.
_XX = printed_band_mm(2, unit=UNIT)
_XXX = printed_band_mm(3, unit=UNIT)
# The title block's DRILLED HOLES row: a drilled hole cuts up to this oversize.
DRILL_OVERSIZE = drilled_oversize_mm(unit=UNIT)
# Owner ruling 2026-11-06: the #10 hanger holes are a letter C drill, .242
# in = 6.1468 mm, the next drill over the ASME B18.2.8 Table 2 #10 loose
# .238: the larger hole's float takes the ream/tap stack and the gauge
# bar's yaw with margin (``build_sm_summing_assembly.HANGER_SCREW_FLOAT_SPARE``
# and ``KNIFE_REAR_YAW_RANGE_DEG``).  The drawing prints the letter
# (HANGER_HOLE_DRILL) as "C DRILL".
HANGER_HOLE_DRILL = "C"
HANGER_CLEARANCE_DIA = 0.242 * IN  # 6.1468
if HANGER_CLEARANCE_DIA <= CLEARANCE_MM[("#10", "loose")]:
    raise AssertionError("the C drill hanger hole must clear past the #10 loose row")
HANGER_CLEARANCE_DIA_PLACES = 3
# The title block's DRILLED HOLES row is the acceptance (+.004/0): it never
# undersizes the drill, so the callout restates no band (machinist review:
# rule 2).
HANGER_CLEARANCE_DIA_BAND = (DRILL_OVERSIZE, 0.0)  # (upper, lower), title block
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
# A plain native Hole Wizard #10 clearance row, drilled through from the
# faced underside, its cut pinned to the C drill: _holes.wizard_holes writes
# HoleDiameter and ThruHoleDiameter from the override (and skips its pinned
# loose-fit edit), and the build reads the exact cut diameter back.
HANGER_HOLE_SPEC = HoleSpec(
    "clearance", "#10", fit="loose", overrides_mm={"HoleDiameter": HANGER_CLEARANCE_DIA}
)
# Washer bounds are ASME B18.21.1 Table 11, owned by the purchased-part spec.
# Full washer float uses the sourced UNC 2A minimum shank diameter, not
# nominal thread-major geometry, charging the full washer eccentricity.
HANGER_WASHER_FLOAT_MAX = (HANGER_WASHER.ID_MAX - HANGER_SCREW.SHANK_DIA_MIN) / 2.0
HANGER_WASHER_CONCENTRIC_ANNULUS_MIN = (
    HANGER_WASHER.OD_MIN - HANGER_CLEARANCE_DIA_MAX
) / 2.0
if HANGER_WASHER_CONCENTRIC_ANNULUS_MIN <= 0.0:
    raise AssertionError("knife-hanger washer lacks a bearing annulus round its hole")
# The dowel press reams: at each hanger station one blind flat-floor ream
# cut KNIFE_DOWEL.PRESS_DEPTH up from the faced underside to the dowel
# spec's press band, .1240 +.0005/0 printed .XXXX (press .0006-.0013 on the
# catalogue pin), two in all.  Owner ruling 2026-11-08 (Pedro), #2144 item
# 11.3: the -X ream at each station, its position frame, its BASIC span and
# its knockout are deleted; the +X ream stays.
HANGER_PIN_X = KNIFE_DOWEL.HANGER_OFFSET  # 7.62 (.300) +X of the bolt axis
# The ream's station from the screw axis, in the dowel spec's order (one).
HANGER_PIN_XS = (HANGER_PIN_X,)
# The hanger stations in part coordinates, which the builder cuts and the
# drawing locates (AGENTS.md: drawings read pure providers, not the
# builder): the crossbar centreline (the knife's x) and the two screw axes
# (build_sm_summing_assembly); each station's ream.  The knife line and the
# summing stations are the summing subsystem's: they flow through unsnapped.
HANGER_X = -15.0
# Owner ruling 2026-11-11 (#1038, question 4, option S-F): the MHA-SM-03
# plate grows .25 at its FRONT end only (6.00 -> 6.25), so the front knife
# mount stands 6.35 further out and the rear one stays: each station is its
# trunnion's mid-length off the summing axis, 82.55 + 10.86 and
# 76.20 + 10.86.  The crossbar's cast pockets do not move.
HEX_Z_MID_FRONT = 93.41
HEX_Z_MID_REAR = 87.06
STUD_Z_FRONT = SUMMING_Z - HEX_Z_MID_FRONT  # -90.322
STUD_Z_REAR = SUMMING_Z + HEX_Z_MID_REAR  # +90.148
PIN_HOLE_X = HANGER_X + HANGER_PIN_X  # -7.38
HANGER_PIN_X_PLACES = KNIFE_DOWEL.HANGER_OFFSET_PLACES
# Each ream's station from its #10 axis along the dowel line, and its
# implied-zero offset across it from that axis's drawn line: the title
# block's .XXX.
HANGER_PIN_X_TOL = KNIFE_DOWEL.HANGER_OFFSET_TOL  # 0.127
HANGER_PIN_HOLE_DIA = KNIFE_DOWEL.PRESS_HOLE_DIA  # 3.1496
HANGER_PIN_HOLE_DIA_BAND = KNIFE_DOWEL.PRESS_HOLE_DIA_BAND  # (0.0127, 0.0)
HANGER_PIN_HOLE_DIA_PLACES = KNIFE_DOWEL.PRESS_HOLE_DIA_PLACES
HANGER_PIN_HOLE_DIA_MIN = HANGER_PIN_HOLE_DIA + min(HANGER_PIN_HOLE_DIA_BAND)
HANGER_PIN_HOLE_DIA_MAX = HANGER_PIN_HOLE_DIA + max(HANGER_PIN_HOLE_DIA_BAND)
HANGER_PIN_HOLE_DEPTH = KNIFE_DOWEL.PRESS_DEPTH  # 11.938, from the underside
HANGER_PIN_HOLE_DEPTH_PLACES = KNIFE_DOWEL.PRESS_DEPTH_PLACES
HANGER_PIN_HOLE_DEPTH_TOL = KNIFE_DOWEL.PRESS_DEPTH_TOL  # 0.254
# Each ream stands .XXX HANGER_PIN_X from its own screw axis along the dowel
# line (F-F), at the screw's own Z (an implied zero across the line, the
# same .XXX).  Owner ruling 2026-11-08 (Pedro), #2144 item 11.3: with the
# -X reams gone, nothing locates to the +X reams, so they are no longer
# datums B (front) and C (rear) and carry no position frame of their own
# (nor owner ruling 2026-11-06's BASIC .300 from D under 2X ⌖Ø.004|A|D,
# which located a pair): the simplest correct control on the remaining ream
# is that toleranced .300 +/-.005 from the #10 clearance hole's axis, which
# is exactly what the knife-hanger bolt-float stack charges
# (``build_sm_summing_assembly``'s HANGER_SCREW_MISMATCH, HANGER_PIN_X_TOL
# along and across), plus the reams' perpendicularity, Ø.001 (owner ruling
# 2026-11-06), to the faced underside (datum A) the knife mounts seat on,
# so each pressed dowel stands square to its block's top seat
# (owner ruling 2026-10-27 (#2016), option A; the block's hole takes
# ⊥Ø.001|A).  The #10
# axes lie on the crossbar median plane D within the centring zone
# (⌖.010|D, owner ruling 2026-11-06).  The values stay literals (the FCF
# provenance scan reads them): the inch strings print, the millimetres
# derive from them.
# The keeper seats carry no frame: rule 5 names flatness on a clamp face
# over-specification and no user ruling accepts one (codex review of
# 06d0bbc59); the faced top (RV-03) carries them.
# Owner rulings B6, D2, D3 and D6 (#2333): the four tube sockets (datum B, the 4X
# pattern) are located BASIC from the casting's target frame E|F|G by a
# two-tier position (two single-segment frames: drawing-guidelines.md allows
# no composite frame), the pattern within Ø.06 of the cast datums and the
# sockets among themselves within Ø.010 to the faced underside A; each rail
# web's median plane stands within .06 of its socket-axis line (⌖.06|A|B).
# Main's delegated ruling 2026-11-11 (#2333): each corner boss's Ø1.77
# barrel on the faced top stands within Ø.06 of its own socket
# (⌖Ø.06|A|B).  The cast targets F and G touch the barrels 1.56 under the
# faced top, where a 2° ±1° barrel's radius runs ±.042, so the sockets'
# Ø.06 to E|F|G alone does not hold a barrel to its socket; this frame is
# the offset the wall and keeper-foot stacks charge between the two
# (build_fr_top_frame._SOCKET_BARREL_OFFSET).
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "knife-hanger crossbar centring": ".010",
    "knife-hanger press ream perpendicularity": ".001",
    "tube socket pattern location": ".06",
    "tube socket pattern refinement": ".010",
    "rail web position": ".06",
    "corner boss position": ".06",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * IN for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
SOCKET_PATTERN_LOCATION_ZONE = GEOMETRIC_TOLERANCES_MM["tube socket pattern location"]
SOCKET_PATTERN_REFINEMENT_ZONE = GEOMETRIC_TOLERANCES_MM[
    "tube socket pattern refinement"
]
RAIL_WEB_POSITION_ZONE = GEOMETRIC_TOLERANCES_MM["rail web position"]
BOSS_POSITION_ZONE = GEOMETRIC_TOLERANCES_MM["corner boss position"]
HANGER_CROSSBAR_CENTER_ZONE = float(
    GEOMETRIC_TOLERANCES_MM["knife-hanger crossbar centring"]
)
HANGER_CROSSBAR_CENTER_TOL = HANGER_CROSSBAR_CENTER_ZONE / 2.0
HANGER_PRESS_HOLE_PERPENDICULARITY_TOL = float(
    GEOMETRIC_TOLERANCES_MM["knife-hanger press ream perpendicularity"]
)
# An orientation refinement of a located feature is tighter than its
# location band (the ream's .XXX station, +/-.005 each way).
if not HANGER_PRESS_HOLE_PERPENDICULARITY_TOL < 2.0 * HANGER_PIN_X_TOL:
    raise AssertionError("the reams' perpendicularity must refine their location")
# The drilled #10 hole's float about the bolt shank is 0.6604 radial.
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
# carries the ream size, its count, mate and fit on one row under it; F-F
# the depth both share, to a flat floor.  Where the press stops (each
# dowel to the ream floor) is MHA-SM-00's step 1, not this part's (rule 7:
# an assembly instruction on a part sheet; farm run 20261106T234223948Z).
# The knockouts' native callout reads its drill above the native size and
# its purpose below (dt_crankshaft_notes.KNOCKOUT_CALLOUT_*).
HANGER_PIN_HOLE_CALLOUT = "2X REAM, PRESS FIT MHA-SM-VN-53 DOWEL"
# The flat floor's corner: the title block's inside-corner radius would
# leave the dowel's end flat bearing on a fillet, so the depth's row limits
# it (numbers in a native dimension's callout row: the knife mount's
# ".0020-.0036 DIAMETRAL CLEARANCE" precedent).  The dowel's spec owns the
# limit with the ream it bounds (codjiflo round 5).
HANGER_PIN_FLOOR_CORNER_R_MAX = KNIFE_DOWEL.PRESS_FLOOR_CORNER_R_MAX
# Three rows: one "CORNER R.003 MAX" row overran F-F's band between the
# depth's line and the title block.
HANGER_PIN_DEPTH_CALLOUT = (
    f"2X FLAT BOTTOM,\nCORNER\nR{render_number(HANGER_PIN_FLOOR_CORNER_R_MAX / IN, UNIT, 3)} MAX"
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
# of its .XX band, the bore at the larger of a .XX band (wider than its
# printed .XXX) and the title block's drilled row.
_GOOSENECK_BORE_RADIUS_MAX = (GOOSENECK_BORE_DIA + max(_XX, DRILL_OVERSIZE)) / 2.0
SET_SCREW_THREAD_TERMS = {
    "spot face from bore axis at its minimum": HUB_SET_SPOT_FROM_AXIS
    - printed_band_mm(HUB_SET_SPOT_PLACES, unit=UNIT),
    "bore radius at its maximum": -_GOOSENECK_BORE_RADIUS_MAX,
    "bore sag across the thread": -_sag(_GOOSENECK_BORE_RADIUS_MAX),
    "one-pitch entry chamfer": -SET_SCREW_PITCH,
}
SET_SCREW_FULL_THREAD_MIN = sum(SET_SCREW_THREAD_TERMS.values())  # 12.03
SET_SCREW_FULL_THREAD_NOMINAL = (
    HUB_SET_SPOT_FROM_AXIS
    - GOOSENECK_BORE_DIA / 2.0
    - _sag(GOOSENECK_BORE_DIA / 2.0)
    - SET_SCREW_PITCH
)  # 12.39
SET_SCREW_ENGAGEMENT_D = SET_SCREW_FULL_THREAD_MIN / SET_SCREW_MAJOR_DIA  # 1.89D
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"hub set screw keeps {SET_SCREW_ENGAGEMENT_D:.2f}D of full thread "
        f"at the printed worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )
# The bare leg slides through the bore for height setting: the bore's least
# printed size (.515) clears the tube's largest mill OD (.507), and its
# largest (.530, as above) leaves .032.
GOOSENECK_SLIP_MIN = GOOSENECK_BORE_DIA - _XXX - TUBE_DIA_MAX  # 0.203, .008
GOOSENECK_SLIP_MAX = 2.0 * _GOOSENECK_BORE_RADIUS_MAX - TUBE_DIA_MIN  # 0.813, .032
if GOOSENECK_SLIP_MIN <= 0.0:
    raise AssertionError(
        f"the gooseneck bore's least printed size leaves {GOOSENECK_SLIP_MIN:.3f} mm "
        "over the tube's largest mill OD; the leg would not slide"
    )
# The 3/4 in MHA-FR-VN-52 still reaches the leg at the worst case: the spot
# face at the far end of its .XX band, the leg at its smallest OD pushed
# against the bore's far wall at its largest.  One pitch of thread-start
# margin keeps the head off the spot face when the cup point bites.
SET_SCREW_REACH_MAX = (
    HUB_SET_SPOT_FROM_AXIS
    + printed_band_mm(HUB_SET_SPOT_PLACES, unit=UNIT)
    - (TUBE_DIA_MIN - _GOOSENECK_BORE_RADIUS_MAX)
)  # 15.42
if SET_SCREW_REACH_MAX >= SET_SCREW_LENGTH - SET_SCREW_PITCH:
    raise AssertionError(
        f"MHA-FR-VN-52 needs {SET_SCREW_REACH_MAX:.2f} mm from the spot face to "
        f"the leg, against its {SET_SCREW_LENGTH:.2f} mm less one pitch"
    )
# Owner ruling 2026-11-08 (Pedro), #2315: tighten snug, 9 in-lb (1 N·m) max.
# Slip at SF 3 on the 69.3 N pull at mu 0.15 needs ~693 N of clamp (0.88
# N·m); the bare .065 wall yields locally near 1.14 kN (1.45 N·m).  The full
# Unbrako 87 in-lb would push ~7.7 kN.  The leg itself at the hub carries
# 7.33 N·m on Z 124 mm^3: 59 MPa against 4130-N's 434 MPa.
SET_SCREW_TORQUE_MAX_IN_LB = 9.0
SET_SCREW_TORQUE_MAX_NM = 1.0


# --- Machining-required surfaces ---------------------------------------------
#
# The four socket bores and the four boss tops own native finish controls
# (SURFACE_FINISHES). The top plane between the
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
# * The gooseneck bore (a drilled hole the set screw clamps the bare leg in) and
#   the set-screw spot face (a clamp face) neither run nor locate, so they
#   carry no symbol (machinist review r1, 2026-10-18; drawing-guidelines.md
#   rule 6).
# * Owner ruling B3 (#2333): the four corner-boss tops are machined seats,
#   .18 above the faced top, so the cap recess, the boss height above the
#   rail and the cross-screw axis below the boss top are machined-to-machined.
#
# SEAT grade throughout: nothing runs on these surfaces continuously, so the
# commercial machine finish is what the fit needs. Each controlled face has
# a native model symbol; each drawing family appears once with a target label.
SOCKET_BORE_TARGET = "TUBE SOCKET BORES, 4X"
BOSS_TOP_TARGET = "BOSS TOPS, 4X"
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
) + tuple(
    SurfaceFinishControl(
        f"boss_top_{rail}_{end}",
        SEAT_UM,
        PlanarFace(
            (0.0, 1.0, 0.0),
            HALF_H + BOSS_ABOVE,
            contains_x_mm=x,
            contains_z_mm=z,
        ),
        production_method=BOSS_TOP_TARGET,
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
    # The rim rectangle prints as references; the flange widths size the
    # window and the web thicknesses the web's inner rectangle, each on a
    # construction line across its rail.
    "OuterProfile": {"Width", "Depth", "SideFlangeWidth", "FrFlangeWidth"},
    "WebProfile": {"SideWebT", "FrWebT"},
    # The rail height is the same finished thickness as the grip: the web
    # ring's own depth, printed in the geometry front view as a reference.
    # One draft angle prints per owner-ruling-D4 band, on sheet 7's elevation:
    # the web ring's for the faces B1 adds draft to, the upper boss barrels'
    # for the faces B1/D1 take it out of (the top flange's own angle, the
    # same 2° ±1°, is not printed a second time).
    "WebRing": {"RingHeight", "WebRingDraft"},
    "TopFlange": {"FlangeT"},
    "Crossbar": {"HangerGrip"},
    # DStation: datum D's median from the G plane (owner ruling D2).
    "BarProfile": {"BarWidth", "GussetRunE", "LandEndW", "DStation"},
    "BarPocketProfile": {"PocketLength", "PocketFromSocket", "CrossbarWebT"},
    "BarPockets": {"PocketDepth"},
    "BossUpProfile": {"C0Dia"},
    "BossesUpper": {"BossesUpperDraft"},
    "BossesLower": {"BossBelowTop"},
    "BoreProfile": {"B0X", "B0Z", "B0Dia"},
    "CounterboreRearProfile": {"CB1Dia"},
    "HubGussetPlateProfile": {"GussetT"},
    "HubGussetProfile": {"GussetSpan"},
    "HubBossProfile": {"HubDia"},
    "HubBoss": {"HubBossDrop"},
    "RibProfile": {"RibWidth"},
    "SetBossProfile": {"SetBossWidth", "SetBossFace"},
    "SetSpotProfile": {"SetSpotDia"},
    "GooseneckTap": {"SetTapZ"},
    "GooseneckProfile": {"GnDia", "GnX", "GnZ"},
    "TRootFillets": {"RootR"},
    # The hanger-hole and keeper-tap placement dims (StudFrontX ...,
    # KeeperFrontX ...) are NOT marked: a Hole Wizard placement sketch
    # measures from the origin -- mid-air on the print -- so sheet 3
    # dimensions those stations from the socket bore axes with sheet-derived
    # dimensions (DRAWING_REFERENCE_PRECISION below, drawing-guidelines.md rule 10 (dimension from a real feature)).  The
    # dowel reams' stations (each ream from its screw axis) are
    # sheet-derived the same way, on section F-F; the
    # ream size is the model's, printed on the underside locator, and the
    # depth the model's, printed on F-F.  The knockouts print their native
    # Hole Wizard callout.
    "CapRecessProfile": {"CapRecessDia"},
    "CapRecesses": {"CapRecessDepth"},
    "HangerPinProfile": {"HangerPinHoleDia"},
    "HangerPinHoles": {"HangerPinHoleDepth"},
}

# Owner ruling B2 (#2333): the model dimensions with an as-cast end.  The
# build authors ``AS_CAST_BAND`` on each (``_drawing_tolerances``), printed
# at the dimension's own places.
AS_CAST_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "OuterProfile": ("SideFlangeWidth", "FrFlangeWidth"),
    "WebProfile": ("SideWebT", "FrWebT"),
    "TopFlange": ("FlangeT",),
    "BarProfile": ("BarWidth", "GussetRunE", "LandEndW", "DStation"),
    "BarPocketProfile": ("PocketLength", "PocketFromSocket", "CrossbarWebT"),
    "BarPockets": ("PocketDepth",),
    "BossUpProfile": ("C0Dia",),
    "BossesLower": ("BossBelowTop",),
    "HubGussetPlateProfile": ("GussetT",),
    "HubGussetProfile": ("GussetSpan",),
    "HubBossProfile": ("HubDia",),
    "HubBoss": ("HubBossDrop",),
    "RibProfile": ("RibWidth",),
    "SetBossProfile": ("SetBossWidth", "SetBossFace"),
    "TRootFillets": ("RootR",),
}
# Owner ruling 2026-11-10 (#2333, D4): each drafted feature's own draft-angle
# dimension and the band it prints, (upper, lower) magnitudes in degrees.
# The set-screw boss is one extrude: its B1-added side walls set its band,
# which its D1 taken-out face then holds inside its own ±1°.
DRAFT_ANGLE_DIMENSIONS: dict[str, tuple[str, tuple[float, float]]] = {
    "WebRing": ("WebRingDraft", DRAFT_ADDED_DEVIATIONS_DEG),
    "HubRib": ("HubRibDraft", DRAFT_ADDED_DEVIATIONS_DEG),
    "Crossbar": ("CrossbarDraft", DRAFT_ADDED_DEVIATIONS_DEG),
    "BarPockets": ("BarPocketsDraft", DRAFT_ADDED_DEVIATIONS_DEG),
    "HubGussetPlate": ("HubGussetPlateDraft", DRAFT_ADDED_DEVIATIONS_DEG),
    "SetBoss": ("SetBossDraft", DRAFT_ADDED_DEVIATIONS_DEG),
    "TopFlange": ("TopFlangeDraft", DRAFT_TAKEN_OUT_DEVIATIONS_DEG),
    "BossesUpper": ("BossesUpperDraft", DRAFT_TAKEN_OUT_DEVIATIONS_DEG),
    "BossesLower": ("BossesLowerDraft", DRAFT_TAKEN_OUT_DEVIATIONS_DEG),
    "HubBoss": ("HubBossDraft", DRAFT_TAKEN_OUT_DEVIATIONS_DEG),
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
# The cap recess depth carries the bilateral band the build applies, its
# diameter the title block's .XXX (owner ruling 2026-11-06), the
# gooseneck bore prints the slip clearance the gooseneck's bare leg slides in, the
# finished grip prints .XXX (the rail height, that same thickness, prints its
# reference at the grip's places), and the dowel press ream holds its own
# +.0005/0 band at four places.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OuterProfile": {
        "Width": 3,
        "Depth": 2,
        "SideFlangeWidth": 2,
        "FrFlangeWidth": 2,
    },
    "WebProfile": {"SideWebT": 2, "FrWebT": 2},
    "WebRing": {"RingHeight": HANGER_GRIP_PLACES, "WebRingDraft": DRAFT_ANGLE_PLACES},
    "TopFlange": {"FlangeT": FLANGE_THICKNESS_PLACES},
    "Crossbar": {"HangerGrip": HANGER_GRIP_PLACES},
    "BossUpProfile": {"C0Dia": 2},
    "BossesUpper": {"BossesUpperDraft": DRAFT_ANGLE_PLACES},
    "BossesLower": {"BossBelowTop": 2},
    "BoreProfile": {"B0Dia": 3},
    "CounterboreRearProfile": {"CB1Dia": 2},
    "BarProfile": {
        "BarWidth": HANGER_CROSSBAR_WIDTH_PLACES,
        "GussetRunE": 2,
        "LandEndW": 2,
        "DStation": 2,
    },
    "BarPocketProfile": {"PocketLength": 2, "PocketFromSocket": 2, "CrossbarWebT": 2},
    # The pocket is the .XXX grip less the .32 flange: it prints the grip's
    # places, and its as-cast band prints at them.
    "BarPockets": {"PocketDepth": HANGER_GRIP_PLACES},
    "HubGussetPlateProfile": {"GussetT": 2},
    "HubGussetProfile": {"GussetSpan": 2},
    "HubBossProfile": {"HubDia": 2},
    "HubBoss": {"HubBossDrop": 2},
    "RibProfile": {"RibWidth": 2},
    "SetBossProfile": {"SetBossWidth": 2, "SetBossFace": 2},
    "SetSpotProfile": {"SetSpotDia": 2},
    "GooseneckProfile": {"GnDia": 3},  # a drill diameter: .520
    "CapRecessProfile": {"CapRecessDia": 3},
    "CapRecesses": {"CapRecessDepth": 3},
    "HangerPinProfile": {"HangerPinHoleDia": HANGER_PIN_HOLE_DIA_PLACES},
    "HangerPinHoles": {"HangerPinHoleDepth": HANGER_PIN_HOLE_DEPTH_PLACES},
    "TRootFillets": {"RootR": 2},
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
    # Sheet 2, GEOMETRY: the overall envelope (as-cast ends, references), the
    # faced top's rim break in H-H and the crossbar flange's thickness in
    # M-M, a reference to the rails' own FlangeT.  Every other size on that
    # sheet is a model dimension with its ±.03 (AS_CAST_DIMENSIONS).
    "overall casting width": 2,
    "overall casting depth": 2,
    "top rim chamfer": 2,
    "crossbar flange thickness": FLANGE_THICKNESS_PLACES,
    # Sheet 3, HOLES-SOCKETS: hole stations baseline from the socket axes (X
    # from the left pair, Z from the upper pair).  The knife line, summing
    # axis and keeper fit-up are other subsystems' stations: they print .XXX
    # as they flow through.
    # The position frame holds the hanger axes BASIC zero on D (sheet 7
    # carries D's width and station); keeper coordinates are reference-only
    # guides to assembly-transferred taps.
    "front hanger z from upper sockets": 3,
    "rear hanger z from upper sockets": 3,
    "keeper x from left sockets": 3,
    "front keeper z from upper sockets": 3,
    "rear keeper z from upper sockets": 3,
    # Sheet 4, CROSS-TAPS: boss stack, cap-mouth chamfer, opposed counterbore
    # floors and the tap axis below the boss top, all on the .XX grid (the
    # cap ligament and keeper cross-tap wall read their ±.01).
    "socket boss overall height": 2,
    "boss top above rail top": 2,
    "top bore mouth chamfer": 2,
    "opposed counterbore floor separation": 2,
    "cross screw axis from boss top": 2,
    # .XX, the floor at .62 (owner ruling D5, #2333;
    # fr_frame_attachment_spec.TOP_SCREW_SEAT_Z):
    # over the .080 target to the cap recess at every printed corner
    # (build_fr_top_frame.COUNTERBORE_PRINTED_CAP_LIGAMENT).
    "counterbore floor from socket axis": 2,
    # The two west bosses' keeper relief step (owner ruling 2026-11-11,
    # #1038, K5), from its socket axis: the .XX the keeper foot margin is
    # proved at (build_fr_top_frame.KEEPER_FOOT_PRINTED_BOSS_MARGINS).
    "keeper relief step from socket axis": KEEPER_BOSS_RELIEF_PLACES,
    # Sheet 5, HUB-SET-SCREW: hub station, set-tap axis, gusset ramp and the
    # removed set-screw boss section K-K (spot face, thread run; the boss
    # face prints its as-cast .95 on sheet 6's DETAIL J).
    # The hub station is the summing axis's (SUMMING_Z): it flows through.
    "hub from left front socket": 3,
    "set screw axis from rail top": 2,
    "hub gusset ramp angle": 1,
    "set-screw spot face from bore axis": HUB_SET_SPOT_PLACES,
    "set-screw thread length": 3,
    # Sheet 6, UNDERSIDE: knife-hanger section F-F.  The native finished-top
    # grip and ream depth are imported; the ream's station from the screw
    # axis is measured.
    "dowel hole from hanger axis": HANGER_PIN_X_PLACES,
    # Sheet 7, CAST-DATUMS: the datum targets' BASIC locations.
    "boss bottom target from socket axis": DATUM_TARGET_PLACES,
    "barrel target above boss bottom": DATUM_TARGET_PLACES,
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


# The tap drill prints its three-place drill size; its blind depths print .XX,
# since no function needs them closer (the receiver stacks below read these
# places).
KEEPER_TAP_CALLOUT_PRECISION = {
    "hw-tapdrldia": 3,
    "hw-tapdrldepth": 2,
    "hw-threaddepth": 2,
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
# chamfer).  Owner ruling 2026-11-07 rescopes the note to the convex cast
# edges where the .06 break fits, the ones the views show chamfered.  The
# edges under a knife seat, beside the hub boss or on a shelf too narrow at
# the as-cast limits
# (build_fr_top_frame._external_edge_breaks: the front crossbar side
# bottoms, the four gusset hypotenuse bottoms, the crossbar flange's
# underside edges, the hub rib's inner bottom, the V-gusset ramp edges and
# the set-screw boss's edges on the faced top): the model leaves these
# unbroken at .06; the
# title block's .010 break applies, so no edge reads SHARP anywhere and
# nothing is noted.  Each row stays within the 64 characters the unnumbered
# first row printed on sheet 3 (EDGE_NOTE_XY).
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
    f"1. CONVEX CAST EDGES {_EDGE_CHAMFER_TEXT} X 45° WHERE SHOWN.\n"
    # TODO(#1625): remove when the title block gains its inside-corner default
    f"2. INSIDE CORNERS R{render_number(INSIDE_CORNER_R_MAX / IN, UNIT, 2)} MAX UNLESS NOTED."
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
DRAWING_NOTES_B = f"WHOLE TOP EXCEPT 4 BOSSES:\nRa {ra(SEAT_UM, unit=UNIT)}."
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
    f"Ra {ra(SEAT_UM, unit=UNIT)}; BOSS BOTTOMS AND\n"
    "HUB GUSSETS EXCLUDED."
)
# Far-wall engagement (rule 18, print worst): every counterbore floor is
# located from its own socket axis ("4X COUNTERBORE FLOOR FROM SOCKET AXIS",
# .XX), so the seat-to-axis stack is that one band at its most outboard; the
# shared joint adds the match-bored socket ceiling and the far mouth's edge
# break.  Pure data here, so the MHA-FR-00 sheet's cross-screw thread check
# reads it without reaching build_fr_top_frame (whose COUNTERBORE_MAX_FLOOR_
# OFFSET is this same printed limit, asserted there).
TOP_CROSS_SCREW_FAR_WALL_START_MAX = far_wall_start_max_mm(
    printed_limit(
        TOP_SCREW_SEAT_Z - abs(FRONT_COLUMN_Z),
        DRAWING_REFERENCE_PRECISION["counterbore floor from socket axis"],
        1.0,
    ),
    unit=UNIT,
)  # 30.018
