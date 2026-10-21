"""Positive pivot capture: shared dimensions and intact-rigid upset bounds.

The flange/cap/block path, not bearing press-fit pullout or unquantified axial
bearing play, retains the carrier. Both top retainers are installed for either
pass. Clearances below bound rigid geometry only: no force/impact rating,
structural deflection allowance, or installed spindle/holder clearance claim.

The credited stop circle is fixed about the BLOCK bearing axis, not the moving
flange centre. Integral cap registers, with clearance in flat-bottom block
receivers, bound lateral movement without clamp friction or assumptions about
short screws' underhead thread form. Pocket/bearing-relative register
coordinates are printed at three places. The fitted chamber and both normal
rim gaps are measured over the complete stop circle with the cap seated.

Sources, read 2026-10-20: NAS1352 revision11 sheets1-3,
https://www.aaestore.com.au/media/specs/NAS1352.pdf ; actual NAS1352N5H12,
https://cbsfasteners.com/nas-fastener-inventory/ ; underhead fillet and bearing
face allowances, ASME B18.3-2012 https://www.finesz.com/pic/ASME%20B18.3.pdf .
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
PIN_STOP_FACE_VARIATION_MAX = 0.05
PIN_STOP_FACE_MEASUREMENT_DIAMETER = 35.0
PIN_BOSS_DIAMETER = 12.70
PIN_BOSS_DIAMETER_PLACES = 2
PIN_LOWER_BOSS_HEIGHT = 1.15  # REF; fit to actual upper inner-race face
PIN_LOWER_GAP = (0.10, 0.15)
PIN_UPPER_BOSS_HEIGHT = 11.35  # flange top to carrier seat; +11.5 mm work-height change
PIN_UPPER_BOSS_PLACES = 2
PIN_CARRIER_JOURNAL_LENGTH = 24.5
PIN_CROSS_HOLE_DIA = 5.0
PIN_CROSS_HOLE_BAND = (0.10, 0.0)
PIN_CROSS_HOLE_FROM_SEAT = 18.5
PIN_CROSS_HOLE_FROM_END = 6.0
PIN_CLEVIS_NOMINAL_DIAMETER = hardware.CLEVIS_DIA
CARRIER_THICKNESS = trammel.CARRIER_THICK
CARRIER_AXIS_DEVIATION_MAX = 0.05
CARRIER_AXIS_MEASUREMENT_SPAN = 10.5
CARRIER_ENGAGEMENT_MIN = 10.5  # 12-.8-.4 lower chamfer-.3 top edge allowance
CARRIER_DIAMETRAL_CLEARANCE_MAX = 0.024  # existing H7/h6, unchanged

BLOCK_SPINDLE_END = -54.5
BLOCK_WING_END = -9.0
BLOCK_WING_HALF_WIDTH = 33.0
BLOCK_STOP_EDGE_BREAK_MAX = 0.25
CAP_WIDTH = 50.0  # X
CAP_LENGTH = 74.0
CAP_HEIGHT = 11.50
CAP_HEIGHT_PLACES = 2
CAP_OUTLINE_PLACES = 1
CAP_CENTER_LOCATION_PLACES = 2
CAP_POCKET_DIAMETER = 36.60
CAP_POCKET_DIAMETER_BAND = (0.10, -0.10)
CAP_POCKET_DEPTH = 3.30  # REF; face to actual flange and chamber-excess requirement
CAP_CHAMBER_EXCESS = (0.20, 0.30)
CAP_APERTURE_DIAMETER = 19.0
CAP_APERTURE_BAND = (0.10, 0.0)
CAP_BOLT_X_OFFSETS = (-15.0, 15.0)
CAP_BOLT_Y_OFFSETS = (-25.0, 25.0)
CAP_BOLT_CENTERS = tuple((x, y) for x in CAP_BOLT_X_OFFSETS for y in CAP_BOLT_Y_OFFSETS)
CAP_BOLT_LOCATION_PLACES = 3
CAP_BOLT_CLEARANCE_DIAMETER = 9.20
CAP_BOLT_CLEARANCE_BAND = (0.10, 0.0)
CAP_COUNTERBORE_DIAMETER = 16.50
CAP_COUNTERBORE_DIAMETER_PLACES = 2
CAP_COUNTERBORE_DEPTH = 8.500
CAP_COUNTERBORE_DEPTH_PLACES = 3
CAP_ENTRY_RELIEF_DIAMETER = 9.90
CAP_ENTRY_RELIEF_BAND = (0.10, 0.0)
CAP_ENTRY_RELIEF_DEPTH = 1.100
CAP_ENTRY_RELIEF_DEPTH_PLACES = 3
CAP_WIRE_CHANNEL_WIDTH = 2.50
CAP_WIRE_CHANNEL_DEPTH = 6.50
CAP_WIRE_CHANNEL_PLACES = 2
CAP_REGISTER_CENTERS = ((-5.0, -24.0), (5.0, 24.0))
CAP_REGISTER_LOCATION_PLACES = 3
CAP_REGISTER_DIAMETER = 6.0
CAP_REGISTER_DIAMETER_BAND = (0.10, -0.10)
CAP_REGISTER_PROJECTION = 1.000
CAP_REGISTER_PROJECTION_PLACES = 3
CAP_REGISTER_END_CHAMFER_MAX = 0.20
BLOCK_REGISTER_DIAMETER = 7.20
BLOCK_REGISTER_DIAMETER_BAND = (0.10, 0.0)
BLOCK_REGISTER_DEPTH = 2.000
BLOCK_REGISTER_DEPTH_PLACES = 3
GENERAL_ANGULAR_BAND_DEGREES = 1.0
CAP_BOLT_SKU = hardware.SCREW_SKU
CAP_BOLT_LENGTH = hardware.SCREW_LENGTH
CAP_BOLT_LENGTH_MIN = hardware.SCREW_LENGTH_MIN
CAP_BOLT_HEAD_DIAMETER_MAX = hardware.SCREW_HEAD_DIA_MAX
CAP_BOLT_HEAD_HEIGHT_MAX = hardware.SCREW_HEAD_HEIGHT_MAX
CAP_BOLT_HEAD_DIAMETER_MIN = hardware.SCREW_HEAD_DIA_MIN
CAP_BOLT_HEAD_BEARING_DIAMETER_MIN = hardware.SCREW_HEAD_BEARING_DIA_MIN
CAP_BOLT_HEAD_ECCENTRICITY_MAX = hardware.SCREW_HEAD_ECCENTRICITY_MAX
CAP_BOLT_BEARING_ANGLE_MAX_DEGREES = hardware.SCREW_BEARING_ANGLE_MAX_DEGREES
CAP_BOLT_FILLET_JUNCTION_DIAMETER_MAX = hardware.SCREW_FILLET_JUNCTION_DIA_MAX
CAP_BOLT_FILLET_LENGTH_MAX = hardware.SCREW_FILLET_LENGTH_MAX
CAP_BOLT_DIAMETER = hardware.SCREW_MAJOR_DIA_MAX
CAP_BOLT_PITCH = hardware.SCREW_DIMS.pitch
CAP_MIN_COMPLETE_THREAD_ENGAGEMENT = 1.5 * CAP_BOLT_DIAMETER
CAP_SEATING_TORQUE_NM = 0.50
CAP_SEATING_TORQUE_BAND_NM = 0.05
LOCK_WIRE_DIAMETER = 0.032 * INCH
TOP_WASHER_OD = 24.0
TOP_WASHER_BORE = 10.2
TOP_WASHER_SUPPLY_MIN_THICKNESS = 7.0
TOP_RUNNING_GAP = (0.10, 0.25)
TOP_WASHER_NOMINAL_THICKNESS = (
    PIN_CROSS_HOLE_FROM_SEAT + PIN_CROSS_HOLE_DIA / 2.0
    - PIN_CLEVIS_NOMINAL_DIAMETER - CARRIER_THICKNESS - sum(TOP_RUNNING_GAP) / 2.0
)
STOP_CONTACT_DIAMETER = 31.5


@dataclass(frozen=True)
class CaptureBounds:
    """Intact rigid dimensions/angles, not strength or machine clearance."""

    cap_lateral_shift: float
    flange_lateral_shift: float
    flange_contact_margin: float
    floor_inner_margin: float
    floor_counterbore_margin: float
    cap_pocket_margin: float
    cap_aperture_margin: float
    pin_aperture_clearance: float
    register_assembly_clearance: float
    register_bottom_clearance: float
    register_engagement: float
    flange_tilt: float
    pin_tilt: float
    carrier_tilt: float
    carrier_normal_tilt: float
    support_lift: float
    support_drop: float
    cap_running_clearance: float
    screw_available_penetration: float

    @property
    def carrier_slope_change(self) -> float:
        """Either-sign rise relative to an actual accepted normal pose."""
        return math.tan(self.carrier_tilt) + math.tan(self.carrier_normal_tilt)


def capture_bounds(
    *,
    chamber_excess: float = CAP_CHAMBER_EXCESS[1],
    stop_diameter: float = STOP_CONTACT_DIAMETER,
    flange_diameter_min: float = PIN_FLANGE_DIA + PIN_FLANGE_DIA_BAND[1],
    flange_thickness_max: float = PIN_FLANGE_THICK + printed_band_mm(PIN_FLANGE_THICK_PLACES),
    pocket_diameter_max: float = CAP_POCKET_DIAMETER + CAP_POCKET_DIAMETER_BAND[0],
    pocket_diameter_min: float = CAP_POCKET_DIAMETER + CAP_POCKET_DIAMETER_BAND[1],
    register_bore_diameter_max: float = BLOCK_REGISTER_DIAMETER + BLOCK_REGISTER_DIAMETER_BAND[0],
    register_bore_diameter_min: float = BLOCK_REGISTER_DIAMETER + BLOCK_REGISTER_DIAMETER_BAND[1],
    register_boss_diameter_min: float = CAP_REGISTER_DIAMETER + CAP_REGISTER_DIAMETER_BAND[1],
    register_boss_diameter_max: float = CAP_REGISTER_DIAMETER + CAP_REGISTER_DIAMETER_BAND[0],
    receiver_location_band: float = printed_band_mm(CAP_REGISTER_LOCATION_PLACES),
    cap_location_band: float = printed_band_mm(CAP_REGISTER_LOCATION_PLACES),
    receiver_pattern: tuple[tuple[float, float], ...] = CAP_REGISTER_CENTERS,
    cap_pattern: tuple[tuple[float, float], ...] = CAP_REGISTER_CENTERS,
    bearing_bore_diameter_max: float = 29.989,
    carriage_counterbore_diameter_max: float = 8.0 + printed_band_mm(2),
    block_edge_break_max: float = BLOCK_STOP_EDGE_BREAK_MAX,
    carrier_clearance: float = CARRIER_DIAMETRAL_CLEARANCE_MAX,
    carrier_engagement: float = CARRIER_ENGAGEMENT_MIN,
    top_running_gap: float = TOP_RUNNING_GAP[1],
) -> CaptureBounds:
    """Bound both captured directions without bearing axial-play authority.

    Averaging the two register centres cancels rigid cap rotation; the loose
    per-coordinate sum also bounds any orientation of each radial fit. Normal
    assembly is possible at the nominal cap transform even with independent
    location and ordinary angular errors. Contact with a screw during upset
    can only stop movement sooner; screw/shank friction is never credited.

    Opposite points on the fixed circle differ by D*tan(theta). The measured
    whole-circle chamber excess limits that difference. Both projected flange
    faces and the unbroken block/cap lands must still cover the circle.
    """
    if min(chamber_excess, stop_diameter, flange_diameter_min, carrier_engagement) <= 0.0:
        raise ValueError("capture sizes and engagement must be positive")
    if len(receiver_pattern) != 2 or len(cap_pattern) != 2:
        raise ValueError("both integral registers and receivers are required")
    pattern_offset = math.hypot(
        *(sum(point[axis] for point in receiver_pattern) / 2.0
          - sum(point[axis] for point in cap_pattern) / 2.0 for axis in (0, 1))
    )
    register_float = (register_bore_diameter_max - register_boss_diameter_min) / 2.0
    gamma = math.radians(GENERAL_ANGULAR_BAND_DEGREES)
    projection_band = printed_band_mm(CAP_REGISTER_PROJECTION_PLACES)
    depth_band = printed_band_mm(BLOCK_REGISTER_DEPTH_PLACES)
    projection_min = CAP_REGISTER_PROJECTION - projection_band
    projection_max = CAP_REGISTER_PROJECTION + projection_band
    depth_min = BLOCK_REGISTER_DEPTH - depth_band
    depth_max = BLOCK_REGISTER_DEPTH + depth_band
    boss_radius_max = register_boss_diameter_max / 2.0
    receiver_radius_max = register_bore_diameter_max / 2.0
    register_axis_allowance = (
        (projection_max + depth_max) * math.tan(gamma)
        + boss_radius_max * (1.0 / math.cos(gamma) - 1.0)
    )
    register_assembly = (
        (register_bore_diameter_min - register_boss_diameter_max) / 2.0
        - math.sqrt(2.0) * (receiver_location_band + cap_location_band)
        - register_axis_allowance - pattern_offset
    )
    register_bottom = (
        depth_min * math.cos(gamma) - receiver_radius_max * math.sin(gamma)
        - projection_max * math.cos(gamma) - boss_radius_max * math.sin(gamma)
    )
    register_engagement = (
        projection_min * math.cos(gamma)
        - boss_radius_max * math.sin(gamma) - CAP_REGISTER_END_CHAMFER_MAX
    )
    if min(register_float, register_assembly, register_bottom, register_engagement) <= 0.0:
        raise ValueError("integral register assembly, bottom clearance or engagement is lost")
    cap_shift = pattern_offset + math.sqrt(2.0) * (
        receiver_location_band + cap_location_band + register_float
    )
    tilt = math.atan(chamber_excess / stop_diameter)
    face_axis_angle = math.atan(PIN_STOP_FACE_VARIATION_MAX / PIN_STOP_FACE_MEASUREMENT_DIAMETER)
    pin_tilt = tilt + face_axis_angle
    # Enclose both finite faces, including their direct-inspection variation.
    flange_half_height = flange_thickness_max / 2.0 + (
        (PIN_FLANGE_DIA + PIN_FLANGE_DIA_BAND[0]) / 2.0 * math.tan(face_axis_angle)
    )
    flange_float = (
        pocket_diameter_max / 2.0 - flange_diameter_min / 2.0 * math.cos(pin_tilt)
        + flange_half_height * math.sin(pin_tilt)
    )
    projected_flat_radius = (
        flange_diameter_min / 2.0 - PIN_FLANGE_EDGE_BREAK_MAX
    ) * math.cos(pin_tilt) - flange_half_height * math.sin(pin_tilt)
    flange_margin = projected_flat_radius - cap_shift - flange_float - stop_diameter / 2.0
    floor_inner = stop_diameter / 2.0 - bearing_bore_diameter_max / 2.0 - block_edge_break_max
    station_stack = printed_band_mm(2) + printed_band_mm(3)
    nearest_carriage_bore = math.hypot(19.0 - station_stack, 13.0 - station_stack)
    floor_outer = nearest_carriage_bore - carriage_counterbore_diameter_max / 2.0 - stop_diameter / 2.0
    pocket_margin = pocket_diameter_min / 2.0 - cap_shift - stop_diameter / 2.0
    relative_center_offset = 2.0 * math.sqrt(2.0) * printed_band_mm(CAP_CENTER_LOCATION_PLACES)
    aperture_margin = (
        stop_diameter / 2.0 - cap_shift - relative_center_offset
        - (CAP_APERTURE_DIAMETER + CAP_APERTURE_BAND[0]) / 2.0
    )
    bore_axis_angle = math.atan(CARRIER_AXIS_DEVIATION_MAX / CARRIER_AXIS_MEASUREMENT_SPAN)
    carrier_fit_angle = math.atan(carrier_clearance / carrier_engagement)
    carrier_tilt = pin_tilt + bore_axis_angle + carrier_fit_angle
    normal_flange_angle = math.atan((PIN_LOWER_GAP[1] - PIN_LOWER_GAP[0]) / stop_diameter)
    normal_tilt = normal_flange_angle + face_axis_angle + bore_axis_angle + carrier_fit_angle
    seat_radius_max = (PIN_BOSS_DIAMETER + printed_band_mm(PIN_BOSS_DIAMETER_PLACES)) / 2.0
    max_cap_height = CAP_HEIGHT + printed_band_mm(CAP_HEIGHT_PLACES)
    aperture_clearance = (
        CAP_APERTURE_DIAMETER / 2.0 - seat_radius_max / math.cos(pin_tilt)
        - flange_float - max_cap_height * math.tan(pin_tilt) - relative_center_offset
    )
    min_seat_above_floor = (
        PIN_FLANGE_THICK - printed_band_mm(PIN_FLANGE_THICK_PLACES)
        + PIN_UPPER_BOSS_HEIGHT - printed_band_mm(PIN_UPPER_BOSS_PLACES)
    )
    edge_offset = printed_band_mm(CAP_OUTLINE_PLACES) + printed_band_mm(CAP_CENTER_LOCATION_PLACES)
    cap_radius_from_pin = math.hypot(
        CAP_WIDTH / 2.0 + edge_offset, CAP_LENGTH / 2.0 + edge_offset,
    ) + flange_float
    fit_z = carrier_clearance * math.tan(carrier_tilt)
    cap_clearance = (
        min_seat_above_floor * math.cos(pin_tilt) - max_cap_height
        - cap_radius_from_pin * math.tan(carrier_tilt) - fit_z
    )
    # Any local upper-stack point can change axial projection between the
    # accepted normal and upset poses; twice the full stack overbounds both.
    stack_height_max = (
        flange_thickness_max + PIN_UPPER_BOSS_HEIGHT + printed_band_mm(PIN_UPPER_BOSS_PLACES)
        + PIN_CARRIER_JOURNAL_LENGTH + printed_band_mm(2)
    )
    projection_change = 2.0 * stack_height_max * (1.0 - math.cos(carrier_tilt))
    support_lift = chamber_excess + top_running_gap / math.cos(carrier_tilt) + projection_change + fit_z
    support_drop = (
        chamber_excess + projection_change + fit_z
        + seat_radius_max * math.tan(bore_axis_angle + gamma + carrier_fit_angle)
    )
    available_penetration = CAP_BOLT_LENGTH_MIN - (
        max_cap_height - (CAP_COUNTERBORE_DEPTH - printed_band_mm(CAP_COUNTERBORE_DEPTH_PLACES))
    )
    margins = (
        flange_margin, floor_inner, floor_outer, pocket_margin, aperture_margin,
        aperture_clearance, cap_clearance,
    )
    if min(margins) <= 0.0:
        raise ValueError("opposing-stop contact or running clearance is lost")
    if available_penetration < CAP_MIN_COMPLETE_THREAD_ENGAGEMENT:
        raise ValueError("cap screw has insufficient available penetration for 1.5D complete threads")
    return CaptureBounds(
        cap_shift, flange_float, flange_margin, floor_inner, floor_outer,
        pocket_margin, aperture_margin, aperture_clearance, register_assembly,
        register_bottom, register_engagement, tilt, pin_tilt, carrier_tilt,
        normal_tilt, support_lift, support_drop, cap_clearance, available_penetration,
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
