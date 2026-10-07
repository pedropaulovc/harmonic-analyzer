r"""Pure-data contract for the rocker arm hub filing stud (MHA-CH-006-TL-05).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's hub filing hold (prechips S3F) the bench vise grips the stud's
tail; the lapped body locates in the arm's reamed pivot bore (datum A) and
carries the two filing buttons (MHA-CH-006-TL-04). The lower button seats on
the integral head, the arm's hub sits between the buttons, and a bought
1/4-20 nut on the thread clamps the stack. Turned in one chucking from 4140 at
HRC 32 and left unhardened (shop-additions section 1): nothing files on it.

Frame: the stud axis is model +X with the head's seat face at X0, the body
and thread toward +X and the head and vise tail toward -X; every axial size
prints from that seat. In the inventory fixture frame (stud axis Z, upper
hub face Z0) the seat sits at Z = -(HUB_LENGTH + button thickness), so
inventory Z = model X - (HUB_LENGTH + button thickness).
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_filing_button_spec as button
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace

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
if not (button.BORE_DIA + button.BORE_BAND[0] < HEAD_DIA < button.OD + button.OD_BAND[1]):
    raise AssertionError("filing-stud head does not land on the button face")

# Axial sizes from the seat face (X0), the one datum the stack reads from.
# The body carries the lower button and the whole hub at every printed
# button thickness and hub length, and stops short of the stack top so the
# nut bears on the upper button (which then centres on the thread crests:
# its float is far inside the hub's printed O.D. band).
AXIAL_PLACES = 1
BODY_LENGTH = 12.5
THREAD_END = 24.0  # seat face to the threaded end
TAIL_END = 45.0  # seat face to the vise end: head plus a forty-two vise tail
OVERALL_LENGTH = TAIL_END + THREAD_END  # printed as a reference for cut-off
TAIL_DIA = 8.0  # stout in the vise; clear of the thread and body sizes
# HA fastener policy (memory/fastener-policy-us-customary.md): the
# inventory's M6 maps to 1/4-20 UNC; an external thread is class 2A.
THREAD = "1/4-20 UNC-2A"
THREAD_MODEL_DIA = 6.35
THREAD_MINOR_DIA = 4.98  # 1/4-20 external minor, for the cosmetic thread

_BUTTON_MIN, _BUTTON_MAX = limits(button.THICKNESS, button.THICKNESS_PLACES)
_STACK_MIN = 2.0 * _BUTTON_MIN + rocker.HUB_LENGTH
_STACK_MAX = 2.0 * _BUTTON_MAX + rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
_HUB_TOP_MAX = _BUTTON_MAX + rocker.HUB_LENGTH + rocker.HUB_LENGTH_BAND[0]
_BODY_LEN_MIN, _BODY_LEN_MAX = limits(BODY_LENGTH, AXIAL_PLACES)
if _BODY_LEN_MAX >= _STACK_MIN:
    raise AssertionError("filing-stud body can stand proud of the button stack")
if _BODY_LEN_MIN <= _HUB_TOP_MAX:
    raise AssertionError("filing-stud body does not reach through the hub")
NUT_THICKNESS = 5.56  # bought 1/4-20 hex nut, 7/32 in
if limits(THREAD_END, AXIAL_PLACES)[0] - _STACK_MAX < NUT_THICKNESS:
    raise AssertionError("filing-stud thread is too short for the nut")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia"},
    "Head": {"HeadLength"},
    "TailProfile": {"TailDia"},
    "Tail": {"TailEnd"},
    "BodyProfile": {"BodyDia"},
    "Body": {"BodyLength"},
    "ThreadProfile": {"ThreadDia"},
    "Thread": {"ThreadEnd"},
    "StationReference": {"OverallLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {"HeadDia": 1},
    "Head": {"HeadLength": AXIAL_PLACES},
    "TailProfile": {"TailDia": 1},
    "Tail": {"TailEnd": AXIAL_PLACES},
    "BodyProfile": {"BodyDia": BODY_PLACES},
    "Body": {"BodyLength": AXIAL_PLACES},
    "ThreadProfile": {"ThreadDia": 2},
    "Thread": {"ThreadEnd": AXIAL_PLACES},
    "StationReference": {"OverallLength": AXIAL_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked filing-stud dimension needs authored places")
# The overall restates the two ends for stock cut-off; the thread size
# prints as its designation, not as a plain diameter.
# Codex round 4: the locating diameter prints as a reference; the fit to its
# three mating bores (hand slide, no shake) governs it, and BODY_BAND stays
# the exported design intent of that fit.
REFERENCE_DIMENSIONS = frozenset({"OverallLength", "BodyDia"})
DIMENSION_TEXT = {"ThreadDia": THREAD}

SURFACE_FINISHES = ()
DRAWING_NOTES = (
    "AXIAL SIZES FROM THE HEAD SEAT FACE; SEAT SQUARE TO THE LOCATING DIAMETER.\n"
    "FIT LOCATING DIAMETER TO THE ROCKER ARM PIVOT BORE AND BOTH FILING BUTTON\n"
    "BORES: EACH SLIDES ON BY HAND WITHOUT SHAKE. VISE TAIL IS HELD ONLY.\n"
    "DO NOT HARDEN."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

_AXIS = ([1.0, 0.0, 0.0], ("__frame__",))
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "locating_body": ExportFeature(
        kind="boss",
        faces=(CylinderFace(BODY_DIA),),
        requirements=("dia", "length"),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia": (
                limits(BODY_DIA, BODY_PLACES, BODY_BAND),
                ("BODY_DIA", "BODY_BAND", ("ch_rocker_arm_spec", "PIVOT_HOLE_DIA"),
                 ("ch_rocker_arm_spec", "PIVOT_HOLE_BAND")),
            ),
            "dia_nominal": (BODY_DIA, ("BODY_DIA",)),
            "length": (
                limits(BODY_LENGTH, AXIAL_PLACES),
                ("BODY_LENGTH", ("ch_rocker_arm_spec", "HUB_LENGTH")),
            ),
        },
        precision={"dia": BODY_PLACES, "length": AXIAL_PLACES},
    ),
    "button_seat": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), 0.0),),
        requirements=("dia",),
        fields={
            "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "x", "value": 0.0}, ("__frame__",)),
            "dia": (limits(HEAD_DIA, 1), ("HEAD_DIA",)),
        },
        precision={"dia": 1},
    ),
    "thread": ExportFeature(
        kind="boss",
        faces=(CylinderFace(THREAD_MODEL_DIA),),
        requirements=("thread",),
        fields={
            "axis": _AXIS,
            "thread": (THREAD, ("THREAD",)),
            "end": (limits(THREAD_END, AXIAL_PLACES), ("THREAD_END",)),
        },
        precision={"end": AXIAL_PLACES},
    ),
    "vise_tail": ExportFeature(
        kind="boss",
        faces=(CylinderFace(TAIL_DIA),),
        requirements=("dia",),
        fields={
            "axis": _AXIS,
            "dia": (limits(TAIL_DIA, 1), ("TAIL_DIA",)),
            "end": (
                [-x for x in reversed(limits(TAIL_END, AXIAL_PLACES))],
                ("TAIL_END",),
            ),
        },
        precision={"dia": 1, "end": AXIAL_PLACES},
    ),
}
