"""Pure-data drawing contract for MHA-SM-04, the gooseneck spring screw.

PURE DATA -- no SolidWorks/COM imports.  ``sm_gooseneck_spring_screw_geom``
owns every size and band; this module adds what the print states (the marked
dimensions, their authored places, the callouts and the notes) and the
strength case that chose the thread.

Design (owner rulings 2026-10-27, #1951, rederived from the ch19 reference
close-up page001_img02).  MHA-SM-04 is a slotted cheese-head screw turned
from hardened 4140: a Ø11.50 x 6.60 flat-topped head, its under-face edge
relieved for the spring's transition wire, and under it the plain Ø6.35
body the MHA-SM-VN-51 loop bears on, which is also the blank the die cuts
the 1/4-28 UNF thread on, toward the tip.  The thread runs into the blind
1/4-28 UNF-2B tap in the solid end piece of MHA-SM-01's 1/2 in arm.  The
2026-09-21 rulings stand unchanged: the head is tightened until the loop is
clamped to the end face and cannot swivel, with no torque value and no
threadlocker.  The Ø11.50 head keeps 0.95 (.037 in) retention under an owner minor
(sm_gooseneck_spring_joint).

Decimal-inch sheet (#290).  The screw's sizes are calibrated spring-support
geometry, so the model keeps its millimetre nominals and the sheet prints them
on the inch grid (sm_gooseneck_spring_screw_geom.PRINTED_BANDS /
PRINTED_LIMITS, which the joint charges).  Every size takes the
title block's .XX band except six limits, each named on the sheet for what
it serves (drawing-guidelines.md rule 4): the body Ø's LIMIT band .248/.245
(the thread blank, inside the 2A major band, and the loop's seat), the plain
length's single ".14 MIN" (the loop bears on the plain body), the full-thread
station's single ".225 MAX" from the under-head face ("TO FULL THREAD"; the
end piece's counterbore clears the run-out short of it), the under-head
corner's single "R.020 MAX" under the title block's INSIDE CORNERS R.040 MAX
(codjiflo round 4 on #1997), and the head Ø's LIMIT band .456/.449 with its
relief chamfer's .059/.056 (the loop's transition wire clears the head, and
the flat inside the relief still bears the loop).
"""

from __future__ import annotations

import math
from enum import Enum

import _config
import sm_gooseneck_spring_joint as joint
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from sm_gooseneck_spring_screw_geom import (
    BODY_DIA,
    BODY_DIA_MIN,
    FULL_THREAD_STATION_MAX,
    HEAD_DIA,
    HEAD_DIA_UPPER,
    HEAD_H,
    HEAD_RELIEF_CHAMFER,
    HEAD_RELIEF_CHAMFER_MIN,
    MAJOR_DIA,
    MM_PER_IN,
    PITCH,
    PRINTED_BANDS,
    PRINTED_LIMITS,
    SHEET_UNIT,
    SLOT_DEPTH,
    THREAD,
    THREAD_MINOR_2A_MIN_EST,
    places,
    require_body_form,
)

# #290: the registry row's drawing_unit (in) is this sheet's unit; the
# geometry module's printed bands, which the joint reads, assume the same.
UNIT = drawing_unit(
    "parts/sm-gooseneck-spring-screw", _config.parts("sm-gooseneck-spring-screw")
)
if UNIT != SHEET_UNIT:
    raise AssertionError("MHA-SM-04's registry unit is not its geometry's SHEET_UNIT")
require_body_form(
    body_dia_max=BODY_DIA + PRINTED_BANDS["BodyDia"][1],
    body_dia_min=BODY_DIA + PRINTED_BANDS["BodyDia"][0],
    plain_length_min=PRINTED_LIMITS["PlainLength"],
    full_thread_station_max=PRINTED_LIMITS["FullThread"],
)

THREAD_CALLOUT = THREAD
CHAMFER_CALLOUT = "X 45 DEG"
# Callouts the PART authors on its dimensions (the drawing only reads them
# back; a drawing-side SetText can write through to the part, #1942).  The
# six limits are tighter than the title block, so each names what it serves
# (drawing-guidelines.md rule 4).  Below the value (the corner radius's
# two rows too: SolidWorks prints no line break in the above compartment,
# pn_pen_v_block_spec; its value stands over them on the leader's shoulder,
# draw_pn_pen_rod's "R0.2 MAX / SEATS ON PEN V-BLOCK / MHA-PN-05"):
COUNTER_SPRING_NUMBER = str(_config.parts("sm-vn-counter-spring")["number"])
PLUG_NUMBER = str(_config.parts("sm-gooseneck")["number"])
# The head's retention under its 1.0 target stands only on owner minor RV-01
# (sm_gooseneck_spring_joint.owner_minor).
if joint.HEAD_RETENTION_MIN < joint.HEAD_RETENTION_TARGET:
    joint.owner_minor(
        _config.parts("sm-gooseneck-spring-screw"), "RV-01", "sm_gooseneck_spring_screw"
    )
# The head's worst-case overlap of the loop's eye, under the 1.0 check (owner
# minor RV-01), stated on the head Ø as a plain fact (drawing-guidelines.md
# rule 20; codjiflo P2 on #1997), in inches floored, never rounded up: the
# joint's 0.9525 at the printed .449 floor is .037.  Two rows, so neither is
# wider than the part number's.
_RETENTION_MILS = math.floor(joint.HEAD_RETENTION_MIN / MM_PER_IN * 1000.0)
HEAD_RETENTION_CALLOUT = f"LOOP OVERLAP\n.{_RETENTION_MILS:03d} MIN"
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    "HeadProfile": {
        "HeadDia": f"{COUNTER_SPRING_NUMBER}\nWIRE CLEARS;\n{HEAD_RETENTION_CALLOUT}",
        "HeadReliefChamfer": f"{CHAMFER_CALLOUT};\n{COUNTER_SPRING_NUMBER}\nWIRE CLEARS",
    },
    "ShankProfile": {
        "BodyDia": f"THREAD BLANK;\n{COUNTER_SPRING_NUMBER}\nLOOP SEAT",
        "TipChamfer": CHAMFER_CALLOUT,
        "UnderHeadCornerR": f"{COUNTER_SPRING_NUMBER}\nLOOP CLEARS",
    },
    "StationReference": {
        "PlainLength": f"PLAIN;\n{COUNTER_SPRING_NUMBER}\nLOOP SEAT",
    },
}
# Above the value: the full-thread limit's span is wider than its ".225 max."
# but narrower than any callout, so the value takes the dimension line and
# the callout stands over it (farm run 20261027T053051351Z).
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

# drawing-guidelines.md rule 17 (walls and webs): the head left under the
# slot floor is thinnest at the slot's ends, over the relief chamfer's widest
# rise.  At the printed shortest head (.25), deepest slot (.09) and largest
# chamfer (.059) it stays above the .080 wall target (6.35 - 2.286 - 1.4986
# = 2.565).
SLOT_WEB_TARGET = WALL_TARGET_MM
SLOT_WEB_MIN = round(
    HEAD_H
    + PRINTED_BANDS["HeadHeight"][0]
    - (SLOT_DEPTH + PRINTED_BANDS["SlotDepth"][1])
    - (HEAD_RELIEF_CHAMFER + PRINTED_BANDS["HeadReliefChamfer"][1]),
    6,
)
if SLOT_WEB_MIN < SLOT_WEB_TARGET:
    raise AssertionError(
        "spring-screw slot leaves under the drawing-guidelines.md rule 17 (walls and webs) head web"
    )

# --- Strength case (#1941 / #1951 load model) ---------------------------------
# Inputs: the catalogue maximum pull of MHA-SM-VN-51 (config); the yield of
# the bar MHA-SM-04 is turned from, McMaster 6818T53 (1/2 in 4140 hardened to
# HRC 32, ASTM A108; yield 130,000 psi, read live 2026-10-27); and the oiled
# black-oxide friction range.  The grade is required (drawing-guidelines.md
# rule 2): at the clamp-couple bound below, 12L14 CD's 415 MPa (azom.com
# ArticleID 6604) leaves the root at SF 1.22 (#1951 sketch).
SPRING_PULL_MAX_N = float(_config.parts("sm-vn-counter-spring")["maximum_load_n"])
YIELD_MPA = 130_000.0 * 0.00689475729
# The clamp faces (the head and the end face on the loop wire) and the thread
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
# at least F/(2 mu).  The thread carries the thread share of the tightening
# torque, Fp d2/2 (tan lambda + mu sec 30)/(1 - mu tan lambda sec 30), on the
# basic pitch diameter; the under-head share reacts at the head, above the
# shank.  F/(2 mu) is the preload the clamp NEEDS, not a ceiling: under the
# 2026-09-21 rulings MHA-SM-00 step 8 gives no torque value (the fitter stops
# once the loop is clamped and cannot swivel), so no installation bound
# exists above it.  Both tightening stresses are linear in the preload, so
# TIGHTENING_SF is that envelope stated as a ratio: the multiple of the
# needed preload (and of its torque) the root takes before nominal yield,
# OVERTIGHTEN_MARGIN (codjiflo round 4, #1997).
_PITCH_DIA = MAJOR_DIA - 0.649519 * PITCH
_TAN_LEAD = PITCH / (math.pi * _PITCH_DIA)
_SEC_FLANK = 1.0 / math.cos(math.radians(30.0))
# The clamp couple (codjiflo eccentric-clamp P1s on #1997): the loop hangs
# below the screw axis, so the clamp's reaction on the head face need not sit
# on the axis, and the shank carries the preload times that offset in both
# states.  Statics bounds the offset by the flat head face itself: the relief
# chamfer ends it at the largest head less the smallest chamfer, and a wire
# resting on the face's plane meets the 45-degree relief nowhere past that
# edge (#1951 rederived-photo sketch: e = 0 / uniform pressure / this bound).
CLAMP_ECCENTRICITY_MAX = (HEAD_DIA + HEAD_DIA_UPPER) / 2.0 - HEAD_RELIEF_CHAMFER_MIN


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
# and the end piece share, at its farthest (codjiflo P1 round 3 on #1997): the
# screw's own full thread starts by FULL_THREAD_STATION_MAX, the receiver's
# past the end piece's counterbore floor and its 0.25 break, from an end face
# at the widest clamped gap; inside the counterbore the screw is unsupported.
# Sections: the plain body at its smallest diameter to the thread's earliest
# start, the estimated deepest 1/4-28 root everywhere past it (the run-out
# only adds metal).
# Path 1: half the pull enters at the head face by friction; the head is
# bracketed guided (M = PL/2) to free (M = PL at the far support).  Path 2:
# the pull bears at the loop's pull-side passes; supports at the head face and
# the far support, bracketed fixed-fixed to simply supported; every split.
# Each adds the clamp couple at its bound, with the same sign.
RECEIVER_FULL_THREAD_STATION_MAX = (
    joint.CLAMPED_GAP_MAX + joint.COUNTERBORE_DEPTH_MAX + joint.EDGE_BREAK
)
STRENGTH_SPAN = max(FULL_THREAD_STATION_MAX, RECEIVER_FULL_THREAD_STATION_MAX)
# The thread may start at the printed ".14 MIN" plain station.
_SECTIONS = (
    (0.0, PRINTED_LIMITS["PlainLength"], BODY_DIA_MIN),
    (PRINTED_LIMITS["PlainLength"], STRENGTH_SPAN, THREAD_MINOR_2A_MIN_EST),
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


def service_safety_factor(
    mu_clamp: float, mu_thread: float, eccentricity: float = CLAMP_ECCENTRICITY_MAX
) -> float:
    """Preload, the pull's bending, the clamp couple and the residual torsion:
    worst nominal von Mises SF against yield over sections, brackets and
    splits."""
    preload = clamp_preload_n(mu_clamp)
    torsion = RESIDUAL_TORSION_FACTOR * thread_torque_n_mm(preload, mu_thread)
    couple = preload * eccentricity
    return min(
        _von_mises_sf(preload, moment(x) + couple, torsion, dia)
        for x0, x1, dia in _SECTIONS
        for x in _peak_stations(x0, x1)
        for moment in _MOMENT_CASES
    )


def tightening_safety_factor(
    mu_clamp: float, mu_thread: float, eccentricity: float = CLAMP_ECCENTRICITY_MAX
) -> float:
    """Preload, the clamp couple and the full thread torsion, on the estimated
    deepest root."""
    preload = clamp_preload_n(mu_clamp)
    torsion = thread_torque_n_mm(preload, mu_thread)
    return _von_mises_sf(
        preload, preload * eccentricity, torsion, THREAD_MINOR_2A_MIN_EST
    )


_SERVICE_SF_EXACT = {pair: service_safety_factor(*pair) for pair in FRICTION_PAIRS}
_TIGHTENING_SF_EXACT = {
    pair: tightening_safety_factor(*pair) for pair in FRICTION_PAIRS
}
# The criterion is NOMINAL von Mises stress against yield, on smooth sections
# at the deepest estimated root and the smallest body.  The die-cut root and
# the under-head corner raise local stress above it, and local first yield
# there is accepted: the screw is a statically loaded clamp of ductile steel
# (4140 at HRC 32, 7 % elongation, McMaster 6818T53), so a notch root yields
# locally and redistributes, and the #1951 sketches reported their SFs as
# nominal on that basis.  Fatigue does not govern: the summing lever is
# quasi-static and the pull swings about +/-1.2 N about a 46.9-47.1 N service
# load (#1951 sketch), so first-load yield at the low-friction preload sets
# the margin.  Acceptance reads the unrounded factors; the rounded tables are
# for print.
if min((*_SERVICE_SF_EXACT.values(), *_TIGHTENING_SF_EXACT.values())) < (
    STRENGTH_SF_TARGET
):
    raise AssertionError(
        f"MHA-SM-04 clamp strength SF service {_SERVICE_SF_EXACT}, tightening "
        f"{_TIGHTENING_SF_EXACT} under {STRENGTH_SF_TARGET}"
    )
SERVICE_SF = {pair: round(sf, 3) for pair, sf in _SERVICE_SF_EXACT.items()}
TIGHTENING_SF = {pair: round(sf, 3) for pair, sf in _TIGHTENING_SF_EXACT.items()}
OVERTIGHTEN_MARGIN = min(_TIGHTENING_SF_EXACT.values())

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HeadProfile": {"HeadDia", "HeadHeight", "HeadReliefChamfer"},
    "ShankProfile": {
        "UnderHeadLength",
        "BodyDia",
        "TipChamfer",
        "UnderHeadCornerR",
    },
    "SlotProfile": {"SlotWidth"},
    "DriverSlot": {"SlotDepth"},
    "StationReference": {"OverallLength", "PlainLength", "FullThread"},
}
# Inch places (#290): three on the LIMIT bands and the full-thread and corner
# single limits (sm_gooseneck_spring_screw_geom.THREE_PLACE_DIMENSIONS), two
# on every other mark, the tip chamfer's among them (an .X band, +/-.1, would
# be five chamfers wide).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: places(name) for name in sorted(names)}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: digits
    for dimensions in DRAWING_PRECISION.values()
    for name, digits in dimensions.items()
}
# The overall length is the stock cut-off, a restatement of the head height
# and under-head length.
REFERENCE_DIMENSIONS = frozenset({"OverallLength"})

# The fitter's clamp step (user ruling 2026-09-21: no torque value, no
# threadlocker) prints on the summing assembly sheet as MHA-SM-00 step 8,
# not here: a part sheet carries no assembly instruction (machinist review
# 2026-10-23).  The plain length and the full-thread limit print on their
# features (machinist FIX round 1), so one note is left.
DRAWING_NOTES = f"1. THREAD MATES THE TAPPED END PIECE OF {PLUG_NUMBER}."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 2:1"
