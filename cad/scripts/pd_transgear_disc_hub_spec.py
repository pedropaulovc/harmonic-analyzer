r"""MHA-PD-017 transgear-disc-hub: the brass hub and flange in front of the 120T disc.

R9-68 (rev 5): a Ø13.2 turned hub whose bore slides on the pinion sleeve's
(MHA-PD-010) Ø9 boss and drives through its D-flat, with a Ø25.1 × 2.4 flange
and a Ø13.1 h6 rear spigot.  The spigot passes the 120T disc's (MHA-PD-006)
bore, which pilots on it, and its end seats on the sleeve's step face (the
12T's tooth ends); the flange's rear face clamps the disc's front face, the
spigot's length ahead of the step.  Three #0-80 fillister screws (MHA-VN-039)
pass the flange's Ø1.7 holes on the Ø19 circle into the disc's taps
(``transgear_disc_hub_geometry``; the taps are spotted through these holes at
assembly, R9-9).  The bore is Ø9 H7 round over its whole length; the flat
only drives, from the flange's rear face forward, and starts clear ahead of
the sleeve flat's end wall.  Nothing fastens the hub axially: the spigot
bears rearward on the step, and the MHA-PD-025 front bushing, held by the
MHA-VN-047 ring, traps hub and disc forward.  The hub's front face is faced at
assembly to stand ``transgear_cluster_fit.HUB_NOSE_WINDOW`` behind the
sleeve's nose, so the bushing, whose rear face covers the hub's front face,
bears on the steel nose and never thrusts on the brass (R9-5).  The bore is
datum A; the flange's rear face and the spigot's end are held square to it,
all turned in one setup.  A Ø1.2 radial oil hole on +Y reaches the bore; it
is drilled through the hub wall and the sleeve's boss in one operation at
assembly (R9-8), centred on the hub body (R9-60), so the sheet carries a
match-drill note, not a free drilled hole.

Sizes (policy rule 12): the body is the smallest .XXX diameter that keeps
2.0 of wall over the bore and its flat, the circle the smallest that keeps
the screw heads 1.0 clear of the body and the disc's taps 2.0 from its bore,
and the flange the smallest .XXX diameter that keeps 2.0 from the holes to
its rim, each at the printed worst case and each on a 0.1 step.

Printed lengths, from the flange's rear face: the spigot 3.650 .XXX (it
places the disc on the step) and the flange 2.400 .XXX (the
screw-tip-to-platen stack reads it).  The overall, spigot end to hub front
face, is set at assembly (faced to fit; ``transgear_cluster_fit`` owns the
fitted band and the model length), so it prints as a reference under its
fit-up callout and the blank's MIN goes in the notes.  The hub body's own
length is the remainder and is not printed.

Local frame (the build's, and the one the assembly mates): the gear axis is
Z through the origin (``Axis1``).  ``Front Plane`` (z = 0) is the flange's
rear face, the face that clamps the disc's front face; the spigot runs
z = 0..+SPIGOT_LENGTH, the flange z = -2.4..0 and the hub body down to the
front face, so local -Z is the machine's -Z (toward the operator).  Screw 0°
is local +X, angles counter-clockwise seen from +Z; the bore's flat is on
local -Y, the oil hole on local +Y, centred on the hub body.  The part sits
in the machine unrotated at z0 = -147.65.

Pure data; no SolidWorks calls.  This module reads the cluster fit, the
sleeve's and the disc's specs; none reads it back.
"""

from __future__ import annotations

import math

import _config
import pd_rack_pinion_spec as DISC
import transgear_cluster_fit as FIT
import pd_transgear_feed_pinion_spec as SLEEVE
from _fit_limits import deviations
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES
from pd_transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_PLACES,
    BOLT_CIRCLE_POSITION_TOL,
    SCREW_COUNT,
    SCREW_HOLE_DIA,
    SCREW_SKU,
    SPIGOT_DIA,
    SPIGOT_DIA_BAND,
    SPIGOT_DIA_PLACES,
    SPIGOT_LENGTH,
    SPIGOT_LENGTH_BAND,
    SPIGOT_LENGTH_PLACES,
)

# The mating parts the sheet names, by name and number (policy rule 2): the
# feed pinion whose Ø9 boss and flat the hub's bore slides on, the disc that
# pilots on the spigot, and the disc screws.
SLEEVE_NUMBER = "MHA-PD-010"
SLEEVE_NAME = "FEED PINION"
DISC_NUMBER = "MHA-PD-006"
DISC_NAME = "DISC"
SCREW_NUMBER = "MHA-VN-039"
SCREW_NAME = "DISC SCREW"
if SLEEVE.SLEEVE_NUMBER != SLEEVE_NUMBER:
    raise AssertionError("the hub's fit notes name another part than the sleeve")
if SLEEVE.DISC_NUMBER != DISC_NUMBER:
    raise AssertionError("the hub's fit notes name another part than the disc")

# --- screw (MHA-VN-039, McMaster 91794A055) ------------------------------------
SCREW_MAJOR_DIA, SCREW_LENGTH, SCREW_HEAD_H, SCREW_HEAD_DIA, _SCREW_PITCH = (
    FILLISTER_SIZES[SCREW_SKU]
)
# Head diameter allowance over the catalogue size (contract §8, "head +0.05").
SCREW_HEAD_DIA_ALLOWANCE = 0.05

# --- turned body ------------------------------------------------------------
# .XXX on both diameters: the bore's walls and the heads' air read the body,
# the hole-to-rim wall the flange.
FLANGE_DIA = 25.1
FLANGE_DIA_PLACES = 3
FLANGE_THICK = 2.4
FLANGE_THICK_PLACES = 3  # the screw-tip-to-platen stack reads it (R9-5)
HUB_DIA = 13.2
HUB_DIA_PLACES = 3
# The spigot (``pd_transgear_disc_hub_geometry``): its h6 band is the model's,
# its length .XXX.
SPIGOT_DIA_DEVIATIONS = deviations(SPIGOT_DIA_BAND)
SPIGOT_DIA_MIN = SPIGOT_DIA + SPIGOT_DIA_BAND[1]
SPIGOT_LENGTH_MIN = SPIGOT_LENGTH - SPIGOT_LENGTH_BAND
SPIGOT_LENGTH_MAX = SPIGOT_LENGTH + SPIGOT_LENGTH_BAND
if FIT.HUB_CHAIN_NOMINAL <= SPIGOT_LENGTH + FLANGE_THICK:
    raise AssertionError("MHA-PD-017 has no body between its flange and the nose")

# --- length: faced to the sleeve's nose at assembly --------------------------
# Spigot end (on the step) to hub front face.  The model is the fitted
# band's nominal (the nose window's centre); the sheet prints it as a
# reference under the fitted band.
HUB_LENGTH = FIT.HUB_LENGTH_MODEL  # 13.70
HUB_LENGTH_FITTED_MIN = FIT.HUB_LENGTH_FITTED_MIN  # 13.47
HUB_LENGTH_FITTED_MAX = FIT.HUB_LENGTH_FITTED_MAX  # 13.93
HUB_LENGTH_PLACES = 2
# The blank is turned long and faced at fit-up: the longest fit plus one
# finishing cut (the front bushing's allowance).
FACING_ALLOWANCE = 0.10
BLANK_LENGTH_MIN = 14.05
if BLANK_LENGTH_MIN < HUB_LENGTH_FITTED_MAX + FACING_ALLOWANCE - 1e-9:
    raise AssertionError(
        f"MHA-PD-017 blank {BLANK_LENGTH_MIN:.2f} MIN leaves no {FACING_ALLOWANCE} "
        f"facing allowance over the {HUB_LENGTH_FITTED_MAX:.3f} longest fit"
    )
# The hub body (flange front face to hub front face) is the remainder of the
# lengths; it is modelled, never printed.
HUB_BODY_LENGTH = HUB_LENGTH - SPIGOT_LENGTH - FLANGE_THICK  # 7.65
# Local z of the hub's front face (the spigot's end is z = +SPIGOT_LENGTH).
HUB_FRONT_Z = SPIGOT_LENGTH - HUB_LENGTH  # -10.05

# --- bore on the sleeve's boss and flat (MHA-PD-010) ---------------------------
# Round over the whole length: it locates on the boss's h6 band, ISO H7 at
# 6-10 mm.  The flat at local -Y only drives the disc's torque; its plane sits
# FLAT_TO_AXIS from the axis, printed with a band above the sleeve flat's
# (0, -0.015) for a 0.020-0.050 clearance.
BORE_DIA = 9.0
BORE_PLACES = 3
BORE_BAND = (0.015, 0.0)  # (upper, lower) deviations, H7
BORE_DEVIATIONS = deviations(BORE_BAND)
FLAT_TO_AXIS = 3.5
FLAT_TO_AXIS_PLACES = 3
FLAT_TO_AXIS_BAND = (0.035, 0.020)  # (upper, lower) deviations
FLAT_TO_AXIS_DEVIATIONS = deviations(FLAT_TO_AXIS_BAND)
if not 0.0 < FLAT_TO_AXIS < BORE_DIA / 2.0:
    raise AssertionError("MHA-PD-017 bore flat must cut the round bore")
# Both corners at the flange stay sharp: the #0-80 heads sit beside the
# hub's, and the disc's bore chamfer clears the spigot's.
CORNER_RADIUS_MAX = 0.1
if DISC.BORE_FRONT_CHAMFER_LIMITS[0] < CORNER_RADIUS_MAX:
    raise AssertionError("the disc's bore chamfer rides the spigot's corner")

# (least, greatest) diametral clearance of the round bore on the sleeve's
# boss, and radial clearance of the flat on the sleeve's flat: each part is
# made to its own sheet, so neither may bind at any printed limit pair.
if BORE_DIA != SLEEVE.BOSS_DIA:
    raise AssertionError("the hub's bore is not the sleeve's boss size")
if FLAT_TO_AXIS != SLEEVE.FLAT_TO_AXIS:
    raise AssertionError("the hub's bore flat is not the sleeve's flat")
BOSS_CLEARANCE_LIMITS = (
    round(BORE_DIA + BORE_BAND[1] - (SLEEVE.BOSS_DIA + SLEEVE.BOSS_DIA_BAND[0]), 3),
    round(BORE_DIA + BORE_BAND[0] - (SLEEVE.BOSS_DIA + SLEEVE.BOSS_DIA_BAND[1]), 3),
)  # 0.000 .. 0.024
# The greatest: the hub's rock on the boss reads it.
BOSS_CLEARANCE = BOSS_CLEARANCE_LIMITS[1]  # 0.024
FLAT_CLEARANCE = (
    round(FLAT_TO_AXIS_BAND[1] - SLEEVE.FLAT_TO_AXIS_BAND[0], 3),
    round(FLAT_TO_AXIS_BAND[0] - SLEEVE.FLAT_TO_AXIS_BAND[1], 3),
)  # 0.020 .. 0.050
if BOSS_CLEARANCE_LIMITS[0] < 0.0:
    raise AssertionError(f"MHA-PD-017 binds on the sleeve's boss: {BOSS_CLEARANCE_LIMITS}")
if FLAT_CLEARANCE[0] <= 0.0:
    raise AssertionError(f"MHA-PD-017 flat binds on the sleeve's: {FLAT_CLEARANCE}")

# The hub's flat starts at the flange's rear face, the spigot's length ahead
# of the step; the sleeve flat's end wall stands behind it, so the wall never
# touches.  Worst: the shortest tooth length and spigot against the wall at
# its furthest forward.
FLAT_END_CLEARANCE_WORST = (
    SLEEVE.FACE_WIDTH
    - SLEEVE.FACE_WIDTH_BAND
    + SPIGOT_LENGTH_MIN
    - (SLEEVE.FLAT_END_STATION + SLEEVE.STATION_TOL)
)  # 0.34
if FLAT_END_CLEARANCE_WORST <= 0.0:
    raise AssertionError(
        f"the sleeve's flat end wall reaches the hub's flat: {FLAT_END_CLEARANCE_WORST:.3f}"
    )

# Round engagement on the boss: from the boss's first full round (the step,
# or behind it the form cutter's run-out slots at their deepest) to the hub
# front face at the nose window's furthest back on the shortest sleeve.  The
# title block's edge breaks at both ends are not subtracted.
ROUND_ENGAGEMENT_MIN = (
    SLEEVE.OVERALL_LENGTH
    - SLEEVE.STATION_TOL
    - FIT.HUB_NOSE_WINDOW[1]
    - max(SLEEVE.FACE_WIDTH + SLEEVE.FACE_WIDTH_BAND, SLEEVE.CUTTER_RUNOUT_END_WORST)
)  # 13.411

# --- the seat: the spigot's end on the sleeve's step ---------------------------
# The step face is the 12T's tooth ends between the boss (r 4.5) and the tip
# circle: the gaps run below the boss.  The spigot's end bears on those
# islands from its bore's edge break to the smallest tip circle (the teeth's
# edges are never broken, TOOTH_EDGE_NOTE).
EDGE_BREAK_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])  # 0.25
_BORE_MAX = BORE_DIA + BORE_BAND[0]
SEAT_INNER_R = _BORE_MAX / 2.0 + EDGE_BREAK_MAX  # 4.7575
SEAT_CONTACT_R = (SLEEVE.OUTSIDE_DIA + SLEEVE.OUTSIDE_DIA_BAND[1]) / 2.0  # 5.877


def _inv(angle: float) -> float:
    return math.tan(angle) - angle


def tooth_half_angle(radius: float) -> float:
    """Half the angle one 12T tooth subtends at ``radius`` (rad): the involute
    above the base circle, the radial flank below it."""
    pitch_r = SLEEVE.PITCH_DIA / 2.0
    phi = math.radians(SLEEVE.PRESSURE_ANGLE_DEG)
    base_r = pitch_r * math.cos(phi)
    thickness = math.pi * SLEEVE.MODULE_MM / 2.0  # circular, at the pitch circle
    phi_r = math.acos(base_r / max(radius, base_r))
    return thickness / (2.0 * pitch_r) + _inv(phi) - _inv(phi_r)


def tooth_island_area(inner_r: float, outer_r: float, steps: int = 2000) -> float:
    """Area of the 12T's tooth ends between two radii (mm^2), midpoint rule."""
    h = (outer_r - inner_r) / steps
    return sum(
        2.0 * SLEEVE.TEETH * tooth_half_angle(r) * r * h
        for r in (inner_r + (i + 0.5) * h for i in range(steps))
    )


if tooth_half_angle(SEAT_CONTACT_R) <= 0.0:
    raise AssertionError("the 12T's teeth are pointed inside the seat")
SEAT_ANNULUS_AREA = math.pi * (SEAT_CONTACT_R**2 - SEAT_INNER_R**2)
SEAT_CONTACT_AREA = tooth_island_area(SEAT_INNER_R, SEAT_CONTACT_R)
SEAT_ISLAND_FRACTION = SEAT_CONTACT_AREA / SEAT_ANNULUS_AREA

# --- geometric control --------------------------------------------------------
# All turned in one setup with the bore, datum A.  The flange's rear face
# clamps the disc's front face, and the spigot's end seats the hub on the
# step, so both are held square to A: the paper-drive assembly's disc tilt
# reads each value over its zone (the flange's diameter; the seat's contact
# circle) plus the hub's rock on the boss, the greatest clearance over the
# shortest round engagement, unpreloaded on the step.
BORE_DATUM = "A"
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "flange rear face perpendicularity to bore": "0.03",
    "spigot end perpendicularity to bore": "0.005",
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
DISC_STEP_GAP_NOMINAL = SPIGOT_LENGTH - DISC.FACE_WIDTH  # 0.65
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

# --- drilled holes (the title block's DRILLED HOLES row, +0.10/0) -----------
DRILL_OVERSIZE = drilled_oversize_mm()
SCREW_HOLE_PLACES = 1
OIL_HOLE_DIA = 1.2
OIL_HOLE_PLACES = 1
# The oil hole is centred on the hub body (R9-60): it is match-drilled at
# assembly, after the front face is faced, so the drill finds the body's
# centre at fit-up instead of a printed station.
OIL_HOLE_STATION = HUB_BODY_LENGTH / 2.0  # 3.825 behind the hub front face
# Marking the body's centre with a rule at fit-up.
OIL_HOLE_CENTRING_TOL = 0.25
OIL_HOLE_Z = HUB_FRONT_Z + OIL_HOLE_STATION  # -6.225 in the local frame
# The same hole in the sleeve's frame (its rear face z 0): the spigot's end
# stands on the step.  The sleeve's model drills it here.
OIL_HOLE_SLEEVE_Z = SLEEVE.FACE_WIDTH + HUB_LENGTH - OIL_HOLE_STATION  # 23.475

_BAND = {places: printed_band_mm(places) for places in (1, 2, 3)}

# --- worst-case walls (policy rule 12) ----------------------------------------
_FLAT_MAX = FLAT_TO_AXIS + FLAT_TO_AXIS_BAND[0]
_SCREW_HOLE_MAX_R = (SCREW_HOLE_DIA + DRILL_OVERSIZE) / 2.0
_OIL_HOLE_MAX_R = (OIL_HOLE_DIA + DRILL_OVERSIZE) / 2.0
_HEAD_MAX_R = (SCREW_HEAD_DIA + SCREW_HEAD_DIA_ALLOWANCE) / 2.0
WALL_FLOOR = 2.0
# Air from a disc screw's head to the hub body: a clearance for the driver
# and the head's seat beside the sharp corner, not a web.
HEAD_AIR_MIN = 1.0


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
HUB_WALL_WORST, FLAT_WALL_WORST = body_walls_worst(HUB_DIA)  # 2.0275, 3.000
SPIGOT_WALL_NOMINAL = (SPIGOT_DIA - BORE_DIA) / 2.0
SPIGOT_WALL_WORST = (SPIGOT_DIA_MIN - _BORE_MAX) / 2.0  # 2.037
HEAD_TO_HUB_NOMINAL = BOLT_CIRCLE_DIA / 2.0 - SCREW_HEAD_DIA / 2.0 - HUB_DIA / 2.0
HEAD_TO_HUB_WORST = head_air_worst(BOLT_CIRCLE_DIA, HUB_DIA)  # 1.526
HOLE_TO_RIM_NOMINAL = FLANGE_DIA / 2.0 - BOLT_CIRCLE_DIA / 2.0 - SCREW_HOLE_DIA / 2.0
HOLE_TO_RIM_WORST = hole_to_rim_worst(FLANGE_DIA, BOLT_CIRCLE_DIA)  # 2.020
HOLE_TO_BORE_WORST = (
    BOLT_CIRCLE_DIA / 2.0
    - BOLT_CIRCLE_POSITION_TOL
    - _SCREW_HOLE_MAX_R
    - _BORE_MAX / 2.0
)
# The hole is centred on the faced body, so its edge sits the same distance
# from the hub front face and from the flange face: the shortest fitted
# overall less the longest spigot and thickest flange, and the reverse.
HUB_BODY_LENGTH_RANGE = (
    HUB_LENGTH_FITTED_MIN
    - SPIGOT_LENGTH_MAX
    - (FLANGE_THICK + _BAND[FLANGE_THICK_PLACES]),
    HUB_LENGTH_FITTED_MAX
    - SPIGOT_LENGTH_MIN
    - (FLANGE_THICK - _BAND[FLANGE_THICK_PLACES]),
)  # 7.16 .. 8.14
# (least, greatest) station of the hole centre behind the hub front face.
OIL_HOLE_STATION_RANGE = (
    HUB_BODY_LENGTH_RANGE[0] / 2.0 - OIL_HOLE_CENTRING_TOL,
    HUB_BODY_LENGTH_RANGE[1] / 2.0 + OIL_HOLE_CENTRING_TOL,
)
OIL_HOLE_LIGAMENT_NOMINAL = OIL_HOLE_STATION - OIL_HOLE_DIA / 2.0
OIL_HOLE_LIGAMENT_WORST = OIL_HOLE_STATION_RANGE[0] - _OIL_HOLE_MAX_R
# The same hole's ligament to the sleeve's nose (the sleeve's wall, judged
# against its 2.0 target): the hub front face at the window's nearest plus
# the hole's least station, less its largest radius.
OIL_HOLE_TO_NOSE = SLEEVE.OVERALL_LENGTH - OIL_HOLE_SLEEVE_Z - OIL_HOLE_DIA / 2.0
OIL_HOLE_TO_NOSE_WORST = (
    FIT.HUB_NOSE_WINDOW[0] + OIL_HOLE_STATION_RANGE[0] - _OIL_HOLE_MAX_R
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
        raise AssertionError(f"MHA-PD-017 {_label}: {_wall:.3f} worst < floor {_floor}")

# --- sheet --------------------------------------------------------------------
CORNER_NOTE = f"SPIGOT AND HUB CORNERS AT FLANGE SHARP, R{CORNER_RADIUS_MAX:.1f} MAX."
FLANGE_THICK_NOTE = f"FLANGE {FLANGE_THICK:.3f} SETS {SCREW_NAME} {SCREW_NUMBER} REACH."
BLANK_NOTE = f"SUPPLY {BLANK_LENGTH_MIN:.2f} MIN OVERALL, SPIGOT END TO HUB FRONT."
FACING_NOTE = "THE HUB FRONT FACE IS FACED TO FIT AT ASSEMBLY."
DRAWING_NOTES = "\n".join((CORNER_NOTE, FLANGE_THICK_NOTE, BLANK_NOTE, FACING_NOTE))
# The overall's requirement; the sheet adds the step that sets it.
HUB_LENGTH_CALLOUT = (
    f"SET AT ASSEMBLY {HUB_LENGTH_FITTED_MIN:.2f}-{HUB_LENGTH_FITTED_MAX:.2f}"
    "\nFACED TO FIT"
)
# The spigot's native h6 limits print with the dimension; the callout names
# the mate and the clearance the pair gives, in three lines under the
# spigot diameter beside the flange's: the mate's name and number share the
# last line, BORE) closing it.
SPIGOT_CALLOUT_BELOW = "\n".join(
    (
        "SPIGOT (DIA",
        f"CLR {DISC.SPIGOT_DIAMETRAL_CLEARANCE[0]:.3f}-"
        f"{DISC.SPIGOT_DIAMETRAL_CLEARANCE[1]:.3f} IN",
        f"{DISC_NAME} {DISC_NUMBER} BORE)",
    )
)

# Callouts the sheet hangs on the native dimensions.  The holes are drilled
# (the title block's DRILLED HOLES row governs their sizes); the three screw
# holes are one patterned feature, equally spaced on the printed circle.  The
# oil hole is drilled with the hub seated on the sleeve, through both and
# centred on the hub body (R9-60): the crank pinion's pin-hole wording
# (dt_crank_pinion_spec.pin_hole_note).
SCREW_HOLE_CALLOUT_ABOVE = f"{SCREW_COUNT}X"
SCREW_HOLE_CALLOUT_BELOW = "DRILL THRU FLANGE, EQ SP"
OIL_HOLE_CALLOUT_BELOW = "\n".join(
    (
        "CENTRED ON HUB BODY",
        "MATCH DRILL AT ASSY THRU HUB WALL AND",
        f"{SLEEVE_NAME} {SLEEVE_NUMBER} WITH HUB SEATED",
    )
)

# Marked model dimensions and the places the model authors on them (policy
# rule 2).  Edge view: the turned profile's three diameters, the spigot's and
# flange's lengths from the flange's rear face, the overall, and the oil
# hole's size (rule 7); face view: the bore and its flat, which only show
# there, and the screw holes on their bolt circle.  The overall is faced to
# fit, so it prints as a reference.
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
    "OilHoleProfile": {"OilHoleDia"},
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
    "OilHoleProfile": {"OilHoleDia": OIL_HOLE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {f: set(n) for f, n in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked MHA-PD-017 dimension needs its printed places")
REFERENCE_DIMENSIONS = frozenset({"HubLength"})
