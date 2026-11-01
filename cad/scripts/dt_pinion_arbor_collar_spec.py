r"""Pure-data dimensional contract shared by the pinion-arbor collar and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  R1a (user, 2026-09-24): the collar is
bench-drilled and slides on MHA-DT-22 from its back crown end before the arbor
is journaled; the rig's 1/16 in slotted spring pin, driven through both at
the arbor's printed pin station, fixes it there.  Its inboard face then
stands clear of the front MHA-DT-14 strap's outer face at every corner of the
printed bands, so it never locates anything: if the drum's Loctite 638 bond
ever let go, it stops the arbor walking north (toward the back) after the
gap closes.  U27: the gap grows to absorb the bands, none is tightened.
"""

from __future__ import annotations

import math
from itertools import product

import _config
from _package_units import drawing_unit
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import (
    drilled_oversize_mm,
    drilled_undersize_mm,
    printed_band_mm,
)

import dt_vn_pinion_strap_pin_spec as _pin
from dt_pinion_arbor_collar_geometry import (
    BORE as BORE,
    COLLAR_LEN as COLLAR_LEN,
    COLLAR_OD as COLLAR_OD,
    PIN_HOLE_Z as PIN_HOLE_Z,
)
from dt_pinion_arbor_pin_spec import PIN_HOLE_CALLOUT as PIN_HOLE_CALLOUT
from dt_pinion_arbor_pin_spec import PIN_NUMBER as PIN_NUMBER
from dt_pinion_arbor_spec import (
    DRUM_STATION,
    DRUM_STATION_BAND,
    END_PLAY,
    PIN_STATION_BAND,
    PIN_STATION_FROM_HEAD_REAR,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    drum_total_air,
)
from dt_pinion_bracket_geometry import THICKNESS as STRAP_T
from dt_pinion_bracket_geometry import THICKNESS_BAND as STRAP_T_BAND
from pinion_rig_layout import RIG_MARGIN_SPARE

# The rig's one pin family (dt_vn_pinion_strap_pin_spec): a 1/16 x 1/2 slotted
# spring pin in a 1/16 drilled hole carrying its own functional band.
PIN_HOLE = _pin.HOLE_DIA
PIN_HOLE_BAND = _pin.HOLE_BAND
PIN_HOLE_MAX = _pin.HOLE_MAX
PIN_LEN = _pin.PIN_LEN  # 1/2 in: .045 sub-flush each side of the Ø.59 OD
PIN_LEN_TOL = _pin.PIN_LEN_BAND

ARBOR_NUMBER = "MHA-DT-22"
STRAP_NUMBER = "MHA-DT-14"
# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit(
    "parts/dt-pinion-arbor-collar", _config.parts("dt-pinion-arbor-collar")
)
# Drilled 5/16 slide fit over the 5/16 arbor (-.0004/-.0038 in, lands
# -.0004/-.0012 in).
# The title block's DRILLED HOLES row (+.004/0) governs it and is NOT printed
# on the dimension (drawing-guidelines.md rule 2 (the title block is the general specification)); the band is restated here only for the
# stacks below.
BORE_BAND = (drilled_oversize_mm(unit=UNIT), -drilled_undersize_mm(unit=UNIT))
# The OD, the length and the pin station all feed a wall or the strap gap, so
# each prints at the title block's .XX.
OD_BAND = printed_band_mm(2, unit=UNIT)
LEN_BAND = printed_band_mm(2, unit=UNIT)
# PinHoleCz prints from one end face, independently of Depth.
PIN_HOLE_Z_BAND = printed_band_mm(2, unit=UNIT)


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
# The novice-margin rule (Main, restricted review of #858): the gap keeps
# RIG_MARGIN_SPARE over its floor at the worst corner, like every rig margin.
GAP_REQUIRED = MIN_GAP + RIG_MARGIN_SPARE


def collar_strap_gaps() -> tuple[float, float]:
    """Least and greatest air between the collar's inboard face and the front
    strap's outer face, over every corner of the printed bands.

    Stations run from MHA-DT-22's head rear face toward the back.  The strap's
    outer face sits DRUM_STATION less the drum's front air and the strap
    thickness; the collar's inboard face sits one pin-to-face distance past
    the pin, and that distance runs over the length AND pin-station bands
    (pin_to_face_distances), not just half the length.  The straps are
    pinned at the drum plus the drilling shim (#858), so the drum's front
    air runs from nothing (drum hard forward) to the whole of its end play
    (drum hard aft, the drilling pose).
    """
    gaps = []
    for station, air, strap, pin, to_face in product(
        (DRUM_STATION - DRUM_STATION_BAND, DRUM_STATION + DRUM_STATION_BAND),
        (0.0, drum_total_air()[1]),
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
# In the assembly's pose: the drum hard on the back strap, its front end one
# drilling shim (END_PLAY) off the front strap.
GAP_NOMINAL = (DRUM_STATION - END_PLAY - STRAP_T) - (
    PIN_STATION_FROM_HEAD_REAR + COLLAR_LEN / 2.0
)
if GAP_MIN < GAP_REQUIRED - 1e-9:
    raise AssertionError(
        f"collar gap to the front strap {GAP_MIN:.3f} under {GAP_REQUIRED}"
    )

# drawing-guidelines.md rule 17 (walls and webs) webs at the printed worst case (.080 in target).
COLLAR_WALL_WORST = (COLLAR_OD - OD_BAND - (BORE + BORE_BAND[0])) / 2.0
PIN_TO_END_WEB_WORST = PIN_TO_FACE_MIN - PIN_HOLE_MAX / 2.0
for _name, _web in (
    ("collar wall", COLLAR_WALL_WORST),
    ("pin hole to collar end face", PIN_TO_END_WEB_WORST),
):
    if _web < WALL_TARGET_MM:
        raise AssertionError(
            f"{_name} web {_web:.3f} is under the {WALL_TARGET_MM} target"
        )

# The pin is never proud of the smallest OD, and still crosses the largest
# bore into both walls.
PIN_SUB_FLUSH_WORST = (COLLAR_OD - OD_BAND - (PIN_LEN + PIN_LEN_TOL)) / 2.0
# The drive's acceptance (Codex #860, PRRT_kwDOPHDy386mWhrK).  SUB-FLUSH alone
# lets the largest collar hold the shortest pin nearly flush at one end and
# OD - L = 3.354 down at the other, 0.496 past the bore.  A one-sided "0 TO x
# BELOW" window cannot fit the OD band: x must reach half the largest
# OD - L to hold every pin, yet the smallest OD with an end x down leaves
# under the floor.  So the acceptance bounds the difference between the two
# end depths: with it under D, the deeper end sits at most D / 2 past centred,
# and the far wall keeps (L - D - bore) / 2 at any OD.  D is the loosest .01 in
# step that holds the rig's one-pin-diameter grip (dt_vn_pinion_strap_pin_spec).
PIN_WALL_ENGAGEMENT_FLOOR = _pin.PIN_WALL_ENGAGEMENT_FLOOR
_PIN_LEN_MIN = PIN_LEN - PIN_LEN_TOL
_BORE_MAX = BORE + BORE_BAND[0]
PIN_END_DEPTH_SPREAD_STEP = 0.254  # .01 in
PIN_END_DEPTH_SPREAD_MAX = (
    math.floor(
        round(
            (_PIN_LEN_MIN - _BORE_MAX - 2.0 * PIN_WALL_ENGAGEMENT_FLOOR)
            / PIN_END_DEPTH_SPREAD_STEP,
            9,
        )
    )
    * PIN_END_DEPTH_SPREAD_STEP
)
PIN_WALL_ENGAGEMENT_WORST = (_PIN_LEN_MIN - PIN_END_DEPTH_SPREAD_MAX - _BORE_MAX) / 2.0
if PIN_SUB_FLUSH_WORST <= 0.0:
    raise AssertionError("the spring pin can stand proud of the collar")
if PIN_END_DEPTH_SPREAD_MAX <= 0.0:
    raise AssertionError("no pin-end depth spread keeps both collar walls gripped")
if PIN_WALL_ENGAGEMENT_WORST < PIN_WALL_ENGAGEMENT_FLOOR:
    raise AssertionError("the spring pin barely reaches the collar wall")
if not math.isclose(PIN_HOLE_Z, COLLAR_LEN / 2.0):
    raise AssertionError("the pin hole must stay centred on the collar length")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd"},
    "BoreProfile": {"BoreDia"},
    "Collar": {"Depth"},
    # drawing-guidelines.md rule 11 (turned parts read like the lathe): the pin station is printed from a finished end face.
    "PinHoleProfile": {"PinHoleDia", "PinHoleCz"},
}
# The MODEL owns every printed place (drawing-simplicity-policy.md `How the repository implements the guidelines`).  #290 inch places:
# four on the 1/16 pin hole (its +.0025/.0000 band rides the dimension),
# three on the 5/16 drilled bore (the drill grid, drawing-guidelines rule 3;
# the callout names the 5/16 drill, which governs the hole), and the
# title block's .XX on the OD, length and pin station, which the walls and
# the strap gap read.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "CollarProfile": {"CollarOd": 2},
    "BoreProfile": {"BoreDia": 3},
    "Collar": {"Depth": 2},
    "PinHoleProfile": {"PinHoleDia": 4, "PinHoleCz": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked collar dimension needs authored places")

# The pin is the stock MHA-DT-VN-63 (McMaster 98296A027): its own BOM line and a
# modelled drive-train component.  So the collar sheet carries no supply note
# (the MHA-DT-14 strap precedent); the hole callout names the pin it takes,
# the same callout MHA-DT-22 prints for the same pin (PIN_NUMBER and
# PIN_HOLE_CALLOUT come from dt_pinion_arbor_pin_spec).
BORE_CALLOUT = f"5/16 DRILL THRU\nSLIDES ON {ARBOR_NUMBER}"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

# The rig's first assembly step (Codex #860, PRRT_kwDOPHDy386mTbe7).  The
# collar reaches the pin station only from the arbor's back crown end: its
# Ø5/16 bore passes neither the Ø.59 head nor a drum already bonded at the drum
# station.  The front strap, journaled between the collar and the drum, is
# trapped the same way, so it follows the collar on before the bond.
COLLAR_NUMBER = "MHA-DT-33"
# The step prints on MHA-DT-00, still a millimetre sheet (#290 converts it
# last), so the spread is written in mm, rounded down so the print is never
# looser than the computed limit (codex review).
ASSEMBLY_STEP = "\n".join(
    (
        f"BEFORE THE DRUM BOND: SLIDE {COLLAR_NUMBER} ONTO {ARBOR_NUMBER} FROM ITS",
        f"BACK CROWN END TO THE PIN STATION; DRIVE {PIN_NUMBER} THRU BOTH, BOTH ENDS",
        "SUB-FLUSH AND THEIR DEPTHS BELOW THE OD WITHIN "
        f"{math.floor(PIN_END_DEPTH_SPREAD_MAX * 10.0) / 10.0:.1f} OF EACH OTHER;",
        f"THEN SLIDE THE FRONT {STRAP_NUMBER} ON BEHIND IT.",
    )
)

