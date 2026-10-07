r"""Pure-data contract for the cone pivot post's bond cradle (MHA-DT-005-TL-01).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). While the
retaining compound in the cone and crank sockets cures (prechips S6/S7), the
post lies on its side in this cradle, held by gravity alone: the turned body
in the body seat, the raw tail on the tail seat, foot B against the foot stop,
the cone sleeve's north cap on the two tilted cone pins and the crank sleeve's
north face on the two crank pins.

Frame: the cone pivot post's model frame R0, unchanged (make-data section 1.2:
the cradle frame IS the post frame, so a prechips pose of the post in the
cradle is the identity). Post axis +Y through X0 Z0 with foot B, the
foot-stop face, at Y0; crank socket axis +Z (up). The base top is at Z -30
and the base bottom at Z -40. Every height prints from the base top and every
station along the post from foot B.
"""

from __future__ import annotations

import math

import dt_cone_pivot_post_spec as post
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl

# Base plate, foot stop and the two saddles (inventory cone-bond-cradle rows).
BASE_WIDTH = 80.0
BASE_LENGTH = 134.0
BASE_THICK = 10.0
BASE_TOP_Z = -30.0
BASE_END_Y = -12.0
STOP_WIDTH = 30.0
STOP_THICK = -BASE_END_Y  # flush with the base end; its +Y face is foot B
BLOCK_HEIGHT = 15.0  # the stop and both saddles, above the base top
BLOCK_TOP_Z = BASE_TOP_Z + BLOCK_HEIGHT
SADDLE_WIDTH = 60.0
BODY_SADDLE_Y = 10.0
BODY_SADDLE_THICK = 10.0
TAIL_SADDLE_Y = 100.0
TAIL_SADDLE_THICK = 20.0

# Seats: on the post axis, SEAT_AXIS_HEIGHT above the base top. The body seat
# is the post's turned body; the tail seat carries the raw bar the tail is
# left at (cone-plan stock component "body", dia_mm 44.45).
SEAT_AXIS_HEIGHT = -BASE_TOP_Z
BODY_SEAT_DIA = post.BLOCK_DIA
TAIL_SEAT_DIA = 44.45
SEAT_OVERRUN = 1.0  # each seat cut runs past both saddle faces
BED_HEIGHT = BASE_THICK + SEAT_AXIS_HEIGHT - BODY_SEAT_DIA / 2.0
if abs(BED_HEIGHT - 18.9945) > 1e-9:
    raise AssertionError("body seat bed height left the inventory's 18.9945")

# Pins: hardened O4 m6 dowels pressed into reamed holes in the base.
PIN_DIA = 4.0
PIN_RADIUS = PIN_DIA / 2.0

# Crank pins: vertical, under the crank sleeve's north face, at the crank
# socket's station from foot B.
CRANK_PIN_X = 6.0
CRANK_PIN_Y = post.CRANK_BORE_HEIGHT
CRANK_PIN_TOP_Z = -post.CRANK_BOSS_NORTH_FACE
CRANK_PIN_HEIGHT = CRANK_PIN_TOP_Z - BASE_TOP_Z
if abs(round(CRANK_PIN_HEIGHT, 2) - 8.62) > 1e-9:
    raise AssertionError("crank pin height left the plan's 8.62")

# Cone pins: tilted with the cone journal, axis n = (sin i, 0, cos i), the
# reverse of the post's north-cap normal. One either side of the journal
# station; their square tops lie in the north-cap plane, CONE_BOSS_LENGTH / 2
# below the journal centre along n. A pin reaches CONE_PIN_LENGTH from its
# top down n, into the base.
CONE_PIN_OFFSET = 5.0
CONE_PIN_NEAR_Y = post.BORE_HEIGHT - CONE_PIN_OFFSET
CONE_PIN_FAR_Y = post.BORE_HEIGHT + CONE_PIN_OFFSET
CONE_PIN_LENGTH = 18.0
_INCLINE = math.radians(post.INCLINE_DEG)
CONE_PIN_AXIS = (math.sin(_INCLINE), 0.0, math.cos(_INCLINE))
_NORTH_CAP = post.SURFACE_FINISHES[3].face
if any(abs(a + c) > 1e-12 for a, c in zip(CONE_PIN_AXIS, _NORTH_CAP.normal, strict=True)):
    raise AssertionError("cone pin axis is not square to the post's north cap")
CONE_PIN_TOP_S = -post.CONE_BOSS_LENGTH / 2.0
if abs(-CONE_PIN_TOP_S - _NORTH_CAP.offset_mm) > 1e-9:
    raise AssertionError("cone pin tops left the post's north-cap plane")
CONE_PIN_TOP_X = CONE_PIN_TOP_S * math.sin(_INCLINE)
CONE_PIN_TOP_Z = CONE_PIN_TOP_S * math.cos(_INCLINE)
CONE_PIN_BOTTOM_S = CONE_PIN_TOP_S - CONE_PIN_LENGTH
# Where the pin axis enters the base top: the reamed hole's position.
CONE_PIN_ENTRY_S = BASE_TOP_Z / math.cos(_INCLINE)
CONE_PIN_ENTRY_X = CONE_PIN_ENTRY_S * math.sin(_INCLINE)
# The high (-X) edge of the tilted top, where the height gauge reads it.
CONE_PIN_HIGH_EDGE_X = CONE_PIN_TOP_X - PIN_RADIUS * math.cos(_INCLINE)
CONE_PIN_HIGH_EDGE_Z = CONE_PIN_TOP_Z + PIN_RADIUS * math.sin(_INCLINE)
CONE_PIN_HIGH_EDGE_HEIGHT = CONE_PIN_HIGH_EDGE_Z - BASE_TOP_Z
CONE_PIN_CENTRE_HEIGHT = CONE_PIN_TOP_Z - BASE_TOP_Z
if (
    abs(CONE_PIN_TOP_X + 4.552936) > 1e-5
    or abs(CONE_PIN_TOP_Z + 20.506141) > 1e-5
    or abs(round(CONE_PIN_HIGH_EDGE_HEIGHT, 2) - 9.93) > 1e-9
    or abs(round(CONE_PIN_CENTRE_HEIGHT, 2) - 9.49) > 1e-9
):
    raise AssertionError("cone pin top left the inventory's tilted-top station")
# The pin's bottom end stays inside the base plate.
_BOTTOM_Z = CONE_PIN_BOTTOM_S * math.cos(_INCLINE)
_BOTTOM_HALF_DROP = PIN_RADIUS * math.sin(_INCLINE)
if not (
    BASE_TOP_Z - BASE_THICK < _BOTTOM_Z - _BOTTOM_HALF_DROP
    and _BOTTOM_Z + _BOTTOM_HALF_DROP < BASE_TOP_Z
):
    raise AssertionError("cone pin end leaves the base plate")

# Layout datum: every transverse (X) location prints from the base's west
# side face, a physical face the shop can square from, never from the post
# axis. Stations (Y) print from foot B; heights from the base top.
SIDE_W_X = -BASE_WIDTH / 2.0
SEAT_AXIS_FROM_SIDE = -SIDE_W_X
STOP_SIDE_OFFSET = (BASE_WIDTH - STOP_WIDTH) / 2.0
SADDLE_SIDE_OFFSET = (BASE_WIDTH - SADDLE_WIDTH) / 2.0
CRANK_PIN_WEST_FROM_SIDE = -CRANK_PIN_X - SIDE_W_X
CRANK_PIN_EAST_FROM_SIDE = CRANK_PIN_X - SIDE_W_X
CONE_PIN_ENTRY_FROM_SIDE = CONE_PIN_ENTRY_X - SIDE_W_X

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BaseProfile": {"BaseThick", "BaseLength"},
    "Base": {"BaseWidth"},
    "StopProfile": {"StopHeight", "StopThick"},
    "Stop": {"StopWidth"},
    "SaddlesProfile": {
        "BodySaddleHeight",
        "BodySaddleThick",
        "BodySaddleY",
        "TailSaddleHeight",
        "TailSaddleThick",
        "TailSaddleY",
    },
    "Saddles": {"SaddleWidth"},
    "BodySeatProfile": {"BodySeatDia"},
    "TailSeatProfile": {"TailSeatDia"},
    "CrankPinProfile": {"CrankPinY", "CrankPinDia"},
    "CrankPins": {"CrankPinHeight"},
    "PlanReference": {
        "ConePinNearY",
        "ConePinFarY",
        "StopSideX",
        "SaddleSideX",
        "CrankPinWestX",
        "CrankPinEastX",
    },
    "ConePinSectionReference": {
        "BodySeatAxisX",
        "BodySeatAxisHeight",
        "ConePinEntryX",
        "ConePinTilt",
        "ConePinHighEdge",
    },
    "TailSeatReference": {"TailSeatAxisX", "TailSeatAxisHeight"},
}
# One place for the plates and blocks, the crank pins' transverse spots and
# the seats' centring and axis heights: nothing locates on them closer than
# the .X band. The body seat prints at the post body's own places
# (MainBodyDia) and the crank pin station at the crank axis's (CrankAxisY).
# The tail seat, the cone pins' stations, hole entry and the pin heights take
# two: the pins set each sleeve against the post. The cone pin tilt prints to
# a tenth of a degree under the general angular band. The pin diameter names
# the stock dowel; the press fit is the reamed hole's job (DRAWING_NOTES),
# not a printed limit.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BaseProfile": {"BaseThick": 1, "BaseLength": 1},
    "Base": {"BaseWidth": 1},
    "StopProfile": {"StopHeight": 1, "StopThick": 1},
    "Stop": {"StopWidth": 1},
    "SaddlesProfile": {
        "BodySaddleHeight": 1,
        "BodySaddleThick": 1,
        "BodySaddleY": 1,
        "TailSaddleHeight": 1,
        "TailSaddleThick": 1,
        "TailSaddleY": 1,
    },
    "Saddles": {"SaddleWidth": 1},
    "BodySeatProfile": {"BodySeatDia": post.DRAWING_PRECISION_BY_NAME["MainBodyDia"]},
    "TailSeatProfile": {"TailSeatDia": 2},
    "CrankPinProfile": {
        "CrankPinY": post.DRAWING_PRECISION_BY_NAME["CrankAxisY"],
        "CrankPinDia": 1,
    },
    "CrankPins": {"CrankPinHeight": 2},
    "PlanReference": {
        "ConePinNearY": 2,
        "ConePinFarY": 2,
        "StopSideX": 1,
        "SaddleSideX": 1,
        "CrankPinWestX": 1,
        "CrankPinEastX": 1,
    },
    "ConePinSectionReference": {
        "BodySeatAxisX": 1,
        "BodySeatAxisHeight": 1,
        "ConePinEntryX": 2,
        "ConePinTilt": 1,
        "ConePinHighEdge": 2,
    },
    "TailSeatReference": {"TailSeatAxisX": 1, "TailSeatAxisHeight": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked bond-cradle dimension needs authored places")

# Construction-only sketches the part saves hidden; the drawing shows them in
# the views that print their dimensions (_drawing_hidden_sketches). The two
# section sketches lie in their cutting planes: A-A through the near cone
# pin, B-B between the crank pins and the tail saddle, so B-B looks on to the
# tail saddle's south face, uncut, and its seat arc is a model edge.
TAIL_SECTION_Y = (CRANK_PIN_Y + TAIL_SADDLE_Y) / 2.0
REFERENCE_SKETCHES = ("PlanReference", "ConePinSectionReference", "TailSeatReference")
SECTION_REFERENCE_SKETCHES = ("ConePinSectionReference", "TailSeatReference")

# The seats MUST be cut (the title block's surface row is CAST/MACHINED, not
# a grade): the post lies in them. Nothing runs on them, so they take the
# static seat grade.
SURFACE_FINISHES = (
    SurfaceFinishControl("body_seat", SEAT_UM, CylinderFace(BODY_SEAT_DIA)),
    SurfaceFinishControl("tail_seat", SEAT_UM, CylinderFace(TAIL_SEAT_DIA)),
)
BUILT_UP_PERMISSION_NOTE = "BASE, STOP AND SADDLES MAY BE SCREWED AND DOWELED BLOCKS."
DRAWING_NOTES = "\n".join(
    (
        BUILT_UP_PERMISSION_NOTE,
        "PINS ARE STOCK HARDENED DOWELS; PIN ENDS STAY INSIDE THE BASE.",
        "REAM PIN HOLES THRU FOR A PRESS FIT; A PRESSED PIN MUST NOT TURN.",
        "PIN HEIGHTS FROM THE BASE TOP; CONE PINS AT THE HIGH EDGE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

_POST = "dt_cone_pivot_post_spec"
_UP = ([0.0, 0.0, 1.0], ("__frame__",))
_POST_AXIS = ([0.0, 1.0, 0.0], ("__frame__",))


def _crank_pin(x: float) -> ExportFeature:
    return ExportFeature(
        kind="pin",
        faces=(
            CylinderFace(PIN_DIA, contains_x_mm=x, contains_y_mm=CRANK_PIN_Y),
            PlanarFace((0.0, 0.0, 1.0), CRANK_PIN_TOP_Z, contains_x_mm=x),
        ),
        requirements=("height", "station"),
        fields={
            "at": ([x, CRANK_PIN_Y, CRANK_PIN_TOP_Z], ("CRANK_PIN_X", "CRANK_PIN_Y", "CRANK_PIN_TOP_Z")),
            "axis": _UP,
            "height": (
                limits(CRANK_PIN_HEIGHT, DRAWING_PRECISION_BY_NAME["CrankPinHeight"]),
                ("CRANK_PIN_HEIGHT", (_POST, "CRANK_BOSS_NORTH_FACE"), "BASE_TOP_Z"),
            ),
            "height_nominal": (CRANK_PIN_HEIGHT, ("CRANK_PIN_HEIGHT",)),
            "station": (
                limits(CRANK_PIN_Y, DRAWING_PRECISION_BY_NAME["CrankPinY"]),
                ("CRANK_PIN_Y", (_POST, "CRANK_BORE_HEIGHT")),
            ),
            "dia_nominal": (PIN_DIA, ("PIN_DIA",)),
        },
        precision={
            "height": DRAWING_PRECISION_BY_NAME["CrankPinHeight"],
            "station": DRAWING_PRECISION_BY_NAME["CrankPinY"],
        },
    )


def _cone_pin(y: float, y_name: str) -> ExportFeature:
    return ExportFeature(
        kind="pin",
        faces=(CylinderFace(PIN_DIA, contains_y_mm=y),),
        requirements=("height", "station", "angle_deg"),
        fields={
            "at": (
                [CONE_PIN_TOP_X, y, CONE_PIN_TOP_Z],
                ("CONE_PIN_TOP_X", y_name, "CONE_PIN_TOP_Z", (_POST, "CONE_BOSS_LENGTH")),
            ),
            "axis": (list(CONE_PIN_AXIS), ("CONE_PIN_AXIS", (_POST, "INCLINE_DEG"))),
            "height": (
                limits(CONE_PIN_HIGH_EDGE_HEIGHT, DRAWING_PRECISION_BY_NAME["ConePinHighEdge"]),
                (
                    "CONE_PIN_HIGH_EDGE_HEIGHT",
                    (_POST, "CONE_BOSS_LENGTH"),
                    (_POST, "INCLINE_DEG"),
                    "BASE_TOP_Z",
                ),
            ),
            "height_nominal": (CONE_PIN_HIGH_EDGE_HEIGHT, ("CONE_PIN_HIGH_EDGE_HEIGHT",)),
            "station": (
                limits(y, DRAWING_PRECISION_BY_NAME["ConePinNearY"]),
                (y_name, (_POST, "BORE_HEIGHT")),
            ),
            "angle_deg": (post.INCLINE_DEG, ((_POST, "INCLINE_DEG"),)),
            "dia_nominal": (PIN_DIA, ("PIN_DIA",)),
        },
        precision={
            "height": DRAWING_PRECISION_BY_NAME["ConePinHighEdge"],
            "station": DRAWING_PRECISION_BY_NAME["ConePinNearY"],
        },
    )


EXPORT_FEATURES: dict[str, ExportFeature] = {
    "body_seat": ExportFeature(
        kind="seat",
        faces=(CylinderFace(BODY_SEAT_DIA),),
        requirements=("dia", "height"),
        fields={
            "at": ([0.0, BODY_SADDLE_Y, 0.0], ("BODY_SADDLE_Y", "__frame__")),
            "axis": _POST_AXIS,
            "dia": (
                limits(BODY_SEAT_DIA, DRAWING_PRECISION_BY_NAME["BodySeatDia"]),
                ("BODY_SEAT_DIA", (_POST, "BLOCK_DIA")),
            ),
            "dia_nominal": (BODY_SEAT_DIA, ("BODY_SEAT_DIA", (_POST, "BLOCK_DIA"))),
            "height": (
                limits(SEAT_AXIS_HEIGHT, DRAWING_PRECISION_BY_NAME["BodySeatAxisHeight"]),
                ("SEAT_AXIS_HEIGHT", "BASE_TOP_Z"),
            ),
            "height_nominal": (SEAT_AXIS_HEIGHT, ("SEAT_AXIS_HEIGHT",)),
        },
        precision={
            "dia": DRAWING_PRECISION_BY_NAME["BodySeatDia"],
            "height": DRAWING_PRECISION_BY_NAME["BodySeatAxisHeight"],
        },
    ),
    "tail_seat": ExportFeature(
        kind="seat",
        faces=(CylinderFace(TAIL_SEAT_DIA),),
        requirements=("dia",),
        fields={
            "at": ([0.0, TAIL_SADDLE_Y, 0.0], ("TAIL_SADDLE_Y", "__frame__")),
            "axis": _POST_AXIS,
            "dia": (
                limits(TAIL_SEAT_DIA, DRAWING_PRECISION_BY_NAME["TailSeatDia"]),
                ("TAIL_SEAT_DIA",),
            ),
            "dia_nominal": (TAIL_SEAT_DIA, ("TAIL_SEAT_DIA",)),
        },
        precision={"dia": DRAWING_PRECISION_BY_NAME["TailSeatDia"]},
    ),
    "foot_stop": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 1.0, 0.0), 0.0),),
        requirements=("plane",),
        fields={
            "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
            "thickness": (
                limits(STOP_THICK, DRAWING_PRECISION_BY_NAME["StopThick"]),
                ("STOP_THICK",),
            ),
            "thickness_nominal": (STOP_THICK, ("STOP_THICK",)),
        },
        precision={"thickness": DRAWING_PRECISION_BY_NAME["StopThick"]},
    ),
    "base_top": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), BASE_TOP_Z),),
        requirements=("thickness",),
        fields={
            "normal": _UP,
            "plane": ({"frame": "model", "axis": "z", "value": BASE_TOP_Z}, ("BASE_TOP_Z",)),
            "thickness": (
                limits(BASE_THICK, DRAWING_PRECISION_BY_NAME["BaseThick"]),
                ("BASE_THICK",),
            ),
            "thickness_nominal": (BASE_THICK, ("BASE_THICK",)),
        },
        precision={"thickness": DRAWING_PRECISION_BY_NAME["BaseThick"]},
    ),
    "crank_pin_west": _crank_pin(-CRANK_PIN_X),
    "crank_pin_east": _crank_pin(CRANK_PIN_X),
    "cone_pin_near": _cone_pin(CONE_PIN_NEAR_Y, "CONE_PIN_NEAR_Y"),
    "cone_pin_far": _cone_pin(CONE_PIN_FAR_Y, "CONE_PIN_FAR_Y"),
}
