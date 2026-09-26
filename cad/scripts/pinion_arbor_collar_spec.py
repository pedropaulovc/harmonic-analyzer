r"""Pure-data dimensional contract shared by the pinion-arbor collar and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  R1a (user, 2026-09-24): the collar is
bench-drilled and slides on MHA-102 from its back crown end before the arbor
is journaled; the rig's 1/16 in slotted spring pin, driven through both at
the arbor's printed pin station, fixes it there.  Its inboard face then
stands clear of the front MHA-056 strap's outer face at every corner of the
printed bands, so it never locates anything: if the drum's Loctite 638 bond
ever let go, it stops the arbor walking north (toward the back) after the
gap closes.  U27: the gap grows to absorb the .X bands, none is tightened.
"""

from __future__ import annotations

import math
from itertools import product

import pinion_strap_pin_spec as _pin
from pinion_arbor_collar_geometry import (
    BORE as BORE,
    COLLAR_LEN as COLLAR_LEN,
    COLLAR_OD as COLLAR_OD,
    PIN_HOLE_Z as PIN_HOLE_Z,
)
from pinion_arbor_spec import (
    DRUM_STATION,
    DRUM_STATION_BAND,
    LINEAR_X_BAND,
    PIN_STATION_BAND,
    PIN_STATION_FROM_HEAD_REAR,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    drum_total_air,
)
from pinion_bracket_geometry import THICKNESS as STRAP_T
from pinion_bracket_geometry import THICKNESS_BAND as STRAP_T_BAND

# The rig's one pin family (pinion_strap_pin_spec): a 1/16 x 1/2 slotted
# spring pin in a 1/16 drilled hole carrying its own functional band.
PIN_HOLE = _pin.HOLE_DIA
PIN_HOLE_BAND = _pin.HOLE_BAND
PIN_HOLE_MAX = _pin.HOLE_MAX
PIN_LEN = _pin.PIN_LEN  # 1/2 in: 1.15 sub-flush each side of the Ø15 OD
PIN_LEN_TOL = _pin.PIN_LEN_BAND

ARBOR_NUMBER = "MHA-102"
STRAP_NUMBER = "MHA-056"
# Drilled Ø8 slide fit over the arbor (Ø8 -0.01/-0.10, lands -0.01/-0.03).
# The title block's DRILLED HOLES row (+0.10/0) governs it and is NOT printed
# on the dimension (policy rule 1); the band is restated here only for the
# stacks below, and a test pins it to title_block.yaml's drilled_hole row.
BORE_BAND = (0.10, 0.0)  # (upper, lower) deviations
OD_BAND = LINEAR_X_BAND
LEN_BAND = LINEAR_X_BAND
# PinHoleCz prints at one place from one end face, independently of Depth.
PIN_HOLE_Z_BAND = LINEAR_X_BAND


def pin_to_face_distances() -> tuple[float, float]:
    """Least and greatest distance from the pin hole's axis to either end
    face, over every corner of the printed length and pin-station bands.

    The station is printed from one face (PinHoleCz), the other face sits the
    length away, and the collar goes on either way round, so both faces can
    end up inboard.
    """
    distances = []
    for length, station in product(
        (COLLAR_LEN - LEN_BAND, COLLAR_LEN + LEN_BAND),
        (PIN_HOLE_Z - PIN_HOLE_Z_BAND, PIN_HOLE_Z + PIN_HOLE_Z_BAND),
    ):
        distances.extend((station, length - station))
    return min(distances), max(distances)


PIN_TO_FACE_MIN, PIN_TO_FACE_MAX = pin_to_face_distances()
SLIDE_CLEARANCE_MIN = round(BORE + BORE_BAND[1] - (SHAFT_DIA + SHAFT_DIA_BAND[0]), 6)
if SLIDE_CLEARANCE_MIN <= 0.0:
    raise AssertionError("the collar no longer slides over the arbor")

MIN_GAP = 0.0  # the collar never touches the strap at rest


def collar_strap_gaps() -> tuple[float, float]:
    """Least and greatest air between the collar's inboard face and the front
    strap's outer face, over every corner of the printed bands.

    Stations run from MHA-102's head rear face toward the back.  The strap's
    outer face sits DRUM_STATION less the drum's front air and the strap
    thickness; the collar's inboard face sits one pin-to-face distance past
    the pin, and that distance runs over the length AND pin-station bands
    (pin_to_face_distances), not just half the length.
    """
    gaps = []
    for station, air, strap, pin, to_face in product(
        (DRUM_STATION - DRUM_STATION_BAND, DRUM_STATION + DRUM_STATION_BAND),
        drum_total_air(),
        (STRAP_T - STRAP_T_BAND, STRAP_T + STRAP_T_BAND),
        (
            PIN_STATION_FROM_HEAD_REAR - PIN_STATION_BAND,
            PIN_STATION_FROM_HEAD_REAR + PIN_STATION_BAND,
        ),
        (PIN_TO_FACE_MIN, PIN_TO_FACE_MAX),
    ):
        strap_outer = station - air - strap
        collar_inboard = pin + to_face
        gaps.append(strap_outer - collar_inboard)
    return min(gaps), max(gaps)


GAP_MIN, GAP_MAX = collar_strap_gaps()
GAP_NOMINAL = (
    DRUM_STATION - sum(drum_total_air()) / 2.0 - STRAP_T
) - (PIN_STATION_FROM_HEAD_REAR + COLLAR_LEN / 2.0)
if GAP_MIN <= MIN_GAP:
    raise AssertionError(f"collar can touch the front strap: gap {GAP_MIN:.3f}")

# Rule 12 webs at the printed worst case (U27 target 2.0, floor 1.5).
COLLAR_WALL_WORST = (COLLAR_OD - OD_BAND - (BORE + BORE_BAND[0])) / 2.0
PIN_TO_END_WEB_WORST = PIN_TO_FACE_MIN - PIN_HOLE_MAX / 2.0
for _name, _web in (
    ("collar wall", COLLAR_WALL_WORST),
    ("pin hole to collar end face", PIN_TO_END_WEB_WORST),
):
    if _web < 2.0:
        raise AssertionError(f"{_name} web {_web:.2f} is under the 2.0 target")

# The pin is never proud of the smallest OD, and still crosses the largest
# bore into both walls.
PIN_SUB_FLUSH_WORST = (COLLAR_OD - OD_BAND - (PIN_LEN + PIN_LEN_TOL)) / 2.0
PIN_WALL_ENGAGEMENT_WORST = (PIN_LEN - PIN_LEN_TOL) / 2.0 - (BORE + BORE_BAND[0]) / 2.0
if PIN_SUB_FLUSH_WORST <= 0.0:
    raise AssertionError("the spring pin can stand proud of the collar")
if PIN_WALL_ENGAGEMENT_WORST < 1.5:
    raise AssertionError("the spring pin barely reaches the collar wall")
if not math.isclose(PIN_HOLE_Z, COLLAR_LEN / 2.0):
    raise AssertionError("the pin hole must stay centred on the collar length")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd"},
    "BoreProfile": {"BoreDia"},
    "Collar": {"Depth"},
    # Rule 7: the pin station is printed from a finished end face.
    "PinHoleProfile": {"PinHoleDia", "PinHoleCz"},
}
# The MODEL owns every printed place (policy rule 2).  Two on the two drilled
# fits (their bands ride the dimensions), one everywhere else.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CollarProfile": {"CollarOd": 1},
    "BoreProfile": {"BoreDia": 2},
    "Collar": {"Depth": 1},
    "PinHoleProfile": {"PinHoleDia": 2, "PinHoleCz": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked collar dimension needs authored places")

# The pin is the stock MHA-145 (McMaster 98296A027): its own BOM line and a
# modelled drive-train component.  So the collar sheet carries no supply note
# (the MHA-056 strap precedent); the hole callout names the pin it takes.
PIN_NUMBER = "MHA-145"
PIN_HOLE_CALLOUT = f"{_pin.DRILL_THRU_CALLOUT}\nFOR {PIN_NUMBER} SPRING PIN"
BORE_CALLOUT = f"DRILL THRU\nSLIDES ON {ARBOR_NUMBER}"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

