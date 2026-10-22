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
  (-58, 303.234), countersunk Ø4.3 max both faces: the shoulder's end ring
  still bears outside the back one, and the screw's faced tip stays below
  the front face the platen slides on, staked at the front mouth;
* the latch hook's (MHA-PD-14) two #4-40 THROUGH taps for its base screws
  (MHA-SH-VN-52) at machine x 65.0 and 72.0 on the same line, countersunk Ø3.1
  max both faces (their exits on the front face lie under the platen
  footprint, machine x -33.25..236.39).
"""

from __future__ import annotations

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _column_clamp_interface import BAR_DEPTH

# 28 tall (Y), the top edge carrying the hanging platen's top rail at machine
# y 317.734 and the bottom edge 1.0 above the bottom rail (the paper-drive
# assembly's GUIDE_Y and BOTTOM_RAIL_CLEARANCE). The rails' screw rows stand
# ~34 apart in the front photos (ch30 p002: 33-34 by the platen width) and so
# do the rail centres in the ch22 back photo, so the
# rails stay put; with 5-tall rails that leaves a 29 channel, which the 22 bar
# (an earlier low wear-band read) only part filled. The ch30 p002 front view
# measures the exposed bar right of the platen at ~25.5 tall, and the ch22 back
# photo's bright band between the rails at ~25 -- both well over 22. One lock
# plate size then serves both rails (the user's 2026-10-11 ruling: 1 lip +
# 5 rail + ~3 bar overlap, top and bottom).
BAR_HEIGHT = 28.0
# The bar's .XXX height band: the bottom rail's running clearance under the
# bar spends it (build_pd_paper_drive_assembly._assert_lock_retention).
# build_pd_support_bar authors it natively on Height@BarProfile.
BAR_HEIGHT_BAND = 0.13
# Deep (Z), BAR_DEPTH (_column_clamp_interface, shared with the wheel
# bar): the back face on the clamp arcs, the front face carrying the platen's
# back. 9.5, not the 9.0 stock read, so the MHA-PD-VN-57 pivot screw's faced tip
# (0.20-0.50 below the front face) keeps rule 18's 1.5D at the thinnest bar
# (user ruling 2026-10-15; transgear_hanger_joints).
# The pivot screw's tip recess and the latch-hook-bracket-screw (MHA-SH-VN-52)
# tips spend the bar's .XXX thickness band.
# build_pd_support_bar authors it natively on Depth@Bar.
BAR_DEPTH_BAND = 0.13
BAR_BAND_PLACES = 3  # both bands print .XXX
BACK_FACE_Z = BAR_DEPTH / 2.0

HANGER_TAP_Y = -0.5  # machine y 303.234 on the 303.734 bar centre

# --- MHA-PD-VN-57 pivot tap -------------------------------------------------------
PIVOT_TAP_X = -58.0
PIVOT_TAP_THREAD = "#8-32"
PIVOT_TAP_CSK_DIA = 4.3  # MAX, both faces
PIVOT_TAP_DRILL_DIA = TAP_DRILL_MM[PIVOT_TAP_THREAD]

# --- Latch-hook base taps (MHA-PD-14's base, MHA-SH-VN-52 screws) -----------------
BRACKET_TAP_X = (65.0, 72.0)
BRACKET_TAP_SPEC = HoleSpec("tapped", "#4-40")
BRACKET_TAP_CSK_DIA = 3.1  # MAX, both faces

TAP_CSK_ANGLE_DEG = 90.0

# --- Walls at the printed bands (contract §8) -------------------------------
HOLE_POSITION_BAND = 0.065
_TAP_OVERSIZE_R = 0.025
WALL_TARGET = 2.0
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
    if _worst < WALL_TARGET:
        raise AssertionError(f"support-bar {_name} wall {_worst:.3f} < {WALL_TARGET}")
