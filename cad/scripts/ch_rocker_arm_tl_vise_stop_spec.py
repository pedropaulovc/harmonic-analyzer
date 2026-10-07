r"""Pure-data contract for the rocker arm's vise blank-end stop (MHA-CH-006-TL-01).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's vise setups (prechips S1/S2) a bought Kanetec MB-PM switchable
magnetic base sits on the fixed jaw's left end face; this one-piece
aluminium L screws to the base's tapped face and reaches round the blank's left end,
where a bought hardened 6 mm dowel pin (the nose) touches the raw end face.
It only positions the blank along X before the jaws close: hand-seating
contact, no cutting or clamping load, and X zero is edge-found on the part
afterwards. One is made.

Frame (the inventory's fixture frame, rocker-inv ``[fixtures.rocker-vise-stop]``):
origin at the fixed jaw's left end, on its inner gripping plane at the jaw
top, i.e. setup ``[-79.3369, Y, -4.68295]``; model +X = setup +X, +Z up. The
base's attractive face lies on the jaw's end face (X0) and its tapped face
is X-40, this part's seat face. The base envelope in this frame is
X -40..0, Y 0.5..40.5, Z -41.31705..-1.31705 (``BASE_ENVELOPE``), its switch
knob standing 18 further toward +Y; the M6 tap is at the face centre
(Y20.5, Z-21.31705). A lug at the seat carries the screw; beyond it the arm
is a flange over a full-width step that leaves the screw head and the hex
key room, and the finger at the far end reaches -Y across the blank end.
The nose pin, bonded flush with the finger's back face, ends at the blank's
raw left end (setup X-170).

One-piece rather than the inventory's built-up arm + finger: the arm's end
could not carry the screw clearance, two finger screws and a dowel with
rule-12 walls, and the shop has no 4 mm reamer for that dowel
(review-loop r3 shop-additions, C bar). The inventory's 30 x 17 x 24 base
has no vendor SKU; the MB-PM is the smallest documented switchable base
with an M6 tap. Aluminium, not steel: Kanetec warns that a magnetic plate
mounted on the tapped face drops the base's holding power significantly
and asks for a nonmagnetic one (aluminium, SUS304, brass).
"""

from __future__ import annotations

import math

import _config
import ch_rocker_arm_spec as parent
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace

# --- The setup the stop serves -----------------------------------------------
# The prechips rocker route (fixture-cad rocker-plan.toml) is the one that
# uses this stop: its S1 and S2 name stop_fixture "rocker-vise-stop", and its
# [stock.prepared] blank is 340 x 65 x 16, X -170..170 and Y -28..37 relative
# to S1 zero (10 mm scrap ears beyond X +-160). The tracked
# cad/process/ch_rocker_arm/plan.toml is the rev-3 route (310 x 45 blank,
# X -155..155) whose S1 stop is a bare fixed-jaw stop, not this fixture; the
# prechips route replaces it when the fixture travelers land. The PM-6 fixed
# jaw is 158.6738 wide (6.247 in); the frame origin sits on its left end.
# The blank's Z span in the setup frame is -11.52825..4.47175; the nose is
# centred on the 65 mm width (local Y-32.5) at setup Z-5.
JAW_HALF_WIDTH = 158.6738 / 2.0
PREPARED_BLANK_LENGTH = 340.0  # rocker-plan.toml [stock.prepared] length_mm
BLANK_END_X_SETUP = -PREPARED_BLANK_LENGTH / 2.0  # rocker-plan origin_mm X-170
SETUP_Z_OF_JAW_TOP = -4.68295
BLANK_Z_SETUP = (-11.52825, 4.47175)
NOSE_Z_SETUP = -5.0
NOSE_Y = -32.5
# rocker-inv [fixtures.vise-pm-6]: bed slideway to jaw top 1.7695 in.
JAW_HEIGHT = 1.7695 * 25.4

# The stop touches stock the profile pass removes: the blank end lies
# outboard of the finished arm's widest half-span (the parent's rod tip).
if not -BLANK_END_X_SETUP > parent.ROD_TIP_X:
    raise AssertionError("vise stop would touch the finished rocker arm, not its stock")

NOSE_FACE_X = BLANK_END_X_SETUP + JAW_HALF_WIDTH  # -90.6631
NOSE_Z = NOSE_Z_SETUP - SETUP_Z_OF_JAW_TOP  # -0.31705

# --- Bought items (not modelled) -------------------------------------------
# Nose: hardened 6 x 8 dowel pin (ISO 8734, m6: 6.004..6.012), bonded in the
# finger flush with its back face.
NOSE_PIN_DIA = 6.0
NOSE_PIN_MAX = 6.012
NOSE_PIN_LENGTH = 8.0
# Base: Kanetec MB-PM magnetic holder base (Kanetec product guide
# http://www.kanetec.co.jp/en/pdf/057_068.pdf, p. N-2 table and the MB-PM
# figure): 40 x 40 x 40, 600 N holding power, ON/OFF knob standing to (58)
# overall on one side, tapped hole "M6 x Depth 6" at the centre of the face
# opposite the attractive face. Its M6 is the vendor's thread, kept.
BASE_SKU = "KANETEC MB-PM"
BASE_SIZE = 40.0
BASE_DEPTH = BASE_SIZE
BASE_HOLDING_N = 600.0
BASE_KNOB_PROJECTION = 58.0 - BASE_SIZE
BASE_TAP_DEPTH = 6.0
SCREW_THREAD = "M6"
SCREW_MAJOR = 6.0
SCREW_PITCH = 1.0
# ISO 4762 M6 socket head cap screw: head dk 10, k 6; the chamfered end of
# ISO 4753 leaves up to 2 P of incomplete thread (u <= 2P).
SCREW_LENGTH = 16.0
SCREW_HEAD_DIA = 10.0
SCREW_HEAD_HEIGHT = 6.0
SCREW_END_INCOMPLETE = 2.0 * SCREW_PITCH

# --- Geometry (model frame above) -------------------------------------------
SEAT_X = -BASE_DEPTH
FINGER_THICK = 5.0
FINGER_FRONT_X = NOSE_FACE_X - (NOSE_PIN_LENGTH - FINGER_THICK)
BACK_X = FINGER_FRONT_X - FINGER_THICK
# The axial sizes print from the seat face (the face clamped to the base).
OVERALL_LENGTH = SEAT_X - BACK_X  # 58.6631
FINGER_FRONT = SEAT_X - FINGER_FRONT_X  # 53.6631

# The screw sits on the base's tap; the base stays 0.5 behind the rear jaw's
# gripping plane (clear of the risers inside the jaws) and below the jaw top.
SCREW_Y = 0.5 + BASE_SIZE / 2.0  # 20.5
SCREW_FROM_REAR = 8.0
SCREW_HEIGHT = 8.0
ARM_WIDTH = 16.0
REAR_Y = SCREW_Y + SCREW_FROM_REAR  # 28.5, the shared rear face
ARM_INNER_Y = REAR_Y - ARM_WIDTH  # 12.5
NOSE_FROM_REAR = REAR_Y - NOSE_Y  # 61
NOSE_HEIGHT = 29.0  # nose axis above the shared bottom face (the lug's)
BOTTOM_Z = NOSE_Z - NOSE_HEIGHT
SCREW_Z = BOTTOM_Z + SCREW_HEIGHT
ARM_HEIGHT = 28.0
ARM_TOP_Z = BOTTOM_Z + ARM_HEIGHT
FINGER_HEIGHT = 36.0
FINGER_TOP_Z = BOTTOM_Z + FINGER_HEIGHT
FINGER_LENGTH = 68.0
FINGER_END_Y = REAR_Y - FINGER_LENGTH
# Beyond the lug a full-width step clears the screw head and the hex key;
# both its sizes print from the lug's seat and bottom faces.
NOTCH_HEIGHT = 16.0
NOTCH_TOP_Z = BOTTOM_Z + NOTCH_HEIGHT
# Seat face to the lug's head-bearing face: printed at three places so its
# band costs the screw's engagement only 0.26 (below).
SCREW_GRIP = 11.15
GRIP_FACE_X = SEAT_X - SCREW_GRIP

BASE_ENVELOPE = (
    (SEAT_X, 0.0),
    (SCREW_Y - BASE_SIZE / 2.0, SCREW_Y + BASE_SIZE / 2.0),
    (SCREW_Z - BASE_SIZE / 2.0, SCREW_Z + BASE_SIZE / 2.0),
)
if not BASE_ENVELOPE[1][0] > 0.0:
    raise AssertionError("magnetic base reaches the rear jaw's gripping plane")
if not BASE_ENVELOPE[2][1] < 0.0:
    raise AssertionError("magnetic base stands above the jaw top")
if not BASE_ENVELOPE[2][0] > -JAW_HEIGHT:
    raise AssertionError("magnetic base hangs below the jaw's bed slideway")

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
LINEAR_3PL = float(str(_config.title_block("linear_3pl")["display"]).lstrip("±"))
RULE12_WALL_TARGET = 2.0

# --- Rule 12 at the printed worst case ---------------------------------------
_NOSE_R = (NOSE_HOLE_DIA + DRILLED_BAND[0]) / 2.0
# The screw hole is drilled through the lug only (about 2 D), so no
# deep-drilling wander is added.
_SCREW_R = (SCREW_HOLE_DIA + DRILLED_BAND[0]) / 2.0
WALLS = {
    "nose to finger top": (FINGER_HEIGHT - LINEAR_1PL) - (NOSE_HEIGHT + LINEAR_1PL) - _NOSE_R,
    "nose to finger bottom": (NOSE_HEIGHT - LINEAR_1PL) - (NOTCH_HEIGHT + LINEAR_1PL) - _NOSE_R,
    "nose to finger end": (FINGER_LENGTH - LINEAR_1PL) - (NOSE_FROM_REAR + LINEAR_1PL) - _NOSE_R,
    "screw to rear face": SCREW_FROM_REAR - LINEAR_1PL - _SCREW_R,
    "screw to bottom": SCREW_HEIGHT - LINEAR_1PL - _SCREW_R,
    "screw to arm inner face": (ARM_WIDTH - LINEAR_1PL) - (SCREW_FROM_REAR + LINEAR_1PL) - _SCREW_R,
    "flange over the step": (ARM_HEIGHT - LINEAR_1PL) - (NOTCH_HEIGHT + LINEAR_1PL),
}
_thin = {name: round(wall, 3) for name, wall in WALLS.items() if wall < RULE12_WALL_TARGET}
if _thin:
    raise AssertionError(f"vise stop walls under the rule-12 target: {_thin}")
# The screw head clears the flange over the step at the worst case.
HEAD_CLEARANCE_MIN = (
    (NOTCH_HEIGHT - LINEAR_1PL) - (SCREW_HEIGHT + LINEAR_1PL) - SCREW_HEAD_DIA / 2.0
)
if HEAD_CLEARANCE_MIN <= 0.0:
    raise AssertionError("screw head fouls the flange over the step")
if GRIP_FACE_X - SCREW_HEAD_HEIGHT <= FINGER_FRONT_X:
    raise AssertionError("screw head fouls the finger")

# The bonded nose: the loosest drilled hole on the smallest pin stays inside
# the compound's gap; the tightest still slips over the largest pin.
if NOSE_HOLE_DIA + DRILLED_BAND[0] - NOSE_PIN_DIA > BOND_GAP_MAX:
    raise AssertionError("nose bond gap exceeds the retaining compound's fill")
if NOSE_HOLE_DIA + DRILLED_BAND[1] <= NOSE_PIN_MAX:
    raise AssertionError("nose pin does not slip into the smallest drilled hole")

# --- The screw in the base's M6 x 6 tap, at the printed grip's worst case ----
# On the shortest grip the tip stops at least 1 P short of the tap's thread
# depth; on the longest, the full-thread overlap is what the protrusion
# leaves after the screw end's incomplete thread.
SCREW_PROTRUSION_MAX = round(SCREW_LENGTH - (SCREW_GRIP - LINEAR_3PL), 6)  # 4.98
SCREW_PROTRUSION_MIN = round(SCREW_LENGTH - (SCREW_GRIP + LINEAR_3PL), 6)  # 4.72
if SCREW_PROTRUSION_MAX > BASE_TAP_DEPTH - SCREW_PITCH + 1e-9:
    raise AssertionError("M6 screw can reach the bottom of the base's tap")
SCREW_ENGAGEMENT_MIN = round(SCREW_PROTRUSION_MIN - SCREW_END_INCOMPLETE, 6)  # 2.72
if SCREW_ENGAGEMENT_MIN <= 0.0:
    raise AssertionError("M6 screw engages no full thread in the base")
# Under rule 12's 1.5 D: the base's 6 mm tap caps it. Named exception row
# MHA-CH-006-TL-01 (user, 2026-10-07): hand-seating load only, no cutting load.
SCREW_ENGAGEMENT_MIN_D = SCREW_ENGAGEMENT_MIN / SCREW_MAJOR
SCREW_ENGAGEMENT_PRINTED = math.floor(SCREW_ENGAGEMENT_MIN * 10.0 + 1e-9) / 10.0
SCREW_ENGAGEMENT_PRINTED_D = math.floor(SCREW_ENGAGEMENT_MIN_D * 100.0 + 1e-9) / 100.0
# The tip's clearance to the tap bottom at the shortest grip: the sheet
# states it so the grip's three-place band reads as the bottoming limit.
SCREW_TIP_CLEARANCE_MIN = round(BASE_TAP_DEPTH - SCREW_PROTRUSION_MAX, 6)  # 1.02
SCREW_TIP_CLEARANCE_PRINTED = math.floor(SCREW_TIP_CLEARANCE_MIN * 10.0 + 1e-9) / 10.0

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
if ARM_INNER_Y - LINEAR_1PL <= 0.0:
    raise AssertionError("arm reaches the rear jaw's gripping plane")

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
    "NotchProfile": {"ScrewGrip", "NotchHeight"},
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
    "Block": {"OverallLength": 1},
    "ArmCutProfile": {"ArmHeight": 1, "ArmWidth": 1},
    "ArmCut": {"FingerFront": 1},
    "NotchProfile": {"ScrewGrip": 3, "NotchHeight": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked vise-stop dimension needs authored places")
# The walls above assume one-place sizes and the screw's engagement a
# three-place grip; a precision edit re-proves them.
if any(
    places != 1
    for name, places in DRAWING_PRECISION_BY_NAME.items()
    if name not in ("NoseHoleDia", "ScrewHoleDia", "ScrewGrip")
):
    raise AssertionError("vise-stop wall proof assumes one-place positions and sizes")
if DRAWING_PRECISION_BY_NAME["ScrewGrip"] != 3:
    raise AssertionError("the screw's engagement proof assumes a three-place grip")

SURFACE_FINISHES = ()
DRAWING_NOTES = "\n".join(
    (
        "BOND NOSE PIN WITH RETAINING COMPOUND.",
        "HAND-SEATING LOAD ONLY, NO CUTTING LOAD.",
    )
)
# The bought nose pin and its seating ride the hole's callout (rule 6: the
# note carries no numbers); the projection is reference, set by the pin.
NOSE_PROJECTION = NOSE_PIN_LENGTH - FINGER_THICK
NOSE_PIN_CALLOUT = "\n".join(
    (
        f"NOSE: Ø{NOSE_PIN_DIA:g} x {NOSE_PIN_LENGTH:g} ISO 8734 DOWEL PIN",
        f"FLUSH AT BACK FACE, ({NOSE_PROJECTION:.1f}) PROUD",
    )
)
# Named exception: MHA-CH-006-TL-01 engagement (drawing-simplicity-policy.md, "Named exceptions").
SCREW_HOLE_CALLOUT = "\n".join(
    (
        f"DRILL THRU FOR {SCREW_THREAD} X {SCREW_LENGTH:g} SHCS",
        f"INTO {BASE_SKU} {SCREW_THREAD} X {BASE_TAP_DEPTH:g} DEEP TAP",
        f"ENGAGEMENT {SCREW_ENGAGEMENT_PRINTED:.1f} MIN ({SCREW_ENGAGEMENT_PRINTED_D:.2f}D)",
        f"TIP {SCREW_TIP_CLEARANCE_PRINTED:.1f} MIN CLEAR OF TAP BOTTOM",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

_PLUS_X = ([1.0, 0.0, 0.0], ("__frame__",))
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "seat_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((1.0, 0.0, 0.0), SEAT_X),),
        requirements=("length",),
        fields={
            "normal": _PLUS_X,
            "plane": ({"frame": "model", "axis": "x", "value": SEAT_X}, ("SEAT_X", "BASE_DEPTH")),
            "length": (limits(OVERALL_LENGTH, 1), ("OVERALL_LENGTH",)),
            "length_nominal": (OVERALL_LENGTH, ("OVERALL_LENGTH",)),
            "note": (
                "clamped to the tapped face of a Kanetec MB-PM magnetic base "
                "(40 x 40 x 40, M6 x 6 tap) by one M6 x 16 SHCS",
                ("BASE_SKU", "BASE_SIZE", "BASE_TAP_DEPTH", "SCREW_THREAD", "SCREW_LENGTH"),
            ),
        },
        precision={"length": 1},
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
            "length": (limits(FINGER_FRONT, 1), ("FINGER_FRONT",)),
            "length_nominal": (FINGER_FRONT, ("FINGER_FRONT",)),
        },
        precision={"length": 1},
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
                "clearance through the lug for one M6 x 16 SHCS into the Kanetec "
                "MB-PM's M6 x 6 tap (vendor thread kept); head on the lug face "
                "11.150 from the seat; full-thread engagement 2.7 min (0.45D), "
                "hand-seating load only",
                (
                    "SCREW_THREAD",
                    "SCREW_LENGTH",
                    "BASE_SKU",
                    "BASE_TAP_DEPTH",
                    "SCREW_GRIP",
                    "SCREW_ENGAGEMENT_MIN",
                ),
            ),
        },
        precision={"dia": 2},
    ),
}
