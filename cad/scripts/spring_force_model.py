"""Small-motion force response at the CAD's loaded spring seats.

Anchor centres rotate with the summing lever. Spring eyes slide on their seats;
they are not rigid lever points. Initial tension contributes geometric stiffness
and a small channel-gain term, even though mean-line zero removes its DC offset.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import channel_kinematics
import channel_spring_stock_geom as channel_stock
import counter_spring_stock_geom as counter_stock
import spring_mount_geom as mounts


@dataclass(frozen=True, slots=True)
class ChannelResponse:
    stiffness_n_mm_per_rad: float
    lift_torque_n: float
    hole_gain_per_mm: float
    rate_gain_per_fraction: float
    initial_gain_per_n: float


@lru_cache(maxsize=32)
def channel_response(
    hole_x_mm: float, rate_n_per_mm: float, initial_tension_n: float
) -> ChannelResponse:
    """Differentiate torque with respect to lever angle and vertical hook lift.

    For anchor vector r, upper-hook vector q, d=|q-r| and u=(q-r)/d,
    a=r cross u. With F=k*d+B, torque is k*(r cross q)+B*a.
    The common torsional denominator cancels in channel calibration; the
    reported gain sensitivities therefore differentiate only the lift numerator.
    """
    x = hole_x_mm
    y = mounts.CHANNEL_ANCHOR_XY[1] - mounts.KNIFE_CONTACT_Y
    hx, hy = channel_kinematics.spring_hole_xy()
    qx, qy = hx - mounts.KNIFE[0], hy - mounts.KNIFE_CONTACT_Y
    dx, dy = qx - x, qy - y
    span = math.hypot(dx, dy)
    ux, uy = dx / span, dy / span
    arm = x * uy - y * ux
    # The seat offsets are constant along the loaded axis. Obtain their sum
    # from the authoritative pose rather than duplicating wire/pin geometry.
    nominal_span = math.dist((hx, hy), mounts.CHANNEL_ANCHOR_XY)
    extension = (
        span
        - nominal_span
        + mounts.CHANNEL_NOMINAL_POSE.length_mm
        - channel_stock.FREE_LENGTH_MM
    )
    force = initial_tension_n + rate_n_per_mm * extension
    parallel = x * ux + y * uy
    stiffness = rate_n_per_mm * arm * arm + force * parallel * (1.0 + parallel / span)
    arm_lift = (x - arm * uy) / span
    lift = rate_n_per_mm * uy * arm + force * arm_lift
    if lift <= 0:
        raise ValueError("channel spring has no positive lift response")
    intercept = force - rate_n_per_mm * span
    arm_lift_x = 1.0 / span + (x * ux - qy * uy - 3.0 * arm * uy * ux) / span**2
    lift_x = rate_n_per_mm + intercept * arm_lift_x
    return ChannelResponse(
        stiffness,
        lift,
        lift_x / lift,
        rate_n_per_mm * (uy * arm + extension * arm_lift) / lift,
        arm_lift / lift,
    )


@lru_cache(maxsize=16)
def counter_stiffness(rate_n_per_mm: float, initial_tension_n: float) -> float:
    """Counter torsional tangent with the screw fixed at the built setting.

    The upper eye follows the screw's radial support as the spring axis turns.
    Its axial station is the CAD installation station. Full operating travel
    and contact migration remain part of the magnifier operating-pose gate.
    """
    pose = mounts.COUNTER_REFERENCE_POSE
    screw_y = pose.upper_eye_xy[1] + mounts.counter_upper_support_offset(pose.axis_xy)
    lower_offset = math.dist(mounts.COUNTER_ANCHOR_XY, pose.lower_eye_xy)
    rx = mounts.COUNTER_ANCHOR_XY[0] - mounts.KNIFE[0]
    ry = mounts.COUNTER_ANCHOR_XY[1] - mounts.KNIFE_CONTACT_Y

    def torque(angle: float) -> float:
        x = rx * math.cos(angle) - ry * math.sin(angle)
        y = rx * math.sin(angle) + ry * math.cos(angle)
        dx = pose.upper_eye_xy[0] - mounts.KNIFE[0] - x
        upper_y = pose.upper_eye_xy[1]
        for _ in range(12):
            dy = upper_y - mounts.KNIFE_CONTACT_Y - y
            span = math.hypot(dx, dy)
            axis = (dx / span, dy / span)
            supported_y = screw_y - mounts.counter_upper_support_offset(axis)
            if abs(supported_y - upper_y) < 1e-11:
                upper_y = supported_y
                break
            upper_y = supported_y
        else:
            raise ValueError("counter upper contact did not converge")
        dy = upper_y - mounts.KNIFE_CONTACT_Y - y
        span = math.hypot(dx, dy)
        length = span - lower_offset + counter_stock.EYE_ID_MM
        force = initial_tension_n + rate_n_per_mm * (
            length - counter_stock.FREE_LENGTH_MM
        )
        return force * (x * dy - y * dx) / span

    # 10 microradians keeps truncation below the contact solver's numerical
    # precision while avoiding subtractive cancellation in the torque difference.
    step = 1e-5
    return -(torque(step) - torque(-step)) / (2.0 * step)
