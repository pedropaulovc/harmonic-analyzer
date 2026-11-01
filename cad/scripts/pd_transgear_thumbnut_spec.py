r"""MHA-PD-13 transgear-thumbnut: the knurled brass nut on the knob shaft's stud.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  The nut runs on the #8-32 stud of the knob shaft (MHA-PD-08) and
seats on the drive collar's (MHA-PD-22) pilot, faced at assembly to stand
0.05-0.15 proud of the removable chain wheel's (MHA-PD-09, T24) front face, so
the wheel floats free under it (R9-70, N-A).  Contract §1.6 (round 10),
printed in decimal inch (#290): knurled head Ø.81 x .34 with a dished front
face (a cone from Ø.59 at the rim to a flat Ø.35 floor .04 deep), a Ø.43
waist x .09 (ruling 5), a Ø.49 flange to the seat face, .63 long, #8-32
UNC-2B through with an entry countersink at each end.  The stud's
side of the engagement (tip station, tip chamfer, cut-to-fit) is MHA-PD-08's;
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

import _config
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg, printed_deviations

# #290: the sheet prints decimal inch; every turned size below is the exact
# millimetre value of its printed .XX inch size.
UNIT = drawing_unit(
    "parts/pd-transgear-thumbnut", _config.parts("pd-transgear-thumbnut")
)
MM_PER_IN = 25.4

# --- Turned outline (contract §1.6) -------------------------------------------
HEAD_DIA = 20.574  # .81, knurl crests: the diameter over the knurl
# Straight knurl, 25 TPI with a 90° tooth: the inch wheel's pitch is stated
# in its own unit (machinist review round 2 found the metric "DIN 82-RAA 1.0"
# pitch unlabelled, and an inch sheet prints no mm).  64 teeth round the Ø.81
# (pitch 1.010 mm at the crest, 0.6 % off the wheel's 1.016) and a 0.5 mm
# deep tooth; the sketch's 128-point star puts crests on HEAD_DIA, roots on
# KNURL_ROOT_DIA.
KNURL_TEETH = 64
KNURL_ROOT_DIA = HEAD_DIA - 1.0  # 19.574, not printed
KNURL_TPI = 25
KNURL_DESIGNATION = f"{KNURL_TPI} TPI"  # the standard wheel's 90° tooth
KNURL_PITCH = MM_PER_IN / KNURL_TPI
KNURL_FLANK_ANGLE_DEG = 90.0
WAIST_DIA = 10.922  # .43
FLANGE_DIA = 12.446  # .49
OVERALL_LENGTH = 16.002  # .63
# The flange length and the head's rear face print from the faced seat face
# (drawing-guidelines.md rules 10 and 11), baseline with the overall length;
# the waist is the remainder between them, so it does not print.
FLANGE_LENGTH = 5.08  # .20
HEAD_REAR_Y = 7.366  # .29, the head's rear face from the seat face
HEAD_LENGTH = OVERALL_LENGTH - HEAD_REAR_Y  # 8.636 (.34), not printed
WAIST_LENGTH = HEAD_REAR_Y - FLANGE_LENGTH  # 2.286 (.09), not printed
# Dished front face: a conical recess from the rim's Ø down to a flat floor,
# centred on the axis; the front countersink is cut in that floor.  The
# machinist review of 6de7230aa found the earlier spherical cap (chord 15,
# sagitta 1.2 to a point on the axis inside the tap drill) ended on the
# countersink at no definite Ø: the floor gives the recess a definite inner
# edge and its depth a real surface.
DISH_DIA = 14.986  # .59, at the rim
DISH_FLOOR_DIA = 8.89  # .35, the floor's outer edge, where the cone ends
DISH_DEPTH = 1.016  # .04, rim to the floor


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
KNURL_CREST_PITCH = math.pi * HEAD_DIA / KNURL_TEETH  # 1.010
KNURL_TOOTH_ANGLE_DEG = knurl_tooth_angle_deg(HEAD_DIA, KNURL_ROOT_DIA, KNURL_TEETH)
if (
    abs(KNURL_CREST_PITCH - KNURL_PITCH) > 0.01 * KNURL_PITCH
    or abs(KNURL_TOOTH_ANGLE_DEG - KNURL_FLANK_ANGLE_DEG) > 2.0
    or KNURL_TEETH % 2
):
    raise AssertionError(
        f"MHA-PD-13 knurl {KNURL_TEETH}T Ø{HEAD_DIA}/Ø{KNURL_ROOT_DIA} (pitch "
        f"{KNURL_CREST_PITCH:.3f}, {KNURL_TOOTH_ANGLE_DEG:.1f}° V) is not "
        f"{KNURL_DESIGNATION}"
    )

# --- Stations along the axis (local y) ----------------------------------------
SEAT_FACE_Y = 0.0
if abs(OVERALL_LENGTH - HEAD_LENGTH - HEAD_REAR_Y) > 1e-9:
    raise AssertionError("MHA-PD-13 head rear face off the seat-face station")
RIM_Y = OVERALL_LENGTH
DISH_FLOOR_Y = OVERALL_LENGTH - DISH_DEPTH
# The dish profile's two corners (radius from the axis, local y): the depth
# runs between them, from the rim's edge down to the floor's.
DISH_RIM_CORNER = (DISH_DIA / 2.0, RIM_Y)
DISH_FLOOR_CORNER = (DISH_FLOOR_DIA / 2.0, DISH_FLOOR_Y)


# --- Thread (contract §1.6, §7) -----------------------------------------------
THREAD = "#8-32"
TAP_SPEC = HoleSpec("tapped", THREAD)  # UNC-2B, through all
TAP_DRILL_DIA = blind_cut_dia_mm(TAP_SPEC)
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]
# Conservative #8-32 UNC-2B minor diameter: the published rounded 0.130 in
# lower limit, ASME B1.1 Class 2B table (read 2026-10-08):
# https://itpbolt.com/wp-content/uploads/2015/08/Class-2B-Internal-Threads.pdf
# Where the nut stands over the shaft's relief, its crests must clear it.
TAP_MINOR_2B_MIN = 0.130 * 25.4
# 90° entry countersink at each end, opened at least 0.2 mm a side past the
# thread major so the first thread starts full rather than on a feather
# edge.  The sheet prints it as a two-place MAX (a thread-entry chamfer
# needs no more places, drawing-guidelines.md rule 3): the size rounds UP
# to that place (Ø.18 on the #8-32), and the thread it removes never
# exceeds the losses below.
CSK_DIA_PLACES = 2
_CSK_SCALE = 10**CSK_DIA_PLACES
CSK_DIA = (
    math.ceil((THREAD_MAJOR + 2.0 * 0.2) / MM_PER_IN * _CSK_SCALE - 1e-9)
    / _CSK_SCALE
    * MM_PER_IN
)  # 4.572 (.18)
CSK_DIA_TOL_TYPE = 6  # swTolType_e.swTolMAX
CSK_DIA_DEVIATIONS = (THREAD_MAJOR - CSK_DIA, 0.0)
# The sheet prints the cone's 45° half-angle at the title block's angular
# row: no mate seats in these thread-entry cones, so no tighter band.
CSK_INCLUDED_ANGLE_DEG = 90.0
CSK_HALF_ANGLE_DEG = CSK_INCLUDED_ANGLE_DEG / 2.0
CSK_HALF_ANGLE_PLACES = 1
CSK_HALF_ANGLE_MIN = CSK_HALF_ANGLE_DEG - angular_band_deg()  # shared by both units
if CSK_DIA <= THREAD_MAJOR:
    raise AssertionError("MHA-PD-13 countersink ends inside the thread major")
CSK_QUALIFIER = "CSK, BOTH ENDS"
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

# --- Places each printed dimension carries (drawing-guidelines.md rule 3 (decimal places carry the tolerance), contract §12) ----
# Every turned size at .XX: the diameters over the thread hold walls, the
# knurl's root wall, the dish's floor margins and the head's rear-face wall
# read the others, and the stud is cut to fit the nut's rim at assembly, so
# the engagement stack takes the shortest .XX nut
# (pd_transgear_drive_collar_spec.thumbnut_engagement).
HEAD_DIA_PLACES = 2
HEAD_REAR_Y_PLACES = 2
OVERALL_LENGTH_PLACES = 2
FLANGE_DIA_PLACES = 2
FLANGE_LENGTH_PLACES = 2
WAIST_DIA_PLACES = 2
DISH_DIA_PLACES = 2
DISH_FLOOR_DIA_PLACES = 2
DISH_DEPTH_PLACES = 2

WALL_FLOOR = WALL_TARGET_MM  # .080 (rule 17 target)
# A tap cuts up to 0.05 over the basic major: half of it on a wall.
_TAP_OVERSIZE_R = 0.025


def _deviations(model: float, places: int) -> tuple[float, float]:
    return printed_deviations(model, places, unit=UNIT)


_HEAD_LO, _ = _deviations(HEAD_DIA, HEAD_DIA_PLACES)
_HEAD_REAR_LO, _HEAD_REAR_HI = _deviations(HEAD_REAR_Y, HEAD_REAR_Y_PLACES)
_FLANGE_LEN_LO, _FLANGE_LEN_HI = _deviations(FLANGE_LENGTH, FLANGE_LENGTH_PLACES)
_WAIST_LO, _ = _deviations(WAIST_DIA, WAIST_DIA_PLACES)
_FLANGE_LO, _ = _deviations(FLANGE_DIA, FLANGE_DIA_PLACES)
_DISH_LO, _ = _deviations(DISH_DIA, DISH_DIA_PLACES)
_DISH_FLOOR_LO, _DISH_FLOOR_HI = _deviations(DISH_FLOOR_DIA, DISH_FLOOR_DIA_PLACES)
_DISH_DEPTH_LO, _DISH_DEPTH_HI = _deviations(DISH_DEPTH, DISH_DEPTH_PLACES)
OVERALL_LENGTH_LO, OVERALL_LENGTH_HI = _deviations(
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
        (OVERALL_LENGTH + OVERALL_LENGTH_LO)
        - (HEAD_REAR_Y + _HEAD_REAR_HI)
        - (DISH_DEPTH + _DISH_DEPTH_HI),
    ),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-PD-13 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under the {WALL_FLOOR} floor"
        )

# The Ø.43 waist keeps a real length at every printed corner: the head's rear
# face at its lowest and the flange's shoulder at its highest, both read
# from the seat face (codjiflo on 11fe6c440: chained from the rim's head
# length and the seat's flange length, the waist could close to nothing).
WAIST_LENGTH_WORST = (HEAD_REAR_Y + _HEAD_REAR_LO) - (FLANGE_LENGTH + _FLANGE_LEN_HI)
if WAIST_LENGTH_WORST <= 0.0:
    raise AssertionError(
        f"MHA-PD-13 waist closes to {WAIST_LENGTH_WORST:.3f} at the printed worst case"
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
            f"MHA-PD-13 dish: {_name} is {_margin:.3f} at the printed worst case"
        )

# --- The seat on the collar's pilot (R9-70) -------------------------------------
# The bearing annulus and the flange's cover over the pilot are MHA-PD-22's
# (``pd_transgear_drive_collar_spec``), which reads this module.

# --- The nut's side of the stud engagement (contract §7) ----------------------
# The stack subtracts the thread each countersink takes (at its printed MAX,
# from the seat face and from the rim, the front one on the dish floor at its
# deepest printed depth) and, after cut-to-fit, the nut's shortest printed
# length.  The stud's tip station and chamfer are MHA-PD-08's.
# Smallest accepted included angle makes the largest axial thread loss.
# Charge the printed angular row, not the nominal exactly-45-degree cone.
REAR_THREAD_LOSS = REAR_CSK_BREAK / math.tan(math.radians(CSK_HALF_ANGLE_MIN))
FRONT_THREAD_LOSS = DISH_DEPTH + _DISH_DEPTH_HI + REAR_THREAD_LOSS

# The Ø.81 dimension is the diameter over the knurl; the designation gives
# the pitch, and a standard inch straight-knurl wheel forms the 90° tooth,
# so no tooth count prints (R9-57).  One line above: SolidWorks keeps a
# two-line above callout in the document but prints none of it (run
# 20261001T154021634Z: "...\nDIA OVER KNURL" read back over Ø20.5 and was
# missing from the PDF).  It fits inside the Ø.81's extension lines, and
# "OVER KNURL" rides the value as its suffix: the one-line callout wider
# than the span ran the dimension line out under its text past the left
# extension line (machinist review round 3).
KNURL_CALLOUT = f"STRAIGHT KNURL {KNURL_DESIGNATION}"
KNURL_DIA_SUFFIX = " OVER KNURL"

# No roughness symbol: the seat face clamps the wheel (a clamp face, not a
# running, sliding or locating surface; drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates)).

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity-policy.md `How the repository implements the guidelines`).  The head profile carries the knurl
# diameter and, from the seat face, the head's rear face and the overall
# length; the stem profile the flange and waist diameters and the flange
# length from the seat face (the waist length is the remainder); the dish its
# rim and floor diameters and its depth from the rim's edge to the floor's.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadRearY", "OverallLength"},
    "StemProfile": {"FlangeDia", "WaistDia", "FlangeLength"},
    "DishProfile": {"DishDia", "DishFloorDia", "DishDepth"},
    "CountersinkProfile": {"CountersinkDia", "CountersinkHalfAngle"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HeadProfile": {
        "HeadDia": HEAD_DIA_PLACES,
        "HeadRearY": HEAD_REAR_Y_PLACES,
        "OverallLength": OVERALL_LENGTH_PLACES,
    },
    "StemProfile": {
        "FlangeDia": FLANGE_DIA_PLACES,
        "WaistDia": WAIST_DIA_PLACES,
        "FlangeLength": FLANGE_LENGTH_PLACES,
    },
    "DishProfile": {
        "DishDia": DISH_DIA_PLACES,
        "DishFloorDia": DISH_FLOOR_DIA_PLACES,
        "DishDepth": DISH_DEPTH_PLACES,
    },
    "CountersinkProfile": {
        "CountersinkDia": CSK_DIA_PLACES,
        "CountersinkHalfAngle": CSK_HALF_ANGLE_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
