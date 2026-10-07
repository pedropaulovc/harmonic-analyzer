r"""Pure-data contract for the cone pivot post's saw cradle (MHA-DT-005-TL-02).

This is a shop fixture, not a machine part (cad/docs/subsystem-identities.md). In
the built-up cone post's saw setup (prechips S10) the post lies in the cradle's
two saddle seats with its cone cross-bore vertical. The cone sleeve's north cap
rests on the pad between the saddles. The cap-bridge clamp's two studs thread
into the base, and the bandsaw vise grips the base. The bridge load runs down the
cone sleeve onto the pad, never through the bonded joint.

The cradle is one piece: a milled 1018 block whose seats are bored on one
axis through both saddles. The pad top is a matched fit: it is left proud
and milled down to suit the identified post until its cap bears with the
body seated, because the post prints its body diameter and cap-to-cap boss
length independently. The inventory's screwed and doweled saddles are not a
permitted route.

Frame: model axes are the inventory's saw-cradle frame (cone plan frame B6:
post axis along -X, head top X0, cone cross-bore +Z up), re-based to a
touchable corner and turned Y-up for ASME views. The mapping is

    model X = B6 X - 2      (the base's kerf-side end face, B6 X2)
    model Y = B6 Z + 49     (the base underside, B6 Z-49)
    model Z = 50 - B6 Y     (the base side face at B6 Y+50)

so a nominal post's axis lies on model Y49, Z50, the seat bottoms on model
Y27.9945, and the cone axis at model X50.632. Z stations and Z heights run
from the base side face (model Z0).
"""

from __future__ import annotations

import math

import _config
import dt_cone_pivot_post_spec as post
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import THREAD_MAJOR_MM, TAP_DRILL_MM, HoleSpec
from _printed_tolerance import printed_band_mm

# --- Frame (B6 -> model) -------------------------------------------------------
B6_X_AT_END = 2.0
B6_Z_AT_UNDERSIDE = -49.0
B6_Y_AT_SIDE = 50.0

# --- Base: the vise grips its long sides; the studs thread into it ------------
BASE_LENGTH = 95.0
BASE_WIDTH = 100.0
BASE_HT = 19.0

# --- Saddles: two blocks on the base, bored together for the post body --------
OVERALL_HT = 39.0
HEAD_SADDLE_X = (26.5, 39.5)
FOOT_SADDLE_X = (64.0, 78.0)
SADDLE_Z = (26.0, 74.0)
# The head saddle sits on the body between the head shoulder and the cone
# boss; it is narrowed from the inventory's 14 so its widest .X print still
# fits the narrowest gap the post's print allows (below).
SADDLE_X_PLACES = 1

# The cone axis crosses the post axis BORE_HEIGHT above foot B; B6 X0 is the
# head top, BLOCK_HEIGHT above the foot.
CONE_AXIS_X = post.BLOCK_HEIGHT - post.BORE_HEIGHT - B6_X_AT_END
POST_AXIS_Z = B6_Y_AT_SIDE

# --- Seats -------------------------------------------------------------------
# The post body prints at .X. A seat at least as large as the largest body
# lets every body bottom on the seat's lowest line, which stays where a nominal
# body's underside is. A smaller seat would carry a large body on its lips.
SEAT_PLACES = 1
BODY_DIA_MAX = limits(post.BLOCK_DIA, post.DRAWING_PRECISION_BY_NAME["MainBodyDia"])[1]
SEAT_DIA = 43.6
if limits(SEAT_DIA, SEAT_PLACES)[0] < BODY_DIA_MAX - 1e-9:
    raise AssertionError("the smallest saw-cradle seat is smaller than the largest post body")
SEAT_BOTTOM_Y = -B6_Z_AT_UNDERSIDE - post.BLOCK_DIA / 2.0
SEAT_CENTRE_Y = SEAT_BOTTOM_Y + SEAT_DIA / 2.0
SEAT_Z = POST_AXIS_Z

# --- North-cap pad -------------------------------------------------------------
# The cone boss is BLOCK_DIA long (post.CONE_BOSS_LENGTH), so a nominal cap lies
# in the body's tangent plane. The post prints the body diameter at .X and the
# boss length at .XX independently, so with the body seated a compliant cap
# stands anywhere within CAP_OFFSET_MAX of the seat bottoms: no printed pad
# height carries every post. The pad is a MATCHED FIT (policy rule 2): the
# model leaves it proud of every compliant cap over the seat-bottom band, its
# height prints as a reference size, and the callout names the mate and the
# acceptance.
# The pad is a land on the cone axis under the cap. Its X faces leave a
# quarter-inch cutter room to either saddle; its Z ends stop short of the
# bridge studs, and its length covers the largest printed cap at the post's
# worst float in the seat (checked below).
PAD_WIDTH = 8.0
PAD_LENGTH = 28.0
PAD_X = CONE_AXIS_X
PAD_X0 = PAD_X - PAD_WIDTH / 2.0
PAD_X1 = PAD_X + PAD_WIDTH / 2.0
PAD_Z = POST_AXIS_Z
PAD_Z0 = PAD_Z - PAD_LENGTH / 2.0
PAD_Z1 = PAD_Z + PAD_LENGTH / 2.0
POST_NUMBER = _config.parts("dt-cone-pivot-post")["number"]
# Narrow lines, so the block stands in the gap between the front and right views.
PAD_FIT_CALLOUT = f"FIT TO SUIT\n{POST_NUMBER}\nCONE PIVOT\nPOST: CAP\nBEARS WITH\nBODY SEATED"
_BODY_BAND = limits(post.BLOCK_DIA, post.DRAWING_PRECISION_BY_NAME["MainBodyDia"])
_BOSS_BAND = limits(post.CONE_BOSS_LENGTH, post.DRAWING_PRECISION_BY_NAME["ConeBossLen"])
# The cap face stands body/2 - boss/2 above the seat line of a seated body.
CAP_OFFSET_MAX = max(
    (_BODY_BAND[1] - _BOSS_BAND[0]) / 2.0, (_BOSS_BAND[1] - _BODY_BAND[0]) / 2.0
)
# AUTHOR'S CHOICE: half a millimetre of fitting stock over the highest cap.
PAD_FIT_STOCK_MIN = 0.5
PAD_HT = 30.0
# The unfitted top stands above the highest compliant cap: the seats bored
# high within their band, the cap at its farthest from the seat line.
PAD_FIT_STOCK_WORST = PAD_HT - (SEAT_BOTTOM_Y + printed_band_mm(1) + CAP_OFFSET_MAX)
if PAD_FIT_STOCK_WORST < PAD_FIT_STOCK_MIN:
    raise AssertionError("a compliant cap can stand above the unfitted pad")
if abs(post.CONE_BOSS_LENGTH - post.BLOCK_DIA) > 1e-9:
    raise AssertionError("the cone cap no longer lies in the post body's tangent plane")

# --- Cap-bridge stud taps (3/8-16 studs, inventory B6 Y+-30) --------------------
STUD_THREAD = "3/8-16"
STUD_TAP_SPEC = HoleSpec("tapped", STUD_THREAD)
STUD_TAP_DRILL = TAP_DRILL_MM[STUD_THREAD]
STUD_X = CONE_AXIS_X
STUD_Z = (POST_AXIS_Z - 30.0, POST_AXIS_Z + 30.0)
STUD_MIN_ENGAGEMENT_D = 1.5

# --- Print-worst checks ----------------------------------------------------------
WALL_FLOOR_MM = post.WEB_FLOOR_MM
_ROW1 = printed_band_mm(1)

# The head saddle lands on the body between the head shoulder and the cone
# boss. Its widest print fits the narrowest gap the post's print allows: the
# shoulder sits HeadHt below the top, which is MainBodyHt above the foot; the
# cone axis sits within its own band above the foot; the boss radius is .X.
_SADDLE_ROW = printed_band_mm(SADDLE_X_PLACES)
HEAD_SADDLE_WIDTH_MAX = (HEAD_SADDLE_X[1] + _SADDLE_ROW) - (HEAD_SADDLE_X[0] - _SADDLE_ROW)
HEAD_GAP_MIN = (
    (post.HEAD_BASE_Y - post.BORE_HEIGHT)
    - printed_band_mm(post.DRAWING_PRECISION_BY_NAME["HeadHt"])
    - printed_band_mm(post.DRAWING_PRECISION_BY_NAME["MainBodyHt"])
    - post.JOURNAL_AXIS_HEIGHT_TOLERANCE_MM
    - limits(post.CONE_BOSS_DIA, post.DRAWING_PRECISION_BY_NAME["ConeBossDia"])[1] / 2.0
)
if HEAD_SADDLE_WIDTH_MAX > HEAD_GAP_MIN:
    raise AssertionError("the head saddle can be wider than the post's shoulder-to-boss gap")


def _seat_lip_worst() -> float:
    """Narrowest saddle lip beside the seat at the saddle top, print-worst."""
    worst = math.inf
    for seat_r in ((SEAT_DIA - _ROW1) / 2.0, (SEAT_DIA + _ROW1) / 2.0):
        for bottom in (SEAT_BOTTOM_Y - _ROW1, SEAT_BOTTOM_Y + _ROW1):
            for top in (OVERALL_HT - _ROW1, OVERALL_HT + _ROW1):
                rise = bottom + seat_r - top
                half_chord = math.sqrt(seat_r**2 - rise**2) if abs(rise) < seat_r else 0.0
                lip = (SADDLE_Z[1] - SADDLE_Z[0]) / 2.0 - 2.0 * _ROW1 - half_chord
                worst = min(worst, lip)
    return worst


SEAT_LIP_WORST = _seat_lip_worst()
if SEAT_LIP_WORST < WALL_FLOOR_MM:
    raise AssertionError(f"saddle lip {SEAT_LIP_WORST:.3f} under the {WALL_FLOOR_MM} wall floor")

STUD_ENGAGEMENT_D_WORST = (BASE_HT - _ROW1) / THREAD_MAJOR_MM[STUD_THREAD]
if STUD_ENGAGEMENT_D_WORST < STUD_MIN_ENGAGEMENT_D:
    raise AssertionError("the stud taps carry less than 1.5D of full thread")

# The bridge studs stand beside the largest body without touching it.
STUD_BODY_CLEARANCE_WORST = (
    (STUD_Z[1] - SEAT_Z)
    - 2.0 * _ROW1
    - BODY_DIA_MAX / 2.0
    - THREAD_MAJOR_MM[STUD_THREAD] / 2.0
)
if STUD_BODY_CLEARANCE_WORST <= 0.0:
    raise AssertionError("a bridge stud can touch the post body")


def _stud_raised_clearance_worst() -> float:
    """Narrowest gap from a bridge stud's thread to the saddles or the pad.

    Each gap is measured in plan (X, Z) from the stud axis to the raised
    block's nearest face; both the stud station and the face take their
    one-place band, so each axis gap shrinks by two bands.
    """
    raised = (
        (HEAD_SADDLE_X, SADDLE_Z),
        (FOOT_SADDLE_X, SADDLE_Z),
        ((PAD_X0, PAD_X1), (PAD_Z0, PAD_Z1)),
    )
    worst = math.inf
    for z in STUD_Z:
        for (x0, x1), (z0, z1) in raised:
            dx = max(x0 - STUD_X, 0.0, STUD_X - x1)
            dz = max(z0 - z, 0.0, z - z1)
            dx = max(dx - 2.0 * _ROW1, 0.0) if dx > 0.0 else 0.0
            dz = max(dz - 2.0 * _ROW1, 0.0) if dz > 0.0 else 0.0
            worst = min(worst, math.hypot(dx, dz) - THREAD_MAJOR_MM[STUD_THREAD] / 2.0)
    return worst


STUD_RAISED_CLEARANCE_WORST = _stud_raised_clearance_worst()
if STUD_RAISED_CLEARANCE_WORST < WALL_FLOOR_MM:
    raise AssertionError(
        f"a bridge stud stands {STUD_RAISED_CLEARANCE_WORST:.3f} from a saddle or the pad"
    )

# The pad still carries the whole cap with the post at its worst float: the
# largest printed boss at the seat's widest float about the pad's narrowest
# print.
_CAP_RADIUS_MAX = limits(post.CONE_BOSS_DIA, post.DRAWING_PRECISION_BY_NAME["ConeBossDia"])[1] / 2.0
_POST_FLOAT_MAX = (limits(SEAT_DIA, SEAT_PLACES)[1] - limits(post.BLOCK_DIA, 1)[0]) / 2.0
PAD_CAP_COVER_WORST = (
    (PAD_LENGTH / 2.0 - 2.0 * _ROW1) - (_CAP_RADIUS_MAX + _POST_FLOAT_MAX + _ROW1)
)
if PAD_CAP_COVER_WORST < 0.0:
    raise AssertionError("the cone cap can overhang the pad")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BaseProfile": {"BaseLength", "BaseWidth"},
    "Base": {"BaseHt"},
    "SaddleProfile": {
        "HeadSaddleX0",
        "HeadSaddleX1",
        "FootSaddleX0",
        "FootSaddleX1",
        "OverallHt",
    },
    "Pad": {"PadHt"},
    "PadProfile": {"PadX0", "PadX1", "PadZ0", "PadZ1"},
    "ReliefProfile": {"SaddleZ0", "SaddleZ1"},
    "SeatProfile": {"SeatZ", "SeatBottomHt", "SeatDia"},
    "StudTaps": {"StudX", "StudNearZ", "StudFarZ"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BaseProfile": {"BaseLength": 1, "BaseWidth": 1},
    "Base": {"BaseHt": 1},
    "SaddleProfile": {
        "HeadSaddleX0": SADDLE_X_PLACES,
        "HeadSaddleX1": SADDLE_X_PLACES,
        "FootSaddleX0": SADDLE_X_PLACES,
        "FootSaddleX1": SADDLE_X_PLACES,
        "OverallHt": 1,
    },
    "Pad": {"PadHt": 1},
    "PadProfile": {"PadX0": 1, "PadX1": 1, "PadZ0": 1, "PadZ1": 1},
    "ReliefProfile": {"SaddleZ0": 1, "SaddleZ1": 1},
    "SeatProfile": {"SeatZ": 1, "SeatBottomHt": 1, "SeatDia": SEAT_PLACES},
    "StudTaps": {"StudX": 1, "StudNearZ": 1, "StudFarZ": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked saw-cradle dimension needs authored places")

SURFACE_FINISHES = ()
DRAWING_NOTES = "BOTH SEATS ON ONE COMMON AXIS."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

_POST = "dt_cone_pivot_post_spec"
_X_AXIS = ([1.0, 0.0, 0.0], ("__frame__",))
# Z heights (the stud stations across the base) run from the base side face.
_FROM_SIDE = ("side_face", ("__frame__",))


def _seat(x_span: tuple[float, float], name: str) -> ExportFeature:
    return ExportFeature(
        kind="hole",
        faces=(CylinderFace(SEAT_DIA, contains_x_mm=sum(x_span) / 2.0),),
        requirements=("dia", "length", "height", "process"),
        fields={
            "at": ([x_span[0], SEAT_CENTRE_Y, SEAT_Z], (name, "SEAT_CENTRE_Y", "SEAT_Z")),
            "axis": _X_AXIS,
            "dia": (
                limits(SEAT_DIA, SEAT_PLACES),
                ("SEAT_DIA", "BODY_DIA_MAX", (_POST, "BLOCK_DIA")),
            ),
            "nominal_dia": (SEAT_DIA, ("SEAT_DIA",)),
            "length": (
                [x_span[1] - x_span[0] - 2.0 * _SADDLE_ROW, x_span[1] - x_span[0] + 2.0 * _SADDLE_ROW],
                (name,),
            ),
            "length_nominal": (x_span[1] - x_span[0], (name,)),
            "height": (
                limits(SEAT_BOTTOM_Y, 1),
                ("SEAT_BOTTOM_Y", (_POST, "BLOCK_DIA")),
            ),
            "height_nominal": (SEAT_BOTTOM_Y, ("SEAT_BOTTOM_Y",)),
            "thru": (True, (name,)),
            "process": ("bore", ("DRAWING_NOTES",)),
        },
        precision={"dia": SEAT_PLACES, "length": SADDLE_X_PLACES, "height": 1},
    )


def _stud(z: float) -> ExportFeature:
    return ExportFeature(
        kind="hole",
        faces=(CylinderFace(STUD_TAP_DRILL, contains_z_mm=z),),
        requirements=("thread", "station", "height"),
        fields={
            "at": ([STUD_X, BASE_HT, z], ("STUD_X", "BASE_HT", "STUD_Z")),
            "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "thread": (f"{STUD_THREAD} UNC-{STUD_TAP_SPEC.thread_class}", ("STUD_TAP_SPEC",)),
            "tap_drill_mm": (STUD_TAP_DRILL, ("STUD_TAP_DRILL",)),
            "thru": (True, ("STUD_TAP_SPEC",)),
            "station": (limits(STUD_X, 1), ("STUD_X",)),
            "station_nominal": (STUD_X, ("STUD_X",)),
            "height": (limits(z, 1), ("STUD_Z",)),
            "height_nominal": (z, ("STUD_Z",)),
            "height_from": _FROM_SIDE,
        },
        precision={"station": 1, "height": 1},
    )


EXPORT_FEATURES: dict[str, ExportFeature] = {
    "head_seat": _seat(HEAD_SADDLE_X, "HEAD_SADDLE_X"),
    "foot_seat": _seat(FOOT_SADDLE_X, "FOOT_SADDLE_X"),
    "cap_pad": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 1.0, 0.0), PAD_HT),),
        requirements=("note", "width", "length", "station", "process"),
        fields={
            "at": ([PAD_X, PAD_HT, PAD_Z], ("PAD_X", "PAD_HT", "PAD_Z")),
            "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": PAD_HT}, ("PAD_HT",)),
            # A matched fit: the reference height is the unfitted stock, and
            # the callout's acceptance, not a band, defines the fitted top.
            "height_nominal": (
                PAD_HT,
                ("PAD_HT", "PAD_FIT_STOCK_MIN", (_POST, "BLOCK_DIA"), (_POST, "CONE_BOSS_LENGTH")),
            ),
            "width": (
                [PAD_WIDTH - 2.0 * _ROW1, PAD_WIDTH + 2.0 * _ROW1],
                ("PAD_X0", "PAD_X1"),
            ),
            "width_nominal": (PAD_WIDTH, ("PAD_WIDTH",)),
            "length": (
                [PAD_LENGTH - 2.0 * _ROW1, PAD_LENGTH + 2.0 * _ROW1],
                ("PAD_Z0", "PAD_Z1"),
            ),
            "length_nominal": (PAD_LENGTH, ("PAD_LENGTH",)),
            "station": (limits(PAD_X, 1), ("PAD_X", (_POST, "BORE_HEIGHT"))),
            "station_nominal": (PAD_X, ("PAD_X",)),
            "process": ("mill", ("DRAWING_NOTES",)),
            "note": (PAD_FIT_CALLOUT, ("PAD_FIT_CALLOUT", "POST_NUMBER")),
        },
        precision={"width": 1, "length": 1, "station": 1},
    ),
    "underside": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
        requirements=("height",),
        fields={
            "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
            "height": (limits(OVERALL_HT, 1), ("OVERALL_HT",)),
            "height_nominal": (OVERALL_HT, ("OVERALL_HT",)),
        },
        precision={"height": 1},
    ),
    "side_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
        requirements=("plane",),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        },
    ),
    "stud_tap_near": _stud(STUD_Z[0]),
    "stud_tap_far": _stud(STUD_Z[1]),
}
