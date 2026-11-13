r"""MHA-PD-17 transgear-disc-hub: the brass hub and flange in front of the reducer disc.

The turned Ø.540 hub has a plain round .313 +.0010/+.0005 bore,
reamed through (the shop's .3135 over reamer), a sliding fit on the pinion
sleeve's (MHA-PD-10) .313 +.0005/.0000 boss, with a Ø1.05 × .094 flange and
a Ø.498 +.000/-.001 rear spigot.  The spigot passes the reducer disc's
(MHA-PD-06) bore, which it clears (the disc is centred at assembly), and its
end seats on the sleeve's step face (the 12T's tooth ends); the flange's rear
face clamps the disc's front face, the spigot's length ahead of the step.
Three #0-80 fillister screws (MHA-PD-VN-55) pass the flange's #51 holes on the
Ø.75 circle into the disc's taps (``pd_transgear_disc_hub_geometry``; the
taps are spotted through these holes at assembly, R9-9).  One 1/16 × 5/16
hardened dowel (MHA-PD-VN-69) lies on a chord of the hub body over the
sleeve's D-flat on local -Y, pressed from +X into a .0615 ream to its stop
(a #56 knockout runs on through): the chord breaks into the bore, so the
pin's side lies along the flat and keys the hub in rotation.  The disc's
torque runs disc → disc screws → hub flange → the pin's side, in shear
between its ends held in the hub wall → flat → sleeve, with no thrust along
the pin.  The spigot's end seats on the step, and the MHA-PD-25 front
bushing, held by the MHA-PD-VN-61 ring, traps hub and disc forward.  The hub's
printed overall leaves its front face ``transgear_cluster_fit.RECESS_RANGE``
behind the sleeve's nose (never proud at the worst case), so the bushing,
whose rear face covers the hub's front face, bears on the steel nose and
never thrusts on the brass (R9-5).  The bore is datum A; the flange's rear
face and the spigot's end are held square to it, all turned in one setup.
A #57 radial oil hole on +Y, opposite the key pin on its axis, reaches the
bore; it is drilled through the hub wall and the sleeve's boss in one
operation at assembly (R9-8), so the sheet carries a match-drill callout, not
a free drilled hole.

Sizes (drawing-guidelines.md rule 17 (walls and webs)): every wall holds the
.080 target at the printed worst case; the flange is Ø1.05 so the screw
hole keeps it to the rim with the flange and the circle both at .XX, its
edge breaks charged.  Finished, the body's and the spigot's walls over the
round bore pay both .010 breaks at their exposed ends and land under the
target, over the .060 floor; the bore's callout states the least
(BORE_WALL_TEXT).  The wall over the key pin's chord ream lands over the
floor, under the target: the hub is Ø.540 to hold it (package minor RV-03).

Printed lengths, from the spigot's end and the flange's rear face: the
overall, spigot end to hub front face, and the spigot (both terms of the
disc cluster's stack, +/-.001 for the collar air and the recess; the shims
set the end float, owner ruling 2026-11-01, #2124; ``transgear_cluster_fit``
owns the overall), and
the flange .094 .XXX (the screw-tip-to-platen stack reads it).  The hub
body's own length is the remainder and is not printed.  Decimal inch
(#290): every nominal is the exact millimetre value of its printed inch.

Local frame (the build's, and the one the assembly mates): the gear axis is
Z through the origin (``Axis1``).  ``Front Plane`` (z = 0) is the flange's
rear face, the face that clamps the disc's front face; the spigot runs
z = 0..+SPIGOT_LENGTH, the flange z = -FLANGE_THICK..0 and the hub body down to the
front face, so local -Z is the machine's -Z (toward the operator).  Screw 0°
is local +X, angles counter-clockwise seen from +Z; the key pin's chord is
parallel to local X on -Y (over the sleeve's flat), and the oil hole is on
local +Y, on the hub body.
The part sits
in the machine unrotated at z0 = ``transgear_cluster_fit.DISC_FRONT_Z``.

Pure data; no SolidWorks calls.  This module reads the cluster fit, the
sleeve's, the disc's and the key pin's specs; none reads it back.
"""

from __future__ import annotations

import math

import _config
import pd_rack_pinion_spec as DISC
import transgear_cluster_fit as FIT
import pd_transgear_feed_pinion_spec as SLEEVE
import pd_vn_transgear_hub_key_pin_spec as KEY_PIN
from _fit_deviations import deviations
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    inside_corner_radius_mm,
    printed_band_mm,
)
from _mcmaster_91794a055 import FILLISTER_SIZE
from pd_cluster_stack_band import STACK_NAME
from pd_rack_pinion_spec import inch_text
from pd_transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_PLACES,
    BOLT_CIRCLE_POSITION_TOL,
    SCREW_COUNT,
    SCREW_HOLE_DIA,
    SPIGOT_DIA,
    SPIGOT_DIA_BAND,
    SPIGOT_DIA_PLACES,
    SPIGOT_LENGTH,
    SPIGOT_LENGTH_BAND,
    SPIGOT_LENGTH_PLACES,
    UNIT,
)

MM_PER_IN = 25.4

# The mating parts the sheet names, by name and number (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the
# feed pinion whose boss the hub's bore slides on, the disc that the spigot
# clears, the disc screws and the key pin on the feed pinion's flat.
SLEEVE_NUMBER = "MHA-PD-10"
DISC_NUMBER = "MHA-PD-06"
DISC_NAME = "DISC"
SCREW_NUMBER = "MHA-PD-VN-55"
SCREW_NAME = "DISC SCREW"
if SLEEVE.SLEEVE_NUMBER != SLEEVE_NUMBER:
    raise AssertionError("the hub's fit notes name another part than the sleeve")
if SLEEVE.DISC_NUMBER != DISC_NUMBER:
    raise AssertionError("the hub's fit notes name another part than the disc")

# --- screw (MHA-PD-VN-55, McMaster 91794A055) ------------------------------------
SCREW_MAJOR_DIA, SCREW_LENGTH, SCREW_HEAD_H, SCREW_HEAD_DIA, _SCREW_PITCH = (
    FILLISTER_SIZE
)
# Head diameter allowance over the catalogue size (contract §8, "head +0.05").
SCREW_HEAD_DIA_ALLOWANCE = 0.05

# --- turned body ------------------------------------------------------------
# Every turned diameter but the spigot prints .XX.  The flange is sized so
# the screw holes' finished wall to its rim, less the title block's rim break
# and the holes' mouth break, holds the .080 target at the .XX row on both it
# and the bolt circle (machinist review: a .XXX flange held only to rescue
# that wall is over-specification; Codjiflo, #2124: Ø1.01 held it only
# before the breaks); the body's wall over the bore and the heads' air hold
# at .XX too.
FLANGE_DIA = 26.67  # 1.05
FLANGE_DIA_PLACES = 2
FLANGE_THICK = 2.3876  # .094
FLANGE_THICK_PLACES = 3  # the screw-tip-to-platen stack reads it (R9-5)
HUB_DIA = 13.716  # .540: the wall over the key pin's chord hole holds the floor
HUB_DIA_PLACES = 3
# The spigot (``pd_transgear_disc_hub_geometry``): its turned-row band is the
# model's, its length the cluster's printed band.
SPIGOT_DIA_DEVIATIONS = deviations(SPIGOT_DIA_BAND)
SPIGOT_DIA_MIN = SPIGOT_DIA + SPIGOT_DIA_BAND[1]
SPIGOT_LENGTH_MIN = SPIGOT_LENGTH - SPIGOT_LENGTH_BAND
SPIGOT_LENGTH_MAX = SPIGOT_LENGTH + SPIGOT_LENGTH_BAND

# --- overall: +/-.001 (owner ruling 2026-11-01, #2124) ----------------------
# Spigot end (on the step) to hub front face, a term of the disc cluster's
# stack (transgear_cluster_fit): it sets the collar air and leaves the front
# face never proud of the sleeve's nose at the worst case.
HUB_LENGTH = FIT.HUB_LENGTH
HUB_LENGTH_BAND = FIT.LENGTH_BAND
HUB_LENGTH_MIN = HUB_LENGTH - HUB_LENGTH_BAND
HUB_LENGTH_MAX = HUB_LENGTH + HUB_LENGTH_BAND
HUB_LENGTH_PLACES = FIT.LENGTH_PLACES
if HUB_LENGTH_MIN <= SPIGOT_LENGTH_MAX + FLANGE_THICK + printed_band_mm(
    FLANGE_THICK_PLACES, unit=UNIT
):
    raise AssertionError("MHA-PD-17 has no body between its flange and the nose")
# The hub body (flange front face to hub front face) is the remainder of the
# lengths; it is modelled, never printed.
HUB_BODY_LENGTH = HUB_LENGTH - SPIGOT_LENGTH - FLANGE_THICK
# Local z of the hub's front face (the spigot's end is z = +SPIGOT_LENGTH).
HUB_FRONT_Z = SPIGOT_LENGTH - HUB_LENGTH

# --- bore on the sleeve's boss (MHA-PD-10) ------------------------------------
# Plain round, reamed through: .313 +.0010/+.0005 (.3135-.3140), the shop's
# owned .3135 over reamer (``_fit_ream_slide``), a sliding fit on the boss's
# +.0005/.0000 band.  The hub does not drive through its bore: the key pin
# (below) keys it on the sleeve's flat.
BORE_DIA = SLEEVE.BOSS_DIA
BORE_PLACES = 4
BORE_BAND = (0.0254, 0.0127)  # (upper, lower) deviations: +.0010/+.0005
BORE_DEVIATIONS = deviations(BORE_BAND)
# The spigot's root at the flange stays sharp so the disc's front face
# seats on the flange: the disc's bore chamfer clears it.  The hub body's
# root takes the title block's inside corner; the #0-80 heads stand clear
# of its fillet (checked with the head air below).
CORNER_RADIUS_MAX = 0.1016  # .004
if DISC.BORE_FRONT_CHAMFER_LIMITS[0] < CORNER_RADIUS_MAX:
    raise AssertionError("the disc's bore chamfer rides the spigot's corner")
INSIDE_CORNER_RADIUS_MAX = inside_corner_radius_mm(unit=UNIT)

# (least, greatest) diametral clearance of the round bore on the sleeve's
# boss: each part is made to its own sheet, so it may not bind at any
# printed limit pair.
if BORE_DIA != SLEEVE.BOSS_DIA:
    raise AssertionError("the hub's bore is not the sleeve's boss size")
BOSS_CLEARANCE_LIMITS = (
    round(BORE_DIA + BORE_BAND[1] - (SLEEVE.BOSS_DIA + SLEEVE.BOSS_DIA_BAND[0]), 6),
    round(BORE_DIA + BORE_BAND[0] - (SLEEVE.BOSS_DIA + SLEEVE.BOSS_DIA_BAND[1]), 6),
)  # .0000 .. .0010
# The greatest: the hub's rock on the boss reads it.
BOSS_CLEARANCE = BOSS_CLEARANCE_LIMITS[1]
if BOSS_CLEARANCE_LIMITS[0] < 0.0:
    raise AssertionError(f"MHA-PD-17 binds on the sleeve's boss: {BOSS_CLEARANCE_LIMITS}")

# The spigot's end seats on the step.  The round
# engagement below still allows the conservative slide it was sized for:
# forward off the step by up to the disc's whole end float (hub on the front
# bushing, sleeve on the rear), its front face then past the nose.
_HUB_SLIDE_MAX = FIT.END_FLOAT_RANGE[1]
_TOOTH_LENGTHS = (
    SLEEVE.FACE_WIDTH - SLEEVE.FACE_WIDTH_BAND,
    SLEEVE.FACE_WIDTH + SLEEVE.FACE_WIDTH_BAND,
)
_SLEEVE_LENGTH_MIN = SLEEVE.OVERALL_LENGTH - SLEEVE.OVERALL_LENGTH_BAND


# Round engagement on the boss: from the boss's first full round (the hub
# bore's rear edge break, or ahead of it the form cutter's run-out slots at
# their deepest) to the hub bore's front edge break or the nose's, whichever
# is nearer, over the hub's slide.  The title block's edge break comes off
# every exposed end of the contact (codjiflo P2 on 6228b6ead), as the
# sleeve's own bearing span does (pd_cluster_air.SLEEVE_COCK).
_ENGAGEMENT_EDGE_BREAK = edge_break_chamfer_mm(unit=UNIT)
ROUND_ENGAGEMENT_MIN = min(
    *(
        tooth
        + HUB_LENGTH_MIN
        - _ENGAGEMENT_EDGE_BREAK
        - max(tooth + _ENGAGEMENT_EDGE_BREAK, SLEEVE.CUTTER_RUNOUT_END_WORST)
        for tooth in _TOOTH_LENGTHS
    ),
    _SLEEVE_LENGTH_MIN
    - _ENGAGEMENT_EDGE_BREAK
    - max(
        _TOOTH_LENGTHS[1] + _HUB_SLIDE_MAX + _ENGAGEMENT_EDGE_BREAK,
        SLEEVE.CUTTER_RUNOUT_END_WORST,
    ),
)

# --- the seat: the spigot's end on the sleeve's step ---------------------------
# The step face is the pinion's end between the boss and the tip circle.
# The spigot's end bears from its bore's edge break to the smallest tip
# circle (the tooth edges are never broken, TOOTH_EDGE_NOTE).
EDGE_BREAK_MAX = edge_break_chamfer_mm(unit=UNIT)  # .010
_BORE_MAX = BORE_DIA + BORE_BAND[0]
SEAT_INNER_R = _BORE_MAX / 2.0 + EDGE_BREAK_MAX
SEAT_CONTACT_R = (SLEEVE.OUTSIDE_DIA + SLEEVE.OUTSIDE_DIA_BAND[1]) / 2.0


# A real form cutter leaves partial-depth gaps at the step. Use the sleeve
# owner's bounded end-envelope sections, never a full-depth ideal involute.
# Compare every printed setting/tip/step/full-depth corner on the common
# contact annulus; smaller step-minus-depth and inward tool translation can
# only remove more of that annulus.  The sleeve prints only its full depth's
# MIN and the run-out's MAX, past the step, so the deepest corner is full
# depth at the step itself: the whole form gap, whatever cutter cut it.
SEAT_ANNULUS_AREA = math.pi * (SEAT_CONTACT_R**2 - SEAT_INNER_R**2)
_SEAT_AREA_BOUNDS = tuple(
    SLEEVE.step_seat_area_bounds_mm2(
        SEAT_INNER_R,
        SEAT_CONTACT_R,
        profile=profile,
        station_mm=station,
        full_depth_mm=min(full_depth, station),
    )
    for profile in SLEEVE.manufactured_profiles()
    for station in (
        SLEEVE.FACE_WIDTH - SLEEVE.FACE_WIDTH_BAND,
        SLEEVE.FACE_WIDTH + SLEEVE.FACE_WIDTH_BAND,
    )
    for full_depth in (SLEEVE.FULL_DEPTH_MIN, SLEEVE.FULL_DEPTH_MAX)
)
SEAT_CONTACT_AREA_BOUNDS = (
    min(lower for lower, _upper in _SEAT_AREA_BOUNDS),
    min(upper for _lower, upper in _SEAT_AREA_BOUNDS),
)
SEAT_CONTACT_AREA = SEAT_CONTACT_AREA_BOUNDS[0]
if not 0.0 < SEAT_CONTACT_AREA <= SEAT_CONTACT_AREA_BOUNDS[1] <= SEAT_ANNULUS_AREA:
    raise AssertionError("the finite cutter leaves no bounded spigot seat")
SEAT_ISLAND_FRACTION = SEAT_CONTACT_AREA / SEAT_ANNULUS_AREA

# --- geometric control --------------------------------------------------------
# All turned in one setup with the bore, datum A.  The flange's rear face
# clamps the disc's front face, and the spigot's end seats the hub on the
# step, so both are held square to A: the paper-drive assembly's disc tilt
# reads each value over its zone (the flange's diameter; the seat's contact
# circle) plus the hub's rock on the boss, the greatest clearance over the
# shortest round engagement, unpreloaded on the step.  Both print at the
# shop's .001 row (owner ruling 2026-11-08 (Pedro), #2144 item 3.2, for the
# spigot end): the collar-to-disc air the spigot end's squareness closes is
# felt at MHA-PD-00 and recovered there if short (pd_cluster_air.
# ASSEMBLY_ACCEPTED_COLLAR_SOURCES); the platen air still charges it.
BORE_DATUM = "A"
# The frame prints GEOMETRIC_TOLERANCES_IN; readers take the derived mm.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "flange rear face perpendicularity to bore": ".001",
    "spigot end perpendicularity to bore": ".001",
}
GEOMETRIC_TOLERANCES_MM: dict[str, float] = {
    key: float(value) * MM_PER_IN for key, value in GEOMETRIC_TOLERANCES_IN.items()
}
FLANGE_FACE_PERPENDICULARITY = float(
    GEOMETRIC_TOLERANCES_MM["flange rear face perpendicularity to bore"]
)
FLANGE_FACE_PERPENDICULARITY_ZONE_DIA = FLANGE_DIA
SPIGOT_END_PERPENDICULARITY = float(
    GEOMETRIC_TOLERANCES_MM["spigot end perpendicularity to bore"]
)
SPIGOT_END_PERPENDICULARITY_ZONE_DIA = 2.0 * SEAT_CONTACT_R
ROCK_ANGLE_MAX = BOSS_CLEARANCE / ROUND_ENGAGEMENT_MIN  # rad

# The disc's rear face stands in air ahead of the 12T's face: the shortest
# spigot less the thickest disc, less the disc's rear-face parallelism and
# its tilt (the step, the spigot's end, the flange's face and the rock) at
# its bore's edge.  The disc's bore is outside the 12T's tips, so this is
# axial air, never a radial overlap.
DISC_TILT_MAX = (
    SLEEVE.STEP_FACE_PERPENDICULARITY / SLEEVE.STEP_FACE_PERPENDICULARITY_ZONE_DIA
    + SPIGOT_END_PERPENDICULARITY / SPIGOT_END_PERPENDICULARITY_ZONE_DIA
    + FLANGE_FACE_PERPENDICULARITY / FLANGE_FACE_PERPENDICULARITY_ZONE_DIA
    + ROCK_ANGLE_MAX
)  # rad
DISC_STEP_GAP_NOMINAL = SPIGOT_LENGTH - DISC.FACE_WIDTH  # .026
DISC_STEP_GAP_WORST = (
    SPIGOT_LENGTH_MIN
    - DISC.FACE_WIDTH_MAX
    - DISC.REAR_FACE_PARALLELISM_BOUND_MM
    - DISC_TILT_MAX * DISC.BORE_DIA_MAX / 2.0
)
if DISC_STEP_GAP_WORST <= 0.0:
    raise AssertionError(
        f"the disc's rear face reaches the 12T: {DISC_STEP_GAP_WORST:.3f}"
    )

# --- drilled holes (the title block's DRILLED HOLES row, +.004/0) -----------
DRILL_OVERSIZE = drilled_oversize_mm(unit=UNIT)
SCREW_HOLE_PLACES = 3
OIL_HOLE_DIA = 1.0922  # .043, a #57 drill
OIL_HOLE_PLACES = 3

_BAND = {places: printed_band_mm(places, unit=UNIT) for places in (1, 2, 3)}

# --- the key pin across the sleeve's flat (MHA-PD-VN-69, McMaster 98381A416) --
# One 1/16 x 5/16 hardened alloy dowel on a chord of the hub body, parallel
# to local X, on the -Y side the sleeve's D-flat faces in the hub's frame
# (#2409, codjiflo round 2).  The chord hole is drilled #56 through, then
# reamed .0615 REAM_H7 from the +X side to a stop short of the -X O.D.: the
# pin is pressed in from +X until it bottoms on the step (a positive stop),
# and is knocked out through the #56 from -X (rule 16).  The chord breaks into
# the bore over the flat, so the pin's SIDE lies along the flat across the
# D-gap: the disc's torque runs disc -> disc screws -> hub flange -> key pin
# (bearing on its side, in shear between its two supported ends in the hub
# wall) -> flat -> sleeve, with no thrust along the pin, and the hub still
# slides off forward with the pin riding along the open-ended flat.  The
# hole sits at a printed .XX station behind the hub front face, the body's
# centre to the .01 grid (machinist review: a location given only as
# "centred" is missing), and .174 from the hub axis at the reamed-hole
# location band, as is its stop.
KEY_PIN_NUMBER = _config.parts("pd-vn-transgear-hub-key-pin")["number"]
KEY_PIN_HOLE_DIA = KEY_PIN.PRESS_HOLE_DIA  # .0615
KEY_PIN_HOLE_BAND = KEY_PIN.PRESS_HOLE_BAND  # REAM_H7, +.0005/.0000
KEY_PIN_HOLE_DEVIATIONS = deviations(KEY_PIN_HOLE_BAND)
KEY_PIN_HOLE_PLACES = 4
KEY_PIN_INTERFERENCE = KEY_PIN.PRESS_INTERFERENCE_MM  # (.0006, .0013) in
KEY_PIN_DRILL_DIA = 1.1811  # .0465, a #56 drill: the knockout, through
KEY_PIN_DRILL_PLACES = 4
_KEY_PIN_HOLE_MAX_R = (KEY_PIN_HOLE_DIA + max(KEY_PIN_HOLE_BAND)) / 2.0
_KEY_PIN_R_MIN = min(KEY_PIN.DIA_LIMITS_MM) / 2.0
_KEY_PIN_R_MAX = max(KEY_PIN.DIA_LIMITS_MM) / 2.0
if not KEY_PIN_DRILL_DIA + DRILL_OVERSIZE < KEY_PIN_HOLE_DIA:
    raise AssertionError("the #56 knockout leaves no step for the key pin to stop on")
# The chord's offset from the hub axis along local -Y, and the stop's from
# the axis along local -X, each at the reamed-hole location band.
KEY_PIN_CHORD_OFFSET = 4.4196  # .174
KEY_PIN_STOP = 4.064  # .160
KEY_PIN_STOP_X = -KEY_PIN_STOP
KEY_PIN_LOCATION_PLACES = 3
KEY_PIN_LOCATION_BAND = 0.0508  # +/-.002
KEY_PIN_CHORD_RANGE = (
    KEY_PIN_CHORD_OFFSET - KEY_PIN_LOCATION_BAND,
    KEY_PIN_CHORD_OFFSET + KEY_PIN_LOCATION_BAND,
)
KEY_PIN_STOP_RANGE = (
    KEY_PIN_STOP - KEY_PIN_LOCATION_BAND,
    KEY_PIN_STOP + KEY_PIN_LOCATION_BAND,
)
KEY_PIN_STATION = 3.81  # .15, behind the hub front face
KEY_PIN_STATION_PLACES = 2
# The hole's axis in the local frame: z here, at y = -KEY_PIN_CHORD_OFFSET.
KEY_PIN_Z = HUB_FRONT_Z + KEY_PIN_STATION
# (least, greatest) station of the hole's axis behind the hub front face.
KEY_PIN_STATION_RANGE = (
    KEY_PIN_STATION - _BAND[KEY_PIN_STATION_PLACES],
    KEY_PIN_STATION + _BAND[KEY_PIN_STATION_PLACES],
)
# The same axis in the sleeve's frame (its rear face z 0), the spigot's end
# on the step: the pin lies along the flat here, its whole section ahead of
# the flat's end wall at the shortest tooth length, hub and greatest
# station.
KEY_PIN_SLEEVE_Z = SLEEVE.FACE_WIDTH + HUB_LENGTH - KEY_PIN_STATION  # .924
KEY_PIN_FLAT_END_CLEARANCE_WORST = (
    _TOOTH_LENGTHS[0]
    + HUB_LENGTH_MIN
    - KEY_PIN_STATION_RANGE[1]
    - _KEY_PIN_HOLE_MAX_R
    - (SLEEVE.FLAT_END_STATION + SLEEVE.STATION_TOL)
)
if KEY_PIN_FLAT_END_CLEARANCE_WORST <= 0.0:
    raise AssertionError(
        "the key pin reaches the sleeve flat's end wall: "
        f"{KEY_PIN_FLAT_END_CLEARANCE_WORST:.3f}"
    )
# Air from the pin's side to the flat (mm): the chord's offset less the
# pin's radius less the flat's distance from the axis, at each extreme.  It
# never closes, so the pin never pinches the sleeve: the hub slides on.
_FLAT_RANGE = (
    SLEEVE.FLAT_TO_AXIS + SLEEVE.FLAT_TO_AXIS_BAND[1],
    SLEEVE.FLAT_TO_AXIS + SLEEVE.FLAT_TO_AXIS_BAND[0],
)
KEY_PIN_FLAT_AIR = (
    KEY_PIN_CHORD_RANGE[0] - _KEY_PIN_R_MAX - _FLAT_RANGE[1],
    KEY_PIN_CHORD_RANGE[1] - _KEY_PIN_R_MIN - _FLAT_RANGE[0],
)  # (.0006, .0087) in
if KEY_PIN_FLAT_AIR[0] <= 0.0:
    raise AssertionError(f"the key pin pinches the sleeve's flat: {KEY_PIN_FLAT_AIR}")
# The flat's least chord, where the boss's least round meets its deepest
# plane.
KEY_PIN_FLAT_CHORD_MIN = 2.0 * math.sqrt(
    ((SLEEVE.BOSS_DIA + SLEEVE.BOSS_DIA_BAND[1]) / 2.0) ** 2 - _FLAT_RANGE[1] ** 2
)
# The pin bears on the flat only where it crosses the bore: its side line
# nearest the axis is inside the least bore over half this length.
_BORE_R_MIN = (BORE_DIA + BORE_BAND[1]) / 2.0
_KEY_PIN_BEARING_HALF = math.sqrt(
    _BORE_R_MIN**2 - (KEY_PIN_CHORD_RANGE[1] - _KEY_PIN_R_MIN) ** 2
)
# Play: the hub turns on the flat until the pin's side meets it at the end
# of the shorter of the flat's half chord and the pin's bearing half; the
# paper drive turns one way, so the play is lost once, on reversal, through
# both sides of it at the 12T's pitch radius.
_KEY_PIN_LEVER = min(KEY_PIN_FLAT_CHORD_MIN / 2.0, _KEY_PIN_BEARING_HALF)
KEY_PIN_PLAY_DEG = math.degrees(KEY_PIN_FLAT_AIR[1] / _KEY_PIN_LEVER)
KEY_PIN_PAPER_LOST = 2.0 * math.radians(KEY_PIN_PLAY_DEG) * SLEEVE.PITCH_DIA / 2.0

# The oil hole is match-drilled at assembly through hub and sleeve together,
# at the key pin's station, opposite it on +Y.  The sleeve's model drills it at
# the same station in its own frame.  The chord hole stays wholly on -Y, so
# the two meet only across the bore's air.
OIL_HOLE_SLEEVE_Z = KEY_PIN_SLEEVE_Z
if not KEY_PIN_CHORD_RANGE[0] - _KEY_PIN_HOLE_MAX_R > 0.0:
    raise AssertionError("the key pin's chord hole reaches the oil hole's +Y side")

# --- worst-case walls (drawing-guidelines.md rule 17 (walls and webs)) ----------------------------------------
_SCREW_HOLE_MAX_R = (SCREW_HOLE_DIA + DRILL_OVERSIZE) / 2.0
_OIL_HOLE_MAX_R = (OIL_HOLE_DIA + DRILL_OVERSIZE) / 2.0
_HEAD_MAX_R = (SCREW_HEAD_DIA + SCREW_HEAD_DIA_ALLOWANCE) / 2.0
WALL_FLOOR = WALL_TARGET_MM
# Air from a disc screw's head to the hub body: a clearance for the driver
# and the head's seat clear of the body root's fillet, not a web.
HEAD_AIR_MIN = max(1.0, INSIDE_CORNER_RADIUS_MAX)


def body_wall_worst(hub_dia: float) -> float:
    """The wall over the round bore at the thinnest body the .XX row allows,
    over the bore at its largest."""
    return (hub_dia - _BAND[HUB_DIA_PLACES]) / 2.0 - _BORE_MAX / 2.0


def head_air_worst(bolt_circle_dia: float, hub_dia: float) -> float:
    """Air from the largest head, on the circle's nearest hole position, to
    the largest body."""
    return (
        bolt_circle_dia / 2.0
        - BOLT_CIRCLE_POSITION_TOL
        - _HEAD_MAX_R
        - (hub_dia + _BAND[HUB_DIA_PLACES]) / 2.0
    )


def hole_to_rim_worst(flange_dia: float, bolt_circle_dia: float) -> float:
    """Finished wall from the largest screw hole, on the circle's furthest
    hole position, to the smallest flange's rim: the rim's edge break and
    the hole's mouth break both come off it at the face."""
    return (
        (flange_dia - _BAND[FLANGE_DIA_PLACES]) / 2.0
        - (bolt_circle_dia / 2.0 + BOLT_CIRCLE_POSITION_TOL)
        - _SCREW_HOLE_MAX_R
        - 2.0 * EDGE_BREAK_MAX
    )


HUB_WALL_NOMINAL = (HUB_DIA - BORE_DIA) / 2.0
HUB_WALL_WORST = body_wall_worst(HUB_DIA)
SPIGOT_WALL_NOMINAL = (SPIGOT_DIA - BORE_DIA) / 2.0
SPIGOT_WALL_WORST = (SPIGOT_DIA_MIN - _BORE_MAX) / 2.0
HEAD_TO_HUB_NOMINAL = BOLT_CIRCLE_DIA / 2.0 - SCREW_HEAD_DIA / 2.0 - HUB_DIA / 2.0
HEAD_TO_HUB_WORST = head_air_worst(BOLT_CIRCLE_DIA, HUB_DIA)
HOLE_TO_RIM_NOMINAL = FLANGE_DIA / 2.0 - BOLT_CIRCLE_DIA / 2.0 - SCREW_HOLE_DIA / 2.0
HOLE_TO_RIM_WORST = hole_to_rim_worst(FLANGE_DIA, BOLT_CIRCLE_DIA)
HOLE_TO_BORE_WORST = (
    BOLT_CIRCLE_DIA / 2.0
    - BOLT_CIRCLE_POSITION_TOL
    - _SCREW_HOLE_MAX_R
    - _BORE_MAX / 2.0
)
# The holes' edges to the hub front face, and to the flange face: the
# station's printed band against the shortest body the overall less the
# longest spigot and thickest flange leaves.
HUB_BODY_LENGTH_RANGE = (
    HUB_LENGTH_MIN
    - SPIGOT_LENGTH_MAX
    - (FLANGE_THICK + _BAND[FLANGE_THICK_PLACES]),
    HUB_LENGTH_MAX
    - SPIGOT_LENGTH_MIN
    - (FLANGE_THICK - _BAND[FLANGE_THICK_PLACES]),
)


def _ligament_worst(radius: float) -> float:
    """Least ligament from a hole of ``radius`` on the key pin's axis to
    either end of the hub body."""
    return (
        min(
            KEY_PIN_STATION_RANGE[0],
            HUB_BODY_LENGTH_RANGE[0] - KEY_PIN_STATION_RANGE[1],
        )
        - radius
    )


KEY_PIN_LIGAMENT_WORST = _ligament_worst(_KEY_PIN_HOLE_MAX_R)  # .103
OIL_HOLE_LIGAMENT_NOMINAL = min(
    KEY_PIN_STATION, HUB_BODY_LENGTH - KEY_PIN_STATION
) - OIL_HOLE_DIA / 2.0
OIL_HOLE_LIGAMENT_WORST = _ligament_worst(_OIL_HOLE_MAX_R)
# The oil hole's ligament to the sleeve's nose (the sleeve's wall, judged
# against its .080 target): the hub front face at its least recess plus the
# hole's least station, less its largest radius.
OIL_HOLE_TO_NOSE = SLEEVE.OVERALL_LENGTH - OIL_HOLE_SLEEVE_Z - OIL_HOLE_DIA / 2.0
OIL_HOLE_TO_NOSE_WORST = (
    FIT.RECESS_RANGE[0] + KEY_PIN_STATION_RANGE[0] - _OIL_HOLE_MAX_R
)

for _label, _wall, _floor in (
    ("hub wall over the bore", HUB_WALL_WORST, WALL_FLOOR),
    ("spigot wall over the bore", SPIGOT_WALL_WORST, WALL_FLOOR),
    ("screw hole to bore", HOLE_TO_BORE_WORST, WALL_FLOOR),
    ("screw hole to flange rim", HOLE_TO_RIM_WORST, WALL_FLOOR),
    ("key-pin hole to either end of the hub body", KEY_PIN_LIGAMENT_WORST, WALL_FLOOR),
    ("oil hole to either end of the hub body", OIL_HOLE_LIGAMENT_WORST, WALL_FLOOR),
    ("oil hole to the sleeve nose", OIL_HOLE_TO_NOSE_WORST, SLEEVE.WALL_TARGET),
    ("screw head air to the hub body", HEAD_TO_HUB_WORST, HEAD_AIR_MIN),
):
    if _wall < _floor - 1e-9:
        raise AssertionError(f"MHA-PD-17 {_label}: {_wall:.3f} worst < floor {_floor}")

# Finished, the walls over the bore also pay the title block's .010 break at
# both edges of their exposed end (Codjiflo, #2124; the flange rim's
# pattern): the body's at the hub front face (the OD's rim and the bore's
# mouth), the spigot's at its end on the step.  The bore (the MHA-PD-10
# boss's) and the spigot (the MHA-PD-06 bore's) are the cluster's fits, so
# the body and spigot walls over the bore land between the .060 floor and
# the .080 target; the bore's callout states the least (rule 20;
# pd-transgear-disc-hub.yaml).
BORE_WALLS_FINISHED = {
    "hub wall over the bore": HUB_WALL_WORST - 2.0 * EDGE_BREAK_MAX,
    "spigot wall over the bore": SPIGOT_WALL_WORST - 2.0 * EDGE_BREAK_MAX,
}
for _label, _wall in BORE_WALLS_FINISHED.items():
    if _wall < WALL_FLOOR_MM - 1e-9:
        raise AssertionError(
            f"MHA-PD-17 {_label}: {_wall:.3f} finished < floor {WALL_FLOOR_MM}"
        )
BORE_WALL_FINISHED_MIN = min(BORE_WALLS_FINISHED.values())
BORE_WALL_TEXT = f"WALL {inch_text(DISC.inch_floor_mm(BORE_WALL_FINISHED_MIN, 3), 3)} MIN"

# --- the key pin in the hub wall: ends, support and the wall over it ---------
# Checked after the walls, so a coarser printed row trips the rule-17 gate
# first.  The pin bottoms on the stop, so it spans x = -stop .. length - stop.
KEY_PIN_END_X_RANGE = (
    KEY_PIN.LENGTH_LIMITS_MM[0] - KEY_PIN_STOP_RANGE[1],
    KEY_PIN.LENGTH_LIMITS_MM[1] - KEY_PIN_STOP_RANGE[0],
)  # its outer (+X) end
# Both ends stay under the hub's least O.D.: the ream's corner at its
# deepest stop and the pin's rim at its farthest outer end, each on the
# chord farthest from the axis.
_HUB_R_MIN = (HUB_DIA - _BAND[HUB_DIA_PLACES]) / 2.0
_CHORD_MAX = KEY_PIN_CHORD_RANGE[1]
KEY_PIN_END_RECESS_WORST = _HUB_R_MIN - max(
    math.hypot(KEY_PIN_STOP_RANGE[1], _CHORD_MAX + _KEY_PIN_HOLE_MAX_R),
    math.hypot(KEY_PIN_END_X_RANGE[1], _CHORD_MAX + _KEY_PIN_R_MAX),
)
if KEY_PIN_END_RECESS_WORST <= 0.0:
    raise AssertionError(
        f"the key pin's chord hole breaks out of the hub: {KEY_PIN_END_RECESS_WORST:.4f}"
    )
# The ream opens into the bore over the flat (the largest bore, the chord
# nearest the axis); the hub wall holds the pin over at least one diameter
# each side of that window.
_BORE_R_MAX = _BORE_MAX / 2.0
KEY_PIN_WINDOW_HALF = math.sqrt(
    _BORE_R_MAX**2 - (KEY_PIN_CHORD_RANGE[0] - _KEY_PIN_HOLE_MAX_R) ** 2
)
KEY_PIN_SUPPORT_WORST = (
    KEY_PIN_STOP_RANGE[0] - KEY_PIN_WINDOW_HALF,
    KEY_PIN_END_X_RANGE[0] - KEY_PIN_WINDOW_HALF,
)  # (-X side, +X side)
if min(KEY_PIN_SUPPORT_WORST) < KEY_PIN.DIA:
    raise AssertionError(
        f"the key pin is held over less than 1D of the hub wall: {KEY_PIN_SUPPORT_WORST}"
    )
# The wall over the ream to the least O.D., at the chord farthest from the
# axis: over the .060 floor, under the .080 target (pd-transgear-disc-hub.yaml
# minor); Ø.540 (.XXX, the title block's +/-.005) holds it, Ø.530 would not.
KEY_PIN_WALL_WORST = _HUB_R_MIN - (_CHORD_MAX + _KEY_PIN_HOLE_MAX_R)
if KEY_PIN_WALL_WORST < WALL_FLOOR_MM - 1e-9:
    raise AssertionError(
        f"MHA-PD-17 wall over the key pin's chord hole: {KEY_PIN_WALL_WORST:.3f} < floor"
    )

# --- sheet --------------------------------------------------------------------
# Each requirement is flagged at its feature (rule 7): a callout carries at
# most two lines of words, and the requirements several dimensions share are
# numbered notes their callouts link, each stated once.
COLLAR_NUMBER = _config.parts("pd-transgear-drive-collar")["number"]
# The hub O.D.'s third place is held for the wall over the key pin's chord
# ream (rule 3: a size finer than the turned row states its function): the
# least wall, floored at three places (rule 20), under the size.
HUB_DIA_CALLOUT_BELOW = "\n".join(
    (
        f"WALL {inch_text(DISC.inch_floor_mm(KEY_PIN_WALL_WORST, 3), 3)} MIN",
        "TO PIN REAM",
    )
)
# The bore is reamed through and slides on the sleeve's boss: the process,
# the fit by its standard name and its mate (rules 4 and 12), then the least
# finished wall over it (rule 20).
BORE_CALLOUT_BELOW = "\n".join(
    (
        "REAM THRU",
        f"SLIDING FIT ON {SLEEVE_NUMBER}",
        BORE_WALL_TEXT,
    )
)
# The overall and the spigot's length both print the disc cluster's band and
# serve one stack (rule 4): one note, named once, linked from both.
STACK_NOTE = 1
STACK_TEXT = f"{STACK_NAME}: SETS {COLLAR_NUMBER} TO {DISC_NUMBER} CLEARANCE."
HUB_LENGTH_CALLOUT = f"SEE NOTE {STACK_NOTE}"
SPIGOT_LENGTH_CALLOUT = f"SEE NOTE {STACK_NOTE}"
# The flange's .XXX thickness sets the disc screws' reach (the cut window
# in pd_vn_transgear_disc_screw_spec reads it).
FLANGE_THICK_CALLOUT = f"SETS {SCREW_NAME}\n{SCREW_NUMBER} REACH"
# The spigot slides into the disc's bore at assembly (the disc is then
# centred and its taps transferred); its turned-row band keeps it clear at
# the bore's least size.  The callout names the fit by its standard name
# (rule 4) and the sharp root the disc's face seats past: two lines of words
# (rule 7), so the clearance the limits give is not repeated as REF.
SPIGOT_CALLOUT_BELOW = "\n".join(
    (
        f"SLIDING FIT IN {DISC_NUMBER}",
        f"SPIGOT ROOT R{inch_text(CORNER_RADIUS_MAX, 3)} MAX",
    )
)

# Callouts the sheet hangs on the native dimensions.  The holes are drilled
# (the title block's DRILLED HOLES row governs their sizes); the three screw
# holes are one patterned feature, equally spaced on the printed circle.  The
# oil hole is drilled with the hub seated on the sleeve, through both, at the
# key pin's station (R9-60): a match-drill at assembly with its mate.
SCREW_HOLE_CALLOUT_ABOVE = f"{SCREW_COUNT}X"
SCREW_HOLE_CALLOUT_BELOW = "DRILL THRU FLANGE, EQ SP"
OIL_HOLE_CALLOUT_BELOW = "\n".join(
    (
        f"MATCH-DRILL WITH {SLEEVE_NUMBER}",
        "INTO BORE",
    )
)
# The chord hole prints in section A-A, cut through its station: the ream's
# size with its REAM_H7 band from the model, said reamed and naming the
# press fit's pin (rules 4 and 12); the #56 knockout drilled through; the
# chord's offset and the ream's stop from the hub axis at the reamed-hole
# location band, locations that carry their value and band only (rule 7).
KEY_PIN_CALLOUT_BELOW = "\n".join(("REAM, PRESS FIT", f"PIN {KEY_PIN_NUMBER}"))
KEY_PIN_DRILL_CALLOUT_BELOW = "#56 DRILL THRU"

# The key-pin hole's station lives on a hidden reference sketch: one
# construction line on the hub's +X O.D. line, from the hub front face to the
# hole's axis, whose driving dimension is the printed station (the hole's own
# profile places it from the same global).
REFERENCE_SKETCHES = ("KeyPinReference",)

# Marked model dimensions and the places the model authors on them (policy
# drawing-simplicity-policy.md `How the repository implements the guidelines`).  Edge view: the turned profile's three diameters, the spigot's and
# flange's lengths from the flange's rear face, the overall, the key-pin
# hole's station on the axis it shares with the oil hole, and the oil hole's
# size (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)); face view: the bore,
# and the screw holes on their bolt circle; section A-A: the key pin's chord
# hole, its ream, knockout, offset and stop.  The overall and the spigot
# print the disc cluster's +/-.001.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HubProfile": {
        "FlangeDia",
        "FlangeThick",
        "HubDia",
        "HubLength",
        "SpigotDia",
        "SpigotLength",
    },
    "BoreProfile": {"BoreDia"},
    "ScrewHoleProfile": {"BoltCircleDia", "ScrewHoleDia"},
    "OilHoleProfile": {"OilHoleDia"},
    "KeyPinProfile": {"KeyPinDia", "KeyPinDrillDia", "KeyPinChord", "KeyPinStop"},
    "KeyPinReference": {"KeyPinStation"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HubProfile": {
        "FlangeDia": FLANGE_DIA_PLACES,
        "FlangeThick": FLANGE_THICK_PLACES,
        "HubDia": HUB_DIA_PLACES,
        "HubLength": HUB_LENGTH_PLACES,
        "SpigotDia": SPIGOT_DIA_PLACES,
        "SpigotLength": SPIGOT_LENGTH_PLACES,
    },
    "BoreProfile": {"BoreDia": BORE_PLACES},
    "ScrewHoleProfile": {
        "BoltCircleDia": BOLT_CIRCLE_PLACES,
        "ScrewHoleDia": SCREW_HOLE_PLACES,
    },
    "OilHoleProfile": {"OilHoleDia": OIL_HOLE_PLACES},
    "KeyPinProfile": {
        "KeyPinDia": KEY_PIN_HOLE_PLACES,
        "KeyPinDrillDia": KEY_PIN_DRILL_PLACES,
        "KeyPinChord": KEY_PIN_LOCATION_PLACES,
        "KeyPinStop": KEY_PIN_LOCATION_PLACES,
    },
    "KeyPinReference": {"KeyPinStation": KEY_PIN_STATION_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {f: set(n) for f, n in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked MHA-PD-17 dimension needs its printed places")
if not set(REFERENCE_SKETCHES) <= set(DRAWING_DIMENSIONS):
    raise AssertionError("a hidden MHA-PD-17 reference sketch prints nothing")
REFERENCE_DIMENSIONS: frozenset[str] = frozenset()
