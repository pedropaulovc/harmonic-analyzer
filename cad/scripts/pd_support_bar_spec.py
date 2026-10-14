r"""Pure support-bar (MHA-PD-007) section and hanger-hole geometry.

PURE DATA, no SolidWorks/COM imports: ``build_pd_support_bar`` builds from it,
and the hanger's pivot screw (MHA-VN-041) reads the pivot tap from it to judge
its engagement without importing a COM build script.

Bar frame (the build's): bar axis along X with the origin at the bar centre;
height along Y (y = 0 at mid-height); depth along Z with the FRONT face at
z = -BAR_DEPTH/2 and the BACK face at z = +BAR_DEPTH/2.  The paper-drive
assembly places it without rotation on the bar centre line, its back face on
the front clamp arcs (machine z -129.9).

Ch. 23 hanger holes (contract §5), all entering the BACK face:

* the MHA-VN-041 pivot screw's #8-32 blind tap at the arm pivot P, machine
  x -2-5/16, 1/32 below the bar centre: a flat-bottomed tap drill (drill + end
  mill; no drill-point cone) 1/4 +0/-0.4 deep, full thread 3/16 minimum
  (bottoming tap), entry countersink Ø5/32 max so the shoulder's end ring
  still bears;
* the latch hook's (MHA-PD-014) two #4-40 THROUGH taps for its base screws
  (MHA-VN-043) at machine x 2-9/16 and 2-13/16 on the same line, countersunk
  Ø1/8 max both faces (their exits on the front face lie under the platen
  footprint).
"""

from __future__ import annotations

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _inch import inch

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
#
# All-inch experiment: 1-1/8 x 3/8 flat bar (was 28 x 9). The rails' screw
# rows now stand 1-11/32 apart (pd_platen_spec.GUIDE_HOLE_Y): 1-1/8 bar +
# 3/16 rail + a 1/32 running clearance over the bottom rail.
BAR_HEIGHT = inch(1 + 1 / 8)
# The bar's .XXX height band: the bottom rail's running clearance under the
# bar spends it (build_pd_paper_drive_assembly._assert_lock_retention).
# build_pd_support_bar authors it natively on Height@BarProfile.
BAR_HEIGHT_BAND = 0.13
# 3/8 deep (Z) -- front face rubs the platen back (low). 11/32 would leave
# the latch-hook bracket screws' tips proud of the front face
# (vn_latch_hook_bracket_screw_spec.tip_short_worst).
BAR_DEPTH = inch(3, 8)
# The pivot floor and the latch-hook-bracket-screw (MHA-VN-043) tips need the bar's
# thickness at 3/8 ±0.13 (.XXX).
# build_pd_support_bar authors it natively on Depth@Bar.
BAR_DEPTH_BAND = 0.13
BAR_BAND_PLACES = 3  # both bands print .XXX
BACK_FACE_Z = BAR_DEPTH / 2.0

# 1/32 below the bar centre (was 0.5 below; the 1/16 grid would snap the
# offset to 0, a >25% move of a sub-1/4 feature): 17/32 above the bottom edge.
HANGER_TAP_Y = -inch(1, 32)

# --- MHA-VN-041 pivot tap -------------------------------------------------------
PIVOT_TAP_X = -inch(2 + 5 / 16)
PIVOT_TAP_THREAD = "#8-32"
PIVOT_TAP_DRILL_DEPTH = inch(1, 4)
PIVOT_TAP_DRILL_DEPTH_LIMITS = (-0.4, 0.0)
# A bottoming tap's ~1.5-pitch lead under the 1/4 drill's shallowest 0.4
# leaves 3/16 of full thread: exactly the MHA-VN-041 thread length.
PIVOT_TAP_FULL_THREAD_MIN = inch(3, 16)
# MAX. 5/32 (1/32 grid): 3/16 would swallow the shoulder's end ring
# (transgear_hanger_joints).
PIVOT_TAP_CSK_DIA = inch(5, 32)
# The Hole Wizard's blind tap always carries a 118-degree drill point, which
# the flat-bottomed drill forbids, so the build cuts the tap drill as a flat
# blind cylinder; its thread is this spec's, not a wizard feature's.
PIVOT_TAP_DRILL_DIA = TAP_DRILL_MM[PIVOT_TAP_THREAD]

# --- Latch-hook base taps (MHA-PD-014's base, MHA-VN-043 screws) -----------------
BRACKET_TAP_X = (inch(2 + 9 / 16), inch(2 + 13 / 16))
BRACKET_TAP_SPEC = HoleSpec("tapped", "#4-40")
BRACKET_TAP_CSK_DIA = inch(1, 8)  # MAX, both faces

TAP_CSK_ANGLE_DEG = 90.0

# --- Walls at the printed bands (contract §8) -------------------------------
HOLE_POSITION_BAND = 0.065
_TAP_OVERSIZE_R = 0.025
WALL_TARGET = 2.0
WALLS: dict[str, tuple[float, float]] = {
    "floor under the pivot tap": (
        BAR_DEPTH - PIVOT_TAP_DRILL_DEPTH,
        BAR_DEPTH
        - BAR_DEPTH_BAND
        - PIVOT_TAP_DRILL_DEPTH
        - PIVOT_TAP_DRILL_DEPTH_LIMITS[1],
    ),
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
if PIVOT_TAP_FULL_THREAD_MIN > PIVOT_TAP_DRILL_DEPTH + PIVOT_TAP_DRILL_DEPTH_LIMITS[0]:
    raise AssertionError("the pivot tap's full thread outruns its shallowest drill")
