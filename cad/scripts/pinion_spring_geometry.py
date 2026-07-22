r"""Geometry-only contract for the pinion return leaf spring.

The drive-train assembly imports this module directly so drawing-note edits do
not become assembly recipe changes.
"""

from __future__ import annotations

import math

from _holes import HoleSpec, blind_cut_dia_mm

THICK = 0.8
WIDTH = 4.0
FOOT_LEN = 31.0
R_BEND = 2.0
R_KINK = 1.5
KINK_DEG = 20.0
FLAT_LEN = 2.0
BLADE_TILT_DEG = 12.38

PIVOT_LX = 1.16 - 9.04
PIVOT_LY = 62.8 - 50.8
AXIS_OFFSET = 10.1
KINK_T = 32.0
FOOT_Y = 0.8
HOLE_SPEC = HoleSpec("clearance", "#4")
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
HOLE_FROM_END = 3.1

_TH = math.radians(BLADE_TILT_DEG)
_U = (math.sin(_TH), math.cos(_TH))
_N = (math.cos(_TH), -math.sin(_TH))
BEND_CY = FOOT_Y + R_BEND
BEND_CX = PIVOT_LX + (AXIS_OFFSET - R_BEND - (BEND_CY - PIVOT_LY) * _N[1]) / _N[0]
BEND_EXIT = (BEND_CX + R_BEND * _N[0], BEND_CY + R_BEND * _N[1])
FOOT_TAN = (BEND_CX, FOOT_Y)
FOOT_END = (BEND_CX - FOOT_LEN, FOOT_Y)
KINK_START = (
    PIVOT_LX + KINK_T * _U[0] + AXIS_OFFSET * _N[0],
    PIVOT_LY + KINK_T * _U[1] + AXIS_OFFSET * _N[1],
)
KINK_C = (KINK_START[0] - R_KINK * _N[0], KINK_START[1] - R_KINK * _N[1])
_A1 = math.atan2(_N[1], _N[0])
_A2 = _A1 + math.radians(KINK_DEG)
KINK_EXIT = (KINK_C[0] + R_KINK * math.cos(_A2), KINK_C[1] + R_KINK * math.sin(_A2))
_FLAT_DIR = (
    math.sin(math.radians(BLADE_TILT_DEG - KINK_DEG)),
    math.cos(math.radians(BLADE_TILT_DEG - KINK_DEG)),
)
FLAT_TIP = (
    KINK_EXIT[0] + FLAT_LEN * _FLAT_DIR[0],
    KINK_EXIT[1] + FLAT_LEN * _FLAT_DIR[1],
)

_BEND_SWEEP = math.radians(90.0 - BLADE_TILT_DEG)
_BLADE_LEN = math.hypot(KINK_START[0] - BEND_EXIT[0], KINK_START[1] - BEND_EXIT[1])
BLADE_STRAIGHT_LEN = _BLADE_LEN
PATH_LEN = (
    FOOT_LEN
    + R_BEND * _BEND_SWEEP
    + _BLADE_LEN
    + R_KINK * math.radians(KINK_DEG)
    + FLAT_LEN
)
_ARC_SIDE = (math.radians(KINK_DEG) + _BEND_SWEEP) * (THICK / 2.0) * THICK
VOLUME = (PATH_LEN * THICK + _ARC_SIDE) * WIDTH
