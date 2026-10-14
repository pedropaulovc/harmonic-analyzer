r"""Pure-data contract for the rocker arm hub filing stud (MHA-CH-006-TL-05).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's hub filing hold (prechips S3F) the bench vise grips the stud's
tail; the lapped body locates in the arm's reamed pivot bore (datum A) and
carries the two filing buttons (MHA-CH-006-TL-04). The lower button seats on
the integral head, the arm's hub sits between the buttons, and a bought
1/4-20 coupling nut (McMaster 90264A435) on the thread clamps the stack. Turned in one chucking from 4140 at
HRC 32 and left unhardened (shop-additions section 1): nothing files on it.

Frame: the stud axis is model +X with the head's seat face at X0, the body
and thread toward +X and the head and vise tail toward -X. Every axial size
prints as one baseline from the faced tip (model X = THREAD_END). In the inventory fixture frame (stud axis Z, upper
hub face Z0) the seat sits at Z = -(HUB_LENGTH + button thickness), so
inventory Z = model X - (HUB_LENGTH + button thickness).
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_filing_button_spec as button
from _inch import inch
from _printed_tolerance import printed_deviations
from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl

# Lapped body: slips into the smallest pivot bore the arm's reamed band
# allows and into the smallest lapped button bore.
BODY_DIA = 6.49
BODY_BAND = (0.0, -0.005)  # (upper, lower) deviations: 6.485-6.490
BODY_PLACES = 3
BODY_CLEARANCE_MIN = 0.005  # a lapped slip fit; 0.010 at the tightest pairing
_BODY_MAX = BODY_DIA + BODY_BAND[0]
if rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1] - _BODY_MAX < BODY_CLEARANCE_MIN:
    raise AssertionError("filing-stud body does not slip into the smallest pivot bore")
if button.BORE_DIA + button.BORE_BAND[1] - _BODY_MAX < BODY_CLEARANCE_MIN:
    raise AssertionError("filing-stud body does not slip into the smallest button bore")

# The head seat carries the lower button; the head stays inside the button
# face and outside the button bore.
HEAD_DIA = inch(3, 8)
# Collar: two millimetres left at the worst-case stations. 5/32: 1/8 leaves
# under two at the .X and .XX bands.
HEAD_LENGTH = inch(5, 32)
if not (
    button.BORE_DIA + button.BORE_BAND[0]
    < HEAD_DIA
    < round(button.OD + printed_deviations(button.OD, button.OD_PLACES)[0], 12)
):
    raise AssertionError("filing-stud head does not land on the button face")

# Axial sizes print as one baseline from the faced tip (the thread end): the
# thread start, the head seat, the head's back face and the vise end. The
# model keeps the seat at X0 (the stack datum). The body carries the lower
# button and the whole hub at every printed button thickness and hub length,
# and stops short of the stack top so the nut bears on the upper button
# (which then centres on the thread crests: its float is far inside the
# hub's printed O.D. band). The stack-bearing stations print to two places;
# the body length is their difference, checked at worst case below.
STATION_PLACES = 2  # thread start and head seat: the stack reads from them
STOCK_PLACES = 1  # head back face and vise end: stock only
BODY_LENGTH = inch(9, 16)  # model: seat face to the thread start (derived on print)
# Seat face to the faced tip; printed tip to seat. 1-1/4: 1-3/16 leaves the
# nut under 1.5D of full thread on the thickest 3/16 button stack.
THREAD_END = inch(5, 4)
THREAD_START = THREAD_END - BODY_LENGTH  # printed: tip to the thread start
TAIL_END = inch(7, 4)  # seat face to the vise end: head plus a 1-19/32 vise tail
HEAD_BACK = THREAD_END + HEAD_LENGTH  # printed: tip to the head's back face
OVERALL_LENGTH = TAIL_END + THREAD_END  # printed: tip to the vise end
TAIL_DIA = inch(5, 16)  # stout in the vise; clear of the thread and body sizes
# HA fastener policy (memory/fastener-policy-us-customary.md): the
# inventory's M6 maps to 1/4-20 UNC; an external thread is class 2A.
THREAD = "1/4-20 UNC-2A"
THREAD_MODEL_DIA = inch(1, 4)

_BUTTON_MIN, _BUTTON_MAX = [
    round(button.THICKNESS + deviation, 12)
    for deviation in printed_deviations(button.THICKNESS, button.THICKNESS_PLACES)
]
_STACK_MIN = 2.0 * _BUTTON_MIN + rocker.HUB_LENGTH
_STACK_MAX = 2.0 * _BUTTON_MAX + rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
_HUB_TOP_MAX = _BUTTON_MAX + rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
_SEAT_MIN, _SEAT_MAX = [round(THREAD_END + deviation, 12) for deviation in printed_deviations(THREAD_END, STATION_PLACES)]
_START_MIN, _START_MAX = [round(THREAD_START + deviation, 12) for deviation in printed_deviations(THREAD_START, STATION_PLACES)]
_BODY_LEN_MIN, _BODY_LEN_MAX = _SEAT_MIN - _START_MAX, _SEAT_MAX - _START_MIN
if _BODY_LEN_MAX >= _STACK_MIN:
    raise AssertionError("filing-stud body can stand proud of the button stack")
if _BODY_LEN_MIN <= _HUB_TOP_MAX:
    raise AssertionError("filing-stud body does not reach through the hub")
# Bought clamping nut: McMaster 90264A435, zinc-plated steel hex coupling
# nut, 1/4"-20, 7/8 in long, 3/8 in across flats, fully threaded (verified
# live 2026-10-08). Its chamfers are not stated; each end is taken as one
# pitch of incomplete thread. drawing-guidelines.md rule 18 (thread engagement): at the worst case of the printed
# stack and stations the INSTALLED full-thread engagement in the nut is at
# least one and a half diameters. Engagement starts above the stack top
# past the nut's entry chamfer, or past the die's runout (one and a half
# pitches beyond the thread start), whichever is higher; it ends one pitch
# short of the faced tip (the tip chamfer) or at the nut's far chamfer.
NUT_SKU = "90264A435"
NUT_LENGTH = inch(7, 8)
_THREAD_PITCH = inch(1, 20)
_NUT_CHAMFER = _THREAD_PITCH
_DIE_RUNOUT = 1.5 * _THREAD_PITCH
_TIP_CHAMFER = _THREAD_PITCH


def installed_engagement(stack: float, seat_to_tip: float, body: float) -> float:
    """Full-thread engagement in the coupling nut seated on the stack top."""
    start = max(stack + _NUT_CHAMFER, body + _DIE_RUNOUT)
    end = min(seat_to_tip - _TIP_CHAMFER, stack + NUT_LENGTH - _NUT_CHAMFER)
    return end - start


ENGAGEMENT_MIN = min(
    installed_engagement(stack, seat_to_tip, body)
    for stack in (_STACK_MIN, _STACK_MAX)
    for seat_to_tip in (_SEAT_MIN, _SEAT_MAX)
    for body in (_BODY_LEN_MIN, _BODY_LEN_MAX)
)
if ENGAGEMENT_MIN < 1.5 * THREAD_MODEL_DIA:
    raise AssertionError("filing-stud nut engagement is under one and a half diameters")
# A worst-case collar of two millimetres between the seat and back face.
if round(HEAD_BACK + printed_deviations(HEAD_BACK, STOCK_PLACES)[0], 12) - _SEAT_MAX < 2.0:
    raise AssertionError(
        "filing-stud collar is thinner than two millimetres at worst case"
    )

_STATIONS = {
    "ThreadStartStation": STATION_PLACES,
    "SeatStation": STATION_PLACES,
    "HeadBackStation": STOCK_PLACES,
    "TailEndStation": STOCK_PLACES,
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "TailProfile": {"TailDia"},
    "BodyProfile": {"BodyDia"},
    "ThreadProfile": {"ThreadDia"},
    "StationReference": set(_STATIONS),
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {"HeadDia": 1},
    "TailProfile": {"TailDia": 1},
    "BodyProfile": {"BodyDia": BODY_PLACES},
    "ThreadProfile": {"ThreadDia": 2},
    "StationReference": dict(_STATIONS),
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked filing-stud dimension needs authored places")
# The locating diameter prints as a reference; the fit callout on it
# governs. BODY_BAND is that fit's design intent for the stack checks only;
# features.toml carries the printed nominal and the callout text.
# drawing-guidelines.md rule 4 (tighten only for function, and name the mate) and drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the matched fit sits on the locating diameter's
# callout, naming each mate by Number with its acceptance (above, below).
BODY_FIT_CALLOUT = (
    "SLIDES IN MHA-CH-006 ROCKER ARM PIVOT BORE AND",
    "MHA-CH-006-TL-04 BUTTONS BY HAND WITHOUT SHAKE",
)
BODY_FIT_NOTE = " ".join(part for part in BODY_FIT_CALLOUT if part)
REFERENCE_DIMENSIONS = frozenset({"BodyDia"})
REFERENCE_CALLOUTS = {"BodyDia": BODY_FIT_CALLOUT}
# The thread size prints as its designation, not as a plain diameter.
DIMENSION_TEXT = {"ThreadDia": THREAD}

# The sliding journal is a required machined surface at the project grade;
# the fit callout governs its size.
SURFACE_FINISHES = (
    SurfaceFinishControl("locating_body", MACHINED_UM, CylinderFace(BODY_DIA)),
)
# The two-place tip stations are functional: the journal between them must
# carry the whole hub yet stop below the stack top so the nut clamps.
DRAWING_NOTES = (
    "SEAT AND THREAD START HOLD THE BUTTON STACK: NUT MUST CLAMP THE UPPER BUTTON.\n"
    "VISE TAIL IS HELD ONLY."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

