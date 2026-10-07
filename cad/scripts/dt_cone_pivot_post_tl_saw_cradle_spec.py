r"""Pure-data contract for the cone pivot post's saw cradle (MHA-DT-005-TL-02).

This is a shop fixture, not a machine part (cad/docs/subsystem-identities.md). In
the built-up cone post's saw setup (prechips S10) the post lies in the cradle's
two saddle seats with its cone cross-bore vertical. The cone sleeve's north cap
rests on the pad between the saddles. The cap-bridge clamp's two studs thread
into the base, and the bandsaw vise grips the base. The bridge load runs down the
cone sleeve onto the pad, never through the bonded joint.

Frame: model axes are the inventory's saw-cradle frame (cone plan frame B6:
post axis along -X, head top X0, cone cross-bore +Z up), re-based to a
touchable corner and turned Y-up for ASME views. The mapping is

    model X = B6 X - 2      (the base's kerf-side end face, B6 X2)
    model Y = B6 Z + 49     (the base underside, B6 Z-49)
    model Z = 50 - B6 Y     (the base side face at B6 Y+50)

so a nominal post's axis lies on model Y49, Z50, the seat bottoms and pad top
on model Y27.9945, and the cone axis at model X50.632.
"""

from __future__ import annotations

import math

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
# body's underside is: flush with the pad top under the cap. A smaller seat
# would carry a large body on its lips and lift the cap off the pad.
SEAT_PLACES = 1
BODY_DIA_MAX = limits(post.BLOCK_DIA, post.DRAWING_PRECISION_BY_NAME["MainBodyDia"])[1]
SEAT_DIA = 43.6
if limits(SEAT_DIA, SEAT_PLACES)[0] < BODY_DIA_MAX - 1e-9:
    raise AssertionError("the smallest saw-cradle seat is smaller than the largest post body")
SEAT_BOTTOM_Y = -B6_Z_AT_UNDERSIDE - post.BLOCK_DIA / 2.0
SEAT_CENTRE_Y = SEAT_BOTTOM_Y + SEAT_DIA / 2.0
SEAT_Z = POST_AXIS_Z

# --- North-cap pad -------------------------------------------------------------
# The cone boss is BLOCK_DIA long (post.CONE_BOSS_LENGTH), so its cap lies in
# the body's tangent plane: the pad top is flush with the seat bottoms.
# The pad is a land across the cone axis, trimmed to the saddles' width by the
# same cut, so its two X faces locate it; it leaves a quarter-inch cutter
# room on either side.
PAD_WIDTH = 8.0
PAD_X = CONE_AXIS_X
PAD_X0 = PAD_X - PAD_WIDTH / 2.0
PAD_X1 = PAD_X + PAD_WIDTH / 2.0
PAD_Z = POST_AXIS_Z
PAD_HT = SEAT_BOTTOM_Y
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
    "PadProfile": {"PadX0", "PadX1"},
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
    "PadProfile": {"PadX0": 1, "PadX1": 1},
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
BUILT_UP_PERMISSION_NOTE = "BUILT-UP CONSTRUCTION IS PERMITTED."
PAD_FLUSH_NOTE = "PAD TOP FLUSH WITH SEAT BOTTOMS."
DRAWING_NOTES = "\n".join(
    (
        "BOTH SEATS ON ONE COMMON AXIS.",
        PAD_FLUSH_NOTE,
        BUILT_UP_PERMISSION_NOTE,
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

_POST = "dt_cone_pivot_post_spec"
_X_AXIS = ([1.0, 0.0, 0.0], ("__frame__",))


def _seat(x_span: tuple[float, float], name: str) -> ExportFeature:
    return ExportFeature(
        kind="hole",
        faces=(CylinderFace(SEAT_DIA, contains_x_mm=sum(x_span) / 2.0),),
        requirements=("dia", "at", "process"),
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
        requirements=("thread", "at"),
        fields={
            "at": ([STUD_X, BASE_HT, z], ("STUD_X", "BASE_HT", "STUD_Z")),
            "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "thread": (f"{STUD_THREAD} UNC-{STUD_TAP_SPEC.thread_class}", ("STUD_TAP_SPEC",)),
            "tap_drill_mm": (STUD_TAP_DRILL, ("STUD_TAP_DRILL",)),
            "thru": (True, ("STUD_TAP_SPEC",)),
            "station": (limits(STUD_X, 1), ("STUD_X",)),
            "station_nominal": (STUD_X, ("STUD_X",)),
        },
        precision={"station": 1},
    )


EXPORT_FEATURES: dict[str, ExportFeature] = {
    "head_seat": _seat(HEAD_SADDLE_X, "HEAD_SADDLE_X"),
    "foot_seat": _seat(FOOT_SADDLE_X, "FOOT_SADDLE_X"),
    "cap_pad": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 1.0, 0.0), PAD_HT),),
        requirements=("height", "width", "process"),
        fields={
            "at": ([PAD_X, PAD_HT, PAD_Z], ("PAD_X", "PAD_HT", "PAD_Z")),
            "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": PAD_HT}, ("PAD_HT",)),
            "height": (
                limits(SEAT_BOTTOM_Y, 1),
                ("PAD_HT", "SEAT_BOTTOM_Y", (_POST, "BLOCK_DIA"), (_POST, "CONE_BOSS_LENGTH")),
            ),
            "height_nominal": (PAD_HT, ("PAD_HT",)),
            "width": (
                [PAD_WIDTH - 2.0 * _ROW1, PAD_WIDTH + 2.0 * _ROW1],
                ("PAD_X0", "PAD_X1"),
            ),
            "width_nominal": (PAD_WIDTH, ("PAD_WIDTH",)),
            "length": (
                [SADDLE_Z[1] - SADDLE_Z[0] - 2.0 * _ROW1, SADDLE_Z[1] - SADDLE_Z[0] + 2.0 * _ROW1],
                ("SADDLE_Z",),
            ),
            "station": (limits(PAD_X, 1), ("PAD_X", (_POST, "BORE_HEIGHT"))),
            "station_nominal": (PAD_X, ("PAD_X",)),
            "process": ("mill", ("DRAWING_NOTES",)),
            "note": (PAD_FLUSH_NOTE, ("DRAWING_NOTES",)),
        },
        precision={"height": 1, "width": 1, "length": 1, "station": 1},
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
    "stud_tap_near": _stud(STUD_Z[0]),
    "stud_tap_far": _stud(STUD_Z[1]),
}
