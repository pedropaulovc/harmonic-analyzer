"""Loaded stock-spring attachment geometry, independent of SolidWorks.

The supplier length is INSIDE end to INSIDE end, not eye-centre spacing.
The lower eyes bear against the underside of their anchors under upward
spring force. The upper ends bear on the lever-hole edge / gooseneck screw.
The counter reference setting balances the spring moments at crank home;
actual setup slides the gooseneck until level, absorbing weight and measured
initial-tension differences rather than pretending the assembly simulates forces.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import _config
import channel_kinematics
import channel_lever_spec
import channel_spring_stock_geom as channel_stock
import counter_spring_stock_geom as counter_stock
import gooseneck_geom
import summing_lever_spec
from _hole_spec import blind_cut_dia_mm
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1

KNIFE = (-15.0, 979.7)
KNIFE_CONTACT_Y = KNIFE[1] + summing_lever_spec.HEX_H / 2.0
COLUMN_X = -197.0
MIN_CLEARANCE_MM = 0.25
PLATE_TOP_Y = KNIFE[1] + summing_lever_spec.PLATE_T / 2.0
CHANNEL_ANCHOR_XY = (
    KNIFE[0] + summing_lever_spec.HOLE_X,
    PLATE_TOP_Y - ANCHOR_9489T111.thread_start_y_mm,
)
COUNTER_SHANK_LENGTH_MM = summing_lever_spec.ANCHOR_H
COUNTER_ANCHOR_XY = (
    KNIFE[0] + summing_lever_spec.TIP_X,
    KNIFE[1] + summing_lever_spec.ANCHOR_H / 2.0 - ANCHOR_9490T1.thread_start_y_mm,
)
GOOSENECK_END_X = COLUMN_X - gooseneck_geom.ARM_END_X
COUNTER_UPPER_EYE_X = GOOSENECK_END_X + gooseneck_geom.SCREW_SHANK_LEN / 2.0

_channel = _config.parts("channel-spring-installed")
_counter = _config.parts("counter-spring")
CHANNEL_RATE_N_PER_MM = float(_channel["spring_rate_n_per_mm"])
CHANNEL_INITIAL_TENSION_N = float(_channel["initial_tension_n"])
COUNTER_RATE_N_PER_MM = float(_counter["spring_rate_n_per_mm"])
COUNTER_INITIAL_TENSION_N = float(_counter["initial_tension_n"])
COUNTER_MAXIMUM_LOAD_N = float(_counter["maximum_load_n"])

_CHANNEL_INNER_R = channel_stock.COIL_ID_MM / 2.0
_CHANNEL_LOWER_OFFSET = ANCHOR_9489T111.eye_id_mm / 2.0 + _CHANNEL_INNER_R
_CHANNEL_UPPER_DROP = (
    math.sqrt(_CHANNEL_INNER_R**2 - (channel_lever_spec.LEVER_THICKNESS / 2.0) ** 2)
    + blind_cut_dia_mm(channel_lever_spec.SPRING_EYE_HOLE_SPEC) / 2.0
)


@dataclass(frozen=True, slots=True)
class SpringPose:
    length_mm: float
    lower_eye_xy: tuple[float, float]
    upper_eye_xy: tuple[float, float]
    axis_xy: tuple[float, float]
    centre_xy: tuple[float, float]
    clocking: Literal["standard", "half_turn"] = "standard"

    @property
    def moment_arm_mm(self) -> float:
        """Signed perpendicular arm about the actual knife contact line."""
        x, y = self.lower_eye_xy
        ux, uy = self.axis_xy
        return (x - KNIFE[0]) * uy - (y - KNIFE_CONTACT_Y) * ux

    @property
    def rotation_rows(self) -> list[list[float]]:
        """Map the vendor coil frame, including the selected end clocking."""
        ux, uy = self.axis_xy
        sign = -1.0 if self.clocking == "half_turn" else 1.0
        return [[ux, uy, 0.0], [0.0, 0.0, sign], [sign * uy, -sign * ux, 0.0]]


@dataclass(frozen=True, slots=True)
class BankBalance:
    """One stationary spring-bank load and its reachable counter setting.

    ``channel_force_sum_n`` is the conservative sum of force magnitudes used
    for knife rolling resistance.  ``channel_vertical_force_n`` resolves those
    same forces onto the vertical knife reaction.  Counter/knife fields are
    ``None`` when no catalog-valid counter pose can balance the channel moment.
    """

    stations_mm: tuple[float, ...]
    channel_force_sum_n: float
    channel_vertical_force_n: float
    channel_moment_n_mm: float
    counter_minimum_force_n: float
    counter_maximum_force_n: float
    counter_minimum_moment_n_mm: float
    counter_maximum_moment_n_mm: float
    static_balance: bool
    counter_pose: SpringPose | None
    counter_force_n: float | None
    counter_vertical_force_n: float | None
    knife_vertical_load_n: float | None
    conservative_knife_load_n: float | None


def _pose(
    length: float,
    lower: tuple[float, float],
    upper: tuple[float, float],
    axis: tuple[float, float],
    *,
    clocking: Literal["standard", "half_turn"] = "standard",
) -> SpringPose:
    return SpringPose(
        length,
        lower,
        upper,
        axis,
        ((lower[0] + upper[0]) / 2.0, (lower[1] + upper[1]) / 2.0),
        clocking,
    )


def channel_pose(amplitude: float = 0.0) -> SpringPose:
    """Catalog-nominal seed; assembly builders resolve the native end surfaces."""
    hx, hy = channel_kinematics.spring_hole_xy(amplitude)
    ax, ay = CHANNEL_ANCHOR_XY
    dx, dy = hx - ax, hy - ay
    span = math.hypot(dx, dy)
    ux, uy = dx / span, dy / span
    lower = (ax + ux * _CHANNEL_LOWER_OFFSET, ay + uy * _CHANNEL_LOWER_OFFSET)
    upper = (hx - ux * _CHANNEL_UPPER_DROP, hy - uy * _CHANNEL_UPPER_DROP)
    length = channel_stock.check_length_mm(
        span - _CHANNEL_LOWER_OFFSET - _CHANNEL_UPPER_DROP + channel_stock.COIL_ID_MM
    )
    return _pose(length, lower, upper, (ux, uy))


def channel_force_n(
    length_mm: float,
    *,
    rate_n_per_mm: float = CHANNEL_RATE_N_PER_MM,
    initial_tension_n: float = CHANNEL_INITIAL_TENSION_N,
) -> float:
    """Catalog extension branch; at free length its endpoint is initial tension."""
    length = channel_stock.check_length_mm(length_mm)
    return initial_tension_n + rate_n_per_mm * (
        length - channel_stock.FREE_LENGTH_MM
    )


def counter_force_n(
    length_mm: float,
    *,
    rate_n_per_mm: float = COUNTER_RATE_N_PER_MM,
    initial_tension_n: float = COUNTER_INITIAL_TENSION_N,
) -> float:
    length = counter_stock.validate_length_mm(length_mm)
    return initial_tension_n + rate_n_per_mm * (
        length - counter_stock.FREE_LENGTH_MM
    )


def _minimum(fn, lo: float, hi: float) -> float:
    """Golden-section minimum on one known, convex loop-contact interval."""
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    left, right = hi - ratio * (hi - lo), lo + ratio * (hi - lo)
    fl, fr = fn(left), fn(right)
    for _ in range(48):
        if fl < fr:
            hi, right, fr = right, left, fl
            left = hi - ratio * (hi - lo)
            fl = fn(left)
            continue
        lo, left, fl = left, right, fr
        right = lo + ratio * (hi - lo)
        fr = fn(right)
    return min(fl, fr)


def _counter_lower_offset() -> float:
    """Seat BOTH helical loop turns against the open anchor's circular wire.

    The two turns have different axial offsets. A concentric-torus estimate
    overlaps the anchor; minimize clearance over each lower crossing instead.
    """
    radius = counter_stock.COIL_MEAN_RADIUS_MM
    tube = counter_stock.WIRE_RADIUS_MM + ANCHOR_9490T1.wire_radius_mm
    anchor_radius = ANCHOR_9490T1.eye_mean_radius_mm
    omega = 2.0 * math.pi * counter_stock.LOOP_TURNS
    half_interval = math.asin(tube / radius) / omega

    def limit(t: float) -> float:
        theta = -omega * t
        z = -counter_stock.LOOP_HALF_RISE_MM + counter_stock.LOOP_RISE_MM * t
        radial = anchor_radius - math.sqrt(
            max(0.0, tube**2 - (radius * math.sin(theta)) ** 2)
        )
        return -radius * math.cos(theta) + math.sqrt(radial**2 - z * z)

    return min(
        _minimum(limit, centre - half_interval, centre + half_interval)
        for centre in (
            1.0 / (2.0 * counter_stock.LOOP_TURNS),
            3.0 / (2.0 * counter_stock.LOOP_TURNS),
        )
    )


_COUNTER_LOWER_OFFSET = _counter_lower_offset()


def counter_upper_support_offset(axis: tuple[float, float]) -> float:
    """Ideal circular-wire support seed for the counter's half-turn clocking."""
    ux, uy = axis
    radius = counter_stock.COIL_MEAN_RADIUS_MM
    tube = counter_stock.WIRE_RADIUS_MM + gooseneck_geom.SCREW_SHANK_DIA / 2.0
    omega = 2.0 * math.pi * counter_stock.LOOP_TURNS
    half_interval = math.asin(tube / radius) / omega

    def limit(t: float) -> float:
        theta = math.pi / 2.0 - omega * t
        z = -counter_stock.LOOP_HALF_RISE_MM + counter_stock.LOOP_RISE_MM * t
        y = uy * radius * math.cos(theta) + ux * z
        return y - math.sqrt(max(0.0, tube**2 - (radius * math.sin(theta)) ** 2))

    return min(
        _minimum(limit, centre - half_interval, centre + half_interval)
        for centre in (
            1.0 / (4.0 * counter_stock.LOOP_TURNS),
            5.0 / (4.0 * counter_stock.LOOP_TURNS),
        )
    )


def counter_pose(length_mm: float) -> SpringPose:
    length = counter_stock.validate_length_mm(length_mm)
    span = length - counter_stock.EYE_ID_MM
    ax, ay = COUNTER_ANCHOR_XY
    ux = (COUNTER_UPPER_EYE_X - ax) / (span + _COUNTER_LOWER_OFFSET)
    uy = math.sqrt(1.0 - ux * ux)
    lower = (ax + ux * _COUNTER_LOWER_OFFSET, ay + uy * _COUNTER_LOWER_OFFSET)
    upper = (lower[0] + ux * span, lower[1] + uy * span)
    # The +X end has an extra half-turn and an asymmetric transition. Put
    # that raised wire on the OPEN side of the arm end, not inside the tube.
    # The opposite clocking penetrates the tube; the clearance regression
    # exercises this geometry rather than asserting an arbitrary angle.
    return _pose(length, lower, upper, (ux, uy), clocking="half_turn")


def solve_bank_balance(
    amplitudes_mm: Iterable[float],
    *,
    channel_rate_n_per_mm: float = CHANNEL_RATE_N_PER_MM,
    channel_initial_tension_n: float = CHANNEL_INITIAL_TENSION_N,
    counter_rate_n_per_mm: float = COUNTER_RATE_N_PER_MM,
    counter_initial_tension_n: float = COUNTER_INITIAL_TENSION_N,
) -> BankBalance:
    """Balance one stationary channel vector with a catalog-valid counter pose.

    The channel side uses each station's actual pose, catalog force and signed
    perpendicular arm.  The counter is solved in length because both its force
    and physical moment arm vary with the gooseneck setting.  Rate and initial
    tension are arguments so the tolerance model can preserve ``Nominal``
    overrides without replacing either geometry convention.
    """
    stations = tuple(float(amplitude) for amplitude in amplitudes_mm)
    channel_poses = tuple(channel_pose(amplitude) for amplitude in stations)
    channel_forces = tuple(
        channel_force_n(
            pose.length_mm,
            rate_n_per_mm=channel_rate_n_per_mm,
            initial_tension_n=channel_initial_tension_n,
        )
        for pose in channel_poses
    )
    channel_force_sum = sum(abs(force) for force in channel_forces)
    channel_vertical_force = sum(
        force * pose.axis_xy[1]
        for force, pose in zip(channel_forces, channel_poses, strict=True)
    )
    channel_moment = sum(
        force * pose.moment_arm_mm
        for force, pose in zip(channel_forces, channel_poses, strict=True)
    )

    if counter_rate_n_per_mm <= 0.0:
        raise ValueError("counter_rate_n_per_mm must be positive")
    lo = counter_stock.FREE_LENGTH_MM
    load_limited_hi = lo + (
        COUNTER_MAXIMUM_LOAD_N - counter_initial_tension_n
    ) / counter_rate_n_per_mm
    hi = min(counter_stock.MAX_LENGTH_MM, load_limited_hi)

    def counter_force(length: float) -> float:
        return counter_force_n(
            length,
            rate_n_per_mm=counter_rate_n_per_mm,
            initial_tension_n=counter_initial_tension_n,
        )

    def counter_moment(length: float) -> float:
        pose = counter_pose(length)
        return -counter_force(length) * pose.moment_arm_mm

    if hi < lo:
        return BankBalance(
            stations,
            channel_force_sum,
            channel_vertical_force,
            channel_moment,
            counter_initial_tension_n,
            COUNTER_MAXIMUM_LOAD_N,
            math.nan,
            math.nan,
            False,
            None,
            None,
            None,
            None,
            None,
        )

    minimum_moment = counter_moment(lo)
    maximum_moment = counter_moment(hi)
    minimum_force = counter_force(lo)
    maximum_force = counter_force(hi)
    if not minimum_moment <= channel_moment <= maximum_moment:
        return BankBalance(
            stations,
            channel_force_sum,
            channel_vertical_force,
            channel_moment,
            minimum_force,
            maximum_force,
            minimum_moment,
            maximum_moment,
            False,
            None,
            None,
            None,
            None,
            None,
        )

    for _ in range(48):
        mid = (lo + hi) / 2.0
        if counter_moment(mid) < channel_moment:
            lo = mid
        else:
            hi = mid
    pose = counter_pose((lo + hi) / 2.0)
    force = counter_force(pose.length_mm)
    counter_vertical_force = force * pose.axis_xy[1]
    return BankBalance(
        stations,
        channel_force_sum,
        channel_vertical_force,
        channel_moment,
        minimum_force,
        maximum_force,
        minimum_moment,
        maximum_moment,
        True,
        pose,
        force,
        counter_vertical_force,
        channel_vertical_force + counter_vertical_force,
        channel_force_sum + abs(force),
    )


def counter_half_turn_clearances(
    pose: SpringPose, screw_y: float
) -> tuple[float, float]:
    """Lower bounds on raised half-turn clearance to the tube and screw head.

    Distance to the solid cylinders is 1-Lipschitz. Subtract half the sampled
    centreline arc step, so a narrow collision between samples cannot pass.
    Native interference checks separately cover the transition and full bodies.
    """
    radius = counter_stock.COIL_MEAN_RADIUS_MM
    wire = counter_stock.WIRE_RADIUS_MM
    eye_x = counter_stock.end_centers_mm(pose.length_mm)[1][0]
    start_x = counter_stock.coil_end_x_mm(pose.length_mm) + wire
    rows = pose.rotation_rows
    head_x = GOOSENECK_END_X + gooseneck_geom.SCREW_SHANK_LEN
    tube_gap = head_gap = math.inf
    steps = 1024
    for index in range(steps + 1):
        angle = math.pi * index / steps
        local = (
            start_x - wire * index / steps - eye_x,
            -radius * math.sin(angle),
            -radius * math.cos(angle),
        )
        x = pose.upper_eye_xy[0] + sum(local[k] * rows[k][0] for k in range(3))
        y = pose.upper_eye_xy[1] + sum(local[k] * rows[k][1] for k in range(3))
        z = sum(local[k] * rows[k][2] for k in range(3))
        radial = math.hypot(y - screw_y, z)
        tube_gap = min(
            tube_gap,
            math.hypot(
                max(x - GOOSENECK_END_X, 0.0),
                max(radial - gooseneck_geom.TUBE_DIA / 2.0, 0.0),
            )
            - wire,
        )
        head_gap = min(
            head_gap,
            math.hypot(
                max(head_x - x, x - head_x - gooseneck_geom.SCREW_HEAD_T, 0.0),
                max(radial - gooseneck_geom.SCREW_HEAD_DIA / 2.0, 0.0),
            )
            - wire,
        )
    sampling_bound = math.hypot(wire, math.pi * radius) / (2.0 * steps)
    return tube_gap - sampling_bound, head_gap - sampling_bound


def _reference_counter_pose() -> SpringPose:
    # Full-machine coefficients, not active_count (which only truncates debug builds).
    balance = solve_bank_balance(_config.amplitudes())
    if not balance.static_balance:
        raise ValueError(
            "1330K524 cannot balance the configured spring moment "
            f"{balance.channel_moment_n_mm:.3f} N mm within its catalog load range"
        )
    assert balance.counter_pose is not None
    return balance.counter_pose


CHANNEL_NOMINAL_POSE = channel_pose()
COUNTER_REFERENCE_POSE = _reference_counter_pose()
GOOSENECK_ORIGIN_Y = (
    COUNTER_REFERENCE_POSE.upper_eye_xy[1]
    + counter_upper_support_offset(COUNTER_REFERENCE_POSE.axis_xy)
    - gooseneck_geom.ARM_Y
)
