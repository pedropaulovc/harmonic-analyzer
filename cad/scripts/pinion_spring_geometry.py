r"""Geometry-only contract for the pinion return leaf spring (MHA-114).

The drive-train assembly imports this module directly so drawing-note edits do
not become assembly recipe changes.

Re-derived 2026-09-24 (swing, handoff dt-pinion-spring-rederive-20260924): the
previous foot ran 35 mm WEST under the strap and the lift rod, from a mis-read
of ch25 img01 (its image-left is the DRUM side, east).  The screw sits EAST of
the back strap, outboard, and the blade rises from it leaning IN toward the
strap, bearing on the east flank about 5 below the arbor (img04).

Part-local frame: +x is machine EAST (the assembly places the part with a
Ry(180)), +y is up, y 0 is the base top.  The sketch path is the INSIDE
surface of the formed strip -- the foot's top face and the blade's east face --
and the wall lies outside it: under the foot, west of the blade.  The blade's
west face is the contact face.
"""

from __future__ import annotations

import math

from _hole_spec import HoleSpec, blind_cut_dia_mm
from pinion_spring_section import (
    PAD_WIDTH,
    PAD_WIDTH_PLACES as PAD_WIDTH_PLACES,
    SCREW_EAST_OF_PIVOT,
    THICK,
    WIDTH,
    WIDTH_PLACES as WIDTH_PLACES,
)

# The strap the blade bears on (the drive train asserts both in lockstep).
STRAP_LEAN_DEG = 8.138574451932667  # parked lean, top east
STRAP_HALF_WIDTH = 7.5

# The part owns a convenient local frame; the assembly translates this local
# pivot onto the live strap pivot.  These are not machine coordinates.
PIVOT_LX = -7.88
PIVOT_LY = 12.0

R_BEND = 2.0
R_KINK = 1.5  # the crest
KINK_DEG = 25.0  # the flick turns back EAST above the crest
FLAT_LEN = 2.0
FOOT_Y = THICK  # the foot's top face (the path); its underside is the base top

# Contact (img04): the crest bears on the straight east flank 23.0 up the strap
# from the pivot, 5.0 below the arbor.  The model's parked pose keeps 0.15 of
# air there (no exact tangency: the cam's PR5 lesson); physically the crest is
# on the flank, pressed by the preset below.
CONTACT_T = 23.0
PARKED_AIR = 0.15

# Screw-down pad: #4 clearance, webs >= 2.0 at the printed .XX worst case
# (test_pinion_spring_drawing), which takes the 9.5 square.  O5 (Main,
# 2026-09-24, option c): the screw stands 20.0 east of the pivot axis -- 12.5
# east of the flank -- which keeps the blade at the packet's 10.35 deg to the
# flank.  FOOT_FLAT is the straight between the pad and the bend.
HOLE_SPEC = HoleSpec("clearance", "#4")
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
PAD_LEN = 9.5
PAD_LEN_PLACES = 2  # PadLen prints .XX (pinion_spring_spec)
HOLE_FROM_END = 4.5
FOOT_FLAT = 0.5
FOOT_LEN = PAD_LEN + FOOT_FLAT  # free end to the bend tangent
# #859 option (iv): the pad is flush with the strip's aft edge and widens
# forward only (pinion_rig_layout).  Placed Ry(180), the part's local +z
# runs machine -z (forward), so the pad's centre, and the hole's, stand
# PAD_Z local +z of the strip's mid-plane.
PAD_Z = (PAD_WIDTH - WIDTH) / 2.0

# Spring rate and preset.  C51000 spring temper (CDA typical values).  The
# part is modelled in its installed, parked shape (O2); the maker forms the
# FREE shape, the blade turned PRESET_DEG further toward the strap about the
# bend centre, so the free crest stands PRESET into the parked flank.
MODULUS_MPA = 110_000.0
# The hand-formed profile's band (Main's r6 ruling (c)); the print states it
# as pinion_spring_spec.FORMED_TOLERANCE_MM, and the preset is gated at its
# low end.
FORMED_BAND_MM = 0.5
YIELD_MPA = 550.0
PRESET_DEG = 3.4

_LAM = math.radians(STRAP_LEAN_DEG)
STRAP_U = (math.sin(_LAM), math.cos(_LAM))  # up the strap axis
STRAP_N = (math.cos(_LAM), -math.sin(_LAM))  # east normal of the strap axis


def _add(p: tuple[float, float], v: tuple[float, float], s: float = 1.0):
    return (p[0] + s * v[0], p[1] + s * v[1])


def _cw(v: tuple[float, float], deg: float) -> tuple[float, float]:
    """``v`` turned clockwise (toward +x from +y) by ``deg``."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (v[0] * c + v[1] * s, -v[0] * s + v[1] * c)


_PIVOT = (PIVOT_LX, PIVOT_LY)
HOLE_X = PIVOT_LX + SCREW_EAST_OF_PIVOT
FOOT_END = (HOLE_X + HOLE_FROM_END, FOOT_Y)  # the free end, east
FOOT_TAN = (FOOT_END[0] - FOOT_LEN, FOOT_Y)  # the bend tangent, west
BEND_CX = FOOT_TAN[0]
BEND_CY = FOOT_Y + R_BEND

# The parked contact point on the crest's west (outer) face, and the crest
# centre east of it.
CREST = _add(_add(_PIVOT, STRAP_N, STRAP_HALF_WIDTH + PARKED_AIR), STRAP_U, CONTACT_T)
KINK_C = _add(CREST, STRAP_N, R_KINK + THICK)

# Blade lean: the one straight tangent to both the bend (inside radius, its
# centre east of the path) and the crest (inside radius, centre east too).
# With W the blade's west normal, (bend centre - crest centre) . W equals
# R_KINK - R_BEND; B = (-sin a, cos a) leans a WEST of vertical.
_DX, _DY = BEND_CX - KINK_C[0], BEND_CY - KINK_C[1]
_BLADE_A = math.atan2(_DY, _DX) + math.acos((R_BEND - R_KINK) / math.hypot(_DX, _DY))
BLADE_LEAN_DEG = math.degrees(_BLADE_A)  # west of vertical
BLADE_TO_FLANK_DEG = BLADE_LEAN_DEG + STRAP_LEAN_DEG
_B = (-math.sin(_BLADE_A), math.cos(_BLADE_A))  # up the blade
_W = (-math.cos(_BLADE_A), -math.sin(_BLADE_A))  # the blade's west normal
BEND_EXIT = _add((BEND_CX, BEND_CY), _W, R_BEND)
KINK_START = _add(KINK_C, _W, R_KINK)
_W_FLICK = _cw(_W, KINK_DEG)
_B_FLICK = _cw(_B, KINK_DEG)
KINK_EXIT = _add(KINK_C, _W_FLICK, R_KINK)
FLAT_TIP = _add(KINK_EXIT, _B_FLICK, FLAT_LEN)

BLADE_STRAIGHT_LEN = math.hypot(
    KINK_START[0] - BEND_EXIT[0], KINK_START[1] - BEND_EXIT[1]
)
_BEND_SWEEP = math.radians(90.0 - BLADE_LEAN_DEG)
PATH_LEN = (
    FOOT_LEN
    + R_BEND * _BEND_SWEEP
    + BLADE_STRAIGHT_LEN
    + R_KINK * math.radians(KINK_DEG)
    + FLAT_LEN
)
# Both arcs carry the wall on their convex side: each adds theta * T^2 / 2.
_ARC_SIDE = (math.radians(KINK_DEG) + _BEND_SWEEP) * (THICK / 2.0) * THICK
VOLUME = (PATH_LEN * THICK + _ARC_SIDE) * WIDTH
PAD_VOLUME = (PAD_WIDTH - WIDTH) * PAD_LEN * THICK  # the wings beside the strip

# Free (as-formed) profile: everything past the bend exit turned PRESET_DEG
# counter-clockwise (toward the strap) about the bend centre.
_BEND_C = (BEND_CX, BEND_CY)


def _free(p: tuple[float, float]) -> tuple[float, float]:
    v = _cw((p[0] - BEND_CX, p[1] - BEND_CY), -PRESET_DEG)
    return _add(_BEND_C, v)


FREE_BEND_EXIT = _free(BEND_EXIT)
FREE_KINK_START = _free(KINK_START)
FREE_KINK_C = _free(KINK_C)
FREE_KINK_EXIT = _free(KINK_EXIT)
FREE_FLAT_TIP = _free(FLAT_TIP)
# How far the free crest stands into the parked flank, along the flank normal.
PRESET = (
    (CREST[0] - _free(CREST)[0]) * STRAP_N[0]
    + (CREST[1] - _free(CREST)[1]) * STRAP_N[1]
    - PARKED_AIR
)

# Cantilever from the blade root (the bend exit) to the contact.
BLADE_ARM = (CREST[0] - BEND_EXIT[0]) * _B[0] + (CREST[1] - BEND_EXIT[1]) * _B[1]
RATE_N_PER_MM = MODULUS_MPA * WIDTH * THICK**3 / (4.0 * BLADE_ARM**3)


def contact_force(deflection_mm: float) -> float:
    """Normal force (N) at the crest for a crest deflection (mm)."""
    return RATE_N_PER_MM * deflection_mm


def root_stress(deflection_mm: float) -> float:
    """Bending stress (MPa) at the blade root for a crest deflection (mm)."""
    return 1.5 * MODULUS_MPA * THICK * deflection_mm / BLADE_ARM**2


# The contact normal (-N) must fall on the crest arc, between the blade's west
# normal and the flick's.
_CONTACT_ANGLE = math.atan2(-STRAP_N[1], -STRAP_N[0])
_ARC_FROM = math.atan2(_W[1], _W[0])
if not (
    math.radians(-KINK_DEG) - 1e-9
    <= (_CONTACT_ANGLE - _ARC_FROM + math.pi) % (2.0 * math.pi) - math.pi
    <= 1e-9
):
    raise AssertionError("the flank contact misses the crest arc")
if (KINK_START[0] - BEND_EXIT[0]) * _B[0] + (KINK_START[1] - BEND_EXIT[1]) * _B[
    1
] <= 0.0:
    raise AssertionError("the blade runs backwards between bend and crest")
