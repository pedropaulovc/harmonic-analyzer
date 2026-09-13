"""SolidWorks-free channel rest-pose kinematics.

The closure reads only dimensional specs, machine-frame geometry, and config.
Assembly builders consume these solved poses but do not own the mechanism math.
"""

from __future__ import annotations

import math

import _config
import amplitude_bar_spec
import channel_frame_geom
import channel_lever_spec
import connecting_rod_spec
import cylinder_gear_spec
import rocker_arm_spec

__all__ = ["ARC", "arc_geometry", "solve_state", "spring_hole_xy"]


_PIVOT = channel_frame_geom.ROCKER_PIVOT_XY
_FULCRUM = channel_frame_geom.LEVER_FULCRUM_XY
_RING_CENTER = (
    channel_frame_geom.CAM_SHAFT_XY[0]
    + cylinder_gear_spec.ECCENTRICITY
    * math.sin(math.radians(channel_frame_geom.CYLINDER_LOCK_PHASE_DEG)),
    channel_frame_geom.CAM_SHAFT_XY[1]
    + cylinder_gear_spec.ECCENTRICITY
    * math.cos(math.radians(channel_frame_geom.CYLINDER_LOCK_PHASE_DEG)),
)
_ROD_C2C = connecting_rod_spec.CENTER_DISTANCE
_LEVER_DX = rocker_arm_spec.ROD_HOLE_X
_LEVER_DY = rocker_arm_spec.ROD_HOLE_Y - rocker_arm_spec.PIVOT_MID_Y
_ARM_ROD_LEVER = math.hypot(_LEVER_DX, _LEVER_DY)
_ARM_LEVER_BETA_DEG = math.degrees(math.atan2(_LEVER_DY, _LEVER_DX))
_ARM_ARC_CENTER_LOCAL_Y = rocker_arm_spec.CENTER_Y
_ARM_PIVOT_LOCAL_Y = rocker_arm_spec.PIVOT_MID_Y
_ARM_TOP_RADIUS = rocker_arm_spec.CURVE_RADIUS
# TOP_PIN_Y is measured from the bar profile's bottom-origin foot axis.
_BAR_TOP_TO_FOOT = amplitude_bar_spec.TOP_PIN_Y
_CONTACT_OFF_X = amplitude_bar_spec.BAR_WIDTH / 2.0
_CONTACT_OFF_Y = amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT - _config.fit(
    "cam_follower_contact", "contact_gap_mm"
)
_LEVER_BAR_PIN_X = channel_lever_spec.BAR_PIN_X


def arc_geometry() -> dict[str, float]:
    """Amplitude-independent rocker/rod kinematics + the top-edge arc centre.

    Rod-pin point P: |P - pivot| = ARM_ROD_LEVER (127.583) and
    |P - ring centre| = ROD_C2C, +X branch (rod side). The R800 arc the bar
    foot rides has its centre 808 mm out along the tilted arm's +Y, about the
    pivot hole at local (0, 8).
    """
    ox, oy = _PIVOT
    cx, cy = _RING_CENTER
    dx, dy = cx - ox, cy - oy
    d = math.hypot(dx, dy)
    a = (_ARM_ROD_LEVER**2 - _ROD_C2C**2 + d * d) / (2.0 * d)
    h = math.sqrt(_ARM_ROD_LEVER**2 - a * a)
    ux, uy = dx / d, dy / d
    # -X branch (rod side, machine frame): the ring sits at machine -X of the
    # pivot, so the rod-side intersection is the perpendicular branch with the
    # more-negative x -- (+h*uy, -h*ux) rather than the pre-#151 (-h*uy, +h*ux)
    # that picked the +X (mirrored) side. This IS the h-term sign flip the
    # machine-hand re-authoring demands: the rest of the loop is x-mirror-even.
    px = ox + a * ux + h * uy
    py = oy + a * uy - h * ux
    # The pin azimuth is the LEVER's direction, and the lever leans beta above
    # the arm's local +X. In the machine frame the arm's rod-side points -X, so
    # the azimuth is measured from -X (atan2 with x = ox - px); the ARM tilt is
    # that azimuth MINUS beta. Beta is load-bearing: the low rod-pin bore
    # (ROD_HOLE_Y 15.30) sits 7.30 above the pivot bore, and ignoring the 3.28
    # deg lever angle would land the pin 7 mm off and drag the ring off the cam.
    arm_tilt = math.degrees(math.atan2(py - oy, ox - px)) - _ARM_LEVER_BETA_DEG
    rod_tilt = math.degrees(math.atan2(px - cx, py - cy))  # machine hand: mirror
    # of the pre-#151 -atan2 (the ring is now at -X of the pin).

    t = math.radians(arm_tilt)
    rel = _ARM_ARC_CENTER_LOCAL_Y - _ARM_PIVOT_LOCAL_Y
    acx = ox + rel * math.sin(t)
    acy = oy + rel * math.cos(t)
    return {
        "arm_tilt": arm_tilt,
        "rod_tilt": rod_tilt,
        "pin_x": px,
        "pin_y": py,
        "acx": acx,
        "acy": acy,
    }


ARC = arc_geometry()
# LEVEL rest pose is authored, not incidental: ROD_HOLE_X / ROD_C2C /
# RING_CENTER are co-solved so the neutral arm sits flat (ch14 end views,
# 0-crank tip row). Any drift here means one of those constants moved without
# re-solving the closure -- fail before SolidWorks bakes the wrong pose in.
if abs(ARC["arm_tilt"]) > 0.02 or abs(ARC["rod_tilt"]) > 0.02:
    raise RuntimeError(
        "neutral pose no longer level: arm_tilt=%.4f deg, rod_tilt=%.4f deg "
        "-- re-solve ROD_HOLE_X (build_rocker_arm) and CENTER_DISTANCE "
        "(build_connecting_rod) against RING_CENTER"
        % (ARC["arm_tilt"], ARC["rod_tilt"])
    )


def solve_state(amplitude: float = 0.0) -> dict[str, float]:
    """Solve one channel's kinematics for an amplitude-bar station ``amplitude``.

    ``amplitude`` is the foot-axis X offset from the rocker pivot (mm), the
    Fourier coefficient a_j (channels.yaml ``amplitude_mm``); 0 reproduces the
    neutral pose bit-exactly. The mechanism is a 4-bar loop: the bar top pin
    rides the lever's 127 mm crank, the rigid bar (801.95 mm) hangs to the foot,
    and the foot-notch roof rests on the rocker's R800 top-edge arc. Positive
    amplitude slides the foot +X along the arc (the machine-frame lifting side,
    clear of the pivot shaft; the mirror of the pre-#151 -X side), tilting the
    bar by ``bar_tilt`` and the lever by ``lever_tilt``. Solved by driving the
    lever-reach residual to zero over the bar tilt.

    The solver runs in the machine frame, so its swing root ``beta`` is the
    PHYSICAL bar tilt (the mirror of the pre-#151 value). The reported
    ``bar_tilt`` negates it: the bar is authored ``rows_from_euler([bar_tilt,
    -90, 0])`` (Ry(-90), the mirror of the old Ry(+90)), and with that turn the
    scalar that reproduces the physical pose is -degrees(beta).
    """
    ox, _oy = _PIVOT
    acx, acy = ARC["acx"], ARC["acy"]
    fx = ox + amplitude  # foot-axis X (+X = the machine-frame lifting side)

    def foot_y(beta: float) -> float:
        s, c = math.sin(beta), math.cos(beta)
        cx_c = fx + _CONTACT_OFF_X * c - _CONTACT_OFF_Y * s
        ky = _CONTACT_OFF_X * s + _CONTACT_OFF_Y * c
        disc = _ARM_TOP_RADIUS**2 - (cx_c - acx) ** 2
        if disc <= 0.0:
            raise RuntimeError(f"foot station {amplitude:.1f} mm runs off the R800 arc")
        return acy - ky - math.sqrt(disc)

    def residual(beta: float) -> float:
        fy = foot_y(beta)
        tx = fx + _BAR_TOP_TO_FOOT * math.sin(beta)
        ty = fy + _BAR_TOP_TO_FOOT * math.cos(beta)
        return math.hypot(tx - _FULCRUM[0], ty - _FULCRUM[1]) - _LEVER_BAR_PIN_X

    beta = _bisect(residual, -0.30, 0.20)
    fy = foot_y(beta)
    tx = fx + _BAR_TOP_TO_FOOT * math.sin(beta)
    ty = fy + _BAR_TOP_TO_FOOT * math.cos(beta)
    contact_y = fy + _CONTACT_OFF_X * math.sin(beta) + _CONTACT_OFF_Y * math.cos(beta)
    return {
        "arm_tilt": ARC["arm_tilt"],
        "rod_tilt": ARC["rod_tilt"],
        "pin_x": ARC["pin_x"],
        "pin_y": ARC["pin_y"],
        "bar_tilt": -math.degrees(beta),
        "bar_bottom": fy,  # foot-axis Y
        "bar_origin_x": fx + (amplitude_bar_spec.BAR_WIDTH / 2.0) * math.cos(beta),
        "bar_origin_y": fy - (amplitude_bar_spec.BAR_WIDTH / 2.0) * math.sin(beta),
        "contact_y": contact_y,
        "bar_pin_y": ty,
        "lever_tilt": math.degrees(math.atan2(ty - _FULCRUM[1], _FULCRUM[0] - tx)),
    }


def spring_hole_xy(amplitude: float = 0.0) -> tuple[float, float]:
    """Return the channel lever's spring-hole centre in the machine XY frame."""
    phi = math.radians(solve_state(amplitude)["lever_tilt"])
    return (
        channel_frame_geom.LEVER_FULCRUM_XY[0]
        - channel_lever_spec.LEVER_SPRING_X * math.cos(phi),
        channel_frame_geom.LEVER_FULCRUM_XY[1]
        + channel_lever_spec.LEVER_SPRING_X * math.sin(phi),
    )


def _bisect(f, lo: float, hi: float, tol: float = 1e-10, iters: int = 80) -> float:
    """Root of monotone ``f`` on [lo, hi] (the bar-tilt that closes the loop)."""
    flo, fhi = f(lo), f(hi)
    if flo == 0.0:
        return lo
    if flo * fhi > 0.0:
        raise RuntimeError(
            f"bar-tilt root not bracketed: f({lo})={flo:.3f}, f({hi})={fhi:.3f}"
        )
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) < tol or (hi - lo) < tol:
            return mid
        if (fmid > 0.0) == (fhi > 0.0):
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)
