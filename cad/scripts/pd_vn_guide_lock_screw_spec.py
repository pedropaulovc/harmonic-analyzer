r"""Stock guide-lock screw (McMaster 91792A108) nominals and its joint stacks.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, shank and head dims the paper-drive assembly and the
platen guide read to prove MHA-PD-VN-60 is the screw the lock stack was sized for.
Ruling R9-31: the eight platen-riding lock screws take a low #4-40 head so
the heads clear the hanger arm; every other MHA-PD-VN-52 station keeps the
brass fillister.  2026-10-11: that head is slotted, as on the book's
guide-lock plates (ch22 img05), not a hex socket: an 18-8 slotted pan head,
the lowest stocked slotted #4 rounded head.  The vendor dims are
``PAN_HEAD_SIZE`` in ``_mcmaster_91792a108.py`` (SolidWorks-free).
Consumers read them here, not from ``build_pd_vn_guide_lock_screw``, whose stock
build recipe would otherwise ride their cache keys (#880).

Ruling R9-48: the 1/4 in screw held 1.26D in the guide's blind rear tap at
the worst case.  The rear taps now run through the .40 guide and the screw
is 3/8 in long through the 1/16 sheet lock (pd_guide_lock_spec), so the
worst case holds 2.17D (``ENGAGEMENT_WORST``) and the tip stays inside the
guide (``build_pd_platen_guide`` asserts the tip against the guide's
shallowest seat).

Ruling R9-49: the lock's hole positions and the guide's Ø.008 tap
position need hole-over-screw clearance; the #4 close .120 left too
little.  The lock holes are 1/8 DRILL (.125), and at assembly each lock is
pushed away from the bar until its holes bear on the screws before they are
tightened (``pd_paper_drive_assembly_steps`` "guide-locks-set").  Pushed so, a
lock stands between ``LOCK_SET_OFFSET`` beyond its model position at each
hole, away from the bar.

Ruling R9-61: the two holes need not bear alike, so a set plate can skew
(``LOCK_SET_SKEW``); the step pushes it at its middle, and the lock-station
sweep reads the skewed plate's edges (``LOCK_SET_EDGE_REACH``).
"""

from __future__ import annotations

import math

import pd_guide_lock_spec as lock
import pd_platen_guide_spec as guide
from _hole_spec import blind_cut_dia_mm
from _printed_tolerance import (
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    edge_break_radius_mm,
    printed_deviations,
)
from _mcmaster_91792a108 import IN, PAN_HEAD_SIZE, PART_NO

SKU = PART_NO
THREAD = "#4-40"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH = PAN_HEAD_SIZE
# (plus, minus): the commercial length band, +0/-0.03 in to 1 in long (the
# policy's ASME B18.6.3 row, the standard the screw is made to).
SHANK_LEN_BAND = (0.0, 0.03 * IN)
# The incomplete first thread at the tip and at the tap mouth costs full
# engagement: one pitch, as the contract's §7 counts it.
FIRST_THREAD_LOSS = PITCH
ENGAGEMENT_FLOOR_D = 1.5
# The guide's rear tap mouth carries the title block's edge break (the
# lock seat may be faced at fit-up and re-broken to the same row).
TAP_MOUTH_BREAK = max(
    edge_break_radius_mm(unit=guide.UNIT), edge_break_chamfer_mm(unit=guide.UNIT)
)

# --- R9-48: engagement in the guide's rear through tap -----------------------
# The lock is 1/16 sheet as supplied: its thickness carries the sheet's own
# band (pd_guide_lock_spec.LOCK_THICK_BAND), the supplier's.
LOCK_THICK_MAX = lock.LOCK_THICK + lock.LOCK_THICK_BAND
LOCK_THICK_MIN = lock.LOCK_THICK - lock.LOCK_THICK_BAND
ENGAGEMENT_NOMINAL = SHANK_LEN - lock.LOCK_THICK
# The shortest screw under the thickest sheet, less the first thread and the
# tap mouth's break.
ENGAGEMENT_WORST = (
    SHANK_LEN - SHANK_LEN_BAND[1] - LOCK_THICK_MAX - FIRST_THREAD_LOSS - TAP_MOUTH_BREAK
)
# The longest screw under the thinnest sheet: how far the tip reaches into the
# guide from its rear (lock-seat) face.
TIP_REACH_MAX = SHANK_LEN + SHANK_LEN_BAND[0] - LOCK_THICK_MIN
if ENGAGEMENT_WORST < ENGAGEMENT_FLOOR_D * SHANK_DIA:
    raise AssertionError(
        "MHA-PD-VN-60 guide-lock screw in the MHA-PD-11 platen guide's rear tap: "
        f"worst-case engagement {ENGAGEMENT_WORST:.3f} "
        f"({ENGAGEMENT_WORST / SHANK_DIA:.2f}D) under {ENGAGEMENT_FLOOR_D}D"
    )

# --- R9-49: the lock's bias-set window on the screws ---------------------------
# Major-diameter limits, ASME B1.1 #4-40 UNC: the recipe models the basic
# major, above the screw's class-2A max (0.1112 in), so it bounds the
# tightest fit; the class-2A min (0.1061 in) bounds the loosest.
SCREW_MAJOR_MAX = SHANK_DIA
SCREW_MAJOR_MIN = 0.1061 * IN
LOCK_HOLE_DIA_MIN = blind_cut_dia_mm(lock.HOLE_SPEC)
LOCK_HOLE_DIA_MAX = LOCK_HOLE_DIA_MIN + drilled_oversize_mm(unit=lock.UNIT)
# Radial position error of one screw axis relative to its lock hole: the
# radial reach of the lock's ± coordinate band plus half the guide's printed
# position diameter.
POSITION_RADIAL = (
    math.hypot(lock.HOLE_LOCATION_BAND, lock.HOLE_LOCATION_BAND)
    + float(guide.GEOMETRIC_TOLERANCES_MM["guide hole-pattern position"]) / 2.0
)
CLEARANCE_RADIAL_MIN = (LOCK_HOLE_DIA_MIN - SCREW_MAJOR_MAX) / 2.0
CLEARANCE_RADIAL_MAX = (LOCK_HOLE_DIA_MAX - SCREW_MAJOR_MIN) / 2.0
# (min, max) as set, away from the bar from the model position. Pushed until
# a hole bears on its screw, the lock gains at least the radial clearance less
# the position error at any pitch error in x (the least gain is the screw
# offset straight toward the bar), and at most the largest clearance plus it.
LOCK_SET_OFFSET = (
    CLEARANCE_RADIAL_MIN - POSITION_RADIAL,
    CLEARANCE_RADIAL_MAX + POSITION_RADIAL,
)
if LOCK_SET_OFFSET[0] < 0.0:
    raise AssertionError(
        "MHA-PD-12 guide lock on MHA-PD-VN-60 screws in the MHA-PD-11 guide taps: "
        f"radial clearance {CLEARANCE_RADIAL_MIN:.4f} under the position error "
        f"{POSITION_RADIAL:.3f} (hole-over-screw "
        f"{LOCK_HOLE_DIA_MIN - SCREW_MAJOR_MAX:.3f} < {2.0 * POSITION_RADIAL:.2f})"
    )

# --- The set plate's skew -----------------------------------------------------
# The window holds at each hole on its own, so a set plate need not translate:
# one hole can bear at the least gain (the smallest drill on the fattest
# screw, its position errors toward the bar) while the other bears at the
# most (the largest drill on the thinnest screw, its errors away from it).
# The rigid plate then turns through the gain difference over the shortest
# hole pitch the coordinates print, and its corner outboard of the
# less-gained hole swings toward the bar by that skew times the longest
# overhang the outline and coordinate bands allow. This bounds the plate
# pushed at its middle, as the "guide-locks-set" step does: there the
# frictionless contact (both holes bearing, any x pitch error) stays inside
# it (test_pd_guide_lock_fit_drawing).
_HOLE_X = sorted(x for x, _ in lock.HOLE_XY)
_HOLE_PITCH_MIN = _HOLE_X[-1] - _HOLE_X[0] - 2.0 * lock.HOLE_LOCATION_BAND
_WIDTH_DEV = printed_deviations(
    lock.LOCK_WIDTH, lock.DRAWING_PRECISION["LockProfile"]["Width"], unit=lock.UNIT
)
CORNER_OVERHANG_MAX = (
    max(_HOLE_X[0], lock.LOCK_WIDTH + _WIDTH_DEV[1] - _HOLE_X[-1])
    + lock.HOLE_LOCATION_BAND
)
# The sine of the largest skew.
LOCK_SET_SKEW = (LOCK_SET_OFFSET[1] - LOCK_SET_OFFSET[0]) / _HOLE_PITCH_MIN
# (far, guide side): the most a set plate's long edges stand beyond their
# model positions anywhere along them, the far (spacer-side) edge toward the
# bar and the guide-side edge away from it. The skew's cosine only draws both
# edges in, so it is left out.
LOCK_SET_EDGE_REACH = (
    CORNER_OVERHANG_MAX * LOCK_SET_SKEW - LOCK_SET_OFFSET[0],
    LOCK_SET_OFFSET[1] + CORNER_OVERHANG_MAX * LOCK_SET_SKEW,
)
