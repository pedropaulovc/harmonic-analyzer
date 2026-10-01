r"""MHA-159 transgear-disc-hub: the brass hub and flange behind the 120T disc.

Contract §2.4 (round 10): a Ø12.9 turned hub pressed on the pinion sleeve's
(MHA-110) Ø8.2 front shank, with a Ø21 × 2.4 flange whose rear face seats the
120T disc (MHA-070).  Three #0-80 fillister screws (MHA-161) pass the
flange's Ø1.7 holes into the disc's taps (``transgear_disc_hub_geometry``;
the taps are spotted through these holes at assembly, R9-9).  A Ø1.2 radial
oil hole on +Y reaches the bore; it is drilled through the hub wall and the
sleeve in one operation after pressing (R9-8), so the sheet carries a
match-drill note, not a free drilled hole.

Printed lengths (R9-5): the overall, flange rear face to hub front face,
9.400 .XXX (it keeps the hub behind the sleeve nose), and the flange 2.400
.XXX (the screw-tip-to-platen stack reads it).  The hub body's own length is
their remainder and is not printed.

Local frame (the build's, and the one the assembly mates): the gear axis is
Z through the origin (``Axis1``).  ``Front Plane`` (z = 0) is the flange's
rear face, the face that seats on the disc's front face; the flange runs
z = -2.4..0 and the hub body z = -9.4..-2.4, so local -Z is the machine's
-Z (toward the operator).  Screw 0° is local +X, angles counter-clockwise
seen from +Z; the oil hole is on local +Y at z = -5.9, 3.5 behind the hub's
front face.  The part sits in the machine unrotated at z0 = -147.65.

Pure data; no SolidWorks calls.
"""

from __future__ import annotations

import math

from _fit_limits import deviations
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES
from transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_PLACES,
    BOLT_CIRCLE_POSITION_TOL,
    SCREW_COUNT,
)

# The mating parts the sheet names.
SLEEVE_NUMBER = "MHA-110"  # transgear pinion sleeve: the Ø8.2 front shank
DISC_NUMBER = "MHA-070"

# --- screw (MHA-161, McMaster 91794A055) ------------------------------------
SCREW_SKU = "91794A055"
SCREW_MAJOR_DIA, SCREW_LENGTH, SCREW_HEAD_H, SCREW_HEAD_DIA, _SCREW_PITCH = (
    FILLISTER_SIZES[SCREW_SKU]
)
# Head diameter allowance over the catalogue size (contract §8, "head +0.05").
SCREW_HEAD_DIA_ALLOWANCE = 0.05

# --- turned body ------------------------------------------------------------
FLANGE_DIA = 21.0
FLANGE_DIA_PLACES = 2  # prints .XX: the hole-to-rim stack reads it
FLANGE_THICK = 2.4
FLANGE_THICK_PLACES = 3  # the screw-tip-to-platen stack reads it (R9-5)
HUB_DIA = 12.9
HUB_DIA_PLACES = 2
# Overall, flange rear face to hub front face: keeps the hub behind the
# sleeve nose at the worst case (R9-5), so it prints .XXX.
HUB_LENGTH = 9.4
HUB_LENGTH_PLACES = 3
# The hub body (flange front face to hub front face) is the remainder of the
# two printed lengths; it is modelled, never printed.
HUB_BODY_LENGTH = HUB_LENGTH - FLANGE_THICK
# Pressed on the sleeve's Ø8.2 front shank (line to line modelled).  Both
# printed .XXX ±0.13, the pair ran from 0.26 clearance to 0.26 interference,
# and the press is all that holds the flange's clamp on the disc and carries
# its torque (R9-45).  So this module owns the pair, as rack_pinion_spec owns
# the disc's slip pair: the bore is reamed to ISO H7 at 6-10 mm, and the
# sleeve's shank turned to a SHAFT_H-wide band above it (its model reads
# SHANK_DIA_BAND here), for 0.010-0.045 diametral interference -- close to
# ANSI FN2 at this size (0.013-0.041), never line to line.
BORE_DIA = 8.2
BORE_PLACES = 3
BORE_BAND = (0.015, 0.0)  # (upper, lower) deviations, reamed
BORE_DEVIATIONS = deviations(BORE_BAND)
SHANK_DIA = BORE_DIA
SHANK_DIA_BAND = (0.045, 0.025)  # (upper, lower) deviations, turned
PRESS_INTERFERENCE_FLOOR = 0.010  # the fleet's light-press floor (crank hub)
# (least, greatest) diametral interference.
PRESS_INTERFERENCE = (
    round(SHANK_DIA + SHANK_DIA_BAND[1] - (BORE_DIA + BORE_BAND[0]), 3),
    round(SHANK_DIA + SHANK_DIA_BAND[0] - (BORE_DIA + BORE_BAND[1]), 3),
)
if PRESS_INTERFERENCE[0] < PRESS_INTERFERENCE_FLOOR - 1e-9:
    raise AssertionError(
        f"MHA-159 bore loses its press on the MHA-110 shank: {PRESS_INTERFERENCE}"
    )
# The hub-to-flange corner stays sharp: the #0-80 heads sit beside it.
CORNER_RADIUS_MAX = 0.1

# --- drilled holes (the title block's DRILLED HOLES row, +0.10/0) -----------
DRILL_OVERSIZE = drilled_oversize_mm()
SCREW_HOLE_DIA = 1.7
SCREW_HOLE_PLACES = 1
OIL_HOLE_DIA = 1.2
OIL_HOLE_PLACES = 1
# Oil-hole station from the hub's FRONT face, at the .X default (R9-8).
OIL_HOLE_STATION = 3.5
OIL_HOLE_STATION_PLACES = 1
OIL_HOLE_Z = -(HUB_LENGTH - OIL_HOLE_STATION)  # -5.9 in the local frame

_BAND = {places: printed_band_mm(places) for places in (1, 2, 3)}


def _floor2(value: float) -> float:
    """Round DOWN to the 0.01 a MIN note prints: never more than the limits give."""
    return math.floor(value * 100.0 + 1e-9) / 100.0


def _largest_dia(nominal: float, places: int) -> float:
    return nominal + _BAND[places]


def _smallest_dia(nominal: float, places: int) -> float:
    return nominal - _BAND[places]


# --- worst-case walls at the printed bands (policy rule 12) ------------------
HUB_WALL_NOMINAL = (HUB_DIA - BORE_DIA) / 2.0
_BORE_MAX = BORE_DIA + BORE_BAND[0]
HUB_WALL_WORST = (_smallest_dia(HUB_DIA, HUB_DIA_PLACES) - _BORE_MAX) / 2.0

_SCREW_HOLE_MAX_R = (SCREW_HOLE_DIA + DRILL_OVERSIZE) / 2.0
_OIL_HOLE_MAX_R = (OIL_HOLE_DIA + DRILL_OVERSIZE) / 2.0
_BC_R_MAX = BOLT_CIRCLE_DIA / 2.0 + BOLT_CIRCLE_POSITION_TOL
_BC_R_MIN = BOLT_CIRCLE_DIA / 2.0 - BOLT_CIRCLE_POSITION_TOL

HOLE_TO_RIM_NOMINAL = FLANGE_DIA / 2.0 - BOLT_CIRCLE_DIA / 2.0 - SCREW_HOLE_DIA / 2.0
HOLE_TO_RIM_WORST = _floor2(
    _smallest_dia(FLANGE_DIA, FLANGE_DIA_PLACES) / 2.0 - _BC_R_MAX - _SCREW_HOLE_MAX_R
)
HOLE_TO_BORE_WORST = _BC_R_MIN - _SCREW_HOLE_MAX_R - _BORE_MAX / 2.0
# The station is dimensioned from the hub front face itself: no length stack.
OIL_HOLE_TO_FRONT_NOMINAL = OIL_HOLE_STATION - OIL_HOLE_DIA / 2.0
OIL_HOLE_TO_FRONT_WORST = (
    OIL_HOLE_STATION - _BAND[OIL_HOLE_STATION_PLACES] - _OIL_HOLE_MAX_R
)
# Toward the flange the hole edge meets the flange's front face, which is
# backed by the whole flange: an edge distance, not a web.
OIL_HOLE_TO_FLANGE_WORST = (
    _smallest_dia(HUB_LENGTH, HUB_LENGTH_PLACES)
    - (FLANGE_THICK + _BAND[FLANGE_THICK_PLACES])
    - (OIL_HOLE_STATION + _BAND[OIL_HOLE_STATION_PLACES])
    - _OIL_HOLE_MAX_R
)

# Heads beside the hub body: a clearance (contract §2.4, default 4), not a web.
HEAD_TO_HUB_NOMINAL = BOLT_CIRCLE_DIA / 2.0 - SCREW_HEAD_DIA / 2.0 - HUB_DIA / 2.0
HEAD_TO_HUB_WORST = (
    _BC_R_MIN
    - (SCREW_HEAD_DIA + SCREW_HEAD_DIA_ALLOWANCE) / 2.0
    - _largest_dia(HUB_DIA, HUB_DIA_PLACES) / 2.0
)

WALL_FLOOR = 2.0
for _label, _wall in (
    ("hub wall over the bore", HUB_WALL_WORST),
    ("screw hole to bore", HOLE_TO_BORE_WORST),
    ("oil hole to hub front face", OIL_HOLE_TO_FRONT_WORST),
):
    if _wall < WALL_FLOOR - 1e-9:
        raise AssertionError(
            f"MHA-159 {_label}: {_wall:.3f} worst < floor {WALL_FLOOR}"
        )
if OIL_HOLE_TO_FLANGE_WORST <= 0.0:
    raise AssertionError(
        f"MHA-159 oil hole breaks into the flange: {OIL_HOLE_TO_FLANGE_WORST:.3f}"
    )
if HEAD_TO_HUB_WORST <= 0.0:
    raise AssertionError(
        f"MHA-159 screw heads can touch the hub body: {HEAD_TO_HUB_WORST:.3f}"
    )
# The named exception stays a shortfall only while the rim is thin; if the
# flange ever grows, the MIN note and its policy row must go.
if not 0.0 < HOLE_TO_RIM_WORST < WALL_FLOOR:
    raise AssertionError(f"MHA-159 hole to rim {HOLE_TO_RIM_WORST:.2f} is no exception")

# --- sheet --------------------------------------------------------------------
# Named exception: MHA-159 hole to rim (drawing-simplicity-policy.md, "Named exceptions").
HOLE_TO_RIM_NOTE = f"SCREW HOLE TO RIM {HOLE_TO_RIM_WORST:.2f} MIN."
CORNER_NOTE = f"HUB-TO-FLANGE CORNER SHARP, R{CORNER_RADIUS_MAX:.1f} MAX."
DRAWING_NOTES = "\n".join((HOLE_TO_RIM_NOTE, CORNER_NOTE))

# Callouts the sheet hangs on the native dimensions.  The holes are drilled
# (the title block's DRILLED HOLES row governs their sizes); the three screw
# holes are one patterned feature, equally spaced on the printed circle.  The
# oil hole is drilled with the hub pressed on the sleeve, through both: the
# crank pinion's pin-hole wording (crank_pinion_spec.pin_hole_note).
SCREW_HOLE_CALLOUT_ABOVE = f"{SCREW_COUNT}X"
SCREW_HOLE_CALLOUT_BELOW = "DRILL THRU FLANGE, EQ SP"
OIL_HOLE_CALLOUT_BELOW = "\n".join(
    (
        f"MATCH DRILL AT ASSY WITH {SLEEVE_NUMBER}",
        "THRU HUB WALL AND SLEEVE AFTER PRESSING",
    )
)
# The bore's native limits print with the dimension; the callout adds the
# process, names the mate and states the interference the pair gives, in the
# crank hub's three short lines: a wider block hangs its leader off the
# block's far corner, across the hub diameter's shoulder (native leaf
# fc9c2d700, shoulder-crosses-line).
BORE_CALLOUT = "\n".join(
    (
        "REAM THRU",
        f"({PRESS_INTERFERENCE[0]:.3f}-{PRESS_INTERFERENCE[1]:.3f} DIAMETRAL",
        f"INTERFERENCE ON {SLEEVE_NUMBER})",
    )
)

# Marked model dimensions and the places the model authors on them (policy
# rule 2).  Face view: the four diameters and the bolt circle; edge view: the
# flange, the overall length, the oil-hole station and its size.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FlangeProfile": {"FlangeDia"},
    "Flange": {"FlangeThick"},
    "HubBodyProfile": {"HubDia"},
    "HubBody": {"HubLength"},
    "BoreProfile": {"BoreDia"},
    "ScrewHoleProfile": {"BoltCircleDia", "ScrewHoleDia"},
    "OilHoleProfile": {"OilHoleStation", "OilHoleDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FlangeProfile": {"FlangeDia": FLANGE_DIA_PLACES},
    "Flange": {"FlangeThick": FLANGE_THICK_PLACES},
    "HubBodyProfile": {"HubDia": HUB_DIA_PLACES},
    "HubBody": {"HubLength": HUB_LENGTH_PLACES},
    "BoreProfile": {"BoreDia": BORE_PLACES},
    "ScrewHoleProfile": {
        "BoltCircleDia": BOLT_CIRCLE_PLACES,
        "ScrewHoleDia": SCREW_HOLE_PLACES,
    },
    "OilHoleProfile": {
        "OilHoleStation": OIL_HOLE_STATION_PLACES,
        "OilHoleDia": OIL_HOLE_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
if {f: set(n) for f, n in DRAWING_PRECISION.items()} != DRAWING_DIMENSIONS:
    raise AssertionError("every marked MHA-159 dimension needs its printed places")
