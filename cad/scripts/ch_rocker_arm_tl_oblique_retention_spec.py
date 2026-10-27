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

import _config
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
# C2 independently accepts both normal rim gaps, as well as chamber excess.
PIN_LOWER_GAP = (0.10, 0.15)
PIN_UPPER_GAP = (0.10, 0.15)
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
BLOCK_WING_AXIS_REACH = 20.60
BLOCK_WING_AXIS_REACH_PLACES = 2
BLOCK_WING_END = trammel.PIN_OFFSET + BLOCK_WING_AXIS_REACH
BLOCK_WING_HALF_WIDTH = 36.0
WING_BRACKET_CLEARANCE_MIN = 0.50
BLOCK_STOP_EDGE_BREAK_MAX = 0.25
CAP_WIDTH = 50.0  # X
CAP_LENGTH = 86.0
CAP_HEIGHT = 11.60
CAP_HEIGHT_PLACES = 2
CAP_OUTLINE_PLACES = 1
CAP_CENTER_LOCATION_PLACES = 2
CAP_POCKET_DIAMETER = 36.60
CAP_POCKET_DIAMETER_BAND = (0.10, -0.10)
CAP_POCKET_CORNER_RADIUS_MAX = 0.20  # local floor/wall finish limit; not a modeled fillet
CAP_POCKET_DEPTH = 3.30  # REF; face to actual flange and chamber-excess requirement
CAP_CHAMBER_EXCESS = (0.20, 0.30)
CAP_APERTURE_DIAMETER = 19.0
CAP_APERTURE_BAND = (printed_band_mm(2), -printed_band_mm(2))
CAP_BOLT_X_OFFSETS = (-13.25, 13.25)
CAP_BOLT_Y_OFFSETS = (-28.5, 28.5)
CAP_BOLT_CENTERS = tuple((x, y) for x in CAP_BOLT_X_OFFSETS for y in CAP_BOLT_Y_OFFSETS)
CAP_BOLT_LOCATION_PLACES = 3
CAP_BOLT_CLEARANCE_DIAMETER = 10.00
CAP_BOLT_CLEARANCE_BAND = (0.10, 0.0)
CAP_COUNTERBORE_DIAMETER = 21.00
CAP_COUNTERBORE_DIAMETER_PLACES = 2
CAP_COUNTERBORE_DEPTH = 8.40  # REF; fit each actual seated NAS head
CAP_HEAD_RECESS_MIN = 0.50
CAP_HEAD_RECESS_MAX = 0.60
CAP_COUNTERBORE_FLOOR_MIN = 2.00  # actual minimum over floor AND outward mouth
CAP_WIRE_CHANNEL_WIDTH = 8.00
CAP_WIRE_CHANNEL_DEPTH = 7.00
CAP_WIRE_CHANNEL_PLACES = 2
CAP_REGISTER_CENTERS = ((-2.5, -24.0), (2.5, 24.0))
CAP_REGISTER_LOCATION_PLACES = 3
CAP_REGISTER_DIAMETER = 6.0
CAP_REGISTER_DIAMETER_BAND = (0.10, -0.10)
CAP_REGISTER_PROJECTION = 1.000
CAP_REGISTER_PROJECTION_PLACES = 3
# cad/config/title_block.yaml edge_break.chamfer_max_mm governs the free end.
# The capture proof subtracts that full chamfer from straight engagement.
CAP_REGISTER_END_CHAMFER_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])
# The boss root fillet is tangent to the seating plane, so it meets the
# receiver's sharp mouth (its edge break is a MAX only, never credited) at
# boss radius + root radius. The title block's R1.0 inside-corner default
# would not enter the Ø7.20 receiver, so the cap prints this tighter maximum.
# It is charged in full to radial register assembly and, past the vertical
# motion enclosure, to straight engagement. The native root stays sharp.
CAP_REGISTER_ROOT_RADIUS_MAX = 0.12
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
CAP_BOLT_DIAMETER = hardware.SCREW_MAJOR_DIA_MAX
CAP_BOLT_PITCH = hardware.SCREW_DIMS.pitch
CAP_MIN_COMPLETE_THREAD_ENGAGEMENT = 1.5 * CAP_BOLT_DIAMETER
CAP_SEATING_TORQUE_NM = 0.50
CAP_SEATING_TORQUE_BAND_NM = 0.05
CAP_HEAD_SEATING_GAP_MAX = 0.05
CAP_BASE_SEATING_GAP_MAX = 0.05
# The block's THRU tap mouth carries only the title-block edge break MAX.
BLOCK_TAP_MOUTH_BREAK_MAX = float(_config.title_block("edge_break")["chamfer_max_mm"])


def cap_screw_complete_engagement_estimate() -> float:
    """Estimated worst-case complete-thread overlap of a cap screw in its tap, mm.

    An ESTIMATE, conditional on the hardware spec's ASME B18.3-convention
    thread runouts (no NAS or supplier limit exists for a screw this short).
    Along the actual tap axis from the block top: the screw's complete
    threads run from SCREW_COMPLETE_THREAD_FROM_HEAD_MAX under its head to
    SCREW_POINT_INCOMPLETE_MAX short of its point; the block's start below
    the tap mouth's title-block break plus one partial thread. The shortest
    screw pairs with the highest seated head for the deep end and the lowest
    seat for the shallow end. Even this estimate falls short of
    CAP_MIN_COMPLETE_THREAD_ENGAGEMENT: owner minor exception RV-04 (owner
    ruling 2026-10-27) accepts the shortfall with no assembly measurement.
    """
    gamma = math.radians(GENERAL_ANGULAR_BAND_DEGREES)
    fitted = fitted_counterbore_bounds()
    deep = (
        CAP_BOLT_LENGTH_MIN - hardware.SCREW_POINT_INCOMPLETE_MAX
        - fitted.head_seat_max / math.cos(gamma)
    )
    shallow = max(
        BLOCK_TAP_MOUTH_BREAK_MAX / math.cos(gamma) + CAP_BOLT_PITCH,
        hardware.SCREW_COMPLETE_THREAD_FROM_HEAD_MAX - fitted.head_seat_min,
    )
    return deep - shallow


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
# Installed qualification, not new manufactured-part tolerances. The travel
# is measured relative to the pin/clevis at primary take-up; secondary keeper
# features must remain clear rather than becoming an unintended uplift stop.
TOP_PRIMARY_RELATIVE_TRAVEL_MAX = TOP_RUNNING_GAP[1]
TOP_SECONDARY_CLEARANCE_MIN = 0.50
PIN_TIP_CARRIAGE_CLEARANCE_MIN = 0.50
TOP_WASHER_NOMINAL_THICKNESS = (
    PIN_CROSS_HOLE_FROM_SEAT + PIN_CROSS_HOLE_DIA / 2.0
    - PIN_CLEVIS_NOMINAL_DIAMETER - CARRIER_THICKNESS - sum(TOP_RUNNING_GAP) / 2.0
)
STOP_CONTACT_DIAMETER = 31.5


@dataclass(frozen=True)
class FittedCounterboreBounds:
    """Geometric enclosures conditional on actual fitted-head acceptance."""

    head_axis_height_min: float
    head_axis_height_max: float
    head_seat_min: float
    head_seat_max: float
    head_point_height_max: float
    head_top_height_max: float
    depth_at_head_min: float
    depth_at_head_max: float
    parallel_cut_floor_min: float


def initial_cap_tilt() -> float:
    return math.atan(math.hypot(
        CAP_BASE_SEATING_GAP_MAX / (2.0 * CAP_FLOOR_WITNESS_X),
        CAP_BASE_SEATING_GAP_MAX / (2.0 * CAP_FLOOR_WITNESS_Y),
    ))


def fitted_counterbore_bounds(*, height: float | None = None) -> FittedCounterboreBounds:
    """Bound matched heads without turning the REF depth into a tolerance.

    Installed recess is measured normal to the actual top over the WHOLE
    head, after C3 seating. The actual floor, including each full-width
    mouth, must retain CAP_COUNTERBORE_FLOOR_MIN. A floor parallel to the
    actual top constructively fits the worst hardware; incompatible actual
    floor/head slopes still require rejection or remachining, not forcing.

    NAS H is axis-parallel. Its inclined bearing-plane reference need not
    be guessed: moving any reference within the head envelope to the axis
    costs at most radius*tan(bearing angle). This is a datum conversion,
    not an additional manufactured tolerance. cap_screw_complete_engagement_estimate
    bounds the complete-thread overlap from these seat heights.
    """
    body_height = CAP_HEIGHT if height is None else height
    inputs = (
        body_height, CAP_HEAD_RECESS_MIN, CAP_HEAD_RECESS_MAX,
        CAP_COUNTERBORE_FLOOR_MIN, CAP_BASE_SEATING_GAP_MAX,
        CAP_HEAD_SEATING_GAP_MAX, GENERAL_ANGULAR_BAND_DEGREES,
        CAP_BOLT_BEARING_ANGLE_MAX_DEGREES,
    )
    if not all(math.isfinite(value) for value in inputs):
        raise ValueError("fitted counterbore inputs must be finite")
    if min(inputs[1:]) < 0.0 or CAP_HEAD_RECESS_MIN > CAP_HEAD_RECESS_MAX:
        raise ValueError("fitted counterbore recess, floor and gaps are invalid")
    gamma = math.radians(GENERAL_ANGULAR_BAND_DEGREES)
    beta = math.radians(CAP_BOLT_BEARING_ANGLE_MAX_DEGREES)
    initial_tilt = initial_cap_tilt()
    roof_angle = gamma + initial_tilt
    head_roof_angle = gamma + roof_angle
    if head_roof_angle + beta >= math.pi / 2.0:
        raise ValueError("fitted head angular enclosure is outside its valid domain")
    radius = CAP_BOLT_HEAD_DIAMETER_MAX / 2.0 + CAP_BOLT_HEAD_ECCENTRICITY_MAX
    conversion = radius * math.tan(beta)
    axis_height_min = hardware.SCREW_HEAD_HEIGHT_MIN - conversion
    axis_height_max = CAP_BOLT_HEAD_HEIGHT_MAX + conversion
    if axis_height_min <= 0.0:
        raise ValueError("fitted head has no positive axial height")
    support_min = axis_height_min * math.cos(head_roof_angle)
    support_max = axis_height_max + radius * math.sin(head_roof_angle)
    height_min = body_height - printed_band_mm(CAP_HEIGHT_PLACES)
    height_max = body_height + printed_band_mm(CAP_HEIGHT_PLACES)
    depth_min = CAP_HEAD_RECESS_MIN + support_min
    depth_max = CAP_HEAD_RECESS_MAX + support_max + CAP_HEAD_SEATING_GAP_MAX
    parallel_floor = height_min - depth_max / math.cos(gamma)
    if parallel_floor < CAP_COUNTERBORE_FLOOR_MIN:
        raise ValueError("fitted counterbore has no whole-floor machining window")
    # The head-axis intersection is inside the convex hull of the qualified
    # accessible bearing footprint. Recess therefore bounds its distance to
    # the roof. The socket void does not invalidate the axis-containing convex
    # hull of the flat head-top material used for the top-plane witness.
    flat_radius = CAP_BOLT_HEAD_BEARING_DIAMETER_MIN / 2.0
    point_separation = support_min - (
        flat_radius + CAP_BOLT_HEAD_ECCENTRICITY_MAX / math.cos(beta)
    ) * math.sin(head_roof_angle + beta)
    # H is mounting-normal thickness; convert it before subtracting actual
    # roof-normal recess/support. Dividing those positive distances by the
    # roof's world-Z cosine would only lower the point, so omit that credit.
    top_height = CAP_BASE_SEATING_GAP_MAX + height_max / math.cos(initial_tilt)
    seat_max = top_height - CAP_HEAD_RECESS_MIN - support_min
    point_max = top_height - CAP_HEAD_RECESS_MIN - point_separation
    seat_min = height_min - (CAP_HEAD_RECESS_MAX + support_max) / math.cos(roof_angle)
    if min(seat_min, seat_max, point_max) <= 0.0:
        raise ValueError("fitted head seating enclosure crosses the block plane")
    return FittedCounterboreBounds(
        head_axis_height_min=axis_height_min, head_axis_height_max=axis_height_max,
        head_seat_min=seat_min, head_seat_max=seat_max,
        head_point_height_max=point_max,
        head_top_height_max=seat_max + axis_height_max + radius * math.sin(gamma),
        depth_at_head_min=depth_min, depth_at_head_max=depth_max,
        parallel_cut_floor_min=parallel_floor,
    )


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
    head_recess: float
    register_endpoint_offset: float
    register_span_min: float
    register_endpoint_motion: float
    head_floor_x_margin: float
    head_floor_y_margin: float


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

    Each through-hole disk is smaller than the guaranteed flat head circle,
    hence removes less than a semicircle. Two cap poses share a solid-floor
    head point. Its fixed head height cancels; release is the measured initial
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
    fitted = fitted_counterbore_bounds()
    head_z = fitted.head_point_height_max
    flat_radius = CAP_BOLT_HEAD_BEARING_DIAMETER_MIN / 2.0
    bearing_angle = math.radians(CAP_BOLT_BEARING_ANGLE_MAX_DEGREES)
    hole_head_angle = 2.0 * gamma + rock_limit + bearing_angle
    if min(gamma, rock_limit, bearing_angle) < 0.0 or not 0.0 <= hole_head_angle < math.pi / 2.0:
        raise ValueError("through-bore/head angular enclosure is outside its valid domain")
    # On the fixed head plane the angled through cylinder is an ellipse.
    # Enclose it by its major-radius disk. Each of two cap poses then removes
    # less than a semicircle of the guaranteed flat circle, leaving a common
    # head point. The full flat_radius still conservatively bounds every
    # possible world-point coordinate and its migration below.
    hole_radius = (CAP_BOLT_CLEARANCE_DIAMETER + CAP_BOLT_CLEARANCE_BAND[0]) / (
        2.0 * math.cos(hole_head_angle)
    )
    if hole_radius >= flat_radius:
        raise ValueError("through bore removes the guaranteed flat head circle")
    # The fitted-depth window also uses the head-axis seating gap. The
    # retained outer-circle arc has a convex hull containing this central
    # disk, even at the worst bore offset. Keep the eccentric thread-axis
    # intersection inside it; a common rim point alone is not sufficient.
    axis_offset = CAP_BOLT_HEAD_ECCENTRICITY_MAX / math.cos(bearing_angle)
    if hole_radius * hole_radius + axis_offset * axis_offset >= flat_radius * flat_radius:
        raise ValueError("through bore removes the qualified thread-axis seating footprint")
    bolt_band = printed_band_mm(CAP_BOLT_LOCATION_PLACES)
    head_error = bolt_band + CAP_BOLT_HEAD_ECCENTRICITY_MAX + head_z * math.tan(gamma)
    max_x = max(abs(x) for x, _ in CAP_BOLT_CENTERS) + head_error
    max_y = max(abs(y) for _, y in CAP_BOLT_CENTERS) + head_error
    edge_band = printed_band_mm(CAP_OUTLINE_PLACES) + printed_band_mm(CAP_CENTER_LOCATION_PLACES)
    head_floor_x_margin = (
        CAP_WIDTH / 2.0 - edge_band - max_x - max_y * math.sin(yaw)
        - shift - head_z * math.sin(rock_limit) - flat_radius
    )
    head_floor_y_margin = (
        CAP_LENGTH / 2.0 - edge_band - max_y - max_x * math.sin(yaw)
        - shift - head_z * math.sin(rock_limit) - flat_radius
    )
    outline_margin = min(head_floor_x_margin, head_floor_y_margin)
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
        BLOCK_WING_AXIS_REACH - fx - printed_band_mm(BLOCK_WING_AXIS_REACH_PLACES),
        BLOCK_WING_HALF_WIDTH - fy - printed_band_mm(1) - printed_band_mm(2),
        # Initial base-gap QA extends affinely across the mounting footprint;
        # every guaranteed head-circle point must remain within its outer hull.
        trammel.PIN_OFFSET - BLOCK_SPINDLE_END - max_x - flat_radius
        - printed_band_mm(1) - printed_band_mm(2),
        BLOCK_WING_AXIS_REACH - max_x - flat_radius
        - printed_band_mm(BLOCK_WING_AXIS_REACH_PLACES),
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
        CAP_COUNTERBORE_FLOOR_MIN,
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
    # Recess is accepted over the actual WHOLE head in the normal pose.
    # Track fixed head-top points against the SAME moving roof; do not charge
    # NAS height/projection again as an independent recess loss. The finite
    # head still needs its full 3-D enclosure for migration and LP support.
    head_radius = CAP_BOLT_HEAD_DIAMETER_MAX / 2.0
    head_top_z = fitted.head_top_height_max
    top_error = bolt_band + CAP_BOLT_HEAD_ECCENTRICITY_MAX + head_top_z * math.tan(gamma)
    top_x = max(abs(x) for x, _ in CAP_BOLT_CENTERS) + top_error + head_radius
    top_y = max(abs(y) for _, y in CAP_BOLT_CENTERS) + top_error + head_radius
    top_point_radius = (
        head_radius + CAP_BOLT_HEAD_ECCENTRICITY_MAX + math.sqrt(2.0) * bolt_band
        + head_top_z * math.tan(gamma)
    )
    top_coefficient = max(
        sum(math.dist(point, register) for register in receiver_pattern)
        + 2.0 * (top_point_radius + math.sqrt(2.0) * receiver_band + register_float)
        for point in CAP_BOLT_CENTERS
    ) / span_min
    top_contact_radius = max(math.hypot(*p) for p in CAP_BOLT_CENTERS) + top_point_radius + shift
    top_migration = (
        endpoint_motion * top_coefficient + 2.0 * head_top_z * math.sin(rock_limit)
        + 2.0 * top_contact_radius * (1.0 - math.cos(rock_limit))
    )
    top_descent = release * max(
        max(0.0, top_x * sx + top_y * sy - 1.0) / (1.0 + bx * sx + by * sy)
        for sx, sy in slopes
    )
    initial_tilt = initial_cap_tilt()
    radial_envelope = head_radius + CAP_BOLT_HEAD_ECCENTRICITY_MAX
    initial_base_at_rim = CAP_BASE_SEATING_GAP_MAX + (
        radial_envelope + fitted.head_axis_height_max * math.sin(gamma)
    ) * math.tan(initial_tilt)
    if (
        fitted.head_seat_min + fitted.head_axis_height_min * math.cos(gamma)
        - radial_envelope * math.sin(gamma)
    ) <= CAP_VERTICAL_MOTION_ENCLOSURE:
        raise ValueError("fixed head-top enclosure crosses the moving cap base")
    # In material coordinates d=c*(h(u)-z), c=cos(actual roof slope).
    # The same roof intercept cancels. Since each head-top point remains
    # above the cap base, the current-pose cosine term is favourable. Initial
    # base QA is extended from the qualified head-axis centre to its rim.
    roof_loss = (
        top_migration * math.sin(gamma) + initial_base_at_rim + top_descent
        + head_top_z * (1.0 - math.cos(initial_tilt))
    )
    head_recess = CAP_HEAD_RECESS_MIN - roof_loss
    if head_recess <= 0.0:
        raise ValueError("captured cap motion loses the fitted whole-head recess")
    return _CapMotion(
        shift, yaw, migration, release, roof_rise, top_rise, rock,
        outline_margin, floor_support, head_recess, endpoint_offset, span_min, endpoint_motion,
        head_floor_x_margin, head_floor_y_margin,
    )


@dataclass(frozen=True)
class CaptureBounds:
    """Intact rigid dimensions/angles, not strength or machine clearance."""

    cap_lateral_shift: float
    cap_yaw: float
    cap_register_endpoint_offset: float
    cap_register_span_min: float
    cap_register_endpoint_motion: float
    cap_head_floor_x_margin: float
    cap_head_floor_y_margin: float
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
    cap_head_running_clearance: float
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
    pocket_corner_radius_max: float = CAP_POCKET_CORNER_RADIUS_MAX,
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
    if pocket_corner_radius_max < 0.0:
        raise ValueError("cap chamber inside-corner maximum cannot be negative")
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
        - register_axis_allowance - pattern_mismatch - CAP_REGISTER_ROOT_RADIUS_MAX
    )
    register_bottom = (
        depth_min * math.cos(gamma) - receiver_radius_max * math.sin(gamma)
        - projection_max * math.cos(gamma + rock_limit) - boss_radius_max * math.sin(gamma + rock_limit)
        - CAP_VERTICAL_MOTION_ENCLOSURE
    )
    # Straight land in the receiver loses the larger of the cap's lift and
    # the root fillet; the fillet sits above the mouth once lifted that far.
    register_engagement = (
        projection_min * math.cos(gamma + rock_limit)
        - boss_radius_max * math.sin(gamma + rock_limit) - CAP_REGISTER_END_CHAMFER_MAX
        - max(CAP_VERTICAL_MOTION_ENCLOSURE, CAP_REGISTER_ROOT_RADIUS_MAX)
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
    # The peripheral corner may stop upset motion sooner. Reserve its entire
    # radius so the FULL fixed stop circle still contacts a flat roof, rather
    # than crediting an unmodeled concave corner as a horizontal stop.
    pocket_margin = (
        pocket_diameter_min / 2.0 * math.cos(cap_motion.rock)
        - cap_shift - roof_shift - stop_diameter / 2.0 - pocket_corner_radius_max
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
        (CAP_APERTURE_DIAMETER + CAP_APERTURE_BAND[1]) / 2.0 - seat_radius_max / math.cos(pin_tilt)
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
    # This is only available AXIAL penetration (a world-Z head height is not
    # an axial distance when the tap axis is inclined). Complete-thread
    # overlap is shorter: cap_screw_complete_engagement_estimate.
    available_penetration = (
        CAP_BOLT_LENGTH_MIN - fitted_counterbore_bounds().head_seat_max / math.cos(gamma)
    )
    margins = (
        flange_margin, floor_inner, floor_outer, pocket_margin, aperture_margin,
        aperture_clearance, cap_clearance,
    )
    if min(margins) <= 0.0:
        raise ValueError("opposing-stop contact or running clearance is lost")
    # Centered normal assembly is feasible, not guaranteed for arbitrary
    # register-slop poses. C2 still accepts actual full-face gaps and a free
    # pin turn. The measured chamber allowance already includes face variation;
    # no minimum flange chamfer is credited. For a quarter-circle corner,
    # (r-a)^2+(r-b)^2 <= r^2 gives r <= a+b+sqrt(2ab).
    normal_radial_gap = (
        pocket_diameter_min - (PIN_FLANGE_DIA + PIN_FLANGE_DIA_BAND[0])
    ) / 2.0
    normal_roof_gap = CAP_CHAMBER_EXCESS[0] - PIN_LOWER_GAP[1]
    if min(normal_radial_gap, normal_roof_gap) <= 0.0:
        raise ValueError("cap chamber has no centered normal running clearance")
    normal_corner_limit = (
        normal_radial_gap + normal_roof_gap
        + math.sqrt(2.0 * normal_radial_gap * normal_roof_gap)
    )
    if pocket_corner_radius_max >= normal_corner_limit:
        raise ValueError("cap chamber corner prevents centered normal running clearance")
    if available_penetration < CAP_MIN_COMPLETE_THREAD_ENGAGEMENT:
        raise ValueError("cap screw has insufficient available penetration for 1.5D complete threads")
    return CaptureBounds(
        cap_lateral_shift=cap_shift, cap_yaw=cap_motion.yaw,
        cap_register_endpoint_offset=cap_motion.register_endpoint_offset,
        cap_register_span_min=cap_motion.register_span_min,
        cap_register_endpoint_motion=cap_motion.register_endpoint_motion,
        cap_head_floor_x_margin=cap_motion.head_floor_x_margin,
        cap_head_floor_y_margin=cap_motion.head_floor_y_margin,
        cap_floor_migration=cap_motion.floor_migration, cap_head_release=cap_motion.head_release,
        cap_roof_rise=cap_motion.roof_rise, cap_top_rise=cap_motion.top_rise, cap_tilt=cap_motion.rock,
        flange_lateral_shift=flange_float, flange_contact_margin=flange_margin,
        floor_inner_margin=floor_inner, floor_counterbore_margin=floor_outer,
        cap_pocket_margin=pocket_margin, cap_aperture_margin=aperture_margin,
        pin_aperture_clearance=aperture_clearance, register_assembly_clearance=register_assembly,
        register_bottom_clearance=register_bottom, register_engagement=register_engagement,
        flange_tilt=tilt, pin_tilt=pin_tilt, carrier_tilt=carrier_tilt,
        carrier_motion_tilt=motion_tilt, support_lift=support_lift, support_drop=support_drop,
        cap_running_clearance=cap_clearance, cap_head_running_clearance=cap_motion.head_recess,
        screw_available_penetration=available_penetration,
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
