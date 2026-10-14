r"""Pure-data contract for the rocker template trammel's pivot point
(MHA-CH-006-TL-18; shop tooling, one off).

Shop tooling, not a machine part (cad/docs/subsystem-identities.md). This
1/4 in O1 drill-rod point stands in the pivot block's (MHA-CH-006-TL-14) reamed
point hole. Its 60 degree tip runs in the 60 degree centre-drilled cone of the
pivot plate (MHA-CH-006-TL-19), so the trammel swings about the plate with no
play (trial route ``rocker-template-route.md`` sections 2.1-2.4, kit contract
``ch_rocker_arm_tl_trammel_spec``). It also drops into the setting bar's H0
cone when the kit is set. The point slides up or down in its pinch hole to
stand ``kit.POINT_PROJECTION`` below the block without moving R.

The rod is cut to length, one end turned to a 60 degree included cone whose
tip lies on the rod axis, and the last 20 mm torch-hardened and tempered to
light straw (route 2.4). The rod's O.D. stays as supplied. Hardness lives in
the Finish field; the hardened zone's extent is a native dimension.

Frame: the point's axis is model +X. The theoretical sharp apex of the cone is
at the origin and the faced back end at X = POINT_LENGTH. The tip is truncated
by a flat at X = TIP_FLAT_STATION (drawing-guidelines rule 16). The kit frame
(``kit.PRECHIPS_SOLIDS``) poses the point with its axis vertical and its tip
at ``kit.TIP_Z``.
"""

from __future__ import annotations

import math

import ch_rocker_arm_tl_trammel_spec as kit
from _fit_deviations import deviations
from _printed_tolerance import angular_band_deg

# --- Stock: 1/4 in O1 drill rod, cut to length --------------------------------
ROD_DIA = kit.POINT_ROD_DIA
ROD_R = ROD_DIA / 2.0
# Precision-ground drill rod's catalogue band. The point prints its O.D. as a
# stock reference: the block's reamed hole carries the fit.
_ROD_LOW, _ROD_HIGH = (
    ROD_DIA + deviation for deviation in deviations(kit.POINT_ROD_DIA_BAND)
)
ROD_DIA_MAX = _ROD_HIGH
ROD_DIA_MIN = _ROD_LOW
ROD_PLACES = 2
# The point slides in the pivot block's reamed hole: the largest rod still
# clears the reamed size.
ROD_HOLE_CLEARANCE_MIN = kit.POINT_HOLE_DIA - ROD_DIA_MAX
if not ROD_HOLE_CLEARANCE_MIN > 0.0:
    raise AssertionError(
        "the largest drill rod does not slide in the reamed point hole"
    )

POINT_LENGTH = kit.POINT_LENGTH
LENGTH_PLACES = 1
# The rod reaches through the block's full height above the projecting tip.
if not POINT_LENGTH - kit.POINT_PROJECTION > kit.BLOCK_HEIGHT:
    raise AssertionError("the pivot point does not pass through its block")

# --- Tip cone ------------------------------------------------------------------
TIP_ANGLE = kit.PIVOT_TIP_ANGLE
TIP_HALF_ANGLE = TIP_ANGLE / 2.0
TIP_HALF_ANGLE_PLACES = 1
# The printed half-angle carries half the title block's angular band, so the
# included angle holds the title block's band (the thumbnut countersink's
# convention).
TIP_HALF_ANGLE_TOL_DEG = angular_band_deg() / 2.0
TIP_ANGLE_TOL_DEG = 2.0 * TIP_HALF_ANGLE_TOL_DEG
TIP_HALF_ANGLE_MIN = TIP_HALF_ANGLE - TIP_HALF_ANGLE_TOL_DEG
TIP_HALF_ANGLE_MAX = TIP_HALF_ANGLE + TIP_HALF_ANGLE_TOL_DEG
# The cone runs from the apex to the full rod O.D.
CONE_LENGTH = ROD_R / math.tan(math.radians(TIP_HALF_ANGLE))

# Drawing-guidelines rule 16: the point carries a stated flat. The model
# carries the printed maximum; swTolMAX prints "MAX" after the nominal, so the
# nominal must be the band's top. A sharp tip (no flat) is acceptable.
TIP_FLAT_DIA = 0.5
TIP_FLAT_PLACES = 1
TIP_FLAT_DIA_BAND = (0.0, -TIP_FLAT_DIA)  # (upper, lower)
TIP_FLAT_DIA_TOL_TYPE = 6  # swTolType_e.swTolMAX
_flat_lower, _flat_upper = deviations(TIP_FLAT_DIA_BAND)
TIP_FLAT_DIA_MAX = TIP_FLAT_DIA + _flat_upper
if (
    TIP_FLAT_DIA != TIP_FLAT_DIA_MAX
    or round(TIP_FLAT_DIA_MAX, TIP_FLAT_PLACES) != TIP_FLAT_DIA_MAX
):
    raise AssertionError("the tip flat's model value is not its printed maximum")
# The flat's station from the theoretical apex.
TIP_FLAT_STATION = TIP_FLAT_DIA / 2.0 / math.tan(math.radians(TIP_HALF_ANGLE))

# --- Seat: the No. 2 centre-drilled cone (pivot plate, setting bar H0) -------
# Inventory tools.center-drills-lms-4859 member "2": pilot 1.982 (kit: 5/64 in),
# 1.98 from the countersink's end (the pilot's entry) to the drill-point tip,
# 118 degree drill point, 60 degree countersink.
PILOT_DIA = kit.CENTER_DRILL_PILOT_DIA
PILOT_R = PILOT_DIA / 2.0
PILOT_LENGTH = 1.98
PILOT_POINT_HALF_ANGLE = 118.0 / 2.0
SEAT_HALF_ANGLE = kit.CENTER_DRILL_ANGLE / 2.0
# A cone sharper than the seat bears on the pilot's entry edge (radius
# PILOT_R); a blunter one bears on the countersink's mouth, higher up. The
# deepest tip is the sharpest printed cone with no flat at all, its apex
# PILOT_R / tan(half) below the pilot's entry.
TIP_DEPTH_MAX = PILOT_R / math.tan(math.radians(TIP_HALF_ANGLE_MIN))
# The pilot's drill-point floor narrows to its own apex at PILOT_LENGTH: the
# floor's radius at the deepest tip's depth is the radial room left there.
# The floor cone (59 degree half-angle) is wider than the point cone (30.5 at
# most) and its apex is deeper, so nowhere above the tip does the point reach it.
TIP_FLOOR_ROOM = (PILOT_LENGTH - TIP_DEPTH_MAX) * math.tan(
    math.radians(PILOT_POINT_HALF_ANGLE)
)
if not TIP_DEPTH_MAX < PILOT_LENGTH or not TIP_FLOOR_ROOM > 0.0:
    raise AssertionError("the pivot point bottoms in the centre drill's pilot")
if not TIP_HALF_ANGLE_MAX < PILOT_POINT_HALF_ANGLE:
    raise AssertionError("the pivot cone is blunter than the pilot's drill-point floor")
# The cone still exists where it bears: the largest flat stays inside the pilot.
if not TIP_FLAT_DIA_MAX < PILOT_DIA:
    raise AssertionError("the pivot tip flat swallows the pilot's bearing edge")
if abs(TIP_HALF_ANGLE - SEAT_HALF_ANGLE) > 1e-12:
    raise AssertionError("the pivot cone does not match its centre-drilled seat")

# --- Hardened zone (route 2.4: the last 20 mm) ---------------------------------
HARDENED_LENGTH = kit.HARDENED_TIP_LENGTH
# The whole projecting tip and the full cone are hard.
if not HARDENED_LENGTH > max(kit.POINT_PROJECTION, CONE_LENGTH):
    raise AssertionError("the hardened zone does not cover the projecting pivot tip")

# --- Print -------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PointProfile": {"PointLength", "RodDia", "TipHalfAngle"},
    "TipFlatProfile": {"TipFlatDia"},
    "HardenedZoneReference": {"HardenedLength"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PointProfile": {
        "PointLength": LENGTH_PLACES,
        "RodDia": ROD_PLACES,
        "TipHalfAngle": TIP_HALF_ANGLE_PLACES,
    },
    "TipFlatProfile": {"TipFlatDia": TIP_FLAT_PLACES},
    "HardenedZoneReference": {"HardenedLength": LENGTH_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot-point dimension needs authored places")

# The O.D. is the drill rod as supplied (stock stays stock): a reference
# with the function that rides on it, naming the mate by Number.
REFERENCE_DIMENSIONS = frozenset({"RodDia"})
# Callouts ride the below lane only, one short line each (about 30
# characters at most): SolidWorks does not wrap callout text.
ROD_CALLOUT = "DRILL ROD AS SUPPLIED\nSLIDES IN MHA-CH-006-TL-14\nPOINT HOLE"
ROD_NOTE = " ".join(ROD_CALLOUT.splitlines())
# Drawing-guidelines rule 4: the half-angle's band serves the seats, so the
# angle callout names them by Number: the pivot plate's and the setting bar's
# centre-drilled cones.
TIP_ANGLE_CALLOUT = (
    "EACH SIDE OF AXIS\nSEATS IN MHA-CH-006-TL-19\nAND MHA-CH-006-TL-17 CONES"
)
HARDENED_CALLOUT = "HARDENED ZONE"
TIP_FLAT_CALLOUT = "TIP FLAT"
DIMENSION_CALLOUTS = {
    "RodDia": ROD_CALLOUT,
    "TipHalfAngle": TIP_ANGLE_CALLOUT,
    "HardenedLength": HARDENED_CALLOUT,
    "TipFlatDia": TIP_FLAT_CALLOUT,
}

# The blind reviewer sees only the sheet: each note states a function.
# Hardness lives in the Finish field.
DRAWING_NOTES = "TIP CONE TRUE TO THE ROD AXIS; TIP FLAT CENTRED ON IT."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
