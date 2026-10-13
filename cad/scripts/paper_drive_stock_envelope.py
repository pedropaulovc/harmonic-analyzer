"""Rigorous end-envelope measures for a true finite stock-form cutter.

PURE DATA. Moved from pd_transgear_feed_pinion_spec's reviewed finite-ground
cap integrator. Feed and reducer use one implementation, with their actual
cutter diameter and axial stock domains.
No sampled-quadrature agreement or fictitious flank continuation is credited.
Public measures cover ONE indexed gap, BOTH signs of Y, and nonnegative axial
offsets from one terminal cutter plane. Callers own opposing planes and must
not double-count the already removed straight axial pass.
"""

from __future__ import annotations

import heapq
import math

from stock_form_cutter import StockFormProfile


def _ground_point(
    profile: StockFormProfile, shape: str, parameter: float
) -> tuple[float, float]:
    if shape == "root":
        return profile.root_point(parameter)
    if shape == "radial":
        return profile.radial_point(parameter)
    if shape == "flank":
        return profile.flank_point(parameter)
    raise ValueError(f"unknown finite ground branch {shape!r}")


def _ground_branches(profile: StockFormProfile) -> tuple[tuple[str, float, float], ...]:
    """Positive-Y branches, individually monotone in both X and Y."""
    template = profile.template
    if not (
        0.0 < profile.root_half_angle_rad < math.pi / 2.0
        and 0.0 < template.half_space_base_angle_rad
        and template.half_space_base_angle_rad + template.flank_parameter_max
        < math.pi / 2.0
    ):
        raise ValueError("finite ground branches do not have the required monotone bounds")
    branches = [("root", 0.0, profile.root_half_angle_rad)]
    if template.root_radius_mm < template.base_radius_mm:
        branches.append(("radial", template.root_radius_mm, template.base_radius_mm))
    branches.append(
        ("flank", template.flank_parameter_min, template.flank_parameter_max)
    )
    return tuple(branch for branch in branches if branch[2] > branch[1])


def _cap_measure(rho: float, q: float, d0: float, d1: float | None) -> float:
    """Exact XZ area (or X length when d1 is None) at one positive Y."""
    if q >= rho or d0 >= rho:
        return 0.0
    if d1 is None:
        return max(0.0, math.sqrt(max(0.0, rho * rho - d0 * d0)) - q)
    end = min(d1, math.sqrt(max(0.0, rho * rho - q * q)))
    if end <= d0:
        return 0.0

    def primitive(d: float) -> float:
        return 0.5 * (
            d * math.sqrt(max(0.0, rho * rho - d * d))
            + rho * rho * math.asin(min(1.0, d / rho))
        ) - q * d

    return max(0.0, primitive(end) - primitive(d0))


def _endcut_integral_bounds(
    profile: StockFormProfile,
    cutter_diameter_mm: float,
    outer_radius: float,
    inner_radius: float,
    d0: float,
    d1: float | None,
    absolute_error: float,
) -> tuple[float, float]:
    """One gap's positive-Y cut integral, enclosed without point quadrature.

    Each branch cell encloses the complete ground X/Y range by its monotone
    endpoints. The exact circular-cap integral is monotone in cutter radius
    and stock X extent. Multiplying its extrema by the enclosed Y width
    therefore encloses the whole cell, including cells crossing tangency.
    Floating padding is charged before summing; refinement is by the largest
    unresolved volume/area interval, never by agreement of two estimates.
    """
    if not (
        isinstance(profile, StockFormProfile)
        and profile.helix_angle_deg == 0.0
        and math.isfinite(cutter_diameter_mm)
        and cutter_diameter_mm > 0.0
        and math.isfinite(outer_radius)
        and math.isfinite(inner_radius)
        and 0.0 <= inner_radius < outer_radius
        and math.isfinite(d0)
        and d0 >= 0.0
        and (d1 is None or math.isfinite(d1) and d1 >= d0)
        and math.isfinite(absolute_error)
        and absolute_error > 0.0
    ):
        raise ValueError("invalid end-envelope integration domain or error")
    # The cutter's real endpoint, not a manufactured-blank reconstruction,
    # must put every side closure outside the complete stock being cut.
    tip_radius = math.hypot(*profile.flank_point(profile.template.flank_parameter_max))
    if tip_radius - max(outer_radius, profile.blank_radius_mm) <= profile.geometry_error_bound_mm:
        raise ValueError("finite ground tip/closure reaches the accepted stock")
    ground = profile
    axis = cutter_diameter_mm / 2.0 + profile.root_point(profile.root_half_angle_rad)[0]
    if axis <= outer_radius:
        raise ValueError("stock envelope reaches the tangential arbor closure")
    point_error = max(ground.geometry_error_bound_mm, 256 * math.ulp(axis))
    measure_error = 256 * math.ulp(axis ** (1 if d1 is None else 3))

    def cell(shape: str, lo: float, hi: float) -> tuple[float, float]:
        x0, y0 = _ground_point(ground, shape, lo)
        x1, y1 = _ground_point(ground, shape, hi)
        if y1 < y0:
            raise ValueError("finite ground branch reverses its Y direction")
        y_min, y_max = max(0.0, y0 - point_error), y1 + point_error
        rho_min = axis - max(x0, x1) - point_error
        rho_max = axis - min(x0, x1) + point_error

        def stock_bounds(radius: float) -> tuple[float, float]:
            if radius == 0.0 or y_min >= radius:
                return 0.0, 0.0
            xmax = math.sqrt(max(0.0, radius * radius - y_min * y_min))
            xmin = math.sqrt(max(0.0, radius * radius - y_max * y_max))
            lower = _cap_measure(rho_min, axis - xmin + point_error, d0, d1)
            upper = _cap_measure(rho_max, axis - xmax - point_error, d0, d1)
            return max(0.0, lower - measure_error), upper + measure_error

        outer_lo, outer_hi = stock_bounds(outer_radius)
        inner_lo, inner_hi = stock_bounds(inner_radius)
        lower = max(0.0, outer_lo - inner_hi)
        upper = max(0.0, outer_hi - inner_lo)
        width = y1 - y0
        return (
            max(0.0, lower * max(0.0, width - 2 * point_error)),
            upper * (width + 2 * point_error),
        )

    pending: list[tuple[float, int, str, float, float, float, float]] = []
    lower_sum = upper_sum = 0.0
    serial = 0
    for shape, lo, hi in _ground_branches(ground):
        lower, upper = cell(shape, lo, hi)
        lower_sum = math.nextafter(lower_sum + lower, -math.inf)
        upper_sum = math.nextafter(upper_sum + upper, math.inf)
        heapq.heappush(pending, (lower - upper, serial, shape, lo, hi, lower, upper))
        serial += 1
    while upper_sum - lower_sum > absolute_error:
        if serial >= 262144:
            raise ValueError("finite end-envelope interval did not resolve its declared error")
        _, _, shape, lo, hi, old_lower, old_upper = heapq.heappop(pending)
        mid = (lo + hi) / 2.0
        if mid == lo or mid == hi:
            raise ValueError("finite end-envelope refinement exhausted its parameter interval")
        lower_sum = math.nextafter(lower_sum - old_lower, -math.inf)
        upper_sum = math.nextafter(upper_sum - old_upper, math.inf)
        for start, end in ((lo, mid), (mid, hi)):
            lower, upper = cell(shape, start, end)
            lower_sum = math.nextafter(lower_sum + lower, -math.inf)
            upper_sum = math.nextafter(upper_sum + upper, math.inf)
            heapq.heappush(
                pending, (lower - upper, serial, shape, start, end, lower, upper)
            )
            serial += 1
    return max(0.0, lower_sum), upper_sum


def cutter_end_volume_bounds_mm3(
    profile: StockFormProfile,
    cutter_diameter_mm: float,
    *,
    outer_radius_mm: float,
    inner_radius_mm: float,
    start_offset_mm: float,
    end_offset_mm: float,
    absolute_error_mm3: float,
) -> tuple[float, float]:
    """ONE finite grounded indexed gap, BOTH ±Y, over one axial offset interval."""
    if not math.isfinite(end_offset_mm):
        raise ValueError("finite axial volume interval required")
    lower, upper = _endcut_integral_bounds(
        profile, cutter_diameter_mm, outer_radius_mm, inner_radius_mm,
        start_offset_mm, end_offset_mm, absolute_error_mm3 / 2.0,
    )
    return max(0.0, math.nextafter(2.0 * lower, -math.inf)), math.nextafter(2.0 * upper, math.inf)


def cutter_end_section_area_bounds_mm2(
    profile: StockFormProfile,
    cutter_diameter_mm: float,
    *,
    outer_radius_mm: float,
    inner_radius_mm: float,
    offset_mm: float,
    absolute_error_mm2: float,
) -> tuple[float, float]:
    """ONE finite grounded indexed gap, BOTH ±Y, at one axial offset."""
    lower, upper = _endcut_integral_bounds(
        profile, cutter_diameter_mm, outer_radius_mm, inner_radius_mm,
        offset_mm, None, absolute_error_mm2 / 2.0,
    )
    return max(0.0, math.nextafter(2.0 * lower, -math.inf)), math.nextafter(2.0 * upper, math.inf)
