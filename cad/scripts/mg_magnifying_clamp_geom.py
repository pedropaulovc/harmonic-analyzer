r"""Magnifying-clamp nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract) and ``build_magnifier_assembly``
(which imports the block's extent along the lever and the lever-bore height
to place the clamp on the lever rod).

PURE DATA, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends -- via
``_buildgraph.module_deps_of`` -- on whatever module it imports a constant from,
so the drawing contract must NOT live here.  ``_spec`` re-exports these and adds
the drawing data.

#1559 owner ruling: the clamp is a VERTICAL length of stock 7/16 in hex brass.
The Ø6 lever (MHA-MG-03) passes through it across the corners; the knurled
thumb screw (MHA-MG-VN-50) enters the top face on the hex axis and pinches the
lever; the vertical rod (MHA-MG-04) screws into a blind tap in the bottom face
on the same axis and seats on its shoulder (``mg_rod_clamp_joint``), so the
thumb screw, the rod and the wire hook below all lie in one plane with the
lever.

Part frame: origin at the bottom-face centre, hex axis +Y, the lever bore along
X through two opposite corners at y = LEVER_BORE_Y, the two flats square to Z.
The assembly places it unrotated, so the flats face the machine front/back.
"""

from __future__ import annotations

import math

from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_drilled_tolerance import drilled_oversize_mm
from _printed_tolerance import printed_band_mm
from mg_rod_clamp_joint import (
    ENGAGEMENT_MIN,
    ROD_TAP_DRILL_DEPTH_MAX,
    ROD_TAP_SPEC,
    THREAD,
)

MM_PER_IN = 25.4

# --- stock: 7/16 in hex brass bar, flats as supplied -------------------------
HEX_AF = 7.0 / 16.0 * MM_PER_IN  # 11.1125 across flats
# Commercial hex-bar across-flats band (the MHA-MG-06 HEX_STOCK_AF_BAND).
HEX_AF_BAND = 0.13
HEX_AC = HEX_AF / math.cos(math.radians(30.0))  # 12.8316 across corners
# The block's extent ALONG THE LEVER: the bore runs corner to corner, so this
# is the across-corners width. error_budget.clamp_radius_band and the web
# mechanics export read it under this name.
BLOCK_DEPTH = HEX_AC

# --- lever bore: Ø6.2 drilled through the corners, slip on the Ø6 lever -------
LEVER_BORE_DIA = 6.2
_LEVER_BORE_R_MAX = (LEVER_BORE_DIA + drilled_oversize_mm()) / 2.0  # 3.15

# --- heights from the bottom face (two-place prints, the .XX band) -----------
HEIGHT_PLACES = 2
_HEIGHT_BAND = printed_band_mm(HEIGHT_PLACES)  # 0.51
WALL_TARGET = 2.0
# The rod tap's drill point stops WALL_TARGET under the lever bore at worst:
# the deepest printed drill depth plus its 118 deg point, the largest drilled
# bore, and the bore's height at its low print. Rounded up to 0.05.
ROD_TAP_DRILL_DIA = blind_cut_dia_mm(ROD_TAP_SPEC)
ROD_TAP_DRILL_POINT = (
    (ROD_TAP_DRILL_DIA + drilled_oversize_mm()) / 2.0 / math.tan(math.radians(59.0))
)
_LEVER_BORE_Y_NEED = (
    WALL_TARGET
    + _LEVER_BORE_R_MAX
    + ROD_TAP_DRILL_DEPTH_MAX
    + ROD_TAP_DRILL_POINT
    + _HEIGHT_BAND
)
LEVER_BORE_Y = round(math.ceil(_LEVER_BORE_Y_NEED / 0.05 - 1e-9) * 0.05, 2)  # 19.65
ROD_TAP_FLOOR_WALL_WORST = (
    (LEVER_BORE_Y - _HEIGHT_BAND)
    - _LEVER_BORE_R_MAX
    - ROD_TAP_DRILL_DEPTH_MAX
    - ROD_TAP_DRILL_POINT
)

# --- thumb-screw tap: #4-40 from the top face, on the hex axis, into the bore
# Top face to the lever-bore axis. The thumb screw's full thread runs from the
# top face's edge break down to where the tap breaks into the bore; at the
# printed worst case (both heights at their .XX limits, the largest bore) that
# is still 1.5D (drawing-guidelines.md rule 18 (thread engagement)).
TOP_TO_BORE = 9.0
BLOCK_HEIGHT = round(LEVER_BORE_Y + TOP_TO_BORE, 2)  # 28.65
EDGE_BREAK = 0.25  # title block edge break at the tap mouth
THUMB_ENGAGEMENT_WORST = (
    TOP_TO_BORE - 2.0 * _HEIGHT_BAND - _LEVER_BORE_R_MAX - EDGE_BREAK
)
# The fixture's precedent: the drill runs on to the bore axis (its point stops
# in the bore, short of the far wall), the thread ends at the bore -- its
# depth a REF on the sheet.
THUMB_TAP_DRILL_DEPTH = TOP_TO_BORE
THUMB_TAP_LENGTH = TOP_TO_BORE - LEVER_BORE_DIA / 2.0  # 5.9
THUMB_TAP_SPEC = HoleSpec(
    "tapped",
    THREAD,
    end="blind",
    depth_mm=THUMB_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": THUMB_TAP_LENGTH},
)

# --- import-time geometry guards ---------------------------------------------
if ROD_TAP_FLOOR_WALL_WORST < WALL_TARGET - 1e-9:
    raise AssertionError(
        f"MHA-MG-02 rod-tap floor under the lever bore {ROD_TAP_FLOOR_WALL_WORST:.3f} "
        f"at worst, under {WALL_TARGET}"
    )
if THUMB_ENGAGEMENT_WORST < ENGAGEMENT_MIN - 1e-9:
    raise AssertionError(
        f"MHA-MG-02 thumb-screw thread {THUMB_ENGAGEMENT_WORST:.3f} at worst, "
        f"under 1.5D = {ENGAGEMENT_MIN:.3f}"
    )
if not LEVER_BORE_DIA / 2.0 < HEX_AF / 2.0:
    raise AssertionError("MHA-MG-02 lever bore breaks through a flat")
if not 0.0 < THUMB_TAP_LENGTH < THUMB_TAP_DRILL_DEPTH:
    raise AssertionError("MHA-MG-02 thumb tap drill stops short of its thread")
