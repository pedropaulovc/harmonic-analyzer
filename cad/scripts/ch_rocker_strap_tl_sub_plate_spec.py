r"""Pure-data contract for the rocker-strap sub-plate (MHA-CH-13-TL-01).

PURE DATA, no SolidWorks/COM and no drawing imports. Shop tooling (owner ask
2026-11-17): the work holder of the rocker strap MHA-CH-13's CNC programs, a
13 in length of the owned 1/2 x 6 in 6061-T6511 flat milled to a 3.00 in
strip, its fence and end stop milled integral with it (the top is milled down
round them). Four Mitee-Bite Pitbull edge clamps MHA-CH-13-TL-VN-50 sit in
pockets with #4-40 taps; the hub plug MHA-CH-13-TL-02 sits in the hub
counterbore, and the #10-32 hub screw MHA-CH-13-TL-VN-51 runs into the tap
under it (owner ruling 2026-11-17).

Model frame = the strap programs' G54 (``cad/process/ch_rocker_strap``):
X0 the end stop's face, Y0 the fence's face, Z0 the plate top the strap's
tape lies on (the Front Plane), +X along the plate to its right end, +Y
toward the fence, +Z up. The fence and stop tops (the faced top) stand
FENCE_HEIGHT above Z0; the underside is as received.

The shop TOMLs and the strap plan are never read here (they are not COM-leaf
inputs): the plan values the functional checks need are mirrored below, and
``test_ch_rocker_strap_tl_sub_plate_plan`` holds each mirror to its source.
"""

from __future__ import annotations

import math

import _config
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _package_units import drawing_unit
from _printed_tolerance import (
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_band_mm,
)
from _wizard_pocket_band import WIZARD_POCKET_BAND_MM

PART_NAME = "ch-rocker-strap-tl-sub-plate"
_ROW = _config.parts("ch-rocker-strap-tl-sub-plate")
if PART_NAME != "ch-rocker-strap-tl-sub-plate":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit("parts/ch-rocker-strap-tl-sub-plate", _ROW)
INCH = 25.4
# The title block's general bands this sheet prints under (inch: .X, .XX, .XXX).
X1 = printed_band_mm(1, unit=UNIT)
XX = printed_band_mm(2, unit=UNIT)
XXX = printed_band_mm(3, unit=UNIT)


def inch_grid_mm(value_mm: float, places: int) -> float:
    """``value_mm`` on its printed inch grid (rule 3: .01 for .XX, .001 for .XXX)."""
    return round(value_mm / INCH, places) * INCH


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as the sheet prints it: ``.23``, ``1.650``."""
    text = f"{value_mm / INCH:.{places}f}"
    return text[1:] if text.startswith("0.") else text


# --- Envelope ------------------------------------------------------------------
# Both ends as sawn (.X); the long edges milled for the vise jaws (.XX); the
# top faced and the underside as received, overall .49 (.XX).
LEFT_END_X = -12.7  # .5 from the left sawn end to X0: the stop's length
PLATE_LENGTH = 330.2  # 13.0
RIGHT_END_X = LEFT_END_X + PLATE_LENGTH  # 317.5
FENCE_WIDTH = 12.7  # .50: the fence from Y0 to the back edge
BACK_EDGE_Y = FENCE_WIDTH
PLATE_WIDTH = 76.2  # 3.00
FRONT_EDGE_Y = BACK_EDGE_Y - PLATE_WIDTH  # -63.5
# The fence and stop tops above Z0 (.XXX: at most .079, the shop record's
# "at most .079 in (2.0 mm)" and the plan's keep-out). Z0 is milled down
# round them, so the floor cut's depth from the faced top is this height.
FENCE_HEIGHT = 1.8796  # .074
PLATE_THICKNESS = 12.446  # .49 overall, faced top to underside
UNDERSIDE_Z = FENCE_HEIGHT - PLATE_THICKNESS  # -10.5664 (.416 under Z0)
PLATE_TOP_Z = 0.0  # Z0: everything not fence or stop

# --- Fence notches -----------------------------------------------------------------
# Floor Z0, back corners cutter-formed at CORNER_RADIUS MAX. The left notch
# runs from the stop face, so it also removes the fence at the stop/fence
# corner (no separate corner relief); the right notch is open at the plate's
# right end. Each covers the strap plan's notch station (hub -/+ inner..outer)
# at the worst case of its .XX band and its corner radius (NOTCH_COVER below;
# owner-accepted .92 / 11.08, StrapFixtureCad 2026-11-17).
NOTCH_LEFT_END = 23.368  # .92 from X0
NOTCH_RIGHT_START = 281.432  # 11.08 from X0
NOTCH_DEPTH = 4.318  # .17 back from Y0
NOTCH_FLOOR_Z = PLATE_TOP_Z
# Every cutter-formed inside corner (notch back corners, pocket corners):
# printed R.07 MAX (StrapFixtureCad ruling 2026-11-17: the smallest owned end
# mill is the 1/8 carbide, R.0625, which cannot form R.06 MAX). A MAX limit
# prints its nominal, so the model's corner is the limit itself; the 1/8
# cutter (CORNER_CUTTER_RADIUS) forms a corner inside it.
CORNER_RADIUS = 1.778  # R.07 MAX
CORNER_CUTTER_RADIUS = 1.5875  # the 1/8 end mill
if CORNER_CUTTER_RADIUS > CORNER_RADIUS:
    raise AssertionError("the owned cutter cannot form the printed corner limit")

# --- Clamp pockets and taps (TL-VN-50, Mitee-Bite Pitbull 26000) -------------------
# Stations from X0, the strap plan's clamp_1..4_x_mm (1.000, 4.250, 7.750,
# 11.000), each a pocket centred on its 4-40 tap.
CLAMP_STATIONS: tuple[float, ...] = (25.4, 107.95, 196.85, 279.4)
POCKET_LENGTH = 14.224  # .56 along X
# The pocket's back wall seats the clamp's heel; its knife reaches the blank's
# edge at C = .375 from it. Explicit band (shop table: a milled step <= 6 in
# from its datum, +/-.002): the clamp fits and grips only while the wall less
# the blank's width lies within its .0075 total throw of C (Mitee-Bite
# PITBULL-INST-0426), which the title block's +/-.005 alone overruns
# (necessity register N-02).
POCKET_BACK_WALL_Y = -47.625  # 1.875 from Y0
POCKET_BACK_WALL_TOL = 0.0508  # +/-.002
# The near wall: the blank's edge line (the 1.50 in blank against the fence).
BLANK_EDGE_Y = -38.1  # 1.50
POCKET_NEAR_WALL_Y = BLANK_EDGE_Y
POCKET_DEPTH = 3.556  # .140 from Z0: Pitbull B
POCKET_FLOOR_Z = PLATE_TOP_Z - POCKET_DEPTH
# The clamp's screw: A = .150 in front of the blank's edge (1.650 from Y0).
CLAMP_SCREW_Y = -41.91
CLAMP_TAP_THREAD = "#4-40"
CLAMP_TAP_SPEC = HoleSpec("tapped", CLAMP_TAP_THREAD, end="through_all")
CLAMP_TAP_DRILL = TAP_DRILL_MM[CLAMP_TAP_THREAD]  # #43, .089
# The clamp as the catalogue gives it (Mitee-Bite 26000: A .150, B .140,
# C .375, F .375 body width), mirrored from the TL-VN-50 contract.
CLAMP_A = 3.81
CLAMP_B = 3.556
CLAMP_C = 9.525
CLAMP_BODY_WIDTH = 9.525

# --- Hub counterbore and tap (TL-02 plug, TL-VN-51 screw) ---------------------------
# The hub hole's position carries the shop table's +/-.002 for a milled step:
# the hub screw stands in its tap and centres the washer TL-VN-52, which the
# strap's outline program keeps its cutter clear of round its own hub centre,
# so the tap's position error closes that air (necessity register N-01;
# ch_rocker_strap_tl_vn_hub_washer_spec). The counterbore's Ø and depth are
# its Hole Wizard callout's, three places at the .XX grade (rule 3, #3622).
HUB_X = 152.4  # 6.000 from X0
HUB_Y = -25.4  # 1.000 from Y0
HUB_LOCATION_TOL = 0.0508  # +/-.002
HUB_CBORE_DIA = 12.7  # .500
HUB_CBORE_DEPTH = 4.699  # .185 from Z0
HUB_CBORE_BAND = (WIZARD_POCKET_BAND_MM, -WIZARD_POCKET_BAND_MM)
COUNTERBORE_FLOOR_Z = PLATE_TOP_Z - HUB_CBORE_DEPTH
# Owner ruling 2026-11-23: "change the screw to #10-32. The sub-plate's
# tapped hole becomes #10-32" (reversing 2026-11-17's "Use a 1/4-20 hub
# screw"), its tap through the plate from the counterbore floor.
HUB_TAP_THREAD = "#10-32"
HUB_TAP_DRILL = TAP_DRILL_MM[HUB_TAP_THREAD]  # #21, .159
# The counterbore and its drill are ONE Hole Wizard counterbore (the fleet's
# counterbored holes: draw_ch_fulcrum_keeper), whose native callout prints
# the drill, the counterbore's Ø and its depth together (drawing-guidelines:
# "a depth is never deferred to a view"; machinist reviews mr5 and mr7). Its
# drill is the tap's: the thread is a cosmetic thread on it, and the
# callout's thread row names it (HUB_THREAD_ROW).
HUB_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "#10",
    overrides_mm={
        "HoleDiameter": HUB_TAP_DRILL,
        "CounterBoreDiameter": HUB_CBORE_DIA,
        "CounterBoreDepth": HUB_CBORE_DEPTH,
    },
)
HUB_THREAD_ROW = f"{HUB_TAP_THREAD.removeprefix('#')} UNF"
# The cosmetic thread's own label, SolidWorks' form for a wizard tap's
# thread ("#10-32 Tapped Hole"), which the drawing's sweep deletes as it does
# the clamp taps'.
HUB_THREAD_LABEL = f"{HUB_TAP_THREAD} Tapped Hole"

# --- Strap-plan mirrors (asserted against plan.toml in the plan test) -------------
PLAN_HUB_X = 152.4
PLAN_HUB_Y = 25.4  # the plan's distance toward the operator from Y0
PLAN_FENCE_NOTCH_INNER = 131.0
PLAN_FENCE_NOTCH_OUTER = 150.0
PLAN_FENCE_NOTCH_DEPTH = 4.0
PLAN_DRILL_TIP_Z = -4.0
PLAN_REAM_TIP_Z = -4.0
PLAN_RELIEF_FLOOR_CLEARANCE = 0.5
# The finished strap's thinnest top (ch_rocker_arm_spec ARM_THICKNESS less its
# band, .097): the face cutter's lowest pass in Setups 2-3 (no tape under).
STRAP_THICKNESS_MIN = 2.4638

# --- Functional checks -------------------------------------------------------------
# Fence and stop: their tallest stays under the strap's thinnest finished top,
# so the face cutter clears them.
FENCE_HEIGHT_MAX = FENCE_HEIGHT + XXX
FACE_CUT_CLEARANCE_MIN = STRAP_THICKNESS_MIN - FENCE_HEIGHT_MAX
if FACE_CUT_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the fence or stop reaches the strap's face cut")


def _in_rounded_notch(
    point: tuple[float, float],
    x_range: tuple[float, float],
    depth: float,
    rounded_x: tuple[float, ...],
) -> bool:
    """Whether ``point`` (x, y >= 0) lies in a notch spanning ``x_range`` back to
    ``depth`` from Y0, its back corners at each ``rounded_x`` rounded to
    CORNER_RADIUS."""
    x, y = point
    if not (x_range[0] <= x <= x_range[1] and 0.0 <= y <= depth):
        return False
    for corner_x in rounded_x:
        sign = 1.0 if corner_x > x_range[0] else -1.0
        centre = (corner_x - sign * CORNER_RADIUS, depth - CORNER_RADIUS)
        beyond_x = (x - centre[0]) * sign > 0.0
        if beyond_x and y > centre[1] and math.dist(point, centre) > CORNER_RADIUS:
            return False
    return True


# The plan's notch stations, each the X range its fence-sliver rings sweep
# (hub -/+ inner..outer), cleared back to its notch depth.
PLAN_NOTCH_STATIONS: tuple[tuple[float, float], ...] = (
    (PLAN_HUB_X - PLAN_FENCE_NOTCH_OUTER, PLAN_HUB_X - PLAN_FENCE_NOTCH_INNER),
    (PLAN_HUB_X + PLAN_FENCE_NOTCH_INNER, PLAN_HUB_X + PLAN_FENCE_NOTCH_OUTER),
)
# Worst case of the printed bands: the notch ends .XX short, the depth .XX
# shallow, the right sawn end .X short; X0 itself (the stop face, the left
# notch's end wall) is the datum.
NOTCH_EXTENTS_WORST: tuple[
    tuple[tuple[float, float], float, tuple[float, ...]], ...
] = (
    ((0.0, NOTCH_LEFT_END - XX), NOTCH_DEPTH - XX, (0.0, NOTCH_LEFT_END - XX)),
    (
        (NOTCH_RIGHT_START + XX, RIGHT_END_X - X1),
        NOTCH_DEPTH - XX,
        (NOTCH_RIGHT_START + XX,),
    ),
)
for (_lo, _hi), ((_x_range, _depth, _rounded)) in zip(
    PLAN_NOTCH_STATIONS, NOTCH_EXTENTS_WORST, strict=True
):
    for _corner in ((_lo, PLAN_FENCE_NOTCH_DEPTH), (_hi, PLAN_FENCE_NOTCH_DEPTH)):
        if not _in_rounded_notch(_corner, _x_range, _depth, _rounded):
            raise AssertionError(
                f"fence notch {_x_range} misses the plan station's corner {_corner}"
            )

# A square-cornered clamp body clears the pocket's corner radii at both ends.
POCKET_END_CLEARANCE = (
    POCKET_LENGTH - XX - CLAMP_BODY_WIDTH - 2.0 * CORNER_RADIUS
) / 2.0
if POCKET_END_CLEARANCE <= 0.25:
    raise AssertionError("the clamp pocket does not clear the clamp body's corners")
# Heel on the back wall, the knife reaches the blank's edge; the depth is B.
if abs(POCKET_BACK_WALL_Y + CLAMP_C - BLANK_EDGE_Y) > 1e-9:
    raise AssertionError(
        "the pocket's back wall does not put the knife on the blank edge"
    )
if abs(BLANK_EDGE_Y - CLAMP_A - CLAMP_SCREW_Y) > 1e-9:
    raise AssertionError("the clamp tap is not A in front of the blank edge")
if POCKET_DEPTH != CLAMP_B:
    raise AssertionError("the clamp pocket's depth is not the clamp's B")

# Thread engagement (rule 18: 1.5D of full thread), each tap through the plate
# from its floor, at nominal and at the worst case of the printed bands
# (overall -.01, fence height +.005, the floor's depth: a pocket's +.005, the
# hub counterbore's +.01, since a Hole Wizard counterbore's depth takes the
# .XX grade, drawing-guidelines rule 3 and #3622), less the title block's
# edge break at both tap mouths: only full thread counts (Codjiflo review of
# #3056; pd_platen_spec's SOCKET_THREAD_ENGAGEMENT_MIN).
TAP_MOUTH_BREAK = max(edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT))
CLAMP_THREAD_LENGTH = POCKET_FLOOR_Z - UNDERSIDE_Z  # 7.0104, .276
CLAMP_THREAD_LENGTH_MIN = CLAMP_THREAD_LENGTH - XX - XXX - XXX - 2.0 * TAP_MOUTH_BREAK
CLAMP_THREAD_REQUIRED = 1.5 * THREAD_MAJOR_MM[CLAMP_TAP_THREAD]
if CLAMP_THREAD_LENGTH_MIN < CLAMP_THREAD_REQUIRED:
    raise AssertionError("the clamp tap is short of 1.5D of thread")
HUB_THREAD_LENGTH = COUNTERBORE_FLOOR_Z - UNDERSIDE_Z  # 5.8674, .231
HUB_THREAD_LENGTH_MIN = (
    HUB_THREAD_LENGTH - XX - XXX - HUB_CBORE_BAND[0] - 2.0 * TAP_MOUTH_BREAK
)  # 4.7244, .186
HUB_THREAD_MAJOR = THREAD_MAJOR_MM[HUB_TAP_THREAD]
HUB_THREAD_REQUIRED = 1.5 * HUB_THREAD_MAJOR  # .285
# Owner ruling 2026-11-17 (registry RV-01) accepts the .23 in of thread in
# the plate; under the #10-32 of 2026-11-23 it is .21 of full thread nominal
# (1.11D), .186 at the worst case (0.979D; the 1/4-20 had .76D).
# The sheet states the worst case as a plain fact (rule 20), on the tap's
# callout, its length and its diameters each floored to two places: a stated
# minimum is never rounded up past what the bands leave.
HUB_ENGAGEMENT_DIAMETERS = HUB_THREAD_LENGTH_MIN / HUB_THREAD_MAJOR
if not HUB_THREAD_LENGTH_MIN < HUB_THREAD_REQUIRED:
    raise AssertionError("the hub tap now meets 1.5D: drop the shortfall statement")
_ENGAGEMENT_FLOOR_IN = math.floor(round(HUB_THREAD_LENGTH_MIN / INCH * 100, 6)) / 100
_ENGAGEMENT_FLOOR_D = math.floor(round(HUB_ENGAGEMENT_DIAMETERS * 100, 6)) / 100
HUB_ENGAGEMENT_STATEMENT = (
    f"ENGAGEMENT {inch_text(_ENGAGEMENT_FLOOR_IN * INCH, 2)} MIN "
    f"({_ENGAGEMENT_FLOOR_D:.2f}D)".replace("(0.", "(.")
)

# The counterbore is the relief the strap's hub drill and reamer run into
# (the plan's tips at drill_tip_z_mm / ream_tip_z_mm). At its shallowest
# (the wizard depth's .XX) the tips still stop 0.445 mm above its floor. What
# fails is a tip that reaches the floor, so the worst case is checked
# against the tool-length reading, .001 (tolerance-policy.md; check register
# C-01). The plan's relief_floor_clearance_mm (0.5, "the author's allowance,
# no source") gates nothing here.
HUB_CBORE_TIP_CLEARANCE_MIN = (HUB_CBORE_DEPTH + HUB_CBORE_BAND[1]) + min(
    PLAN_DRILL_TIP_Z, PLAN_REAM_TIP_Z
)
TIP_FLOOR_READING = 0.001 * INCH
if HUB_CBORE_TIP_CLEARANCE_MIN <= TIP_FLOOR_READING:
    raise AssertionError(
        "the strap's hub drill or reamer tip can reach the counterbore floor"
    )

# --- Printed grid (rule 3) ------------------------------------------------------------
PRINTED_PLACES: tuple[tuple[float, int], ...] = (
    (-LEFT_END_X, 1),
    (PLATE_LENGTH, 1),
    (FENCE_WIDTH, 2),
    (PLATE_WIDTH, 2),
    (PLATE_THICKNESS, 2),
    (FENCE_HEIGHT, 3),
    (NOTCH_LEFT_END, 2),
    (NOTCH_RIGHT_START, 2),
    (NOTCH_DEPTH, 2),
    (CORNER_RADIUS, 2),
    *((station, 2) for station in CLAMP_STATIONS),
    (POCKET_LENGTH, 2),
    (-POCKET_BACK_WALL_Y, 3),
    (-POCKET_NEAR_WALL_Y, 2),
    (POCKET_DEPTH, 3),
    (-CLAMP_SCREW_Y, 2),
    (HUB_X, 3),
    (-HUB_Y, 3),
    (HUB_CBORE_DIA, 3),
    (HUB_CBORE_DEPTH, 3),
)
for _value, _places in PRINTED_PLACES:
    if abs(inch_grid_mm(_value, _places) - _value) > 1e-9:
        raise AssertionError(f"{_value} mm is off its printed .{'X' * _places} grid")

# --- Volume (analytic, for the build's gates) -------------------------------------
# A filleted inside corner of a cut puts back (1 - pi/4) R^2 per unit height.
_CORNER_FILL = (1.0 - math.pi / 4.0) * CORNER_RADIUS**2
V_PLATE = PLATE_LENGTH * PLATE_WIDTH * PLATE_THICKNESS
V_FLOOR_CUT = (RIGHT_END_X - 0.0) * (0.0 - FRONT_EDGE_Y) * FENCE_HEIGHT
V_NOTCHES = (
    (NOTCH_LEFT_END + (RIGHT_END_X - NOTCH_RIGHT_START)) * NOTCH_DEPTH * FENCE_HEIGHT
)
V_NOTCH_CORNERS = 3 * _CORNER_FILL * FENCE_HEIGHT
V_POCKETS = (
    len(CLAMP_STATIONS)
    * POCKET_LENGTH
    * (POCKET_NEAR_WALL_Y - POCKET_BACK_WALL_Y)
    * POCKET_DEPTH
)
V_POCKET_CORNERS = 4 * len(CLAMP_STATIONS) * _CORNER_FILL * POCKET_DEPTH
V_HUB_CBORE = math.pi / 4.0 * HUB_CBORE_DIA**2 * HUB_CBORE_DEPTH
V_CLAMP_TAPS = (
    len(CLAMP_STATIONS) * math.pi / 4.0 * CLAMP_TAP_DRILL**2 * CLAMP_THREAD_LENGTH
)
V_HUB_TAP = math.pi / 4.0 * HUB_TAP_DRILL**2 * HUB_THREAD_LENGTH
V_FINISHED = (
    V_PLATE
    - V_FLOOR_CUT
    - V_NOTCHES
    + V_NOTCH_CORNERS
    - V_POCKETS
    + V_POCKET_CORNERS
    - V_HUB_CBORE
    - V_CLAMP_TAPS
    - V_HUB_TAP
)

# --- Native model contract ------------------------------------------------------------
# Feature names (the build names them; the drawing imports their dimensions):
# PlateProfile/Plate the stock blank (faced top down to the underside),
# PlateTopProfile/PlateTop the Z0 floor milled down round the fence and stop,
# NotchProfile/FenceNotches and NotchCorners, PocketProfile/ClampPockets and
# PocketCorners, the wizard taps ClampTaps and the wizard counterbore
# HubHole (its #10-32 cosmetic thread HubThread). The faced top is the
# reference plane FacedTopPlane, FENCE_HEIGHT
# above the Front Plane (Z0).
FACED_TOP_PLANE = "FacedTopPlane"
# A section imports no sketch or extrusion size (farm run 20261117T234245842Z:
# section A-A delivered none of FenceHeight, PlateThickness, PocketDepth), so
# every size a section prints is owned by a hidden construction-only reference
# sketch lying in its cutting plane (build_pd_platen's CboreFloorReference):
# short chords along Z lying on edges the section draws, the top view they
# are cut from seeing each end-on, every printed size a chord's length or a
# chord's start from the sketch origin (the fence face's foot, Y0 Z0).
# Both sections cut across the plate along Y, so the pocket walls print as
# rows over a section instead of a stack of lanes beside the top view (farm
# run 20261118T001932117Z: seven Y lanes from Y0 piled their texts on one
# another). Section A-A cuts pocket 3 beside its tap, across the plate's
# full width (machinist review mr5: a partial section without a break line
# read 2.55 wide against the 3.00): the pocket walls from Y0, the pocket
# depth, and the overall thickness on a chord down the fence face's line.
# Section B-B cuts the hub on its axis (mr5: .15 off the axis it missed the
# tapped hole and drew a solid floor under the counterbore), showing the
# counterbore, its floor and the tap through: the fence height (the hub's
# sizes are its callout's). The fence and overall widths print on the top view
# from the plate's own sketch: farm runs r13 and r14 (20261118T012253828Z
# and its successor) imported neither them nor the thickness from B-B's
# chords on the back and front faces, however anchored. Each tap's callout
# stands on the top view; A-A's offset keeps its plane clear of its tap's
# thread and inside the pocket's straight walls.
SECTION_A_PLANE = "SectionAPlane"
SECTION_A_OFFSET = 4.445  # .175 right of pocket 3's tap
SECTION_A_X = CLAMP_STATIONS[2] + SECTION_A_OFFSET
SECTION_A_REFERENCE = "SectionAReference"
SECTION_B_PLANE = "SectionBPlane"
SECTION_B_X = HUB_X
SECTION_B_REFERENCE = "SectionBReference"
if not (
    THREAD_MAJOR_MM[CLAMP_TAP_THREAD] / 2.0
    < SECTION_A_OFFSET
    < POCKET_LENGTH / 2.0 - CORNER_RADIUS
):
    raise AssertionError("section A-A cuts pocket 3's tap or a corner radius")
CLAMP_TAP_X_NAMES: tuple[str, ...] = tuple(
    f"ClampTapX{index}" for index in range(1, len(CLAMP_STATIONS) + 1)
)
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"LeftEnd", "PlateLength", "FenceWidth", "PlateWidth"},
    "NotchProfile": {"NotchLeftEnd", "NotchRightStart", "NotchDepth"},
    "NotchCorners": {"NotchCornerR"},
    "PocketProfile": {"PocketLength"},
    "PocketCorners": {"PocketCornerR"},
    "HubHole": {"HubX", "HubY"},
    "ClampTaps": {*CLAMP_TAP_X_NAMES, "ClampTapY"},
    SECTION_A_REFERENCE: {
        "PocketNearWallY",
        "PocketBackWallY",
        "PocketDepth",
        "PlateThickness",
    },
    SECTION_B_REFERENCE: {"FenceHeight"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {"LeftEnd": 1, "PlateLength": 1, "FenceWidth": 2, "PlateWidth": 2},
    "NotchProfile": {"NotchLeftEnd": 2, "NotchRightStart": 2, "NotchDepth": 2},
    "NotchCorners": {"NotchCornerR": 2},
    "PocketProfile": {"PocketLength": 2},
    "PocketCorners": {"PocketCornerR": 2},
    "HubHole": {"HubX": 3, "HubY": 3},
    # Routine tap locations at two places (rule 3; machinist review r24:
    # three places with no band or function were over-specification).
    "ClampTaps": {**{name: 2 for name in CLAMP_TAP_X_NAMES}, "ClampTapY": 2},
    SECTION_A_REFERENCE: {
        "PocketNearWallY": 2,
        "PocketBackWallY": 3,
        "PocketDepth": 3,
        "PlateThickness": 2,
    },
    SECTION_B_REFERENCE: {"FenceHeight": 3},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
for _feature, _names in DRAWING_DIMENSIONS.items():
    if set(DRAWING_PRECISION[_feature]) != _names:
        raise AssertionError(
            f"{_feature}: every marked dimension needs authored places"
        )
# Each printed dimension, its model value (mm) for the readback gates.
DIMENSION_VALUES: dict[str, float] = {
    "LeftEnd": -LEFT_END_X,
    "PlateLength": PLATE_LENGTH,
    "FenceWidth": FENCE_WIDTH,
    "PlateWidth": PLATE_WIDTH,
    "PlateThickness": PLATE_THICKNESS,
    "FenceHeight": FENCE_HEIGHT,
    "NotchLeftEnd": NOTCH_LEFT_END,
    "NotchRightStart": NOTCH_RIGHT_START,
    "NotchDepth": NOTCH_DEPTH,
    "NotchCornerR": CORNER_RADIUS,
    "PocketLength": POCKET_LENGTH,
    "PocketNearWallY": -POCKET_NEAR_WALL_Y,
    "PocketBackWallY": -POCKET_BACK_WALL_Y,
    "PocketDepth": POCKET_DEPTH,
    "PocketCornerR": CORNER_RADIUS,
    "HubX": HUB_X,
    "HubY": -HUB_Y,
    **dict(zip(CLAMP_TAP_X_NAMES, CLAMP_STATIONS, strict=True)),
    "ClampTapY": -CLAMP_SCREW_Y,
}
if set(DIMENSION_VALUES) != set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every printed dimension needs its model value")
# Explicit bands (mm, symmetric) on named model dimensions, each with its
# necessity entry (cad/config/necessity/ch-rocker-strap-tl-sub-plate.yaml);
# everything else is the title block's row for its places. The build sets
# each one (build_ch_rocker_strap_tl_sub_plate).
SYMMETRIC_BANDS: dict[tuple[str, str], float] = {
    (SECTION_A_REFERENCE, "PocketBackWallY"): POCKET_BACK_WALL_TOL,
    ("HubHole", "HubX"): HUB_LOCATION_TOL,
    ("HubHole", "HubY"): HUB_LOCATION_TOL,
}
# Single-limit (MAX) corner radii: the model value is the limit itself, the
# limit word the value's suffix with no native tolerance, since swTolMAX
# prints a lowercase "max." (machinist review mr5: "3X .07 max.").
MAX_RADII: tuple[tuple[str, str], ...] = (
    ("NotchCorners", "NotchCornerR"),
    ("PocketCorners", "PocketCornerR"),
)
MAX_SUFFIX = " MAX"

# --- Sheet words -------------------------------------------------------------------
# Counts on the pocket set and the corner radii (rule 10: identical features
# take one nX callout); each tight or three-place feature's mate or reason
# once, on its own dimension (rules 3, 4, 7). A prefix replaces SolidWorks'
# own radius "R", so each radius carries it (mr5: the radii printed bare).
# The hub hole's sizes are its wizard callout's native variables, three
# places each (HUB_CALLOUT_PLACES).
POCKET_COUNT = len(CLAMP_STATIONS)
NOTCH_CORNER_COUNT = 3
# Both fence notches share one back wall (the sketch's collinear back
# walls), so their one depth is a 2X (machinist review r26: the right
# notch's depth was given nowhere). SECTION A-A cuts one pocket, so both its
# wall locations carry the pocket count as its depth does (#3490).
NOTCH_COUNT = 2
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("PocketProfile", "PocketLength"): f"{POCKET_COUNT}X ",
    (SECTION_A_REFERENCE, "PocketNearWallY"): f"{POCKET_COUNT}X ",
    (SECTION_A_REFERENCE, "PocketBackWallY"): f"{POCKET_COUNT}X ",
    (SECTION_A_REFERENCE, "PocketDepth"): f"{POCKET_COUNT}X ",
    ("PocketCorners", "PocketCornerR"): f"{4 * POCKET_COUNT}X R",
    ("NotchCorners", "NotchCornerR"): f"{NOTCH_CORNER_COUNT}X R",
    ("NotchProfile", "NotchDepth"): f"{NOTCH_COUNT}X ",
}
HUB_CALLOUT_PLACES = 3
CLAMP_NUMBER = "TL-VN-50"
PLUG_NUMBER = "TL-02"
STRAP_NUMBER = "MHA-CH-13"
# The fence height's three-place reason holds only at .XXX (rule 3), checked
# here: its top stays at or under the shop record's .079 (FENCE_TOP_LIMIT),
# which .XX's band would break, and under the strap's finished top face, so
# the face mill clears it (FACE_CUT_CLEARANCE_MIN). The hub counterbore's
# depth is its wizard callout's, at the .XX grade (rule 3, #3622), and is
# checked at that grade above.
FENCE_TOP_LIMIT = 0.079 * INCH
if not FENCE_HEIGHT + XXX <= FENCE_TOP_LIMIT + 1e-9 < FENCE_HEIGHT + XX:
    raise AssertionError("the fence height's third place is not what holds .079")
# The pocket's tight back-wall location (1.875 +/-.002) and its depth both
# serve the clamp's seat, so the clamp is named once, on one numbered note
# both dimensions flag (rule 4: one feature with several tight dimensions
# names its mate once; rule 7: SEE NOTE n links it; machinist review mr7:
# named only on the depth, the 1.875's mate read as missing). Rule 4 names
# the fit: the back wall locates the clamp's heel and the floor its height,
# so the clamp sits on a locating fit (machinist review r23: "SEAT" is no
# standard fit name).
POCKET_SEAT_NOTE_NUMBER = 1
POCKET_SEAT_NOTE = f"{POCKET_SEAT_NOTE_NUMBER}. LOCATING FIT ON {CLAMP_NUMBER}."
POCKET_SEAT_FLAG = f"SEE NOTE {POCKET_SEAT_NOTE_NUMBER}"
DIMENSION_CALLOUTS: dict[str, str] = {
    "PocketBackWallY": POCKET_SEAT_FLAG,
    "PocketDepth": POCKET_SEAT_FLAG,
    "FenceHeight": f"CLEARS {STRAP_NUMBER} STRAP TOP FACE",
}
# The taps' native callouts: DRILL after the drill's Ø, the clamp taps'
# count. The hub hole's, four rows (the audit's limit): its drill, its
# thread, its counterbore with the plug it holds (the plug floats in it, so
# no fit is named: #3713), the thread's stated shortfall.
CLAMP_TAP_COUNT = f"{POCKET_COUNT}X"
HUB_CBORE_MATE = f"FOR {PLUG_NUMBER}"
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
