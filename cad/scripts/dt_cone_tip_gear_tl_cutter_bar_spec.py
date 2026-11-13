r"""MHA-DT-37-TL-02: the DT6-FORM1 fly-cutter bar, dimensional contract.

PURE DATA, no SolidWorks/COM and no drawing imports.  Shop tooling
(cad/docs/subsystem-identities.md): a 3/8 cold-finished round, held in the
PM-30MV's 3/8 R8 collet, with a reamed cross hole square to its axis for the
MHA-DT-37-TL-01 bit and a #4-40 tap from its cutting end onto the bit for the
bought set screw MHA-SH-VN-54 (fixture MHA-DT-37-TL-00, issue #2358).

Part frame: bar axis +Y through the origin; the cutting end face on the Top
Plane (y = 0), the collet end at y = BAR_LENGTH.  The cross hole runs along
model X through the axis at y = CROSS_HOLE_STATION; the tap runs up the axis
from the cutting end into the cross hole.
"""

from __future__ import annotations

import _config
import sh_vn_arbor_set_screw_spec as set_screw
from _fit_deviations import deviations
from _fit_ream_h7 import REAM_H7
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, HoleSpec
from _package_units import drawing_unit
from dt_cone_tip_gear_spec import inch_range
from dt_cone_tip_gear_tl_form_cutter_spec import (
    BIT_DIA_LIMITS,
    BIT_RADIUS,
)
from dt_cone_tip_gear_tl_form_cutter_spec import (
    NUMBER as BIT_NUMBER,
)

STEM = "dt-cone-tip-gear-tl-cutter-bar"
_ROW = _config.parts("dt-cone-tip-gear-tl-cutter-bar")
UNIT = drawing_unit("parts/dt-cone-tip-gear-tl-cutter-bar", _ROW)
NUMBER = str(_ROW["number"])
QUANTITY = 1
INCH = 25.4
SET_SCREW_NUMBER = str(_config.parts("sh-vn-arbor-set-screw")["number"])

# --- The bar: 3/8 cold-finished round, as supplied ----------------------------
# The shop's R8 collet set holds 3/8 (the travelers' 3/8 collet); the .XX
# length leaves the collet a full grip above the cross hole.
BAR_DIA = 9.525  # .375
BAR_DIA_PLACES = 3
BAR_RADIUS = BAR_DIA / 2.0
BAR_LENGTH = 44.45  # 1.75
BAR_LENGTH_PLACES = 2

# --- The cross hole: reamed slip fit on the 1/8 drill rod bit ----------------
# A .1260 reamer over the drill rod's .1245-.1255 leaves .0005-.0020 of slip.
CROSS_HOLE_DIA = 3.2004  # .1260
CROSS_HOLE_PLACES = 4
CROSS_HOLE_BAND = REAM_H7  # (upper, lower): +.0005/.0000
_lower, _upper = deviations(CROSS_HOLE_BAND)
CROSS_HOLE_LIMITS = (CROSS_HOLE_DIA + _lower, CROSS_HOLE_DIA + _upper)
SLIP_CLEARANCE = (
    CROSS_HOLE_LIMITS[0] - BIT_DIA_LIMITS[1],
    CROSS_HOLE_LIMITS[1] - BIT_DIA_LIMITS[0],
)
if SLIP_CLEARANCE[0] <= 0.0:
    raise AssertionError("the largest bit must slide into the smallest reamed hole")
# From the cutting end face to the hole's axis, .XX: the set screw seats on
# the bit near flush with that face (the 1/4 screw over the bit's radius).
CROSS_HOLE_STATION = 7.874  # .31
CROSS_HOLE_STATION_PLACES = 2
# The title block's .XX row the station is held to.
CROSS_HOLE_STATION_TOL = 0.254  # +/-.01

# --- The set-screw tap: #4-40 up the axis from the cutting end --------------
# The tap breaks into the cross hole by design (its screw clamps the bit
# there): a native up-to-next tap (pn_pen_v_block's set-screw tap INTO PIVOT
# BORE), drill and full thread both run into the hole, so no web is left
# between the thread and the bore and the callout states no depth.
SET_SCREW_THREAD = set_screw.THREAD
TAP_DRILL_DIA = TAP_DRILL_MM[SET_SCREW_THREAD]
SET_SCREW_HOLE_SPEC = HoleSpec("tapped", SET_SCREW_THREAD, end="through_next")
_STATION_RANGE = (
    CROSS_HOLE_STATION - CROSS_HOLE_STATION_TOL,
    CROSS_HOLE_STATION + CROSS_HOLE_STATION_TOL,
)
# The tap's full length, end face to where the tap drill breaks wholly into
# the hole (the hole's wall over the drill's edge) at the nominal station.
TAP_LENGTH = (
    CROSS_HOLE_STATION
    - ((CROSS_HOLE_DIA / 2.0) ** 2 - (TAP_DRILL_DIA / 2.0) ** 2) ** 0.5
)
SET_SCREW_MIN_ENGAGEMENT = 1.5 * THREAD_MAJOR_MM[SET_SCREW_THREAD]
if TAP_LENGTH < SET_SCREW_MIN_ENGAGEMENT:
    raise AssertionError("the set-screw tap must give the screw 1.5D of thread")
# Seated on the bit's top the screw's socket face stands this far proud of the
# end face (negative: below it).  On the bar's axis it sweeps nothing, so the
# station's band only moves it; what it must keep is its full thread at both
# ends of the band, the thread counted only up to the hole's lowest wall (on
# the axis, at the largest reamed size): the shortest station stands it
# proudest, the longest carries its socket face inside the bar.
SET_SCREW_PROUD = set_screw.LENGTH - (CROSS_HOLE_STATION - BIT_RADIUS)
SET_SCREW_PROUD_MAX = SET_SCREW_PROUD + CROSS_HOLE_STATION_TOL


def set_screw_engaged(station: float) -> float:
    """Full thread the seated screw holds at a cross-hole ``station``."""
    cup = station - BIT_RADIUS
    thread_end = station - CROSS_HOLE_LIMITS[1] / 2.0
    return min(cup, thread_end) - max(cup - set_screw.LENGTH, 0.0)


SET_SCREW_ENGAGED_MIN = min(set_screw_engaged(s) for s in _STATION_RANGE)
if SET_SCREW_ENGAGED_MIN < SET_SCREW_MIN_ENGAGEMENT:
    raise AssertionError("the seated set screw must keep 1.5D of thread")
# Walls: from the cross hole to the bar's surface, and to the cutting end.
CROSS_HOLE_SIDE_WALL = (BAR_DIA - CROSS_HOLE_LIMITS[1]) / 2.0
CROSS_HOLE_END_WALL = CROSS_HOLE_STATION - CROSS_HOLE_LIMITS[1] / 2.0
if min(CROSS_HOLE_SIDE_WALL, CROSS_HOLE_END_WALL) < 2.032:
    raise AssertionError("the cross hole leaves under .080 of wall")


def tap_drill_volume_mm3(steps: int = 400) -> float:
    """Material the tap drill removes: its cylinder up the axis from the
    cutting end to where it meets the cross hole (beyond that, the hole has
    already taken it): the integral over the drill's disc of the height
    y = station - sqrt(r_hole^2 - z^2) at which the hole's wall stands."""
    r_tap, r_hole = TAP_DRILL_DIA / 2.0, CROSS_HOLE_DIA / 2.0
    total = 0.0
    step = 2.0 * r_tap / steps
    for i in range(steps):
        z = -r_tap + (i + 0.5) * step
        chord = 2.0 * (r_tap * r_tap - z * z) ** 0.5
        total += chord * (CROSS_HOLE_STATION - (r_hole * r_hole - z * z) ** 0.5) * step
    return total


# --- Native drawing contract --------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"BarDia", "BarLength"},
    "CrossHoleProfile": {"CrossHoleDia", "CrossHoleStation"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"BarDia": BAR_DIA_PLACES, "BarLength": BAR_LENGTH_PLACES},
    "CrossHoleProfile": {
        "CrossHoleDia": CROSS_HOLE_PLACES,
        "CrossHoleStation": CROSS_HOLE_STATION_PLACES,
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# The tap callout's drill prints at the title block's three places.
HOLE_CALLOUT_PRECISION = 3
DIMENSION_CALLOUTS: dict[str, str] = {
    "BarDia": "STOCK OK",
    "CrossHoleDia": (
        f"REAM THRU\nSLIDING FIT ON {BIT_NUMBER}\n"
        f"(CLEARANCE {inch_range(SLIP_CLEARANCE)} REF)"
    ),
}
