r"""MHA-PD-013 transgear-thumbnut: the knurled brass nut on the knob shaft's stud.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The nut runs on the 1/4-20 stud of the knob shaft (MHA-PD-008) and
seats on the drive collar's (MHA-PD-022) pilot, faced at assembly to stand
0.05-0.15 proud of the removable chain wheel's (MHA-PD-009, T24) front face, so
the wheel floats free under it (R9-70, N-A).  Contract §1.6 (round 10):
knurled head Ø20.5 × 8.7 with a dished front face (a cone from Ø15 at the
rim to a flat Ø9 floor 1.0 deep), a Ø11 waist × 2.4 (ruling 5), a Ø12.4
flange to the seat face, 16.1 long, 1/4-20 UNC-2B through with an entry
countersink at each end.  The stud's
side of the engagement (tip station, tip chamfer, cut-to-fit) is MHA-PD-008's;
this module owns only the nut's side of it.

Part frame: axis local +Y through the origin (``Axis1``, Front Plane ∩ Right
Plane).  The seat face -- the flange's rear face, the one that bears on the
collar's pilot -- is the Top Plane, y = 0; the rim of the dished front face
is the ``RimFace`` plane, y = OVERALL_LENGTH; the dish's flat floor is the
``DishFloor`` plane, y = OVERALL_LENGTH - DISH_DEPTH.  The paper-drive
assembly maps local +Y to machine -Z (the nut's rim faces the machine
front), mates ``Axis1`` to the knob axis and the Top Plane to the pilot's
front face.  The knurl's crests lie on the Front Plane, so the axial section
through it cuts two crests.
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import printed_deviations

# --- Turned outline (contract §1.6) -------------------------------------------
HEAD_DIA = 20.5  # knurl crests: the diameter over the knurl
HEAD_LENGTH = 8.7
# Straight knurl DIN 82 RAA 1.0 (R9-57): a 90° V at 1.0 pitch, so 64 teeth
# round the Ø20.5 (pitch 1.006 at the crest) and a 0.5 deep tooth; the
# sketch's 128-point star puts crests on HEAD_DIA, roots on KNURL_ROOT_DIA.
KNURL_TEETH = 64
KNURL_ROOT_DIA = 19.5
KNURL_DESIGNATION = "DIN 82-RAA 1.0"
KNURL_PITCH = 1.0
KNURL_FLANK_ANGLE_DEG = 90.0
WAIST_DIA = 11.0
WAIST_LENGTH = 2.4
FLANGE_DIA = 12.4
OVERALL_LENGTH = 16.1
FLANGE_LENGTH = OVERALL_LENGTH - HEAD_LENGTH - WAIST_LENGTH  # 5.0, not printed
# Dished front face: a conical recess from the rim's Ø down to a flat floor,
# centred on the axis; the front countersink is cut in that floor.  The
# machinist review of 6de7230aa found the earlier spherical cap (chord 15,
# sagitta 1.2 to a point on the axis inside the tap drill) ended on the
# countersink at no definite Ø: the floor gives the recess a definite inner
# edge and its depth a real surface.
DISH_DIA = 15.0  # at the rim
DISH_FLOOR_DIA = 9.0  # the floor's outer edge, where the cone ends
DISH_DEPTH = 1.0  # rim to the floor


def knurl_tooth_angle_deg(crest_dia: float, root_dia: float, teeth: int) -> float:
    """Included angle of one modelled tooth space: the V from a root to the
    two crests either side of it."""
    half = math.pi / teeth
    root = (root_dia / 2.0 * math.cos(half), root_dia / 2.0 * math.sin(half))
    flanks = [
        (
            crest_dia / 2.0 * math.cos(angle) - root[0],
            crest_dia / 2.0 * math.sin(angle) - root[1],
        )
        for angle in (0.0, 2.0 * half)
    ]
    (ax, ay), (bx, by) = flanks
    return math.degrees(
        math.acos((ax * bx + ay * by) / (math.hypot(ax, ay) * math.hypot(bx, by)))
    )


# The modelled knurl is the designated one: its crest pitch within 1 % of
# the wheel's (the wheel tracks the circumference), its V within 2° of 90°,
# and an even tooth count so the section plane cuts a crest on both sides.
KNURL_CREST_PITCH = math.pi * HEAD_DIA / KNURL_TEETH  # 1.006
KNURL_TOOTH_ANGLE_DEG = knurl_tooth_angle_deg(HEAD_DIA, KNURL_ROOT_DIA, KNURL_TEETH)
if (
    abs(KNURL_CREST_PITCH - KNURL_PITCH) > 0.01 * KNURL_PITCH
    or abs(KNURL_TOOTH_ANGLE_DEG - KNURL_FLANK_ANGLE_DEG) > 2.0
    or KNURL_TEETH % 2
):
    raise AssertionError(
        f"MHA-PD-013 knurl {KNURL_TEETH}T Ø{HEAD_DIA}/Ø{KNURL_ROOT_DIA} (pitch "
        f"{KNURL_CREST_PITCH:.3f}, {KNURL_TOOTH_ANGLE_DEG:.1f}° V) is not "
        f"{KNURL_DESIGNATION}"
    )

# --- Stations along the axis (local y) ----------------------------------------
SEAT_FACE_Y = 0.0
HEAD_REAR_Y = OVERALL_LENGTH - HEAD_LENGTH
RIM_Y = OVERALL_LENGTH
DISH_FLOOR_Y = OVERALL_LENGTH - DISH_DEPTH
# The dish profile's two corners (radius from the axis, local y): the depth
# runs between them, from the rim's edge down to the floor's.
DISH_RIM_CORNER = (DISH_DIA / 2.0, RIM_Y)
DISH_FLOOR_CORNER = (DISH_FLOOR_DIA / 2.0, DISH_FLOOR_Y)


# --- Thread (contract §1.6, §7) -----------------------------------------------
THREAD = "1/4-20"
TAP_SPEC = HoleSpec("tapped", THREAD)  # UNC-2B, through all
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]
# The smallest 1/4-20 UNC-2B minor diameter, 0.1960 in, ASME B1.1 as tabled
# by Engineers Edge (read 2026-10-01,
# https://www.engineersedge.com/thread_strength/internal_screw_threads_chart.htm):
# where the nut stands over MHA-PD-008's thread relief its crests clear it.
TAP_MINOR_2B_MIN = 0.1960 * 25.4  # 4.978
# 90° entry countersink at each end, opened 0.2 past the thread major so the
# first thread starts full rather than on a feather edge.  The sheet prints
# it as a MAX, so the thread it removes never exceeds the losses below.
CSK_DIA = THREAD_MAJOR + 2.0 * 0.2
if CSK_DIA <= THREAD_MAJOR:
    raise AssertionError("MHA-PD-013 countersink ends inside the thread major")
CSK_QUALIFIER = f"90\u00b0 CSK \u00d8{CSK_DIA:.2f} MAX BOTH ENDS"
# Rear countersink: a 45° break on the tap-drill edge of the seat face, its
# cone y = CSK_DIA / 2 - r.  Front: the same break on the dish floor, its
# cone y = FRONT_CSK_APEX_Y + r.
REAR_CSK_BREAK = (CSK_DIA - TAP_DRILL_DIA) / 2.0
REAR_CSK_APEX_Y = CSK_DIA / 2.0
FRONT_CSK_APEX_Y = DISH_FLOOR_Y - CSK_DIA / 2.0
# First full thread from each end: where the cone meets the tap drill, not
# the major (R9-63).
REAR_FULL_THREAD_Y = REAR_CSK_APEX_Y - TAP_DRILL_DIA / 2.0
FRONT_FULL_THREAD_Y = FRONT_CSK_APEX_Y + TAP_DRILL_DIA / 2.0

# --- Places each printed dimension carries (policy rule 12, contract §12) ----
# The diameters over the thread at .XX (walls); the overall length, the
# knurl, the head length, the waist length and the dish at .X.  The stud is
# cut to fit the nut's rim at assembly, so the engagement stack takes the
# shortest .X nut (pd_transgear_drive_collar_spec.thumbnut_engagement).
HEAD_DIA_PLACES = 1
HEAD_LENGTH_PLACES = 1
OVERALL_LENGTH_PLACES = 1
FLANGE_DIA_PLACES = 2
WAIST_DIA_PLACES = 2
WAIST_LENGTH_PLACES = 1
DISH_DIA_PLACES = 1
DISH_FLOOR_DIA_PLACES = 1
DISH_DEPTH_PLACES = 1

WALL_FLOOR = 2.0
# A tap cuts up to 0.05 over the basic major: half of it on a wall.
_TAP_OVERSIZE_R = 0.025

_HEAD_LO, _ = printed_deviations(HEAD_DIA, HEAD_DIA_PLACES)
_HEAD_LEN_LO, _ = printed_deviations(HEAD_LENGTH, HEAD_LENGTH_PLACES)
_WAIST_LO, _ = printed_deviations(WAIST_DIA, WAIST_DIA_PLACES)
_FLANGE_LO, _ = printed_deviations(FLANGE_DIA, FLANGE_DIA_PLACES)
_DISH_LO, _ = printed_deviations(DISH_DIA, DISH_DIA_PLACES)
_DISH_FLOOR_LO, _DISH_FLOOR_HI = printed_deviations(
    DISH_FLOOR_DIA, DISH_FLOOR_DIA_PLACES
)
_DISH_DEPTH_LO, _DISH_DEPTH_HI = printed_deviations(DISH_DEPTH, DISH_DEPTH_PLACES)
OVERALL_LENGTH_LO, OVERALL_LENGTH_HI = printed_deviations(
    OVERALL_LENGTH, OVERALL_LENGTH_PLACES
)
_THREAD_R_MAX = THREAD_MAJOR / 2.0 + _TAP_OVERSIZE_R

# --- Walls at the printed worst case (contract §8) ----------------------------
# (nominal, worst).  The knurl root follows the head's band; the dish floor
# is solid round the thread (informational).
WALLS: dict[str, tuple[float, float]] = {
    "waist over the thread major": (
        (WAIST_DIA - THREAD_MAJOR) / 2.0,
        (WAIST_DIA + _WAIST_LO) / 2.0 - _THREAD_R_MAX,
    ),
    "flange over the thread major": (
        (FLANGE_DIA - THREAD_MAJOR) / 2.0,
        (FLANGE_DIA + _FLANGE_LO) / 2.0 - _THREAD_R_MAX,
    ),
    "knurl root over the thread major": (
        (KNURL_ROOT_DIA - THREAD_MAJOR) / 2.0,
        (KNURL_ROOT_DIA + _HEAD_LO) / 2.0 - _THREAD_R_MAX,
    ),
    "dish floor to the head's rear face": (
        HEAD_LENGTH - DISH_DEPTH,
        (HEAD_LENGTH + _HEAD_LEN_LO) - (DISH_DEPTH + _DISH_DEPTH_HI),
    ),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-PD-013 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under the {WALL_FLOOR} floor"
        )


def dish_floor_margins(
    dish_dia: float, floor_dia: float, depth: float, csk_dia: float
) -> dict[str, float]:
    """Worst-case margins (mm, each > 0 when it holds) that keep the dish
    ending on its own floor at every printed size: the floor's edge outside
    the front countersink's MAX, the cone running inward from the rim, and
    the floor below the rim."""
    floor_land = floor_dia + _DISH_FLOOR_LO - csk_dia
    cone_run = dish_dia + _DISH_LO - floor_dia - _DISH_FLOOR_HI
    return {
        "floor land outside the countersink": floor_land / 2.0,
        "cone from the rim to the floor": cone_run / 2.0,
        "floor below the rim": depth + _DISH_DEPTH_LO,
    }


# --- The dish ends on its floor ------------------------------------------------
# So the depth and the floor's Ø stay the recess's inner edge whatever size
# the countersink is cut, and the countersink sits on a flat face like the
# rear one.
DISH_FLOOR_MARGINS = dish_floor_margins(DISH_DIA, DISH_FLOOR_DIA, DISH_DEPTH, CSK_DIA)
for _name, _margin in DISH_FLOOR_MARGINS.items():
    if _margin <= 0.0:
        raise AssertionError(
            f"MHA-PD-013 dish: {_name} is {_margin:.3f} at the printed worst case"
        )

# --- The seat on the collar's pilot (R9-70) -------------------------------------
# The bearing annulus and the flange's cover over the pilot are MHA-PD-022's
# (``pd_transgear_drive_collar_spec``), which reads this module.

# --- The nut's side of the stud engagement (contract §7) ----------------------
# The stack subtracts the thread each countersink takes (at its printed MAX,
# from the seat face and from the rim, the front one on the dish floor at its
# deepest printed depth) and, after cut-to-fit, the nut's shortest printed
# length.  The stud's tip station and chamfer are MHA-PD-008's.
REAR_THREAD_LOSS = REAR_FULL_THREAD_Y - SEAT_FACE_Y  # 0.823
FRONT_THREAD_LOSS = RIM_Y - FRONT_FULL_THREAD_Y + _DISH_DEPTH_HI  # 2.623

# The Ø20.5 dimension is the diameter over the knurl; the designation gives
# the pitch and the 90° tooth, so no tooth count prints (R9-57).  One line:
# it prints in the dimension's above-callout compartment, and SolidWorks
# keeps a two-line above callout in the document but prints none of it (run
# 20261001T154021634Z: "...\nDIA OVER KNURL" read back over Ø20.5 and was
# missing from the PDF).
KNURL_CALLOUT = f"STRAIGHT KNURL {KNURL_DESIGNATION}; DIA OVER KNURL"

# No roughness symbol: the seat face clamps the wheel (a clamp face, not a
# running, sliding or locating surface; policy rule 5).

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The head profile carries the knurl
# diameter, the head length and the overall length from the seat face; the
# stem profile the flange and waist diameters and the waist length (the
# flange length is the remainder); the dish its rim and floor diameters and
# its depth from the rim's edge to the floor's.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadLength", "OverallLength"},
    "StemProfile": {"FlangeDia", "WaistDia", "WaistLength"},
    "DishProfile": {"DishDia", "DishFloorDia", "DishDepth"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {
        "HeadDia": HEAD_DIA_PLACES,
        "HeadLength": HEAD_LENGTH_PLACES,
        "OverallLength": OVERALL_LENGTH_PLACES,
    },
    "StemProfile": {
        "FlangeDia": FLANGE_DIA_PLACES,
        "WaistDia": WAIST_DIA_PLACES,
        "WaistLength": WAIST_LENGTH_PLACES,
    },
    "DishProfile": {
        "DishDia": DISH_DIA_PLACES,
        "DishFloorDia": DISH_FLOOR_DIA_PLACES,
        "DishDepth": DISH_DEPTH_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
