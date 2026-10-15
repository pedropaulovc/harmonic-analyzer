"""Assembly-level settings of the mg-magnifier wheel stack, as model dimensions.

Two settings belong to no single part: the press gauge the wheel axle is pressed
to in the bar, and the endshake the first nut sets. Each one is printed as a
native model dimension on the MHA-MG-000 sheet. A construction chain in the
assembly carries both (the ms-measuring-stick ClampedSetting pattern). It runs
along the axle centreline on the Right plane, through four stations: the bar
front face, the shank step, the wheel's spigot face and the front washer. The
chain is blanked, so it prints only in the drawing view that dimensions it.
"""

from __future__ import annotations

import mg_wheel_axle_spec as _pin
import mg_wheel_bar_geom as _bar
import mg_wheel_group as _group
from vn_lever_wire_geom import WHEEL_BAR_Y, WHEEL_X

# The axle centreline in the machine frame: x, y of the bore; z runs from the
# bar's front face forward (-z), station d at z = BAR_FRONT_Z - d.
AXLE_X = WHEEL_X
AXLE_Y = WHEEL_BAR_Y
BAR_FRONT_Z = _bar.BAR_FRONT_Z

PRESS_GAUGE = _pin.PRESS_GAUGE
PRESS_GAUGE_TOL = _pin.PRESS_GAUGE_TOL
# The modelled endshake sits mid-band, so its band prints symmetric.
ENDSHAKE = _group.ENDSHAKE
ENDSHAKE_TOL = _group.ENDSHAKE_MAX - _group.ENDSHAKE
if abs((_group.ENDSHAKE - _group.ENDSHAKE_MIN) - ENDSHAKE_TOL) > 1e-9:
    raise AssertionError("the endshake band is not symmetric about its model value")

# Chain stations d (from the bar front face) along the axle centreline.
STEP_D = PRESS_GAUGE
HUB_FRONT_D = _group.HUB_FRONT_D
WASHER_D = _group.FRONT_WASHER_D
if abs((WASHER_D - HUB_FRONT_D) - ENDSHAKE) > 1e-9:
    raise AssertionError("the front washer no longer sits one endshake off the hub")
if not 0.0 < HUB_FRONT_D - STEP_D:
    raise AssertionError("the shank step must stand inside the wheel hub")
CHAIN_D = (0.0, STEP_D, HUB_FRONT_D, WASHER_D)

FEATURE = "AxleStackReference"
PRESS_GAUGE_DIMENSION = "PressGauge"
ENDSHAKE_DIMENSION = "Endshake"
DRAWING_DIMENSIONS = {FEATURE: {PRESS_GAUGE_DIMENSION, ENDSHAKE_DIMENSION}}
DRAWING_PRECISION = {FEATURE: {PRESS_GAUGE_DIMENSION: 2, ENDSHAKE_DIMENSION: 2}}
TOLERANCE_PRECISION = 2
DIMENSION_TOLERANCES = {
    PRESS_GAUGE_DIMENSION: PRESS_GAUGE_TOL,
    ENDSHAKE_DIMENSION: ENDSHAKE_TOL,
}
# Each callout states what its band protects. The gauge's prints above its
# value, on one line: SolidWorks keeps a line break in that compartment but
# prints none of the callout (run 20261012T185729782Z). The endshake's
# prints below, where line breaks print.
DIMENSION_CALLOUTS = {
    PRESS_GAUGE_DIMENSION: "PRESS GAUGE: KEEPS WHEEL LOCKNUT ON FULL THREAD",
    ENDSHAKE_DIMENSION: "\n".join(
        (
            "WHEEL FREE, NO RATTLE;",
            "SET BY THE FIRST NUT,",
            "LOCKED BY THE SECOND",
        )
    ),
}
