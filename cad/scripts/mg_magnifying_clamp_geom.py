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

import _config
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from sh_vn_thumb_screw_spec import COLLAR_DIA, SHANK_LEN, TIP_CHAMFER, TIP_FLAT_R
from _printed_tolerance import (
    angular_band_deg,
    drilled_oversize_mm,
    edge_break_chamfer_mm,
    printed_band_mm,
    printed_deviations,
)
from mg_lever_thread_joint import ROD_DIA, ROD_DIA_BAND
from mg_rod_clamp_joint import (
    ENGAGEMENT_MIN,
    ROD_TAP_DRILL_DEPTH_MAX,
    ROD_TAP_SPEC,
    THREAD,
    THREAD_MAJOR,
)

MM_PER_IN = 25.4
# #290: the sheet prints decimal inch; every band below is its inch row.
UNIT = drawing_unit("parts/mg-magnifying-clamp", _config.parts("mg-magnifying-clamp"))

# --- stock: as-bought 1/2 in HEX, all three opposed-flat pairs --------------
HEX_AF = 0.5 * MM_PER_IN  # 1/2 across flats, a stock REF on the sheet
HEX_AF_FRACTION_DENOMINATOR = 2
HEX_AC = HEX_AF / math.cos(math.radians(30.0))  # nominal .577 across corners
BLOCK_HEIGHT = 29.464  # 1.16
HEIGHT_PLACES = 2
_HEIGHT_BAND = printed_band_mm(HEIGHT_PLACES, unit=UNIT)
# An assumption, not a printed band: the flats as supplied stay within
# +/-.005 in of 1/2 in (the rod and fixture stock assume the same).
HEX_STOCK_AF_BAND = 0.127
_ANGULAR_BAND_DEG = angular_band_deg(unit=UNIT)
_HEX_ANGLE = math.radians(_ANGULAR_BAND_DEG)
_DRILL_OVERSIZE = drilled_oversize_mm(unit=UNIT)
# The supplied hex over the full length: bound adjacent normals, opposite-face
# angular error and full-height drift without assuming exact 60-degree faces
# or centring: D cos(30+a) <= AFmax + 2 Hmax tan(a) + D sin(a).
# Round OUT to the .01 in grid; this is a calculation bound, not a printed
# limit or an additional receiving inspection requirement.
_ENVELOPE_STEP = MM_PER_IN / 100.0
STOCK_ENVELOPE_MAX = math.ceil(
    (HEX_AF + HEX_STOCK_AF_BAND + 2.0 * (BLOCK_HEIGHT + _HEIGHT_BAND) * math.tan(_HEX_ANGLE))
    / (math.cos(math.radians(30.0) + _HEX_ANGLE) - math.sin(_HEX_ANGLE))
    / _ENVELOPE_STEP
) * _ENVELOPE_STEP
# The block's extent ALONG THE LEVER: the bore runs corner to corner, so this
# is the across-corners width. error_budget.clamp_radius_band and the web
# mechanics export read it under this name.
BLOCK_DEPTH = HEX_AC

# --- lever bore: ordinary drilled slip clearance on selected 1/4-inch stock --
LEVER_BORE_DIA = 6.5278  # .257, letter F drill
_LEVER_BORE_R_MAX = (LEVER_BORE_DIA + _DRILL_OVERSIZE) / 2.0
# Ordinary finished-entrance locations include the drill's starting error.
# Spend angular run-off additionally from the actual entrance to the target.
LOCATION_PLACES = 2
LOCATION_BAND = printed_band_mm(LOCATION_PLACES, unit=UNIT)
LOCATION_FROM_FLAT = HEX_AF / 2.0  # .25
DRILL_WANDER_DEG = 0.3
_DRILL_SLOPE = math.tan(math.radians(DRILL_WANDER_DEG))
BORE_FULL_ANGULAR = STOCK_ENVELOPE_MAX * _DRILL_SLOPE
# Bore and both tap entry axes use ONE actual Z-flat baseline at .XX.
# Two independent ordinary ±.010 locations bound their relative offset by
# .020; diameter variation does not enter a center-to-center location.
# At maximum bore radius a small opposite-offset corner is admitted;
# all functional bounds below use the conservative absolute offset.
TAP_TO_BORE_ENTRY_Z_MAX = 2.0 * LOCATION_BAND


# --- heights from the bottom face (two-place prints, the .XX band) -----------
# Rule 17 at the inch sheet's .080 target and .060 floor.
WALL_TARGET = WALL_TARGET_MM
WALL_FLOOR = WALL_FLOOR_MM
# The opposite flat, maximum independent location, bore size and relative
# flat/drill angle give the limiting nonintersecting wall.
BORE_TO_FLAT_WALL_WORST = (
    HEX_AF - HEX_STOCK_AF_BAND - (LOCATION_FROM_FLAT + LOCATION_BAND)
    - _LEVER_BORE_R_MAX
    - STOCK_ENVELOPE_MAX * math.tan(math.radians(_ANGULAR_BAND_DEG + DRILL_WANDER_DEG))
)
ROD_TAP_DRILL_DIA = blind_cut_dia_mm(ROD_TAP_SPEC)
ROD_TAP_DRILL_POINT = (
    (ROD_TAP_DRILL_DIA + _DRILL_OVERSIZE) / 2.0 / math.tan(math.radians(59.0))
)
# This approved interface is not re-solved when a stock/wander proof changes:
# doing so would silently move the bottom seat, rod engagement and hook. It
# keeps its millimetre nominal and prints rounded at .XX (.79), so every stack
# reads its PRINTED limits.
LEVER_BORE_Y = 19.95
BORE_Y_DEVIATIONS = printed_deviations(LEVER_BORE_Y, HEIGHT_PLACES, unit=UNIT)
_BORE_Y_MIN = LEVER_BORE_Y + BORE_Y_DEVIATIONS[0]
_BORE_Y_MAX = LEVER_BORE_Y + BORE_Y_DEVIATIONS[1]
ROD_TAP_FLOOR_WALL_WORST = (
    _BORE_Y_MIN
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
TOP_TO_BORE = BLOCK_HEIGHT - LEVER_BORE_Y
TOP_TO_BORE_MAX = BLOCK_HEIGHT + _HEIGHT_BAND - _BORE_Y_MIN
TOP_TO_BORE_MIN = BLOCK_HEIGHT - _HEIGHT_BAND - _BORE_Y_MAX
EDGE_BREAK = edge_break_chamfer_mm(unit=UNIT)  # title block edge break at the tap mouth
# A tap cuts up to .002 over the basic major: half of it on a wall. A
# normal-shop allowance, not an ASME maximum or an inspection requirement.
TAP_OVERSIZE_R = 0.0254
# Conservatively add the general angular band to drill angular run-off.
# This is a contact allowance, not a new/tighter manufactured angle tolerance.
THUMB_CONTACT_ANGLE_MAX = math.radians(_ANGULAR_BAND_DEG + DRILL_WANDER_DEG)
_SEC = 1.0 / math.cos(THUMB_CONTACT_ANGLE_MAX)
_TAN = math.tan(THUMB_CONTACT_ANGLE_MAX)
# Finite screw-flat contact can miss the lever's highest transverse point
# after independent tap/bore entry errors. Spend that actual chord loss.
THUMB_CONTACT_Z_MAX = TAP_TO_BORE_ENTRY_Z_MAX + TOP_TO_BORE_MAX * _DRILL_SLOPE + BORE_FULL_ANGULAR
_ROD_R_MIN = (ROD_DIA + ROD_DIA_BAND[1]) / 2.0
_LATERAL_CONTACT = max(THUMB_CONTACT_Z_MAX + _LEVER_BORE_R_MAX * _SEC - _ROD_R_MIN - TIP_FLAT_R, 0.0)
if _LATERAL_CONTACT >= _ROD_R_MIN:
    raise AssertionError("MHA-MG-02 finite screw tip cannot reach the lever contact envelope")
THUMB_CONTACT_CHORD_LOSS = _ROD_R_MIN - math.sqrt(_ROD_R_MIN**2 - _LATERAL_CONTACT**2)
_CONTACT_MAX = _BORE_Y_MAX + BORE_FULL_ANGULAR + _LEVER_BORE_R_MAX * _SEC + TIP_FLAT_R * _TAN
_CONTACT_MIN = _BORE_Y_MIN - BORE_FULL_ANGULAR - _LEVER_BORE_R_MAX * _SEC + 2.0 * _ROD_R_MIN - THUMB_CONTACT_CHORD_LOSS - TIP_FLAT_R * _TAN
_FEMALE_START_MAX = _BORE_Y_MAX + BORE_FULL_ANGULAR + _LEVER_BORE_R_MAX * _SEC + (THREAD_MAJOR / 2.0 + TAP_OVERSIZE_R) * _TAN
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
if min(BORE_TO_FLAT_WALL_WORST, ROD_TAP_FLOOR_WALL_WORST) < WALL_TARGET - 1e-9:
    raise AssertionError(
        "MHA-MG-02 stock hex/bore bands lose the .080 in wall target"
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
