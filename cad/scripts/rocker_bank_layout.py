r"""Axial (machine-z) layout of the rocker-arm bank on the pivot shaft
(issue #743 PR2; #3114) -- one source for the channel assembly, the pivot
shaft and the bracket stations.

GEOMETRY ONLY, like ``cylinder_bank_layout``: no drawing notes, no drawing
specs, no title-block reads. It reads the channel stations and ONE datum it
shares with the cylinder bank: the arm plane IS the cam plane
(``cam_plane.CAM_MID_DZ``), because each connecting rod is flat -- its ring
rides the cam and its fork straddles the arm in that one plane. That leaf
reads only the MHA-DT-12 gear spec (and the gear-train config it reads), so
a cylinder-gear spec change re-keys the pivot parts; the cylinder bank's
pedestals, arbor, washers, spring and bank pitch do not reach them.

The arms FLOAT on the shaft (owner ruling 2026-11-18, #3114, replacing the
preloaded face-to-face hub stack of #948 ruling R): each MHA-CH-06 arm is
located along the bank by its own connecting rod, whose ring slides between
the two tooth discs of its cam slot and whose fork carries the arm's strap.

* Each hub is shorter than the station pitch (``ch_rocker_arm_spec``), so
  neighbouring hubs stand apart at the nominal stations and no run of hubs
  can hold a rod off its cam slot (``test_channel_axial_budget``). A hub only
  bounds how close two neighbours can come.
* There is no preload spring and there are no thrust washers: nothing bears
  on an ear. Each ear stands END_FLOAT clear of its end hub's nominal face,
  and the end arms, following their rods, never reach an ear
  (END_CLEARANCE_MIN).
* The NORTH bracket is DRO-located at fit-up (NORTH_EAR_LOCATE_BAND) and the
  SOUTH bracket is set from it to the ears' inner-face span (EAR_INNER_SPAN,
  +/-EAR_SPAN_BAND, the title block's .XXX). The ears stand within .008 of
  where the retired preloaded stack put them, and the shaft keeps its
  printed length.
* The shaft is a plain rod whose cylinder spans both ears' outer faces, each
  end domed proud of its ear. One #4-40 set screw down through each ear's
  arch apex bites a flat milled on the shaft at that ear's mid-plane, so the
  screws hold the shaft both axially and in rotation, flats up.
"""

from __future__ import annotations

import _config
from cam_plane import CAM_MID_DZ
import ch_amplitude_bar_spec as _bar
import ch_pivot_bracket_spec as _bracket
import ch_pivot_shaft_spec as _shaft
from ch_rocker_arm_spec import HUB_LENGTH, HUB_LENGTH_MAX

COUNT = 20  # the full bank (the brackets never follow active_count)

# --- stations ----------------------------------------------------------------
# The ONE station source for the bank (#743 (d), #914 option 1): fit-up sets
# the north bracket in the drive-train step-9 setup off the LOCATED drum bank
# (9A), whose nominal cam stations are these channel stations. Taking the
# bank's as-set Z instead is a change to this line alone.
STATION_Z0 = _config.machine("channels", "station_z0_mm")  # channel 0 gear plane
PITCH = _config.machine("channels", "station_pitch_mm")
# Arm/bar/lever mid-planes, the rod-pin plane and the spring stations sit on
# the cam plane: z_j + CAM_MID_DZ (-3.81, the integral cam's mid-width).
ARM_MID_DZ = CAM_MID_DZ
if HUB_LENGTH_MAX >= PITCH:
    raise AssertionError("a rocker hub as long as the station pitch cannot float")


def hub_mid_z(j: int) -> float:
    """Machine z of arm j's plate / hub mid-plane (nominal: its rod centred
    in its cam slot)."""
    return STATION_Z0 + PITCH * j + ARM_MID_DZ


STACK_MID_Z = (hub_mid_z(0) + hub_mid_z(COUNT - 1)) / 2.0
# Nominal air between neighbouring hubs at their stations.
HUB_GAP = PITCH - HUB_LENGTH

RUNNING_FLOOR = 0.10  # least running air between oiled steel faces
MARGIN_SPARE = 0.25  # novice spare over every floor (pinion_rig_layout rule)

# --- the ears ------------------------------------------------------------------
# Each ear's inner face from its end arm's nominal mid-plane: .189 north and
# .205 south, on the inch grid so the ears' inner-face span prints 6.094.
# The retired preloaded stack had them at .181 (half a pitch-long hub and a
# .031 washer) and .2046 (that and the spring's 0.60 set): the north ear
# moves .008 out to give the floating end arm its room, and the shaft's
# printed 6.85 still spans both ears.
NORTH_EAR_STANDOFF = 4.8006  # .189
SOUTH_EAR_STANDOFF = 5.207  # .205
# Nominal end faces of the two end hubs, and the ears' faces.
HUB19_NORTH_FACE_Z = hub_mid_z(COUNT - 1) + HUB_LENGTH / 2.0
HUB0_SOUTH_FACE_Z = hub_mid_z(0) - HUB_LENGTH / 2.0
NORTH_EAR_INNER_Z = hub_mid_z(COUNT - 1) + NORTH_EAR_STANDOFF
NORTH_EAR_OUTER_Z = NORTH_EAR_INNER_Z + _bracket.EAR_T
SOUTH_EAR_INNER_Z = hub_mid_z(0) - SOUTH_EAR_STANDOFF
SOUTH_EAR_OUTER_Z = SOUTH_EAR_INNER_Z - _bracket.EAR_T
# Nominal end float: each end hub's face to its ear, (south, north).
END_FLOAT = (
    HUB0_SOUTH_FACE_Z - SOUTH_EAR_INNER_Z,
    NORTH_EAR_INNER_Z - HUB19_NORTH_FACE_Z,
)
# Fit-up: the north ear's inner face is DRO-located off the located drum bank;
# the south bracket is then set to the ears' inner-face span at the title
# block's .XXX, +/-.005 in: delegated ruling 2026-11-25 (Main), precedent:
# owner ruling 2026-11-24 merging the fit policy (a band tighter than the
# title block must earn its place), #2144 (rulings.md D20). It was +/-.004
# (owner ruling X1+B1, 2026-10-18); at +/-.005 END_CLEARANCE_MIN is still
# (0.560, 0.281) mm over the 0.10 running floor, so nothing earns the
# tighter band.
NORTH_EAR_LOCATE_BAND = 0.10  # DRO edge-find on the ear's inner face
EAR_INNER_SPAN = NORTH_EAR_INNER_Z - SOUTH_EAR_INNER_Z
EAR_SPAN_BAND = 0.127  # +/-.005, the title block's .XXX
# Each ear's inner face off its nominal station, (south, north).
EAR_LOCATE_BAND = (NORTH_EAR_LOCATE_BAND + EAR_SPAN_BAND, NORTH_EAR_LOCATE_BAND)
# How far an END arm's hub mid-plane may stand off its nominal station while
# it follows its rod (.034): the cam bank's datum chain and stack to that
# slot, the ring's float in the slot, the rod's ring-to-fork bands, the
# fork's float on the strap and the strap's symmetry to its hub. This layout
# cannot read the cylinder bank (the pivot parts would re-key on it), so the
# allowance is declared here and test_channel_axial_budget holds both end
# stations' stacks inside it.
END_ARM_FOLLOW_MAX = 0.8636
# Least air between each end hub and its ear at that worst case, (south, north).
END_CLEARANCE_MIN = tuple(
    standoff - locate - END_ARM_FOLLOW_MAX - HUB_LENGTH_MAX / 2.0
    for standoff, locate in zip(
        (SOUTH_EAR_STANDOFF, NORTH_EAR_STANDOFF), EAR_LOCATE_BAND, strict=True
    )
)
if min(END_CLEARANCE_MIN) < RUNNING_FLOOR:
    raise AssertionError(
        f"an end rocker hub can reach its bracket ear: {END_CLEARANCE_MIN}"
    )

# Bracket origins (ear mid-planes), (south, north).
PIVOT_BRACKET_Z = (
    SOUTH_EAR_INNER_Z - _bracket.EAR_T / 2.0,
    NORTH_EAR_INNER_Z + _bracket.EAR_T / 2.0,
)

# --- the pivot shaft -----------------------------------------------------------
# Its cylinder spans both ears' outer faces; the shop makes it to the overall
# length, tip to tip, and fit-up sets its north tip DOME_HEIGHT proud of the
# north ear's outer face. The part's origin is the north cylinder end. The
# overall length is the ears' span plus both domes snapped to the printed .XX
# grid, so the south end stands off the south ear's outer face by the snap.
_PRINT_GRID = 25.4 / 10 ** _shaft.DRAWING_PRECISION_BY_NAME["OverallLength"]
PIVOT_SHAFT_OVERALL_LENGTH = (
    round(
        (NORTH_EAR_OUTER_Z - SOUTH_EAR_OUTER_Z + 2.0 * _shaft.DOME_HEIGHT)
        / _PRINT_GRID
    )
    * _PRINT_GRID
)  # 6.85
PIVOT_SHAFT_LENGTH = PIVOT_SHAFT_OVERALL_LENGTH - 2.0 * _shaft.DOME_HEIGHT
PIVOT_SHAFT_NORTH_Z = NORTH_EAR_OUTER_Z
PIVOT_SHAFT_SOUTH_Z = PIVOT_SHAFT_NORTH_Z - PIVOT_SHAFT_LENGTH
# The south cylinder end's nominal offset inboard of the south ear's outer
# face (negative: proud of it), less than half a grid step.
SOUTH_END_INSET = PIVOT_SHAFT_SOUTH_Z - SOUTH_EAR_OUTER_Z
if not abs(SOUTH_END_INSET) <= _PRINT_GRID / 2.0 + 1e-9:
    raise AssertionError("the shaft's overall length is not the ear span's snap")

# Set-screw flats (user, 2026-10-10): one at each end, half an ear from its
# cylinder end, as stations from the shaft's north end (south, north). The
# north one sits under the north ear's apex screw; the south one stands off
# the south ear's by the south end's inset.
PIVOT_SHAFT_FLAT_STATIONS = (
    PIVOT_SHAFT_LENGTH - _shaft.NORTH_FLAT_STATION,
    _shaft.NORTH_FLAT_STATION,
)
if abs(PIVOT_SHAFT_NORTH_Z - PIVOT_BRACKET_Z[1] - _shaft.NORTH_FLAT_STATION) > 1e-9:
    raise AssertionError("the north flat is not under the north ear's set screw")
# Where each flat may sit off its screw at fit-up: the shaft's north tip set
# by depth gauge, and at the south ear the span's set band, which moves the
# south ear along the shaft. The shaft is set on the north ear's OUTBOARD
# face, while the south ear is set from the north ear's INBOARD face, so the
# north ear's thickness band also moves the south flat off its ear.
SHAFT_TIP_SET_BAND = 0.254  # ±.010 in
SOUTH_EAR_SET_RANGE = (-EAR_SPAN_BAND, EAR_SPAN_BAND)
FLAT_OFFSET_MAX = (
    SHAFT_TIP_SET_BAND
    + _bracket.EAR_T_BAND
    + max(abs(v) for v in SOUTH_EAR_SET_RANGE)
    + abs(SOUTH_END_INSET),
    SHAFT_TIP_SET_BAND,
)  # (south, north)
# Each flat is stationed from its own end's tip, so the bar goes in either
# way round; the north one from the tip fit-up sets, the south one from the
# far tip, which the overall length's band also moves (south, north).
FLAT_STATION_ERROR = (
    _shaft.FLAT_STATION_BAND + _shaft.LENGTH_BAND,
    _shaft.FLAT_STATION_BAND,
)
# The south tip stands DOME_HEIGHT less the south end's inset past the south
# ear's outer face, give or take the tip's set, the length's band, both ears'
# thickness bands and the south ear's set: at most this far.
SOUTH_APEX_REACH_MAX = (
    _shaft.DOME_HEIGHT
    - SOUTH_END_INSET
    + SHAFT_TIP_SET_BAND
    + _shaft.LENGTH_BAND
    + 2.0 * _bracket.EAR_T_BAND
    + max(abs(v) for v in SOUTH_EAR_SET_RANGE)
)
# How far a flat may run from its ear's mid-plane before a hub's bore rides
# over its edge: half the thinnest ear and the least air to its end hub
# (END_CLEARANCE_MIN, which already carries the ear's own location). Under
# the ear the flat is harmless (the ear does not run on the shaft). The north
# flat is set from the ear's OUTBOARD face (the shaft's set tip), so the
# inboard face closes by the whole ear-thickness band, not half of it.
FLAT_RUN_MAX = (
    (_bracket.EAR_T - _bracket.EAR_T_BAND) / 2.0 + END_CLEARANCE_MIN[0],
    _bracket.EAR_T / 2.0 - _bracket.EAR_T_BAND + END_CLEARANCE_MIN[1],
)  # (south, north)
# The tap is held from the ear's inboard face. At the south ear that face is
# the flat's reference too; at the north ear the flat is set from the
# outboard face, so the ear-thickness band also lies between flat and tap.
SET_SCREW_TO_FLAT_BAND = (
    _bracket.SET_SCREW_STATION_BAND,
    _bracket.SET_SCREW_STATION_BAND + _bracket.EAR_T_BAND,
)  # (south, north)
for _offset, _station_error, _run_max, _tap_band in zip(
    FLAT_OFFSET_MAX, FLAT_STATION_ERROR, FLAT_RUN_MAX, SET_SCREW_TO_FLAT_BAND, strict=True
):
    _reach = _offset + _station_error + _tap_band
    # The cup lands wholly on the flat...
    if _reach + _shaft.SET_SCREW_CUP_DIA / 2.0 > _shaft.FLAT_LENGTH_RANGE[0] / 2.0:
        raise AssertionError("a set-screw cup runs off its flat at worst case")
    # ...and no hub rides over the flat's edge.
    if (
        _offset + _station_error + _shaft.FLAT_LENGTH_RANGE[1] / 2.0
        > _run_max - RUNNING_FLOOR
    ):
        raise AssertionError("a shaft flat runs under a rocker hub at worst case")

# The ch0 / ch19 amplitude bar's nominal axial air to the ear it faces: the
# ear's stand-off from the arm's mid-plane less the bar's half-width (the bar
# straddles its plate). The north side is the closer.
BAR_TO_EAR = NORTH_EAR_STANDOFF - _bar.BAR_WIDTH / 2.0

__all__ = [
    "ARM_MID_DZ",
    "BAR_TO_EAR",
    "COUNT",
    "EAR_INNER_SPAN",
    "EAR_LOCATE_BAND",
    "EAR_SPAN_BAND",
    "END_ARM_FOLLOW_MAX",
    "END_CLEARANCE_MIN",
    "END_FLOAT",
    "FLAT_OFFSET_MAX",
    "FLAT_RUN_MAX",
    "FLAT_STATION_ERROR",
    "HUB0_SOUTH_FACE_Z",
    "HUB19_NORTH_FACE_Z",
    "HUB_GAP",
    "MARGIN_SPARE",
    "NORTH_EAR_INNER_Z",
    "NORTH_EAR_LOCATE_BAND",
    "NORTH_EAR_OUTER_Z",
    "NORTH_EAR_STANDOFF",
    "PITCH",
    "PIVOT_BRACKET_Z",
    "PIVOT_SHAFT_FLAT_STATIONS",
    "PIVOT_SHAFT_LENGTH",
    "PIVOT_SHAFT_NORTH_Z",
    "PIVOT_SHAFT_OVERALL_LENGTH",
    "PIVOT_SHAFT_SOUTH_Z",
    "RUNNING_FLOOR",
    "SHAFT_TIP_SET_BAND",
    "SOUTH_APEX_REACH_MAX",
    "SOUTH_EAR_INNER_Z",
    "SOUTH_EAR_OUTER_Z",
    "SOUTH_EAR_SET_RANGE",
    "SOUTH_EAR_STANDOFF",
    "SOUTH_END_INSET",
    "STACK_MID_Z",
    "STATION_Z0",
    "hub_mid_z",
]
