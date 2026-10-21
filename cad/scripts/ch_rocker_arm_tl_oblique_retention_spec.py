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
PIN_UPPER_BOSS_HEIGHT = 12.35  # flange top to carrier seat; +12.5 mm work-height change
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
CAP_HEAD_SEATING_GAP_MAX = 0.05
CAP_BASE_SEATING_GAP_MAX = 0.05
# Analytic enclosures, NOT tighter machining tolerances. The computed motion
# must remain strictly inside both to close the connected-branch argument.
CAP_VERTICAL_MOTION_ENCLOSURE = 0.35
CAP_ROCK_ENCLOSURE_DEGREES = 1.0
CAP_FLOOR_WITNESS_X = 20.0
CAP_FLOOR_WITNESS_Y = 29.0
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
class _CapMotion:
    shift: float
    yaw: float
    floor_migration: float
    head_release: float
    roof_rise: float
    top_rise: float
    rock: float
    outline_margin: float
    floor_support_margin: float


def _cap_motion(
    register_float: float, receiver_band: float, cap_band: float,
    receiver_pattern: tuple[tuple[float, float], ...],
    cap_pattern: tuple[tuple[float, float], ...],
    stop_diameter: float, pocket_diameter_max: float, receiver_radius_max: float,
) -> _CapMotion:
    """One fixed manufactured cap moving in the SAME two receivers.

    For endpoint travel E, the coupled two-register rigid transform gives
    |u(p)| <= E*(|p-r+|+|p-r-|)/|r+-r-|. Fixed machining errors affect the
    lever/separation, not E twice. Projection residuals enclose cap rock.

    Each entry disk is smaller than the guaranteed flat head circle, hence
    removes less than a semicircle. Two cap poses share a solid-floor head
    point. Its fixed head height cancels; release is the measured initial
    gap plus material-coordinate migration times the CAP FLOOR's own slope,
    not a fresh 1-degree rotation of the carrier.
    """
    gamma = math.radians(GENERAL_ANGULAR_BAND_DEGREES)
    rock_limit = math.radians(CAP_ROCK_ENCLOSURE_DEGREES)
    centre_offset = math.hypot(
        *(sum(p[a] for p in receiver_pattern) / 2.0
          - sum(p[a] for p in cap_pattern) / 2.0 for a in (0, 1))
    )
    register_span = math.dist(cap_pattern[0], cap_pattern[1])
    register_radius = max(math.hypot(*point) for point in cap_pattern) + math.sqrt(2.0) * cap_band
    span_min = (register_span - 2.0 * math.sqrt(2.0) * cap_band) * math.cos(rock_limit)
    if span_min <= 0.0:
        raise ValueError("integral register separation is lost")
    shift = centre_offset + math.sqrt(2.0) * (receiver_band + cap_band + register_float)
    endpoint_offset = (
        math.sqrt(2.0) * (receiver_band + cap_band) + register_float + centre_offset
        + register_radius * (1.0 - math.cos(rock_limit))
    )
    sine = endpoint_offset / (register_span * math.cos(rock_limit))
    if sine >= 1.0:
        raise ValueError("integral registers do not bound cap yaw")
    yaw = 2.0 * math.asin(sine)
    head_z = CAP_HEIGHT + printed_band_mm(CAP_HEIGHT_PLACES) - (
        CAP_COUNTERBORE_DEPTH - printed_band_mm(CAP_COUNTERBORE_DEPTH_PLACES)
    ) + CAP_BASE_SEATING_GAP_MAX
    flat_radius = CAP_BOLT_HEAD_BEARING_DIAMETER_MIN / 2.0
    if (CAP_ENTRY_RELIEF_DIAMETER + CAP_ENTRY_RELIEF_BAND[0]) / 2.0 >= flat_radius:
        raise ValueError("entry relief removes the guaranteed flat head circle")
    bolt_band = printed_band_mm(CAP_BOLT_LOCATION_PLACES)
    head_error = bolt_band + CAP_BOLT_HEAD_ECCENTRICITY_MAX + head_z * math.tan(gamma)
    max_x = max(abs(x) for x, _ in CAP_BOLT_CENTERS) + head_error
    max_y = max(abs(y) for _, y in CAP_BOLT_CENTERS) + head_error
    edge_band = printed_band_mm(CAP_OUTLINE_PLACES) + printed_band_mm(CAP_CENTER_LOCATION_PLACES)
    outline_margin = min(
        CAP_WIDTH / 2.0 - edge_band - max_x - max_y * math.sin(yaw) - shift,
        CAP_LENGTH / 2.0 - edge_band - max_y - max_x * math.sin(yaw) - shift,
    ) - head_z * math.sin(rock_limit) - flat_radius
    if outline_margin <= 0.0:
        raise ValueError("guaranteed head circle can leave the cap floor outline")
    point_radius = (
        flat_radius + CAP_BOLT_HEAD_ECCENTRICITY_MAX + math.sqrt(2.0) * bolt_band
        + head_z * math.tan(gamma)
    )
    coefficient = max(
        sum(math.dist(point, register) for register in receiver_pattern)
        + 2.0 * (point_radius + math.sqrt(2.0) * receiver_band + register_float)
        for point in CAP_BOLT_CENTERS
    ) / span_min
    endpoint_motion = 2.0 * register_float + 2.0 * register_radius * (1.0 - math.cos(rock_limit))
    contact_radius = max(math.hypot(*p) for p in CAP_BOLT_CENTERS) + point_radius + shift
    migration = (
        endpoint_motion * coefficient + 2.0 * head_z * math.sin(rock_limit)
        + 2.0 * contact_radius * (1.0 - math.cos(rock_limit))
    )
    release = (
        CAP_BASE_SEATING_GAP_MAX + CAP_HEAD_SEATING_GAP_MAX
        + migration * math.tan(gamma)
        + 2.0 * (CAP_HEIGHT + printed_band_mm(CAP_HEIGHT_PLACES)) * (1.0 - math.cos(rock_limit))
    )
    # Common head points can lie anywhere on each guaranteed flat circle.
    # Their convex hull contains this conservative fixed-world rectangle.
    bx = min(abs(x) for x, _ in CAP_BOLT_CENTERS) - head_error - flat_radius
    by = min(abs(y) for _, y in CAP_BOLT_CENTERS) - head_error - flat_radius
    if min(bx, by) <= 0.0:
        raise ValueError("head-floor support polygon is lost")
    # Fixed-world floor witnesses remain solid in cap AND block in every
    # enclosed pose. The stepped wing, pocket and through-hole checks below
    # prevent treating a hole or an overhang as a downward support.
    fx, fy = CAP_FLOOR_WITNESS_X, CAP_FLOOR_WITNESS_Y
    hole_shift = shift + 2.0 * max(math.hypot(*p) for p in CAP_BOLT_CENTERS) * math.sin(yaw / 2.0)
    floor_support = min(
        fx - pocket_diameter_max / 2.0 - shift,
        trammel.PIN_OFFSET - BLOCK_SPINDLE_END - fx - printed_band_mm(1) - printed_band_mm(2),
        BLOCK_WING_END - trammel.PIN_OFFSET - fx - printed_band_mm(1) - printed_band_mm(2),
        BLOCK_WING_HALF_WIDTH - fy - printed_band_mm(1) - printed_band_mm(2),
        # Initial base-gap QA extends affinely across the mounting footprint;
        # every guaranteed head-circle point must remain within its outer hull.
        trammel.PIN_OFFSET - BLOCK_SPINDLE_END - max_x - flat_radius
        - printed_band_mm(1) - printed_band_mm(2),
        BLOCK_WING_END - trammel.PIN_OFFSET - max_x - flat_radius
        - printed_band_mm(1) - printed_band_mm(2),
        BLOCK_WING_HALF_WIDTH - max_y - flat_radius - printed_band_mm(1) - printed_band_mm(2),
        min(
            math.dist(witness, point) for witness in ((fx, 0.0), (-fx, 0.0), (0.0, fy), (0.0, -fy))
            for point in receiver_pattern
        ) - math.sqrt(2.0) * receiver_band
        - receiver_radius_max
        - (BLOCK_REGISTER_DEPTH + printed_band_mm(BLOCK_REGISTER_DEPTH_PLACES)) * math.tan(gamma),
        CAP_WIDTH / 2.0 - edge_band - max(fx, fy * math.sin(yaw)) - shift,
        CAP_LENGTH / 2.0 - edge_band - max(fy, fx * math.sin(yaw)) - shift,
        min(
            math.dist(witness, point) for witness in ((fx, 0.0), (-fx, 0.0), (0.0, fy), (0.0, -fy))
            for point in CAP_BOLT_CENTERS
        ) - hole_shift - (CAP_BOLT_CLEARANCE_DIAMETER + CAP_BOLT_CLEARANCE_BAND[0]) / 2.0,
        CAP_HEIGHT - printed_band_mm(CAP_HEIGHT_PLACES)
        - CAP_COUNTERBORE_DEPTH - printed_band_mm(CAP_COUNTERBORE_DEPTH_PLACES)
        - CAP_ENTRY_RELIEF_DEPTH - printed_band_mm(CAP_ENTRY_RELIEF_DEPTH_PLACES),
    )
    if floor_support <= 0.0:
        raise ValueError("cap rocking proof loses a solid floor witness")
    slopes = ((0.0, 0.0), (1.0 / fx, 0.0), (0.0, 1.0 / fy), (1.0 / fx, 1.0 / fy))

    def rise_gain(x: float, y: float, *, circle: bool = False) -> float:
        # Linear-fractional (circle: quasiconvex) maxima occur at these four
        # vertices. Nonpenetration at the four floor witnesses supplies the
        # lower constraints; head points supply the upper constraints.
        return max(
            (1.0 + (x * math.hypot(sx, sy) if circle else x * sx + y * sy))
            / (1.0 + bx * sx + by * sy) for sx, sy in slopes
        )

    rock = math.atan(max(
        release * math.hypot(sx, sy) / (1.0 + bx * sx + by * sy) for sx, sy in slopes
    ))
    roof_rise = release * rise_gain(stop_diameter / 2.0, 0.0, circle=True)
    # Absolute height above the block plane. Initial base gap is separately
    # budgeted from underhead gap. Adding this to a chamber measured in the
    # accepted normal pose deliberately overbounds the initial base allowance.
    global_x = shift + CAP_WIDTH / 2.0 + edge_band + (
        CAP_LENGTH / 2.0 + edge_band
    ) * math.sin(yaw) + (CAP_HEIGHT + printed_band_mm(CAP_HEIGHT_PLACES)) * math.sin(rock)
    global_y = shift + CAP_LENGTH / 2.0 + edge_band + (
        CAP_WIDTH / 2.0 + edge_band
    ) * math.sin(yaw) + (CAP_HEIGHT + printed_band_mm(CAP_HEIGHT_PLACES)) * math.sin(rock)
    top_rise = release * rise_gain(global_x, global_y)
    bottom_drop = release * max(
        max(0.0, global_x * sx + global_y * sy - 1.0)
        / (1.0 + bx * sx + by * sy) for sx, sy in slopes
    ) + 2.0 * (CAP_HEIGHT + printed_band_mm(CAP_HEIGHT_PLACES)) * (1.0 - math.cos(rock))
    if max(top_rise, roof_rise, bottom_drop) >= CAP_VERTICAL_MOTION_ENCLOSURE or rock >= rock_limit:
        raise ValueError("cap motion escapes its connected-branch enclosure")
    return _CapMotion(shift, yaw, migration, release, roof_rise, top_rise, rock, outline_margin, floor_support)


@dataclass(frozen=True)
class CaptureBounds:
    """Intact rigid dimensions/angles, not strength or machine clearance."""

    cap_lateral_shift: float
    cap_yaw: float
    cap_floor_migration: float
    cap_head_release: float
    cap_roof_rise: float
    cap_top_rise: float
    cap_tilt: float
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
    carrier_motion_tilt: float
    support_lift: float
    support_drop: float
    cap_running_clearance: float
    screw_available_penetration: float

    @property
    def carrier_slope_change(self) -> float:
        """Either-sign rise relative to an actual accepted normal pose."""
        return math.tan(self.carrier_motion_tilt)


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
    pattern_mismatch = max(
        math.dist(receiver, cap) for receiver, cap in zip(receiver_pattern, cap_pattern, strict=True)
    )
    gamma = math.radians(GENERAL_ANGULAR_BAND_DEGREES)
    rock_limit = math.radians(CAP_ROCK_ENCLOSURE_DEGREES)
    register_float = (
        register_bore_diameter_max / (2.0 * math.cos(gamma)) - register_boss_diameter_min / 2.0
        + CAP_VERTICAL_MOTION_ENCLOSURE * math.tan(gamma + rock_limit)
    )
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
        - register_axis_allowance - pattern_mismatch
    )
    register_bottom = (
        depth_min * math.cos(gamma) - receiver_radius_max * math.sin(gamma)
        - projection_max * math.cos(gamma + rock_limit) - boss_radius_max * math.sin(gamma + rock_limit)
        - CAP_VERTICAL_MOTION_ENCLOSURE
    )
    register_engagement = (
        projection_min * math.cos(gamma + rock_limit)
        - boss_radius_max * math.sin(gamma + rock_limit) - CAP_REGISTER_END_CHAMFER_MAX
        - CAP_VERTICAL_MOTION_ENCLOSURE
    )
    if min(register_float, register_assembly, register_bottom, register_engagement) <= 0.0:
        raise ValueError("integral register assembly, bottom clearance or engagement is lost")
    cap_motion = _cap_motion(
        register_float, receiver_location_band, cap_location_band,
        receiver_pattern, cap_pattern, stop_diameter, pocket_diameter_max, receiver_radius_max,
    )
    cap_shift = cap_motion.shift
    tilt = math.atan((chamber_excess + cap_motion.roof_rise) / stop_diameter)
    face_axis_angle = math.atan(PIN_STOP_FACE_VARIATION_MAX / PIN_STOP_FACE_MEASUREMENT_DIAMETER)
    pin_tilt = tilt + face_axis_angle
    # Enclose both finite faces, including their direct-inspection variation.
    flange_half_height = flange_thickness_max / 2.0 + (
        (PIN_FLANGE_DIA + PIN_FLANGE_DIA_BAND[0]) / 2.0 * math.tan(face_axis_angle)
    )
    pocket_depth_max = flange_thickness_max + chamber_excess
    roof_shift = pocket_depth_max * math.sin(cap_motion.rock)
    flange_float = (
        pocket_diameter_max / 2.0 + roof_shift - flange_diameter_min / 2.0 * math.cos(pin_tilt)
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
    pocket_margin = (
        pocket_diameter_min / 2.0 * math.cos(cap_motion.rock)
        - cap_shift - roof_shift - stop_diameter / 2.0
    )
    relative_center_offset = 2.0 * math.sqrt(2.0) * printed_band_mm(CAP_CENTER_LOCATION_PLACES)
    aperture_margin = (
        stop_diameter / 2.0 - cap_shift - roof_shift - relative_center_offset
        - (CAP_APERTURE_DIAMETER + CAP_APERTURE_BAND[0]) / 2.0
    )
    bore_axis_angle = math.atan(CARRIER_AXIS_DEVIATION_MAX / CARRIER_AXIS_MEASUREMENT_SPAN)
    carrier_fit_angle = math.atan(carrier_clearance / carrier_engagement)
    carrier_tilt = pin_tilt + bore_axis_angle + carrier_fit_angle
    normal_flange_angle = math.atan((PIN_LOWER_GAP[1] - PIN_LOWER_GAP[0]) / stop_diameter)
    # The carrier's manufactured bore-to-bottom bias is fixed in the SAME
    # body and cancels in relative motion. Pin face bias can reverse with free
    # pin clocking; H7/h6 rocking is reversible, so both retain two occurrences.
    motion_tilt = tilt + normal_flange_angle + 2.0 * face_axis_angle + 2.0 * carrier_fit_angle
    seat_radius_max = (PIN_BOSS_DIAMETER + printed_band_mm(PIN_BOSS_DIAMETER_PLACES)) / 2.0
    max_cap_height = CAP_HEIGHT + printed_band_mm(CAP_HEIGHT_PLACES)
    aperture_clearance = (
        CAP_APERTURE_DIAMETER / 2.0 - seat_radius_max / math.cos(pin_tilt)
        - flange_float - (max_cap_height + cap_motion.top_rise) * math.tan(pin_tilt) - relative_center_offset
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
    # A tilted lower flange cannot have its centre simultaneously on the
    # floor: at the moving pin centre q it must rise at least
    # (Rstop-|q|)*tan(theta_face). The edge-loss and this rise use the SAME
    # angle; their derivative is negative, so the maximum angle is worst.
    floor_imposed_rise = (
        stop_diameter / 2.0 - cap_shift - flange_float
    ) * math.tan(max(0.0, pin_tilt - face_axis_angle))
    cap_clearance = (
        min_seat_above_floor * math.cos(pin_tilt) + floor_imposed_rise
        - max_cap_height - cap_motion.top_rise
        - cap_radius_from_pin * math.tan(carrier_tilt) - fit_z
    )
    # Any local upper-stack point can change axial projection between the
    # accepted normal and upset poses; twice the full stack overbounds both.
    stack_height_max = (
        flange_thickness_max + PIN_UPPER_BOSS_HEIGHT + printed_band_mm(PIN_UPPER_BOSS_PLACES)
        + PIN_CARRIER_JOURNAL_LENGTH + printed_band_mm(2)
    )
    projection_change = 2.0 * stack_height_max * (1.0 - math.cos(carrier_tilt))
    support_lift = (
        chamber_excess + cap_motion.roof_rise + top_running_gap / math.cos(carrier_tilt)
        + projection_change + fit_z
    )
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
        cap_lateral_shift=cap_shift, cap_yaw=cap_motion.yaw,
        cap_floor_migration=cap_motion.floor_migration, cap_head_release=cap_motion.head_release,
        cap_roof_rise=cap_motion.roof_rise, cap_top_rise=cap_motion.top_rise, cap_tilt=cap_motion.rock,
        flange_lateral_shift=flange_float, flange_contact_margin=flange_margin,
        floor_inner_margin=floor_inner, floor_counterbore_margin=floor_outer,
        cap_pocket_margin=pocket_margin, cap_aperture_margin=aperture_margin,
        pin_aperture_clearance=aperture_clearance, register_assembly_clearance=register_assembly,
        register_bottom_clearance=register_bottom, register_engagement=register_engagement,
        flange_tilt=tilt, pin_tilt=pin_tilt, carrier_tilt=carrier_tilt,
        carrier_motion_tilt=motion_tilt, support_lift=support_lift, support_drop=support_drop,
        cap_running_clearance=cap_clearance, screw_available_penetration=available_penetration,
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
    end_slope = min(bound.carrier_slope_change, (bound.support_lift + bound.support_drop) / (b[0] - a[0]))
    return bound.support_lift + outboard * end_slope + abs(y - a[1]) * bound.carrier_slope_change


# Nominal only: limits are reported separately from actual manufactured bands.
PIN_PROJECTION_ABOVE_WORK_NOMINAL = (
    PIN_CARRIER_JOURNAL_LENGTH - trammel.CARRIER_THICK - trammel.RISER_THICK - trammel.STRAP_THICK
)
