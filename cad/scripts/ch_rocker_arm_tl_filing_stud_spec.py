r"""Pure-data contract for the rocker arm hub filing stud (MHA-CH-006-TL-05).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's hub filing hold (prechips S3F) the bench vise grips the stud's
tail; the lapped body locates in the arm's reamed pivot bore (datum A) and
carries the two filing buttons (MHA-CH-006-TL-04). The lower button seats on
the integral head, the arm's hub sits between the buttons, and a bought
1/4-20 nut on the thread clamps the stack. Turned in one chucking from 4140 at
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
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
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
HEAD_DIA = 9.0
HEAD_LENGTH = 3.0
if not (
    button.BORE_DIA + button.BORE_BAND[0]
    < HEAD_DIA
    < limits(button.OD, button.OD_PLACES)[0]
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
BODY_LENGTH = 12.8  # model: seat face to the thread start (derived on print)
THREAD_END = 24.0  # seat face to the faced tip; printed tip to seat
THREAD_START = THREAD_END - BODY_LENGTH  # printed: tip to the thread start
TAIL_END = 45.0  # seat face to the vise end: head plus a forty-two vise tail
HEAD_BACK = THREAD_END + HEAD_LENGTH  # printed: tip to the head's back face
OVERALL_LENGTH = TAIL_END + THREAD_END  # printed: tip to the vise end
TAIL_DIA = 8.0  # stout in the vise; clear of the thread and body sizes
# HA fastener policy (memory/fastener-policy-us-customary.md): the
# inventory's M6 maps to 1/4-20 UNC; an external thread is class 2A.
THREAD = "1/4-20 UNC-2A"
THREAD_MODEL_DIA = 6.35

_BUTTON_MIN, _BUTTON_MAX = limits(button.THICKNESS, button.THICKNESS_PLACES)
_STACK_MIN = 2.0 * _BUTTON_MIN + rocker.HUB_LENGTH
_STACK_MAX = 2.0 * _BUTTON_MAX + rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
_HUB_TOP_MAX = _BUTTON_MAX + rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
_SEAT_MIN, _SEAT_MAX = limits(THREAD_END, STATION_PLACES)
_START_MIN, _START_MAX = limits(THREAD_START, STATION_PLACES)
_BODY_LEN_MIN, _BODY_LEN_MAX = _SEAT_MIN - _START_MAX, _SEAT_MAX - _START_MIN
if _BODY_LEN_MAX >= _STACK_MIN:
    raise AssertionError("filing-stud body can stand proud of the button stack")
if _BODY_LEN_MIN <= _HUB_TOP_MAX:
    raise AssertionError("filing-stud body does not reach through the hub")
NUT_THICKNESS = 5.56  # bought 1/4-20 hex nut, 7/32 in
if _SEAT_MIN - _STACK_MAX < NUT_THICKNESS:
    raise AssertionError("filing-stud thread is too short for the nut")

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
# Policy rules 2 and 6: the matched fit sits on the locating diameter's
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
    "VISE TAIL IS HELD ONLY. DO NOT HARDEN."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

_AXIS = ([1.0, 0.0, 0.0], ("__frame__",))
# Stations are the printed tip-baseline bands, read from the faced tip.
_FROM_TIP = ("tip_face", ("THREAD_END",))
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "tip_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), THREAD_END),),
        requirements=(),
        fields={
            "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
            "plane": (
                {"frame": "model", "axis": "x", "value": THREAD_END},
                ("THREAD_END",),
            ),
        },
    ),
    "locating_body": ExportFeature(
        kind="boss",
        faces=(CylinderFace(BODY_DIA),),
        requirements=("note", "station"),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia_nominal": (BODY_DIA, ("BODY_DIA",)),
            "note": (
                BODY_FIT_NOTE,
                (
                    "BODY_FIT_NOTE",
                    ("ch_rocker_arm_spec", "PIVOT_HOLE_DIA"),
                    ("ch_rocker_arm_spec", "PIVOT_HOLE_BAND"),
                ),
            ),
            # The journal runs from the printed thread start to the seat.
            "station": (
                limits(THREAD_START, STATION_PLACES),
                ("THREAD_START", ("ch_rocker_arm_spec", "HUB_LENGTH")),
            ),
            "height_from": _FROM_TIP,
        },
        precision={"station": STATION_PLACES},
    ),
    "button_seat": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), 0.0),),
        requirements=("dia", "station"),
        fields={
            "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "x", "value": 0.0}, ("__frame__",)),
            "dia": (limits(HEAD_DIA, 1), ("HEAD_DIA",)),
            "station": (limits(THREAD_END, STATION_PLACES), ("THREAD_END",)),
            "height_from": _FROM_TIP,
        },
        precision={"dia": 1, "station": STATION_PLACES},
    ),
    "thread": ExportFeature(
        kind="boss",
        faces=(CylinderFace(THREAD_MODEL_DIA),),
        requirements=("thread",),
        fields={
            "axis": _AXIS,
            "thread": (THREAD, ("THREAD",)),
            "length": (limits(THREAD_START, STATION_PLACES), ("THREAD_START",)),
        },
        precision={"length": STATION_PLACES},
    ),
    "vise_tail": ExportFeature(
        kind="boss",
        faces=(CylinderFace(TAIL_DIA),),
        requirements=("dia",),
        fields={
            "axis": _AXIS,
            "dia": (limits(TAIL_DIA, 1), ("TAIL_DIA",)),
            "station": (limits(OVERALL_LENGTH, STOCK_PLACES), ("OVERALL_LENGTH",)),
            "height_from": _FROM_TIP,
        },
        precision={"dia": 1, "station": STOCK_PLACES},
    ),
}
