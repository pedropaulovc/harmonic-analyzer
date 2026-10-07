r"""Pure-data contract for the rocker arm's vise blank-end stop (MHA-CH-006-TL-01).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's vise setups (prechips S1/S2) a switchable magnetic base sits on
the fixed jaw's left end face; this one-piece steel L screws to the base's
back face and reaches round the blank's left end, where a bought hardened
6 mm dowel pin (the nose) touches the raw end face. It only positions the
blank along X before the jaws close: gentle contact, no cutting or clamping
load, and X zero is edge-found on the part afterwards. One is made.

Frame (the inventory's fixture frame, rocker-inv ``[fixtures.rocker-vise-stop]``):
origin at the fixed jaw's left end, on its inner gripping plane at the jaw
top, i.e. setup ``[-79.3369, Y, -4.68295]``; model +X = setup +X, +Z up. The
magnetic base occupies X -30..0 (its mating face on the jaw is X0), so this
part's seat face, clamped to the base's back face, is X-30. The arm runs -X
from the seat; the finger at the far end reaches -Y across the blank end.
The nose pin, bonded flush with the finger's back face, ends at the blank's
raw left end (setup X-170).

One-piece rather than the inventory's built-up arm + finger: the arm's end
could not carry the screw clearance, two finger screws and a dowel with
rule-12 walls, and the shop has no 4 mm reamer for that dowel
(review-loop r3 shop-additions, C bar).
"""

from __future__ import annotations

import _config
import ch_rocker_arm_spec as parent
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace

# --- The setup the stop serves (rocker-plan S1/S2; rocker-inv vise-stop) ---
# The PM-6 fixed jaw is 158.6738 wide (6.247 in); the frame origin sits on
# its left end. The raw blank's left end face is at setup X-170 and its Z
# span (setup frame) is -11.52825..4.47175; the nose is centred on the blank
# width (local Y-32.5) at setup Z-5.
JAW_HALF_WIDTH = 158.6738 / 2.0
BLANK_END_X_SETUP = -170.0
SETUP_Z_OF_JAW_TOP = -4.68295
BLANK_Z_SETUP = (-11.52825, 4.47175)
NOSE_Z_SETUP = -5.0
NOSE_Y = -32.5
# The arm stays this far behind the inner gripping plane, clear of the blank.
ARM_INNER_Y = 3.5

# The stop touches stock the profile pass removes: the blank end lies
# outboard of the finished arm's widest half-span (the parent's rod tip).
if not -BLANK_END_X_SETUP > parent.ROD_TIP_X:
    raise AssertionError("vise stop would touch the finished rocker arm, not its stock")

NOSE_FACE_X = BLANK_END_X_SETUP + JAW_HALF_WIDTH  # -90.6631
NOSE_Z = NOSE_Z_SETUP - SETUP_Z_OF_JAW_TOP  # -0.31705

# --- Bought items (not modelled) -------------------------------------------
# Nose: hardened 6 x 8 dowel pin (ISO 8734, m6: 6.004..6.012), bonded in the
# finger flush with its back face. Base: switchable magnetic base,
# 30 x 17 x 24, M6 back tap; one M6 x 80 SHCS through the part into it.
NOSE_PIN_DIA = 6.0
NOSE_PIN_MAX = 6.012
NOSE_PIN_LENGTH = 8.0
BASE_DEPTH = 30.0
SCREW_THREAD = "M6"
SCREW_MAJOR = 6.0
SCREW_LENGTH = 80.0

# --- Geometry (model frame above) -------------------------------------------
SEAT_X = -BASE_DEPTH
FINGER_THICK = 5.0
FINGER_FRONT_X = NOSE_FACE_X - (NOSE_PIN_LENGTH - FINGER_THICK)
BACK_X = FINGER_FRONT_X - FINGER_THICK
# Both axial sizes print from the seat face (the face clamped to the base).
OVERALL_LENGTH = SEAT_X - BACK_X  # 68.6631
FINGER_FRONT = SEAT_X - FINGER_FRONT_X  # 63.6631

ARM_WIDTH = 16.0
ARM_HEIGHT = 16.0
REAR_Y = ARM_INNER_Y + ARM_WIDTH  # the shared rear face, Y19.5
NOSE_FROM_REAR = REAR_Y - NOSE_Y  # 52
NOSE_HEIGHT = 17.0  # nose axis above the shared bottom face
BOTTOM_Z = NOSE_Z - NOSE_HEIGHT
ARM_TOP_Z = BOTTOM_Z + ARM_HEIGHT
FINGER_HEIGHT = 24.0
FINGER_TOP_Z = BOTTOM_Z + FINGER_HEIGHT
FINGER_LENGTH = 59.0
FINGER_END_Y = REAR_Y - FINGER_LENGTH
SCREW_FROM_REAR = 8.0
SCREW_HEIGHT = 8.0
SCREW_Y = REAR_Y - SCREW_FROM_REAR
SCREW_Z = BOTTOM_Z + SCREW_HEIGHT

# Drilled holes: the title block's drilled band (+0.10/0).
_DRILLED = _config.title_block("drilled_hole")
DRILLED_BAND = (float(_DRILLED["plus_mm"]), -float(_DRILLED["minus_mm"]))  # (upper, lower)
# Nose pin bonded with a retaining compound (shop-additions r3 #3 route):
# a drilled slip hole whose gap stays inside Loctite 638's 0.25 mm fill.
NOSE_HOLE_DIA = 6.10
BOND_GAP_MAX = 0.25
# ISO 273 medium clearance for the M6 screw (vendor thread kept).
SCREW_HOLE_DIA = 6.60

LINEAR_1PL = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
LINEAR_2PL = float(str(_config.title_block("linear_2pl")["display"]).lstrip("±"))
RULE12_WALL_TARGET = 2.0
# Realistic wander of a 6.6 drill run ~10 D through the full length (author's
# allowance for rule 12's deep-drilling term).
SCREW_HOLE_WANDER = 0.5

# --- Rule 12 at the printed worst case ---------------------------------------
_NOSE_R = (NOSE_HOLE_DIA + DRILLED_BAND[0]) / 2.0
_SCREW_R = (SCREW_HOLE_DIA + DRILLED_BAND[0]) / 2.0 + SCREW_HOLE_WANDER
WALLS = {
    "nose to finger top": (FINGER_HEIGHT - LINEAR_1PL) - (NOSE_HEIGHT + LINEAR_1PL) - _NOSE_R,
    "nose to finger end": (FINGER_LENGTH - LINEAR_1PL) - (NOSE_FROM_REAR + LINEAR_1PL) - _NOSE_R,
    "screw to rear face": SCREW_FROM_REAR - LINEAR_1PL - _SCREW_R,
    "screw to bottom": SCREW_HEIGHT - LINEAR_1PL - _SCREW_R,
    "screw to arm inner face": (ARM_WIDTH - LINEAR_1PL) - (SCREW_FROM_REAR + LINEAR_1PL) - _SCREW_R,
    "screw to arm top": (ARM_HEIGHT - LINEAR_1PL) - (SCREW_HEIGHT + LINEAR_1PL) - _SCREW_R,
}
_thin = {name: round(wall, 3) for name, wall in WALLS.items() if wall < RULE12_WALL_TARGET}
if _thin:
    raise AssertionError(f"vise stop walls under the rule-12 target: {_thin}")

# The bonded nose: the loosest drilled hole on the smallest pin stays inside
# the compound's gap; the tightest still slips over the largest pin.
if NOSE_HOLE_DIA + DRILLED_BAND[0] - NOSE_PIN_DIA > BOND_GAP_MAX:
    raise AssertionError("nose bond gap exceeds the retaining compound's fill")
if NOSE_HOLE_DIA + DRILLED_BAND[1] <= NOSE_PIN_MAX:
    raise AssertionError("nose pin does not slip into the smallest drilled hole")

# Engagement in the base's back tap at the longest printed grip (rule 12: 1.5 D).
SCREW_ENGAGEMENT_MIN = SCREW_LENGTH - (OVERALL_LENGTH + LINEAR_2PL)
if SCREW_ENGAGEMENT_MIN < 1.5 * SCREW_MAJOR:
    raise AssertionError("M6 screw engages under 1.5 D in the magnetic base")

# The nose disc lands on the raw end face, and every part of the stop stays
# below the blank top and outside it in X.
_BLANK_Z = tuple(z - SETUP_Z_OF_JAW_TOP for z in BLANK_Z_SETUP)
NOSE_EDGE_MARGIN = min(
    (NOSE_Z - NOSE_PIN_DIA / 2.0) - _BLANK_Z[0], _BLANK_Z[1] - (NOSE_Z + NOSE_PIN_DIA / 2.0)
)
if NOSE_EDGE_MARGIN < LINEAR_1PL:
    raise AssertionError("nose can miss the blank's end face")
if FINGER_TOP_Z + LINEAR_1PL >= _BLANK_Z[1]:
    raise AssertionError("finger stands above the blank top")
if ARM_TOP_Z + LINEAR_1PL >= 0.0:
    raise AssertionError("arm reaches the jaw top")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BlockProfile": {
        "FingerHeight",
        "FingerLength",
        "NoseHeight",
        "NoseFromRear",
        "NoseHoleDia",
        "ScrewHeight",
        "ScrewFromRear",
        "ScrewHoleDia",
    },
    "Block": {"OverallLength"},
    "ArmCutProfile": {"ArmHeight", "ArmWidth"},
    "ArmCut": {"FingerFront"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BlockProfile": {
        "FingerHeight": 1,
        "FingerLength": 1,
        "NoseHeight": 1,
        "NoseFromRear": 1,
        "NoseHoleDia": 2,
        "ScrewHeight": 1,
        "ScrewFromRear": 1,
        "ScrewHoleDia": 2,
    },
    "Block": {"OverallLength": 2},
    "ArmCutProfile": {"ArmHeight": 1, "ArmWidth": 1},
    "ArmCut": {"FingerFront": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked vise-stop dimension needs authored places")
# The walls above assume these places; a precision edit re-proves them.
if any(
    DRAWING_PRECISION_BY_NAME[name] != 1
    for name in ("FingerHeight", "FingerLength", "NoseHeight", "NoseFromRear",
                 "ScrewHeight", "ScrewFromRear", "ArmHeight", "ArmWidth")
):
    raise AssertionError("vise-stop wall proof assumes one-place positions and sizes")

SURFACE_FINISHES = ()
DRAWING_NOTES = "\n".join(
    (
        "BOND HARDENED DOWEL PIN NOSE WITH RETAINING COMPOUND, FLUSH WITH BACK FACE.",
        "MOUNT TO MAGNETIC BASE WITH ONE SOCKET HEAD CAP SCREW THROUGH THE ARM.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

_PLUS_X = ([1.0, 0.0, 0.0], ("__frame__",))
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "seat_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), SEAT_X),),
        requirements=("length",),
        fields={
            "normal": _PLUS_X,
            "plane": ({"frame": "model", "axis": "x", "value": SEAT_X}, ("SEAT_X", "BASE_DEPTH")),
            "length": (limits(OVERALL_LENGTH, 2), ("OVERALL_LENGTH",)),
            "length_nominal": (OVERALL_LENGTH, ("OVERALL_LENGTH",)),
            "note": (
                "clamped to the magnetic base's back face by one M6 SHCS",
                ("BASE_DEPTH", "SCREW_THREAD"),
            ),
        },
        precision={"length": 2},
    ),
    "finger_front": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), FINGER_FRONT_X),),
        requirements=("length",),
        fields={
            "normal": _PLUS_X,
            "plane": (
                {"frame": "model", "axis": "x", "value": FINGER_FRONT_X},
                ("FINGER_FRONT_X", "NOSE_FACE_X", "NOSE_PIN_LENGTH", "FINGER_THICK"),
            ),
            "length": (limits(FINGER_FRONT, 2), ("FINGER_FRONT",)),
            "length_nominal": (FINGER_FRONT, ("FINGER_FRONT",)),
        },
        precision={"length": 2},
    ),
    "nose_hole": ExportFeature(
        kind="hole",
        faces=(CylinderFace(NOSE_HOLE_DIA),),
        requirements=("dia", "at", "end"),
        fields={
            "at": ([FINGER_FRONT_X, NOSE_Y, NOSE_Z], ("FINGER_FRONT_X", "NOSE_Y", "NOSE_Z")),
            "axis": _PLUS_X,
            "dia": (limits(NOSE_HOLE_DIA, 2, DRILLED_BAND), ("NOSE_HOLE_DIA", "DRILLED_BAND")),
            "dia_nominal": (NOSE_HOLE_DIA, ("NOSE_HOLE_DIA",)),
            "thru": (True, ("DRAWING_DIMENSIONS",)),
            "process": ("drill", ("DRILLED_BAND",)),
            # The stop contact: the bonded pin's end, on the blank's raw left
            # end (nominal; X zero is edge-found on the part afterwards).
            "end": (
                [NOSE_FACE_X, NOSE_Y, NOSE_Z],
                ("NOSE_FACE_X", "BLANK_END_X_SETUP", "JAW_HALF_WIDTH", ("ch_rocker_arm_spec", "ROD_TIP_X")),
            ),
            "supply_length": (NOSE_PIN_LENGTH, ("NOSE_PIN_LENGTH",)),
            "note": (
                "bought hardened 6 x 8 dowel pin bonded flush with the back face; its end is the blank-end stop",
                ("NOSE_PIN_DIA", "NOSE_PIN_LENGTH", "BOND_GAP_MAX"),
            ),
        },
        precision={"dia": 2},
    ),
    "screw_hole": ExportFeature(
        kind="hole",
        faces=(CylinderFace(SCREW_HOLE_DIA),),
        requirements=("dia", "at"),
        fields={
            "at": ([SEAT_X, SCREW_Y, SCREW_Z], ("SEAT_X", "SCREW_Y", "SCREW_Z")),
            "axis": ([-1.0, 0.0, 0.0], ("__frame__",)),
            "dia": (limits(SCREW_HOLE_DIA, 2, DRILLED_BAND), ("SCREW_HOLE_DIA", "DRILLED_BAND")),
            "dia_nominal": (SCREW_HOLE_DIA, ("SCREW_HOLE_DIA",)),
            "thru": (True, ("DRAWING_DIMENSIONS",)),
            "process": ("drill", ("DRILLED_BAND",)),
            "thread": (SCREW_THREAD, ("SCREW_THREAD",)),
            "note": (
                "clearance for one M6 x 80 SHCS into the magnetic base's M6 back tap "
                "(vendor thread kept)",
                ("SCREW_THREAD", "SCREW_LENGTH", "SCREW_ENGAGEMENT_MIN"),
            ),
        },
        precision={"dia": 2},
    ),
}
