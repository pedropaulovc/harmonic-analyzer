"""Pure-data drawing contract for MHA-SM-04, the gooseneck spring screw.

PURE DATA -- no SolidWorks/COM imports.  ``sm_gooseneck_spring_screw_geom``
owns every size and band; this module adds what the print states (the marked
dimensions, their authored places, the callouts and the notes) and the
strength case that chose the thread.

Design (owner ruling 2026-10-26 (#1951, option B)).  MHA-SM-04 is a custom
shoulder screw: a plain turned Ø3.50 shoulder under the head is the
MHA-SM-VN-51 loop seat, a 45-degree lead steps up to an #8-32 UNC thread, and
the MHA-SM-01 plug is retapped #8-32 UNC-2B THRU.  The 2026-09-21 rulings
stand unchanged: the head is tightened until the loop is clamped to the plug
face and cannot swivel, with no torque value and no threadlocker.  The ruling
supersedes the #6-32 the 2026-10-10 option-B note named; that note's purpose,
the supplier coil/tube clearance, holds because the seat keeps the #6-32
crests' height (Ø3.50 against 3.5052).

Why the thread and not the shoulder (#1951 options sketch,
gooseneck-shoulder-screw-1951.png).  While the head clamps the loop, friction
alone must hold the spring on both faces (the #1941 model), so the screw
carries F/(2 mu) of preload plus its thread torque, and that load runs
through the first engaged thread whatever the shoulder looks like.  On the
#6-32 root that was twist-off SF 2.02 at mu 0.05 before any bending, 1.24 with
the clamp's bending, 1.17 with the old Ø2.15 relief.  A seated shoulder that
stops clamping the loop needs far less preload, but makes the loop a pivot
(rule 23) and needs a stated seating torque, so it would reverse 2026-09-21.
The #8-32 root carries the same clamp at the SF below.

Every size takes the title block's band for its places except the two LIMIT
bands, each named on the sheet for what it serves (drawing-guidelines.md rule
4): the seat Ø (the loop seat, under the thread major) and the shoulder
length (to the lead's foot: the loop clears the lead, and full thread starts
inside the MHA-SM-01 engagement budget).
"""

from __future__ import annotations

import math

import _config
import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spring_joint as joint
from sm_gooseneck_spring_screw_geom import (
    CROWN_RISE,
    CROWN_RISE_LOWER,
    CROWN_RISE_UPPER,
    DIE_RUNOUT,
    FULL_THREAD_STATION_MAX,
    HEAD_H,
    HEAD_H_LOWER,
    MAJOR_DIA,
    PITCH,
    SEAT_DIA_MIN,
    SHOULDER_LENGTH_MIN,
    SLOT_DEPTH,
    SLOT_DEPTH_LOWER,
    SLOT_DEPTH_UPPER,
    THREAD,
    THREAD_MINOR_2A_MIN_EST,
)

THREAD_CALLOUT = THREAD
CHAMFER_CALLOUT = "X 45 DEG"
# Below-value callouts the PART authors on its dimensions (the drawing only
# reads them back; a drawing-side SetText can write through to the part,
# #1942).  The two LIMIT bands are tighter than the title block, so each names
# what it serves (drawing-guidelines.md rule 4).
COUNTER_SPRING_NUMBER = str(_config.parts("sm-vn-counter-spring")["number"])
PLUG_NUMBER = str(_config.parts("sm-gooseneck")["number"])
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "ShankProfile": {
        "SeatDia": f"{COUNTER_SPRING_NUMBER} LOOP\nSEAT, UNDER\nTHREAD MAJOR",
        "ShoulderLength": (
            f"TO 45 DEG LEAD; LOOP\nCLEARS LEAD, FULL\nTHREAD IN {PLUG_NUMBER}"
        ),
        "TipChamfer": CHAMFER_CALLOUT,
    },
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}

# drawing-guidelines.md rule 17 (walls and webs): the head left under the slot floor, at the shortest head,
# the deepest slot and a full under-head edge break, stays above the 2.0
# wall target (7.00 - 0.51 - 3.51 - 0.25 = 2.73).
EDGE_BREAK_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])
SLOT_WEB_TARGET = 2.0
SLOT_WEB_MIN = round(
    HEAD_H + HEAD_H_LOWER - (SLOT_DEPTH + SLOT_DEPTH_UPPER) - EDGE_BREAK_MAX, 6
)
if SLOT_WEB_MIN < SLOT_WEB_TARGET:
    raise AssertionError("spring-screw slot leaves under the drawing-guidelines.md rule 17 (walls and webs) head web")

# The crown rise is the only printed size that fixes the dome (the head Ø and
# height do not), so it controls at the .XX band.  Across that band the dome
# must stay a usable fillister head: the shallowest slot still cuts through
# the cylindrical rim under the tallest crown, so a full-width blade bears on
# both slot walls, and the tallest crown on the shortest head still leaves a
# cylindrical side after a full edge break.
CROWN_RISE_MIN = CROWN_RISE + CROWN_RISE_LOWER
CROWN_RISE_MAX = CROWN_RISE + CROWN_RISE_UPPER
SLOT_RIM_CUT_MIN = round(SLOT_DEPTH + SLOT_DEPTH_LOWER - CROWN_RISE_MAX, 6)
HEAD_SIDE_MIN = round(HEAD_H + HEAD_H_LOWER - CROWN_RISE_MAX - EDGE_BREAK_MAX, 6)
if CROWN_RISE_MIN <= 0.0 or SLOT_RIM_CUT_MIN <= 0.0 or HEAD_SIDE_MIN <= 0.0:
    raise AssertionError("spring-screw crown band does not leave a fillister head")

# --- Strength case (#1941 / #1951 load model, unchanged) --------------------
# Inputs: the catalogue maximum pull of MHA-SM-VN-51 (config), yield of AISI
# 1018 cold-drawn, the weaker listed stock (370 MPa, azom.com ArticleID 6115;
# 12L14 CD's 415 MPa adds 12 %), and the oiled black-oxide friction floor.
SPRING_PULL_MAX_N = float(_config.parts("sm-vn-counter-spring")["maximum_load_n"])
YIELD_MPA = 370.0
FRICTIONS = (0.05, 0.10, 0.15)
STRENGTH_SF_TARGET = 2.0
# Clamp: friction alone holds the pull on both clamp faces, so the preload is
# F/(2 mu).  The thread carries the thread share of the tightening torque,
# Fp d2/2 (tan lambda + mu sec 30)/(1 - mu tan lambda sec 30), on the basic
# pitch diameter; the under-head share reacts at the head, above the shank.
_PITCH_DIA = MAJOR_DIA - 0.649519 * PITCH
_TAN_LEAD = PITCH / (math.pi * _PITCH_DIA)
_SEC_FLANK = 1.0 / math.cos(math.radians(30.0))


def clamp_preload_n(mu: float) -> float:
    return SPRING_PULL_MAX_N / (2.0 * mu)


def thread_torque_n_mm(preload_n: float, mu: float) -> float:
    return (
        preload_n
        * _PITCH_DIA
        / 2.0
        * (_TAN_LEAD + mu * _SEC_FLANK)
        / (1.0 - mu * _TAN_LEAD * _SEC_FLANK)
    )


# Beam from the under-head face (x = 0) to the first FULL engaged thread, at
# its farthest: the longest shoulder, the steepest-legged lead and the die's
# run-out push it STRENGTH_SPAN past the clamp gap into the plug.  Sections:
# the seat at its smallest diameter to the shortest shoulder, the estimated
# deepest #8-32 root everywhere past it (the lead and run-out only add metal).
# Path 1: half the pull enters at the head face by friction; the head is
# bracketed guided (M = PL/2) to free (M = PL at the far support).  Path 2:
# the pull bears at the loop's pull-side passes; supports at the head face and
# the far support, bracketed fixed-fixed to simply supported; every split.
STRENGTH_SPAN = max(gooseneck.SPRING_EYE_GAP, FULL_THREAD_STATION_MAX)
_SECTIONS = (
    (0.0, SHOULDER_LENGTH_MIN, SEAT_DIA_MIN),
    (SHOULDER_LENGTH_MIN, STRENGTH_SPAN, THREAD_MINOR_2A_MIN_EST),
)
_F = SPRING_PULL_MAX_N
_PASS_LOADS = (
    ((_F, joint.LOOP_PASS_X[0]),),
    ((_F, joint.LOOP_PASS_X[1]),),
    ((_F / 2.0, joint.LOOP_PASS_X[0]), (_F / 2.0, joint.LOOP_PASS_X[1])),
)


def _path1_moment(x: float, span: float, guided: bool) -> float:
    half = _F / 2.0
    return abs(half * (x - span / 2.0)) if guided else half * x


def _path2_moment(x: float, span: float, loads, fixed: bool) -> float:
    moment = 0.0
    for load, a in loads:
        b = span - a
        if fixed:
            reaction = load * b * b * (3.0 * a + b) / span**3
            end_moment = -load * a * b * b / span**2
        else:
            reaction, end_moment = load * b / span, 0.0
        moment += end_moment + reaction * x - (load * (x - a) if x > a else 0.0)
    return abs(moment)


def combined_safety_factor(mu: float, samples: int = 400) -> float:
    """Worst nominal von Mises SF against yield over sections, brackets and splits."""
    preload = clamp_preload_n(mu)
    torque = thread_torque_n_mm(preload, mu)
    cases = [lambda x, g=g: _path1_moment(x, STRENGTH_SPAN, g) for g in (True, False)]
    cases += [
        lambda x, ld=ld, f=f: _path2_moment(x, STRENGTH_SPAN, ld, f)
        for ld in _PASS_LOADS
        for f in (True, False)
    ]
    worst = math.inf
    for x0, x1, dia in _SECTIONS:
        area = math.pi / 4.0 * dia * dia
        tau = 16.0 * torque / (math.pi * dia**3)
        for index in range(samples + 1):
            x = x0 + (x1 - x0) * index / samples
            for moment in cases:
                sigma = preload / area + 32.0 * moment(x) / (math.pi * dia**3)
                worst = min(worst, YIELD_MPA / math.hypot(sigma, math.sqrt(3.0) * tau))
    return worst


def twist_off_safety_factor(mu: float) -> float:
    """Preload plus thread torsion alone, on the estimated deepest root."""
    dia = THREAD_MINOR_2A_MIN_EST
    preload = clamp_preload_n(mu)
    sigma = preload / (math.pi / 4.0 * dia * dia)
    tau = 16.0 * thread_torque_n_mm(preload, mu) / (math.pi * dia**3)
    return YIELD_MPA / math.hypot(sigma, math.sqrt(3.0) * tau)


COMBINED_SF = {mu: round(combined_safety_factor(mu), 3) for mu in FRICTIONS}
TWIST_OFF_SF = {mu: round(twist_off_safety_factor(mu), 3) for mu in FRICTIONS}
if min(COMBINED_SF.values()) < STRENGTH_SF_TARGET:
    raise AssertionError(
        f"MHA-SM-04 clamp strength SF {COMBINED_SF} under {STRENGTH_SF_TARGET}"
    )
# Fatigue does not govern: the summing lever is quasi-static and the pull
# swings about +/-1.2 N about a 46.9-47.1 N service load (#1951 sketch), so
# first-load yield at the low-friction preload sets the margin.

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadHeight", "CrownRise"},
    "ShankProfile": {"UnderHeadLength", "SeatDia", "ShoulderLength", "TipChamfer"},
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
    "StationReference": {"OverallLength"},
}
# Chamfers never need extra places (drawing-guidelines.md rule 3): the tip
# chamfer rides the title block's .X band.  Every other mark prints at two.
ONE_PLACE_DIMENSIONS = frozenset({"TipChamfer"})
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: 1 if name in ONE_PLACE_DIMENSIONS else 2 for name in sorted(names)}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
# The overall length is the stock cut-off, a restatement of the head height
# and under-head length; the crown rise is NOT a reference (see above).
REFERENCE_DIMENSIONS = frozenset({"OverallLength"})

# The fitter's clamp step (user ruling 2026-09-21: no torque value, no
# threadlocker) prints on the summing assembly sheet as MHA-SM-00 step 8,
# not here: a part sheet carries no assembly instruction (machinist review
# 2026-10-23).  Note 3 bounds the die's run-out the engagement budget assumes
# (sm_gooseneck_spring_joint.MATED_ENGAGEMENT_MIN).
DRAWING_NOTES = "\n".join(
    (
        "1. CROWN SPHERICAL THROUGH RIM AND APEX.",
        f"2. THREAD MATES THE TAPPED END PLUG OF {PLUG_NUMBER}.",
        f"3. FULL THREAD FORM WITHIN {DIE_RUNOUT:.1f} OF THE LEAD.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
