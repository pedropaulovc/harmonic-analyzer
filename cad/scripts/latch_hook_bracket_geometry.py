r"""MHA-170 latch-hook bracket: the formed geometry, as pure data.

PURE DATA, no SolidWorks/COM imports and no ``build_*`` module in its import
closure.  A 1.5 steel sheet bent into an L (contract §4.2, ruling R9-10): the
BASE lies flat on the support bar's back face and takes the two #4-40
bracket screws (MHA-171) into the bar's through taps; the FLAP stands
rearward (+Z) at the base's +X end and carries the latch hook strip
(MHA-127) riveted to its -X (inside) face.

Part frame, axes parallel to the machine's, so the assembly places the part
by translation only (``MACHINE_ORIGIN``):

* origin = the L's outer corner at the base's low-Y edge: the flap's outer
  (+X) face, the base's underside (on the bar), the base's y = 0 edge;
* Right Plane (x = 0) = the flap's outer face, datum for the hole X
  positions: holes are drilled after bending, so they are located from the
  formed flap;
* Front Plane (z = 0) = the base's underside, seated on the bar's back face
  (machine z -129.9), datum for the rivet heights;
* Top Plane (y = 0) = the base's low-Y edge (machine y 299.2), datum for the
  hole Y positions;
* the base runs -X to x = -BASE_LENGTH; the flap rises +Z to FLAP_HEIGHT.

The sheet's thickness is owned here; the bracket screws' engagement stack
(``latch_hook_bracket_screw_spec``) reads it.
"""

from __future__ import annotations

from latch_hook_geometry import RIVET_YZ as _HOOK_RIVET_YZ
from support_bar_spec import BRACKET_TAP_X, HANGER_TAP_Y

# --- Stock sheet -------------------------------------------------------------
SHEET_T = 1.5  # low-carbon steel sheet (16 GA is 1.519)
SHEET_T_PLUS = 0.1  # stock band: the thickest sheet a buyer receives
SHEET_T_MINUS = 0.1  # stock band: the thinnest

# --- Placement ---------------------------------------------------------------
# The support bar sits unrotated at machine (0, BAR_CENTRE_Y, -134.4) with its
# back face at z -129.9 (support_bar_spec's frame), so a bar-frame X is a
# machine X and a bar-frame Y is BAR_CENTRE_Y above.
BAR_CENTRE_Y = 306.734
BAR_BACK_FACE_Z = -129.9
# Base from machine x 43.0 (contract default e) to the flap's outer face at
# x 60.0; base y 299.2..307.2 inside the bar's lock-free band 298.7..307.7.
MACHINE_ORIGIN = (60.0, 299.2, BAR_BACK_FACE_Z)

# --- Formed outline (part frame) ---------------------------------------------
BASE_LENGTH = 17.0  # x -17.0..0: machine 43.0..60.0
WIDTH = 8.0  # y 0..8: machine 299.2..307.2
# z 0..19.5: machine -129.9..-110.4.  0.5 over the contract's 19.0 so the
# upper rivet hole, match-drilled wherever the hook sets (R9-15), keeps a 2.0
# wall to the top edge at the .X row (latch_hook_bracket_spec.WALLS).
FLAP_HEIGHT = 19.5

# Bend (R9-10): modelled at inside R0.75 (outside R2.25, concentric); the
# sheet accepts any inside radius up to INSIDE_BEND_R_MAX.
INSIDE_BEND_R = 0.75
OUTSIDE_BEND_R = INSIDE_BEND_R + SHEET_T
INSIDE_BEND_R_MAX = 1.0

# --- Holes (part frame) ------------------------------------------------------
# Two Ø3.2 screw clearance holes over the bar's #4-40 through taps.
SCREW_HOLE_DIA = 3.2
SCREW_HOLE_X = tuple(round(x - MACHINE_ORIGIN[0], 6) for x in BRACKET_TAP_X)
SCREW_HOLE_Y = round(BAR_CENTRE_Y + HANGER_TAP_Y - MACHINE_ORIGIN[1], 6)

# Two Ø1.6 holes for the 1/16 solid rivets through the flap and the hook
# strip, on one line along Z (the hook's centreline at the rivets), lower
# first.  The hook owns the positions; the flap takes them.
RIVET_HOLE_DIA = 1.6
RIVET_YZ = tuple(
    sorted(
        (
            (round(y - MACHINE_ORIGIN[1], 6), round(z - MACHINE_ORIGIN[2], 6))
            for y, z in _HOOK_RIVET_YZ
        ),
        key=lambda yz: yz[1],
    )
)

if SCREW_HOLE_X[0] >= SCREW_HOLE_X[1]:
    raise AssertionError("bracket screw holes are not ordered -X to +X")
if not all(-BASE_LENGTH < x < -SHEET_T for x in SCREW_HOLE_X):
    raise AssertionError("a bracket screw hole left the base")
if not 0.0 < SCREW_HOLE_Y < WIDTH:
    raise AssertionError("the bracket screw holes left the base's width")
if len(RIVET_YZ) != 2 or not all(
    0.0 < y < WIDTH and SHEET_T + INSIDE_BEND_R_MAX < z < FLAP_HEIGHT
    for y, z in RIVET_YZ
):
    raise AssertionError("a hook rivet hole left the bracket's flat flap")
