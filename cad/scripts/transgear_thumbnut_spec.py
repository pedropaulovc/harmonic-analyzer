r"""MHA-126 transgear-thumbnut: the knurled brass nut on the knob shaft's stud.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The nut runs on the 1/4-20 stud of the knob shaft (MHA-078) and
clamps the removable chain wheel (MHA-081, T24) against the drive collar
(MHA-177): its rear face bears on the wheel's front face only, round the
wheel's Ø10.3 bore.  Contract §1.6 (round 10): knurled head Ø20.5 × 8.7 with a
dished front face (chord 15, sagitta 1.2), a Ø11 waist × 2.4 (ruling 5), a
Ø12.4 flange to the seat face, 16.1 long, 1/4-20 UNC-2B through with an
entry countersink at each end.  The stud's side of the engagement (tip
station, tip chamfer, cut-to-fit) is MHA-078's; this module owns only the
nut's side of it.

Part frame: axis local +Y through the origin (``Axis1``, Front Plane ∩ Right
Plane).  The seat face -- the flange's rear face, the one that bears on the
T24 -- is the Top Plane, y = 0; the rim of the dished front face is the
``RimFace`` plane, y = OVERALL_LENGTH; the dish floor on the axis is the
``DishFloor`` plane, y = OVERALL_LENGTH - DISH_DEPTH.  The paper-drive
assembly maps local +Y to machine -Z (the nut's rim faces the machine
front), mates ``Axis1`` to the knob axis and the Top Plane to the T24's
front face.  The knurl's crests lie on the Front Plane, so the axial section
through it cuts two crests.
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from transgear_removable_spec import BORE_DIA as T24_BORE_DIA

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
# Dished front face: a spherical cap cut into the head, centre on the axis.
DISH_DIA = 15.0  # chord at the rim
DISH_DEPTH = 1.2  # sagitta, rim to the floor on the axis
DISH_RADIUS = ((DISH_DIA / 2.0) ** 2 + DISH_DEPTH**2) / (2.0 * DISH_DEPTH)


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
        f"MHA-126 knurl {KNURL_TEETH}T Ø{HEAD_DIA}/Ø{KNURL_ROOT_DIA} (pitch "
        f"{KNURL_CREST_PITCH:.3f}, {KNURL_TOOTH_ANGLE_DEG:.1f}° V) is not "
        f"{KNURL_DESIGNATION}"
    )

# --- Stations along the axis (local y) ----------------------------------------
SEAT_FACE_Y = 0.0
HEAD_REAR_Y = OVERALL_LENGTH - HEAD_LENGTH
RIM_Y = OVERALL_LENGTH
DISH_FLOOR_Y = OVERALL_LENGTH - DISH_DEPTH


def dish_surface_y(radius: float) -> float:
    """Local y of the dished face at ``radius`` from the axis."""
    if not 0.0 <= radius <= DISH_DIA / 2.0 + 1e-9:
        raise ValueError(f"radius {radius} is off the dish")
    return DISH_FLOOR_Y + DISH_RADIUS - math.sqrt(DISH_RADIUS**2 - radius**2)


# --- Thread (contract §1.6, §7) -----------------------------------------------
THREAD = "1/4-20"
TAP_SPEC = HoleSpec("tapped", THREAD)  # UNC-2B, through all
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]
# The smallest 1/4-20 UNC-2B minor diameter, 0.1960 in, ASME B1.1 as tabled
# by Engineers Edge (read 2026-10-01,
# https://www.engineersedge.com/thread_strength/internal_screw_threads_chart.htm):
# where the nut stands over MHA-078's thread relief its crests clear it.
TAP_MINOR_2B_MIN = 0.1960 * 25.4  # 4.978
# 90° entry countersink at each end, 0.2 deep at the thread major: the first
# full thread starts 0.2 in from the seat face.  The sheet prints the
# countersink as a MAX so the thread it removes never exceeds the 0.2 the
# engagement stack (contract §7) deducts.
CSK_DEPTH = 0.2
CSK_DIA = THREAD_MAJOR + 2.0 * CSK_DEPTH
if CSK_DIA <= THREAD_MAJOR:
    raise AssertionError("MHA-126 countersink ends inside the thread major")
CSK_QUALIFIER = f"90\u00b0 CSK \u00d8{CSK_DIA:.2f} MAX BOTH ENDS"
# Rear countersink: a 45° break on the tap-drill edge of the seat face, its
# cone y = CSK_DIA / 2 - r.  Front: the same Ø at the dished face, its cone
# y = FRONT_CSK_APEX_Y + r.
REAR_CSK_BREAK = (CSK_DIA - TAP_DRILL_DIA) / 2.0
REAR_CSK_APEX_Y = CSK_DIA / 2.0
FRONT_CSK_APEX_Y = dish_surface_y(CSK_DIA / 2.0) - CSK_DIA / 2.0
# First full thread (at the major) from each end.
REAR_FULL_THREAD_Y = REAR_CSK_APEX_Y - THREAD_MAJOR / 2.0
FRONT_FULL_THREAD_Y = FRONT_CSK_APEX_Y + THREAD_MAJOR / 2.0

# --- Places each printed dimension carries (policy rule 12, contract §12) ----
# The diameters over the thread at .XX (walls); the overall length, the
# knurl, the head length, the waist length and the dish at .X.  The stud is
# cut to fit the nut's rim at assembly, so the engagement stack takes the
# shortest .X nut (transgear_drive_collar_spec.thumbnut_engagement).
HEAD_DIA_PLACES = 1
HEAD_LENGTH_PLACES = 1
OVERALL_LENGTH_PLACES = 1
FLANGE_DIA_PLACES = 2
WAIST_DIA_PLACES = 2
WAIST_LENGTH_PLACES = 1
DISH_DIA_PLACES = 1
DISH_DEPTH_PLACES = 1

WALL_FLOOR = 2.0
# A tap cuts up to 0.05 over the basic major: half of it on a wall.
_TAP_OVERSIZE_R = 0.025
_DRILL_OVERSIZE = drilled_oversize_mm()

_HEAD_LO, _ = printed_deviations(HEAD_DIA, HEAD_DIA_PLACES)
_HEAD_LEN_LO, _ = printed_deviations(HEAD_LENGTH, HEAD_LENGTH_PLACES)
_WAIST_LO, _ = printed_deviations(WAIST_DIA, WAIST_DIA_PLACES)
_FLANGE_LO, _ = printed_deviations(FLANGE_DIA, FLANGE_DIA_PLACES)
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
            f"MHA-126 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under the {WALL_FLOOR} floor"
        )

# --- The seat on the T24 -------------------------------------------------------
# The seat face covers the wheel's drilled bore all round (radial overlap),
# so the nut clamps the wheel's front face and never enters its bore.
SEAT_OVERLAP = (FLANGE_DIA - T24_BORE_DIA) / 2.0
SEAT_OVERLAP_WORST = (
    (FLANGE_DIA + _FLANGE_LO) - (T24_BORE_DIA + _DRILL_OVERSIZE)
) / 2.0
if SEAT_OVERLAP_WORST <= 0.0:
    raise AssertionError("MHA-126 seat face no longer covers the T24's bore")
# The rear countersink stays inside the seat annulus' inner edge.
if CSK_DIA >= T24_BORE_DIA:
    raise AssertionError("MHA-126 rear countersink reaches the T24's bore edge")

# --- The nut's side of the stud engagement (contract §7) ----------------------
# The stack subtracts the rear countersink's thread loss (CSK_DEPTH, a MAX on
# the sheet) and, after cut-to-fit, the nut's shortest printed length.  The
# stud's tip station and chamfer are MHA-078's.
REAR_THREAD_LOSS = CSK_DEPTH

# The Ø20.5 dimension is the diameter over the knurl; the designation gives
# the pitch and the 90° tooth, so no tooth count prints (R9-57).
KNURL_CALLOUT = f"STRAIGHT KNURL {KNURL_DESIGNATION}\nDIA OVER KNURL"

# No roughness symbol: the seat face clamps the wheel (a clamp face, not a
# running, sliding or locating surface; policy rule 5).

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The head profile carries the knurl
# diameter, the head length and the overall length from the seat face; the
# stem profile the flange and waist diameters and the waist length (the
# flange length is the remainder); the dish its chord and depth.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadLength", "OverallLength"},
    "StemProfile": {"FlangeDia", "WaistDia", "WaistLength"},
    "DishProfile": {"DishDia", "DishDepth"},
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
        "DishDepth": DISH_DEPTH_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
