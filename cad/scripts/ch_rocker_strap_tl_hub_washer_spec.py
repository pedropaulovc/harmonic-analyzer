r"""Pure-data contract for MHA-CH-13-TL-03, the rocker strap's hub washer.

Shop tooling for the rocker-strap sub-plate fixture MHA-CH-13-TL-00 (owner,
2026-11-17): the flat washer under the hub screw's head (MHA-CH-13-TL-VN-51,
1/4-20 button head, owner ruling 2 of 2026-11-17). It bears on the strap
blank's top round its reamed hub hole and clamps the blank down on its tape
while the outline is cut. Turned from round bar on the manual lathe, faced to
thickness and drilled through.

Sizes: OD .53 and thickness .06 at the title block's .XX, bore Ø.266 drilled
through (H drill, the plug's bore, clears the 1/4-20 screw). Every limit is
judged at the worst case of those bands, against the hub keep-out the
accepted geometry needs (13.716 mm diameter, 1.778 + 3.353 = 5.131 mm stack
above the strap); the pytest checks that keep-out sits inside the plan's
``bushing_flange_dia_mm`` and ``bushing_stack_height_mm``.

Deviation from the shop record: the fixture record as first written
(shop-equipment ``fixtures.strap-hub-plug``, commit 1833599b90) sized the
washer .547 x .079, matched to the then 5/16 screw's .547 x .166 head.
Printed at the title block's .XXX (+/-.005) those sizes broke the plan's
keep-out of the time (13.9 mm flange, 6.2 mm stack): the largest .547
washer is 14.02 mm, and .084 under a .166 head stacks 6.35 mm. The owner
accepted .53 x .06 at .XX (2026-11-17), kept under the 1/4-20 screw
(ruling 2); the record now states these sizes.

Frame: axis +Z, centred; z = 0 the face on the strap (the Front Plane), the
face under the screw head at z = THICKNESS.

Copied constants: the strap hole and the screw's head are copied, not
imported (the strap spec pulls the rocker-arm spec into this closure, and the
screw's own spec is a separate vendor part); no COM leaf may read the plan
TOML, so the plan agreement is asserted in
``test_ch_rocker_strap_tl_hub_washer_drawing``, with each copy.

PURE DATA, no SolidWorks/COM imports.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

PART_NAME = "ch-rocker-strap-tl-hub-washer"
_ROW = _config.parts(PART_NAME)
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit(f"parts/{PART_NAME}", _ROW)
INCH = 25.4

XX = printed_band_mm(2, unit=UNIT)
DRILLED_PLUS = drilled_oversize_mm(unit=UNIT)

# --- The keep-out the accepted geometry needs (the plan's
# bushing_flange_dia_mm and bushing_stack_height_mm must be at least these;
# the pytest asserts it): the largest diameter above the strap and the stack
# height above its top.
FLANGE_DIA_MAX = 13.716
STACK_HEIGHT_MAX = 5.1308
# MHA-CH-13's reamed hub hole, .400 +.0005/.0000.
STRAP_HOLE_DIA_MAX = 10.1727
# MHA-CH-13-TL-VN-51, 1/4-20 button head SCS (ASME B18.3): major diameter
# and the head's height, max.
SCREW_MAJOR_DIA = 6.35  # 1/4
SCREW_HEAD_HEIGHT_MAX = 3.3528  # .132

# --- The washer ---
OUTER_DIA = 13.462  # .53
THICKNESS = 1.524  # .06
BORE_DIA = 6.7564  # .266, letter H drill
OUTER_PLACES = 2
THICKNESS_PLACES = 2
BORE_PLACES = 3

for _value, _places in (
    (OUTER_DIA, OUTER_PLACES),
    (THICKNESS, THICKNESS_PLACES),
    (BORE_DIA, BORE_PLACES),
):
    _step = INCH * 10.0**-_places
    if abs(round(_value / _step) * _step - _value) > 1e-9:
        raise AssertionError(f"{_value} mm is off its {_places}-place inch grid")

OUTER_DIA_MAX = OUTER_DIA + XX
OUTER_DIA_MIN = OUTER_DIA - XX
THICKNESS_MAX = THICKNESS + XX
THICKNESS_MIN = THICKNESS - XX
BORE_DIA_MAX = BORE_DIA + DRILLED_PLUS
STACK_HEIGHT = THICKNESS_MAX + SCREW_HEAD_HEIGHT_MAX

# The plan books these worst cases exactly, so they compare to the micron.
_EPS = 1e-6
if not OUTER_DIA_MAX <= FLANGE_DIA_MAX + _EPS:
    raise AssertionError("the largest washer breaks the plan's hub flange keep-out")
if not STACK_HEIGHT <= STACK_HEIGHT_MAX + _EPS:
    raise AssertionError("washer and screw head break the plan's hub stack height")
if not BORE_DIA > SCREW_MAJOR_DIA:
    raise AssertionError("the washer bore does not clear the 1/4 hub screw")
# It bears on the strap round the hub hole: the smallest washer covers the
# largest hole with a land, and the largest bore stays inside it.
BEARING_LAND_MIN = (OUTER_DIA_MIN - STRAP_HOLE_DIA_MAX) / 2.0
if not BEARING_LAND_MIN > 1.0:
    raise AssertionError("the washer leaves no land on the strap round its hub hole")
if not BORE_DIA_MAX < STRAP_HOLE_DIA_MAX:
    raise AssertionError("the washer bore is larger than the hub hole it covers")
if not THICKNESS_MIN > 0.0:
    raise AssertionError("the thinnest washer has no thickness")

# --- Drawing contract: the PART owns places and callouts.
PROFILE = "WasherProfile"
WASHER = "Washer"
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    PROFILE: {"OuterDia", "BoreDia"},
    WASHER: {"Thickness"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    PROFILE: {"OuterDia": OUTER_PLACES, "BoreDia": BORE_PLACES},
    WASHER: {"Thickness": THICKNESS_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
for _feature, _names in DRAWING_DIMENSIONS.items():
    if set(DRAWING_PRECISION[_feature]) != _names:
        raise AssertionError(
            f"{_feature}: every marked dimension needs authored places"
        )
# Rule 12: the bore is a plain drilled hole (the title block's DRILLED HOLES
# row), its process on its callout. OD and thickness are title-block .XX
# sizes and carry no words.
DIMENSION_CALLOUTS: dict[str, dict[str, str]] = {
    PROFILE: {"BoreDia": "DRILL THRU"},
}
DIMENSION_CALLOUTS_BY_NAME: dict[str, str] = {
    name: text
    for callouts in DIMENSION_CALLOUTS.values()
    for name, text in callouts.items()
}
if set(DIMENSION_CALLOUTS_BY_NAME) - set(DRAWING_PRECISION_BY_NAME):
    raise AssertionError("a hub washer callout names an unmarked dimension")

V_WASHER = math.pi / 4.0 * (OUTER_DIA**2 - BORE_DIA**2) * THICKNESS

ISOMETRIC_VIEW_SCALE = (2, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
