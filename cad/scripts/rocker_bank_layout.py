r"""Axial (machine-z) layout of the rocker-arm bank and its retention on the
pivot shaft (issue #743 PR2) -- one source for the channel assembly, the
pivot shaft and the bracket stations.

GEOMETRY ONLY, like ``cylinder_bank_layout``: no drawing notes, no drawing
specs, no title-block reads. It reads the channel stations and nothing from
the gear train, so the pivot parts never re-key on a cone or gear edit.

The bank is a SOLID STACK: each MHA-071 arm's integral hub is one station
pitch long, and neighbouring hubs bear face on face. Reading 1 (user, #743
Q4) retains it with no keeper:

* The pivot shaft's integral O10 x 1.5 SHOULDER bears on the NORTH bracket
  ear's inner face, and hub 19 bears on the shoulder. That ear is the bank's
  axial datum; the stack is pushed north against it.
* The SOUTH bracket is feeler-set: one ROCKER_END_FEELER leaf between the
  MHA-148 thrust washer on hub 0 and the south ear. That gap is the bank's
  assembled end play E_r, and the shaft floats by the same E_r (the shoulder
  pulls the stack south until the washer meets the south ear).
* Each hub's length is +0.05/0 on its print, and a fit-up acceptance on the
  measured 20-arm stack caps the cumulative excess (STACK_L20_ACCEPT).
* The shaft's cylinder spans both ears' outer faces, and each end is domed
  proud of its ear.

The feeler rule is the cylinder bank's (and ``pinion_rig_layout``'s),
restated here rather than imported so the pivot parts read no gear-train
config; ``test_rocker_bank_layout`` pins the two in lockstep.
"""

from __future__ import annotations

import math

import _config
import amplitude_bar_spec as _bar
import pivot_bracket_spec as _bracket
import pivot_shaft_spec as _shaft
import rocker_thrust_washer_spec as _washer
from rocker_arm_spec import HUB_LENGTH, HUB_LENGTH_BAND

COUNT = 20  # the full bank (the brackets never follow active_count)

# --- stations ----------------------------------------------------------------
# The ONE station source for the bank (#743 (d), #914 option 1): fit-up sets
# the north bracket in the drive-train step-9 setup off the LOCATED drum bank
# (9A), whose nominal cam stations are these channel stations. Taking the
# bank's as-set Z instead is a change to this line alone.
STATION_Z0 = _config.machine("channels", "station_z0_mm")  # channel 0 gear plane
PITCH = _config.machine("channels", "station_pitch_mm")
ARM_MID_DZ = 0.8  # arm/bar/lever mid-planes sit at z_j + 0.8
if abs(HUB_LENGTH - PITCH) > 1e-6:
    raise AssertionError("rocker_arm_spec.HUB_LENGTH must equal the station pitch")


def hub_mid_z(j: int) -> float:
    """Machine z of arm j's plate / hub mid-plane (nominal, pushed north)."""
    return STATION_Z0 + PITCH * j + ARM_MID_DZ


STACK_MID_Z = (hub_mid_z(0) + hub_mid_z(COUNT - 1)) / 2.0

# --- end play (E_r) ------------------------------------------------------------
MIN_END_PLAY = 0.10  # running floor for 20 oiled steel hub faces
MARGIN_SPARE = 0.25  # novice spare over every floor (pinion_rig_layout rule)
FEELER_STEP = 0.05  # blades of the metric gauge set (pinion_rig_fitup)
ROCKER_END_FEELER_BAND = 0.10  # set error: the bracket re-set on its screws
ROCKER_END_FEELER = FEELER_STEP * math.ceil(
    round((MIN_END_PLAY + MARGIN_SPARE + ROCKER_END_FEELER_BAND) / FEELER_STEP, 9)
)
ROCKER_END_PLAY = (
    ROCKER_END_FEELER - ROCKER_END_FEELER_BAND,
    ROCKER_END_FEELER + ROCKER_END_FEELER_BAND,
)

# --- stack length acceptance ---------------------------------------------------
STACK_L20 = COUNT * HUB_LENGTH  # hub 0 south face to hub 19 north face
STACK_L20_ACCEPT_BAND = (0.20, 0.0)  # (upper, lower): re-face a long stack
STACK_L20_ACCEPT = (
    STACK_L20 + STACK_L20_ACCEPT_BAND[1],
    STACK_L20 + STACK_L20_ACCEPT_BAND[0],
)
if HUB_LENGTH_BAND[1] < 0.0:
    raise AssertionError("a short hub cannot be fixed at fit-up; keep the band +/0")

# --- north: shoulder against the datum ear ------------------------------------
HUB19_NORTH_FACE_Z = hub_mid_z(COUNT - 1) + HUB_LENGTH / 2.0
SHOULDER_Z = (HUB19_NORTH_FACE_Z, HUB19_NORTH_FACE_Z + _shaft.SHOULDER_LENGTH)
NORTH_EAR_INNER_Z = SHOULDER_Z[1]
NORTH_EAR_OUTER_Z = NORTH_EAR_INNER_Z + _bracket.EAR_T

# --- south: washer, leaf, feeler-set ear --------------------------------------
HUB0_SOUTH_FACE_Z = hub_mid_z(0) - HUB_LENGTH / 2.0
SOUTH_WASHER_Z = (HUB0_SOUTH_FACE_Z - _washer.THICKNESS, HUB0_SOUTH_FACE_Z)
SOUTH_EAR_INNER_Z = SOUTH_WASHER_Z[0] - ROCKER_END_FEELER
SOUTH_EAR_OUTER_Z = SOUTH_EAR_INNER_Z - _bracket.EAR_T

# Bracket origins (ear mid-planes), (south, north).
PIVOT_BRACKET_Z = (
    SOUTH_EAR_INNER_Z - _bracket.EAR_T / 2.0,
    NORTH_EAR_INNER_Z + _bracket.EAR_T / 2.0,
)

# --- the pivot shaft -----------------------------------------------------------
# Its cylinder spans both ears' outer faces (the fitter's measurement); the
# shoulder sits one ear thickness in from the north end. The part's origin is
# that north end.
PIVOT_SHAFT_LENGTH = NORTH_EAR_OUTER_Z - SOUTH_EAR_OUTER_Z
PIVOT_SHAFT_SOUTH_Z = SOUTH_EAR_OUTER_Z
PIVOT_SHAFT_NORTH_Z = NORTH_EAR_OUTER_Z
NORTH_JOURNAL_LENGTH = _shaft.JOURNAL_LENGTH
PIVOT_SHAFT_OVERALL_LENGTH = PIVOT_SHAFT_LENGTH + 2.0 * _shaft.DOME_HEIGHT
# The plain (south) end is cut flush with the south ear's outer face to 0.5
# proud, then domed: with the shaft floated south by E_r max, its apex stands
# this far south of the ear's outer face at the worst case.
PLAIN_END_CUT_BAND = (0.5, 0.0)  # (upper, lower) past the south ear's outer face
SOUTH_APEX_REACH_MAX = PLAIN_END_CUT_BAND[0] + _shaft.DOME_HEIGHT + ROCKER_END_PLAY[1]
if abs(PIVOT_SHAFT_NORTH_Z - NORTH_JOURNAL_LENGTH - SHOULDER_Z[1]) > 1e-9:
    raise AssertionError("the shaft's shoulder is not on the north ear's inner face")

# The ch0 / ch19 amplitude bar's nominal axial air to the ear it faces: the
# stand-off, plus the hub's half-length, less the bar's half-width (the bar
# straddles its plate).
BAR_TO_THRUST_EAR = _shaft.SHOULDER_LENGTH + HUB_LENGTH / 2.0 - _bar.BAR_WIDTH / 2.0

__all__ = [
    "ARM_MID_DZ",
    "BAR_TO_THRUST_EAR",
    "COUNT",
    "FEELER_STEP",
    "HUB0_SOUTH_FACE_Z",
    "HUB19_NORTH_FACE_Z",
    "MARGIN_SPARE",
    "MIN_END_PLAY",
    "NORTH_EAR_INNER_Z",
    "NORTH_EAR_OUTER_Z",
    "NORTH_JOURNAL_LENGTH",
    "PITCH",
    "PLAIN_END_CUT_BAND",
    "PIVOT_BRACKET_Z",
    "PIVOT_SHAFT_LENGTH",
    "PIVOT_SHAFT_NORTH_Z",
    "PIVOT_SHAFT_OVERALL_LENGTH",
    "PIVOT_SHAFT_SOUTH_Z",
    "ROCKER_END_FEELER",
    "ROCKER_END_FEELER_BAND",
    "ROCKER_END_PLAY",
    "SHOULDER_Z",
    "SOUTH_EAR_INNER_Z",
    "SOUTH_APEX_REACH_MAX",
    "SOUTH_EAR_OUTER_Z",
    "SOUTH_WASHER_Z",
    "STACK_L20",
    "STACK_L20_ACCEPT",
    "STACK_MID_Z",
    "STATION_Z0",
    "hub_mid_z",
]
