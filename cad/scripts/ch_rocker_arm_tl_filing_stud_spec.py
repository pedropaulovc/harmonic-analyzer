r"""Pure-data contract for the rocker arm hub filing stud (MHA-CH-006-TL-05).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's hub filing hold (traveler setup S6, inventory fixture
``hub-filing-buttons``) the bench vise grips the stud's tail; the lapped
body locates in the arm's reamed pivot bore (datum A) and carries both
filing buttons (MHA-CH-006-TL-04). The lower button seats on the integral
head, the arm's hub sits between the buttons, the upper button rides the
body, and a bought #10-24 coupling nut (McMaster 90264A425) on the thread
clamps the stack. Turned in one chucking from 4140 at HRC 32 and left
unhardened (shop stock: "headed stud (ruling 1)"): nothing files on it.

Frame: the stud axis is model +X with the head's seat face at X0, the body
and thread toward +X and the head and vise tail toward -X. Every axial size
prints as one baseline from the faced tip (model X = THREAD_END). In the inventory fixture frame (stud axis Z, upper
hub face Z0) the seat sits at Z = -(HUB_LENGTH + button thickness), so
inventory Z = model X - (HUB_LENGTH + button thickness).
"""

from __future__ import annotations

import math

import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_filing_button_spec as button
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
# rim (a file laid on the rim clears it) and outside the button bore, at the
# worst case of both printed bands.
HEAD_DIA = 9.0
HEAD_PLACES = 1
# The record's head: five millimetres of bare tail above the vise jaws.
HEAD_LENGTH = 5.0
_BUTTON_OD_MIN = round(
    button.OD + printed_deviations(button.OD, button.OD_PLACES)[0], 12
)
if not (
    button.BORE_DIA + button.BORE_BAND[0]
    < round(HEAD_DIA + printed_deviations(HEAD_DIA, HEAD_PLACES)[0], 12)
    and round(HEAD_DIA + printed_deviations(HEAD_DIA, HEAD_PLACES)[1], 12)
    < _BUTTON_OD_MIN
):
    raise AssertionError(
        "filing-stud head does not land on the button face inside its rim"
    )

# Axial sizes print as one baseline from the faced tip (the thread end): the
# thread start, the head seat, the head's back face and the vise end. The
# model keeps the seat at X0 (the stack datum). The body carries the lower
# button, the whole hub and the upper button at every printed button
# thickness and hub length, and stops short of the stack top so the nut
# bears on the upper button. Both buttons therefore centre on the lapped
# body, never on the thread crests (the hub coaxiality budget below). The
# stack-bearing stations print to three places; the body length is their
# difference, checked at worst case below.
STATION_PLACES = 3  # thread start and head seat: the stack reads from them
STOCK_PLACES = 1  # head back face and vise end: stock only
BODY_LENGTH = 13.9  # model: seat face to the thread start (derived on print)
THREAD_END = 25.0  # seat face to the faced tip; printed tip to seat
THREAD_START = round(THREAD_END - BODY_LENGTH, 6)  # printed: tip to the thread start
TAIL_END = 35.0  # seat face to the vise end: head plus a thirty-millimetre vise tail
HEAD_BACK = THREAD_END + HEAD_LENGTH  # printed: tip to the head's back face
OVERALL_LENGTH = TAIL_END + THREAD_END  # printed: tip to the vise end
# The record's tail: the body size, so the bench vise jaws posed for the kit
# (inventory bench-vise-4in) close on it; stock only.
TAIL_DIA = 6.49
TAIL_PLACES = 2
# HA fastener policy (memory/fastener-policy-us-customary.md): the
# inventory's M5 maps to #10-24 UNC; an external thread is class 2A.
THREAD = "#10-24 UNC-2A"
THREAD_MODEL_DIA = 4.826

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
# The upper button bore rides the lapped body over at least half its
# thickness at the worst case, so it centres on the body, not the thread.
UPPER_BUTTON_SUPPORT_MIN = round(_BODY_LEN_MIN - _HUB_TOP_MAX, 12)
if UPPER_BUTTON_SUPPORT_MIN < _BUTTON_MIN / 2.0:
    raise AssertionError("filing-stud body does not carry the upper button")
# Bought clamping nut: McMaster 90264A425, zinc-plated steel hex coupling
# nut, #10-24, 3/4 in long, 5/16 in across flats, fully threaded (verified
# live 2026-10-14). The inventory's M5 DIN 934 nut is 0.8D tall; the coupling
# nut meets the engagement rule and its corners stay inside the button rim.
# Its chamfers are not stated; each end is taken as one
# pitch of incomplete thread. drawing-guidelines.md rule 18 (thread engagement): at the worst case of the printed
# stack and stations the INSTALLED full-thread engagement in the nut is at
# least one and a half diameters. Engagement starts above the stack top
# past the nut's entry chamfer, or past the die's runout (one and a half
# pitches beyond the thread start), whichever is higher; it ends one pitch
# short of the faced tip (the tip chamfer) or at the nut's far chamfer.
NUT_SKU = "90264A425"
NUT_LENGTH = 3.0 / 4.0 * 25.4
NUT_ACROSS_FLATS = 5.0 / 16.0 * 25.4
NUT_CORNER_DIA = NUT_ACROSS_FLATS / math.cos(math.radians(30.0))
if NUT_CORNER_DIA >= _BUTTON_OD_MIN:
    raise AssertionError("filing-stud nut corners stand outside the button rim")
_THREAD_PITCH = 25.4 / 24.0
_NUT_CHAMFER = _THREAD_PITCH
_DIE_RUNOUT = 1.5 * _THREAD_PITCH
_TIP_CHAMFER = _THREAD_PITCH
# The nut seats on the stack before its first full thread meets the die's
# runout: at the shortest stack its full thread starts at or above the stud's.
if _STACK_MIN + _NUT_CHAMFER < _BODY_LEN_MAX + _DIE_RUNOUT:
    raise AssertionError("filing-stud nut meets the die runout before it seats")


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

# Hub coaxiality budget (the manual-arc stack): a filed hub follows its
# button rim, whose centre may sit off the pivot-bore axis by half the
# bore-on-body clearance, plus half the button-bore-on-body clearance, plus
# half the rim's runout to its own bore. Both buttons ride the body, so the
# worst-case diametral shift is inside the arm's printed hub coaxiality and
# the filed O.D. inside its printed band.
_BODY_MIN = BODY_DIA + BODY_BAND[1]
HUB_CENTRE_SHIFT_MAX = (
    (rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0] - _BODY_MIN) / 2.0
    + (button.BORE_DIA + button.BORE_BAND[0] - _BODY_MIN) / 2.0
    + button.OD_RUNOUT_TIR / 2.0
)
if 2.0 * HUB_CENTRE_SHIFT_MAX > rocker.HUB_COAXIALITY_DIA:
    raise AssertionError("filing kit cannot hold the hub coaxiality to the pivot bore")
_BUTTON_OD_MAX = round(
    button.OD + printed_deviations(button.OD, button.OD_PLACES)[1], 12
)
FILED_HUB_DIA = (
    _BUTTON_OD_MIN - 2.0 * HUB_CENTRE_SHIFT_MAX,
    _BUTTON_OD_MAX + 2.0 * HUB_CENTRE_SHIFT_MAX,
)
_HUB_MIN, _HUB_MAX = [
    round(rocker.HUB_DIA + deviation, 12)
    for deviation in printed_deviations(rocker.HUB_DIA, 2)
]
if not (_HUB_MIN <= FILED_HUB_DIA[0] and FILED_HUB_DIA[1] <= _HUB_MAX):
    raise AssertionError("filing kit files the hub outside its printed O.D. band")

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
    "HeadProfile": {"HeadDia": HEAD_PLACES},
    "TailProfile": {"TailDia": TAIL_PLACES},
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
    SurfaceFinishControl(
        "locating_body",
        MACHINED_UM,
        CylinderFace(BODY_DIA, contains_x_mm=BODY_LENGTH / 2.0),
    ),
)
# The three-place tip stations are functional: the journal between them must
# carry the whole hub and the upper button yet stop below the stack top so
# the nut clamps.
DRAWING_NOTES = (
    "SEAT AND THREAD START HOLD THE BUTTON STACK: UPPER BUTTON RIDES THE BODY, NUT CLAMPS IT.\n"
    "VISE TAIL IS HELD ONLY."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

# prechips primitives for the whole kit (inventory ``hub-filing-buttons``
# binds ``cad = "ch_rocker_arm_tl_filing_stud"``: one CAD stem per inventory
# table, and the stud owns the stack). Fixture frame: stud axis Z, Z0 on the
# upper hub face (P02), lower hub face at -HUB_LENGTH; each button's and the
# stud's size come from their TL specs, the nut from its catalogue page.
_SEAT_Z = round(-(rocker.HUB_LENGTH + button.THICKNESS), 6)
_O1_BUTTON = "O1 drill rod, hardened and tempered; bore, faces and O.D. lapped"
_STUD_ROD = "4140 rod, HRC 32, left unhardened"
PRECHIPS_SOLIDS: list[dict] = [
    {
        "name": "upper button",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": button.OD,
        "length_mm": button.THICKNESS,
        "label": "hub buttons",
        "locates": "upper hub face (P02) and the file's stop for the upper hub OD",
        "note": _O1_BUTTON,
    },
    {
        "name": "upper button bore",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, -0.5],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": button.BORE_DIA,
        "length_mm": button.THICKNESS + 1.0,
        "void": True,
        "cuts": ["upper button"],
    },
    {
        "name": "lower button",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, -rocker.HUB_LENGTH],
        "axis": [0.0, 0.0, -1.0],
        "dia_mm": button.OD,
        "length_mm": button.THICKNESS,
        "label": "hub buttons",
        "locates": "lower hub face (P01) and the file's stop for the lower hub OD",
        "note": _O1_BUTTON,
    },
    {
        "name": "lower button bore",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, round(-rocker.HUB_LENGTH + 0.5, 6)],
        "axis": [0.0, 0.0, -1.0],
        "dia_mm": button.BORE_DIA,
        "length_mm": button.THICKNESS + 1.0,
        "void": True,
        "cuts": ["lower button"],
    },
    {
        "name": "stud head",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, _SEAT_Z],
        "axis": [0.0, 0.0, -1.0],
        "dia_mm": HEAD_DIA,
        "length_mm": HEAD_LENGTH,
        "note": _STUD_ROD,
    },
    {
        "name": "stud pin",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, _SEAT_Z],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": BODY_DIA,
        "length_mm": BODY_LENGTH,
        "locates": "pivot bore (datum A)",
        "bears": "bore",
        "note": _STUD_ROD,
    },
    {
        "name": "stud thread",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, round(_SEAT_Z + BODY_LENGTH, 6)],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": THREAD_MODEL_DIA,
        "length_mm": THREAD_START,
        "fastener": THREAD,
        "note": _STUD_ROD,
    },
    {
        "name": "stud tail",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, round(_SEAT_Z - HEAD_LENGTH, 6)],
        "axis": [0.0, 0.0, -1.0],
        "dia_mm": TAIL_DIA,
        "length_mm": TAIL_END - HEAD_LENGTH,
        "note": _STUD_ROD,
    },
    {
        "name": "nut",
        "shape": "cylinder",
        "supply": "bought",
        "fastener": f"#10-24 hex coupling nut, 5/16 in A/F (McMaster {NUT_SKU})",
        "at_mm": [0.0, 0.0, button.THICKNESS],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": round(NUT_CORNER_DIA, 3),
        "length_mm": round(NUT_LENGTH, 3),
    },
]
