"""Native MHA-DT-00 cylinder-bank fit-up dimensions, shared by build and print.

Two hidden Right-plane construction legs follow the actual bearing faces:
gear 0 cam face to gear 19 north face, then gear 19 to the north strap.
Separate sketches let the full-bank view and enlarged spring view each show
only the leg it dimensions. No note text belongs in the assembly recipe.
"""

from __future__ import annotations

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
DRAWING_PRECISION = {feature: {name: 2} for feature, name, _south, _north in LEGS}
DIMENSION_BANDS = {
    STACK_DIMENSION: bank.STACK_L20_ACCEPT_BAND,
    SPRING_DIMENSION: (bank.BANK_SPRING_SET_BAND, -bank.BANK_SPRING_SET_BAND),
}
TOLERANCE_PRECISION = 2

if abs(LEGS[0][3] - LEGS[0][2] - bank.STACK_L20) > bank.PITCH_LOCKSTEP_TOLERANCE:
    raise AssertionError("the bank setting leg is not the closed stack length")
if abs(LEGS[1][3] - LEGS[1][2] - bank.BANK_SPRING_SET) > 1e-9:
    raise AssertionError("the spring setting leg is not the north bearing-face gap")
