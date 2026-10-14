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
# relief end, the body shoulder, the head seat, the head's back face and the
# vise end. The model keeps the seat at X0 (the stack datum). The body
# carries the lower button, the whole hub and the upper button at every
# printed button thickness and hub length, and stops short of the stack top
# so the nut bears on the upper button. Both buttons therefore centre on the
# lapped body, never on the thread crests (the hub coaxiality budget below).
# The stack-bearing stations print to three places; the body length is their
# difference, checked at worst case below.
STATION_PLACES = 3  # body shoulder and head seat: the stack reads from them
STOCK_PLACES = 1  # relief end, head back face and vise end: title block
BODY_LENGTH = 13.9  # model: seat face to the body shoulder (derived on print)
THREAD_END = 26.0  # seat face to the faced tip; printed tip to seat
SHOULDER_STATION = round(THREAD_END - BODY_LENGTH, 6)  # printed: tip to the shoulder
TAIL_END = 35.0  # seat face to the vise end: head plus a thirty-millimetre vise tail
HEAD_BACK = THREAD_END + HEAD_LENGTH  # printed: tip to the head's back face
OVERALL_LENGTH = TAIL_END + THREAD_END  # printed: tip to the vise end
# The tail is only held in the bench vise (traveler S6: 25 in the jaws, 5
# bare below the head); nothing passes over it, so it is plain stock at the
# title-block band, stout in the jaws and clear of the body and head sizes.
TAIL_DIA = 8.0
TAIL_PLACES = 1
# HA fastener policy (memory/fastener-policy-us-customary.md): the
# inventory's M5 maps to #10-24 UNC. The title block states the 2A class, so
# the callout prints the size and series only.
THREAD = "#10-24 UNC-2A"
THREAD_CALLOUT = "#10-24 UNC"
THREAD_MODEL_DIA = 4.826
_THREAD_PITCH = 25.4 / 24.0
# drawing-guidelines.md rule 16 (design for the cutter): a relief groove at
# the body shoulder takes the die's incomplete threads, so the full thread
# starts at the relief end. Its floor sits under the thread's basic minor
# diameter at the .XX band's top, and its width (shoulder station less the
# relief-end station) is at least one pitch at the worst case.
RELIEF_DIA = 2.9
RELIEF_PLACES = 2
RELIEF_END_STATION = 10.0  # printed: tip to the relief end, .X
RELIEF_WIDTH = round(SHOULDER_STATION - RELIEF_END_STATION, 6)  # model: 2.1
_THREAD_MINOR = THREAD_MODEL_DIA - 1.299038 * _THREAD_PITCH
if (
    round(RELIEF_DIA + printed_deviations(RELIEF_DIA, RELIEF_PLACES)[1], 12)
    >= _THREAD_MINOR
):
    raise AssertionError(
        "filing-stud relief floor is not under the thread minor diameter"
    )

_BUTTON_MIN, _BUTTON_MAX = [
    round(button.THICKNESS + deviation, 12)
    for deviation in printed_deviations(button.THICKNESS, button.THICKNESS_PLACES)
]
_STACK_MIN = 2.0 * _BUTTON_MIN + rocker.HUB_LENGTH
_STACK_MAX = 2.0 * _BUTTON_MAX + rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
_HUB_TOP_MAX = _BUTTON_MAX + rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
_SEAT_MIN, _SEAT_MAX = [round(THREAD_END + deviation, 12) for deviation in printed_deviations(THREAD_END, STATION_PLACES)]
_START_MIN, _START_MAX = [round(SHOULDER_STATION + deviation, 12) for deviation in printed_deviations(SHOULDER_STATION, STATION_PLACES)]
_RELIEF_END_MIN, _RELIEF_END_MAX = [
    round(RELIEF_END_STATION + deviation, 12)
    for deviation in printed_deviations(RELIEF_END_STATION, STOCK_PLACES)
]
RELIEF_WIDTH_MIN = round(_START_MIN - _RELIEF_END_MAX, 12)
if RELIEF_WIDTH_MIN < _THREAD_PITCH:
    raise AssertionError("filing-stud thread relief is shorter than one pitch")
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

# Internal corner radii (Main's round-6 ruling: both reviewer families ask
# for a largest acceptable radius, which still states one at every corner).
# Each prints as a MAX on its model dimension (swTolMAX: the print shows the
# model value), so the model carries the worst-case corner. The relief's two
# roots stay inside the relief depth under the thread and do not meet at the
# worst-case relief width; the held-only tail's step root leaves a flat on
# the head's back face; the button seat corner stays under the title block's
# 0.25 edge break on the lower button's bore (the kit test reads the row), so
# the button bears on the head face.
RADIUS_PLACES = 1
RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX
ROOT_RADIUS = 0.3
TAIL_ROOT_RADIUS = 0.4
SEAT_FILLET_RADIUS = 0.2
for _radius in (ROOT_RADIUS, TAIL_ROOT_RADIUS, SEAT_FILLET_RADIUS):
    if round(_radius, RADIUS_PLACES) != _radius:
        raise AssertionError("filing-stud corner MAX does not print as its model value")
if ROOT_RADIUS >= (THREAD_MODEL_DIA - RELIEF_DIA) / 2.0:
    raise AssertionError("filing-stud relief root radius is deeper than the relief")
if 2.0 * ROOT_RADIUS >= RELIEF_WIDTH_MIN:
    raise AssertionError("filing-stud relief roots meet at the narrowest relief")
if TAIL_ROOT_RADIUS >= (HEAD_DIA - TAIL_DIA) / 2.0:
    raise AssertionError("filing-stud tail root radius leaves no head step face")
RELIEF_ROOTS_CALLOUT = "2X"
# The shoulder station stays at three places: at the title block's .X band
# the relief would narrow under one pitch and the body could stand proud of
# the stack, so its callout states the function.
SHOULDER_CALLOUT = "BODY UNDER STACK TOP"
# Bought clamping nut: McMaster 90264A425, zinc-plated steel hex coupling
# nut, #10-24, 3/4 in long, 5/16 in across flats, fully threaded (verified
# live 2026-10-14). The inventory's M5 DIN 934 nut is 0.8D tall; the coupling
# nut meets the engagement rule and its corners stay inside the button rim.
# Its chamfers are not stated; each end is taken as one
# pitch of incomplete thread. drawing-guidelines.md rule 18 (thread engagement): at the worst case of the printed
# stack and stations the INSTALLED full-thread engagement in the nut is at
# least one and a half diameters. Engagement starts above the stack top
# past the nut's entry chamfer, or at the relief end (the die's runout lies
# in the relief), whichever is higher; it ends one pitch short of the faced
# tip (the tip chamfer) or at the nut's far chamfer.
NUT_SKU = "90264A425"
NUT_LENGTH = 3.0 / 4.0 * 25.4
NUT_ACROSS_FLATS = 5.0 / 16.0 * 25.4
NUT_CORNER_DIA = NUT_ACROSS_FLATS / math.cos(math.radians(30.0))
if NUT_CORNER_DIA >= _BUTTON_OD_MIN:
    raise AssertionError("filing-stud nut corners stand outside the button rim")
_NUT_CHAMFER = _THREAD_PITCH
_TIP_CHAMFER = _THREAD_PITCH


def installed_engagement(stack: float, seat_to_tip: float, relief_end: float) -> float:
    """Full-thread engagement in the coupling nut seated on the stack top;
    ``relief_end`` is the seat-to-relief-end length."""
    start = max(stack + _NUT_CHAMFER, relief_end)
    end = min(seat_to_tip - _TIP_CHAMFER, stack + NUT_LENGTH - _NUT_CHAMFER)
    return end - start


ENGAGEMENT_MIN = min(
    installed_engagement(stack, seat_to_tip, seat_to_tip - relief_station)
    for stack in (_STACK_MIN, _STACK_MAX)
    for seat_to_tip in (_SEAT_MIN, _SEAT_MAX)
    for relief_station in (_RELIEF_END_MIN, _RELIEF_END_MAX)
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
# the filed O.D. inside its printed band. The button prints the whole
# remainder as its rim runout: the largest TIR at its places that the budget
# allows (Main's round-6 ruling).
_BODY_MIN = BODY_DIA + BODY_BAND[1]
_FIT_SHIFT_MAX = (
    rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0] - _BODY_MIN
) / 2.0 + (button.BORE_DIA + button.BORE_BAND[0] - _BODY_MIN) / 2.0
RIM_RUNOUT_BUDGET_TIR = 2.0 * (rocker.HUB_COAXIALITY_DIA / 2.0 - _FIT_SHIFT_MAX)
_RUNOUT_STEP = 10.0**-button.OD_RUNOUT_PLACES
if not (
    button.OD_RUNOUT_TIR <= RIM_RUNOUT_BUDGET_TIR + 1e-9
    and button.OD_RUNOUT_TIR + _RUNOUT_STEP > RIM_RUNOUT_BUDGET_TIR + 1e-9
):
    raise AssertionError("filing-button rim runout is not the hub coaxiality remainder")
HUB_CENTRE_SHIFT_MAX = _FIT_SHIFT_MAX + button.OD_RUNOUT_TIR / 2.0
if 2.0 * HUB_CENTRE_SHIFT_MAX > rocker.HUB_COAXIALITY_DIA + 1e-9:
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
    "ShoulderStation": STATION_PLACES,
    "SeatStation": STATION_PLACES,
    "ReliefEndStation": STOCK_PLACES,
    "HeadBackStation": STOCK_PLACES,
    "TailEndStation": STOCK_PLACES,
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "TailProfile": {"TailDia"},
    "BodyProfile": {"BodyDia"},
    "ThreadProfile": {"ThreadDia"},
    "ReliefProfile": {"ReliefDia"},
    "StationReference": set(_STATIONS),
    "SeatFillet": {"SeatFilletR"},
    "ReliefRoots": {"ReliefRootR"},
    "TailRoot": {"TailRootR"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {"HeadDia": HEAD_PLACES},
    "TailProfile": {"TailDia": TAIL_PLACES},
    "BodyProfile": {"BodyDia": BODY_PLACES},
    "ThreadProfile": {"ThreadDia": 2},
    "ReliefProfile": {"ReliefDia": RELIEF_PLACES},
    "StationReference": dict(_STATIONS),
    "SeatFillet": {"SeatFilletR": RADIUS_PLACES},
    "ReliefRoots": {"ReliefRootR": RADIUS_PLACES},
    "TailRoot": {"TailRootR": RADIUS_PLACES},
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
DIMENSION_TEXT = {"ThreadDia": THREAD_CALLOUT}

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
# the nut clamps. The seat's reason rides its dimension as a callout; the
# shoulder row has no lane (the tip's extension line rises past it to the
# upper rows), so its reason stays a note.
STACK_CALLOUT = "HOLDS BUTTON STACK"
DRAWING_NOTES = (
    "SHOULDER KEEPS THE BODY UNDER THE STACK TOP: UPPER BUTTON RIDES THE BODY, NUT CLAMPS IT.\n"
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
        "name": "stud relief",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, round(_SEAT_Z + BODY_LENGTH, 6)],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": RELIEF_DIA,
        "length_mm": RELIEF_WIDTH,
        "note": _STUD_ROD,
    },
    {
        "name": "stud thread",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, round(_SEAT_Z + BODY_LENGTH + RELIEF_WIDTH, 6)],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": THREAD_MODEL_DIA,
        "length_mm": RELIEF_END_STATION,
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
