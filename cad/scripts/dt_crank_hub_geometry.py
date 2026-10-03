r"""Pure-data interface geometry for the crank arm, hub, pins and shaft nose.

The outboard photograph supplies only unitless proportions.  Scaling its
3.14:2.60:1.65:0.59 arm/hub/shaft/key-pin ratios to the authoritative 3/8-in
shaft gives 18.13:15.01:9.525:3.405 mm, which left a 0.5-mm hub wall between
the seam pin and the bore.  User ruling U29 (2026-09-23) enlarges the outboard
set about the fixed shaft instead: hub and seam pin 1.3x (Ø19.4 seat, 0.1
under the photograph's 19.5; Ø4 dowel stock) and the arm unmachined 1-in
cold-finished flat bar (25.4).  The arm-to-hub width ratio is therefore a named
deviation from the photograph (``ARM_TO_HUB_RATIO`` vs
``PHOTO_ARM_TO_HUB_RATIO``).

Local axial station zero is the common outboard plane: the through hub and
crank arm are flush there, the shaft cylinder terminates there, and only the
shaft's spherical dome projects outboard.  Positive station runs inboard.
"""

from __future__ import annotations

import math
from fractions import Fraction

import _config
import pd_transgear_removable_spec as _removable
from dt_crank_pin_spec import BIG_END_DIA as SERVICE_PIN_BIG_END_DIA


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
ARM_THICKNESS = 8.0
# The bar's as-supplied thickness, which the tapped MHA-DT-032 pivot engages
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
# The photograph gives 19.5 at the U29 enlargement.  MHA-DT-006 bores the seat
# first at the title block's .X band and MHA-DT-031 is turned to suit it, so the
# bore's printed limits are the seat's real limits.  At the sourced 0.004-in
# width tolerance, a 19.5 bore at +0.8 leaves the arm cheek 1.999 -- under
# U29's 2.0 -- so the seat is drawn 0.1 under the photograph: a named
# deviation, inside the photograph's own rounding.
PHOTO_HUB_SEAT_DIA = round(PHOTO_HUB * PHOTO_MM_PER_UNIT * OUTBOARD_SCALE, 1)
HUB_SEAT_DIA = round(PHOTO_HUB_SEAT_DIA - 0.1, 1)
HUB_SEAT_LENGTH = ARM_THICKNESS
# Seat-in-arm press (B1, Main 2026-09-25): the seat is turned to suit the
# MHA-DT-006 bore as measured, for a light press.  A 1018 hub in a 1018 arm,
# 8.0 long and keyed by MHA-VN-029 on the seam, needs the press only to hold the
# hub square and stop it turning while the seam is match-drilled.  The band
# sits inside ISO 286 H7/p6 at 18-30 mm (0.001-0.035 diametral, the
# locational-interference fit); its line-to-line end is raised to 0.010
# because the hub is turned to a measured bore, not drawn from stock.  The
# model seats line-to-line; the shoulder land below reads the largest seat.
SEAT_PRESS_INTERFERENCE = (0.010, 0.030)  # diametral, mm (min, max)
# CONTRACT-crank MHA-DT-031: the barrel behind the arm (observed Ø≈20, review
# Q4) is turned to its own size, narrower than the 1-in arm, and the hub
# runs 17.2 from the arm shoulder to a flat rear face 0.7 clear of the
# MHA-PD-009 removable, which it keeps from walking forward (the drive train
# asserts the air against pd_transgear_removable_spec).  It followed the seat
# face 1.8 forward (user ruling 2026-09-30): 19 -> 17.2.  Its front face is
# the shoulder the arm is pressed to: R9-38 took it Ø20.6 -> Ø22.25 at .XX so
# the shoulder keeps its land (SHOULDER_LAND_WORST_MIN) over the largest
# seat the press can turn, after both edge breaks.
HUB_BARREL_DIA = 22.25
HUB_SHOULDER_TO_REAR = 17.2
# The #25 plates wrapping the crank T12 overhang the removable's front face
# toward the hub, so the rear end is turned down to a Ø16.5 relief the plates
# pass over; the barrel's rear shoulder stands ahead of the link.  The drive
# train asserts the radial and axial air from these names (RELIEF_STATION is
# the shoulder's local station; its machine z is the drive train's
# crank-face datum plus it); dt_crank_hub_notes carries the axial stack.
RELIEF_DIA = 16.5
# Printed from the rear face at .XX with a functional ±0.05: with the hub
# length below it places the shoulder the chain must clear.
RELIEF_LENGTH_TOL = 0.05
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
_PLATE_MIN = _removable.PLATE + min(_removable.PLATE_BAND)
RELIEF_LENGTH = round(
    math.ceil(
        round(
            (CHAIN_SHOULDER_AIR_MIN + _removable.CHAIN_REACH_FRONT - _PLATE_MIN) * 100,
            6,
        )
    )
    / 100
    + RELIEF_LENGTH_TOL,
    2,
)  # 3.85
HUB_BARREL_LENGTH = round(HUB_SHOULDER_TO_REAR - RELIEF_LENGTH, 6)
HUB_LENGTH = HUB_SEAT_LENGTH + HUB_SHOULDER_TO_REAR
# The hub prints its overall length, front face to rear face, at .XX with a
# functional ±0.10.  The fitter sets the front face flush with the crankshaft's
# dome root (CRANK_FACE_Z) before the MHA-DT-009 match-ream, so this band (not the arm's stock
# thickness) places the rear face: the 0.7 air to the removable and, with
# the relief, the chain's air to the shoulder.  At ±0.10 the worst hub-to-T12
# air is 0.10 and the drive-pin tips' 0.146; the title block's ±0.51 would
# close both (machinist review of 19e33c6c2 loosened it from ±0.05).
HUB_LENGTH_TOL = 0.10
RELIEF_STATION = round(HUB_LENGTH - RELIEF_LENGTH, 6)
HUB_SHOULDER_STATION = HUB_SEAT_LENGTH


def chain_shoulder_axial_air(
    *,
    relief_length: float,
    seat_face: float,
    seat_face_band: tuple[float, float],
    plate: float = _removable.PLATE,
    plate_band: tuple[float, float] = _removable.PLATE_BAND,
    reach_front: float = _removable.CHAIN_REACH_FRONT,
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

# MHA-DT-009's match-ream is fully behind the 8-mm arm, located from the arm
# shoulder it must not break into; the barrel -- printed from the shoulder --
# carries the 1:48 ream at that station: policy rule 12 ligaments below.
SERVICE_PIN_FROM_SHOULDER = 5.6
SERVICE_PIN_STATION = HUB_SEAT_LENGTH + SERVICE_PIN_FROM_SHOULDER
CRANK_FACE_SHIFT = ARM_THICKNESS

# Shared shaft-in-bushing fit class, re-expressed as a bore nominal/band against
# the already released ground-shaft h band (0/-0.02).  The resulting worst-case
# diametral clearance is exactly the catalogued 0.025..0.075 mm.  The catalogue
# pair is restated, not read: _interference_contracts imports this module into
# every assembly's recipe, and a fit-class read would make them all depend on
# tolerances.yaml.  test_dt_crank_hub_drawing pins it to the catalogue.
SHAFT_DIA_BAND = (0.00, -0.02)
SHAFT_CLEARANCE_MIN, SHAFT_CLEARANCE_MAX = 0.025, 0.075
HUB_BORE_DIA = SHAFT_DIA + SHAFT_CLEARANCE_MIN
HUB_BORE_BAND = (
    SHAFT_CLEARANCE_MAX - (HUB_BORE_DIA - (SHAFT_DIA + SHAFT_DIA_BAND[1])),
    0.0,
)

# MHA-VN-029 is an axial seam pin at six o'clock in the outboard view, cut from
# Ø4 m6 dowel stock (1.3x the photograph's 3.405 is 4.43; 4 mm is the stock
# size below it).  It is match-drilled/reamed through both parts with its axis
# on the nominal hub-seat seam, parallel to the crankshaft.
AXIAL_PIN_DIA = 4.0
AXIAL_PIN_DIA_STOCK_MAX = 4.012
AXIAL_PIN_LENGTH = ARM_THICKNESS / 2.0
AXIAL_PIN_RADIUS_FROM_AXIS = HUB_SEAT_DIA / 2.0

# The dome is integral to MHA-DT-011 and cannot exceed the cylindrical shaft
# diameter: the crank assembly must withdraw through the MHA-DT-031 through bore.
SHAFT_DOME_HEIGHT = 2.0
FIDUCIAL_MODEL_DIA = 0.8
FIDUCIAL_MODEL_DEPTH = 0.2
ARM_FIDUCIAL_RADIUS = (ARM_WIDTH + HUB_SEAT_DIA) / 4.0
SHAFT_FIDUCIAL_RADIUS = 2.5

# U27: the two thin walls of the matched arm/hub/pin set -- the hub web between
# the seam pin and the bore, and the arm cheek around the hub seat -- are judged
# at the worst case of the printed bands after both edge breaks.  The seat's
# printed band is MHA-DT-006's .X bore; MHA-DT-031's seat is turned to suit it for a
# press, so it is never under the bore's minimum.
WALL_TARGET_MM = 2.0
GENERAL_1PL_TOL_MM = round(
    float(_config.title_block("linear_1pl")["value_in"]) * MM_PER_IN, 1
)
EDGE_BREAK_MAX_MM = float(_config.title_block("edge_break")["chamfer_max_mm"])
HUB_SEAT_DIA_MIN_GENERAL = HUB_SEAT_DIA - GENERAL_1PL_TOL_MM
HUB_SEAT_DIA_MAX_GENERAL = HUB_SEAT_DIA + GENERAL_1PL_TOL_MM
HUB_BORE_DIA_MAX = HUB_BORE_DIA + HUB_BORE_BAND[0]
GENERAL_2PL_TOL_MM = round(
    float(_config.title_block("linear_2pl")["value_in"]) * MM_PER_IN, 2
)
# Policy rule 12 (U27): MHA-DT-009 ream ligaments at the worst case of the printed
# bands.  The ream never exceeds the pin's big end, which stands proud of the
# hub.  Ahead of it the arm shoulder: the .XX station printed from it.  Behind
# it the relief shoulder, which the print places from the front face through
# the .XX overall and the .XX relief back from the rear face, while the ream
# is placed through the .X seat length and the .XX station.
SERVICE_PIN_REAM_RADIUS_MAX = SERVICE_PIN_BIG_END_DIA / 2.0
SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM = (
    SERVICE_PIN_FROM_SHOULDER - SERVICE_PIN_REAM_RADIUS_MAX - GENERAL_2PL_TOL_MM
)
SERVICE_PIN_REAR_LIGAMENT_WORST_MM = (
    (HUB_LENGTH - HUB_LENGTH_TOL)
    - (RELIEF_LENGTH + RELIEF_LENGTH_TOL)
    - (HUB_SEAT_LENGTH + GENERAL_1PL_TOL_MM)
    - (SERVICE_PIN_FROM_SHOULDER + GENERAL_2PL_TOL_MM)
    - SERVICE_PIN_REAM_RADIUS_MAX
)
# The relief is a clearance diameter at the title block's .XX band (R9-37:
# a real #25 plate on the T12 floated on its pins keeps 0.23 off it, 0.08 at
# .X): the largest it can come out is what the #25 plates must clear, the
# smallest is the relief's wall over the bore.
RELIEF_DIA_MAX = RELIEF_DIA + GENERAL_2PL_TOL_MM
# The hub rides the shaft in its clearance bore, pinned wherever the
# match-ream found it, so its relief can stand this far off the shaft axis.
HUB_SHAFT_FLOAT = (HUB_BORE_DIA_MAX - (SHAFT_DIA + SHAFT_DIA_BAND[1])) / 2.0  # 0.0375
# The barrel is printed at the title block's .XX: its smallest is what the
# arm shoulder and the MHA-DT-009 ream's wall read.
HUB_BARREL_DIA_MIN = HUB_BARREL_DIA - GENERAL_2PL_TOL_MM
# The barrel wall standing beside the big end of the ream, across the axis.
SERVICE_PIN_BARREL_WALL_WORST_MM = (
    HUB_BARREL_DIA_MIN / 2.0 - SERVICE_PIN_REAM_RADIUS_MAX
)


def wall_after_edge_break(outer_dia: float, inner_dia: float) -> float:
    """Return the finished radial wall between two diameters after edge breaks."""
    return (outer_dia - inner_dia) / 2.0 - 2.0 * EDGE_BREAK_MAX_MM


SEAM_WEB_WORST_MM = wall_after_edge_break(
    HUB_SEAT_DIA_MIN_GENERAL - AXIAL_PIN_DIA_STOCK_MAX, HUB_BORE_DIA_MAX
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
    (SEAM_WEB_WORST_MM, "MHA-DT-031 seam-to-bore web"),
    (ARM_CHEEK_WORST_MM, "MHA-DT-006 cheek around the hub seat"),
    (SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM, "MHA-DT-009 ream to the MHA-DT-031 shoulder"),
    (
        SERVICE_PIN_REAR_LIGAMENT_WORST_MM,
        "MHA-DT-009 ream to the MHA-DT-031 relief shoulder",
    ),
    (SERVICE_PIN_BARREL_WALL_WORST_MM, "MHA-DT-031 barrel beside the MHA-DT-009 ream"),
    (RELIEF_WALL_WORST_MM, "MHA-DT-031 rear relief over the bore"),
):
    if _wall < WALL_TARGET_MM:
        raise AssertionError(f"{_label} is only {_wall:.3f} mm at worst case")
# The arm is pressed to the barrel's front face (FACES FLUSH), which carries
# the press and then holds the arm square.  The face it bears on runs from
# the arm bore's broken edge to the barrel's broken corner, and the seat is
# turned to the bore it meets, so at worst the largest bore (.X) plus the
# tightest press stands inside the smallest barrel.  The land must stay one
# title-block edge break wide: a flat a fitter can see and gauge the press
# against, not a knife edge left between two chamfers.
SHOULDER_LAND_WORST_MIN = EDGE_BREAK_MAX_MM
HUB_SEAT_DIA_MAX_MATCHED = HUB_SEAT_DIA_MAX_GENERAL + SEAT_PRESS_INTERFERENCE[1]


def shoulder_land(barrel_dia_min: float, seat_dia_max: float) -> float:
    """Radial land the arm bears on, the barrel's smallest against the largest
    matched seat, both edges broken.  Raises below SHOULDER_LAND_WORST_MIN."""
    land = wall_after_edge_break(barrel_dia_min, seat_dia_max)
    if land < SHOULDER_LAND_WORST_MIN - 1e-9:
        raise AssertionError(
            f"MHA-DT-031 shoulder land {land:.3f} < {SHOULDER_LAND_WORST_MIN}"
        )
    return land


HUB_SHOULDER_LAND_WORST_MM = shoulder_land(
    HUB_BARREL_DIA_MIN, HUB_SEAT_DIA_MAX_MATCHED
)  # 0.255
if not HUB_BORE_DIA < RELIEF_DIA < HUB_BARREL_DIA:
    raise AssertionError("MHA-DT-031 relief is not a step between the bore and barrel")
if SERVICE_PIN_STATION >= RELIEF_STATION:
    raise AssertionError("MHA-DT-009 station lies on the rear relief")
if SHAFT_DIA + SHAFT_DIA_BAND[0] >= HUB_BORE_DIA + HUB_BORE_BAND[1]:
    raise AssertionError("shaft dome cannot withdraw through the hub bore")
if HUB_SHOULDER_STATION >= SERVICE_PIN_STATION:
    raise AssertionError("MHA-DT-009 is not behind the crank arm")
if SERVICE_PIN_STATION >= HUB_LENGTH:
    raise AssertionError("MHA-DT-009 station lies beyond the through hub")
