r"""Pure-data contract for the round arbor's backing collar (MHA-DT-03-TL-08).

Shop tooling (issue #2356; owner ruling 2026-11-20, Option 2: "Ø.38
collar"). The one collar stands between T024 and the #8-32 nut
(MHA-DT-03-TL-VN-51) on the round arbor MHA-DT-03-TL-07's pilot, under
T024's root: every number and every assert on it lives with the stack in
``dt_cone_gear_tl_round_arbor_spec`` (COLLAR_DIA, COLLAR_LENGTH,
COLLAR_BORE). 3/8 round bar left at stock diameter, faced to length and
drilled through with an E (1/4) drill: the keyed arbor's collar
(``dt_cone_gear_tl_arbor_collar_spec``) as one member.

Frame: axis +Z; the face on the blank at z = 0 (the Front Plane), the face
under the nut at z = LENGTH.
"""

from __future__ import annotations

import math

import _config
import dt_cone_gear_tl_round_arbor_spec as arbor
from _package_units import drawing_unit

PART_NAME = "dt-cone-gear-tl-round-arbor-collar"
_ROW = _config.parts("dt-cone-gear-tl-round-arbor-collar")
if PART_NAME != "dt-cone-gear-tl-round-arbor-collar":
    raise AssertionError("PART_NAME and the registry row it reads disagree")
PART_NUMBER = str(_ROW["number"])
UNIT = drawing_unit("parts/dt-cone-gear-tl-round-arbor-collar", _ROW)
INCH = arbor.INCH

OUTER_DIA = arbor.COLLAR_DIA
LENGTH = arbor.COLLAR_LENGTH
BORE = arbor.COLLAR_BORE
V_COLLAR = math.pi / 4.0 * (OUTER_DIA**2 - BORE**2) * LENGTH

PROFILE = "CollarProfile"
COLLAR = "Collar"
# Model globals (mm). "Length" alone is a dimension name, so each global
# carries the part's name (the hub washer's "Thickness" lesson).
GLOBALS: dict[str, float] = {
    "CollarOD": OUTER_DIA,
    "CollarBore": BORE,
    "CollarLength": LENGTH,
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    PROFILE: {"OuterDia", "BoreDia"},
    COLLAR: {"Length"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    PROFILE: {"OuterDia": 2, "BoreDia": 3},
    COLLAR: {"Length": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dims in DRAWING_PRECISION.values() for name, places in dims.items()
}
for _feature, _names in DRAWING_DIMENSIONS.items():
    if set(DRAWING_PRECISION[_feature]) != _names:
        raise AssertionError(
            f"{_feature}: every marked dimension needs authored places"
        )
DRAWING_VALUES_BY_NAME: dict[str, float] = {
    "OuterDia": OUTER_DIA,
    "BoreDia": BORE,
    "Length": LENGTH,
}
for _name, _value in DRAWING_VALUES_BY_NAME.items():
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(arbor.inch_grid_mm(_value, _places) - _value) > 1e-9:
        raise AssertionError(f"{_name} {_value} mm is off its printed grid")

# Sheet words (the keyed collar's): the bore is a plain drilled hole (the
# title block's DRILLED HOLES row), through, its process on its callout (rule
# 12); the outside diameter is the bar left at stock.
BORE_CALLOUT = "DRILL THRU"
STOCK_CALLOUT = "STOCK OK"
CALLOUTS_BELOW: dict[str, str] = {
    "OuterDia": STOCK_CALLOUT,
    "BoreDia": BORE_CALLOUT,
}

ISOMETRIC_VIEW_SCALE = (2, 1)
ISOMETRIC_VIEW_NOTE = (
    f"ISOMETRIC VIEW SCALE {ISOMETRIC_VIEW_SCALE[0]}:{ISOMETRIC_VIEW_SCALE[1]}"
)
