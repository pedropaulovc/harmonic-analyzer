r"""Pure-data interface geometry for the crank arm, hub, pins and shaft nose.

The outboard photograph supplies only unitless proportions.  Scaling its
3.14:2.60:1.65:0.59 arm/hub/shaft/key-pin ratios to the authoritative 3/8-in
shaft gives 18.13:15.01:9.525:3.405 mm; the manufacturable nominal set below
rounds that to 18.1:15.0:9.525:3.4 without treating the photograph ratios as
independent millimetre dimensions.

Local axial station zero is the common outboard plane: the through hub and
crank arm are flush there, the shaft cylinder terminates there, and only the
shaft's spherical dome projects outboard.  Positive station runs inboard.
"""

from __future__ import annotations

from _config import fit


MM_PER_IN = 25.4
SHAFT_DIA = 0.375 * MM_PER_IN
ARM_WIDTH = 18.1
ARM_THICKNESS = 8.0
HUB_SEAT_DIA = 15.0
HUB_BARREL_DIA = ARM_WIDTH
HUB_SEAT_LENGTH = ARM_THICKNESS
HUB_LENGTH = 20.0
HUB_SHOULDER_STATION = HUB_SEAT_LENGTH

# MHA-024 remains at its established world station after the common crank face
# moves 8 mm outboard.  At station 12 its #14/#9 match-ream is fully behind the
# 8-mm arm and still leaves a 5.5-mm air gap from the hub rear to the T12 face.
SERVICE_PIN_STATION = 12.0
CRANK_FACE_SHIFT = ARM_THICKNESS

# Shared shaft-in-bushing fit class, re-expressed as a bore nominal/band against
# the already released ground-shaft h band (0/-0.02).  The resulting worst-case
# diametral clearance is exactly the catalogued 0.025..0.075 mm.
SHAFT_DIA_BAND = (0.00, -0.02)
SHAFT_CLEARANCE_MIN, SHAFT_CLEARANCE_MAX = tuple(
    float(value) for value in fit("shaft_in_bushing", "diametral_clearance_mm")
)
HUB_BORE_DIA = SHAFT_DIA + SHAFT_CLEARANCE_MIN
HUB_BORE_BAND = (
    SHAFT_CLEARANCE_MAX - (HUB_BORE_DIA - (SHAFT_DIA + SHAFT_DIA_BAND[1])),
    0.0,
)

# MHA-138 is an axial seam pin at six o'clock in the outboard view.  It is
# match-drilled/reamed through both parts with its axis on the nominal hub-seat
# seam, parallel to the crankshaft.
AXIAL_PIN_DIA = 3.4
AXIAL_PIN_LENGTH = ARM_THICKNESS / 2.0
AXIAL_PIN_RADIUS_FROM_AXIS = HUB_SEAT_DIA / 2.0

# The dome is integral to MHA-026 and cannot exceed the cylindrical shaft
# diameter: the crank assembly must withdraw through the MHA-137 through bore.
SHAFT_DOME_HEIGHT = 2.0
FIDUCIAL_MODEL_DIA = 0.8
FIDUCIAL_MODEL_DEPTH = 0.2
ARM_FIDUCIAL_RADIUS = (ARM_WIDTH + HUB_SEAT_DIA) / 4.0
SHAFT_FIDUCIAL_RADIUS = 2.5

# Binding separation checks include all fit-band extremes.  The assembled seam
# hole's innermost radius must leave a real wall outside the largest hub bore;
# the largest shaft/dome must pass the smallest finished bore.
_PIN_TO_BORE_WALL_MIN = (
    AXIAL_PIN_RADIUS_FROM_AXIS
    - AXIAL_PIN_DIA / 2.0
    - (HUB_BORE_DIA + HUB_BORE_BAND[0]) / 2.0
)
if _PIN_TO_BORE_WALL_MIN < 0.75:
    raise AssertionError(
        f"MHA-138 leaves only {_PIN_TO_BORE_WALL_MIN:.3f} mm to the hub bore"
    )
if SHAFT_DIA + SHAFT_DIA_BAND[0] >= HUB_BORE_DIA + HUB_BORE_BAND[1]:
    raise AssertionError("shaft dome cannot withdraw through the hub bore")
if HUB_SHOULDER_STATION >= SERVICE_PIN_STATION:
    raise AssertionError("MHA-024 is not behind the crank arm")
if SERVICE_PIN_STATION >= HUB_LENGTH:
    raise AssertionError("MHA-024 station lies beyond the through hub")
