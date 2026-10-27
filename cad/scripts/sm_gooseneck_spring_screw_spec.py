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

Every size takes the title block's band for its places except three limits,
each named on the sheet for what it serves (drawing-guidelines.md rule 4):
the seat Ø's LIMIT band (the loop seat, under the thread major), the shoulder
length's LIMIT band (to the lead's foot: the loop clears the lead) and the
full-thread station's single "5.67 MAX" from the under-head face, "TO FULL
THREAD" over its value (note 1 names the mate).  The crown's sphere prints
on its arc as the reference "(SR20.03)": the head Ø and the crown rise
drive it (machinist FIX round 1: no note carries a feature's geometry).

The counter seats in ``cad/config/machine/springs.yaml`` were re-measured
natively on this seat and the counterbored 8.80 plug by the one-off
``verify:spring_seats`` leaf, farm run
20261027T065717640Z-ab9171bae60b4714a33d72a6d5e5a2a5; the committed file is
that leaf's output byte for byte (sha256
a92a13546d94fe9257aa6d3ea693ab8a9844323cef1825c0cbdbd2dc803c798e).
"""

from __future__ import annotations

import math
from enum import Enum

import _config
import sm_gooseneck_spring_joint as joint
from sm_gooseneck_spring_screw_geom import (
    CROWN_RISE,
    CROWN_RISE_LOWER,
    CROWN_RISE_UPPER,
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
# Callouts the PART authors on its dimensions (the drawing only reads them
# back; a drawing-side SetText can write through to the part, #1942).  The
# three limits are tighter than the title block, so each names what it serves
# (drawing-guidelines.md rule 4).  Below the value:
COUNTER_SPRING_NUMBER = str(_config.parts("sm-vn-counter-spring")["number"])
PLUG_NUMBER = str(_config.parts("sm-gooseneck")["number"])
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "ShankProfile": {
        "SeatDia": f"{COUNTER_SPRING_NUMBER} LOOP\nSEAT, UNDER\nTHREAD MAJOR",
        "ShoulderLength": f"TO 45 DEG LEAD;\n{COUNTER_SPRING_NUMBER} LOOP\nCLEARS LEAD",
        "TipChamfer": CHAMFER_CALLOUT,
    },
}
# Above the value: the full-thread limit's span (22.7 mm on the sheet) is
# wider than its "5.67 max." but narrower than any callout, and the line on
# the dimension line meets both extension lines' overshoot (farm run
# 20261027T053051351Z: under-head line into the 'M' of a below callout), so
# the value takes that line and the callout stands over it.
DIMENSION_CALLOUTS_ABOVE: dict[str, dict[str, str]] = {
    "StationReference": {"FullThread": "TO FULL THREAD"},
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}
DIMENSION_CALLOUTS_ABOVE_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS_ABOVE.values()
    for name, text in callouts.items()
}
if any("\n" in text for text in DIMENSION_CALLOUTS_ABOVE_BY_NAME.values()):
    raise AssertionError("an above-callout line break would not print")
if set(DIMENSION_CALLOUTS_BY_NAME) & set(DIMENSION_CALLOUTS_ABOVE_BY_NAME):
    raise AssertionError("a dimension carries callouts both above and below")

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

# --- Strength case (#1941 / #1951 load model) ---------------------------------
# Inputs: the catalogue maximum pull of MHA-SM-VN-51 (config), yield of AISI
# 12L14 cold-drawn (415 MPa, azom.com ArticleID 6604), and the oiled
# black-oxide friction range.  The grade is required (drawing-guidelines.md
# rule 2): 1018 CD's 370 MPa (azom.com ArticleID 6115) leaves the service SF
# at 1.91 over the beam past the plug's counterbore (codjiflo round 3, #1997).
SPRING_PULL_MAX_N = float(_config.parts("sm-vn-counter-spring")["maximum_load_n"])
YIELD_MPA = 415.0
# The clamp faces (the head and the plug face on the loop wire) and the thread
# are different contact pairs, so each sweeps the range on its own: the lowest
# clamp friction demands the most preload, and the highest thread friction
# turns the most of it into torsion.
CLAMP_FRICTIONS = (0.05, 0.10, 0.15)
THREAD_FRICTIONS = (0.05, 0.10, 0.15)
FRICTION_PAIRS = tuple((c, t) for c in CLAMP_FRICTIONS for t in THREAD_FRICTIONS)
STRENGTH_SF_TARGET = 2.0
# Two load states, in the MHA-SM-00 sequence.  Tightening: the fitter clamps
# the upper loop at step 8 while the spring's lower loop is still free (it is
# hooked at step 9), so the full thread torsion meets the preload alone.
# Service: the pull adds its bending while the torsion has relaxed to the
# working-state share of VDI 2230 Part 1:2015 (R8: k_tau = 0.5).
RESIDUAL_TORSION_FACTOR = 0.5
# Clamp: friction alone holds the pull on both clamp faces, so the preload is
# F/(2 mu).  The thread carries the thread share of the tightening torque,
# Fp d2/2 (tan lambda + mu sec 30)/(1 - mu tan lambda sec 30), on the basic
# pitch diameter; the under-head share reacts at the head, above the shank.
_PITCH_DIA = MAJOR_DIA - 0.649519 * PITCH
_TAN_LEAD = PITCH / (math.pi * _PITCH_DIA)
_SEC_FLANK = 1.0 / math.cos(math.radians(30.0))


def clamp_preload_n(mu_clamp: float) -> float:
    return SPRING_PULL_MAX_N / (2.0 * mu_clamp)


def thread_torque_n_mm(preload_n: float, mu_thread: float) -> float:
    return (
        preload_n
        * _PITCH_DIA
        / 2.0
        * (_TAN_LEAD + mu_thread * _SEC_FLANK)
        / (1.0 - mu_thread * _TAN_LEAD * _SEC_FLANK)
    )


# Beam from the under-head face (x = 0) to the first FULL thread the screw
# and the plug share, at its farthest (codjiflo P1 round 3 on #1997): the
# screw's own full thread starts by FULL_THREAD_STATION_MAX, the receiver's
# past the plug's counterbore floor and its 0.25 break, from a plug face at
# the widest clamped gap; inside the counterbore the screw is unsupported.
# Sections: the seat at its smallest diameter to the shortest shoulder, the
# estimated deepest #8-32 root everywhere past it (the lead and run-out only
# add metal).
# Path 1: half the pull enters at the head face by friction; the head is
# bracketed guided (M = PL/2) to free (M = PL at the far support).  Path 2:
# the pull bears at the loop's pull-side passes; supports at the head face and
# the far support, bracketed fixed-fixed to simply supported; every split.
RECEIVER_FULL_THREAD_STATION_MAX = (
    joint.CLAMPED_GAP_MAX + joint.COUNTERBORE_DEPTH_MAX + joint.EDGE_BREAK
)
STRENGTH_SPAN = max(FULL_THREAD_STATION_MAX, RECEIVER_FULL_THREAD_STATION_MAX)
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


class HeadEnd(Enum):
    """Path 1's bracket on the head's rotation."""

    GUIDED = "guided"  # M = PL/2 at both ends
    FREE = "free"  # M = PL at the far support


class SpanEnds(Enum):
    """Path 2's bracket on both supports."""

    FIXED = "fixed"
    SIMPLE = "simple"


def _path1_moment(x: float, span: float, head: HeadEnd) -> float:
    half = _F / 2.0
    return abs(half * (x - span / 2.0)) if head is HeadEnd.GUIDED else half * x


def _path2_moment(x: float, span: float, loads, ends: SpanEnds) -> float:
    moment = 0.0
    for load, a in loads:
        b = span - a
        if ends is SpanEnds.FIXED:
            reaction = load * b * b * (3.0 * a + b) / span**3
            end_moment = -load * a * b * b / span**2
        else:
            reaction, end_moment = load * b / span, 0.0
        moment += end_moment + reaction * x - (load * (x - a) if x > a else 0.0)
    return abs(moment)


_MOMENT_CASES = (
    *(lambda x, h=h: _path1_moment(x, STRENGTH_SPAN, h) for h in HeadEnd),
    *(
        lambda x, ld=ld, e=e: _path2_moment(x, STRENGTH_SPAN, ld, e)
        for ld in _PASS_LOADS
        for e in SpanEnds
    ),
)


def _peak_stations(x0: float, x1: float) -> tuple[float, ...]:
    """Every moment case is piecewise linear with kinks only at the load
    stations (path 1's |M| kink is its zero, a minimum), and a section's
    diameter is constant, so its worst stress sits at its ends or a load
    station inside it."""
    inner = {a for loads in _PASS_LOADS for _load, a in loads if x0 < a < x1}
    return tuple(sorted({x0, x1, *inner}))


def _von_mises_sf(preload: float, moment: float, torsion: float, dia: float) -> float:
    sigma = preload / (math.pi / 4.0 * dia * dia) + 32.0 * moment / (math.pi * dia**3)
    tau = 16.0 * torsion / (math.pi * dia**3)
    return YIELD_MPA / math.hypot(sigma, math.sqrt(3.0) * tau)


def service_safety_factor(mu_clamp: float, mu_thread: float) -> float:
    """Preload, the pull's bending and the residual torsion: worst nominal von
    Mises SF against yield over sections, brackets and splits."""
    preload = clamp_preload_n(mu_clamp)
    torsion = RESIDUAL_TORSION_FACTOR * thread_torque_n_mm(preload, mu_thread)
    return min(
        _von_mises_sf(preload, moment(x), torsion, dia)
        for x0, x1, dia in _SECTIONS
        for x in _peak_stations(x0, x1)
        for moment in _MOMENT_CASES
    )


def tightening_safety_factor(mu_clamp: float, mu_thread: float) -> float:
    """Preload plus the full thread torsion, on the estimated deepest root."""
    preload = clamp_preload_n(mu_clamp)
    torsion = thread_torque_n_mm(preload, mu_thread)
    return _von_mises_sf(preload, 0.0, torsion, THREAD_MINOR_2A_MIN_EST)


_SERVICE_SF_EXACT = {pair: service_safety_factor(*pair) for pair in FRICTION_PAIRS}
_TIGHTENING_SF_EXACT = {
    pair: tightening_safety_factor(*pair) for pair in FRICTION_PAIRS
}
# Acceptance reads the unrounded factors; the rounded tables are for print.
if min((*_SERVICE_SF_EXACT.values(), *_TIGHTENING_SF_EXACT.values())) < (
    STRENGTH_SF_TARGET
):
    raise AssertionError(
        f"MHA-SM-04 clamp strength SF service {_SERVICE_SF_EXACT}, tightening "
        f"{_TIGHTENING_SF_EXACT} under {STRENGTH_SF_TARGET}"
    )
SERVICE_SF = {pair: round(sf, 3) for pair, sf in _SERVICE_SF_EXACT.items()}
TIGHTENING_SF = {pair: round(sf, 3) for pair, sf in _TIGHTENING_SF_EXACT.items()}
# Fatigue does not govern: the summing lever is quasi-static and the pull
# swings about +/-1.2 N about a 46.9-47.1 N service load (#1951 sketch), so
# first-load yield at the low-friction preload sets the margin.

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadHeight", "CrownRise", "CrownRadius"},
    "ShankProfile": {"UnderHeadLength", "SeatDia", "ShoulderLength", "TipChamfer"},
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
    "StationReference": {"OverallLength", "FullThread"},
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
# and under-head length; the crown radius prints the sphere on its arc as
# "(SR20.03)", fixed by the head Ø and the crown rise.  The crown rise is NOT
# a reference (see above).
REFERENCE_DIMENSIONS = frozenset({"OverallLength", "CrownRadius"})
# The crown radius's display prefix, authored on the part; the drawing adds
# the reference parentheses around it.
CROWN_RADIUS_PREFIX = "SR"

# The fitter's clamp step (user ruling 2026-09-21: no torque value, no
# threadlocker) prints on the summing assembly sheet as MHA-SM-00 step 8,
# not here: a part sheet carries no assembly instruction (machinist review
# 2026-10-23).  The crown's form and the full-thread limit print on their
# features (machinist FIX round 1), so one note is left.
DRAWING_NOTES = f"1. THREAD MATES THE TAPPED END PLUG OF {PLUG_NUMBER}."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
