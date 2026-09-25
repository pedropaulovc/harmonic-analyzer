r"""Pure-data interface geometry for the crank arm, hub, pins and shaft nose.

The outboard photograph supplies only unitless proportions.  Scaling its
3.14:2.60:1.65:0.59 arm/hub/shaft/key-pin ratios to the authoritative 3/8-in
shaft gives 18.13:15.01:9.525:3.405 mm, which left a 0.5-mm hub wall between
the seam pin and the bore.  User ruling U29 (2026-09-23) enlarges the outboard
set about the fixed shaft instead: hub and seam pin 1.3x (Ø19.5 seat, Ø4
dowel stock) and the arm unmachined 1-in cold-finished flat bar (25.4).  The
arm-to-hub width ratio is therefore a named deviation from the photograph
(``ARM_TO_HUB_RATIO`` vs ``PHOTO_ARM_TO_HUB_RATIO``).

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

# The arm is 1 x 5/16-in cold-finished flat bar with its width left as rolled;
# the mill holds that width to 0.003 in, minus only, far inside the .X band.
ARM_WIDTH = 1.0 * MM_PER_IN
ARM_WIDTH_STOCK_MINUS = 0.08
ARM_THICKNESS = 8.0
# The bar's as-supplied thickness, which the tapped MHA-139 pivot engages
# (crank_handle_pivot_screw_spec) and the arm's stock note names
# (crank_arm_spec).  It lives here, below both, because the arm prints the
# screw's engagement: a stock change re-runs that engagement's 1D and U33b
# floors at import.
ARM_STOCK_THICKNESS_IN = Fraction(5, 16)
ARM_STOCK_THICKNESS = float(ARM_STOCK_THICKNESS_IN) * MM_PER_IN
HUB_SEAT_DIA = round(PHOTO_HUB * PHOTO_MM_PER_UNIT * OUTBOARD_SCALE, 1)
HUB_BARREL_DIA = ARM_WIDTH
HUB_SEAT_LENGTH = ARM_THICKNESS
HUB_LENGTH = 20.0
HUB_SHOULDER_STATION = HUB_SEAT_LENGTH
# Named ratio deviation (U29): the stock arm stands 1.303x the hub seat where
# the photograph shows 1.208x; the extra width is what gives the arm cheek
# around the seat a 2-mm wall.
ARM_TO_HUB_RATIO = ARM_WIDTH / HUB_SEAT_DIA
PHOTO_ARM_TO_HUB_RATIO = PHOTO_ARM / PHOTO_HUB

# MHA-024's match-ream is fully behind the 8-mm arm, located from the arm
# shoulder it must not break into.  The hub rear stays at station 20 (BDT pins
# the 5.5-mm T12 air gap), so the 12-mm barrel -- printed from the shoulder --
# holds the 1:48 ream with a centred station: policy rule 12 ligaments below.
HUB_BARREL_LENGTH = HUB_LENGTH - HUB_SEAT_LENGTH
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
# at the worst case of the printed bands after both edge breaks.
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
# bands -- the .XX station from the shoulder and the .X barrel length.  The
# ream never exceeds the pin's big end, which stands proud of the hub.
SERVICE_PIN_REAM_RADIUS_MAX = SERVICE_PIN_BIG_END_DIA / 2.0
SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM = (
    SERVICE_PIN_FROM_SHOULDER - SERVICE_PIN_REAM_RADIUS_MAX - GENERAL_2PL_TOL_MM
)
SERVICE_PIN_REAR_LIGAMENT_WORST_MM = (
    HUB_BARREL_LENGTH
    - SERVICE_PIN_FROM_SHOULDER
    - SERVICE_PIN_REAM_RADIUS_MAX
    - GENERAL_1PL_TOL_MM
    - GENERAL_2PL_TOL_MM
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
for _wall, _label in (
    (SEAM_WEB_WORST_MM, "MHA-137 seam-to-bore web"),
    (ARM_CHEEK_WORST_MM, "MHA-020 cheek around the hub seat"),
    (SERVICE_PIN_SHOULDER_LIGAMENT_WORST_MM, "MHA-024 ream to the MHA-137 shoulder"),
    (SERVICE_PIN_REAR_LIGAMENT_WORST_MM, "MHA-024 ream to the MHA-137 rear face"),
):
    if _wall < WALL_TARGET_MM:
        raise AssertionError(f"{_label} is only {_wall:.3f} mm at worst case")
if SHAFT_DIA + SHAFT_DIA_BAND[0] >= HUB_BORE_DIA + HUB_BORE_BAND[1]:
    raise AssertionError("shaft dome cannot withdraw through the hub bore")
if HUB_SHOULDER_STATION >= SERVICE_PIN_STATION:
    raise AssertionError("MHA-024 is not behind the crank arm")
if SERVICE_PIN_STATION >= HUB_LENGTH:
    raise AssertionError("MHA-024 station lies beyond the through hub")
