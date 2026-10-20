r"""Magnifying-clamp nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract) and ``build_magnifier_assembly``
(which imports the block's extent along the lever and the lever-bore height
to place the clamp on the lever rod).

PURE DATA, no SolidWorks/COM and no drawing imports (the
``column_clamp_front_geom`` precedent): the assembly depends -- via
``_buildgraph.module_deps_of`` -- on whatever module it imports a constant from,
so the drawing contract must NOT live here.  ``_spec`` re-exports these and adds
the drawing data.

#1769: the clamp is a VERTICAL length of selected 1/2 in hex brass stock.
The quarter-inch lever (MHA-MG-03) passes through it across the corners; the knurled
thumb screw (MHA-SH-VN-55) enters the top face on the hex axis and pinches the
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
from _mcmaster_91882a221 import COLLAR_DIA, SHANK_LEN, TIP_CHAMFER, TIP_FLAT_R
from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_band_mm
from mg_lever_thread_joint import ROD_DIA, ROD_DIA_BAND
from mg_rod_clamp_joint import (
    ENGAGEMENT_MIN,
    ROD_TAP_DRILL_DEPTH_MAX,
    ROD_TAP_SPEC,
    THREAD,
    THREAD_MAJOR,
)

MM_PER_IN = 25.4

# --- stock: 1/2 in hex brass bar, flats as supplied --------------------------
HEX_AF = 0.5 * MM_PER_IN  # 12.70 across flats
# Selected-stock receiving acceptance, explicitly owned by the native stock
# property/leader; neither a REF size nor generic "Brass" supplies this band.
HEX_AF_BAND = 0.13
HEX_AC = HEX_AF / math.cos(math.radians(30.0))  # nominal 14.6647 across corners
# Explicit receiving envelope, measured over the entire finished stock length.
# This is not inferred from exact 60-degree normals or from Rule #1 for STOCK.
STOCK_WIDTH_MAX = 15.0
# The block's extent ALONG THE LEVER: the bore runs corner to corner, so this
# is the across-corners width. error_budget.clamp_radius_band and the web
# mechanics export read it under this name.
BLOCK_DEPTH = HEX_AC

# --- lever bore: ordinary drilled slip clearance on selected 1/4-inch stock --
LEVER_BORE_DIA = 6.5
_LEVER_BORE_R_MAX = (LEVER_BORE_DIA + drilled_oversize_mm()) / 2.0
# Ordinary finished-entrance locations include the 0.10 starting error.
# Spend angular run-off additionally from the actual entrance to the target.
LOCATION_PLACES = 2
LOCATION_BAND = printed_band_mm(LOCATION_PLACES)
LOCATION_FROM_FLAT = round(HEX_AF / 2.0, LOCATION_PLACES)
DRILL_WANDER_DEG = 0.3
_DRILL_SLOPE = math.tan(math.radians(DRILL_WANDER_DEG))
BORE_FULL_ANGULAR = STOCK_WIDTH_MAX * _DRILL_SLOPE
# Each tap entry is located directly from the actual bore rim, not by
# subtracting two stock-face locations at different longitudinal stations.
# The ordinary ±1.02 band is the former two independent .XX bands, not a
# precision increase. Native measurements print 3.25 ±1.02; the drilled
# bore's +0.10/0 diameter contributes another 0.05 to the true axis bound.
RELATIVE_AXIS_BAND = 2.0 * LOCATION_BAND
TAP_TO_BORE_ENTRY_Z_MAX = RELATIVE_AXIS_BAND + drilled_oversize_mm() / 2.0


# --- heights from the bottom face (two-place prints, the .XX band) -----------
HEIGHT_PLACES = 2
_HEIGHT_BAND = printed_band_mm(HEIGHT_PLACES)
WALL_TARGET = 2.0
ROD_TAP_DRILL_DIA = blind_cut_dia_mm(ROD_TAP_SPEC)
ROD_TAP_DRILL_POINT = (
    (ROD_TAP_DRILL_DIA + drilled_oversize_mm()) / 2.0 / math.tan(math.radians(59.0))
)
# This approved interface is not re-solved when a stock/wander proof changes:
# doing so would silently move the bottom seat, rod engagement and hook.
LEVER_BORE_Y = 19.95
ROD_TAP_FLOOR_WALL_WORST = (
    (LEVER_BORE_Y - _HEIGHT_BAND)
    - _LEVER_BORE_R_MAX
    - ROD_TAP_DRILL_DEPTH_MAX
    - ROD_TAP_DRILL_POINT
    - BORE_FULL_ANGULAR
)

# --- thumb-screw tap: #4-40 from the top face, on the hex axis, into the bore
# Height alone grows; the bore/bottom seat and installed hook do not move.
# FULL engagement is the intersection of the actual male and female intervals,
# not just female wall length. The stock screw's finite flat tip and 0.75P
# chamfer consume thread above its contact with the rod.
BLOCK_HEIGHT = 29.50
TOP_TO_BORE = BLOCK_HEIGHT - LEVER_BORE_Y
EDGE_BREAK = 0.25  # title block edge break at the tap mouth
# Conservatively add the general angular band to drill angular run-off.
# This is a contact allowance, not a new/tighter manufactured angle tolerance.
THUMB_CONTACT_ANGLE_MAX = math.radians(angular_band_deg() + DRILL_WANDER_DEG)
_SEC = 1.0 / math.cos(THUMB_CONTACT_ANGLE_MAX)
_TAN = math.tan(THUMB_CONTACT_ANGLE_MAX)
# Finite screw-flat contact can miss the lever's highest transverse point
# after independent tap/bore entry errors. Spend that actual chord loss.
THUMB_CONTACT_Z_MAX = TAP_TO_BORE_ENTRY_Z_MAX + (TOP_TO_BORE + _HEIGHT_BAND) * _DRILL_SLOPE + BORE_FULL_ANGULAR
_ROD_R_MIN = (ROD_DIA + ROD_DIA_BAND[1]) / 2.0
_LATERAL_CONTACT = max(THUMB_CONTACT_Z_MAX + _LEVER_BORE_R_MAX * _SEC - _ROD_R_MIN - TIP_FLAT_R, 0.0)
if _LATERAL_CONTACT >= _ROD_R_MIN:
    raise AssertionError("MHA-MG-02 finite screw tip cannot reach the lever contact envelope")
THUMB_CONTACT_CHORD_LOSS = _ROD_R_MIN - math.sqrt(_ROD_R_MIN**2 - _LATERAL_CONTACT**2)
_CONTACT_MAX = LEVER_BORE_Y + _HEIGHT_BAND + BORE_FULL_ANGULAR + _LEVER_BORE_R_MAX * _SEC + TIP_FLAT_R * _TAN
_CONTACT_MIN = LEVER_BORE_Y - _HEIGHT_BAND - BORE_FULL_ANGULAR - _LEVER_BORE_R_MAX * _SEC + 2.0 * _ROD_R_MIN - THUMB_CONTACT_CHORD_LOSS - TIP_FLAT_R * _TAN
_FEMALE_START_MAX = LEVER_BORE_Y + _HEIGHT_BAND + BORE_FULL_ANGULAR + _LEVER_BORE_R_MAX * _SEC + (THREAD_MAJOR / 2.0 + 0.025) * _TAN
_FEMALE_END_MIN = BLOCK_HEIGHT - _HEIGHT_BAND - EDGE_BREAK
_MALE_END_MIN = _CONTACT_MIN + SHANK_LEN * math.cos(THUMB_CONTACT_ANGLE_MAX)
THUMB_ENGAGEMENT_WORST = min(_FEMALE_END_MIN, _MALE_END_MIN) - max(_FEMALE_START_MAX, _CONTACT_MAX + TIP_CHAMFER)
# The stock collar is tilted too: its lowest point, not its centre, must clear.
THUMB_COLLAR_CLEARANCE_MIN = _MALE_END_MIN - (BLOCK_HEIGHT + _HEIGHT_BAND) - COLLAR_DIA / 2.0 * math.sin(THUMB_CONTACT_ANGLE_MAX)
# The fixture's precedent: the drill runs on to the bore axis (its point stops
# in the bore, short of the far wall), the thread ends at the bore -- its
# depth a REF on the sheet.
THUMB_TAP_DRILL_DEPTH = TOP_TO_BORE
THUMB_TAP_LENGTH = TOP_TO_BORE - LEVER_BORE_DIA / 2.0
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
if THUMB_COLLAR_CLEARANCE_MIN <= 0.0:
    raise AssertionError("MHA-MG-02 thumb screw collar bottoms before rod contact")
if not LEVER_BORE_DIA / 2.0 < HEX_AF / 2.0:
    raise AssertionError("MHA-MG-02 lever bore breaks through a flat")
if not 0.0 < THUMB_TAP_LENGTH < THUMB_TAP_DRILL_DEPTH:
    raise AssertionError("MHA-MG-02 thumb tap drill stops short of its thread")
