"""Pure geometry of the made MHA-SM-04 counter-spring clamp screw.

Native frame: axis Z, under-head face Z=0, head +Z, shank -Z. The
thread is represented by its basic major cylinder, not a die blank with a
made-up general diameter tolerance. The external UNF-2A callout defines it.
No drawing, prose, builder or COM dependencies belong in this module.

Owner rulings 2026-10-27 (#1951): rederived from the ch19 reference close-up
(page001_img02): a plain slotted cheese head on the arm axis, the spring's
double loop clamped on the screw's plain body between the head and the
MHA-SM-01 end piece's flush face.  The body is the 1/4-28 UNF thread's own
blank, turned to the 2A major band and left plain under the head for the
loop; the die runs up to it and leaves its run-out inside the end piece's
counterbore.  The Ø11.50 head stands under an owner minor exception to the
1.0 head retention check (sm_gooseneck_spring_joint).  The 2026-09-21 rulings
stand: the head clamps the loop to the end face (no torque value, no
threadlocker).  ``sm_gooseneck_spring_screw_spec`` carries the strength case;
``sm_gooseneck_spring_joint`` the body, engagement and wall budgets.

#290: every size here is calibrated spring-support geometry (the native
counter-seat certificate, settled_spring_seats.counter_upper_support_geometry,
records the nominals), so the model keeps these millimetre values and the
decimal-inch sheet prints them on the inch grid.  The bands and limits below
are the millimetre ENVELOPES the sheet's LIMIT bands are cut from; the inch
sheet's printed bands and limits (PRINTED_BANDS / PRINTED_LIMITS, at the end)
are what ``sm_gooseneck_spring_joint`` charges.
"""

from __future__ import annotations

import math

from _printed_tolerance import printed_deviations

MM_PER_IN = 25.4
STOCK_DIA = 0.5 * MM_PER_IN
THREAD_SIZE = "1/4-28"
THREAD = f"{THREAD_SIZE} UNF"
THREADS_PER_IN = 28
MAJOR_DIA = 0.25 * MM_PER_IN
PITCH = MM_PER_IN / THREADS_PER_IN
# Under-head face to tip, including the plain body, the thread and the tip
# chamfer: the free-gap reach leaves 1.5D of mated full thread past the plug's
# counterbore floor at the shortest screw (sm_gooseneck_spring_joint).
LENGTH = 19.50
# Envelope: the millimetre sheet's .XX band, +/-0.51 (the joint's reach
# budgets); the inch sheet's .77 +/-.01 lies inside it.
LENGTH_LOWER, LENGTH_UPPER = printed_deviations(LENGTH, 2)
# The cheese head: a flat-topped cylinder, as the reference close-up shows.
# Its Ø is a LIMIT band (envelope 11.60/11.40), not the title block's .XX:
# the relief chamfer below is measured from the OD, and at Ø12.01 the
# MHA-SM-VN-51 transition wire would meet the relief's outer end
# (sm_gooseneck_spring_joint; owner ruling 2026-10-27, #1951).
HEAD_DIA = 11.50
HEAD_DIA_LOWER, HEAD_DIA_UPPER = -0.10, 0.10
HEAD_DIA_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
# The head's under-face OD edge is relieved by a 45-degree chamfer, a LIMIT
# band (envelope 1.50/1.40): the MHA-SM-VN-51 loop leaves its head-side end
# for the coil through the vendor's transition wire, which crosses the head
# face's plane just outside the head's OD.  Unrelieved, the Ø11.50 edge cuts
# 0.21 into that wire (native verify:spring_seats probe, farm run
# 20261027T193324627Z; the analytic replica in test_sm_gooseneck_spring_joint
# agrees).  The joint holds the loop's clamp bearing on the flat inside it.
HEAD_RELIEF_CHAMFER = 1.45
HEAD_RELIEF_CHAMFER_LOWER, HEAD_RELIEF_CHAMFER_UPPER = -0.05, 0.05
HEAD_RELIEF_CHAMFER_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
HEAD_RELIEF_CHAMFER_MIN = round(HEAD_RELIEF_CHAMFER + HEAD_RELIEF_CHAMFER_LOWER, 6)
HEAD_RELIEF_CHAMFER_MAX = round(HEAD_RELIEF_CHAMFER + HEAD_RELIEF_CHAMFER_UPPER, 6)
# 6.60 tall, longer than the reference photo shows (head over the Ø12.70 arm
# 0.52 against its 0.46): the relief chamfer rises from the under-head face
# under the slot's ends, and the head left there must hold the rule-17 wall
# (sm_gooseneck_spring_screw_spec SLOT_WEB_MIN; owner ruling 2026-10-27,
# #1951, via coordinator Main).
HEAD_H = 6.60
SLOT_WIDTH = 1.60
SLOT_DEPTH = 2.00  # From the flat top face.

# 1/4-28 UNF-2A limits, ASME B1.1 as tabled by Engineers Edge (read
# 2026-10-27, https://www.engineersedge.com/screw_threads_chart.htm): major
# 0.2490/0.2425 in, pitch diameter 0.2258/0.2225 in.
THREAD_MAJOR_2A_MAX_IN = 0.2490
THREAD_MAJOR_2A_MIN_IN = 0.2425
THREAD_PD_2A_MIN_IN = 0.2225
THREAD_MAJOR_2A_MAX = THREAD_MAJOR_2A_MAX_IN * MM_PER_IN
THREAD_MAJOR_2A_MIN = THREAD_MAJOR_2A_MIN_IN * MM_PER_IN
# DERIVED ESTIMATE, not a standard minimum minor-diameter limit: the repo's
# deepest die-root construction takes a full basic half-depth (0.649519 P)
# below the minimum 2A pitch diameter (pd_vn_transgear_pivot_screw_spec uses
# the same construction for its #8-32): 5.062.
THREAD_MINOR_2A_MIN_EST = (THREAD_PD_2A_MIN_IN - 0.649519 / THREADS_PER_IN) * MM_PER_IN

# The plain body is the thread blank: modelled at the basic major with the
# thread, a LIMIT band (envelope 6.32/6.20) inside the 2A major band, so the
# die cuts a 2A crest and the loop bears on one turned diameter.  The title
# block's .XX band would leave the blank outside the thread class.
BODY_DIA = MAJOR_DIA
BODY_DIA_LOWER, BODY_DIA_UPPER = -0.15, -0.03
BODY_DIA_TOL_TYPE = 3  # swTolType_e.swTolLIMIT
BODY_DIA_MIN = round(BODY_DIA + BODY_DIA_LOWER, 6)
BODY_DIA_MAX = round(BODY_DIA + BODY_DIA_UPPER, 6)
# Under-head face to the die's first incomplete thread, a single MIN limit
# (the inch sheet's ".14 MIN"): the loop's plug-side pass
# (sm_gooseneck_spring_joint.LOOP_PASS_X, 3.14 at the free gap) always bears
# on the plain body.  Any longer plain body only shortens the run-out window
# below, which the full-thread MAX bounds.
PLAIN_LENGTH_MIN = 3.60
PLAIN_LENGTH_MIN_TOL_TYPE = 5  # swTolType_e.swTolMIN
# The die's chamfered start leaves 1.5 pitches of incomplete thread
# (drawing-guidelines.md rule 18; the repo's tip allowance,
# sm_gooseneck_spring_joint.SCREW_END_INCOMPLETE_MAX) behind the full thread.
DIE_RUNOUT = 1.5 * PITCH
# Under-head face to the first full thread, a single MAX limit (the inch
# sheet's ".225 MAX"); 5.71 is the largest two-place mm limit whose run-out
# the end piece's counterbore (sm_gooseneck_spring_joint.COUNTERBORE_DEPTH_MIN,
# 2.73) clears
# by its margin at the least gap on the screw's axis.  Between the two limits
# a die has 2.3 pitches for its chamfer.
FULL_THREAD_STATION_MAX = 5.71
FULL_THREAD_STATION_MAX_TOL_TYPE = 6  # swTolType_e.swTolMAX
FULL_THREAD_DIE_ROOM_MIN = 2.0 * PITCH
# The two limits bound each other, so each one's native band (upper, lower)
# about its modelled limit runs to the other: the plain body at most reaches
# the full thread (zero run-out), and the full thread starts no earlier than
# the plain body's end.
PLAIN_LENGTH_MIN_BAND = (round(FULL_THREAD_STATION_MAX - PLAIN_LENGTH_MIN, 6), 0.0)
FULL_THREAD_STATION_MAX_BAND = (0.0, -PLAIN_LENGTH_MIN_BAND[0])
# The under-head inside corner (head face to body) is turned R.020 MAX, not the
# title block's INSIDE CORNERS R.040 MAX (codjiflo round 4 on #1997): a loop
# wire touching both the face and the body clears a concave round only up to
# R0.8 (sm_gooseneck_spring_joint owns the check).  swTolMAX prints the
# nominal and "MAX" (0.50 rounds to .020 at three places); the band runs from
# sharp up to it.
UNDERHEAD_CORNER_R = 0.50
UNDERHEAD_CORNER_R_BAND = (0.0, -UNDERHEAD_CORNER_R)  # (upper, lower)
UNDERHEAD_CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.020 MAX"
# The thread-start chamfer, about one thread depth, rides the title block's
# two-place band.
TIP_CHAMFER = 0.50
OVERALL_LENGTH = LENGTH + HEAD_H
SLOT_FLOOR_Z = HEAD_H - SLOT_DEPTH


def require_body_form(
    body_dia_max: float = BODY_DIA_MAX,
    body_dia_min: float = BODY_DIA_MIN,
    plain_length_min: float = PLAIN_LENGTH_MIN,
    full_thread_station_max: float = FULL_THREAD_STATION_MAX,
) -> None:
    """Refuse a body outside the 2A major band, or no room for the die and thread."""
    if not THREAD_MAJOR_2A_MIN <= body_dia_min <= body_dia_max <= THREAD_MAJOR_2A_MAX:
        raise AssertionError("screw body leaves the 1/4-28 UNF-2A major band")
    if full_thread_station_max - plain_length_min < FULL_THREAD_DIE_ROOM_MIN:
        raise AssertionError(
            "screw full-thread limit leaves a die no room for its chamfer"
        )
    if full_thread_station_max + TIP_CHAMFER + 1.5 * PITCH >= LENGTH + LENGTH_LOWER:
        raise AssertionError(
            "screw leaves no full thread between the run-out and the tip"
        )


require_body_form()

# --- MHA-SM-04 as its decimal-inch sheet prints it (#290). ---
# The sheet's unit, its registry row's drawing_unit
# (sm_gooseneck_spring_screw_spec checks the two agree): a literal here
# because sm_gooseneck_spring_joint, which charges the printed limits below,
# reads no registry row (codjiflo P3 on #1997).
SHEET_UNIT = "in"
# Three places on the LIMIT bands and on the full-thread and corner single
# limits (each needs them to stay on its side of its envelope); two
# everywhere else.
THREE_PLACE_DIMENSIONS = frozenset(
    {"HeadDia", "HeadReliefChamfer", "BodyDia", "FullThread", "UnderHeadCornerR"}
)


def places(name: str) -> int:
    return 3 if name in THREE_PLACE_DIMENSIONS else 2


def _limit_band(model: float, lower: float, upper: float) -> tuple[float, float]:
    """(lower, upper) mm deviations about ``model`` of the widest .001-in LIMIT
    pair inside the mm envelope ``model + lower .. model + upper``."""
    low = math.ceil(round((model + lower) / MM_PER_IN * 1000.0, 6)) / 1000.0
    high = math.floor(round((model + upper) / MM_PER_IN * 1000.0, 6)) / 1000.0
    return round(low * MM_PER_IN - model, 9), round(high * MM_PER_IN - model, 9)


# What the sheet accepts, (lower, upper) mm about each mm model nominal: the
# three LIMIT bands on the inch grid inside their envelopes, every other band
# the title block's .XX about the printed (rounded) nominal.
PRINTED_BANDS: dict[str, tuple[float, float]] = {
    "HeadDia": _limit_band(HEAD_DIA, HEAD_DIA_LOWER, HEAD_DIA_UPPER),
    "HeadReliefChamfer": _limit_band(
        HEAD_RELIEF_CHAMFER, HEAD_RELIEF_CHAMFER_LOWER, HEAD_RELIEF_CHAMFER_UPPER
    ),
    "BodyDia": _limit_band(BODY_DIA, BODY_DIA_LOWER, BODY_DIA_UPPER),
    **{
        name: printed_deviations(model, places(name), unit=SHEET_UNIT)
        for name, model in (
            ("HeadHeight", HEAD_H),
            ("UnderHeadLength", LENGTH),
            ("SlotWidth", SLOT_WIDTH),
            ("SlotDepth", SLOT_DEPTH),
            ("TipChamfer", TIP_CHAMFER),
        )
    },
}
# The single limits as printed, mm: swTolMIN / swTolMAX print the model
# rounded at its places, the model on the accepted side of it.  No finite inch
# place holds the joint's 3.60 / 5.71 / 0.50, so each prints past it
# (".14 MIN", ".225 MAX", "R.020 MAX") and the joint charges the printed one.
PRINTED_LIMITS: dict[str, float] = {
    name: model
    + printed_deviations(model, places(name), (0.0, 0.0), unit=SHEET_UNIT)[0]
    for name, model in (
        ("PlainLength", PLAIN_LENGTH_MIN),
        ("FullThread", FULL_THREAD_STATION_MAX),
        ("UnderHeadCornerR", UNDERHEAD_CORNER_R),
    )
}
# Every model nominal sits inside its printed band, except the body, which is
# modelled at the thread's basic major with its blank's band below it.
if not all(
    lower <= 0.0 <= upper
    for name, (lower, upper) in PRINTED_BANDS.items()
    if name != "BodyDia"
) or not (
    PRINTED_LIMITS["PlainLength"] <= PLAIN_LENGTH_MIN
    and FULL_THREAD_STATION_MAX <= PRINTED_LIMITS["FullThread"]
    and UNDERHEAD_CORNER_R <= PRINTED_LIMITS["UnderHeadCornerR"]
):
    raise AssertionError("an MHA-SM-04 model nominal leaves its printed band")
