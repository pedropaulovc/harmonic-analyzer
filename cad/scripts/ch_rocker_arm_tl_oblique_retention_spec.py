"""Positive pivot capture: shared dimensions and intact-rigid upset bounds.

The flange/cap/block path, not bearing press-fit pullout or unquantified axial
bearing play, retains the carrier. Both top retainers are installed for either
pass. Clearances below bound rigid geometry only: no force/impact rating,
structural deflection allowance, or installed spindle/holder clearance claim.

The credited stop circle is fixed about the BLOCK bearing axis, not the moving
flange centre. Both flange faces cover that circle even after cap bolts reach
their clearance-hole/thread stops. Clamp friction is not credited. Receiver
and cap hole coordinates are each printed from the bearing/pocket axis at
three places; locating receiver holes from a loose outside edge invalidates
this stack. The cap pocket excess is measured over the complete stop circle,
including local surface/parallelism variation, with the screws seated.

Sources, read 2026-10-20: NAS1352 revision11 sheets1-3, vendor reproduction
https://www.aaestore.com.au/media/specs/NAS1352.pdf ; Hardware Specialty1216451
https://www.hardwarespecialty.com/Product/1216451 (NAS1352N4H12). UNC-3A limits
https://www.engineersedge.com/screw_threads_chart.htm ; UNC-2B pitch limits
https://itpbolt.com/wp-content/uploads/2015/08/Class-2B-Internal-Threads.pdf .
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from _printed_tolerance import printed_band_mm
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware

INCH = 25.4
PIN_FLANGE_DIA = 36.0
PIN_FLANGE_DIA_BAND = (0.10, -0.10)
PIN_FLANGE_THICK = 3.0
PIN_FLANGE_THICK_PLACES = 1
PIN_FLANGE_EDGE_BREAK_MAX = 0.25
PIN_FLANGE_PERPENDICULARITY = 0.02  # face to bearing-journal datum axis, across35
PIN_FLANGE_SQUARENESS_SPAN = 35.0
PIN_BOSS_DIAMETER = 12.70
PIN_BOSS_DIAMETER_PLACES = 2
PIN_LOWER_BOSS_HEIGHT = 1.15  # REF; fit to actual upper inner-race face
PIN_LOWER_GAP = (0.10, 0.15)
PIN_UPPER_BOSS_HEIGHT = 10.35  # flange top to carrier seat
PIN_UPPER_BOSS_PLACES = 2
PIN_CARRIER_JOURNAL_LENGTH = 24.5
PIN_CROSS_HOLE_DIA = 5.0
PIN_CROSS_HOLE_BAND = (0.10, 0.0)
PIN_CROSS_HOLE_FROM_SEAT = 18.5
PIN_CROSS_HOLE_FROM_END = 6.0
PIN_CLEVIS_NOMINAL_DIAMETER = hardware.CLEVIS_DIA
CARRIER_THICKNESS = trammel.CARRIER_THICK
CARRIER_HOLE_PERPENDICULARITY = 0.02  # axis zone relative to carrier lower face
CARRIER_ENGAGEMENT_MIN = 10.5  # 12-.8-.4 lower chamfer-.3 top edge allowance
CARRIER_DIAMETRAL_CLEARANCE_MAX = 0.024  # existing H7/h6, unchanged

BLOCK_SPINDLE_END = -54.0
BLOCK_WING_END = -10.0
BLOCK_WING_HALF_WIDTH = 32.0
BLOCK_STOP_EDGE_BREAK_MAX = 0.25
CAP_WIDTH = 50.0  # X
CAP_LENGTH = 70.0  # Y
CAP_HEIGHT = 10.50
CAP_HEIGHT_PLACES = 2
CAP_POCKET_DIAMETER = 36.60
CAP_POCKET_DIAMETER_BAND = (0.10, -0.10)
CAP_POCKET_DEPTH = 3.30  # REF; face to actual flange and chamber-excess requirement
CAP_CHAMBER_EXCESS = (0.20, 0.30)
CAP_APERTURE_DIAMETER = 15.0
CAP_APERTURE_BAND = (0.10, 0.0)
CAP_APERTURE_POSITION_DIAMETER = 0.02  # aperture axis to pocket axis
CAP_BOLT_X_OFFSETS = (-15.0, 15.0)
CAP_BOLT_Y_OFFSETS = (-25.0, 25.0)
CAP_BOLT_CENTERS = tuple((x, y) for x in CAP_BOLT_X_OFFSETS for y in CAP_BOLT_Y_OFFSETS)
CAP_BOLT_LOCATION_PLACES = 3
CAP_BOLT_CLEARANCE_DIAMETER = 6.8
CAP_BOLT_CLEARANCE_BAND = (0.10, 0.0)
CAP_COUNTERBORE_DIAMETER = 14.30
CAP_COUNTERBORE_DIAMETER_PLACES = 2
CAP_COUNTERBORE_DEPTH = 7.500
CAP_COUNTERBORE_DEPTH_PLACES = 3
CAP_WIRE_CHANNEL_WIDTH = 2.50
CAP_WIRE_CHANNEL_DEPTH = 5.50
CAP_WIRE_CHANNEL_PLACES = 2
CAP_BOLT_SKU = "NAS1352N4H12"
CAP_BOLT_LENGTH = 0.750 * INCH
CAP_BOLT_LENGTH_MIN = (0.750 - 0.030) * INCH
CAP_BOLT_HEAD_DIAMETER_MAX = 0.375 * INCH
CAP_BOLT_HEAD_HEIGHT_MAX = 0.250 * INCH
CAP_BOLT_THREAD_MAJOR_MIN = 0.2419 * INCH  # UNC-3A, not the smooth-body minimum
CAP_BOLT_THREAD_PITCH_DIAMETER_MIN = 0.2147 * INCH
CAP_TAP_THREAD_PITCH_DIAMETER_MAX = 0.2224 * INCH  # UNC-2B
CAP_BOLT_PITCH = INCH / 20.0
CAP_BOLT_DIAMETER = INCH / 4.0
LOCK_WIRE_DIAMETER = 0.032 * INCH
TOP_WASHER_OD = 24.0
TOP_WASHER_BORE = 10.2
TOP_WASHER_SUPPLY_MIN_THICKNESS = 7.0
TOP_RUNNING_GAP = (0.10, 0.25)
TOP_WASHER_NOMINAL_THICKNESS = (
    PIN_CROSS_HOLE_FROM_SEAT + PIN_CROSS_HOLE_DIA / 2.0
    - PIN_CLEVIS_NOMINAL_DIAMETER - CARRIER_THICKNESS - sum(TOP_RUNNING_GAP) / 2.0
)
STOP_CONTACT_DIAMETER = 32.0


@dataclass(frozen=True)
class CaptureBounds:
    """Dimensions/angles, not a load capacity or a spindle-clearance verdict."""

    cap_lateral_shift: float
    flange_lateral_shift: float
    flange_contact_margin: float
    floor_inner_margin: float
    floor_counterbore_margin: float
    cap_pocket_margin: float
    cap_aperture_margin: float
    pin_aperture_clearance: float
    flange_tilt: float
    carrier_tilt: float
    support_lift: float
    support_drop: float
    cap_running_clearance: float
    screw_engagement: float


def capture_bounds(
    *,
    chamber_excess: float = CAP_CHAMBER_EXCESS[1],
    stop_diameter: float = STOP_CONTACT_DIAMETER,
    flange_diameter_min: float = PIN_FLANGE_DIA + PIN_FLANGE_DIA_BAND[1],
    flange_thickness_max: float = PIN_FLANGE_THICK + printed_band_mm(PIN_FLANGE_THICK_PLACES),
    pocket_diameter_max: float = CAP_POCKET_DIAMETER + CAP_POCKET_DIAMETER_BAND[0],
    pocket_diameter_min: float = CAP_POCKET_DIAMETER + CAP_POCKET_DIAMETER_BAND[1],
    cap_hole_diameter_max: float = CAP_BOLT_CLEARANCE_DIAMETER + CAP_BOLT_CLEARANCE_BAND[0],
    receiver_location_band: float = printed_band_mm(CAP_BOLT_LOCATION_PLACES),
    cap_location_band: float = printed_band_mm(CAP_BOLT_LOCATION_PLACES),
    receiver_pattern: tuple[tuple[float, float], ...] = CAP_BOLT_CENTERS,
    cap_pattern: tuple[tuple[float, float], ...] = CAP_BOLT_CENTERS,
    bearing_bore_diameter_max: float = 29.989,
    carriage_counterbore_diameter_max: float = 8.0 + printed_band_mm(2),
    block_edge_break_max: float = BLOCK_STOP_EDGE_BREAK_MAX,
    carrier_clearance: float = CARRIER_DIAMETRAL_CLEARANCE_MAX,
    carrier_engagement: float = CARRIER_ENGAGEMENT_MIN,
    top_running_gap: float = TOP_RUNNING_GAP[1],
) -> CaptureBounds:
    """Conservative source-only bound, with mutable inputs for negative controls.

    Averaging the four symmetric screw locations removes rigid cap rotation
    from its centre translation. The deliberately looser per-coordinate sum
    below bounds pattern errors, thread lateral float and clearance-hole float.
    The cap's minimum under-head floor exceeds one complete thread pitch, so a
    full external crest, not an assumed smooth shank, supplies the hole stop.

    At the fixed stop circle, two opposite XY points have flange-face height
    difference D*tan(theta), and the upper/lower face separation is t/cos(theta)
    >=t. Thus D*tan(theta)<=C. Positive projected-contact margins at that angle
    keep the connected operating branch inside the opposing stops.
    """
    if min(chamber_excess, stop_diameter, flange_diameter_min, carrier_engagement) <= 0.0:
        raise ValueError("capture sizes and engagement must be positive")
    if len(receiver_pattern) != 4 or len(cap_pattern) != 4:
        raise ValueError("both cap and receiver need all four locking screws")
    pattern_offset = math.hypot(
        *(sum(point[axis] for point in receiver_pattern) / 4.0
          - sum(point[axis] for point in cap_pattern) / 4.0 for axis in (0, 1))
    )
    thread_float = (CAP_TAP_THREAD_PITCH_DIAMETER_MAX - CAP_BOLT_THREAD_PITCH_DIAMETER_MIN) / 2.0
    hole_float = (cap_hole_diameter_max - CAP_BOLT_THREAD_MAJOR_MIN) / 2.0
    if hole_float < 0.0:
        raise ValueError("cap clearance hole does not pass the sourced screw")
    cap_shift = pattern_offset + math.sqrt(2.0) * (
        receiver_location_band + cap_location_band + thread_float + hole_float
    )
    tilt = math.atan(chamber_excess / stop_diameter)
    # A tilted cylinder's projected half-height is included, not only nominal
    # diametral pocket clearance. Both flange faces remain credited.
    flange_float = (
        pocket_diameter_max / 2.0 - flange_diameter_min / 2.0 * math.cos(tilt)
        + flange_thickness_max / 2.0 * math.sin(tilt)
    )
    pin_shift = cap_shift + flange_float
    projected_flat_radius = (
        flange_diameter_min / 2.0 - PIN_FLANGE_EDGE_BREAK_MAX
    ) * math.cos(tilt) - flange_thickness_max / 2.0 * math.sin(tilt)
    flange_margin = projected_flat_radius - pin_shift - stop_diameter / 2.0
    floor_inner = stop_diameter / 2.0 - bearing_bore_diameter_max / 2.0 - block_edge_break_max
    # Existing bore stations print two places and carriage-hole stations three.
    station_stack = printed_band_mm(2) + printed_band_mm(3)
    nearest_carriage_bore = math.hypot(19.0 - station_stack, 13.0 - station_stack)
    floor_outer = nearest_carriage_bore - carriage_counterbore_diameter_max / 2.0 - stop_diameter / 2.0
    pocket_margin = pocket_diameter_min / 2.0 - cap_shift - stop_diameter / 2.0
    aperture_margin = stop_diameter / 2.0 - cap_shift - (CAP_APERTURE_DIAMETER + CAP_APERTURE_BAND[0]) / 2.0
    pin_tilt = tilt + math.atan(PIN_FLANGE_PERPENDICULARITY / PIN_FLANGE_SQUARENESS_SPAN)
    carrier_tilt = (
        pin_tilt + math.atan(CARRIER_HOLE_PERPENDICULARITY / carrier_engagement)
        + math.atan(carrier_clearance / carrier_engagement)
    )
    # Both bosses are turned from 1-1/2-in bar; the actual .XX drawing band,
    # not a former 1/2-in stock tolerance, controls the aperture envelope.
    boss_radius_max = (PIN_BOSS_DIAMETER + printed_band_mm(PIN_BOSS_DIAMETER_PLACES)) / 2.0
    aperture_clearance = (
        CAP_APERTURE_DIAMETER / 2.0 - boss_radius_max - flange_float
        - CAP_HEIGHT * math.tan(pin_tilt) - CAP_APERTURE_POSITION_DIAMETER / 2.0
    )
    min_seat_above_floor = (
        PIN_FLANGE_THICK - printed_band_mm(PIN_FLANGE_THICK_PLACES)
        + PIN_UPPER_BOSS_HEIGHT - printed_band_mm(PIN_UPPER_BOSS_PLACES)
    )
    max_cap_height = CAP_HEIGHT + printed_band_mm(CAP_HEIGHT_PLACES)
    cap_radius_from_pin = math.hypot(CAP_WIDTH / 2.0, CAP_LENGTH / 2.0) + flange_float
    cap_clearance = min_seat_above_floor - max_cap_height - cap_radius_from_pin * math.tan(carrier_tilt)
    engagement = CAP_BOLT_LENGTH_MIN - (
        max_cap_height - (CAP_COUNTERBORE_DEPTH - printed_band_mm(CAP_COUNTERBORE_DEPTH_PLACES))
    ) - CAP_BOLT_PITCH
    minimum_head_floor = CAP_HEIGHT - printed_band_mm(CAP_HEIGHT_PLACES) - (
        CAP_COUNTERBORE_DEPTH + printed_band_mm(CAP_COUNTERBORE_DEPTH_PLACES)
    )
    margins = (flange_margin, floor_inner, floor_outer, pocket_margin, aperture_margin, aperture_clearance, cap_clearance)
    if min(margins) <= 0.0:
        raise ValueError("opposing-stop contact or running clearance is lost")
    if minimum_head_floor <= CAP_BOLT_PITCH:
        raise ValueError("under-head floor does not enclose one complete thread crest")
    if engagement < 1.5 * CAP_BOLT_DIAMETER:
        raise ValueError("cap screw has less than 1.5D complete thread engagement")
    return CaptureBounds(
        cap_shift, flange_float, flange_margin, floor_inner, floor_outer,
        pocket_margin, aperture_margin, aperture_clearance, tilt, carrier_tilt,
        chamber_excess + top_running_gap, chamber_excess, cap_clearance, engagement,
    )


def point_lift_bound(
    point: tuple[float, float], pass_name: str, bounds: CaptureBounds | None = None,
) -> float:
    """Point rise above its actual normal pose, both support retainers installed.

    Between supports, interpolate their bounded heights. Outboard of an end,
    include the bounded end-to-end slope; pitch about their line remains the
    full local captured angular bound. No 450-mm-span substitution for pitch.
    """
    if pass_name not in ("inner", "outer"):
        raise ValueError("unknown pass")
    bound = capture_bounds() if bounds is None else bounds
    a, b = (trammel.A1, trammel.B1) if pass_name == "inner" else (trammel.A2, trammel.B2)
    x, y = point
    outboard = max(a[0] - x, x - b[0], 0.0)
    end_slope = min(math.tan(bound.carrier_tilt), (bound.support_lift + bound.support_drop) / (b[0] - a[0]))
    return bound.support_lift + outboard * end_slope + abs(y - a[1]) * math.tan(bound.carrier_tilt)


# Nominal only: limits are reported separately from actual manufactured bands.
PIN_PROJECTION_ABOVE_WORK_NOMINAL = (
    PIN_CARRIER_JOURNAL_LENGTH - trammel.CARRIER_THICK - trammel.RISER_THICK - trammel.STRAP_THICK
)
