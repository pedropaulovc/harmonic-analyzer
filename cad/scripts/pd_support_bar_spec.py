r"""Pure support-bar (MHA-PD-007) section and hanger-hole geometry.

PURE DATA, no SolidWorks/COM imports: ``build_support_bar`` builds from it,
and the hanger's pivot screw (MHA-VN-041) reads the pivot tap from it to judge
its engagement without importing a COM build script.

Bar frame (the build's): bar axis along X with the origin at the bar centre;
height along Y (y = 0 at mid-height); depth along Z with the FRONT face at
z = -BAR_DEPTH/2 and the BACK face at z = +BAR_DEPTH/2.  The paper-drive
assembly places it without rotation at machine (0, 306.734, -134.4), so the
back face is machine z -129.9.

Ch. 23 hanger holes (contract §5), all entering the BACK face:

* the MHA-VN-041 pivot screw's #8-32 blind tap at the arm pivot P, machine
  (-58, 303.234): a flat-bottomed tap drill (drill + end mill; no drill-point
  cone) 6.8 +0/-0.4 deep, full thread 5.2 minimum (bottoming tap), entry
  countersink Ø4.3 max so the shoulder's end ring still bears;
* the latch-hook bracket's two #4-40 THROUGH taps at machine x 47.5 and 54.5
  on the same line, countersunk Ø3.1 max both faces (their exits on the
  front face lie under the platen footprint).
"""

from __future__ import annotations

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec

BAR_HEIGHT = 22.0  # tall (Y) -- ch22 back-side wear band (low)
BAR_DEPTH = 9.0  # deep (Z) -- front face rubs the platen back (low)
# The pivot floor and the latch-hook-bracket-screw tips need the bar's
# thickness at 9.000 ±0.13 (.XXX); at .XX the floor would be 1.69 worst.
BAR_DEPTH_BAND = 0.13
BACK_FACE_Z = BAR_DEPTH / 2.0

HANGER_TAP_Y = -3.5  # machine y 303.234 on the 306.734 bar centre

# --- MHA-VN-041 pivot tap -------------------------------------------------------
PIVOT_TAP_X = -58.0
PIVOT_TAP_THREAD = "#8-32"
PIVOT_TAP_DRILL_DEPTH = 6.8
PIVOT_TAP_DRILL_DEPTH_LIMITS = (-0.4, 0.0)
PIVOT_TAP_FULL_THREAD_MIN = 5.2
PIVOT_TAP_CSK_DIA = 4.3  # MAX
# The Hole Wizard's blind tap always carries a 118-degree drill point, which
# the flat-bottomed drill forbids, so the build cuts the tap drill as a flat
# blind cylinder; its thread is this spec's, not a wizard feature's.
PIVOT_TAP_DRILL_DIA = TAP_DRILL_MM[PIVOT_TAP_THREAD]

# --- Latch-hook bracket taps ------------------------------------------------
BRACKET_TAP_X = (47.5, 54.5)
BRACKET_TAP_SPEC = HoleSpec("tapped", "#4-40")
BRACKET_TAP_CSK_DIA = 3.1  # MAX, both faces

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
    "bracket taps to the lower edge": (
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
