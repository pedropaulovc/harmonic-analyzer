r"""Stock guide-lock screw (McMaster 91255A108) nominals and its joint stacks.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread, shank and head dims the paper-drive assembly and the
platen guide read to prove MHA-176 is the screw the lock stack was sized for.
Ruling R9-31: the eight platen-riding lock screws take a #4-40 button head
so the heads clear the hanger arm; every other MHA-030 station keeps the
brass fillister.  The vendor dims are ``DIMS`` in
``diagnostics/diag_build_91255A108.py`` (SolidWorks-free at import).
Consumers read them here, not from ``build_guide_lock_screw``, whose stock
build recipe would otherwise ride their cache keys (#880).

Ruling R9-48: the 1/4 in screw held 1.26D in the guide's blind rear tap at
the worst case.  The rear taps now run through the 10.00 guide and the screw
is the 3/8 in length of the same series, so the worst case holds 2.02D
(``ENGAGEMENT_WORST``) and the tip stays inside the guide
(``build_platen_guide`` asserts the tip against the guide's shallowest seat).

Ruling R9-49: the lock's Ø0.10 hole position and the guide's Ø0.20 tap
position need 0.30 of hole-over-screw clearance; the #4 close Ø3.048 left
0.20.  The lock holes are 1/8 DRILL (Ø3.175), and at assembly each lock is
pushed away from the bar until its holes bear on the screws before they are
tightened (``paper_drive_assembly_steps`` "guide-locks-set").  Pushed so, a
lock stands between ``LOCK_SET_OFFSET`` beyond its model position, away from
the bar; the lock-station sweep reads that window.
"""

from __future__ import annotations

import _config
import guide_lock_spec as lock
import platen_guide_spec as guide
from _hole_spec import blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_deviations
from diagnostics.diag_build_91255A108 import DIMS, IN

# [INFERENCE] The 3/8 in length of the 91255A series (91255A106 = 1/4 in, read
# live 2026-09-30), not yet read live; the vendor check is pending.
SKU = DIMS.part_no
THREAD = "#4-40"
SHANK_DIA = DIMS.major_dia
SHANK_LEN = DIMS.length
# (plus, minus): the commercial length band, +0/-0.03 in to 1 in long (the
# policy's ASME B18.6.3 row; B18.3 socket screws [INFERENCE] are no looser).
SHANK_LEN_BAND = (0.0, 0.03 * IN)
HEAD_DIA = DIMS.head_dia
HEAD_H = DIMS.head_h
PITCH = DIMS.pitch
# The incomplete first thread at the tip and at the tap mouth costs full
# engagement: one pitch, as the contract's §7 counts it.
FIRST_THREAD_LOSS = PITCH
ENGAGEMENT_FLOOR_D = 1.5
# The guide's rear tap mouth carries the title block's edge break (the
# lock seat may be faced at fit-up and re-broken to the same row).
TAP_MOUTH_BREAK = max(
    float(_config.title_block("edge_break")[key])
    for key in ("radius_mm", "chamfer_max_mm")
)

# --- R9-48: engagement in the guide's rear through tap -----------------------
# The lock's strip thickness prints at its own places (guide_lock_spec).
_LOCK_THICK_DEV = printed_deviations(
    lock.LOCK_THICK, lock.DRAWING_PRECISION["Lock"]["Depth"]
)
LOCK_THICK_MAX = lock.LOCK_THICK + _LOCK_THICK_DEV[1]
LOCK_THICK_MIN = lock.LOCK_THICK + _LOCK_THICK_DEV[0]
ENGAGEMENT_NOMINAL = SHANK_LEN - lock.LOCK_THICK
# The shortest screw under the thickest strip, less the first thread and the
# tap mouth's break.
ENGAGEMENT_WORST = (
    SHANK_LEN - SHANK_LEN_BAND[1] - LOCK_THICK_MAX - FIRST_THREAD_LOSS - TAP_MOUTH_BREAK
)
# The longest screw under the thinnest strip: how far the tip reaches into the
# guide from its rear (lock-seat) face.
TIP_REACH_MAX = SHANK_LEN + SHANK_LEN_BAND[0] - LOCK_THICK_MIN
if ENGAGEMENT_WORST < ENGAGEMENT_FLOOR_D * SHANK_DIA:
    raise AssertionError(
        "MHA-176 guide-lock screw in the MHA-111 platen guide's rear tap: "
        f"worst-case engagement {ENGAGEMENT_WORST:.3f} "
        f"({ENGAGEMENT_WORST / SHANK_DIA:.2f}D) under {ENGAGEMENT_FLOOR_D}D"
    )

# --- R9-49: the lock's bias-set window on the screws ---------------------------
# Major-diameter limits, ASME B1.1 #4-40 UNC: the class-3A max is the basic
# major the recipe models; the class-2A min (0.1061 in) is below the 3A min,
# so it bounds the loosest fit of either class.
SCREW_MAJOR_MAX = DIMS.major_dia
SCREW_MAJOR_MIN = 0.1061 * IN
LOCK_HOLE_DIA_MIN = blind_cut_dia_mm(lock.HOLE_SPEC)
LOCK_HOLE_DIA_MAX = LOCK_HOLE_DIA_MIN + drilled_oversize_mm()
# Radial position error of one screw axis relative to its lock hole: half of
# each printed position diameter.
POSITION_RADIAL = (
    float(lock.GEOMETRIC_TOLERANCES_MM["screw-hole position"])
    + float(guide.GEOMETRIC_TOLERANCES_MM["guide hole-pattern position"])
) / 2.0
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
        "MHA-112 guide lock on MHA-176 screws in the MHA-111 guide taps: "
        f"radial clearance {CLEARANCE_RADIAL_MIN:.4f} under the position error "
        f"{POSITION_RADIAL:.3f} (hole-over-screw "
        f"{LOCK_HOLE_DIA_MIN - SCREW_MAJOR_MAX:.3f} < {2.0 * POSITION_RADIAL:.2f})"
    )
