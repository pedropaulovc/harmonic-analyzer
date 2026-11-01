r"""MHA-PD-17 transgear-disc-hub: the brass hub and flange in front of the reducer disc.

The retained Ø.52 turned hub has a .313 +.0010/+.0005 bore (an owned .3135
reamer) on the pinion sleeve's (MHA-PD-10) .313 +.0005/.0000 boss and drives
through its D-flat, with a Ø1.01 × .094 flange and a Ø.501 SHAFT_H rear
spigot.  The spigot passes the reducer disc's (MHA-PD-06)
bore, which pilots on it, and its end seats on the sleeve's step face (the
12T's tooth ends); the flange's rear face clamps the disc's front face, the
spigot's length ahead of the step.  Three #0-80 fillister screws (MHA-PD-VN-55)
pass the flange's #51 holes on the Ø.75 circle into the disc's taps
(``pd_transgear_disc_hub_geometry``; the taps are spotted through these holes at
assembly, R9-9). The bore's round diameter holds its band over its whole
length; the flat only drives, from the flange's rear face forward, and starts
clear ahead of the sleeve flat's end wall.  Nothing fastens the hub axially: the spigot
bears rearward on the step, and the MHA-PD-25 front bushing, held by the
MHA-PD-VN-61 ring, traps hub and disc forward.  The hub's printed overall
leaves its front face ``transgear_cluster_fit.RECESS_RANGE`` behind the
sleeve's nose (never proud at the worst case), so the bushing, whose rear
face covers the hub's front face, bears on the steel nose and never thrusts
on the brass (R9-5).  The bore is
datum A; the flange's rear face and the spigot's end are held square to it,
all turned in one setup.  A #57 radial oil hole on +Y reaches the bore; it
is drilled through the hub wall and the sleeve's boss in one operation at
assembly (R9-8), at a printed .XX station from the hub front face, so the
sheet carries a match-drill callout, not a free drilled hole.

Sizes (drawing-guidelines.md rule 17 (walls and webs)): every wall holds the
.080 target at the printed worst case; the flange is Ø1.01 so the screw
hole keeps it to the rim with the flange and the circle both at .XX.

Printed lengths, from the spigot's end and the flange's rear face: the
overall, spigot end to hub front face, and the spigot (both terms of the
disc cluster's printed stack, #2038 owner ruling 2026-10-28: nothing in the
cluster is faced to fit; ``transgear_cluster_fit`` owns the overall), and
the flange .094 .XXX (the screw-tip-to-platen stack reads it).  The hub
body's own length is the remainder and is not printed.  Decimal inch
(#290): every nominal is the exact millimetre value of its printed inch.

Local frame (the build's, and the one the assembly mates): the gear axis is
Z through the origin (``Axis1``).  ``Front Plane`` (z = 0) is the flange's
rear face, the face that clamps the disc's front face; the spigot runs
z = 0..+SPIGOT_LENGTH, the flange z = -FLANGE_THICK..0 and the hub body down to the
front face, so local -Z is the machine's -Z (toward the operator).  Screw 0°
is local +X, angles counter-clockwise seen from +Z; the bore's flat is on
local -Y, the oil hole on local +Y, on the hub body.  The part sits
in the machine unrotated at z0 = ``transgear_cluster_fit.DISC_FRONT_Z``.

Pure data; no SolidWorks calls.  This module reads the cluster fit, the
sleeve's and the disc's specs; none reads it back.
"""

from __future__ import annotations

import math

import pd_rack_pinion_spec as DISC
import transgear_cluster_fit as FIT
import pd_transgear_feed_pinion_spec as SLEEVE
from _fit_deviations import deviations
from _inch_wall_limits import WALL_TARGET_MM
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
# feed pinion whose boss and flat the hub's bore slides on, the disc that
# pilots on the spigot, and the disc screws.
SLEEVE_NUMBER = "MHA-PD-10"
SLEEVE_NAME = "FEED PINION"
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
# the screw holes' wall to its rim holds the .080 target at the .XX row on
# both it and the bolt circle (machinist review: a .XXX flange held only to
# rescue that wall is over-specification); the body's walls over the bore
# and flat and the heads' air hold at .XX too.
FLANGE_DIA = 25.654  # 1.01
FLANGE_DIA_PLACES = 2
FLANGE_THICK = 2.3876  # .094
FLANGE_THICK_PLACES = 3  # the screw-tip-to-platen stack reads it (R9-5)
HUB_DIA = 13.208  # .52
HUB_DIA_PLACES = 2
# The spigot (``pd_transgear_disc_hub_geometry``): its SHAFT_H band is the
# model's, its length the cluster's printed band.
SPIGOT_DIA_DEVIATIONS = deviations(SPIGOT_DIA_BAND)
SPIGOT_DIA_MIN = SPIGOT_DIA + SPIGOT_DIA_BAND[1]
SPIGOT_LENGTH_MIN = SPIGOT_LENGTH - SPIGOT_LENGTH_BAND
SPIGOT_LENGTH_MAX = SPIGOT_LENGTH + SPIGOT_LENGTH_BAND

# --- overall: printed (#2038 owner ruling 2026-10-28, option A) ---------------
# Spigot end (on the step) to hub front face, a term of the disc cluster's
# printed stack (transgear_cluster_fit): it leaves the front face never proud
# of the sleeve's nose at the worst case.
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

# --- bore on the sleeve's boss and flat (MHA-PD-10) ---------------------------
# Round over the whole length: it locates on the boss's +.0005/.0000 band,
# .313 +.0010/+.0005.  The flat at local -Y only drives the disc's torque;
# its plane sits FLAT_TO_AXIS from the axis, printed +.0014/+.0008 above the
# sleeve flat's 0/-.0006 for a .0008-.0020 clearance.
BORE_DIA = SLEEVE.BOSS_DIA
BORE_PLACES = 4
BORE_BAND = (0.0254, 0.0127)  # (upper, lower) deviations: +.0010/+.0005
BORE_DEVIATIONS = deviations(BORE_BAND)
FLAT_TO_AXIS = SLEEVE.FLAT_TO_AXIS
FLAT_TO_AXIS_PLACES = 4
FLAT_TO_AXIS_BAND = (0.03556, 0.02032)  # (upper, lower) deviations: +.0014/+.0008
FLAT_TO_AXIS_DEVIATIONS = deviations(FLAT_TO_AXIS_BAND)
if not 0.0 < FLAT_TO_AXIS < BORE_DIA / 2.0:
    raise AssertionError("MHA-PD-17 bore flat must cut the round bore")
# The spigot's root at the flange stays sharp so the disc's front face
# seats on the flange: the disc's bore chamfer clears it.  The hub body's
# root takes the title block's inside corner; the #0-80 heads stand clear
# of its fillet (checked with the head air below).
CORNER_RADIUS_MAX = 0.1016  # .004
if DISC.BORE_FRONT_CHAMFER_LIMITS[0] < CORNER_RADIUS_MAX:
    raise AssertionError("the disc's bore chamfer rides the spigot's corner")
INSIDE_CORNER_RADIUS_MAX = inside_corner_radius_mm(unit=UNIT)

# (least, greatest) diametral clearance of the round bore on the sleeve's
# boss, and radial clearance of the flat on the sleeve's flat: each part is
# made to its own sheet, so neither may bind at any printed limit pair.
if BORE_DIA != SLEEVE.BOSS_DIA:
    raise AssertionError("the hub's bore is not the sleeve's boss size")
if FLAT_TO_AXIS != SLEEVE.FLAT_TO_AXIS:
    raise AssertionError("the hub's bore flat is not the sleeve's flat")
BOSS_CLEARANCE_LIMITS = (
    round(BORE_DIA + BORE_BAND[1] - (SLEEVE.BOSS_DIA + SLEEVE.BOSS_DIA_BAND[0]), 6),
    round(BORE_DIA + BORE_BAND[0] - (SLEEVE.BOSS_DIA + SLEEVE.BOSS_DIA_BAND[1]), 6),
)  # .0000 .. .0010
# The greatest: the hub's rock on the boss reads it.
BOSS_CLEARANCE = BOSS_CLEARANCE_LIMITS[1]
FLAT_CLEARANCE = (
    round(FLAT_TO_AXIS_BAND[1] - SLEEVE.FLAT_TO_AXIS_BAND[0], 6),
    round(FLAT_TO_AXIS_BAND[0] - SLEEVE.FLAT_TO_AXIS_BAND[1], 6),
)  # .0008 .. .0020
if BOSS_CLEARANCE_LIMITS[0] < 0.0:
    raise AssertionError(f"MHA-PD-17 binds on the sleeve's boss: {BOSS_CLEARANCE_LIMITS}")
if FLAT_CLEARANCE[0] <= 0.0:
    raise AssertionError(f"MHA-PD-17 flat binds on the sleeve's: {FLAT_CLEARANCE}")

# The hub's flat starts at the flange's rear face, the spigot's length ahead
# of the step; the sleeve flat's end wall stands behind it, so the wall never
# touches.  Worst: the shortest tooth length and spigot against the wall at
# its furthest forward.
FLAT_END_CLEARANCE_WORST = (
    SLEEVE.FACE_WIDTH
    - SLEEVE.FACE_WIDTH_BAND
    + SPIGOT_LENGTH_MIN
    - (SLEEVE.FLAT_END_STATION + SLEEVE.STATION_TOL)
)
if FLAT_END_CLEARANCE_WORST <= 0.0:
    raise AssertionError(
        f"the sleeve's flat end wall reaches the hub's flat: {FLAT_END_CLEARANCE_WORST:.3f}"
    )

# Available unbroken D-flat face, not a load or torque rating. Standard edge
# breaks are not subtracted here. The flat plane and its axial stations are
# retained while the smaller boss narrows its chord.
FLAT_DRIVE_WIDTH = 2.0 * math.sqrt(
    (SLEEVE.BOSS_DIA / 2.0) ** 2 - SLEEVE.FLAT_TO_AXIS**2
)
FLAT_DRIVE_WIDTH_MIN = 2.0 * math.sqrt(
    ((SLEEVE.BOSS_DIA + SLEEVE.BOSS_DIA_BAND[1]) / 2.0) ** 2
    - (SLEEVE.FLAT_TO_AXIS + SLEEVE.FLAT_TO_AXIS_BAND[0]) ** 2
)
# The hub slides on the boss: seated on the step, or forward off it by up to
# the disc's whole end float (hub on the front bushing, sleeve on the rear),
# its front face then past the nose.  The flat's overlap is the shorter.
_HUB_SLIDE_MAX = FIT.END_FLOAT_RANGE[1]
_TOOTH_LENGTHS = (
    SLEEVE.FACE_WIDTH - SLEEVE.FACE_WIDTH_BAND,
    SLEEVE.FACE_WIDTH + SLEEVE.FACE_WIDTH_BAND,
)
_SLEEVE_LENGTH_MIN = SLEEVE.OVERALL_LENGTH - SLEEVE.OVERALL_LENGTH_BAND
FLAT_DRIVE_LENGTH_MIN = min(
    HUB_LENGTH_MIN - SPIGOT_LENGTH_MAX,
    _SLEEVE_LENGTH_MIN - _TOOTH_LENGTHS[1] - _HUB_SLIDE_MAX - SPIGOT_LENGTH_MAX,
)
FLAT_DRIVE_FACE_AREA_MIN = FLAT_DRIVE_WIDTH_MIN * FLAT_DRIVE_LENGTH_MIN


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
# shortest round engagement, unpreloaded on the step.
BORE_DATUM = "A"
# The frame prints GEOMETRIC_TOLERANCES_IN; readers take the derived mm.
GEOMETRIC_TOLERANCES_IN: dict[str, str] = {
    "flange rear face perpendicularity to bore": ".001",
    "spigot end perpendicularity to bore": ".0002",
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
    - float(DISC.GEOMETRIC_TOLERANCES_MM["disc rear face parallelism to front"])
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
# The oil hole is match-drilled at assembly through hub and sleeve together,
# at a printed .XX station from the hub front face (machinist review: a
# location given only as "centred" is missing), the body's centre to the
# .01 grid.
OIL_HOLE_STATION = 3.81  # .15, behind the hub front face
OIL_HOLE_STATION_PLACES = 2
OIL_HOLE_Z = HUB_FRONT_Z + OIL_HOLE_STATION  # in the local frame
# The same hole in the sleeve's frame (its rear face z 0): the spigot's end
# stands on the step.  The sleeve's model drills it here.
OIL_HOLE_SLEEVE_Z = SLEEVE.FACE_WIDTH + HUB_LENGTH - OIL_HOLE_STATION

_BAND = {places: printed_band_mm(places, unit=UNIT) for places in (1, 2, 3)}

# --- worst-case walls (drawing-guidelines.md rule 17 (walls and webs)) ----------------------------------------
_FLAT_MAX = FLAT_TO_AXIS + FLAT_TO_AXIS_BAND[0]
_SCREW_HOLE_MAX_R = (SCREW_HOLE_DIA + DRILL_OVERSIZE) / 2.0
_OIL_HOLE_MAX_R = (OIL_HOLE_DIA + DRILL_OVERSIZE) / 2.0
_HEAD_MAX_R = (SCREW_HEAD_DIA + SCREW_HEAD_DIA_ALLOWANCE) / 2.0
WALL_FLOOR = WALL_TARGET_MM
# Air from a disc screw's head to the hub body: a clearance for the driver
# and the head's seat clear of the body root's fillet, not a web.
HEAD_AIR_MIN = max(1.0, INSIDE_CORNER_RADIUS_MAX)


def body_walls_worst(hub_dia: float) -> tuple[float, float]:
    """(wall over the round bore, wall over the flat) at the thinnest body
    the .XXX row allows, over the bore and flat at their largest."""
    body_r_min = (hub_dia - _BAND[HUB_DIA_PLACES]) / 2.0
    return body_r_min - _BORE_MAX / 2.0, body_r_min - _FLAT_MAX


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
    """Wall from the largest screw hole, on the circle's furthest hole
    position, to the smallest flange's rim."""
    return (
        (flange_dia - _BAND[FLANGE_DIA_PLACES]) / 2.0
        - (bolt_circle_dia / 2.0 + BOLT_CIRCLE_POSITION_TOL)
        - _SCREW_HOLE_MAX_R
    )


HUB_WALL_NOMINAL = (HUB_DIA - BORE_DIA) / 2.0
HUB_WALL_WORST, FLAT_WALL_WORST = body_walls_worst(HUB_DIA)
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
# The hole's edge to the hub front face, and to the flange face: the
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
# (least, greatest) station of the hole centre behind the hub front face.
OIL_HOLE_STATION_RANGE = (
    OIL_HOLE_STATION - _BAND[OIL_HOLE_STATION_PLACES],
    OIL_HOLE_STATION + _BAND[OIL_HOLE_STATION_PLACES],
)
OIL_HOLE_LIGAMENT_NOMINAL = min(
    OIL_HOLE_STATION, HUB_BODY_LENGTH - OIL_HOLE_STATION
) - OIL_HOLE_DIA / 2.0
OIL_HOLE_LIGAMENT_WORST = min(
    OIL_HOLE_STATION_RANGE[0],
    HUB_BODY_LENGTH_RANGE[0] - OIL_HOLE_STATION_RANGE[1],
) - _OIL_HOLE_MAX_R
# The same hole's ligament to the sleeve's nose (the sleeve's wall, judged
# against its .080 target): the hub front face at its least recess plus the
# hole's least station, less its largest radius.
OIL_HOLE_TO_NOSE = SLEEVE.OVERALL_LENGTH - OIL_HOLE_SLEEVE_Z - OIL_HOLE_DIA / 2.0
OIL_HOLE_TO_NOSE_WORST = (
    FIT.RECESS_RANGE[0] + OIL_HOLE_STATION_RANGE[0] - _OIL_HOLE_MAX_R
)

for _label, _wall, _floor in (
    ("hub wall over the bore", HUB_WALL_WORST, WALL_FLOOR),
    ("hub wall over the flat", FLAT_WALL_WORST, WALL_FLOOR),
    ("spigot wall over the bore", SPIGOT_WALL_WORST, WALL_FLOOR),
    ("screw hole to bore", HOLE_TO_BORE_WORST, WALL_FLOOR),
    ("screw hole to flange rim", HOLE_TO_RIM_WORST, WALL_FLOOR),
    ("oil hole to either end of the hub body", OIL_HOLE_LIGAMENT_WORST, WALL_FLOOR),
    ("oil hole to the sleeve nose", OIL_HOLE_TO_NOSE_WORST, SLEEVE.WALL_TARGET),
    ("screw head air to the hub body", HEAD_TO_HUB_WORST, HEAD_AIR_MIN),
):
    if _wall < _floor - 1e-9:
        raise AssertionError(f"MHA-PD-17 {_label}: {_wall:.3f} worst < floor {_floor}")

# --- sheet --------------------------------------------------------------------
# No loose notes: each requirement is flagged at its feature (rule 7).
# The two printed stack lengths name the stack they serve (rule 4); the
# overall's reason is the nose it must never pass.
HUB_LENGTH_CALLOUT = f"{STACK_NAME},\nNOT PROUD OF {SLEEVE_NAME} {SLEEVE_NUMBER} NOSE"
SPIGOT_LENGTH_CALLOUT = STACK_NAME
# The flange's .XXX thickness sets the disc screws' reach (the cut window
# in pd_vn_transgear_disc_screw_spec reads it).
FLANGE_THICK_CALLOUT = f"SETS {SCREW_NAME}\n{SCREW_NUMBER} REACH"
# The spigot's native SHAFT_H limits print with the dimension; the callout
# names its sharp root, the mate and the clearance the pair gives.
SPIGOT_CALLOUT_BELOW = "\n".join(
    (
        f"SPIGOT ROOT R{inch_text(CORNER_RADIUS_MAX, 3)} MAX",
        f"(DIA CLR {inch_text(DISC.SPIGOT_DIAMETRAL_CLEARANCE[0], 4)}-"
        f"{inch_text(DISC.SPIGOT_DIAMETRAL_CLEARANCE[1], 4)}",
        f"IN {DISC_NAME} {DISC_NUMBER} BORE)",
    )
)

# Callouts the sheet hangs on the native dimensions.  The holes are drilled
# (the title block's DRILLED HOLES row governs their sizes); the three screw
# holes are one patterned feature, equally spaced on the printed circle.  The
# oil hole is drilled with the hub seated on the sleeve, through both, at its
# printed station (R9-60): the crank pinion's pin-hole wording
# (dt_crank_pinion_spec.pin_hole_note).
SCREW_HOLE_CALLOUT_ABOVE = f"{SCREW_COUNT}X"
SCREW_HOLE_CALLOUT_BELOW = "DRILL THRU FLANGE, EQ SP"
# The hole is drilled on +Y, through the round wall opposite the bore's
# flat on -Y (the face view shows the flat), into the bore.
OIL_HOLE_CALLOUT_BELOW = "\n".join(
    (
        "MATCH DRILL AT ASSY WITH",
        "HUB SEATED ON FEED PINION",
        f"{SLEEVE_NUMBER}, THRU ONE WALL",
        "OPPOSITE BORE FLAT",
    )
)

# Marked model dimensions and the places the model authors on them (policy
# drawing-simplicity-policy.md `How the repository implements the guidelines`).  Edge view: the turned profile's three diameters, the spigot's and
# flange's lengths from the flange's rear face, the overall, and the oil
# hole's size and station (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)); face view: the bore and its flat, which only show
# there, and the screw holes on their bolt circle.  The overall and the
# spigot print the disc cluster's band (#2038).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HubProfile": {
        "FlangeDia",
        "FlangeThick",
        "HubDia",
        "HubLength",
        "SpigotDia",
        "SpigotLength",
    },
    "BoreProfile": {"BoreDia", "FlatToAxis"},
    "ScrewHoleProfile": {"BoltCircleDia", "ScrewHoleDia"},
    "OilHoleProfile": {"OilHoleDia", "OilHoleStation"},
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
    "BoreProfile": {"BoreDia": BORE_PLACES, "FlatToAxis": FLAT_TO_AXIS_PLACES},
    "ScrewHoleProfile": {
        "BoltCircleDia": BOLT_CIRCLE_PLACES,
        "ScrewHoleDia": SCREW_HOLE_PLACES,
    },
    "OilHoleProfile": {
        "OilHoleDia": OIL_HOLE_PLACES,
        "OilHoleStation": OIL_HOLE_STATION_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {f: set(n) for f, n in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked MHA-PD-17 dimension needs its printed places")
REFERENCE_DIMENSIONS: frozenset[str] = frozenset()
