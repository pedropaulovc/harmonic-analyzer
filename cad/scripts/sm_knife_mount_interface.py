r"""Knife-mount top-seat footprint and its frame/dowel fit contract.

The top-frame casting consumes these dimensions and printed bands, not the
mating lever profile, bore rocking calculation, or tap-tool/crown-web proof.
The mount's build, drawing and assembly use this same authoritative interface.
"""

from __future__ import annotations

import _config
import sm_vn_knife_mount_dowel_spec as DOWEL

# Overall seat: 25.4 across keeps the -X dowel's far-side web at 2.0 round
# the 15.264 span (sm_knife_mount_spec.PIN_HOLE_FAR_SIDE_WEB; 25.319 least).
BLK_HALF_X = 12.7
SUPPORT_Z_THICK = 14.0  # axial depth straddling the trunnion mid
BLOCK_SIZE_PLACES = 1
BLOCK_SIZE_TOL = float(str(_config.title_block("linear_1pl")["display"]).lstrip("\u00b1"))

# The #10-24 tap's position to the top seat and the dowel pattern (A|B): the
# bolt axis the crossbar's #10 clearance hole must float round
# (``build_sm_summing_assembly``'s knife-hanger stack). Its 0.075 zone radius
# is one term of HANGER_SCREW_MISMATCH (hypot(0.316, 0.264) = 0.412) inside
# the hole's 0.6095 radial float with the drill drift's 0.194 over the
# printed grip's thickest 37.01, 0.0039 spare.
# A screw through a clearance hole needs no tighter zone than that float
# admits (drawing-guidelines.md rule 5), and Ø0.15 is the largest two-place
# zone it admits: the float closes at Ø0.1556; Ø0.16 leaves -0.0031 and
# Ø0.25 -0.067. Plain face dimensions instead, even at .XXX (+/-0.13 each
# way, not 0.075), give hypot(0.371, 0.319) = 0.489 and -0.074: the frame is
# functional.
# The printed strings are authoritative: the drawing and numerical stacks
# must read the same limits, without rounding a separate numerical nominal.
MOUNTING_GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "knife-hanger tap position": "0.15",
    "dowel hole pattern position": "0.13",
}
STUD_TAP_POSITION_TOL = float(
    MOUNTING_GEOMETRIC_TOLERANCES_MM["knife-hanger tap position"]
)
PIN_HOLE_POSITION_TOL = float(
    MOUNTING_GEOMETRIC_TOLERANCES_MM["dowel hole pattern position"]
)
# MHA-SM-VN-53 pair, centred on the hanger tap along local X at mid-depth.
# The pair's BASIC span is positioned to the top seat at Ø0.13.
PIN_HOLE_X = DOWEL.HANGER_OFFSET  # 7.632
PIN_HOLE_XS = (-PIN_HOLE_X, PIN_HOLE_X)
PIN_HOLE_COUNT = len(PIN_HOLE_XS)
if PIN_HOLE_COUNT != DOWEL.PER_MOUNT:
    raise AssertionError("the knife mount reams one hole per MHA-SM-VN-53 dowel")
PIN_HOLE_SPAN = DOWEL.SPAN  # 15.264 BASIC
PIN_HOLE_SPAN_PLACES = DOWEL.SPAN_PLACES
PIN_HOLE_SPAN_TOL = PIN_HOLE_POSITION_TOL  # 0.13: the span's worst variation
PIN_HOLE_HALF_SPAN_TOL = PIN_HOLE_SPAN_TOL / 2.0  # 0.065
PIN_HOLE_X_TOL = PIN_HOLE_HALF_SPAN_TOL + STUD_TAP_POSITION_TOL / 2.0  # 0.14
if PIN_HOLE_SPAN_TOL != DOWEL.SPAN_TOL or PIN_HOLE_SPAN_PLACES != 3:
    raise AssertionError(
        "the dowel pattern's zone must be the span variation the stacks take"
    )

# The +X dowel's station from the +X side face (.XX, chaining the BASIC
# span to the -X dowel), and the -X dowel's row from the front face (.X).
PIN_HOLE_SIDE_DISTANCE = BLK_HALF_X - PIN_HOLE_X  # 5.068, prints 5.07
PIN_HOLE_SIDE_PLACES = 2
PIN_HOLE_SIDE_TOL = float(str(_config.title_block("linear_2pl")["display"]).lstrip("\u00b1"))
HOLE_ROW_FACE_DISTANCE = SUPPORT_Z_THICK / 2.0  # 7.0
HOLE_ROW_FACE_PLACES = 1
HOLE_ROW_FACE_TOL = BLOCK_SIZE_TOL  # 0.8, the same .X title-block row
