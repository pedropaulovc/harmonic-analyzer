"""Native MHA-DT-00 cylinder-bank fit-up dimensions, shared by build and print.

Two hidden Right-plane construction legs follow the actual bearing faces:
gear 0 cam face to gear 19 north face, then gear 19 to the north strap.
Separate sketches let the full-bank view and enlarged spring view each show
only the leg it dimensions. The model also owns their native below-callout
text: writing it through an imported display dimension can dirty the source.
"""

from __future__ import annotations

import math

import cylinder_bank_layout as bank
from cone_line import Y_DRIVE

STACK_FEATURE = "CylinderBankStackReference"
SPRING_FEATURE = "CylinderBankSpringReference"
STACK_DIMENSION = "CylinderBankStackLength"
SPRING_DIMENSION = "CylinderBankSpringSet"

# (feature, dimension, south face z, north face z), in machine millimetres.
LEGS = (
    (STACK_FEATURE, STACK_DIMENSION, bank.G0_CAM_FACE_Z, bank.G19_BACK_FACE_Z),
    (SPRING_FEATURE, SPRING_DIMENSION, *bank.BANK_SPRING_Z),
)
AXIS_Y = Y_DRIVE
DRAWING_DIMENSIONS = {feature: {name} for feature, name, _south, _north in LEGS}
# The package prints decimal inch (#290).  Both settings carry a ±0.10 fit-up
# band, floored to ±.003 (±.004 would admit 0.0016 past the bank layout's
# budget).  The nominals stay the model's (the stack is the gears' sum, the
# gap a metric gauge blade), so they print at four places with the band as
# ±.0030 (6.0000, .0374): the stack is on the inch grid since the #1038
# re-pitch, but the spring gap at three places would round its printed limits
# off the native ones (Codjiflo, #2194; drawing-guidelines rule 3).
BAND_PLACES = 3
PLACES = 4
DRAWING_PRECISION = {feature: {name: PLACES} for feature, name, _south, _north in LEGS}


def _inward(band_mm: float) -> float:
    """``band_mm`` floored onto the ``BAND_PLACES``-place inch grid, in mm."""
    return math.floor(band_mm / 25.4 * 10**BAND_PLACES + 1e-9) / 10**BAND_PLACES * 25.4


DIMENSION_BANDS = {
    STACK_DIMENSION: (
        _inward(bank.STACK_L20_ACCEPT_BAND[0]), -_inward(-bank.STACK_L20_ACCEPT_BAND[1])
    ),
    SPRING_DIMENSION: (
        _inward(bank.BANK_SPRING_SET_BAND), -_inward(bank.BANK_SPRING_SET_BAND)
    ),
}
TOLERANCE_PRECISION = PLACES
DIMENSION_CALLOUTS = {
    STACK_DIMENSION: "CLOSED GEAR STACK",
    SPRING_DIMENSION: "GEAR 19 TO NORTH PEDESTAL / SET WITH BLADE",
}

# The printed limits (nominal at PLACES, ± band) are the native limits to
# within the display rounding, and inside the bank layout's budget.
for _feature, _name, _south, _north in LEGS:
    _nominal = _north - _south
    _budget = (
        (bank.STACK_L20_ACCEPT_BAND[1], bank.STACK_L20_ACCEPT_BAND[0])
        if _name == STACK_DIMENSION
        else (-bank.BANK_SPRING_SET_BAND, bank.BANK_SPRING_SET_BAND)
    )
    _printed = round(_nominal / 25.4, PLACES) * 25.4
    _upper, _lower = DIMENSION_BANDS[_name]
    if abs(_printed - _nominal) > 0.5 * 25.4 / 10**PLACES + 1e-9:
        raise AssertionError(f"{_name}: the printed nominal leaves the native one")
    if not (
        _nominal + _budget[0] - 1e-9 <= _printed + _lower
        and _printed + _upper <= _nominal + _budget[1] + 1e-9
    ):
        raise AssertionError(f"{_name}: the printed limits leave the bank budget {_budget}")

if abs(LEGS[0][3] - LEGS[0][2] - bank.STACK_L20) > bank.PITCH_LOCKSTEP_TOLERANCE:
    raise AssertionError("the bank setting leg is not the closed stack length")
if abs(LEGS[1][3] - LEGS[1][2] - bank.BANK_SPRING_SET) > 1e-9:
    raise AssertionError("the spring setting leg is not the north bearing-face gap")
