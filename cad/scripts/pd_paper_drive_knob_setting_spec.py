"""The reducer's S-K setting as model dimensions (MHA-PD-00 DETAIL K).

The matched knob bore K is jig-bored on the mill DRO from the arm's reamed
pin bore S, on the shank of the MHA-PD-23 pin already pressed into it (the
cluster's running axis; #2417): the arm trammed on its pivot bore P and
S, the DRO zeroed on S, the plate tapped till its knob bore indicates true at
K's two coordinates from S, along the arm toward P and across it to the
plate's end-round side. K is aimed at the middle of the +x/-0 set band
(``pd_rack_pinion_spec.CENTRE_DISTANCE_WINDOW``) so the DRO and indicator
setting error, worst case, stays inside it at both ends
(test_pd_paper_drive_assembly_drawing). The two coordinates are DRO counts:
of the counts about the mid-band point on the nominal S-K line, the one
nearest the band's middle, which leaves the most margin at both ends.

``build_pd_paper_drive_assembly`` authors these as one hidden construction
sketch in the assembly, on its Front plane (sketch x, y = machine x, y): P to
S along the arm, S to Q along it toward P, Q to K across it, and the S-K
line, on which the nominal centre N stands at CENTRE_DISTANCE from S. S to N
carries the limits the centre may stand at, a toleranced model dimension:
the +x/-0 set band the DRO aims into, opened below by what the trial mesh
may move the plate toward S (``pd_rack_pinion_spec.CENTRE_DISTANCE_TRIAL_BAND``,
owner ruling 2026-11-24, audit part 2 question C1). The two DRO
coordinates to the aimed K are references. All three are marked for
MHA-PD-00, whose sheet 6 DETAIL K prints them and whose arm-plate-located
step cites it; the step prints no value of its own. No solid or pose
changes.
"""

from __future__ import annotations

from dataclasses import replace
import math

import _paper_drive_placement as placement
import paper_drive_mesh_check as mesh_check
import pd_rack_pinion_spec as disc
import pd_transgear_arm_geometry as arm
import pd_transgear_knob_bush_geometry as knob_bush
import pd_transgear_knob_shaft_spec as knob_shaft
import transgear_cluster_fit as cluster_fit

FEATURE = "KnobSettingReference"
ALONG_DIMENSION = "KnobSetAlong"
ACROSS_DIMENSION = "KnobSetAcross"
CENTRE_DIMENSION = "KnobSetCentre"
DRAWING_DIMENSIONS = {FEATURE: {ALONG_DIMENSION, ACROSS_DIMENSION, CENTRE_DIMENSION}}
PLACES = 4
DRAWING_PRECISION = {
    FEATURE: {
        ALONG_DIMENSION: PLACES,
        ACROSS_DIMENSION: PLACES,
        CENTRE_DIMENSION: PLACES,
    }
}
# The limits on S to N, as (lower, upper) deviations: the set band's +x and
# the trial's -.001 (owner ruling 2026-11-24, audit part 2 question C1). The
# set band is the .002 inch step
# (stock_form_quality.reducer_k_setting_diameter_mm / 2), so the limits print
# at three places, +.002/-.001, not as a converted .0019.
TOLERANCE_PLACES = 3
CENTRE_TOLERANCE_MM = (
    disc.inch_ceil_mm(disc.CENTRE_DISTANCE_TRIAL_BAND[1], TOLERANCE_PLACES),
    disc.inch_floor_mm(disc.CENTRE_DISTANCE_TRIAL_BAND[0], TOLERANCE_PLACES),
)
if any(
    abs(printed - band) > 1e-9
    for printed, band in zip(
        CENTRE_TOLERANCE_MM, reversed(disc.CENTRE_DISTANCE_TRIAL_BAND), strict=True
    )
):
    raise AssertionError("DETAIL K's S to N limits are off the .001 inch grid")

# The installed mill DRO's display count in inch mode: its 5 um scale reads
# .0002 (shop inventory machines.PM-30MV.resolution_mm;
# test_pd_paper_drive_assembly_drawing holds the two equal).
DRO_COUNT_MM = 0.00508
# K aimed at the band's middle, on the nominal S-K line.
K_SET_CENTRE_DISTANCE_MM = sum(disc.CENTRE_DISTANCE_WINDOW) / 2.0
_S_TO_K = (arm.KNOB_BORE_STATION - arm.PIN_STATION, arm.KNOB_BORE_OFFSET)
_S_TO_K_UNIT = (_S_TO_K[0] / math.hypot(*_S_TO_K), _S_TO_K[1] / math.hypot(*_S_TO_K))
# From S: toward the pivot along the arm, and across it to the plate's
# end-round side (both negative in the arm frame).
K_AIM_FROM_S_MM = (
    -_S_TO_K_UNIT[0] * K_SET_CENTRE_DISTANCE_MM,
    -_S_TO_K_UNIT[1] * K_SET_CENTRE_DISTANCE_MM,
)


def dro_count_candidates() -> list[tuple[float, float]]:
    """The DRO counts about the aim, one count either way on each axis."""
    along, across = (round(value / DRO_COUNT_MM) for value in K_AIM_FROM_S_MM)
    return [
        (round((along + i) * DRO_COUNT_MM, 6), round((across + j) * DRO_COUNT_MM, 6))
        for i in (-1, 0, 1)
        for j in (-1, 0, 1)
    ]


def _off_middle(point: tuple[float, float]) -> tuple[float, float]:
    # Radially off the band's middle, then off the nominal line.
    return (
        abs(math.hypot(*point) - K_SET_CENTRE_DISTANCE_MM),
        abs(point[0] * _S_TO_K_UNIT[1] - point[1] * _S_TO_K_UNIT[0]),
    )


K_FROM_S_ALONG_MM, K_FROM_S_ACROSS_MM = min(dro_count_candidates(), key=_off_middle)
if K_FROM_S_ALONG_MM <= 0.0 or K_FROM_S_ACROSS_MM <= 0.0:
    raise AssertionError("K is no longer toward the pivot and the end-round side of S")

# --- The trial's moves (MHA-PD-00 arm-plate-located) ----------------------------
# Owner ruling 2026-11-24, audit part 2 question C1: "Yes, the trial may move
# the plate within those limits." (.001 away from S for a tight spot, .001
# toward S if the shake reads over .008; never above +.002 nor below -.001 of
# DETAIL K). "Within those limits" holds for N itself, not only for the
# table's aim: every setting the step reaches is indicated TRUE again, and
# that indication's radial error is charged against the limits (Codjiflo r2
# on #3539: aimed at the old .001 away move, N could stand at about +.0027).
#
# TRUE (the located step's 12C): the DRO, zeroed on S, errs once on the
# S-to-K move, its vendor-stated .0002 per axis both along S-K (shop
# equipment dro.pm-30mv); the test indicator centres S and K each within
# half the sweep (owner ruling 2026-11-08 (Pedro), #2144 item 5.3).
TRUE_SWEEP_IN = 0.0005
DRO_ACCURACY_MM = 0.0002 * 25.4
TRUE_RADIAL_ERROR_MM = (
    DRO_ACCURACY_MM * (abs(_S_TO_K_UNIT[0]) + abs(_S_TO_K_UNIT[1])) + TRUE_SWEEP_IN * 25.4
)  # .00078
LIMIT_LOW_MM = disc.CENTRE_DISTANCE + disc.CENTRE_DISTANCE_TRIAL_BAND[1]
LIMIT_HIGH_MM = disc.CENTRE_DISTANCE + disc.CENTRE_DISTANCE_TRIAL_BAND[0]
# Each move is whole DRO counts on both axes, the pair that carries N along
# S-K nearest the ruled .001 step, never past it, with the least move across
# S-K (which only clocks N about S, inside its setting circle), and whose
# setting keeps N, TRUE's error charged, inside the limits and clear of a
# bind: the room rounds down to the counts. Away from S both coordinates grow.
_TRIAL_STEP_MM = disc.CENTRE_DISTANCE_TRIAL_STEP_IN * 25.4
# The least move a hobby mill sets reliably (DRO count, gib and backlash
# take-up): a smaller room prints no move that way.
TRIAL_MOVE_MIN_IN = 0.0005
# The two running fits pressed shut bring the gears closer than N by half
# each diametral clearance: the knob journal in the MHA-PD-28 bush and the
# MHA-PD-10 sleeve on the pin. (least, greatest)
_KNOB_JOURNAL_CLEARANCE_MM = (
    min(knob_bush.BORE_DIA_LIMITS) - max(knob_shaft.JOURNAL_DIA_BAND),
    max(knob_bush.BORE_DIA_LIMITS) - min(knob_shaft.JOURNAL_DIA_BAND),
)
PRESSED_CLOSURE_MM = tuple(
    (journal + sleeve) / 2.0
    for journal, sleeve in zip(
        _KNOB_JOURNAL_CLEARANCE_MM, cluster_fit.BORE_DIAMETRAL_CLEARANCE, strict=True
    )
)


def binds(centre_mm: float) -> bool:
    """True when the tightest gears at N = ``centre_mm``, both running fits
    pressed shut by their largest clearances, have no backlash."""
    return mesh_check.reducer_mesh(centre_mm - PRESSED_CLOSURE_MM[1]).backlash_mm[0] <= 0.0


def _along_s_k(move: tuple[float, float]) -> float:
    return move[0] * abs(_S_TO_K_UNIT[0]) + move[1] * abs(_S_TO_K_UNIT[1])


def _trial_move_miss(move: tuple[float, float]) -> float:
    across = move[0] * abs(_S_TO_K_UNIT[1]) - move[1] * abs(_S_TO_K_UNIT[0])
    return math.hypot(_TRIAL_STEP_MM - _along_s_k(move), across)


def setting_radius(sign: int, move: tuple[float, float]) -> float:
    """S to the table's setting after ``move`` (away from S if ``sign`` > 0)."""
    return math.hypot(K_FROM_S_ALONG_MM + sign * move[0], K_FROM_S_ACROSS_MM + sign * move[1])


def _trial_move(sign: int) -> tuple[float, float] | None:
    counts = range(round(_TRIAL_STEP_MM / DRO_COUNT_MM) + 1)
    inside = [
        move
        for move in (
            (round(i * DRO_COUNT_MM, 6), round(j * DRO_COUNT_MM, 6)) for i in counts for j in counts
        )
        if _along_s_k(move) <= _TRIAL_STEP_MM + 1e-9
        and LIMIT_LOW_MM + TRUE_RADIAL_ERROR_MM - 1e-9
        <= setting_radius(sign, move)
        <= LIMIT_HIGH_MM - TRUE_RADIAL_ERROR_MM + 1e-9
        and not binds(setting_radius(sign, move) - TRUE_RADIAL_ERROR_MM)
    ]
    move = min(inside, key=_trial_move_miss)
    if _along_s_k(move) < TRIAL_MOVE_MIN_IN * 25.4:
        return None
    return move


# K aimed mid-band (+.00094) leaves .00028 above it before N, with TRUE's
# .00078, could pass +.002: under what the mill sets, so no away move prints
# and a pair that runs tight at DETAIL K takes the step's inspection exit.
# Toward S the limit leaves .00116, but the pressed-shut fits bind with N
# below -.00079, which leaves .00095: the move is .0006 along and .0006
# across (.00085 along S-K, N no lower than -.00069).
TRIAL_AWAY_ROOM_MM = LIMIT_HIGH_MM - TRUE_RADIAL_ERROR_MM - setting_radius(1, (0.0, 0.0))
TRIAL_TOWARD_ROOM_MM = setting_radius(1, (0.0, 0.0)) - TRUE_RADIAL_ERROR_MM - LIMIT_LOW_MM
TRIAL_MOVE_AWAY_MM = _trial_move(1)
TRIAL_MOVE_TOWARD_MM = _trial_move(-1)
if TRIAL_MOVE_TOWARD_MM is None:
    raise AssertionError("no trial move toward S keeps N inside DETAIL K's -.001")
# The farthest from and closest to S that N may stand at any setting the step
# reaches, TRUE's error included. The reducer gates are read there: the C3
# runout contact ratio at the top, and every gate (root clearance,
# interference) at the bottom, where the pressed-shut fits do not bind
# (draw_pd_paper_drive_assembly.REDUCER_SHAKE_MIN_MM reads the shake).
TRIAL_HIGHEST_CENTRE_MM = (
    setting_radius(1, TRIAL_MOVE_AWAY_MM or (0.0, 0.0)) + TRUE_RADIAL_ERROR_MM
)
TRIAL_LOWEST_CENTRE_MM = setting_radius(-1, TRIAL_MOVE_TOWARD_MM) - TRUE_RADIAL_ERROR_MM
if not LIMIT_LOW_MM - 1e-9 <= TRIAL_LOWEST_CENTRE_MM < TRIAL_HIGHEST_CENTRE_MM <= (
    LIMIT_HIGH_MM + 1e-9
):
    raise AssertionError("a trial setting lets N pass DETAIL K's limits")
TRIAL_HIGHEST_MESH = replace(
    mesh_check.reducer_mesh(TRIAL_HIGHEST_CENTRE_MM), contact_ratio_floor=None
).require()
TRIAL_LOWEST_MESH = mesh_check.reducer_mesh(TRIAL_LOWEST_CENTRE_MM).require()
if binds(TRIAL_LOWEST_CENTRE_MM):
    raise AssertionError("the trial's move toward S lets the pressed-shut mesh bind")

# The chain's points in the machine frame (the assembly's Front plane).
P_XY = placement.PIVOT_XY
S_XY = placement.STUD_XY
if abs(math.dist(P_XY, S_XY) - arm.PIN_STATION) > 1e-9:
    raise AssertionError("the pressed stud no longer sits at the arm's pin station")
Q_XY = (
    S_XY[0] - K_FROM_S_ALONG_MM * arm.ARM_U[0],
    S_XY[1] - K_FROM_S_ALONG_MM * arm.ARM_U[1],
)
K_XY = (
    Q_XY[0] - K_FROM_S_ACROSS_MM * arm.ARM_N[0],
    Q_XY[1] - K_FROM_S_ACROSS_MM * arm.ARM_N[1],
)
# The nominal centre N on the aimed S-K line.
_S_TO_K_AIM = (K_XY[0] - S_XY[0], K_XY[1] - S_XY[1])
_NOMINAL_SCALE = disc.CENTRE_DISTANCE / math.hypot(*_S_TO_K_AIM)
N_XY = (
    S_XY[0] + _S_TO_K_AIM[0] * _NOMINAL_SCALE,
    S_XY[1] + _S_TO_K_AIM[1] * _NOMINAL_SCALE,
)

# Native IDisplayDimension.SetText compartments (swDimensionTextParts_e):
# 1/2 prefix/suffix, the reference parentheses (S to N's set band governs
# K, not the title block); 3 the one-line above-callout naming the
# coordinate.
REFERENCE_DIMENSIONS = frozenset({ALONG_DIMENSION, ACROSS_DIMENSION})
SETTING_CALLOUTS = {
    ALONG_DIMENSION: (3, "ALONG"),
    ACROSS_DIMENSION: (3, "ACROSS"),
}
