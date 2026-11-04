r"""Pure support-bar (MHA-PD-07) section and hanger-hole geometry.

PURE DATA, no SolidWorks/COM imports: ``build_pd_support_bar`` builds from it,
and the hanger's pivot screw (MHA-PD-VN-57) reads the pivot tap from it to judge
its engagement without importing a COM build script.

Bar frame (the build's): bar axis along X with the origin at the bar centre;
height along Y (y = 0 at mid-height); depth along Z with the FRONT face at
z = -BAR_DEPTH/2 and the BACK face at z = +BAR_DEPTH/2.  The paper-drive
assembly places it without rotation with its front face on the platen-back
plane at machine z -138.9 and its back face on the front clamp arcs at
-138.9 + BAR_DEPTH (-129.4): the 9.5 bar grew rearward, the arcs gave it up.

Ch. 23 hanger holes (contract §5), all entering the BACK face:
* the MHA-PD-VN-57 pivot screw's #8-32 THROUGH tap at the arm pivot P, machine
  (-58, 303.234), countersunk .169 max both faces: the shoulder's end ring
  still bears outside the back one, and the screw's faced tip stays below
  the front face the platen slides on, staked at the front mouth;
* the latch hook's (MHA-PD-14) two #4-40 THROUGH taps for its base screws
  (MHA-SH-VN-52) at machine x 65.0 and 72.0 on the same line, countersunk .122
  max both faces (their exits on the front face lie under the platen
  footprint, machine x -33.25..236.39).

Issue #290: the sheet prints decimal inch. The section and the hole stations
are frame and kinematic interfaces (the rails' channel, the clamp arcs, the
arm pivot P, the latch hook's base), so they keep their millimetre nominals
and print rounded at .XXX; every band below is judged at the printed limits.
"""

from __future__ import annotations

import _config
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from _column_clamp_interface import BAR_DEPTH

UNIT = drawing_unit("parts/pd-support-bar", _config.parts("pd-support-bar"))
BAR_BAND_PLACES = 3  # both bands print .XXX


def _printed_reach(value: float, places: int) -> float:
    """The farthest a printed ``places`` limit stands off the model ``value``."""
    return max(abs(d) for d in printed_deviations(value, places, unit=UNIT))


# The top edge carries the hanging platen's top rail at machine y 317.734 and
# the bottom edge stands a running clearance above the bottom rail (the
# paper-drive assembly's GUIDE_Y and BOTTOM_RAIL_CLEARANCE). The rails' screw
# rows stand ~34 apart in the front photos (ch30 p002: 33-34 by the platen
# width) and so do the rail centres in the ch22 back photo, so the rails'
# datum faces stay put. Owner ruling 2026-11-01 (B2): the .29 rails grow into
# the channel (the bottom rail's datum face sits just over the platen's rack
# backer), so the bar is 1.010 (it was 28.0): the ch30 p002 front view
# measures the exposed bar right of the platen at ~25.5 tall and the ch22
# back photo's bright band between the rails at ~25. One lock plate size
# serves both rails (the user's 2026-10-11 ruling: lip + rail + bar overlap,
# top and bottom).
BAR_HEIGHT = 25.654  # 1.010
# The bar's .XXX height band: the bottom rail's running clearance under the
# bar spends it (build_pd_paper_drive_assembly._assert_lock_retention).
# build_pd_support_bar authors it natively on Height@BarProfile.
BAR_HEIGHT_BAND = _printed_reach(BAR_HEIGHT, BAR_BAND_PLACES)
# Deep (Z), BAR_DEPTH (_column_clamp_interface, shared with the wheel
# bar): the back face on the clamp arcs, the front face carrying the platen's
# back. 9.5 (prints .374), not the 9.0 stock read, so the MHA-PD-VN-57 pivot
# screw's faced tip (0.20-0.50 below the front face) keeps rule 18's 1.5D at
# the thinnest bar (user ruling 2026-10-15; transgear_hanger_joints).
# The pivot screw's tip recess and the latch-hook-bracket-screw (MHA-SH-VN-52)
# tips spend the bar's .XXX thickness band.
# build_pd_support_bar authors it natively on Depth@Bar.
BAR_DEPTH_BAND = _printed_reach(BAR_DEPTH, BAR_BAND_PLACES)
BACK_FACE_Z = BAR_DEPTH / 2.0

# The column clamps (SH column clamps, machine y 303.734) and the hanger row
# (machine y 303.234) keep their machine heights under the fixed top edge,
# 14.0 and 14.5 below it, so in the bar's centred frame they stand below the
# centre line.
CLAMP_TAP_Y = BAR_HEIGHT / 2.0 - 14.0
HANGER_TAP_Y = BAR_HEIGHT / 2.0 - 14.5

# --- MHA-PD-VN-57 pivot tap -------------------------------------------------------
PIVOT_TAP_X = -58.0
PIVOT_TAP_THREAD = "#8-32"
PIVOT_TAP_CSK_DIA = 4.2926  # .169 MAX, both faces
PIVOT_TAP_DRILL_DIA = TAP_DRILL_MM[PIVOT_TAP_THREAD]

# --- Latch-hook base taps (MHA-PD-14's base, MHA-SH-VN-52 screws) -----------------
BRACKET_TAP_X = (65.0, 72.0)
BRACKET_TAP_SPEC = HoleSpec("tapped", "#4-40")
BRACKET_TAP_CSK_DIA = 3.0988  # .122 MAX, both faces

TAP_CSK_ANGLE_DEG = 90.0

# --- Walls at the printed bands (contract §8) -------------------------------
# The hanger row prints ±.002 at .XXX; its stations are off the .001 grid, so
# a hole may stand up to half a step (.0005) further off its model position.
HOLE_POSITION_PLACES = 3
HOLE_POSITION_TOL = 0.0508  # ±.002
HOLE_POSITION_BAND = HOLE_POSITION_TOL + 0.5 * 10.0**-HOLE_POSITION_PLACES * 25.4
_TAP_OVERSIZE_R = 0.025
WALLS: dict[str, tuple[float, float]] = {
    "pivot tap to the lower edge": (
        BAR_HEIGHT / 2.0 + HANGER_TAP_Y - THREAD_MAJOR_MM[PIVOT_TAP_THREAD] / 2.0,
        BAR_HEIGHT / 2.0
        + HANGER_TAP_Y
        - THREAD_MAJOR_MM[PIVOT_TAP_THREAD] / 2.0
        - HOLE_POSITION_BAND
        - _TAP_OVERSIZE_R,
    ),
    "latch-hook taps to the lower edge": (
        BAR_HEIGHT / 2.0 + HANGER_TAP_Y - THREAD_MAJOR_MM[BRACKET_TAP_SPEC.size] / 2.0,
        BAR_HEIGHT / 2.0
        + HANGER_TAP_Y
        - THREAD_MAJOR_MM[BRACKET_TAP_SPEC.size] / 2.0
        - HOLE_POSITION_BAND
        - _TAP_OVERSIZE_R,
    ),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET_MM:
        raise AssertionError(
            f"support-bar {_name} wall {_worst:.3f} < {WALL_TARGET_MM}"
        )
