r"""Pure-data dimensional contract shared by the fulcrum shaft, its drawing and
the channel assembly that places it.

The plain Ø.250 steel shaft the top levers rock on. It runs full length at
one diameter (no journals, shoulders or steps) through the reamed bores of the
two end keepers (MHA-CH-07, ``ch_fulcrum_keeper_spec``); each end stands
END_PROUD past its keeper lug's outer face and finishes in a hemispherical
dome (the bright dome of the ch. 17 p. 40 photo). One set-screw flat per end,
both on +Y, sits under the keeper's crown tap on the lug mid-plane: the two
cup-point set screws (MHA-CH-VN-55) bearing on them are the shaft's only axial
and rotational location.

Part frame: axis along Z, centred on z = 0 (the assembly places the origin at
ch_fulcrum_keeper_spec.FULCRUM_KEEPER_CENTRE_Z); the flats face +Y.
"""

from __future__ import annotations

from math import sqrt

import _config
from _fit_shaft_h import SHAFT_H
from _gtol_cylinder import CylinderFace
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from ch_fulcrum_keeper_spec import (
    BORE_DIA,
    BORE_DIA_BAND,
    BORE_RUNNING_MIN_CLEARANCE_MM,
    BORE_SEAT_ALLOWANCE_MM,
    CROWN_R,
    KEEPER_FITUP_LOCATION_BAND_MM,
    KEEPER_Z_OFF,
    LUG_HALF_T,
    SET_SCREW_MIN_ENGAGEMENT_D,
    SET_SCREW_PITCH,
    crown_least_height,
)
from ch_fulcrum_keeper_spec import DRAWING_PRECISION as KEEPER_PRECISION
from ch_vn_fulcrum_set_screw_spec import CUP_DIA as SET_SCREW_CUP_DIA
from ch_vn_fulcrum_set_screw_spec import LENGTH as SET_SCREW_LENGTH
from ch_vn_fulcrum_set_screw_spec import MAJOR_DIA as SET_SCREW_MAJOR_DIA
from ch_vn_fulcrum_set_screw_spec import POINT_LENGTH as SET_SCREW_POINT_LENGTH

MM_PER_IN = 25.4
# #290: the sheet prints decimal inch (the row's ``drawing_unit``); lengths
# stay millimetres, each the exact decimal of its printed inch value.
UNIT = drawing_unit("parts/ch-fulcrum-shaft", _config.parts("ch-fulcrum-shaft"))

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_DIA_BAND = SHAFT_H
if SHAFT_DIA != BORE_DIA:
    raise AssertionError("fulcrum shaft and keeper bore nominals differ")
SHAFT_R = SHAFT_DIA / 2.0

# --- Length: cylindrical to END_PROUD past each keeper lug's outer face, then
# a full hemisphere (radius = shaft radius). END_PROUD puts the tip-to-tip
# length on the .XX grid and keeps both domes clear of the bores
# (FLAT_STATION_WINDOW_MM below). ---
END_PROUD = 1.016  # .040
CYLINDER_HALF = KEEPER_Z_OFF + LUG_HALF_T + END_PROUD  # 80.137
DOME_R = SHAFT_R
SHAFT_LENGTH = 2.0 * (CYLINDER_HALF + DOME_R)  # 166.624 (6.56) tip to tip

# --- Set-screw flats: one per end on +Y, centred on the keeper lug mid-plane
# (z = +-KEEPER_Z_OFF), so the crown tap's cup point lands mid-flat. Both
# stations are baseline dimensions from the -Z dome tip (sheet left): the -Z
# flat's outer edge FLAT_FROM_END off it and the +Z flat's inner edge
# FLAT_BASELINE off it, so no station chains through another. .17 long, in
# the .32 lug; with the lug's .XX bands in the chain both stations, the flat
# length and the overall length print .XX (FLAT_STATION_WINDOW_MM). ---
FLAT_PITCH = 2.0 * KEEPER_Z_OFF  # 150.114 (5.910) centre to centre (assembly only)
FLAT_LENGTH = 4.318  # .17
FLAT_DEPTH = 0.3048  # .012
FLAT_FROM_END = SHAFT_LENGTH / 2.0 - FLAT_PITCH / 2.0 - FLAT_LENGTH / 2.0  # 6.096 (.24)
FLAT_BASELINE = (
    SHAFT_LENGTH / 2.0 + FLAT_PITCH / 2.0 - FLAT_LENGTH / 2.0
)  # 156.21 (6.15)
ACROSS_FLAT = SHAFT_DIA - FLAT_DEPTH  # 6.0452 (.238): the printed size
FLAT_HEIGHT = SHAFT_R - FLAT_DEPTH  # 2.8702: the set screw's cup seat above the axis

# --- Worst case of the printed bands (drawing-guidelines.md rule 17 (walls
# and webs); DRAWING_PRECISION below, inch title block). ---
_BAND_BY_PLACES = {places: printed_band_mm(places, unit=UNIT) for places in (1, 2, 3)}
_SHAFT_R_MIN = (SHAFT_DIA + SHAFT_DIA_BAND[1]) / 2.0
# Least depth: the smallest printed shaft diameter less the largest AcrossFlat
# (the print controls those two, never the depth itself).
_FLAT_DEPTH_MIN = 2.0 * _SHAFT_R_MIN - (ACROSS_FLAT + _BAND_BY_PLACES[3])
# The shallowest flat must still be wider than the set screw's thread, so its
# cup burr lands on the flat and the shaft withdraws past the bore.
FLAT_CHORD_MIN = 2.0 * sqrt(2.0 * _SHAFT_R_MIN * _FLAT_DEPTH_MIN - _FLAT_DEPTH_MIN**2)
if FLAT_CHORD_MIN <= SET_SCREW_MAJOR_DIA:
    raise AssertionError(
        f"shallowest flat is {FLAT_CHORD_MIN:.3f} wide, under the set screw's "
        f"{SET_SCREW_MAJOR_DIA} major"
    )
# The longest flat stays inside its keeper lug, so a lever hub never rides it.
if FLAT_LENGTH + _BAND_BY_PLACES[2] > 2.0 * LUG_HALF_T:
    raise AssertionError("the longest set-screw flat runs out of the keeper lug")
if KEEPER_Z_OFF + FLAT_LENGTH / 2.0 >= CYLINDER_HALF:
    raise AssertionError("set-screw flat runs onto the domed end")

# Installed set screw (drawing-guidelines.md rule 18 (thread engagement): >= 1.5D of FULL thread at the worst
# case). Heights are above the keeper bore axis: the set screw pulls the shaft
# down onto the bore wall, so its flat sits AcrossFlat - bore radius up. The
# tap's full thread runs from the bore top (plus the keeper spec's
# conservative bore sag) to the crown's least height across the thread (the
# least full round over a bore off the width's centre plane,
# crown_least_height) less one entry-chamfer pitch; the screw's full thread
# starts one cup chamfer above its seat on the flat.
_SCREW_HALF_MAJOR = SET_SCREW_MAJOR_DIA / 2.0


def _sag(radius: float) -> float:
    return radius - sqrt(radius**2 - _SCREW_HALF_MAJOR**2)


_BORE_R_MAX = (BORE_DIA + BORE_DIA_BAND[0]) / 2.0
_BORE_R_MIN = (BORE_DIA + BORE_DIA_BAND[1]) / 2.0
_TAP_FULL_TOP = crown_least_height(_SCREW_HALF_MAJOR) - SET_SCREW_PITCH
_TAP_FULL_BOTTOM = _BORE_R_MAX + _sag(_BORE_R_MAX)
_SEAT_LOW = ACROSS_FLAT - _BAND_BY_PLACES[3] - _BORE_R_MAX
_SEAT_HIGH = ACROSS_FLAT + _BAND_BY_PLACES[3] - _BORE_R_MIN
SET_SCREW_ENGAGEMENT_MM = min(
    min(_TAP_FULL_TOP, seat + SET_SCREW_LENGTH)
    - max(_TAP_FULL_BOTTOM, seat + SET_SCREW_POINT_LENGTH)
    for seat in (_SEAT_LOW, _SEAT_HIGH)
)
SET_SCREW_ENGAGEMENT_D = SET_SCREW_ENGAGEMENT_MM / SET_SCREW_MAJOR_DIA
if SET_SCREW_ENGAGEMENT_D < SET_SCREW_MIN_ENGAGEMENT_D:
    raise AssertionError(
        f"installed set screw engages {SET_SCREW_ENGAGEMENT_D:.2f}D of full "
        f"thread at the worst case (< {SET_SCREW_MIN_ENGAGEMENT_D}D)"
    )
# Socket face above the crown over the tap axis: below it at nominal; the
# ruling lets it stand up to 0.4 proud in free air at the worst case (Main
# ruling A, 2026-10-10; ch_vn_fulcrum_set_screw_spec), the least round over a
# bore off the width's centre plane.
SET_SCREW_PROUD_NOMINAL = FLAT_HEIGHT + SET_SCREW_LENGTH - CROWN_R
SET_SCREW_PROUD_WORST = _SEAT_HIGH + SET_SCREW_LENGTH - crown_least_height(0.0)
if SET_SCREW_PROUD_NOMINAL >= 0.0 or SET_SCREW_PROUD_WORST > 0.4:
    raise AssertionError("set screw stands proud of the keeper crown past the ruling")

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "bearing", MACHINED_UM, CylinderFace(SHAFT_DIA), display_unit=UNIT
    ),
)

# One revolved half-profile carries the diameter and the tip-to-tip length;
# the flats' cut sketch carries their length, both stations off the -Z dome
# tip (a construction line from the origin to the tip), the across-flat size
# (a construction line from the flat to the far O.D.) and the dome radius (a
# construction arc on the -Z dome, printed as a reference).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia", "OverallLength"},
    "FlatProfile": {
        "FlatLength",
        "FlatFromEnd",
        "FlatBaseline",
        "AcrossFlat",
        "DomeRadius",
    },
}
# Decimal places are the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`); the model owns
# them, in inches. ShaftDia carries its SHAFT_H band natively at four places;
# AcrossFlat at .XXX holds FLAT_CHORD_MIN above the set screw's major and its
# >= 1.5D engagement and proud ruling. FlatFromEnd, FlatBaseline, FlatLength
# and OverallLength at .XX hold FLAT_STATION_WINDOW_MM open (inch .X is far
# too loose for it). DomeRadius is a reference (.125): the full hemisphere
# follows from the diameter.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDia": 4, "OverallLength": 2},
    "FlatProfile": {
        "FlatLength": 2,
        "FlatFromEnd": 2,
        "FlatBaseline": 2,
        "AcrossFlat": 3,
        "DomeRadius": 3,
    },
}
if {
    feature: set(names) for feature, names in DRAWING_PRECISION.items()
} != DRAWING_DIMENSIONS:
    raise AssertionError(
        "DRAWING_PRECISION and DRAWING_DIMENSIONS must name the same dims"
    )
# One flat length and one across-flat size govern both flats (the cut sketch
# carries one of each), so each prints "2X". DomeRadius gets its "2X (SR" in
# the drawing, which keeps the native radius symbol.
DIMENSION_PREFIXES = {
    ("FlatProfile", "FlatLength"): "2X ",
    ("FlatProfile", "AcrossFlat"): "2X ",
}


# --- Flat stations, at the worst case of every printed band and of the
# MHA-CH-00 fit-up (drawing-guidelines.md rule 19 (absorb stacks at fit-up, not with tighter bands)). The keepers go on the frame with their
# lug inner faces DRO-set (KEEPER_FITUP_LOCATION_BAND_MM each); each tap
# stands SetScrewLocation off its lug's inner face, as the keeper prints it,
# and the lug is LugThickness thick. The shaft is free to slide until both
# screws bite, so it needs ONE
# axial place where at once: each cup lies wholly on its flat; each flat's
# inner edge stays inside its lug (no lever hub rides a flat); and the
# cylinder runs out past both lug outer faces (the domes never bear in a
# bore). With t the -Z dome tip, every requirement is a bound t >= lo or
# t <= hi linear in the bands, so the window is the least, over every
# (hi, lo) pair, of its nominal less the pair's summed band reach.
def _band(precision: dict[str, dict[str, int]], feature: str, name: str) -> float:
    return _BAND_BY_PLACES[precision[feature][name]]


_STATION_BANDS = {
    "front_face": KEEPER_FITUP_LOCATION_BAND_MM,
    "rear_face": KEEPER_FITUP_LOCATION_BAND_MM,
    "front_lug": _band(KEEPER_PRECISION, "LugBody", "LugThickness"),
    "rear_lug": _band(KEEPER_PRECISION, "LugBody", "LugThickness"),
    "front_tap": _band(KEEPER_PRECISION, "SetScrewReference", "SetScrewLocation"),
    "rear_tap": _band(KEEPER_PRECISION, "SetScrewReference", "SetScrewLocation"),
    "flat_from_end": _band(DRAWING_PRECISION, "FlatProfile", "FlatFromEnd"),
    "front_flat": _band(DRAWING_PRECISION, "FlatProfile", "FlatLength"),
    "rear_flat": _band(DRAWING_PRECISION, "FlatProfile", "FlatLength"),
    "flat_baseline": _band(DRAWING_PRECISION, "FlatProfile", "FlatBaseline"),
    "length": _band(DRAWING_PRECISION, "ShaftProfile", "OverallLength"),
}


def _lin(nominal: float, **terms: float) -> dict[str, float]:
    """A position: its nominal ("") and its coefficient on each band term."""
    return {"": nominal, **terms}


def _sum(*forms: tuple[float, dict[str, float]]) -> dict[str, float]:
    """``sum(sign * form)`` over (sign, form) pairs."""
    total: dict[str, float] = {}
    for sign, form in forms:
        for key, value in form.items():
            total[key] = total.get(key, 0.0) + sign * value
    return total


def _worst(form: dict[str, float]) -> float:
    return form[""] - sum(
        abs(coef) * _STATION_BANDS[key] for key, coef in form.items() if key
    )


_INNER = KEEPER_Z_OFF - LUG_HALF_T
_inner_front = _lin(-_INNER, front_face=1.0)
_inner_rear = _lin(_INNER, rear_face=1.0)
_outer_front = _sum((1, _inner_front), (-1, _lin(2.0 * LUG_HALF_T, front_lug=1.0)))
_outer_rear = _sum((1, _inner_rear), (1, _lin(2.0 * LUG_HALF_T, rear_lug=1.0)))
_tap_front = _sum((1, _inner_front), (-1, _lin(LUG_HALF_T, front_tap=1.0)))
_tap_rear = _sum((1, _inner_rear), (1, _lin(LUG_HALF_T, rear_tap=1.0)))
_from_end = _lin(FLAT_FROM_END, flat_from_end=1.0)
_front_len = _lin(FLAT_LENGTH, front_flat=1.0)
_rear_len = _lin(FLAT_LENGTH, rear_flat=1.0)
_baseline = _lin(FLAT_BASELINE, flat_baseline=1.0)
_length = _lin(SHAFT_LENGTH, length=1.0)
_cup = _lin(SET_SCREW_CUP_DIA / 2.0)
_dome = _lin(DOME_R)
# Bounds on t: front flat [t + S, t + S + FLf]; rear flat [t + B, t + B +
# FLr]; rear tip t + L.
_T_LOW = {
    "front cup on its flat's inner end": _sum(
        (1, _tap_front), (1, _cup), (-1, _from_end), (-1, _front_len)
    ),
    "rear cup on its flat's outer end": _sum(
        (1, _tap_rear), (1, _cup), (-1, _baseline), (-1, _rear_len)
    ),
    "rear flat inside its lug": _sum((1, _inner_rear), (-1, _baseline)),
    "rear cylinder past its lug": _sum((1, _outer_rear), (1, _dome), (-1, _length)),
}
_T_HIGH = {
    "front cup on its flat's outer end": _sum(
        (1, _tap_front), (-1, _cup), (-1, _from_end)
    ),
    "rear cup on its flat's inner end": _sum(
        (1, _tap_rear), (-1, _cup), (-1, _baseline)
    ),
    "front flat inside its lug": _sum(
        (1, _inner_front), (-1, _from_end), (-1, _front_len)
    ),
    "front cylinder past its lug": _sum((1, _outer_front), (-1, _dome)),
}
FLAT_STATION_WINDOW_MM = min(
    _worst(_sum((1, high), (-1, low)))
    for high in _T_HIGH.values()
    for low in _T_LOW.values()
)
if FLAT_STATION_WINDOW_MM <= 0.0:
    raise AssertionError(
        f"no shaft station seats both cups at the worst case "
        f"({FLAT_STATION_WINDOW_MM:.3f})"
    )

# --- The keepers' bores, drilled and reamed through in one pass at their
# installed spacing (ch_fulcrum_keeper_spec.BORE_PAIR_CALLOUT, assembly step
# fulcrum-keepers-pair-reamed): bored apart, the .XX LugRise could put the bores
# BORE_OFFSET_UNPAIRED_MM out of line, past the fit's largest diametral
# clearance; reamed together they are one straight line, gauged by this
# shaft in the clamped setup. What remains is the rail under the two feet:
# within the keeper spec's seat-flatness budget each lug spends
# BORE_SEAT_ALLOWANCE_MM of its clearance on the straight shaft, and the rest
# must still be the running minimum.
BORE_OFFSET_UNPAIRED_MM = 2.0 * _band(KEEPER_PRECISION, "LugProfile", "LugRise")
PAIRED_MIN_CLEARANCE_MM = (
    BORE_DIA_BAND[1] - SHAFT_DIA_BAND[0] - BORE_SEAT_ALLOWANCE_MM
)  # 0.0103
if BORE_OFFSET_UNPAIRED_MM <= BORE_DIA_BAND[0] - SHAFT_DIA_BAND[1]:
    raise AssertionError("the keeper bores line up unpaired: drop the pair reaming")
if PAIRED_MIN_CLEARANCE_MM < BORE_RUNNING_MIN_CLEARANCE_MM:
    raise AssertionError(
        f"the paired keeper bores keep {PAIRED_MIN_CLEARANCE_MM:.4f} on the shaft "
        f"after the rail-seat allowance {BORE_SEAT_ALLOWANCE_MM:.4f} "
        f"(< {BORE_RUNNING_MIN_CLEARANCE_MM})"
    )

# The shaft is the first-made part of the keeper fit (rule 4: the band lives
# here, the bore's .XXX is the mate's), and the levers run on the same O.D.
SHAFT_FIT_CLEARANCE_MM = (
    BORE_DIA_BAND[1] - SHAFT_DIA_BAND[0],
    BORE_DIA_BAND[0] - SHAFT_DIA_BAND[1],
)  # (0.0381, 0.07112), .0015-.0028 in
# No line ends in punctuation: the widest row ends on the dimension's
# vertical leader, and a trailing ';' touched it (machinist review r2).
SHAFT_DIA_CALLOUT = "\n".join(
    (
        "SLIDING FIT IN MHA-CH-07 BORES",
        "-".join(
            f"{value / MM_PER_IN:.4f}".removeprefix("0")
            for value in SHAFT_FIT_CLEARANCE_MM
        )
        + " DIAMETRAL CLEARANCE",
        "MHA-CH-02 LEVERS RUN ON IT",
    )
)
# AcrossFlat's .XXX is the set screw's seat height: it sets both the >= 1.5D
# engagement and the proud limit above (a .XX band breaks both).
ACROSS_FLAT_CALLOUT = "SETS MHA-CH-VN-55\nENGAGEMENT"
DRAWING_NOTES = "\n".join(
    (
        "1/4 IN GROUND STOCK OK.",
        "CENTRE MARKS .04 DEEP MAX.",
    )
)
# The isometric renders at ISO_SCALE (1, 1) while the sheet/title block reads
# 2:1, so without this the pictorial is silently half scale.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
