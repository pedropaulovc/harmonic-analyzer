r"""Pure-data contract for the oblique-trammel jig's nut bracket (MHA-CH-06-TL-29).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). One
bracket hangs the leadscrew feed's flanged nut (bought, shop inventory
``fixtures.trammel-tr8-flange-nut``) off pivot block 1 (MHA-CH-06-TL-22),
so turning the handwheel drives the carriage along rail 1. The layout (the
screw axis, the bracket's envelope and every bought dimension) belongs to
``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, imported as ``leadscrew``; this
module never retypes one of its numbers, so a vendor swap of the nut only
changes numbers there.

Material and stock: 6061-T6 aluminium flat bar 3/4 x 2 in. The 3/4 in runs
along the rail; its +X end is milled to the finished length
(``leadscrew.NUT_BRACKET_LENGTH``, 18.50 at two places) and the bracket is
set centred on the two #8 screws at assembly (``X_SET_*``), so each tap's end
wall clears rule 17's floor at half the length's ±0.51 (Main, 2026-10-17;
c4-r3). The bar is sawn and faced to the height and milled to the 48 depth.

Frame (SolidWorks model, and the ``PRECHIPS_SOLIDS`` frame; the leadscrew
spec's): pivot block 1's axes, the origin on the block's -Y face at the
carriage centre, on the bracket's bottom face. +X runs along the rail away
from the spindle, +Y is the block's +Y, +Z is up. The bracket lies at -Y.
Envelope X ``leadscrew.NUT_BRACKET_X`` (-9.25 .. 9.25), Y -48 .. 0,
Z 0 .. 35.3. The origin's X is mid-air (the bracket centres on the block
screws), so every printed X station runs from the real -X face.

Features:

- Two #8-32 UNC taps, blind from the Y = 0 face, spotted at assembly through
  TL-22's two side holes (``leadscrew.PIVOT_BLOCK_HOLE_SPEC``) with the
  bracket clamped on rail 1's pivot block at the X set (owner ruling 3B,
  2026-10-17; TL-00's match-drill step), then drilled and tapped. The model
  holds them at TL-22's nominal stations (``leadscrew.BLOCK_SCREW_X``, row
  ``NUT_BRACKET_BLOCK_HOLES_Z``); the sheet prints no station. Two #8-32
  SHCS come through TL-22 into them, ``BLOCK_SCREW_ENGAGEMENT`` deep. The
  thread is ``leadscrew.NUT_BRACKET_TAP_DEPTH``; the drill adds a plug tap's
  five-pitch lead.
- The nut seat, on the -X face, on the screw axis: a counterbore for the
  nut's short spigot (``NUT_BODY_SHORT``) and a THRU clearance for the
  leadscrew. The nut is flipped, its long body standing proud on -X
  (JigAssembly; Main's ruling on the tap-to-bore wall). A bore for the body
  would hold the #4-40 taps' sub-floor wall for their full depth.
- Four #4-40 UNC taps on the -X face, on the nut's bolt circle, for the
  #4-40 SHCS through the flange's plain Ø3.5 holes (``leadscrew.NUT_SCREW``;
  shop-chosen US-customary, fastener policy); thread ``NUT_SCREW_TAP_DEPTH``,
  drill with the five-pitch lead.

Bands. The #8 pair is spotted from TL-22 (rule 19, fit-up at assembly), so
it carries no band of its own: each spot lands within TL-22's three-place
station band, the X set's ``X_SET_BAND`` and the transfer punch's float in
TL-22's Ø4.978 hole (``SPOT_FLOAT``). The nut seat's stations, from the
Y = 0 face and the bottom face, print at two places (title block ±0.51):
the bracket's place on TL-22 is set at assembly by the match-drill, so the
edges carry only walls. The #4-40 taps are located from the seat's axis, not
the edges: ``NUT_HOLE_OFFSET`` each way at three places (±0.13), on the
hidden reference sketch ``NutPatternReference``. Each tap's centre sits in
a 0.13 half-side square about its nominal offset from the seat,
``POSITION_RADIUS`` 0.184. Each #4-40 floats in the flange's holes
(``NUT_SCREW_FLOAT``) and the spigot in the counterbore (``SPIGOT_FLOAT``);
with every tap within 0.184 of nominal from the seat, the nut seated on its
spigot clears all four screws by ``NUT_PATTERN_ALLOWANCE``, which is left for
the nut's own hole and spigot positions (not published). At two places
(±0.51, 0.72 radial) the pattern does not fit, so the seat callout states
the offsets' function: the counterbore locates the nut's spigot on the #4-40
pattern. Against the edges each tap stacks both bands (±0.51 + ±0.13). The
counterbore Ø carries a model band (``CBORE_BAND``, 0 / +0.10): the title
block's two-place ±0.51 would admit a counterbore under the spigot. No band
is set by the leadscrew axis: the screw passes a 0.5 radial clearance, and
the KP08s' alignment to the nut is the fit-up in the jig's assembly step.

Rule 17 (walls, 2.0 target, 1.5 floor) at worst case: the seat at its
two-place band, each #4-40 tap at its three-place offset from the seat (and
both bands to an edge), each #8 spot off by TL-22's band, the X set and the
punch's float, the finished length at its two-place ±0.51, the depth and
height at one place (±0.8), each thread at its major diameter, the
counterbore at its +0.10 and the clearance at the drilled +0.1.
``WALLS_MM`` holds the nominal values, ``WORST_WALLS`` the worst. The binding
wall is the #4-40 taps' to the spigot counterbore: the nut's bolt circle fixes
it under the floor, only within the counterbore's depth, where the flange
clamps. The owner accepted it (``RULE_17_FLOOR_EXCEPTIONS``; the part YAML's
machinist exception RV-01, 2026-10-17), and the seat callout states it (rule
20). Below the counterbore, the #4-40 taps' wall to the clearance is also
stated (rule 20), and so is each #8 tap's wall to its end face (1.54, in the
#8 callout; RV-02).

UNVERIFIED: the nut's own tolerances (spigot Ø and length, hole positions)
and the counterbore-depth margin over the spigot.
"""

from __future__ import annotations

import math
from typing import Any

import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
from _hole_spec import (
    CLEARANCE_MM,
    DRILL_POINT_H,
    THREAD_MAJOR_MM,
    HoleSpec,
    blind_cut_dia_mm,
)
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)

# --- Identity ---------------------------------------------------------------
NUMBER = leadscrew.NUT_BRACKET_NUMBER
QUANTITY = leadscrew.NUT_BRACKET_QUANTITY
NUT_ID = leadscrew.NUT_ID
PIVOT_BLOCK_NUMBER = "MHA-CH-06-TL-22"

# --- Bracket: 6061-T6 3/4 x 2 in flat --------------------------------------
FACE_X = round(leadscrew.NUT_BRACKET_X[0], 9)  # the -X (nut) face, -9.25
BRACKET_FACE_X = -FACE_X  # origin to the -X face: an unprinted model knob
BRACKET_LENGTH = round(leadscrew.NUT_BRACKET_X[1] - leadscrew.NUT_BRACKET_X[0], 9)
BRACKET_DEPTH = round(leadscrew.NUT_BRACKET_DEPTH, 9)  # 48
BRACKET_HEIGHT = round(leadscrew.NUT_BRACKET_HEIGHT, 9)  # 35.3
# The finished length sets each #8 tap's end wall (WORST_WALLS): with the
# bracket set centred on the taps, each wall takes half the length's band
# and holds the floor at two places.
LENGTH_PLACES = 2
SIZE_PLACES = 1  # 48.0 and 35.3, milled and faced
if abs(BRACKET_LENGTH - leadscrew.NUT_BRACKET_LENGTH) > 1e-9:
    raise AssertionError("the nut bracket envelope no longer spans its length")
if abs(leadscrew.NUT_FLANGE_X[1] - leadscrew.NUT_BRACKET_X[0]) > 1e-9:
    raise AssertionError("the nut flange no longer seats on the bracket's -X face")
# The +X end is always milled: the longest finished length stays under the
# bar's 3/4 in, so no sawn face survives at the length's two-place band.
LENGTH_CLEANUP = leadscrew.NUT_BRACKET_STOCK_THICK - BRACKET_LENGTH
if LENGTH_CLEANUP - printed_band_mm(LENGTH_PLACES) <= 0.0:
    raise AssertionError("the nut bracket's finished length leaves no cleanup")

# --- Block screws: 2 x #8-32 taps, blind from the Y = 0 face -----------------
BLOCK_THREAD = leadscrew.BLOCK_SCREW  # "#8-32"
# Spotted from TL-22 at assembly, so unprinted: the model holds them at
# TL-22's nominal stations, X from the -X face, the row from the bottom face.
SCREW_X = tuple(round(x - FACE_X, 9) for x in leadscrew.BLOCK_SCREW_X)  # 4.25, 14.25
SCREW_Z = round(leadscrew.NUT_BRACKET_BLOCK_HOLES_Z, 9)  # 22.3
BLOCK_SCREW_POINTS = tuple((x, 0.0, SCREW_Z) for x in leadscrew.BLOCK_SCREW_X)
# The X set (TL-00's match-drill step): clamped on TL-22's -Y face, the
# bracket's centre stands X_SET_MID from TL-22's -X end, within X_SET_BAND.
# X_SET_MID is the mid-station of TL-22's
# two side holes, so the bracket centres on them and each tap's end wall
# takes half the length's band. The set prints at three places and takes the
# title block's ±0.13 (Main's ruling (a), 2026-10-17: no bespoke ±0.10; the
# .X band's 0.8 would need a 19.75 bracket, past FEED_GAP and the 3/4 in
# stock), which holds each end wall over the floor (_END_WALL below).
X_SET_MID = sum(pivot_block.SIDE_STATIONS_X) / 2.0  # 50
X_SET_FAR_END = X_SET_MID + BRACKET_LENGTH / 2.0  # 59.25 at the nominal length
X_SET_NUT_FACE = X_SET_MID - BRACKET_LENGTH / 2.0  # 40.75 at the nominal length
X_SET_PLACES = 3
X_SET_BAND = printed_band_mm(X_SET_PLACES)  # ±0.13
if abs(pivot_block.DATUM_X + X_SET_FAR_END - leadscrew.NUT_BRACKET_X[1]) > 1e-9:
    raise AssertionError("the X set no longer centres the bracket on TL-22's screws")
# Each tap is spotted through TL-22's hole with a transfer punch.
TRANSFER_PUNCH = "3/16"
TRANSFER_PUNCH_DIA = 3.0 / 16.0 * 25.4  # 4.7625
_PLUG_LEAD_PITCHES = 5.0  # a plug tap's lead, past the full thread
_SCREW_TIP_RESERVE = 0.25  # the screw tip short of the last full thread


def _ceil_step(value: float, step: float) -> float:
    return round(math.ceil(round(value / step, 9)) * step, 9)


def _pitch_mm(thread: str) -> float:
    """Pitch of a ``#8-32`` (TPI) thread key."""
    return 25.4 / float(thread.split("-")[1])


BLOCK_TAP_THREAD_DEPTH = round(leadscrew.NUT_BRACKET_TAP_DEPTH, 9)  # 12.0
BLOCK_TAP_DRILL_DEPTH = _ceil_step(
    BLOCK_TAP_THREAD_DEPTH
    + 2.0 * printed_band_mm(2)
    + _PLUG_LEAD_PITCHES * _pitch_mm(BLOCK_THREAD),
    0.05,
)  # 17.0
BLOCK_TAP_SPEC = HoleSpec(
    "tapped",
    BLOCK_THREAD,
    end="blind",
    depth_mm=BLOCK_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": BLOCK_TAP_THREAD_DEPTH},
)
BLOCK_TAP_DRILL = blind_cut_dia_mm(BLOCK_TAP_SPEC)  # 3.454

# --- The nut: every number from leadscrew's bought block -----------------------
NUT_THREAD = leadscrew.NUT_SCREW  # "#4-40"
NUT_TAP_THREAD_DEPTH = round(leadscrew.NUT_SCREW_TAP_DEPTH, 9)  # 8.4125
NUT_TAP_DRILL_DEPTH = _ceil_step(
    NUT_TAP_THREAD_DEPTH
    + 2.0 * printed_band_mm(2)
    + _PLUG_LEAD_PITCHES * _pitch_mm(NUT_THREAD),
    0.05,
)  # 12.65
NUT_TAP_SPEC = HoleSpec(
    "tapped",
    NUT_THREAD,
    end="blind",
    depth_mm=NUT_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": NUT_TAP_THREAD_DEPTH},
)
NUT_TAP_DRILL = blind_cut_dia_mm(NUT_TAP_SPEC)  # 2.261

# The nut seat: Y from the Y = 0 face, Z from the bottom face, at two places
# (module docstring): the edges carry only walls, since the bracket's place
# on TL-22 is match-drilled at assembly.
SEAT_PLACES = 2
BORE_Y = round(-leadscrew.NUT_BORE_YZ[0], 9)  # 35
BORE_Z = round(leadscrew.NUT_BORE_YZ[1], 9)  # 13
NUT_SEAT_POINT = (FACE_X, leadscrew.NUT_BORE_YZ[0], BORE_Z)
# The leadscrew passes a 1.0 diametral clearance.
SCREW_CLEARANCE_DIA = round(leadscrew.SCREW_MAJOR_DIA + 1.0, 9)  # 9.0
# The spigot's counterbore, a locating fit, with its model band (module
# docstring).
CBORE_DIA = round(leadscrew.NUT_BORE_DIA, 9)  # 10.7
CBORE_BAND = (0.10, 0.0)  # (upper, lower)
CALLOUT_PLACES = 2  # the native callout's .XX template
# Deep enough that the spigot never bottoms at the shallowest printed depth.
_SPIGOT_END_CLEARANCE = 0.05
CBORE_DEPTH = _ceil_step(
    leadscrew.NUT_BODY_SHORT + printed_band_mm(CALLOUT_PLACES) + _SPIGOT_END_CLEARANCE,
    0.1,
)  # 2.1
NUT_SEAT_SPEC = HoleSpec(
    "counterbore_socket",
    "5/16",
    overrides_mm={
        "HoleDiameter": SCREW_CLEARANCE_DIA,
        "CounterBoreDiameter": CBORE_DIA,
        "CounterBoreDepth": CBORE_DEPTH,
    },
)
if not (
    leadscrew.SCREW_MAJOR_DIA < SCREW_CLEARANCE_DIA < CBORE_DIA
    and leadscrew.NUT_BODY_DIA < CBORE_DIA + CBORE_BAND[1]
):
    raise AssertionError("the nut seat no longer passes the screw and the spigot")
if CBORE_DEPTH - printed_band_mm(CALLOUT_PLACES) <= leadscrew.NUT_BODY_SHORT:
    raise AssertionError("the nut's spigot bottoms in its counterbore")

# The #4-40 taps on the nut's circle: a square pattern at 45 deg, so two Y and
# two Z stations, each NUT_HOLE_OFFSET either side of the seat's centre. The
# sheet locates them from the seat's axis at three places (the #4-40 pattern's
# fit to the nut, module docstring), on NUT_PATTERN_REFERENCE, a hidden
# sketch of points: the Hole Wizard's own placement dimensions run from the
# edges, so they stay unprinted.
PATTERN_PLACES = 3
NUT_PATTERN_REFERENCE = "NutPatternReference"
REFERENCE_SKETCHES = (NUT_PATTERN_REFERENCE,)
_ANGLES = tuple(sorted(a % 360.0 for a in leadscrew.NUT_HOLE_ANGLES_DEG))
if _ANGLES != (45.0, 135.0, 225.0, 315.0):
    raise AssertionError("the nut's hole pattern is no longer the 45 deg square")
NUT_HOLE_OFFSET = round(leadscrew.NUT_HOLE_PCD / 2.0 * math.sqrt(0.5), 3)  # 5.657
NUT_HOLE_Y = (round(BORE_Y - NUT_HOLE_OFFSET, 9), round(BORE_Y + NUT_HOLE_OFFSET, 9))
NUT_HOLE_Z = (round(BORE_Z - NUT_HOLE_OFFSET, 9), round(BORE_Z + NUT_HOLE_OFFSET, 9))
# Model points on the -X face, in the placement order the build's shared
# coordinates assume: (Y1, Z2), (Y2, Z2), (Y2, Z1), (Y1, Z1).
NUT_HOLE_POINTS = tuple(
    (FACE_X, -y, z)
    for y, z in (
        (NUT_HOLE_Y[0], NUT_HOLE_Z[1]),
        (NUT_HOLE_Y[1], NUT_HOLE_Z[1]),
        (NUT_HOLE_Y[1], NUT_HOLE_Z[0]),
        (NUT_HOLE_Y[0], NUT_HOLE_Z[0]),
    )
)
# Each point lies on the nut's circle to the printed rounding.
for _x, _y, _z in NUT_HOLE_POINTS:
    _radius = math.hypot(-_y - BORE_Y, _z - BORE_Z)
    if abs(2.0 * _radius - leadscrew.NUT_HOLE_PCD) > 0.002:
        raise AssertionError("a #4-40 tap is off the nut's bolt circle")

# --- The fits ----------------------------------------------------------------
_B3 = printed_band_mm(PATTERN_PLACES)  # ±0.13, each tap from the seat's axis
_B2 = printed_band_mm(2)  # ±0.51
_B1 = printed_band_mm(SIZE_PLACES)  # ±0.8
_SEAT_BAND = printed_band_mm(SEAT_PLACES)  # ±0.51, the seat from the edges
# Each #4-40 tap from the edges: the seat's band plus its offset's.
_TAP_BAND = _SEAT_BAND + _B3  # ±0.64
POSITION_RADIUS = math.hypot(_B3, _B3)  # 0.184
_BLOCK_R = THREAD_MAJOR_MM[BLOCK_THREAD] / 2.0
_NUT_R = THREAD_MAJOR_MM[NUT_THREAD] / 2.0
BLOCK_HOLE_DIA = CLEARANCE_MM[
    (leadscrew.PIVOT_BLOCK_HOLE_SPEC.size, leadscrew.PIVOT_BLOCK_HOLE_SPEC.fit)
]  # 4.978
# The punch's float in TL-22's hole: how far a spot can land off its axis.
SPOT_FLOAT = (BLOCK_HOLE_DIA - TRANSFER_PUNCH_DIA) / 2.0  # 0.108
if not SPOT_FLOAT > 0.0:
    raise AssertionError("the transfer punch no longer fits TL-22's #8 hole")
# Each spot off its TL-22 hole's nominal: along X, TL-22's station band, the
# X set and the punch's float; along Z, the row's band and the float.
_TL22_BAND = printed_band_mm(pivot_block.SIDE_STATION_PLACES)  # ±0.13
_SPOT_OFF_X = _TL22_BAND + X_SET_BAND + SPOT_FLOAT
_SPOT_OFF_Z = _TL22_BAND + SPOT_FLOAT
NUT_SCREW_FLOAT = (leadscrew.NUT_HOLE_DIA - THREAD_MAJOR_MM[NUT_THREAD]) / 2.0  # 0.328
SPIGOT_FLOAT = (CBORE_DIA - leadscrew.NUT_BODY_DIA) / 2.0  # 0.25
NUT_PATTERN_ALLOWANCE = min(NUT_SCREW_FLOAT, SPIGOT_FLOAT) - POSITION_RADIUS  # 0.066
if not NUT_PATTERN_ALLOWANCE > 0.0:
    raise AssertionError("the nut bracket's nut pattern does not fit the nut")
# The offsets from the seat's axis at two places would not fit the nut.
_TWO_PLACE_RADIUS = math.hypot(_B2, _B2)
if not _TWO_PLACE_RADIUS > max(NUT_SCREW_FLOAT, SPIGOT_FLOAT):
    raise AssertionError("the nut pattern's offsets no longer need three places")

# --- The nut's flange lands on the -X face ------------------------------------
_FLANGE_R = leadscrew.NUT_FLANGE_DIA / 2.0
NUT_FLANGE_MARGINS: dict[str, float] = {
    "to the -Y side": BRACKET_DEPTH - BORE_Y - _FLANGE_R,
    "to the bottom face": BORE_Z - _FLANGE_R,
}
# Worst case: the seat at its two-place band, the nut shifted by its float,
# the depth at its one-place band (the bottom face is the datum).
WORST_FLANGE_MARGINS: dict[str, float] = {
    "to the -Y side": (BRACKET_DEPTH - _B1)
    - (BORE_Y + _SEAT_BAND + SPIGOT_FLOAT)
    - _FLANGE_R,
    "to the bottom face": (BORE_Z - _SEAT_BAND - SPIGOT_FLOAT) - _FLANGE_R,
}
if min(WORST_FLANGE_MARGINS.values()) < 0.0:
    raise AssertionError("the nut flange overhangs the nut bracket")

# --- Rule 18: thread engagement >= 1.5 D; no screw bottoms --------------------
for _thread, _engagement, _depth in (
    (BLOCK_THREAD, leadscrew.BLOCK_SCREW_ENGAGEMENT, BLOCK_TAP_THREAD_DEPTH),
    (NUT_THREAD, leadscrew.NUT_SCREW_ENGAGEMENT, NUT_TAP_THREAD_DEPTH),
):
    if _engagement < 1.5 * THREAD_MAJOR_MM[_thread]:
        raise AssertionError(f"nut bracket {_thread} engages under 1.5 D")
    if _depth - _B2 < _engagement + _SCREW_TIP_RESERVE:
        raise AssertionError(f"a {_thread} screw bottoms in the nut bracket")

# --- Rule 17: nominal walls ---------------------------------------------------
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
_DIAGONAL = math.hypot(NUT_HOLE_OFFSET, NUT_HOLE_OFFSET)  # 8.05


def _point_h(dia: float) -> float:
    return dia / 2.0 * DRILL_POINT_H


WALLS_MM: dict[str, float] = {
    "#4-40 tap to nut-seat counterbore": _DIAGONAL - CBORE_DIA / 2.0 - _NUT_R,
    "#4-40 tap to screw clearance": _DIAGONAL - SCREW_CLEARANCE_DIA / 2.0 - _NUT_R,
    "#8 tap to +X face": BRACKET_LENGTH - SCREW_X[1] - _BLOCK_R,
}

# --- Rule 17 at the printed bands' worst case -----------------------------------
_CBORE_R_MAX = (CBORE_DIA + CBORE_BAND[0]) / 2.0
_CLEAR_R_MAX = (SCREW_CLEARANCE_DIA + DRILLED_BAND[0]) / 2.0
# Each #4-40 tap from the seat's axis: one three-place offset per axis.
_DIAGONAL_MIN = math.hypot(NUT_HOLE_OFFSET - _B3, NUT_HOLE_OFFSET - _B3)
_LENGTH_MIN = BRACKET_LENGTH - printed_band_mm(LENGTH_PLACES)
# The #8 taps: the shortest bracket set centred on TL-22's holes, each spot
# off by _SPOT_OFF_X toward its end face. The row's height on the bracket
# also follows the screw line it hangs on at the spot, a stack the top
# face's ~8 mm margin over the floor carries.
_HALF_PITCH = (SCREW_X[1] - SCREW_X[0]) / 2.0  # 5
_END_WALL = _LENGTH_MIN / 2.0 - _HALF_PITCH - _SPOT_OFF_X - _BLOCK_R
WORST_WALLS: dict[str, float] = {
    "#4-40 tap to nut-seat counterbore": _DIAGONAL_MIN - _CBORE_R_MAX - _NUT_R,
    "#4-40 tap to screw clearance": _DIAGONAL_MIN - _CLEAR_R_MAX - _NUT_R,
    "#4-40 tap to #4-40 tap": 2.0 * NUT_HOLE_OFFSET - 2.0 * _B3 - 2.0 * _NUT_R,
    "#4-40 tap to bottom face": NUT_HOLE_Z[0] - _TAP_BAND - _NUT_R,
    "#4-40 tap to -Y side": (BRACKET_DEPTH - _B1)
    - (NUT_HOLE_Y[1] + _TAP_BAND)
    - _NUT_R,
    "#4-40 tap drill to +X face": _LENGTH_MIN
    - (NUT_TAP_DRILL_DEPTH + _B2)
    - _point_h(NUT_TAP_DRILL),
    "counterbore to bottom face": BORE_Z - _SEAT_BAND - _CBORE_R_MAX,
    "counterbore to -Y side": (BRACKET_DEPTH - _B1)
    - (BORE_Y + _SEAT_BAND)
    - _CBORE_R_MAX,
    "#8 tap to -X face": _END_WALL,
    "#8 tap to #8 tap": 2.0 * _HALF_PITCH
    - 2.0 * (_TL22_BAND + SPOT_FLOAT)
    - 2.0 * _BLOCK_R,
    "#8 tap to +X face": _END_WALL,
    "#8 tap to top face": (BRACKET_HEIGHT - _B1) - (SCREW_Z + _SPOT_OFF_Z) - _BLOCK_R,
    "#8 tap drill to #4-40 tap": (NUT_HOLE_Y[0] - _TAP_BAND - _NUT_R)
    - (BLOCK_TAP_DRILL_DEPTH + _B2 + _point_h(BLOCK_TAP_DRILL)),
}
# The nut's own circle leaves the #4-40 taps under the floor to their spigot's
# counterbore, only within its depth: inherent in the bought nut, accepted by
# the owner (part YAML machinist exception RV-01, 2026-10-17). Every other
# wall holds the floor.
RULE_17_FLOOR_EXCEPTIONS = frozenset({"#4-40 tap to nut-seat counterbore"})
for _wall, _mm in WORST_WALLS.items():
    if _mm < WALL_FLOOR and _wall not in RULE_17_FLOOR_EXCEPTIONS:
        raise AssertionError(
            f"nut bracket {_wall} wall {_mm:.3f} under the rule 17 floor"
        )
# drawing-guidelines.md rule 20: walls under the target, stated on the sheet.
RULE_20_SHORTFALLS = {
    name: wall for name, wall in WORST_WALLS.items() if wall < WALL_TARGET
}
NUT_WALL_MIN = min(
    WORST_WALLS["#4-40 tap to nut-seat counterbore"],
    WORST_WALLS["#4-40 tap to screw clearance"],
)
# Both end walls, equal under the centred X set: the shortest length's half,
# less the half pitch, the spot's offset chain (TL-22's station band, the X
# set's three-place band, the punch's float) and the tap's major radius
# (1.544). Main's ruling (a): the set's three places hold rule 17's floor;
# under the target, the sheet states it (RV-02).
END_WALL_MIN = min(WORST_WALLS["#8 tap to -X face"], WORST_WALLS["#8 tap to +X face"])
if END_WALL_MIN < WALL_FLOOR:
    raise AssertionError("the X set leaves a #8 tap's end wall under the floor")

# --- Marked dimensions -----------------------------------------------------------
# The seat's stations from the edges on its own placement sketch; the #4-40
# pattern from the seat's axis on NUT_PATTERN_REFERENCE (the NutTaps wizard's
# edge placements stay unprinted).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BracketProfile": {"BracketLength", "BracketHeight"},
    "Bracket": {"BracketDepth"},
    "NutSeat": {"BoreY", "BoreZ"},
    NUT_PATTERN_REFERENCE: {
        "NutPatternY1",
        "NutPatternY2",
        "NutPatternZ1",
        "NutPatternZ2",
    },
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BracketProfile": {
        "BracketLength": LENGTH_PLACES,
        "BracketHeight": SIZE_PLACES,
    },
    "Bracket": {"BracketDepth": SIZE_PLACES},
    "NutSeat": {"BoreY": SEAT_PLACES, "BoreZ": SEAT_PLACES},
    NUT_PATTERN_REFERENCE: {
        "NutPatternY1": PATTERN_PLACES,
        "NutPatternY2": PATTERN_PLACES,
        "NutPatternZ1": PATTERN_PLACES,
        "NutPatternZ2": PATTERN_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked nut bracket dimension needs authored places")
DRAWING_VALUES: dict[str, float] = {
    "BracketLength": BRACKET_LENGTH,
    "BracketHeight": BRACKET_HEIGHT,
    "BracketDepth": BRACKET_DEPTH,
    "BoreY": BORE_Y,
    "BoreZ": BORE_Z,
    "NutPatternY1": NUT_HOLE_OFFSET,
    "NutPatternY2": NUT_HOLE_OFFSET,
    "NutPatternZ1": NUT_HOLE_OFFSET,
    "NutPatternZ2": NUT_HOLE_OFFSET,
}
for _name, _value in DRAWING_VALUES.items():
    if abs(_value - round(_value, DRAWING_PRECISION_BY_NAME[_name])) > 1e-9:
        raise AssertionError(f"nut bracket {_name} {_value} does not print as modelled")

# --- Sheet text ------------------------------------------------------------------
# Every tight band names its mate (drawing-guidelines rule 4). Each pattern's
# native hole callout carries its mate as its first row (the base bar's
# BRACKET_CALLOUT_PROCESS). The #8 pair prints no station: spotted from
# TL-22 at assembly (rule 19), its first row says so.
BLOCK_TAP_PROCESS = f"SPOT FROM {PIVOT_BLOCK_NUMBER} AT ASSEMBLY;\n"
# The mate by its inventory id, as the seat's callout names it (c4-r8/r9,
# rule 4: "NUT" alone named no part), on its own row: the block's widest.
NUT_TAP_PROCESS = f"MATCHES FLANGE HOLES OF\n{NUT_ID}\n"
# The seat's callout: DRILL in its THRU row, then three rows under the native
# ones: the counterbore's locating fit, which the #4-40 pattern's three-place
# offsets from the seat's axis serve (c4 review: at three places the seat's
# own 13.000 and 35.000 served nothing at the edges; they print two), the
# mate, and rule 20's wall statement (the #4-40 taps' least wall to the seat).
NUT_SEAT_PROCESS = "DRILL"
NUT_SEAT_LOCATES_CALLOUT = "LOCATES NUT SPIGOT ON #4-40 PATTERN"
NUT_SEAT_MATE_CALLOUT = "\n".join(
    (
        NUT_SEAT_LOCATES_CALLOUT,
        f"FOR {NUT_ID}",
        f"WALL TO #4-40 TAPS {NUT_WALL_MIN:.2f} MIN",
    )
)
# Rule 20: both #8 taps' end walls, the last row of the #8 taps' own callout
# (the length's two places and the X set fix them). On the length dimension
# the row sat across its extension lines (c4-r3).
BLOCK_TAP_WALL_CALLOUT = f"WALL TO EACH END FACE {END_WALL_MIN:.2f} MIN"
# Each #4-40 offset serves two taps.
DIMENSION_PREFIXES = {
    "NutPatternY1": "2X ",
    "NutPatternY2": "2X ",
    "NutPatternZ1": "2X ",
    "NutPatternZ2": "2X ",
}

SURFACE_FINISHES = ()
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


_MEASURED = {
    "status": "measured",
    "by": "placeholder (realistic, remeasure: #1413)",
    "date": "2026-10-16",
    "instrument": (
        "digital calipers, height gauge and indicator; physical component sizes/fit only"
    ),
}


def _void(
    name: str,
    at: tuple[float, float, float],
    axis: tuple[float, float, float],
    dia: float,
    length: float,
) -> dict[str, Any]:
    return {
        "name": name,
        "shape": "cylinder",
        "at_mm": list(at),
        "axis": list(axis),
        "dia_mm": dia,
        "length_mm": length,
        "void": True,
        "cuts": ["nut bracket"],
        "measured": dict(_MEASURED),
    }


# The bracket as made, in the model frame above; the drill points are left
# to the CAD part.
PRECHIPS_SOLIDS: list[dict[str, Any]] = [
    {
        "name": "nut bracket",
        "shape": "box",
        "at_mm": [FACE_X, -BRACKET_DEPTH, 0.0],
        "size_mm": [BRACKET_LENGTH, BRACKET_DEPTH, BRACKET_HEIGHT],
        "note": (
            f"{NUMBER}, 6061-T6 3/4 x 2 flat; screwed to the pivot block "
            f"({PIVOT_BLOCK_NUMBER}) by 2 x #8-32 SHCS; carries {NUT_ID}"
        ),
        "measured": dict(_MEASURED),
    },
    _void(
        "screw clearance",
        NUT_SEAT_POINT,
        (1.0, 0.0, 0.0),
        SCREW_CLEARANCE_DIA,
        BRACKET_LENGTH,
    ),
    _void("nut seat", NUT_SEAT_POINT, (1.0, 0.0, 0.0), CBORE_DIA, CBORE_DEPTH),
    *(
        _void(
            f"nut tap {index}",
            point,
            (1.0, 0.0, 0.0),
            NUT_TAP_DRILL,
            NUT_TAP_DRILL_DEPTH,
        )
        for index, point in enumerate(NUT_HOLE_POINTS, start=1)
    ),
    *(
        _void(
            f"block tap {index}",
            point,
            (0.0, -1.0, 0.0),
            BLOCK_TAP_DRILL,
            BLOCK_TAP_DRILL_DEPTH,
        )
        for index, point in enumerate(BLOCK_SCREW_POINTS, start=1)
    ),
]
