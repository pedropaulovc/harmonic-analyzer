"""Whole continuous installed wire versus the captured cap's real cut union.

The provider's 0/180 representative route is fixed to its seated heads; the
cap moves through ALL poses admitted by retention.capture_bounds(). Neither
wire contact nor a filled screw-shank cylinder is credited as a cap stop.
This is not a universal six-hole head-clock, elastic-wire, or strength proof.
Accept the actual formed clock route only through real straight drilled holes,
pulling toward tightening, with the C3 seating/fitted-floor qualifications and
NORMAL_WIRE_RECESS_MIN over the whole unforced installed route. Never loosen
or over-torque a seated head to obtain a clock. The actual formed route must
retain the represented continuous control-envelope/clearance conditions.

The ordinary groove depth limits apply OVER ITS WHOLE FLOOR, NORMAL TO THE
ACTUAL TOP. An axis-depth interpretation with an uncharged floor slope is not
an alternative interpretation of this guard. Counterbore depth stays REF;
its actual whole floor and mouths retain retention.CAP_COUNTERBORE_FLOOR_MIN.

Every cubic is enclosed by its complete Bezier control hull, then by the
wire's round section. Exact dyadic subdivision permits different portions to
use overlapping circular counterbores, connecting grooves, and full-width
outward mouths. There is no fictitious closed-X counterbore wall. Actual
head-bearing support at the X outline comes from the SAME retention proof.

The native circular sweep uses these same controls with positive nonuniform
knot spans that match the endpoint derivatives. Reparameterization changes
neither the individual cubic images nor any envelope below; it cannot replace
a missing physical bend or serve as a separately fitted clearance mask.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from _printed_tolerance import printed_band_mm
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_vn_oblique_pivot_lock_wire_spec as wire

NORMAL_WIRE_RECESS_MIN = 0.50
# Analysis subdivision, not a machining tolerance or sampling approximation.
_CONTROL_HULL_BISECTIONS = 5


@dataclass(frozen=True)
class WireCaptureBounds:
    """Positive clearances conditional on the installed-route qualifications."""

    lateral_clearance: float
    channel_floor_clearance: float
    top_clearance: float
    head_bearing_floor_clearance: float
    head_support_x_clearance: float

    @property
    def surface_clearance(self) -> float:
        """Wire/cap surface separation only; exclude head-support margins."""
        return min(self.lateral_clearance, self.channel_floor_clearance, self.top_clearance)


def _bisect(controls):
    def midpoint(a, b):
        return tuple((x + y) / 2.0 for x, y in zip(a, b))

    a, b, c, d = controls
    ab, bc, cd = midpoint(a, b), midpoint(b, c), midpoint(c, d)
    abc, bcd = midpoint(ab, bc), midpoint(bc, cd)
    middle = midpoint(abc, bcd)
    return (a, ab, abc, middle), (middle, bcd, cd, d)


def _pieces(controls, depth=_CONTROL_HULL_BISECTIONS):
    if depth == 0:
        yield controls
    else:
        for half in _bisect(controls):
            yield from _pieces(half, depth - 1)


def require_wire_capture_geometry(
    *, channel_width: float | None = None, channel_depth: float | None = None,
    counterbore_diameter: float | None = None, segments=None,
    normal_wire_recess_min: float = NORMAL_WIRE_RECESS_MIN,
) -> WireCaptureBounds:
    """Certify all provider cubics against the same coupled capture geometry.

    Optional dimensions/controls support behavioral mutations; defaults are
    read at call time. The recess argument is an ACTUAL installed whole-route
    acceptance, not a nominal head-height stack. The ordinary groove depth
    band is whole-floor authority, including its high/low corners.
    """
    width = retention.CAP_WIRE_CHANNEL_WIDTH if channel_width is None else channel_width
    depth = retention.CAP_WIRE_CHANNEL_DEPTH if channel_depth is None else channel_depth
    diameter = retention.CAP_COUNTERBORE_DIAMETER if counterbore_diameter is None else counterbore_diameter
    if not all(math.isfinite(v) and v > 0.0 for v in (width, depth, diameter, normal_wire_recess_min)):
        raise ValueError("wire capture dimensions and installed recess must be finite and positive")
    curves = tuple(wire.installed_wire_segments() if segments is None else segments)
    if not curves or any(len(curve) != 4 or any(
        len(point) != 3 or not all(math.isfinite(v) for v in point) for point in curve
    ) for curve in curves):
        raise ValueError("wire capture requires nonempty finite cubic controls")

    captured = retention.capture_bounds()
    fitted = retention.fitted_counterbore_bounds()
    gamma = math.radians(retention.GENERAL_ANGULAR_BAND_DEGREES)
    beta = math.radians(retention.CAP_BOLT_BEARING_ANGLE_MAX_DEGREES)
    rock = math.radians(retention.CAP_ROCK_ENCLOSURE_DEGREES)
    initial_tilt = retention.initial_cap_tilt()
    head_roof_angle = 2.0 * gamma + initial_tilt
    if max(2.0 * gamma, gamma + rock, head_roof_angle + beta) >= math.pi / 2.0:
        raise ValueError("wire capture angular enclosure is outside its valid domain")
    radius = hardware.WIRE_DIA / 2.0
    head_radius = hardware.SCREW_HEAD_DIA_MAX / 2.0
    eccentricity = hardware.SCREW_HEAD_ECCENTRICITY_MAX
    head_reach = head_radius + eccentricity
    datum_conversion = head_reach * math.tan(beta)
    flat_radius = hardware.SCREW_HEAD_BEARING_DIA_MIN / 2.0
    bolt_band = printed_band_mm(retention.CAP_BOLT_LOCATION_PLACES)
    channel_band = printed_band_mm(retention.CAP_WIRE_CHANNEL_PLACES)
    cb_band = printed_band_mm(retention.CAP_COUNTERBORE_DIAMETER_PLACES)
    edge = printed_band_mm(retention.CAP_OUTLINE_PLACES) + printed_band_mm(retention.CAP_CENTER_LOCATION_PLACES)
    cb_min, cb_max = (diameter - cb_band) / 2.0, (diameter + cb_band) / 2.0
    channel_half = (width - channel_band) / 2.0
    points = tuple(point for curve in curves for point in curve)
    relative_low = min(p[2] - wire.WIRE_AXIS_Z for p in points)
    relative_high = max(p[2] - wire.WIRE_AXIS_Z for p in points)
    wire_low, wire_high = wire.swept_wire_z_bounds(curves, hardware_limits=True)
    # A selected head encloses a whole cubic, not merely each control's
    # independently nearest head. Convexity then encloses every curve point.
    near_radius = max(min(max(math.hypot(p[0] - x, p[1]) for p in curve)
                          for x in retention.CAP_BOLT_X_OFFSETS) for curve in curves)
    near_radius += math.sqrt(2.0) * bolt_band

    # Same ACTUAL roof/head reference: cap Hmax and Hmin are never independently
    # subtracted. The actual head-top/from-top-hole reference can lie anywhere
    # inside head_reach; its unknown H datum cancels from the top-wire bound.
    support_max = fitted.head_axis_height_max + head_reach * math.sin(head_roof_angle)
    wire_support_low = (
        (hardware.SCREW_WIRE_HEIGHT_MIN - datum_conversion + relative_low) * math.cos(head_roof_angle)
        - near_radius * math.sin(head_roof_angle) - radius
    )
    normal_depth_max = retention.CAP_HEAD_RECESS_MAX + support_max - wire_support_low
    source_normal_recess = (
        retention.CAP_HEAD_RECESS_MIN
        + hardware.SCREW_WIRE_FROM_TOP_MIN * math.cos(head_roof_angle)
        - (near_radius + head_reach) * math.sin(head_roof_angle)
        - relative_high - radius
    )
    normal_recess = min(normal_wire_recess_min, source_normal_recess)

    # A world enclosure for the complete fixed paired route. Source controls
    # outside the nominal outline expand it rather than being silently omitted.
    formed_error = (
        math.sqrt(2.0) * bolt_band + eccentricity
        + fitted.head_seat_max * math.tan(gamma)
        + (max(abs(wire_low), abs(wire_high)) + datum_conversion) * math.sin(gamma + rock)
    )
    extent_x = max(retention.CAP_WIDTH / 2.0 + edge, max(abs(p[0]) for p in points) + radius + formed_error)
    extent_y = max(retention.CAP_LENGTH / 2.0 + edge,
                   max(abs(y) for y in retention.CAP_BOLT_Y_OFFSETS)
                   + max(abs(p[1]) for p in points) + radius + formed_error)
    world_z = (fitted.head_seat_max + max(0.0, wire_high + datum_conversion)
               + near_radius * math.sin(gamma + rock))
    world_x = captured.cap_lateral_shift + extent_x + extent_y * math.sin(captured.cap_yaw) + world_z * math.sin(rock)
    world_y = captured.cap_lateral_shift + extent_y + extent_x * math.sin(captured.cap_yaw) + world_z * math.sin(rock)
    register_points = retention.CAP_REGISTER_CENTERS
    endpoint = captured.cap_register_endpoint_offset
    separation = captured.cap_register_span_min
    coefficient = max(
        sum(math.dist(point, register) for register in register_points) + 2.0 * endpoint
        for point in ((-world_x, -world_y), (-world_x, world_y), (world_x, -world_y), (world_x, world_y))
    ) / separation
    migration = (
        captured.cap_register_endpoint_motion * coefficient + 2.0 * world_z * math.sin(rock)
        + 2.0 * (math.hypot(world_x, world_y) + captured.cap_lateral_shift) * (1.0 - math.cos(rock))
    )

    # The SAME fixed-world floor/head support LP as retention._cap_motion.
    head_error = bolt_band + eccentricity + fitted.head_point_height_max * math.tan(gamma)
    bx = min(abs(x) for x, _ in retention.CAP_BOLT_CENTERS) - head_error - flat_radius
    by = min(abs(y) for _, y in retention.CAP_BOLT_CENTERS) - head_error - flat_radius
    fx, fy = retention.CAP_FLOOR_WITNESS_X, retention.CAP_FLOOR_WITNESS_Y
    slopes = ((0.0, 0.0), (1.0 / fx, 0.0), (0.0, 1.0 / fy), (1.0 / fx, 1.0 / fy))
    rise = captured.cap_head_release * max(
        (1.0 + world_x * sx + world_y * sy) / (1.0 + bx * sx + by * sy) for sx, sy in slopes)
    drop = captured.cap_head_release * max(
        max(0.0, world_x * sx + world_y * sy - 1.0) / (1.0 + bx * sx + by * sy) for sx, sy in slopes)
    # C3's base gap is on the mounting hull, not automatically on outer tails.
    hull_x = min(retention.BLOCK_WING_AXIS_REACH - printed_band_mm(retention.BLOCK_WING_AXIS_REACH_PLACES),
                 retention.trammel.PIN_OFFSET - retention.BLOCK_SPINDLE_END - printed_band_mm(1) - printed_band_mm(2))
    hull_y = retention.BLOCK_WING_HALF_WIDTH - printed_band_mm(1) - printed_band_mm(2)
    base_gap = retention.CAP_BASE_SEATING_GAP_MAX
    extrapolation = (base_gap / (2.0 * fx) * max(0.0, world_x - hull_x)
                     + base_gap / (2.0 * fy) * max(0.0, world_y - hull_y))
    roof_rise = (migration * math.sin(gamma) + rise + extrapolation
                 + (world_z + drop) * (1.0 - math.cos(captured.cap_tilt)))
    roof_drop = (migration * math.sin(gamma) + base_gap + extrapolation + drop
                 + (world_z + extrapolation) * (1.0 - math.cos(initial_tilt)))
    if (fitted.head_seat_min + wire_support_low) <= retention.CAP_VERTICAL_MOTION_ENCLOSURE:
        raise ValueError("wire envelope crosses the moving cap base")

    # Absolute cap-vs-fixed-head placement uses R's existing endpoint bound,
    # including BOTH register diagonals. No rounded '2.62mm' allowance is an
    # authority. The whole tube's depth bounds the angled CB/wall-axis drift.
    # Both the manufactured axis and actual roof retain their ordinary gamma
    # band relative to the nominal cap frame. A native CapTop sketch does not
    # establish gamma between those two manufactured features: spend 2*gamma.
    axis_roof_angle = 2.0 * gamma
    bore_lever = max(fitted.depth_at_head_max, normal_depth_max + roof_rise) / math.cos(axis_roof_angle)
    other = (
        2.0 * math.sqrt(2.0) * bolt_band + eccentricity
        + fitted.head_seat_max * math.tan(gamma)
        + fitted.head_point_height_max * math.sin(rock)
        + (max(abs(wire_low), abs(wire_high)) + datum_conversion) * math.sin(gamma + rock)
        + bore_lever * math.tan(axis_roof_angle)
    )
    head_coefficient = max(sum(math.dist(point, register) for register in register_points)
                           for point in retention.CAP_BOLT_CENTERS) / separation
    head_allowance = endpoint * head_coefficient + other

    def cut_margin(controls):
        point_coefficient = max(
            sum(math.dist((sign * p[0], row + p[1]), register) for register in register_points)
            for p in controls for sign in (-1.0, 1.0) for row in retention.CAP_BOLT_Y_OFFSETS
        ) / separation
        # The finite connecting groove joins both full-width outward mouths;
        # their union (then free space beyond stock) contains this infinite-X
        # strip. Clamp to the mouth width too: a width mutant cannot invent a
        # groove beyond its endpoints that is wider than the real mouths.
        strip_half = min(channel_half, cb_min)
        margins = [strip_half - radius - max(abs(p[1]) for p in controls) - other - endpoint * point_coefficient]
        for center in retention.CAP_BOLT_X_OFFSETS:
            margins.append(cb_min - radius - head_allowance
                           - max(math.hypot(p[0] - center, p[1]) for p in controls))
            side = math.copysign(1.0, center)
            outward = min(side * (p[0] - center) for p in controls)
            lateral = max(abs(p[1]) for p in controls)
            reach = max(abs(p[0] - center) for p in controls)
            # Full-width outward mouth, or free space beyond the stock. Its
            # direction follows the cap, so charge residual yaw for the tail.
            margins.append(min(
                outward * math.cos(captured.cap_yaw) - lateral * math.sin(captured.cap_yaw) - head_allowance - radius,
                cb_min - radius - head_allowance - lateral - reach * math.sin(captured.cap_yaw),
            ))
        return max(margins)

    lateral = min(cut_margin(piece) for curve in curves for piece in _pieces(curve))
    # Floors use the same body's actual head-axis anchor. The moving flat
    # circle cannot be undercut by the shallower connecting groove.
    floor_slope = math.tan(2.0 * gamma) / math.cos(gamma)
    protected_floor = fitted.depth_at_head_min - floor_slope * (
        flat_radius + eccentricity / math.cos(beta) + captured.cap_floor_migration)
    mouth_lever = math.hypot(
        retention.CAP_WIDTH / 2.0 + edge - min(abs(x) for x in retention.CAP_BOLT_X_OFFSETS) + bolt_band,
        cb_max,
    ) + head_allowance
    cb_floor_depth = fitted.depth_at_head_min - floor_slope * mouth_lever
    minimum_floor_depth = min(depth - channel_band, cb_floor_depth)
    floor_clearance = minimum_floor_depth - normal_depth_max - roof_rise
    head_floor_clearance = min(
        protected_floor - (depth + channel_band), cb_min - head_allowance - flat_radius)
    result = WireCaptureBounds(
        # Convert transverse/roof-coordinate allowances to conservative normal
        # surface distances at the ordinarily angled walls/floors.
        lateral_clearance=lateral * math.cos(2.0 * gamma + rock),
        channel_floor_clearance=floor_clearance * math.cos(2.0 * gamma),
        top_clearance=normal_recess - roof_drop,
        head_bearing_floor_clearance=head_floor_clearance * math.cos(2.0 * gamma),
        head_support_x_clearance=captured.cap_head_floor_x_margin,
    )
    for name, value in vars(result).items():
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"cap wire {name}: {value:.6f} mm loses the complete-route capture clearance")
    return result
