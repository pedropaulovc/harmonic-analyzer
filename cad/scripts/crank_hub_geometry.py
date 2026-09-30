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

from fractions import Fraction

import _config
from crank_pin_spec import BIG_END_DIA as SERVICE_PIN_BIG_END_DIA


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
# The bar's as-supplied thickness, which the tapped MHA-139 pivot engages
# (crank_handle_pivot_screw_spec) and the arm's stock note names
# (crank_arm_spec).  It lives here, below both, because the screw's worst-case
# engagement is taken in this stock: a stock change re-runs that engagement's
# 1.5D check at import.
ARM_STOCK_THICKNESS_IN = Fraction(5, 16)
ARM_STOCK_THICKNESS = float(ARM_STOCK_THICKNESS_IN) * MM_PER_IN
# The arm prints its thickness as a reference to that stock (crank_arm_spec),
# so the thinnest arm a shop can hand over is the mill's.  On cold-finished
# flats the WIDTH sets the tolerance for width and thickness alike, and a
# 1-in-wide bar is held to 0.004 in (OnlineMetals cold-roll steel tolerances,
# "over 0.75 to 1.5 incl., +/-0.004"; Speedy Metals 1018, "-0.004"; both
# 2026-09-25; ARM_STOCK_MILL_MINUS_IN above).  The minus side is what
# engagement stacks read.
ARM_STOCK_THICKNESS_MIN = float(ARM_STOCK_THICKNESS_IN - ARM_STOCK_MILL_MINUS_IN) * MM_PER_IN
# The photograph gives 19.5 at the U29 enlargement.  MHA-020 bores the seat
# first at the title block's .X band and MHA-137 is turned to suit it, so the
# bore's printed limits are the seat's real limits.  At the sourced 0.004-in
# width tolerance, a 19.5 bore at +0.8 leaves the arm cheek 1.999 -- under
# U29's 2.0 -- so the seat is drawn 0.1 under the photograph: a named
# deviation, inside the photograph's own rounding.
PHOTO_HUB_SEAT_DIA = round(PHOTO_HUB * PHOTO_MM_PER_UNIT * OUTBOARD_SCALE, 1)
HUB_SEAT_DIA = round(PHOTO_HUB_SEAT_DIA - 0.1, 1)
HUB_SEAT_LENGTH = ARM_THICKNESS
# CONTRACT-crank MHA-137: the barrel behind the arm is Ø20.6 (observed Ø≈20,
# review Q4) -- turned to its own size, narrower than the 1-in arm -- and the
# hub runs 17.2 from the arm shoulder to a flat rear face 0.7 clear of the
# MHA-081 removable, which it keeps from walking forward (the drive train
# asserts the air against transgear_removable_spec).  It followed the seat
# face 1.8 forward (user ruling 2026-09-30): 19 -> 17.2.
HUB_BARREL_DIA = 20.6
HUB_SHOULDER_TO_REAR = 17.2
# The #25 plates wrapping the crank T12 overhang the removable's front face
# toward the hub, so the rear end is turned down to a Ø16.5 relief the plates
# pass over; the barrel's rear shoulder stands ahead of the link.  3.6 long,
# so a bought ANSI #25 chain (not just the CAD link) clears the shoulder at
# the printed worst case (crank_hub_notes carries the axial stack); the drive
# train asserts the radial and axial air from these names (RELIEF_STATION is
# the shoulder's local station; its machine z is the drive train's
# crank-face datum plus it).
RELIEF_DIA = 16.5
# Printed from the rear face at .XX with a functional ±0.05: with the hub
# length below it places the shoulder the chain must clear.
RELIEF_LENGTH = 3.6
RELIEF_LENGTH_TOL = 0.05
HUB_BARREL_LENGTH = round(HUB_SHOULDER_TO_REAR - RELIEF_LENGTH, 6)
HUB_LENGTH = HUB_SEAT_LENGTH + HUB_SHOULDER_TO_REAR
# The hub prints its overall length, front face to rear face, at .XX with a
# functional ±0.05.  The fitter sets the front face flush with the crankshaft's
# dome root (CRANK_FACE_Z) before the MHA-024 match-ream, so this band (not the arm's stock
# thickness) places the rear face: the 0.7 air to the removable and, with
# the relief, the chain's air to the shoulder.
HUB_LENGTH_TOL = 0.05
RELIEF_STATION = round(HUB_LENGTH - RELIEF_LENGTH, 6)
HUB_SHOULDER_STATION = HUB_SEAT_LENGTH
# Named ratio deviation (U29): the stock arm stands 1.309x the hub seat where
# the photograph shows 1.208x; the extra width is what gives the arm cheek
# around the seat a 2-mm wall.
ARM_TO_HUB_RATIO = ARM_WIDTH / HUB_SEAT_DIA
PHOTO_ARM_TO_HUB_RATIO = PHOTO_ARM / PHOTO_HUB

# MHA-024's match-ream is fully behind the 8-mm arm, located from the arm
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
# tolerances.yaml.  test_crank_hub_drawing pins it to the catalogue.
SHAFT_DIA_BAND = (0.00, -0.02)
SHAFT_CLEARANCE_MIN, SHAFT_CLEARANCE_MAX = 0.025, 0.075
HUB_BORE_DIA = SHAFT_DIA + SHAFT_CLEARANCE_MIN
HUB_BORE_BAND = (
    SHAFT_CLEARANCE_MAX - (HUB_BORE_DIA - (SHAFT_DIA + SHAFT_DIA_BAND[1])),
    0.0,
)

# MHA-138 is an axial seam pin at six o'clock in the outboard view, cut from
# Ø4 m6 dowel stock (1.3x the photograph's 3.405 is 4.43; 4 mm is the stock
# size below it).  It is match-drilled/reamed through both parts with its axis
# on the nominal hub-seat seam, parallel to the crankshaft.
AXIAL_PIN_DIA = 4.0
AXIAL_PIN_DIA_STOCK_MAX = 4.012
AXIAL_PIN_LENGTH = ARM_THICKNESS / 2.0
AXIAL_PIN_RADIUS_FROM_AXIS = HUB_SEAT_DIA / 2.0

# The dome is integral to MHA-026 and cannot exceed the cylindrical shaft
# diameter: the crank assembly must withdraw through the MHA-137 through bore.
SHAFT_DOME_HEIGHT = 2.0
FIDUCIAL_MODEL_DIA = 0.8
FIDUCIAL_MODEL_DEPTH = 0.2
ARM_FIDUCIAL_RADIUS = (ARM_WIDTH + HUB_SEAT_DIA) / 4.0
SHAFT_FIDUCIAL_RADIUS = 2.5

# U27: the two thin walls of the matched arm/hub/pin set -- the hub web between
# the seam pin and the bore, and the arm cheek around the hub seat -- are judged
# at the worst case of the printed bands after both edge breaks.  The seat's
# printed band is MHA-020's .X bore; MHA-137's seat is turned to suit it for a
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
# Policy rule 12 (U27): MHA-024 ream ligaments at the worst case of the printed
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
# The relief is a clearance diameter at the title block's .X band: the
# largest it can come out is what the #25 plates must clear, the smallest is
# the relief's wall over the bore.
RELIEF_DIA_MAX = RELIEF_DIA + GENERAL_1PL_TOL_MM
# The barrel wall standing beside the big end of the ream, across the axis.
SERVICE_PIN_BARREL_WALL_WORST_MM = (
    HUB_BARREL_DIA - GENERAL_1PL_TOL_MM
) / 2.0 - SERVICE_PIN_REAM_RADIUS_MAX


def wall_after_edge_break(outer_dia: float, inner_dia: float) -> float:
    """Return the finished radial wall between two diameters after edge breaks."""
    return (outer_dia - inner_dia) / 2.0 - 2.0 * EDGE_BREAK_MAX_MM


SEAM_WEB_WORST_MM = wall_after_edge_break(
    HUB_SEAT_DIA_MIN_GENERAL - AXIAL_PIN_DIA_STOCK_MAX, HUB_BORE_DIA_MAX
)
ARM_CHEEK_WORST_MM = wall_after_edge_break(
    ARM_WIDTH - ARM_WIDTH_STOCK_MINUS, HUB_SEAT_DIA_MAX_GENERAL
)
# The relief's wall over the bore: Ø16.5 at its .X lower limit against the
# bore's upper limit, both edges broken.
RELIEF_WALL_WORST_MM = wall_after_edge_break(
    RELIEF_DIA - GENERAL_1PL_TOL_MM, HUB_BORE_DIA_MAX
)
for _wall, _label in (
    (SEAM_WEB_WORST_MM, "MHA-137 seam-to-bore web"),
    (ARM_CHEEK_WORST_MM, "MHA-020 cheek around the hub seat"),
    (SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM, "MHA-024 ream to the MHA-137 shoulder"),
    (
        SERVICE_PIN_REAR_LIGAMENT_WORST_MM,
        "MHA-024 ream to the MHA-137 relief shoulder",
    ),
    (SERVICE_PIN_BARREL_WALL_WORST_MM, "MHA-137 barrel beside the MHA-024 ream"),
    (RELIEF_WALL_WORST_MM, "MHA-137 rear relief over the bore"),
):
    if _wall < WALL_TARGET_MM:
        raise AssertionError(f"{_label} is only {_wall:.3f} mm at worst case")
if HUB_BARREL_DIA <= HUB_SEAT_DIA:
    raise AssertionError("MHA-137 barrel leaves no shoulder against the arm")
if not HUB_BORE_DIA < RELIEF_DIA < HUB_BARREL_DIA:
    raise AssertionError("MHA-137 relief is not a step between the bore and barrel")
if SERVICE_PIN_STATION >= RELIEF_STATION:
    raise AssertionError("MHA-024 station lies on the rear relief")
if SHAFT_DIA + SHAFT_DIA_BAND[0] >= HUB_BORE_DIA + HUB_BORE_BAND[1]:
    raise AssertionError("shaft dome cannot withdraw through the hub bore")
if HUB_SHOULDER_STATION >= SERVICE_PIN_STATION:
    raise AssertionError("MHA-024 is not behind the crank arm")
if SERVICE_PIN_STATION >= HUB_LENGTH:
    raise AssertionError("MHA-024 station lies beyond the through hub")
