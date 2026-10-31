r"""Axial (machine-z) layout of the rocker-arm bank and its retention on the
pivot shaft (issue #743 PR2) -- one source for the channel assembly, the
pivot shaft and the bracket stations.

GEOMETRY ONLY, like ``cylinder_bank_layout``: no drawing notes, no drawing
specs, no title-block reads. It reads the channel stations and ONE datum it
shares with the cylinder bank: the arm plane IS the cam plane
(``cam_plane.CAM_MID_DZ``), because each connecting rod is flat -- its ring
rides the cam and its fork straddles the arm in that one plane. That leaf
reads only the MHA-DT-12 gear spec (and the gear-train config it reads), so
a cylinder-gear spec change re-keys the pivot parts; the cylinder bank's
pedestals, arbor, washers, spring and bank pitch do not reach them.

The bank is a SOLID STACK: each MHA-CH-06 arm's integral hub is one station
pitch long, and neighbouring hubs bear face on face. #948 ruling R (PR #1292)
preloads it with a keeper spring, reversing #743 Q4 (Reading 1, "no keeper"):

* Hub 19 bears on a MHA-CH-VN-56 thrust washer (McMaster 3088A429, a 0.031
  ring shim) against the NORTH bracket ear's inner face (user, 2026-10-10:
  the shaft's shoulder is gone and the washer, kept, goes at both ends).
  That ear is the bank's axial datum:
  fit-up offsets its DRO target by the measured north washer's deviation
  from nominal (MIC_RESIDUAL is what is left of that band), as the cylinder
  bank does for its back washer.
* The SOUTH bracket is set off the thrust washer on hub 0 by one
  ROCKER_SPRING_SET blade, and the MHA-CH-VN-54 wave spring
  (``ch_vn_rocker_bank_spring_spec``) squeezed in that gap holds the stack north
  on the datum ear: the bank has no end play.
* Each hub's length is +0.05/0 on its print, and a fit-up acceptance on the
  measured 20-arm stack caps the cumulative excess (STACK_L20_ACCEPT,
  +.004/0 in, #948 ruling R).
* The shaft is a plain rod whose cylinder spans both ears' outer faces, each
  end domed proud of its ear. One #4-40 set screw down through each ear's
  arch apex bites a flat milled on the shaft at that ear's mid-plane, so the
  screws hold the shaft both axially and in rotation, flats up.

The set-blade and preload rules are the cylinder bank's, restated here
because the rocker bank has its own spring; ``test_rocker_bank_layout`` pins
the two in lockstep.
"""

from __future__ import annotations

import math

import _config
from cam_plane import CAM_MID_DZ
import ch_amplitude_bar_spec as _bar
import ch_pivot_bracket_spec as _bracket
import ch_pivot_shaft_spec as _shaft
import ch_vn_rocker_bank_spring_spec as _spring
import ch_vn_rocker_thrust_washer_spec as _washer
from ch_rocker_arm_spec import HUB_DIA, HUB_LENGTH, HUB_LENGTH_BAND

COUNT = 20  # the full bank (the brackets never follow active_count)

# --- stations ----------------------------------------------------------------
# The ONE station source for the bank (#743 (d), #914 option 1): fit-up sets
# the north bracket in the drive-train step-9 setup off the LOCATED drum bank
# (9A), whose nominal cam stations are these channel stations. Taking the
# bank's as-set Z instead is a change to this line alone.
STATION_Z0 = _config.machine("channels", "station_z0_mm")  # channel 0 gear plane
PITCH = _config.machine("channels", "station_pitch_mm")
# Arm/bar/lever mid-planes, the rod-pin plane and the spring stations sit on
# the cam plane: z_j + CAM_MID_DZ (-3.528, the integral cam's mid-width).
ARM_MID_DZ = CAM_MID_DZ
if abs(HUB_LENGTH - PITCH) > 1e-6:
    raise AssertionError("ch_rocker_arm_spec.HUB_LENGTH must equal the station pitch")


def hub_mid_z(j: int) -> float:
    """Machine z of arm j's plate / hub mid-plane (nominal, pushed north)."""
    return STATION_Z0 + PITCH * j + ARM_MID_DZ


STACK_MID_Z = (hub_mid_z(0) + hub_mid_z(COUNT - 1)) / 2.0

# --- preload (#948 ruling R) ------------------------------------------------------
RUNNING_FLOOR = 0.10  # least running air between oiled steel faces
MARGIN_SPARE = 0.25  # novice spare over every floor (pinion_rig_layout rule)
FEELER_STEP = 0.05  # blades of the metric gauge set (pinion_rig_fitup)
ROCKER_SPRING_SET = _spring.INSTALLED_HEIGHT  # the set blade, 0.60
# Set error (the bracket re-set on its screws): ±.004 in, the inch sheet's band.
ROCKER_SPRING_SET_BAND = 0.1016
ROCKER_SPRING_HEIGHT = (
    ROCKER_SPRING_SET - ROCKER_SPRING_SET_BAND,
    ROCKER_SPRING_SET + ROCKER_SPRING_SET_BAND,
)
# (min, max) preload, N, over the set band [INFERENCE: linear rate].
ROCKER_PRELOAD = (
    _spring.spring_load(ROCKER_SPRING_HEIGHT[1]),
    _spring.spring_load(ROCKER_SPRING_HEIGHT[0]),
)
PRELOAD_LIMITS = (1.0, 10.0)  # light: single-digit N (cylinder_bank_layout)
if not math.isclose(
    ROCKER_SPRING_SET / FEELER_STEP, round(ROCKER_SPRING_SET / FEELER_STEP)
):
    raise AssertionError(f"the spring set {ROCKER_SPRING_SET} is not a gauge blade")
if not (
    _spring.WORKING_HEIGHT
    <= ROCKER_SPRING_HEIGHT[0]
    < ROCKER_SPRING_HEIGHT[1]
    < _spring.FREE_HEIGHT
):
    raise AssertionError(
        f"the set band {ROCKER_SPRING_HEIGHT} leaves {_spring.SKU}'s working range "
        f"{_spring.WORKING_HEIGHT:.4f}..{_spring.FREE_HEIGHT:.4f}"
    )
if not PRELOAD_LIMITS[0] <= ROCKER_PRELOAD[0] < ROCKER_PRELOAD[1] < PRELOAD_LIMITS[1]:
    raise AssertionError(
        f"the rocker preload {ROCKER_PRELOAD} N leaves {PRELOAD_LIMITS}"
    )
# The ch0 amplitude bar's foot passes over the spring as over the hub; the
# washer is smaller still.
if not (_spring.OD + _spring.OD_BAND[0] <= HUB_DIA and _washer.OD_MAX <= HUB_DIA):
    raise AssertionError(
        "the rocker-bank spring or a thrust washer stands proud of the hub"
    )

# Fit-up compensation (#948 ruling R): the fitter mics the north thrust washer
# and offsets the north ear's DRO target by (measured - nominal), so the
# washer's band leaves the chain and only the micrometer reading's residual
# stays.
MIC_RESIDUAL = 0.013  # half a thou: one micrometer reading
NORTH_EAR_LOCATE_BAND = 0.10  # DRO edge-find on the ear's inner face
NORTH_DATUM_STACK = {
    "north ear DRO locate": NORTH_EAR_LOCATE_BAND,
    "north washer, mic-compensated": MIC_RESIDUAL,
}

# --- stack length acceptance ---------------------------------------------------
STACK_L20 = COUNT * HUB_LENGTH  # hub 0 south face to hub 19 north face
# (upper, lower): re-face a long stack. #948 ruling R tightens it from +0.20:
# a fit-up re-face acceptance, not a part band. +.004/0 in on the inch sheet.
STACK_L20_ACCEPT_BAND = (0.1016, 0.0)
STACK_L20_ACCEPT = (
    STACK_L20 + STACK_L20_ACCEPT_BAND[1],
    STACK_L20 + STACK_L20_ACCEPT_BAND[0],
)
if HUB_LENGTH_BAND[1] < 0.0:
    raise AssertionError("a short hub cannot be fixed at fit-up; keep the band +/0")

# --- north: hub 19, washer, datum ear ----------------------------------------------
HUB19_NORTH_FACE_Z = hub_mid_z(COUNT - 1) + HUB_LENGTH / 2.0
NORTH_WASHER_Z = (HUB19_NORTH_FACE_Z, HUB19_NORTH_FACE_Z + _washer.THICKNESS)
NORTH_EAR_INNER_Z = NORTH_WASHER_Z[1]
NORTH_EAR_OUTER_Z = NORTH_EAR_INNER_Z + _bracket.EAR_T

# --- south: washer, spring, set ear -----------------------------------------------
HUB0_SOUTH_FACE_Z = hub_mid_z(0) - HUB_LENGTH / 2.0
SOUTH_WASHER_Z = (HUB0_SOUTH_FACE_Z - _washer.THICKNESS, HUB0_SOUTH_FACE_Z)
SOUTH_EAR_INNER_Z = SOUTH_WASHER_Z[0] - ROCKER_SPRING_SET
SOUTH_EAR_OUTER_Z = SOUTH_EAR_INNER_Z - _bracket.EAR_T
# The spring's installed envelope, south ear to thrust washer.
ROCKER_SPRING_Z = (SOUTH_EAR_INNER_Z, SOUTH_WASHER_Z[0])

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
)  # 6.40
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
# by depth gauge, and at the south ear the stack's acceptance excess, the
# spring blade's set error and both washers' stock bands (the north one moves
# the datum ear with the shaft's set tip, the south one the blade-set ear),
# which move the south ear along the shaft. The shaft is set on the north
# ear's OUTBOARD face, while the south ear is set from the north ear's INBOARD
# face (through the stack), so the north ear's thickness band also moves the
# south flat off its ear.
SHAFT_TIP_SET_BAND = 0.254  # ±.010 in
_WASHER_DEV = (
    _washer.THICKNESS_MIN - _washer.THICKNESS,
    _washer.THICKNESS_MAX - _washer.THICKNESS,
)
SOUTH_EAR_SET_RANGE = (
    -(STACK_L20_ACCEPT_BAND[0] + ROCKER_SPRING_SET_BAND + 2.0 * _WASHER_DEV[1]),
    ROCKER_SPRING_SET_BAND - 2.0 * _WASHER_DEV[0],
)
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
# over its edge: half the thinnest ear, the thinnest washer, and at the south
# ear the shortest spring set. Under the ear, the washer and the spring the
# flat is harmless (none of them runs on the shaft). The north flat is set
# from the ear's OUTBOARD face (the shaft's set tip), so the inboard face
# the hub runs on closes by the whole ear-thickness band, not half of it.
FLAT_RUN_MAX = (
    (_bracket.EAR_T - _bracket.EAR_T_BAND) / 2.0
    + _washer.THICKNESS_MIN
    + ROCKER_SPRING_HEIGHT[0],
    _bracket.EAR_T / 2.0 - _bracket.EAR_T_BAND + _washer.THICKNESS_MIN,
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
# thrust washer's stand-off plus the hub's half-length, less the bar's
# half-width (the bar straddles its plate). The north side is the closer (the
# south one adds the spring's set).
BAR_TO_THRUST_EAR = _washer.THICKNESS + HUB_LENGTH / 2.0 - _bar.BAR_WIDTH / 2.0

__all__ = [
    "ARM_MID_DZ",
    "BAR_TO_THRUST_EAR",
    "COUNT",
    "FEELER_STEP",
    "HUB0_SOUTH_FACE_Z",
    "HUB19_NORTH_FACE_Z",
    "FLAT_OFFSET_MAX",
    "FLAT_RUN_MAX",
    "FLAT_STATION_ERROR",
    "MARGIN_SPARE",
    "MIC_RESIDUAL",
    "NORTH_DATUM_STACK",
    "NORTH_EAR_LOCATE_BAND",
    "NORTH_EAR_INNER_Z",
    "NORTH_EAR_OUTER_Z",
    "NORTH_WASHER_Z",
    "PITCH",
    "PIVOT_BRACKET_Z",
    "PIVOT_SHAFT_LENGTH",
    "PIVOT_SHAFT_NORTH_Z",
    "PIVOT_SHAFT_OVERALL_LENGTH",
    "PIVOT_SHAFT_FLAT_STATIONS",
    "PIVOT_SHAFT_SOUTH_Z",
    "PRELOAD_LIMITS",
    "ROCKER_PRELOAD",
    "ROCKER_SPRING_HEIGHT",
    "ROCKER_SPRING_SET",
    "ROCKER_SPRING_SET_BAND",
    "ROCKER_SPRING_Z",
    "RUNNING_FLOOR",
    "SOUTH_END_INSET",
    "SHAFT_TIP_SET_BAND",
    "SOUTH_EAR_INNER_Z",
    "SOUTH_APEX_REACH_MAX",
    "SOUTH_EAR_OUTER_Z",
    "SOUTH_EAR_SET_RANGE",
    "SOUTH_WASHER_Z",
    "STACK_L20",
    "STACK_L20_ACCEPT",
    "STACK_MID_Z",
    "STATION_Z0",
    "hub_mid_z",
]
