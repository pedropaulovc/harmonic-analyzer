r"""Geometry-only contract for the pinion return leaf spring (MHA-114).

The drive-train assembly imports this module directly so drawing-note edits do
not become assembly recipe changes.

Re-derived 2026-09-24 (swing, handoff dt-pinion-spring-rederive-20260924): the
previous foot ran 35 mm WEST under the strap and the lift rod, from a mis-read
of ch25 img01 (its image-left is the DRUM side, east).  The screw sits EAST of
the back strap, outboard.  The blade rises from it toward the east flank.

Bent a bit more (2026-09-29, PR #1127): the print now holds the FREE (as
formed) profile -- FootLen, BendR, FreeKinkH, FreeKinkV, KinkR, FreeTipH,
FlatLen -- and the pad is SET off the parked strap flank itself (SPRING SET:
slide the leaf west until the crest touches the parked flank, push the pad
SET_PUSH_MM further west, tighten, spot the seat), so no strap cap, c2c, lean
or block .X error reaches the crest's penetration.  Every load number comes
from the root-compliant elastica in pinion_spring_load over the full printed
envelope; the installed solid below is the free profile turned about the bend
centre until its crest hovers PARKED_AIR off the parked flank, a display and
fit stand-in for the assembly, not the load model.

Part-local frame: +x is machine EAST (the assembly places the part with a
Ry(180)), +y is up, y 0 is the base top.  The sketch path is the INSIDE
surface of the formed strip -- the foot's top face and the blade's east face --
and the wall lies outside it: under the foot, west of the blade.  The blade's
west face is the contact face.
"""

from __future__ import annotations

import math

import numpy as np

import pinion_spring_load as load_model
from _hole_spec import THREAD_MAJOR_MM, HoleSpec, blind_cut_dia_mm
from foot_screw_spec import HEAD_DIA as FOOT_SCREW_HEAD_DIA, THREAD as FOOT_SCREW_THREAD
from pinion_bracket_geometry import C2C as STRAP_C2C
from pinion_rig_park_geometry import STRAP_LEAN_DEG
from pinion_rig_layout import SPRING_SET_FEEL_ERROR, SPRING_SET_PUSH
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
KINK_DEG = 55.0  # the crest arc: the flick turns this far back east past the blade
MIN_CREST_ARC_MARGIN_DEG = 3.0  # assembly gate reserves each crest-arc end, loaded
FLAT_LEN = 2.0
FOOT_Y = THICK  # the foot's top face (the path); its underside is the base top

# The installed solid hovers its crest this far off the parked flank so the
# assembly's interference gate sees a clean part; the loaded crest actually
# bears on the flank (pinion_spring_load).  The contact must stay on the
# straight flank, at least this much beyond the 1.0 mm arbor end-cap keep-out.
PARKED_AIR = 0.15
MIN_ARBOR_END_CAP_SPARE_MM = 0.25

# Screw-down pad: #4 clearance, webs >= 2.0 at the printed .XX worst case
# (test_pinion_spring_drawing), which takes the 9.5 square.  The foot screw
# stands 21.3 east of the pivot axis, 13.8 east of the flank.  The bend starts
# at the pad's edge (FOOT_FLAT=0).
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

# 17-7 PH Condition C (#859 ruling 4).
# E: 200 GPa (29.0e3 ksi), the aged-condition modulus -- Cleveland-Cliffs 17-7
# PH bulletin (07/2024) Table 7 lists it for TH 1050 / RH 950 and the Armco
# 17-7 PH bulletin (10/2022) gives 200 GPa static for CH 900; neither lists
# Condition C, so the aged value stands in.
MODULUS_MPA = 200_000.0
# The hand-formed profile's band (Main's r6 ruling (c)); the print states it
# as pinion_spring_spec.FORMED_TOLERANCE_MM.  Every formed dimension walks
# both ends of it independently in the drive train's load gate.
FORMED_BAND_MM = 0.5
# Design yield: ASTM A693-02 Table 5, Type 631 (S17700) "cold rolled at mill"
# (Condition C), 0.0015-0.050 in: 0.2 % yield 175 ksi (1205 MPa) MINIMUM,
# tensile 200 ksi min.  The standard guarantees the yield itself, so no
# scaling from tensile applies (ruling 1's rule was for tensile-only minima).
# The optional CH 900 age (482 C, 1 h) raises it and is NOT counted.
YIELD_MPA = 1205.0

# The FREE (as-formed) profile the print holds, from the foot's free end
# (policy rule 7): the kink (crest) start FREE_KINK_H west and FREE_KINK_V up,
# the flick tip FREE_TIP_H west.  Chosen (PR #1127 bend-only search, full
# printed envelope) so that with SPRING SET the loaded leaf keeps preload
FREE_KINK_H = 19.12
FREE_KINK_V = 28.0
FREE_TIP_H = 17.09
FORMED_CONTACT_BANDS = ("FootLen", "BendR", "FreeKinkH", "FreeKinkV", "KinkR")

# SPRING SET (pinion_rig_fitup.RIG_SET_STEP, pinion_rig_layout): straps
# parked on their cams, slide MHA-114 west until its crest just touches the
# parked back flank (no leaf: the crest itself is the touch), gage the pad's
# east end to the north arbor pedestal's west flank, push the pad
# SET_PUSH_MM further west (that gage plus SET_PUSH_MM), tighten on the
# gage, then spot the base seat.  The pedestal is only the relative
# reference between the two readings.
SET_TOUCH_LEAF_MM = 0.0
SET_PUSH_MM = SPRING_SET_PUSH
# Set error booked in the load gate, each way: the touch and the gage stack
# (feeler class) plus the #4 screw's float in the pad's clearance hole for a
# leaf refitted on the spotted seat without re-setting.
SET_FEEL_ERROR_MM = SPRING_SET_FEEL_ERROR
SET_SCREW_FLOAT_MM = (blind_cut_dia_mm(HOLE_SPEC) - THREAD_MAJOR_MM[FOOT_SCREW_THREAD]) / 2.0
SET_ERROR_MM = SET_FEEL_ERROR_MM + SET_SCREW_FLOAT_MM

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
_BEND_C = (BEND_CX, BEND_CY)

# The free blade: the one straight tangent to both the bend (inside radius,
# its centre east of the path) and the crest whose start is the free kink
# point.  B = (-sin a, cos a) leans a WEST of vertical; W is its west normal.
FREE_KINK_START = (FOOT_END[0] - FREE_KINK_H, FOOT_END[1] + FREE_KINK_V)
_DX, _DY = BEND_CX - FREE_KINK_START[0], BEND_CY - FREE_KINK_START[1]
_FREE_A = math.atan2(_DY, _DX) + math.acos(R_BEND / math.hypot(_DX, _DY))
FREE_BLADE_LEAN_DEG = math.degrees(_FREE_A)  # west of vertical, as formed
_FB = (-math.sin(_FREE_A), math.cos(_FREE_A))
_FW = (-math.cos(_FREE_A), -math.sin(_FREE_A))
FREE_BEND_EXIT = _add(_BEND_C, _FW, R_BEND)
FREE_KINK_C = _add(FREE_KINK_START, _FW, -R_KINK)
FREE_KINK_EXIT = _add(FREE_KINK_C, _cw(_FW, KINK_DEG), R_KINK)
FREE_FLAT_TIP = _add(FREE_KINK_EXIT, _cw(_FB, KINK_DEG), FLAT_LEN)
if abs(FOOT_END[0] - FREE_FLAT_TIP[0] - FREE_TIP_H) > 0.02:
    raise AssertionError(
        f"FREE_TIP_H {FREE_TIP_H} does not close the {KINK_DEG} deg crest: "
        f"the flat tip lands {FOOT_END[0] - FREE_FLAT_TIP[0]:.3f} west of the free end"
    )
FREE_CREST = _add(FREE_KINK_C, STRAP_N, -(R_KINK + THICK))  # outer face, toward the flank


def _flank_air(crest_outer: tuple[float, float]) -> float:
    """How far a crest outer-face point stands OFF the parked flank (negative
    into it), along the flank normal."""
    rel = (crest_outer[0] - _PIVOT[0], crest_outer[1] - _PIVOT[1])
    return rel[0] * STRAP_N[0] + rel[1] * STRAP_N[1] - STRAP_HALF_WIDTH


# How far the free crest stands into the parked flank at the nominal seat.
PRESET = -_flank_air(FREE_CREST)
if PRESET <= FORMED_BAND_MM:
    raise AssertionError("the free crest does not stand into the parked flank")

# Installed solid: the free profile turned PRESET_DEG clockwise (away from the
# strap) about the bend centre until the crest hovers PARKED_AIR off the
# parked flank.  A stand-in for the loaded shape (the elastica's root bends,
# this rotates rigidly), close enough for the assembly's fit gates.


def _turned(p: tuple[float, float], deg: float) -> tuple[float, float]:
    return _add(_BEND_C, _cw((p[0] - BEND_CX, p[1] - BEND_CY), deg))


def _crest_air(deg: float) -> float:
    kink_c = _turned(FREE_KINK_C, deg)
    return _flank_air(_add(kink_c, STRAP_N, -(R_KINK + THICK)))


_lo, _hi = 0.0, 45.0
for _ in range(80):
    _mid = 0.5 * (_lo + _hi)
    if _crest_air(_mid) < PARKED_AIR:
        _lo = _mid
    else:
        _hi = _mid
PRESET_DEG = 0.5 * (_lo + _hi)
if abs(_crest_air(PRESET_DEG) - PARKED_AIR) > 1e-6:
    raise AssertionError("the installed crest does not hover its parked air")

BEND_EXIT = _turned(FREE_BEND_EXIT, PRESET_DEG)
KINK_START = _turned(FREE_KINK_START, PRESET_DEG)
KINK_C = _turned(FREE_KINK_C, PRESET_DEG)
KINK_EXIT = _turned(FREE_KINK_EXIT, PRESET_DEG)
FLAT_TIP = _turned(FREE_FLAT_TIP, PRESET_DEG)
CREST = _add(KINK_C, STRAP_N, -(R_KINK + THICK))  # the crest's west (outer) face
_BLADE_A = _FREE_A - math.radians(PRESET_DEG)
BLADE_LEAN_DEG = math.degrees(_BLADE_A)  # west of vertical, installed
BLADE_TO_FLANK_DEG = BLADE_LEAN_DEG + STRAP_LEAN_DEG
_B = (-math.sin(_BLADE_A), math.cos(_BLADE_A))  # up the blade
_W = (-math.cos(_BLADE_A), -math.sin(_BLADE_A))  # the blade's west normal
# The installed crest's station up the strap, for the assembly's model checks.
CONTACT_T = (CREST[0] - _PIVOT[0]) * STRAP_U[0] + (CREST[1] - _PIVOT[1]) * STRAP_U[1]

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

# The load model's view of this leaf (pinion_spring_load): the same free
# profile, the pad clamped under the screw head, the strap in this frame.
LEAF_DESIGN = load_model.LeafDesign(
    screw_east=SCREW_EAST_OF_PIVOT,
    hole_from_end=HOLE_FROM_END,
    clamp_r=FOOT_SCREW_HEAD_DIA / 2.0,
    pad_len=PAD_LEN,
    taper_len=0.01,  # the pad steps straight to the strip
    foot_len=FOOT_LEN,
    r_bend=R_BEND,
    free_kink_h=FREE_KINK_H,
    free_kink_v=FREE_KINK_V,
    r_kink=R_KINK,
    free_tip_h=FREE_TIP_H,
    flat_len=FLAT_LEN,
)
STRAP = load_model.Strap(
    pivot=_PIVOT, lean_deg=STRAP_LEAN_DEG, half_width=STRAP_HALF_WIDTH, c2c=STRAP_C2C
)
MATERIAL = load_model.Material(MODULUS_MPA, YIELD_MPA)
PAD_SET = load_model.PadSet(SET_TOUCH_LEAF_MM, SET_PUSH_MM)
TIP_CASES = tuple(
    (FREE_TIP_H + dh, FLAT_LEN + dl)
    for dh in (-FORMED_BAND_MM, 0.0, FORMED_BAND_MM)
    for dl in (-FORMED_BAND_MM, 0.0, FORMED_BAND_MM)
)


def loaded(cases: dict[str, np.ndarray]) -> load_model.Loaded:
    return load_model.load(LEAF_DESIGN, STRAP, MATERIAL, PAD_SET, cases, tip_cases=TIP_CASES)


# Nominal, parked: the set's pad shift is centred on the seat (FREE_KINK_H was
# chosen for it) and the crest bears part-way up the straight flank.
_NOMINAL = loaded(
    load_model.nominal_case(
        LEAF_DESIGN, thick=THICK, width=WIDTH, pad_width=PAD_WIDTH, swing=0.0
    )
)
NOMINAL_SET_SHIFT = float(_NOMINAL.shift[0])  # pad east of the model seat, mm
NOMINAL_CONTACT_T = float(_NOMINAL.station[0])  # up the straight flank from the pivot
NOMINAL_FORCE_N = float(_NOMINAL.force[0])
if abs(NOMINAL_SET_SHIFT) > 0.05:
    raise AssertionError(
        f"SPRING SET leaves the nominal pad {NOMINAL_SET_SHIFT:.3f} off the model seat"
    )
if abs(NOMINAL_CONTACT_T - CONTACT_T) > 1.5:
    raise AssertionError(
        f"installed model crest station {CONTACT_T:.2f} strays from the loaded "
        f"nominal {NOMINAL_CONTACT_T:.2f}"
    )

if (KINK_START[0] - BEND_EXIT[0]) * _B[0] + (KINK_START[1] - BEND_EXIT[1]) * _B[
    1
] <= 0.0:
    raise AssertionError("the blade runs backwards between bend and crest")
if min(R_BEND, R_KINK) < MIN_INSIDE_BEND_R - 1e-9:
    raise AssertionError("an inside radius is tighter than the 17-7 PH minimum")
