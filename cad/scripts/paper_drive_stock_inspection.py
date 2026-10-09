"""Physical single-pin inspection of the paper drive's finite stock forms.

The caller owns the certified measuring-pin diameter, running-bore datum,
indicator setup and numerical runout grade. A free span or over-pins width
is translation-invariant and does not certify pattern eccentricity to that
running datum. This module owns only the actual supported-flank pin contact;
it does not substitute an ideal generated tooth or extrapolate a finite tip.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from stock_form_cutter import CutterTemplate, StockFormProfile


class GaugeContact(NamedTuple):
    parameter: float
    flank_point_mm: tuple[float, float]
    center_radius_mm: float
    root_air_mm: float
    tip_air_mm: float
    center_radius_error_bound_mm: float


def toothspace_gauge_contact_mm(
    profile: StockFormProfile, pin_diameter_mm: float
) -> GaugeContact:
    """Seat a certified actual-diameter pin symmetrically in the +X gap.

    On a straight stock-master flank, the actual tangent angle is k+u.
    Its inward normal is (sin(k+u), -cos(k+u)), so a pin centred on +X
    contacts when y(u)/cos(k+u) equals the pin radius. The centre then lies
    at x(u)+Rpin*sin(k+u). All curve points come from the public physical
    profile; only this pin-contact equation is solved here.

    Endpoint contacts and root/tip interference are refused. The returned
    centre-radius error charges the final parameter bracket and the core's
    geometry enclosure. Pin certification/indicator error belongs to the
    caller's inspection budget, not an invented tolerance in this solver.
    """
    if not isinstance(profile.template, CutterTemplate) or profile.helix_angle_deg != 0.0:
        raise ValueError("single-pin inspection requires a straight stock cutter master")
    if not math.isfinite(pin_diameter_mm) or pin_diameter_mm <= 0.0:
        raise ValueError("certified actual pin diameter must be finite and positive")
    radius = pin_diameter_mm / 2.0
    k = profile.template.half_space_base_angle_rad
    lo, hi = profile.flank_parameter_min, profile.flank_parameter_max
    if not (lo < hi and 0.0 < k + lo < k + hi < math.pi / 2.0):
        raise ValueError("single-pin contact has no monotone supported finite flank")
    geometry_error = profile.geometry_error_bound_mm

    def seated_radius(parameter: float) -> float:
        _, y = profile.flank_point(parameter)
        return y / math.cos(k + parameter)

    # y/cos(k+u) increases strictly on this entire supported branch.
    lower_radius, upper_radius = seated_radius(lo), seated_radius(hi)
    if not lower_radius + 4.0 * geometry_error < radius < upper_radius - 4.0 * geometry_error:
        raise ValueError("measuring pin contacts an unsupported root or finite tip endpoint")
    for _ in range(64):
        mid = (lo + hi) / 2.0
        if mid == lo or mid == hi:
            break
        if seated_radius(mid) < radius:
            lo = mid
        else:
            hi = mid
    parameter = (lo + hi) / 2.0
    point = profile.flank_point(parameter)
    lower_point, upper_point = profile.flank_point(lo), profile.flank_point(hi)
    lower_center = lower_point[0] + radius * math.sin(k + lo)
    upper_center = upper_point[0] + radius * math.sin(k + hi)
    center = point[0] + radius * math.sin(k + parameter)
    error = max(center - lower_center, upper_center - center) + 4.0 * geometry_error
    root_air = lower_center - radius - profile.root_radius_max_mm - 4.0 * geometry_error
    tip_air = (
        profile.blank_radius_mm
        - max(math.hypot(*lower_point), math.hypot(*upper_point))
        - 4.0 * geometry_error
    )
    if root_air <= 0.0 or tip_air <= 0.0:
        raise ValueError("measuring pin lacks positive root/finite-tip contact clearance")
    return GaugeContact(parameter, point, center, root_air, tip_air, error)


def span_contact_points_mm(
    profile: StockFormProfile, teeth_spanned: int
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Actual symmetric anvil contacts in the native tooth-at-+X phase."""
    if profile.helix_angle_deg != 0.0:
        raise ValueError("paper-drive span carrier requires a straight finite profile")
    profile.tangent_span_mm(teeth_spanned)
    half = math.pi * teeth_spanned / profile.teeth
    parameter = half - profile.template.half_space_base_angle_rad
    a = profile.flank_point(parameter, 1)
    x, y = profile.flank_point(parameter, -1)
    c, s = math.cos(2.0 * half), math.sin(2.0 * half)
    b = (c * x - s * y, s * x + c * y)
    c, s = math.cos(math.pi / profile.teeth), math.sin(math.pi / profile.teeth)
    return tuple((c * x - s * y, s * x + c * y) for x, y in (a, b))
