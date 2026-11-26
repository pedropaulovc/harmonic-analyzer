r"""Pure-data interface geometry for the crank arm, hub, pins and shaft nose.

The outboard photograph supplies only unitless proportions.  Scaling its
3.14:2.60:1.65:0.59 arm/hub/shaft/key-pin ratios to the authoritative 3/8-in
shaft gives 18.13:15.01:9.525:3.405 mm, which left a 0.5-mm hub wall between
the seam pin and the bore.  User ruling U29 (2026-09-23) enlarges the outboard
set about the fixed shaft instead: hub and seam pin 1.3x (Ø.76 seat, under
the photograph's 19.5 mm; 5/32-in dowel stock) and the arm unmachined
1 x 5/16-in cold-finished flat bar.  The arm-to-hub width ratio is therefore a
named deviation from the photograph (``ARM_TO_HUB_RATIO`` vs
``PHOTO_ARM_TO_HUB_RATIO``).

Issue #290: the arm and hub print decimal inch.  Lengths stay physical
millimetres, each printed nominal the exact decimal of its inch value.

Local axial station zero is the common outboard plane: the through hub and
crank arm are flush there, the shaft cylinder terminates there, and only the
shaft's spherical dome projects outboard.  Positive station runs inboard.
"""

from __future__ import annotations

import math
from fractions import Fraction

import _config
import _sprocket_seat_geometry as seat_geometry
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import (
    drilled_oversize_mm,
    drilled_undersize_mm,
    edge_break_chamfer_mm,
    printed_band_mm,
)
from dt_crank_pin_spec import BIG_END_DIA as SERVICE_PIN_BIG_END_DIA

# The matched arm/hub set prints in the hub's unit; dt_crank_arm_spec asserts
# the arm agrees.
UNIT = drawing_unit("parts/dt-crank-hub", _config.parts("dt-crank-hub"))
GENERAL_2PL_TOL_MM = printed_band_mm(2, unit=UNIT)
EDGE_BREAK_MAX_MM = edge_break_chamfer_mm(unit=UNIT)


MM_PER_IN = 25.4
SHAFT_DIA = 0.375 * MM_PER_IN

# Unitless outboard-photograph proportions and the U29 enlargement.
PHOTO_ARM, PHOTO_HUB, PHOTO_SHAFT, PHOTO_PIN = 3.14, 2.60, 1.65, 0.59
PHOTO_MM_PER_UNIT = SHAFT_DIA / PHOTO_SHAFT
OUTBOARD_SCALE = 1.3

# The arm is 1 x 5/16-in cold-finished flat bar with its width left as rolled.
# On cold-finished flats the width sets the mill tolerance, and a 1-in bar is
# held to 0.004 in (OnlineMetals cold-roll steel tolerances, "over 0.75 to 1.5
# incl., +/-0.004"; Speedy Metals 1018, "-0.004"; both 2026-09-25) -- far
# inside the .X band.  The minus side is what the U29 cheek reads.
ARM_WIDTH = 1.0 * MM_PER_IN
ARM_STOCK_MILL_MINUS_IN = Fraction(4, 1000)
ARM_WIDTH_STOCK_MINUS = float(ARM_STOCK_MILL_MINUS_IN) * MM_PER_IN
# The bar's as-supplied thickness, which the tapped MHA-DT-32 pivot engages
# (dt_crank_handle_pivot_screw_spec) and the arm's stock note names
# (dt_crank_arm_spec).  It lives here, below both, because the screw's worst-case
# engagement is taken in this stock: a stock change re-runs that engagement's
# 1.5D check at import.
ARM_STOCK_THICKNESS_IN = Fraction(5, 16)
ARM_STOCK_THICKNESS = float(ARM_STOCK_THICKNESS_IN) * MM_PER_IN
# The arm prints its thickness as a reference to that stock (dt_crank_arm_spec),
# so the thinnest arm a shop can hand over is the mill's.  On cold-finished
# flats the WIDTH sets the tolerance for width and thickness alike, and a
# 1-in-wide bar is held to 0.004 in (OnlineMetals cold-roll steel tolerances,
# "over 0.75 to 1.5 incl., +/-0.004"; Speedy Metals 1018, "-0.004"; both
# 2026-09-25; ARM_STOCK_MILL_MINUS_IN above).  The minus side is what
# engagement stacks read.
ARM_STOCK_THICKNESS_MIN = float(ARM_STOCK_THICKNESS_IN - ARM_STOCK_MILL_MINUS_IN) * MM_PER_IN
ARM_STOCK_THICKNESS_MAX = float(ARM_STOCK_THICKNESS_IN + ARM_STOCK_MILL_MINUS_IN) * MM_PER_IN
ARM_THICKNESS = ARM_STOCK_THICKNESS
# The photograph gives 19.5 at the U29 enlargement.  MHA-DT-06 bores the seat
# first at the title block's .XX band and MHA-DT-31 is turned to suit it, so
# the bore's printed limits are the seat's real limits.  The seat is drawn
# .76, under the photograph: a named deviation, inside the photograph's own
# rounding, that keeps the arm cheek and the seam web over the rule-17 wall.
PHOTO_HUB_SEAT_DIA = round(PHOTO_HUB * PHOTO_MM_PER_UNIT * OUTBOARD_SCALE, 1)
HUB_SEAT_DIA = 19.304  # .76
HUB_SEAT_LENGTH = ARM_THICKNESS
# Seat in the arm (owner ruling 2026-11-24, fit audit question 21; reverses
# B1, Main 2026-09-25, the light press): a bonded slip fit.  The seat is
# turned last to the MHA-DT-06 bore as made, the arm sliding on by hand, and
# the joint is bonded with LOCTITE 638, which holds the hub square and stops
# it turning while the seam is drilled.  .0005-.003 diametral: the arm slides
# on by hand at the tight end, and the loose end's .0015 a side is far inside
# the compound's 0.25 mm gap limit (RETAINING_COMPOUND_MAX_GAP_MM in
# dt_pinion_arbor_geometry; restated, not imported: this module is in every
# assembly's recipe).  The model seats line-to-line; the shoulder land below
# reads the largest seat.
SEAT_SLIP_CLEARANCE = (0.0127, 0.0762)  # diametral (min, max): .0005-.003 in
_LOCTITE_638_MAX_GAP_MM = 0.25
if SEAT_SLIP_CLEARANCE[1] > _LOCTITE_638_MAX_GAP_MM:
    raise AssertionError("the MHA-DT-31 seat's slip gap is past LOCTITE 638's limit")
# CONTRACT-crank MHA-DT-31: the barrel behind the arm (observed Ø≈20, review
# Q4) is turned to its own size, narrower than the 1-in arm, and the hub
# runs from the arm shoulder to a flat rear face clear of the MHA-PD-09
# removable, which it keeps from walking forward (the drive train asserts the
# air against _sprocket_seat_geometry).  Its front face is the shoulder the
# arm is pressed to: R9-38 sized it at .XX so the shoulder keeps its land
# (SHOULDER_LAND_WORST_MIN) over the largest seat the press can turn, after
# both edge breaks.
HUB_BARREL_DIA = 22.352  # .88
# The #25 plates wrapping the crank T12 overhang the removable's front face
# toward the hub, so the rear end is turned down to a relief the plates
# pass over; the barrel's rear shoulder stands ahead of the link.  The drive
# train asserts the radial and axial air from these names (RELIEF_STATION is
# the shoulder's local station; its machine z is the drive train's
# crank-face datum plus it); dt_crank_hub_notes carries the axial stack.
RELIEF_DIA = 16.51  # .65
# Printed from the rear face at the title block's .XX: with the hub length
# below it places the shoulder the chain must clear, so it may come out
# RELIEF_LENGTH_TOL short.
RELIEF_LENGTH_TOL = GENERAL_2PL_TOL_MM
# Stack A, a bought ANSI #25 chain floated frontmost against the relief
# shoulder, has two poses.  Seated, the wheel's rear face is on the shaft's
# seat face.  Floated, the wheel has walked forward off its drive pins onto
# the hub's rear face (dt_crankshaft_spec.drive_pin_front_clearances admits
# that pose): then the wheel's front face and the shoulder both ride the hub
# rear face, the hub and seat stations cancel, and the air is the relief
# plus the wheel's plate less the chain's reach ahead of the wheel's rear
# face.  That pose governs (the seated one has stack B's 0.7 air on top), so
# the relief is the shortest .XX length whose worst floated air, thinnest
# wheel and shortest relief, holds CHAIN_SHOULDER_AIR_MIN: the seated worst
# PR1 accepted before the float was counted (Main, PR1 Codex review 2).
CHAIN_SHOULDER_AIR_MIN = 0.2135
_PLATE_MIN = seat_geometry.PLATE + min(seat_geometry.PLATE_BAND)
_RELIEF_LENGTH_MIN = CHAIN_SHOULDER_AIR_MIN + seat_geometry.CHAIN_REACH_FRONT - _PLATE_MIN
RELIEF_LENGTH = (
    math.ceil(round((_RELIEF_LENGTH_MIN + RELIEF_LENGTH_TOL) / MM_PER_IN * 100, 6))
    / 100
    * MM_PER_IN
)  # .16
# The hub prints its overall length, front face to rear face, at .XX.  The
# fitter sets the front face flush with the crankshaft's dome root
# (CRANK_FACE_Z) before the MHA-DT-09 match-ream, so this length (not the arm's
# stock thickness) places the rear face: the air to the removable and, with
# the relief, the chain's air to the shoulder.  Only its long side is
# functional: at +.004 the worst hub-to-T12 air and the drive-pin tips' stay
# open, which the title block's +.01 would all but close.  Short, it only
# opens those airs, so that side is the title block's (HUB_LENGTH_BAND;
# owner ruling 2026-10-31, machinist review of main 31cea0b73).
HUB_LENGTH = 25.146  # .99
HUB_LENGTH_TOL = 0.1016  # .004
HUB_SHOULDER_TO_REAR = HUB_LENGTH - HUB_SEAT_LENGTH
HUB_BARREL_LENGTH = round(HUB_SHOULDER_TO_REAR - RELIEF_LENGTH, 6)

RELIEF_STATION = round(HUB_LENGTH - RELIEF_LENGTH, 6)
HUB_SHOULDER_STATION = HUB_SEAT_LENGTH


def chain_shoulder_axial_air(
    *,
    relief_length: float,
    seat_face: float,
    seat_face_band: tuple[float, float],
    plate: float = seat_geometry.PLATE,
    plate_band: tuple[float, float] = seat_geometry.PLATE_BAND,
    reach_front: float = seat_geometry.CHAIN_REACH_FRONT,
) -> dict[str, float]:
    """Stack A, chain envelope front to the relief shoulder, in both poses at
    nominal and at the printed worst case; local stations from the dome root
    (+ rearward).  Raises when either worst case falls under
    CHAIN_SHOULDER_AIR_MIN."""
    shoulder = HUB_LENGTH - relief_length
    shoulder_fwd = HUB_LENGTH + HUB_LENGTH_TOL - (relief_length - RELIEF_LENGTH_TOL)
    seat_fwd = seat_face + min(seat_face_band)
    relief_short = relief_length - RELIEF_LENGTH_TOL
    plate_thin = plate + min(plate_band)
    airs = {
        # Wheel on the seat face; worst: seat forward, hub long, relief short.
        "seated": seat_face - reach_front - shoulder,
        "seated_worst": seat_fwd - reach_front - shoulder_fwd,
        # Wheel floated onto the hub rear face; worst: thinnest wheel, relief
        # short (the hub and seat stations cancel).
        "floated": relief_length + plate - reach_front,
        "floated_worst": relief_short + plate_thin - reach_front,
    }
    for pose in ("seated_worst", "floated_worst"):
        if airs[pose] < CHAIN_SHOULDER_AIR_MIN - 1e-9:
            raise AssertionError(
                f"chain / hub relief shoulder air {pose} {airs[pose]:.4f}"
                f" < {CHAIN_SHOULDER_AIR_MIN}"
            )
    return airs


# Named ratio deviation (U29): the stock arm stands 1.309x the hub seat where
# the photograph shows 1.208x; the extra width is what gives the arm cheek
# around the seat a 2-mm wall.
ARM_TO_HUB_RATIO = ARM_WIDTH / HUB_SEAT_DIA
PHOTO_ARM_TO_HUB_RATIO = PHOTO_ARM / PHOTO_HUB

# MHA-DT-09's match-ream is fully behind the 5/16 arm, clear of the arm
# shoulder it must not break into; the barrel carries the 1:48 ream at that
# station, printed from the faced outboard end (the machinist's baseline,
# machinist review of the inch sheet): drawing-guidelines.md rule 17 (walls
# and webs) ligaments below.
SERVICE_PIN_STATION = 13.462  # .53
CRANK_FACE_SHIFT = ARM_THICKNESS

# The bore is the named 3/8 drill's at DRILLED HOLES, .375-.379 (delegated
# ruling 2026-11-25 (Main), precedent: the fit-necessity rule of the
# owner-approved fit policy (drawing-simplicity-policy.md; owner ruling
# 2026-11-24): a bore with no failing check takes the plain drill; no owner
# number changed; owner review #2144 (D27): the .3760 REAM failed rule 4's
# necessity test, since the crank is
# stopped by eye and taper-pinned to MHA-DT-11, so bore shake reaches no
# reading).  MHA-DT-11's stub is made last and turned to the bore's smallest
# measured reading less the shaft-in-bushing class's catalogued .0010-.0023
# in diametral clearance; SHAFT_DIA_BAND is that REF stub's analysis aim on
# its .375 nominal.  The catalogue pair is restated, not read:
# _interference_contracts imports this module into every assembly's recipe,
# and a fit-class read would make them all depend on
# tolerances/shaft_in_bushing.yaml.  test_dt_crank_hub_drawing pins it to
# the catalogue.
SHAFT_DIA_BAND = (0.0, -0.02032)
SHAFT_CLEARANCE_MIN, SHAFT_CLEARANCE_MAX = 0.0254, 0.05842
HUB_BORE_DIA = 0.375 * MM_PER_IN  # 3/8 drill
HUB_BORE_BAND = (drilled_oversize_mm(unit=UNIT), -drilled_undersize_mm(unit=UNIT))

# MHA-DT-VN-59 is an axial seam pin at six o'clock in the outboard view, cut
# from a 5/32 x 1/2 alloy-steel dowel pin (McMaster-Carr 98381A487, Ø.1563
# +.0001/+.0003; 1.3x the photograph's 3.405 is 4.43, and 5/32 is the stock
# size below it).  Its hole is drilled 5/32 into both parts at assembly with
# its axis on the nominal hub-seat seam, parallel to the crankshaft, and the
# pin is bonded in (LOCTITE 638) flush with the outboard face (fit audit
# 2026-11-23, MHA-DT-06_DT-31.seam_pin; the .1562 reamer is retired): the hole
# runs deeper than the cut pin at every printed limit, so the pin always
# seats before it bottoms.
AXIAL_PIN_DIA = 3.96875  # 5/32
AXIAL_PIN_LENGTH = 3.81  # .15, cut length
SEAM_DEPTH = 4.318  # .17
if SEAM_DEPTH - GENERAL_2PL_TOL_MM < AXIAL_PIN_LENGTH + GENERAL_2PL_TOL_MM - 1e-9:
    raise AssertionError("MHA-DT-VN-59 can bottom before it is flush")
if SEAM_DEPTH + GENERAL_2PL_TOL_MM >= ARM_STOCK_THICKNESS_MIN:
    raise AssertionError("the MHA-DT-VN-59 seam breaks through the arm")
AXIAL_PIN_RADIUS_FROM_AXIS = HUB_SEAT_DIA / 2.0

FIDUCIAL_MODEL_DIA = 0.8
FIDUCIAL_MODEL_DEPTH = 0.2
ARM_FIDUCIAL_RADIUS = (ARM_WIDTH + HUB_SEAT_DIA) / 4.0
SHAFT_FIDUCIAL_RADIUS = 2.5

# U27: the two thin walls of the matched arm/hub/pin set -- the hub web between
# the seam pin and the bore, and the arm cheek around the hub seat -- are judged
# at the worst case of the printed bands after both edge breaks.  The seat's
# printed band is MHA-DT-06's .XX bore; MHA-DT-31's seat is turned to it less
# the slip clearance, so at worst it is the bore's minimum less the widest
# slip, and the seam hole is the 5/32 drill at its DRILLED HOLES maximum.
SEAM_HOLE_DIA_MAX = AXIAL_PIN_DIA + drilled_oversize_mm(unit=UNIT)
# The bonded pin's widest gap: the drilled hole at its maximum round the pin
# at its nominal (98381A487 is +.0001/+.0003, never under).
if SEAM_HOLE_DIA_MAX - AXIAL_PIN_DIA > _LOCTITE_638_MAX_GAP_MM:
    raise AssertionError("the seam pin's drilled gap is past LOCTITE 638's limit")
HUB_SEAT_DIA_MIN_GENERAL = HUB_SEAT_DIA - GENERAL_2PL_TOL_MM
HUB_SEAT_DIA_MAX_GENERAL = HUB_SEAT_DIA + GENERAL_2PL_TOL_MM
HUB_BORE_DIA_MAX = HUB_BORE_DIA + HUB_BORE_BAND[0]
# The printed overall, (upper, lower): functional on its long side only, the
# title block's .XX on the other (see HUB_LENGTH_TOL).
HUB_LENGTH_BAND = (HUB_LENGTH_TOL, -GENERAL_2PL_TOL_MM)
# drawing-guidelines.md rule 17 (walls and webs) (U27): MHA-DT-09 ream ligaments at the worst case of the printed
# bands.  The ream never exceeds the pin's big end, which stands proud of the
# hub.  The ream is placed from the front face by the .XX station; ahead of it
# the arm shoulder, which sits wherever the arm puts it: the seat length is a
# fit-up reference turned to suit the arm (end flush), so the thickest 5/16
# stock the mill ships places it.  Behind it the relief shoulder, which the
# print places from the front face through the .XX overall and the .XX relief
# back from the rear face.
SERVICE_PIN_REAM_RADIUS_MAX = SERVICE_PIN_BIG_END_DIA / 2.0
SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM = (
    (SERVICE_PIN_STATION - GENERAL_2PL_TOL_MM)
    - ARM_STOCK_THICKNESS_MAX
    - SERVICE_PIN_REAM_RADIUS_MAX
)
SERVICE_PIN_REAR_LIGAMENT_WORST_MM = (
    (HUB_LENGTH + HUB_LENGTH_BAND[1])
    - (RELIEF_LENGTH + RELIEF_LENGTH_TOL)
    - (SERVICE_PIN_STATION + GENERAL_2PL_TOL_MM)
    - SERVICE_PIN_REAM_RADIUS_MAX
)
# The relief is a clearance diameter at the title block's .XX band (R9-37):
# the largest it can come out is what the #25 plates must clear, the
# smallest is the relief's wall over the bore.
RELIEF_DIA_MAX = RELIEF_DIA + GENERAL_2PL_TOL_MM
# The hub rides the shaft in its clearance bore, pinned wherever the
# match-ream found it, so its relief can stand this far off the shaft axis:
# the stub turned to the bore's smallest reading (as small as the drill's
# .375) less the widest clearance, inside a drilled hole whose largest
# diameter may reach .379 (a drilled hole is not round).
HUB_SHAFT_FLOAT = (
    HUB_BORE_DIA_MAX - (HUB_BORE_DIA + HUB_BORE_BAND[1] - SHAFT_CLEARANCE_MAX)
) / 2.0  # 0.080
# The barrel is printed at the title block's .XX: its smallest is what the
# arm shoulder and the MHA-DT-09 ream's wall read.
HUB_BARREL_DIA_MIN = HUB_BARREL_DIA - GENERAL_2PL_TOL_MM
# The barrel wall standing beside the big end of the ream, across the axis.
SERVICE_PIN_BARREL_WALL_WORST_MM = (
    HUB_BARREL_DIA_MIN / 2.0 - SERVICE_PIN_REAM_RADIUS_MAX
)


def wall_after_edge_break(outer_dia: float, inner_dia: float) -> float:
    """Return the finished radial wall between two diameters after edge breaks."""
    return (outer_dia - inner_dia) / 2.0 - 2.0 * EDGE_BREAK_MAX_MM


SEAM_WEB_WORST_MM = wall_after_edge_break(
    HUB_SEAT_DIA_MIN_GENERAL - SEAT_SLIP_CLEARANCE[1] - SEAM_HOLE_DIA_MAX, HUB_BORE_DIA_MAX
)
ARM_CHEEK_WORST_MM = wall_after_edge_break(
    ARM_WIDTH - ARM_WIDTH_STOCK_MINUS, HUB_SEAT_DIA_MAX_GENERAL
)
# The relief's wall over the bore: Ø16.50 at its .XX lower limit against the
# bore's upper limit, both edges broken.
RELIEF_WALL_WORST_MM = wall_after_edge_break(
    RELIEF_DIA - GENERAL_2PL_TOL_MM, HUB_BORE_DIA_MAX
)
for _wall, _label in (
    (SEAM_WEB_WORST_MM, "MHA-DT-31 seam-to-bore web"),
    (ARM_CHEEK_WORST_MM, "MHA-DT-06 cheek around the hub seat"),
    (SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM, "MHA-DT-09 ream to the MHA-DT-31 shoulder"),
    (
        SERVICE_PIN_REAR_LIGAMENT_WORST_MM,
        "MHA-DT-09 ream to the MHA-DT-31 relief shoulder",
    ),
    (SERVICE_PIN_BARREL_WALL_WORST_MM, "MHA-DT-31 barrel beside the MHA-DT-09 ream"),
    (RELIEF_WALL_WORST_MM, "MHA-DT-31 rear relief over the bore"),
):
    if _wall < WALL_TARGET_MM:
        raise AssertionError(f"{_label} is only {_wall:.3f} mm at worst case")
# The arm is bonded to the barrel's front face (FACES FLUSH), which takes the
# arm's push on assembly and then holds the arm square while the compound
# cures.  The face it bears on runs from the arm bore's broken edge to the
# barrel's broken corner, and the seat is turned to the bore it meets, so at
# worst the largest bore (.XX) less the tightest slip stands inside the
# smallest barrel.  The land must stay one title-block edge break wide: a
# flat a fitter can see, not a knife edge left between two chamfers.
SHOULDER_LAND_WORST_MIN = EDGE_BREAK_MAX_MM
HUB_SEAT_DIA_MAX_MATCHED = HUB_SEAT_DIA_MAX_GENERAL - SEAT_SLIP_CLEARANCE[0]


def shoulder_land(barrel_dia_min: float, seat_dia_max: float) -> float:
    """Radial land the arm bears on, the barrel's smallest against the largest
    matched seat, both edges broken.  Raises below SHOULDER_LAND_WORST_MIN."""
    land = wall_after_edge_break(barrel_dia_min, seat_dia_max)
    if land < SHOULDER_LAND_WORST_MIN - 1e-9:
        raise AssertionError(
            f"MHA-DT-31 shoulder land {land:.3f} < {SHOULDER_LAND_WORST_MIN}"
        )
    return land


HUB_SHOULDER_LAND_WORST_MM = shoulder_land(
    HUB_BARREL_DIA_MIN, HUB_SEAT_DIA_MAX_MATCHED
)  # 0.255
if not HUB_BORE_DIA < RELIEF_DIA < HUB_BARREL_DIA:
    raise AssertionError("MHA-DT-31 relief is not a step between the bore and barrel")
if SERVICE_PIN_STATION >= RELIEF_STATION:
    raise AssertionError("MHA-DT-09 station lies on the rear relief")
# The stub is turned to the measured bore less at least SHAFT_CLEARANCE_MIN,
# so it always withdraws; its REF model at .375 may sit line-on-line with the
# 3/8 drill's nominal (coincident faces, not an interference) but never over.
if SHAFT_CLEARANCE_MIN <= 0.0 or SHAFT_DIA + SHAFT_DIA_BAND[0] > HUB_BORE_DIA + HUB_BORE_BAND[1]:
    raise AssertionError("shaft dome cannot withdraw through the hub bore")
if HUB_SHOULDER_STATION >= SERVICE_PIN_STATION:
    raise AssertionError("MHA-DT-09 is not behind the crank arm")
if SERVICE_PIN_STATION >= HUB_LENGTH:
    raise AssertionError("MHA-DT-09 station lies beyond the through hub")
