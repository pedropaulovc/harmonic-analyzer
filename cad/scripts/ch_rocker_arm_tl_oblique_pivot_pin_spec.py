r"""Pure-data contract for the oblique trammel's pivot pin
(MHA-CH-06-TL-23; shop tooling, two off).

Two captured pivot cartridges support the carrier in the original k5/N6
6200 bearing fits. Those fits locate rotation only; axial safety is the
mechanically locked washer/pin/flange/cap/block path, not bearing friction.

Material: 1-1/2 in 1144 stress-proof round. The integral flange, the narrow
lower inner-race boss, raised carrier seat and both journals are turned from
one piece. Frame: +Z is the pin axis, origin at the lower end. The unchanged
22-long bearing journal ends at the upper inner-race face (block-local Z23
nominal); model Z is block Z minus the nominal bearing recess.

The narrow Ø12.7 boss alone contacts that inner race. Its nominal height
1.15 puts the broad flange underside at block-local Z24.15; fit its height
from the actual assembled upper-race face and the block's machined top face
around the upper bearing seat to obtain 0.10-0.15 flange-rim/top-face gap,
with the entire relieved underside clear of seal and outer race. This is a
fitted acceptance, not a tolerance-stack promise or a bearing-preload
adjustment. The cap pocket is separately fitted to the actual flange
thickness and local floor/ceiling variation.

The Ø36 flange is 3 thick; the upper Ø12.7 boss is nominally 12.35 from
flange top to carrier seat, reaching block-local Z39.5.
The Ø10 h6 carrier journal extends 24.5 above that seat. Its real Ø5 cross
hole lies 18.5 above the seat and 6 from the end for the removable headed
clevis pin and split cotter. Both journal fit diameters remain unchanged:
Ø10 k5 in the bearings and Ø10 h6 in the carrier's Ø10 H7 holes.

Both broad annular flange stop faces carry total axial runout 0.05 to datum
A, the bearing-journal cylinder, inspected before pressing into the bearings.
The full-face control includes the Ø35 inspection circle: opposing readings
differ by at most 0.05, so face-axis tilt is bounded by atan(0.05 / 35), as
used by capture_bounds. It also limits radial form variation that the old
single-circle inspection did not. Nominally square CAD faces are not proof.

Both ends carry 0.5 x 45 degree leads. The carrier-end lead is 0.5 MAX
to preserve the cross-hole end ligament. Both seating shoulders are R0.2
MAX, under the bearing chamfer and carrier-hole edge break.

Constructive assembly applies each press load only to the fitted ring:
support an inner race when fitting its pin journal and an outer race when
fitting its block seat; never transmit a fitting load through the balls.
Cartridge service is destructive: remove the locked cap,
support the block and press the pin UPWARD from its lower end. Its flange
cannot pass downward through the bearing bores. Use the retained Ø25 collet
puller cavity for the remaining bearing. Replace the pin AND BOTH bearings
after this extraction; no damage-free removal or bearing-reuse claim.
"""

from __future__ import annotations

import _config
import _mcmaster_5972k41 as bearing_catalogue
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_oblique_retention_spec as retention
from _fit_deviations import deviations
from _gtol_controls import GeometricControl, PartDatum
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_drilled_tolerance import drilled_oversize_mm
from _printed_tolerance import printed_band_mm

STOCK_DIA = 38.1  # 1-1/2 in 1144 round
LENGTH_PLACES = 1

# The turned narrow bosses retain the original inner-race abutment diameter.
COLLAR_DIA = retention.PIN_BOSS_DIAMETER
COLLAR_PLACES = retention.PIN_BOSS_DIAMETER_PLACES
BEARING_DA_MIN = 12.0  # 6200 abutment diameter, minimum (SKF)
if not BEARING_DA_MIN <= COLLAR_DIA - printed_band_mm(COLLAR_PLACES):
    raise AssertionError("the printed narrow boss misses the inner race")

# --- Matched fits (ISO 286, 6-10 mm row: IT5 0.006, IT6 0.009, IT7 0.015) -----
FIT_DIA = trammel.BEARING_BORE  # ⚙ 10
FIT_PLACES = 3
PIN_HOLE_BAND = (0.015, 0.0)  # Ø10 H7, the carrier's reamed pin holes
BEARING_BAND = (0.007, 0.001)  # k5 (docstring: p6 would preload the 6200s)
CARRIER_BAND = (0.0, -0.009)  # h6

_bearing_low, _bearing_high = deviations(BEARING_BAND)
_race_low, _race_high = deviations(bearing_catalogue.BORE_BAND)
BEARING_INTERFERENCE_MIN = round(_bearing_low - _race_high, 6)
BEARING_INTERFERENCE_MAX = round(_bearing_high - _race_low, 6)
if (BEARING_INTERFERENCE_MIN, BEARING_INTERFERENCE_MAX) != (0.001, 0.015):
    raise AssertionError("the pivot pin bearing section is not the 0.001-0.015 fit")

_carrier_low, _carrier_high = deviations(CARRIER_BAND)
_hole_low, _hole_high = deviations(PIN_HOLE_BAND)
CARRIER_CLEARANCE_MIN = round(_hole_low - _carrier_high, 6)
CARRIER_CLEARANCE_MAX = round(_hole_high - _carrier_low, 6)
if (CARRIER_CLEARANCE_MIN, CARRIER_CLEARANCE_MAX) != (0.0, 0.024):
    raise AssertionError("the pivot pin carrier section is not the 0.000-0.024 fit")
# The model carries the bearing section at the k5 low limit (an exported
# nominal lies inside its band) and prints it as Ø10.001 +0.006/0: the
# same 10.001/10.007 limits.
BEARING_DIA = round(FIT_DIA + BEARING_BAND[1], 6)
BEARING_PRINT_BAND = (round(BEARING_BAND[0] - BEARING_BAND[1], 6), 0.0)

# --- Section lengths -------------------------------------------------------------
BEARING_LENGTH = (
    trammel.BEARINGS_PER_PIN * trammel.BEARING_WIDTH + trammel.BEARING_SHOULDER
)  # ⚙ 22.0
COLLAR_HEIGHT = trammel.PIN_COLLAR_HEIGHT
CARRIER_LENGTH = retention.PIN_CARRIER_JOURNAL_LENGTH
FLANGE_DIA = retention.PIN_FLANGE_DIA
FLANGE_DIA_BAND = retention.PIN_FLANGE_DIA_BAND
FLANGE_THICK = retention.PIN_FLANGE_THICK
FLANGE_THICK_PLACES = retention.PIN_FLANGE_THICK_PLACES
LOWER_BOSS_HEIGHT = retention.PIN_LOWER_BOSS_HEIGHT
UPPER_BOSS_HEIGHT = retention.PIN_UPPER_BOSS_HEIGHT
UPPER_BOSS_PLACES = retention.PIN_UPPER_BOSS_PLACES
FLANGE_EDGE_BREAK_MAX = retention.PIN_FLANGE_EDGE_BREAK_MAX
# Local aliases keep the shared functional limits visible to native feature
# provenance without introducing a second inspection authority.
STOP_FACE_VARIATION_MAX = retention.PIN_STOP_FACE_VARIATION_MAX
STOP_FACE_MEASUREMENT_DIAMETER = retention.PIN_STOP_FACE_MEASUREMENT_DIAMETER
# The clevis cross hole is an ordinary drilled hole: the retention stack
# analyses the title block's DRILLED HOLES row, which the plain two-place
# "Ø5.00 DRILL THRU" callout already prints (rules 2 and 3).
CROSS_HOLE_BAND = retention.PIN_CROSS_HOLE_BAND
if deviations(CROSS_HOLE_BAND) != (0.0, drilled_oversize_mm()):
    raise AssertionError("the analysed cross-hole band is not the DRILLED HOLES row")
FLANGE_BOTTOM_STATION = BEARING_LENGTH + LOWER_BOSS_HEIGHT
FLANGE_TOP_STATION = FLANGE_BOTTOM_STATION + FLANGE_THICK
CROSS_HOLE_DIA = retention.PIN_CROSS_HOLE_DIA
CROSS_HOLE_FROM_SEAT = retention.PIN_CROSS_HOLE_FROM_SEAT
CROSS_HOLE_FROM_END = retention.PIN_CROSS_HOLE_FROM_END
COLLAR_STATION = BEARING_LENGTH  # bottom end to the collar's seat face
CARRIER_STATION = COLLAR_STATION + COLLAR_HEIGHT  # bottom end to the collar top
OVERALL_LENGTH = CARRIER_STATION + CARRIER_LENGTH
CROSS_HOLE_STATION = CARRIER_STATION + CROSS_HOLE_FROM_SEAT
# The hidden named axis on the turned axis that the jig assembly mates the
# carrier's holes on: a name pick is view-independent, a face point is not.
AXIS_NAME = "PinAxis"
CARRIER_SEAT_PLANE = "CarrierSeat"
FLANGE_LOWER_PLANE = "FlangeLowerFace"
CROSS_PIN_AXIS_NAME = "CrossPinAxis"
LEAD_CHAMFER = 0.5
LEAD_CHAMFER_MAX = LEAD_CHAMFER  # carrier end: physical MAX, not the general band
LEAD_CHAMFER_PLACES = 1
SHOULDER_FILLET_RADIUS = 0.2
FILLET_PLACES = 1
RADIUS_TOL_TYPE = 6  # swTolType_e.swTolMAX
BEARING_BORE_CHAMFER_MIN = 0.6  # 6200 r1,2 min

if COLLAR_HEIGHT != trammel.BEARING_RECESS + trammel.PIN_COLLAR_PROUD:
    raise AssertionError("the collar does not stand PIN_COLLAR_PROUD above the block")
if CARRIER_LENGTH != CROSS_HOLE_FROM_SEAT + CROSS_HOLE_FROM_END:
    raise AssertionError("the cross hole does not leave the specified end ligament")
if not COLLAR_STATION < FLANGE_BOTTOM_STATION < FLANGE_TOP_STATION < CARRIER_STATION:
    raise AssertionError("the integral flange does not lie between the narrow bosses")
if not LEAD_CHAMFER < min(BEARING_LENGTH, CARRIER_LENGTH):
    raise AssertionError("a lead chamfer eats a fit section")
if not SHOULDER_FILLET_RADIUS < BEARING_BORE_CHAMFER_MIN:
    raise AssertionError("the collar fillet fouls the inner race's bore chamfer")

# --- Print -----------------------------------------------------------------------
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PinProfile": {
        "BearingDia",
        "BearingLength",
        "CollarDia",
        "CarrierDia",
        "CarrierLength",
        "UpperBossHeight",
        "PinLength",
        "BottomChamfer",
        "TopChamfer",
        "FlangeDia",
        "FlangeThick",
        "LowerBossHeight",
    },
    "SeatFillet": {"SeatFilletR"},
    "CarrierFillet": {"CarrierFilletR"},
}
DRAWING_DIMENSIONS["CrossHoleProfile"] = {"CrossHoleDia", "CrossHoleFromEnd"}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PinProfile": {
        "BearingDia": FIT_PLACES,
        "BearingLength": LENGTH_PLACES,
        "CollarDia": COLLAR_PLACES,
        "CarrierDia": FIT_PLACES,
        "CarrierLength": LENGTH_PLACES,
        "UpperBossHeight": UPPER_BOSS_PLACES,
        "PinLength": LENGTH_PLACES,
        "BottomChamfer": LEAD_CHAMFER_PLACES,
        "TopChamfer": LEAD_CHAMFER_PLACES,
        "FlangeDia": 2,
        "FlangeThick": FLANGE_THICK_PLACES,
        "LowerBossHeight": 2,
    },
    "SeatFillet": {"SeatFilletR": FILLET_PLACES},
    "CarrierFillet": {"CarrierFilletR": FILLET_PLACES},
}
DRAWING_PRECISION["CrossHoleProfile"] = {
    "CrossHoleDia": 2,
    "CrossHoleFromEnd": LENGTH_PLACES,
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot-pin dimension needs authored places")

# drawing-guidelines rule 4: each tight band is a matched-fit callout naming
# its mate. Callouts ride the below lane, one short line each (SolidWorks
# does not wrap callout text).
# 9bbd's native below-callout starts on BearingDia's vertical leader.
# Three native Century Gothic spaces (1.2931 paper mm each) keep the first
# printed zero clear; other rows retain native centred multiline layout.
BEARING_CALLOUT = (
    f"   {BEARING_INTERFERENCE_MIN:.3f}-{BEARING_INTERFERENCE_MAX:.3f} DIAMETRAL\n"
    "INTERFERENCE ON\n6200-2RS INNER RACE"
)
CARRIER_CALLOUT = (
    f"{CARRIER_CLEARANCE_MIN:.3f}-{CARRIER_CLEARANCE_MAX:.3f} DIAMETRAL\n"
    "CLEARANCE ON\nMHA-CH-06-TL-21 PIN HOLES"
)
BEARING_NOTE = " ".join(BEARING_CALLOUT.split())
CARRIER_NOTE = " ".join(CARRIER_CALLOUT.splitlines())
LEAD_CHAMFER_CALLOUT = "X 45° LEAD CHAMFER"
# The flange's ±0.10 band runs in the positive-capture cap's pocket.
CAP_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-pivot-cap")["number"]
BLOCK_NUMBER = _config.parts("ch-rocker-arm-tl-oblique-pivot-block")["number"]
DIMENSION_CALLOUTS = {
    "BearingDia": BEARING_CALLOUT,
    "CarrierDia": CARRIER_CALLOUT,
    "BottomChamfer": LEAD_CHAMFER_CALLOUT,
    "TopChamfer": LEAD_CHAMFER_CALLOUT,
    "FlangeDia": f"RUNNING FIT IN {CAP_NUMBER}",
    # Name the actual block top surrounding the upper bearing seat, not an
    # unspecified floor or a nonexistent recess. Five native rows fit the
    # witness bay; the drawing reserves their complete measured ink height.
    "LowerBossHeight": (
        "FIT PIVOT BLOCK\n"
        f"{BLOCK_NUMBER} TOP\n"
        "FACE AT UPPER BEARING\n"
        f"SEAT; GAP {retention.PIN_LOWER_GAP[0]:.2f}-{retention.PIN_LOWER_GAP[1]:.2f};\n"
        "NO PRELOAD, CLEAR SEAL"
    ),
    "CrossHoleDia": "DRILL THRU\nHEADED CLEVIS PIN",
    "UpperBossHeight": "SETS CARRIER CLEARANCE\nOVER CAP",
}
# The title block's own edge break (rule 2) stays within the break the
# stop-face capture analysis allows, so the flange thickness has no callout.
_TITLE_EDGE_BREAK = _config.title_block("edge_break")
if max(_TITLE_EDGE_BREAK["radius_mm"], _TITLE_EDGE_BREAK["chamfer_max_mm"]) > FLANGE_EDGE_BREAK_MAX:
    raise AssertionError("the title block's edge break exceeds the flange's analysed break")
# One CollarDia drives both narrow bosses (the profile's horizontal-points
# relation), so its Ø prints once as "2X".
CALLOUTS_ABOVE = {"CollarDia": "2X"}

# Pin-only rule-5 acceptance: user selected standard GD&T on 2026-10-21.
# Total axial runout places each entire annular face between planes normal
# to the actual journal datum axis, 0.05 apart. Its Ø35 subset therefore
# retains the existing capture bound; no assembled-bearing/C2 credit is used.
PART_DATUMS = (
    PartDatum("A", CylinderFace(BEARING_DIA, contains_z_mm=BEARING_LENGTH / 2.0)),
)
GEOMETRIC_CONTROLS = (
    GeometricControl(
        "flange_lower_stop", "total_runout", f"{STOP_FACE_VARIATION_MAX:.2f}",
        PlanarFace((0.0, 0.0, -1.0), -FLANGE_BOTTOM_STATION), ("A",),
    ),
    GeometricControl(
        "flange_upper_stop", "total_runout", f"{STOP_FACE_VARIATION_MAX:.2f}",
        PlanarFace((0.0, 0.0, 1.0), FLANGE_TOP_STATION), ("A",),
    ),
)
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
