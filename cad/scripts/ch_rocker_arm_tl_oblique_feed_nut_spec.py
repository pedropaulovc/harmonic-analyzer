r"""Pure-data contract for the oblique-trammel jig's feed nut (MHA-CH-06-TL-27).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). Owner
ruling 2026-11-01 (item 4): a shop-made brass nut replaces the bought Tr8x2
flange nut (MHA-CH-06-TL-VN-55, retired), so TL-32's lug needs no spigot
recess and no wall exception. The nut threads on the leadscrew
(``ch_rocker_arm_tl_vn_oblique_leadscrew_spec``, imported as ``leadscrew``)
and two #4-40 X 3/4 SHCS (MHA-CH-06-TL-VN-66, McMaster 91251A113) hold it on
the lug's -X face, through its two loose-clearance holes into the lug's
#4-40 taps, tapped THRU (ruling C1). Thread the nut on the screw first, then
tighten the screws: the clearance float aligns the nut to the screw.

Material and stock: brass 360-H02 (C36000, ASTM B16) extruded rectangle bar,
3/4 x 1-1/4 in (OnlineMetals 1500, read live 2026-11-01: in stock, 12 in
$77.45). Height and width stay as bought and print as stock references with
the supplier's band (OnlineMetals brass tolerances, read live 2026-11-01:
extruded rectangle 0.75 thick ±.0045, widths .875-1.25 ±.005); the bar is
sawn and faced to ``LENGTH`` .40 along the screw (ruling A1+C1: five Tr8
turns), printed .XX.

Frame (SolidWorks model): origin at the -X / bottom corner of the seat face
(the face on the lug, the Front plane); +X across the 1-1/4 width, +Y up the
3/4 height, +Z along the screw away from the lug (the screw heads' face at
Z = LENGTH). In the jig the nut's +X runs along TL-32's -Y (toward its lug
end), +Y along TL-32's +Z and +Z along TL-32's -X.

Holes, all THRU along Z on the bore's line (Y = BORE_Y):

- The Tr8x2 RH bore: letter C drill, Ø.242 (over the Tr8x2 D1 6.0), then
  tapped Tr8x2-7H RH (the Fedeas TR8X2 HSS tap's class), .63 from the -X
  side and .38 from the bottom face (the owner's "centre of both stock faces"
  on the .01 grid; ruling: bore stations .XX).
- Two #4 loose-clearance holes, Ø.144 (ASME B18.2.8, the #27 drill), 2X
  .340 from the bore axis, one each side (.XXX, the pair matches TL-32's
  taps and names its mate). Each hole stands on the bore, not on the other
  hole: the review of run 20261101T220223216Z found the chained .63 / .34 /
  .680 stacking three bands on the far hole.

Fit-up: the loose hole floats a #4 by ``HOLE_FLOAT`` .016, the normal-fit
Ø.129 by ``NORMAL_HOLE_FLOAT`` .008. TL-32's spec owns the stack of both
parts' printed stations (``feed_block.FIT_UP_RESIDUAL``, .014) and proves it
falls between the two.

Rule 17 (walls, .080 target) at the printed worst case (``WALLS_MM``): every
station at its band, the holes at the drilled oversize, the stock at its
supplier band, the Tr8 internal thread at its major D4 8.5 (ISO 2904).

Rule 18 belongs to the screw (``SCREW_FULL_THREAD_MIN``): the shortest
91251A113 (B18.3, -0.03 in) through the longest nut (.41) keeps 2 D of full
thread in the lug's through tap (``leadscrew.ENGAGEMENT_TARGET_D``).
"""

from __future__ import annotations

import _config
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _mcmaster_91251a113 import DIMS as SCREW_DIMS
from _mcmaster_91251a113 import FILLET_DIA_MAX as SCREW_FILLET_DIA_MAX
from _mcmaster_91251a113 import HEAD_DIA_MIN as SCREW_HEAD_DIA_MIN
from _mcmaster_91251a113 import LENGTH_TEXT as SCREW_LENGTH_TEXT
from _mcmaster_91251a113 import THREAD as SCREW_THREAD
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

INCH = 25.4
PART_NAME = "ch-rocker-arm-tl-oblique-feed-nut"
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-feed-nut",
    _config.parts("ch-rocker-arm-tl-oblique-feed-nut"),
)
NUMBER = "MHA-CH-06-TL-27"
QUANTITY = 1
DRILLED_OVERSIZE = drilled_oversize_mm(unit=UNIT)  # title-block +.004

# --- Stock: brass 360-H02 rectangle 3/4 x 1-1/4, faced to length ----------------
WIDTH = 1.25 * INCH  # 31.75, X, as bought
HEIGHT = 0.75 * INCH  # 19.05, Y, as bought
WIDTH_STOCK_BAND = 0.005 * INCH
HEIGHT_STOCK_BAND = 0.0045 * INCH
STOCK_PLACES = 2
STOCK_FRACTION_DENOMINATORS = {"NutWidth": 4, "NutHeight": 4}  # (1-1/4), (3/4)
LENGTH = 0.40 * INCH  # 10.16, Z, sawn and faced
LENGTH_PLACES = 2
LENGTH_BAND = printed_band_mm(LENGTH_PLACES, unit=UNIT)  # .01
LENGTH_MIN = LENGTH - LENGTH_BAND
LENGTH_MAX = LENGTH + LENGTH_BAND
# Five turns of the Tr8x2's lead at the nominal length (ruling A1).
if LENGTH < 5.0 * leadscrew.SCREW_LEAD:
    raise AssertionError("the feed nut is shorter than five Tr8 turns")
# The Tr8 engages the nut's whole length: .39 min, 1.24D, under rule 18's
# 1.5D (owner ruling 2026-11-01, RV-01). Rule 20: the callout says so.
TR8_ENGAGEMENT_D = LENGTH_MIN / leadscrew.SCREW_MAJOR_DIA
TR8_ENGAGEMENT_TEXT = f"ENGAGES {LENGTH_MIN / INCH:.2f} MIN ({TR8_ENGAGEMENT_D:.2f}D)".replace("0.", ".", 1)

# --- The Tr8x2 RH bore ------------------------------------------------------------
BORE_X = 0.63 * INCH  # 16.002 from the -X side
BORE_Y = 0.38 * INCH  # 9.652 from the bottom face
BORE_PLACES = 2
BORE_DRILL = 0.242 * INCH  # letter C, 6.147
BORE_DRILL_PLACES = 3
BORE_THREAD = "Tr8x2-7H RH"
TR8_D1 = leadscrew.SCREW_MAJOR_DIA - leadscrew.SCREW_LEAD  # ISO 2904 internal minor, 6.0
TR8_D4 = leadscrew.SCREW_MAJOR_DIA + 0.5  # ISO 2904 internal major (2 ac 0.5 at P 2)
if not TR8_D1 < BORE_DRILL < leadscrew.SCREW_MAJOR_DIA - 0.5 * leadscrew.SCREW_LEAD:
    raise AssertionError("the letter C drill is not a Tr8x2 tap drill")

# --- The #4 loose-clearance pair ------------------------------------------------
SCREW_SIZE = "#4"
HOLE_FIT = "loose"
HOLE_DIA = CLEARANCE_MM[(SCREW_SIZE, HOLE_FIT)]  # 3.658, .144 (#27)
HOLE_DIA_PLACES = 3
HOLE_OFFSET = 0.340 * INCH  # 8.636, each hole from the bore axis
HOLE_OFFSET_PLACES = 3
HOLE_X = (BORE_X - HOLE_OFFSET, BORE_X + HOLE_OFFSET)  # .29, .97
HOLE_Y = BORE_Y
MATE_CALLOUT = "MATCHES TL-32 LUG TAPS"

# --- The pair's float: TL-32's spec checks it against both parts' stations ---
SCREW_MAJOR = THREAD_MAJOR_MM[SCREW_THREAD]
HOLE_OFFSET_BAND = printed_band_mm(HOLE_OFFSET_PLACES, unit=UNIT)  # .005
HOLE_FLOAT = (HOLE_DIA - SCREW_MAJOR) / 2.0  # .016
NORMAL_HOLE_FLOAT = (CLEARANCE_MM[(SCREW_SIZE, "normal")] - SCREW_MAJOR) / 2.0  # .008

# --- The screws: 2 X #4-40 X 3/4 SHCS through the nut into the lug ---------------
SCREW_COUNT = len(HOLE_X)
SCREW_LENGTH = SCREW_DIMS.length  # 19.05
SCREW_HEAD_H = SCREW_DIMS.head_h
SCREW_ENGAGEMENT = SCREW_LENGTH - LENGTH  # 8.89 nominal, into the lug
# Rule 18 at the worst case: the shortest screw through the longest nut.
SCREW_FULL_THREAD_MIN = leadscrew.full_thread_min(
    SCREW_LENGTH_TEXT, LENGTH_MAX, SCREW_THREAD
)  # 6.67, 2.3 D
SCREW_TIP_REACH_MAX = SCREW_LENGTH - LENGTH_MIN  # 9.144 past the lug face
_TARGET = leadscrew.ENGAGEMENT_TARGET_D * SCREW_MAJOR
if not SCREW_FULL_THREAD_MIN >= _TARGET:
    raise AssertionError("the feed nut screws engage the lug under 2 D")
if leadscrew.full_thread_min("5/8", LENGTH_MAX, SCREW_THREAD) >= _TARGET:
    raise AssertionError("a 5/8 nut screw would do: 3/4 is no longer the shortest")
# The head bears flat on the brass: its underhead transition seats inside the
# hole, its least diameter outside the largest hole (concentric).
HEAD_BEARING_LAND_MIN = (SCREW_HEAD_DIA_MIN - (HOLE_DIA + DRILLED_OVERSIZE)) / 2.0
if not (SCREW_FILLET_DIA_MAX < HOLE_DIA and HEAD_BEARING_LAND_MIN > 0.0):
    raise AssertionError("a feed nut screw head does not seat flat on the nut")
# The nut's reach toward the near KP08: the longest nut and the screw heads.
REACH = LENGTH_MAX + SCREW_HEAD_H

# --- Rule 17: walls at the printed worst case --------------------------------
_STATION = printed_band_mm(BORE_PLACES, unit=UNIT)  # .01 on the bore stations
_HOLE_R = (HOLE_DIA + DRILLED_OVERSIZE) / 2.0
_BORE_R = TR8_D4 / 2.0
WALLS_MM: dict[str, float] = {
    "Tr8 major to the holes": HOLE_OFFSET - HOLE_OFFSET_BAND - _HOLE_R - _BORE_R,
    "hole 1 to -X side": HOLE_X[0] - _STATION - HOLE_OFFSET_BAND - _HOLE_R,
    "hole 2 to +X side": (WIDTH - WIDTH_STOCK_BAND)
    - (HOLE_X[1] + _STATION + HOLE_OFFSET_BAND)
    - _HOLE_R,
    "holes to bottom face": BORE_Y - _STATION - _HOLE_R,
    "holes to top face": (HEIGHT - HEIGHT_STOCK_BAND) - (BORE_Y + _STATION) - _HOLE_R,
    "Tr8 major to bottom face": BORE_Y - _STATION - _BORE_R,
    "Tr8 major to top face": (HEIGHT - HEIGHT_STOCK_BAND) - (BORE_Y + _STATION) - _BORE_R,
}
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET_MM:
        raise AssertionError(f"feed nut {_wall} wall {_mm:.3f} under rule 17's target")

# --- Drawing ---------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "NutProfile": {"NutWidth", "NutHeight"},
    "BoreProfile": {"BoreX", "BoreY", "BoreDia"},
    "HoleProfile": {"HoleDia"},
    "HolePatternReference": {"Hole1Offset", "Hole2Offset"},
    # The faced length: a reference sketch, not the extrusion's depth (a
    # drawing view cannot attach the depth; TL-28's BracketThickReference).
    "NutLengthReference": {"NutLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "NutProfile": {"NutWidth": STOCK_PLACES, "NutHeight": STOCK_PLACES},
    "BoreProfile": {"BoreX": BORE_PLACES, "BoreY": BORE_PLACES, "BoreDia": BORE_DRILL_PLACES},
    "HoleProfile": {"HoleDia": HOLE_DIA_PLACES},
    "HolePatternReference": dict.fromkeys(("Hole1Offset", "Hole2Offset"), HOLE_OFFSET_PLACES),
    "NutLengthReference": {"NutLength": LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked feed nut dimension needs authored places")
REFERENCE_SKETCHES = ("HolePatternReference", "NutLengthReference")
# Every fabricated value prints as modelled at its inch places (the hole's
# Ø.144 is the clearance table's 3.658 mm, which prints .144).
for _name, _value in (
    ("NutLength", LENGTH),
    ("BoreX", BORE_X),
    ("BoreY", BORE_Y),
    ("BoreDia", BORE_DRILL),
    ("Hole1Offset", HOLE_OFFSET),
    ("Hole2Offset", HOLE_OFFSET),
):
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(_value / INCH - round(_value / INCH, _places)) > 1e-9:
        raise AssertionError(f"feed nut {_name} {_value} does not print as modelled")
# Model-owned callout rows (swDimensionTextParts_e: 1 prefix, 2 suffix, 4 below).
CALLOUTS_PREFIX = {"HoleDia": "2X <MOD-DIAM>"}
CALLOUTS_SUFFIX = {"BoreDia": " DRILL THRU", "HoleDia": " DRILL THRU"}
CALLOUTS_BELOW = {
    "BoreDia": f"{BORE_THREAD} THRU\n{TR8_ENGAGEMENT_TEXT}",
    "Hole1Offset": MATE_CALLOUT,
    "Hole2Offset": MATE_CALLOUT,
}
# Rule 1 (units): an as-bought fraction is a REF with the supplier's
# tolerance, the band on its own row (TL-28).
STOCK_CALLOUTS = {
    "NutWidth": "STOCK\n±" + f"{WIDTH_STOCK_BAND / INCH:.3f}".lstrip("0"),
    "NutHeight": "STOCK\n±" + f"{HEIGHT_STOCK_BAND / INCH:.4f}".lstrip("0"),
}
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
