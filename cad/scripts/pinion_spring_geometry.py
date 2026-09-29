r"""Geometry-only contract for the pinion return leaf spring (MHA-114).

The drive-train assembly imports this module directly so drawing-note edits do
not become assembly recipe changes.

Re-derived 2026-09-24 (swing, handoff dt-pinion-spring-rederive-20260924): the
previous foot ran 35 mm WEST under the strap and the lift rod, from a mis-read
of ch25 img01 (its image-left is the DRUM side, east).  The screw sits EAST of
the back strap, outboard.  The blade rises from it toward the east flank, with
its crest now 3.2 below the arbor; img04's ~5-below estimate was not a datum.

Part-local frame: +x is machine EAST (the assembly places the part with a
Ry(180)), +y is up, y 0 is the base top.  The sketch path is the INSIDE
surface of the formed strip -- the foot's top face and the blade's east face --
and the wall lies outside it: under the foot, west of the blade.  The blade's
west face is the contact face.
"""

from __future__ import annotations

import itertools
import math

from _hole_spec import HoleSpec, blind_cut_dia_mm
from pinion_rig_park_geometry import STRAP_LEAN_DEG
from pinion_spring_section import (
    PAD_WIDTH,
    PAD_WIDTH_PLACES as PAD_WIDTH_PLACES,
    SCREW_EAST_OF_PIVOT,
    THICK,
    WIDTH,
    WIDTH_PLACES as WIDTH_PLACES,
)

# The manufactured leaf references the actual cam-contact rest strap, not the
# obsolete level-centre construction (which left air beneath the follower).
STRAP_HALF_WIDTH = 7.5

# The part owns a convenient local frame; the assembly translates this local
# pivot onto the live strap pivot.  These are not machine coordinates.
PIVOT_LX = -7.88
PIVOT_LY = 12.0

# Minimum inside bend radius (#859 ruling 4, Main 2026-09-25).  No 17-7 PH
# bulletin publishes one for Condition C (ATI 17-7 TDS; Cleveland-Cliffs 17-7 PH
# 07/2024; ASTM A693-02 Table 6 bends only the solution-treated condition).  The
# nearest published value is a PROXY: NASA SP-5089 (1968) Table XXXI "Design
# standard bend radii used for brake forming", 17-7 PH (STA), 0.012-0.016 in
# sheet: R 0.13 in.  Condition C is the less ductile state (A693-02 Table 5:
# 1 % elongation min vs 3-5 % STA), so the proxy is not a guarantee: the bend
# trial in cad/docs/tolerance-policy.md is mandatory before release.
MIN_INSIDE_BEND_R = 0.13 * 25.4  # 3.302
R_BEND = MIN_INSIDE_BEND_R
R_KINK = MIN_INSIDE_BEND_R  # the crest
KINK_DEG = 28.0  # flick angle past the crest
MIN_CREST_ARC_MARGIN_DEG = 3.0  # assembly gate reserves each crest-arc end
FLAT_LEN = 2.0
FOOT_Y = THICK  # the foot's top face (the path); its underside is the base top

# Contact (img04): the crest bears on the straight east flank near the arbor.
# The photo's ~5 mm below the arbor was an approximate scale reading, not a
# fixed seat: at the revised cam-contact rest, moving the bearing station
# 1.8 mm upward gives formed-corner preload and stress reserve while leaving
# at least 0.25 mm extra spare beyond the 1.0 mm arbor end-cap keep-out at the
# farthest formed contact.
# The parked pose retains 0.15 air; the preset presses the free crest into it.
CONTACT_T = 24.8
MIN_ARBOR_END_CAP_SPARE_MM = 0.25
PARKED_AIR = 0.15

# Screw-down pad: #4 clearance, webs >= 2.0 at the printed .XX worst case
# (test_pinion_spring_drawing), which takes the 9.5 square.  The screw is
# 20.7 east of the pivot axis, 13.2 east of the flank.  The bend starts at
# the pad's edge (FOOT_FLAT=0), leaving the blade 9.77 deg to the parked
# flank, within the 9-13 deg photo band.
HOLE_SPEC = HoleSpec("clearance", "#4")
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
PAD_LEN = 9.5
PAD_LEN_PLACES = 2  # PadLen prints .XX (pinion_spring_spec)
HOLE_FROM_END = 4.5
FOOT_FLAT = 0.0
FOOT_LEN = PAD_LEN + FOOT_FLAT  # free end to the bend tangent
# #859 option (iv): the pad is flush with the strip's aft edge and widens
# forward only (pinion_rig_layout).  Placed Ry(180), the part's local +z
# runs machine -z (forward), so the pad's centre, and the hole's, stand
# PAD_Z local +z of the strip's mid-plane.
PAD_Z = (PAD_WIDTH - WIDTH) / 2.0

# Spring rate and preset, 17-7 PH Condition C (#859 ruling 4).  The part is
# modelled in its installed, parked shape (O2); the maker forms the FREE shape,
# the blade turned PRESET_DEG further toward the strap about the bend centre,
# so the free crest stands PRESET into the parked flank.
# E: 200 GPa (29.0e3 ksi), the aged-condition modulus -- Cleveland-Cliffs 17-7
# PH bulletin (07/2024) Table 7 lists it for TH 1050 / RH 950 and the Armco
# 17-7 PH bulletin (10/2022) gives 200 GPa static for CH 900; neither lists
# Condition C, so the aged value stands in.
MODULUS_MPA = 200_000.0
# The hand-formed profile's band (Main's r6 ruling (c)); the print states it
# as pinion_spring_spec.FORMED_TOLERANCE_MM.  The drive train gates preload at
# the band's low end and stress at its high end, each at the stock corner.
FORMED_BAND_MM = 0.5
# Design yield: ASTM A693-02 Table 5, Type 631 (S17700) "cold rolled at mill"
# (Condition C), 0.0015-0.050 in: 0.2 % yield 175 ksi (1205 MPa) MINIMUM,
# tensile 200 ksi min.  The standard guarantees the yield itself, so no
# scaling from tensile applies (ruling 1's rule was for tensile-only minima).
# The optional CH 900 age (482 C, 1 h) raises it and is NOT counted.
YIELD_MPA = 1205.0
PRESET_DEG = 5.4  # balances the 32-corner preload and engaged-yield reserves

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


def contact_force(
    deflection_mm: float,
    thick: float = THICK,
    width: float = WIDTH,
    arm: float = BLADE_ARM,
) -> float:
    """Normal force (N) at the crest for a crest deflection (mm), for a strip
    of ``thick`` x ``width`` on a cantilever ``arm`` long (the nominal part by
    default)."""
    return MODULUS_MPA * width * thick**3 / (4.0 * arm**3) * deflection_mm


def root_stress(
    deflection_mm: float, thick: float = THICK, arm: float = BLADE_ARM
) -> float:
    """Bending stress (MPa) at the blade root for a crest deflection (mm)."""
    return 1.5 * MODULUS_MPA * thick * deflection_mm / arm**2


# The formed profile as the print holds it (Codex #859, PRRT_kwDOPHDy386mTao2):
# FootLen, BendR, the free kink start's FreeKinkH / FreeKinkV from the foot's
# free end, and KinkR each carry FORMED_BAND_MM on their own.  FlatLen and
# FreeTipH shape the flick past the crest's contact point, so they move
# neither the contact nor the arm.  A corner is one sign per band.
FREE_KINK_H = FOOT_END[0] - FREE_KINK_START[0]
FREE_KINK_V = FREE_KINK_START[1] - FOOT_END[1]
FORMED_CONTACT_BANDS = ("FootLen", "BendR", "FreeKinkH", "FreeKinkV", "KinkR")


def _formed_root_and_tangent(
    deviations: dict[str, float] | None,
) -> tuple[tuple[float, float], tuple[float, float], float, float]:
    """Root centre, free kink tangent, root radius and free blade angle."""
    dev = deviations or {}
    r_bend = R_BEND + dev.get("BendR", 0.0)
    bend_c = (FOOT_END[0] - FOOT_LEN - dev.get("FootLen", 0.0), FOOT_Y + r_bend)
    kink_start = (
        FOOT_END[0] - FREE_KINK_H - dev.get("FreeKinkH", 0.0),
        FOOT_END[1] + FREE_KINK_V + dev.get("FreeKinkV", 0.0),
    )
    dx, dy = bend_c[0] - kink_start[0], bend_c[1] - kink_start[1]
    lean = math.atan2(dy, dx) + math.acos(r_bend / math.hypot(dx, dy))
    return bend_c, kink_start, r_bend, lean


def formed_contact(
    deviations: dict[str, float] | None = None, thick: float = THICK
) -> tuple[float, float, float]:
    """(penetration, arm, station) of a formed FREE profile, mm.

    ``deviations`` moves each named FORMED_CONTACT_BANDS dimension off its
    nominal.  The foot's free end is fixed (the pad screw); the bend starts
    FootLen west of it; the blade is the tangent from the free kink start to
    the bend circle; the crest's outer face is KinkR + ``thick`` round its
    centre.  Penetration is how far that face stands into the parked flank,
    arm runs from the bend exit to the contact along the blade, and station
    is the contact's distance up the strap from the pivot.
    """
    bend_c, kink_start, r_bend, lean = _formed_root_and_tangent(deviations)
    r_kink = R_KINK + (deviations or {}).get("KinkR", 0.0)
    up = (-math.sin(lean), math.cos(lean))
    west = (-math.cos(lean), -math.sin(lean))
    bend_exit = _add(bend_c, west, r_bend)
    kink_c = _add(kink_start, west, -r_kink)
    outer = r_kink + thick
    contact = _add(kink_c, STRAP_N, -outer)
    rel = (kink_c[0] - _PIVOT[0], kink_c[1] - _PIVOT[1])
    penetration = STRAP_HALF_WIDTH - (rel[0] * STRAP_N[0] + rel[1] * STRAP_N[1] - outer)
    arm = (contact[0] - bend_exit[0]) * up[0] + (contact[1] - bend_exit[1]) * up[1]
    station = (contact[0] - _PIVOT[0]) * STRAP_U[0] + (contact[1] - _PIVOT[1]) * STRAP_U[1]
    return penetration, arm, station


def formed_contact_arc_sweep(
    deviations: dict[str, float], swing_deg: float
) -> float:
    """Contact-normal rotation from the formed blade's crest entry, degrees.

    Zero is the blade-side tangent; negative values advance over the crest.
    Installed machine swing is reversed by the spring's Ry(180) placement.
    """
    _, _, _, lean = _formed_root_and_tangent(deviations)
    west_angle = math.atan2(-math.sin(lean), -math.cos(lean))
    contact_angle = _CONTACT_ANGLE - math.radians(swing_deg)
    return math.degrees((contact_angle - west_angle + math.pi) % (2.0 * math.pi) - math.pi)


FORMED_CORNERS = tuple(
    dict(zip(FORMED_CONTACT_BANDS, (s * FORMED_BAND_MM for s in signs), strict=True))
    for signs in itertools.product((-1.0, 1.0), repeat=len(FORMED_CONTACT_BANDS))
)


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
if min(R_BEND, R_KINK) < MIN_INSIDE_BEND_R - 1e-9:
    raise AssertionError("an inside radius is tighter than the 17-7 PH minimum")
