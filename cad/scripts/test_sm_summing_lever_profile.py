"""Host-hermetic geometry and receiver regressions; never import a CAD recipe.

Independent quadrature is deliberately test-only. Its cosine change of variable
regularizes circular endpoint square roots before applying Gauss-Legendre.
Production area/moment gates use finite analytic line/circle integrals, not a
sampled mesh. Historical before/after estimates stay local to this evidence.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from itertools import product
import math
from pathlib import Path

import pytest

from _printed_tolerance import printed_band_mm
import magnifying_bracket_joint_layout as joint
import sm_summing_lever_profile as profile
import sm_summing_lever_spec as spec


def _dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _g1_contract(section: profile.RibProfile) -> None:
    for branch, sign, face in (
        (section.upper, 1.0, section.top_y),
        (section.lower, -1.0, section.bottom_y),
    ):
        normal = branch.normal_xy
        assert math.hypot(*normal) == pytest.approx(1.0, abs=1e-13)
        assert normal[1] * sign > 0.0
        assert _dot(normal, branch.center_xy) == pytest.approx(
            section.wrap_radius + section.blend_radius, abs=1e-12
        )
        assert math.hypot(*branch.wrap_xy) == pytest.approx(section.wrap_radius)
        assert math.dist(branch.center_xy, branch.flank_xy) == pytest.approx(section.blend_radius)
        assert branch.wrap_xy == pytest.approx(tuple(section.wrap_radius * n for n in normal))
        assert branch.flank_xy == pytest.approx(tuple(
            c - section.blend_radius * n for c, n in zip(branch.center_xy, normal)
        ))
        tangent = tuple(b - a for a, b in zip(branch.wrap_xy, branch.flank_xy))
        assert _dot(tangent, normal) == pytest.approx(0.0, abs=1e-12)
        assert branch.end_xy == (section.reach, face)
        assert branch.center_xy == (section.reach, face + sign * section.blend_radius)
        assert _dot((1.0, 0.0), (0.0, face - branch.center_xy[1])) == 0.0
        if section.blend_radius:
            assert branch.blend.start_xy == pytest.approx(branch.end_xy)
            assert branch.blend.end_xy == pytest.approx(branch.flank_xy)
        for x in (branch.wrap_xy[0], branch.flank_xy[0], section.reach):
            expected = branch.height(x, section.wrap_radius)
            epsilon = 1e-7
            assert branch.height(x - epsilon, section.wrap_radius) == pytest.approx(expected, abs=2e-7)
            if x < section.reach:
                assert branch.height(x + epsilon, section.wrap_radius) == pytest.approx(expected, abs=2e-7)


def test_defining_dimensions_derive_the_approved_g1_profile() -> None:
    assert (spec.COEFFICIENT_T, spec.COEFFICIENT_TOP_Y, spec.COEFFICIENT_BOTTOM_Y) == pytest.approx((7.0, 2.54, -4.46))
    assert spec.COEFFICIENT_TOP_Y - spec.COEFFICIENT_BOTTOM_Y == pytest.approx(spec.COEFFICIENT_T)
    assert (spec.COUNTER_WEB_T, spec.RIB_WRAP_R, spec.RIB_REACH, spec.RIB_BLEND_R) == pytest.approx((5.08, 15.24, 35.814, 1.016))
    assert profile.UPPER.wrap_xy == pytest.approx((5.506482, 14.210428), abs=1e-6)
    assert profile.LOWER.wrap_xy == pytest.approx((4.700858, -14.496880), abs=1e-6)
    _g1_contract(profile.PROFILE)
    assert profile.rib_bounds(spec.RIB_REACH) == pytest.approx((-4.46, 2.54))
    lower, upper = profile.rib_bounds(29.7)
    assert upper != pytest.approx(-lower)
    assert profile.rib_bounds(-spec.RIB_WRAP_R) == pytest.approx((0.0, 0.0))
    with pytest.raises(ValueError):
        profile.rib_bounds(spec.RIB_REACH + 0.01)


def test_uniform_ribs_and_relocated_row_preserve_other_installed_interfaces() -> None:
    assert (spec.PLATE_W, spec.PLATE_L, spec.CYL_R) == pytest.approx((44.45, 152.4, 12.7))
    assert (spec.HOLE_X, spec.HOLE_COUNT, spec.HOLE_Z_OFFSET) == pytest.approx((39.85, 20, -3.52825))
    assert (spec.CHANNEL_Z0, spec.CHANNEL_PITCH) == pytest.approx((-67.1, 7.0565))
    assert (spec.HEX_W, spec.HEX_H, spec.HEX_DEPTH) == pytest.approx((8.080, 10.268, 21.717))
    assert (spec.TIP_X, spec.ANCHOR_H) == pytest.approx((-76.2, 19.05))
    # The lever's taps sit at the nearest .001 in (1.120 / .581, .128).
    assert tuple(point[0] for point in joint.LEVER_HOLE_POINTS) == (16.002, 29.6926)
    assert all(point[1] == pytest.approx(-0.7112) for point in joint.LEVER_HOLE_POINTS)
    assert all(point[2] == pytest.approx(-76.2) for point in joint.LEVER_HOLE_POINTS)
    assert (spec.RIB_T, joint.DRILL_DEPTH, joint.THREAD_DEPTH) == (5.08, 6.604, 4.95)
    assert joint.LEVER_FRONT_LOCAL_Z + spec.RIB_T == pytest.approx(-71.12)
    assert joint.DRILL_DEPTH_MIN > spec.RIB_T + spec.RIB_T_DEVIATIONS[1]
    assert joint.DRILL_DEPTH_DEVIATIONS == pytest.approx((-0.254, 0.254))
    assert joint.BRACKET_ORIGIN == (40.0, 979.7, -173.51)
    assert spec.HOLE_X - (joint.TAP_DRILL_DIA + joint.RECEIVER_DRILLED_DIAMETER_PLUS) / 2.0 > spec.RIB_REACH


def test_nearest_distance_is_not_a_vertical_height_or_infinite_line_shortcut() -> None:
    radius = joint.TAP_DRILL_DIA / 2.0
    x, y = 29.7, 0.0
    branch = profile.UPPER
    line_distance = spec.RIB_WRAP_R - _dot(branch.normal_xy, (x, y))
    assert profile.receiver_wall_margin(x, y, radius) == pytest.approx(line_distance - radius)
    assert profile.rib_bounds(x)[1] - y - radius > line_distance - radius + 0.2
    # Beyond the blend endpoint the real wall is the horizontal plate face,
    # not a negative-clearance extension of the rib flank.
    x, y = 40.0, 0.0
    assert profile.receiver_wall_margin(x, y, 0.0) == pytest.approx(2.54)
    assert spec.RIB_WRAP_R - _dot(branch.normal_xy, (x, y)) < 2.0
    # On the concave runout, nearest distance is to the circular arc, not its
    # infinite tangent line. The rightward normal points into material here.
    angle = (branch.blend.start_angle + branch.blend.start_angle + branch.blend.sweep) / 2.0
    on_arc = branch.blend.point(angle)
    toward_center = tuple((c - p) / branch.blend_radius for c, p in zip(branch.center_xy, on_arc))
    inside = tuple(p - 0.1 * n for p, n in zip(on_arc, toward_center))
    assert profile.receiver_wall_margin(*inside, 0.0) == pytest.approx(0.1, abs=1e-11)
    assert abs(spec.RIB_WRAP_R - _dot(branch.normal_xy, inside) - 0.1) > 0.001
    assert profile.receiver_wall_margin(44.5, 0.0, 0.0) == pytest.approx(-0.05)
    assert profile.receiver_wall_margin(40.0, 3.0, 0.0) == pytest.approx(-0.46)
    # The rib's sketch closure at reach lies INSIDE the plate; it is no wall.
    assert profile.receiver_wall_margin(spec.RIB_REACH - 0.01, 0.0, 0.0) > 2.5


def _receiver_pilot_radius() -> float:
    printed_pilot = round(joint.TAP_DRILL_DIA / spec.MM_PER_IN, 3) * spec.MM_PER_IN
    pilot_radius = (
        max(joint.TAP_DRILL_DIA, printed_pilot) + joint.RECEIVER_DRILLED_DIAMETER_PLUS
    ) / 2.0
    pilot_wander = math.tan(math.radians(joint.DRILL_WANDER_DEG)) * (
        joint.DRILL_DEPTH_MAX + pilot_radius * joint.DRILL_POINT_H
    )
    return pilot_radius + pilot_wander


def _witness_clearance(
    nominal_x: float, witness: tuple[float, ...], side: str
) -> float:
    wrap, reach, blend, width, top, thickness, ex, ey = witness
    section = profile.RibProfile(
        wrap_radius=wrap, reach=reach, blend_radius=blend, plate_width=width,
        top_y=top, bottom_y=top - thickness,
    )
    x = width - (spec.PLATE_W - nominal_x) + ex
    nominal_y = next(y for x, y, _z in joint.LEVER_HOLE_POINTS if x == nominal_x)
    y = top - (spec.COEFFICIENT_TOP_Y - nominal_y) + ey
    radius = _receiver_pilot_radius()
    if side == "minimum":
        return section.receiver_wall_margin(x, y, radius)
    boundary = section.upper_boundary if side == "upper" else section.lower_boundary
    return min(segment.distance(x, y) for segment in boundary) - radius


def _plate_top_y_limits() -> tuple[float, float]:
    """The printed chain: the top .10 (.XX) below the knife ridge, which stands
    half the .404 (.XXX) vertex height above the axis."""
    xx, xxx = printed_band_mm(2, unit="in"), printed_band_mm(3, unit="in")
    ridge = round(spec.HEX_H / spec.MM_PER_IN, 3) * spec.MM_PER_IN / 2.0
    drop = round((spec.HEX_H / 2.0 - spec.COEFFICIENT_TOP_Y) / spec.MM_PER_IN, 2) * spec.MM_PER_IN
    low = ridge - xxx / 2.0 - (drop + xx) - spec.COEFFICIENT_TOP_Y
    high = ridge + xxx / 2.0 - (drop - xx) - spec.COEFFICIENT_TOP_Y
    allowance = max(-low, high)
    return spec.COEFFICIENT_TOP_Y - allowance, spec.COEFFICIENT_TOP_Y + allowance


def test_pilot_ordinary_bands_have_replayable_correlated_wall_witnesses() -> None:
    budgets = profile.receiver_pilot_wall_budget()
    top_limits = _plate_top_y_limits()
    assert len(budgets) == len(joint.LEVER_HOLE_POINTS) == 2
    for budget, point in zip(budgets, joint.LEVER_HOLE_POINTS):
        assert budget.x_mm == point[0]
        for side in ("upper", "lower", "minimum"):
            clearance = getattr(budget, side + "_mm")
            witness = getattr(budget, side + "_witness")
            assert clearance == pytest.approx(_witness_clearance(point[0], witness, side))
            assert clearance > joint.RECEIVER_PILOT_WALL_MIN
            assert witness[2] in (0.0, spec.RIB_BLEND_R)  # R.040 MAX, never a band.
            assert any(witness[4] == pytest.approx(limit) for limit in top_limits)
            assert any(
                witness[5] - spec.COEFFICIENT_T == pytest.approx(deviation)
                for deviation in spec.COEFFICIENT_T_DEVIATIONS
            )
        assert budget.minimum_mm <= min(budget.upper_mm, budget.lower_mm) + 1e-12
    assert budgets[1].minimum_mm < budgets[0].minimum_mm
    # Check interior dimensions too: the finite corner budget must not hide a
    # lower mid-band wall, nor rely on top and tap motion being independent.
    worst = budgets[1]

    def span(nominal, deviations):
        return (nominal + deviations[0], nominal, nominal + deviations[1])

    for radius, reach, blend, top, thickness in product(
        span(spec.RIB_WRAP_R, spec.RIB_WRAP_R_DEVIATIONS),
        span(spec.RIB_REACH, spec.RIB_REACH_DEVIATIONS),
        (0.0, spec.RIB_BLEND_R / 2.0, spec.RIB_BLEND_R),
        (top_limits[0], spec.COEFFICIENT_TOP_Y, top_limits[1]),
        span(spec.COEFFICIENT_T, spec.COEFFICIENT_T_DEVIATIONS),
    ):
        width = spec.PLATE_W + spec.PLATE_W_DEVIATIONS[1]
        band = joint.POSITION_BAND
        witness = (radius, reach, blend, width, top, thickness, band, band)
        assert _witness_clearance(
            joint.LEVER_HOLE_POINTS[-1][0], witness, "upper"
        ) >= worst.upper_mm - 1e-10


def test_independent_plate_top_boundary_catches_obsolete_half_band(monkeypatch) -> None:
    # Construct the permitted outer receiver's upper-wall corner from the
    # title block, independently of the production top allowance/enumerator.
    top = _plate_top_y_limits()[1]
    wrap = spec.RIB_WRAP_R + spec.RIB_WRAP_R_DEVIATIONS[0]
    reach = spec.RIB_REACH + spec.RIB_REACH_DEVIATIONS[0]
    blend = spec.RIB_BLEND_R
    width = spec.PLATE_W + spec.PLATE_W_DEVIATIONS[1]
    thickness = spec.COEFFICIENT_T + spec.COEFFICIENT_T_DEVIATIONS[0]
    nominal_x, nominal_y, _ = joint.LEVER_HOLE_POINTS[-1]
    witness = (
        wrap, reach, blend, width, top, thickness,
        joint.POSITION_BAND, joint.POSITION_BAND,
    )
    x = width - (spec.PLATE_W - nominal_x) + joint.POSITION_BAND
    y = top - (spec.COEFFICIENT_TOP_Y - nominal_y) + joint.POSITION_BAND

    # Independent angular construction of the common tangent. Prove its
    # perpendicular foot lies on the finite flank before using line distance;
    # no RibProfile boundary/distance implementation supplies this oracle.
    cy = top + blend
    angle = math.atan2(cy, reach) + math.acos((wrap + blend) / math.hypot(reach, cy))
    nx, ny = math.cos(angle), math.sin(angle)
    distance = wrap - nx * x - ny * y
    foot_x = x + distance * nx
    assert wrap * nx < foot_x < reach - blend * nx
    permitted_wall = distance - _receiver_pilot_radius()
    assert permitted_wall > joint.RECEIVER_PILOT_WALL_MIN == pytest.approx(2.032)

    budget = profile.receiver_pilot_wall_budget()[-1]
    assert budget.upper_mm == pytest.approx(permitted_wall, abs=1e-12)
    assert budget.minimum_mm <= permitted_wall + 1e-12
    assert budget.upper_witness == pytest.approx(witness, abs=1e-12)
    assert _witness_clearance(nominal_x, witness, "upper") == pytest.approx(
        permitted_wall, abs=1e-12
    )

    # Both a missing top band and the former symmetric-5.08 half-band miss
    # this allowed configuration, reporting more wall than it actually has.
    printed_band = printed_band_mm(2, unit=spec.UNIT)
    for too_small in (0.0, printed_band / 2.0):
        with monkeypatch.context() as patch:
            patch.setattr(profile, "PLATE_TOP_Y_ALLOWANCE", too_small)
            incomplete = profile.receiver_pilot_wall_budget()[-1]
        assert incomplete.upper_mm > permitted_wall + 1e-6


def test_screw_stack_and_connected_material_are_independent_of_rib_thickness() -> None:
    assert joint.SCREW_TIP_GAP_MIN == pytest.approx(
        joint.THREAD_DEPTH - joint.THREAD_DEPTH_BAND - joint.SCREW_REACH_MAX
    )
    assert joint.TAP_LEAD_MARGIN_MIN == pytest.approx(
        joint.DRILL_DEPTH_MIN - joint.THREAD_DEPTH - joint.THREAD_DEPTH_BAND - 2.0 * joint.SCREW_PITCH
    )
    assert min(joint.SCREW_TIP_GAP_MIN, joint.TAP_LEAD_MARGIN_MIN) > 0.0
    assert joint.ENGAGEMENT_MIN >= 1.5 * joint.SCREW_MAJOR_DIA
    assert spec.RIB_T + spec.RIB_T_DEVIATIONS[0] < joint.THREAD_DEPTH
    assert spec.RIB_T + spec.RIB_T_DEVIATIONS[1] < joint.DRILL_DEPTH_MIN
    assert joint.receiver_pilot_material_wall_budget() >= joint.RECEIVER_PILOT_WALL_MIN
    assert all(
        wall.minimum_mm > joint.RECEIVER_PILOT_WALL_MIN
        for wall in profile.receiver_pilot_wall_budget()
    )
    # Beyond a shortened rib the relocated row is still backed by the plate.
    # Removing rib material is not itself a breakout; thinning that plate is.
    narrowed = replace(profile.PROFILE, reach=18.0)
    x, y, _ = joint.LEVER_HOLE_POINTS[-1]
    radius = joint.TAP_DRILL_DIA / 2.0
    assert narrowed.reach < x < narrowed.plate_width
    plate_wall = min(narrowed.top_y - y, y - narrowed.bottom_y) - radius
    assert narrowed.receiver_wall_margin(x, y, radius) == pytest.approx(plate_wall)
    assert plate_wall >= joint.RECEIVER_PILOT_WALL_MIN
    thinned = replace(
        narrowed,
        bottom_y=y - radius - joint.RECEIVER_PILOT_WALL_MIN / 2.0,
    )
    assert thinned.receiver_wall_margin(x, y, radius) < joint.RECEIVER_PILOT_WALL_MIN


def test_row_changes_recompute_longitudinal_wall_budget(monkeypatch) -> None:
    before = profile.receiver_pilot_wall_budget()
    monkeypatch.setattr(joint, "LEVER_HOLE_POINTS", tuple(
        (x, y - 0.20, z) for x, y, z in joint.LEVER_HOLE_POINTS
    ))
    after = profile.receiver_pilot_wall_budget()
    for old, new in zip(before, after, strict=True):
        assert new.lower_mm < old.lower_mm
        assert new.upper_mm > old.upper_mm
        for side in ("minimum", "upper", "lower"):
            assert getattr(new, side + "_mm") == pytest.approx(
                _witness_clearance(new.x_mm, getattr(new, side + "_witness"), side), abs=1e-12,
            )


@pytest.mark.parametrize("pilot", [1.778, 1.784])
def test_longitudinal_pilot_uses_printed_diameter_and_deepest_wander(monkeypatch, pilot) -> None:
    monkeypatch.setattr(joint, "TAP_DRILL_DIA", pilot)
    for budget in profile.receiver_pilot_wall_budget():
        for side in ("minimum", "upper", "lower"):
            assert getattr(budget, side + "_mm") == pytest.approx(
                _witness_clearance(budget.x_mm, getattr(budget, side + "_witness"), side),
                abs=1e-12,
            )


@pytest.mark.parametrize("name,value", [
    ("RECEIVER_DRILLED_DIAMETER_PLUS", 0.20),
    ("DRILL_WANDER_DEG", 0.6),
    ("DRILL_DEPTH_MAX", 7.4),
    ("DRILL_POINT_H", 1.0),
])
def test_longitudinal_pilot_rederives_allowance_and_deepest_wander(
    monkeypatch, name: str, value: float,
) -> None:
    before = profile.receiver_pilot_wall_budget()
    original_radius = _receiver_pilot_radius()
    monkeypatch.setattr(joint, name, value)
    radius_increase = _receiver_pilot_radius() - original_radius
    assert radius_increase > 0.0
    after = profile.receiver_pilot_wall_budget()
    for old, new in zip(before, after, strict=True):
        for side in ("minimum", "upper", "lower"):
            assert getattr(new, side + "_mm") == pytest.approx(
                getattr(old, side + "_mm") - radius_increase, abs=1e-12,
            )


def test_longitudinal_pilot_does_not_assume_a_thread_major_radius(monkeypatch) -> None:
    before = profile.receiver_pilot_wall_budget()
    monkeypatch.setattr(joint, "SCREW_MAJOR_DIA", 4.0)
    monkeypatch.setattr(joint, "THREAD_DEPTH", 8.0)
    monkeypatch.setattr(joint, "THREAD_DEPTH_BAND", 0.5)
    assert profile.receiver_pilot_wall_budget() == before


# Fixed four-point Gauss-Legendre quadrature, only an independent test oracle.
_GAUSS = (
    (-0.8611363115940526, 0.3478548451374538),
    (-0.3399810435848563, 0.6521451548625461),
    (0.3399810435848563, 0.6521451548625461),
    (0.8611363115940526, 0.3478548451374538),
)


def _integral(function, breaks: list[float]) -> float:
    """Regularize both endpoints of every geometric interval, without sampling them."""
    result = 0.0
    endpoints = sorted(set(breaks))
    theta_half_step = math.pi / 64.0
    for start, end in zip(endpoints, endpoints[1:]):
        midpoint = (start + end) / 2.0
        half_width = (end - start) / 2.0
        # x = midpoint - half_width*cos(theta), 0 < theta < pi.
        # A circular sqrt(x-start) or sqrt(end-x) endpoint becomes smooth
        # after multiplication by dx/dtheta = half_width*sin(theta).
        for index in range(32):
            theta_midpoint = math.pi * (index + 0.5) / 32.0
            for node, weight in _GAUSS:
                theta = theta_midpoint + node * theta_half_step
                x = midpoint - half_width * math.cos(theta)
                result += (
                    theta_half_step * weight * function(x)
                    * half_width * math.sin(theta)
                )
    return result


def test_independent_integral_matches_known_semicircle_moments() -> None:
    radius = 15.24
    cx, cy = 3.25, -2.5
    breaks = [cx, cx + radius]

    def height(x: float) -> float:
        return math.sqrt(max(0.0, radius**2 - (x - cx) ** 2))

    # A translated right semicircle has a singular right endpoint and nonzero,
    # differently signed first moments: symmetry cannot conceal a wrong weight.
    area = math.pi * radius**2 / 2.0
    assert _integral(lambda x: 2.0 * height(x), breaks) == pytest.approx(area, rel=0.0, abs=1e-8)
    assert _integral(lambda x: 2.0 * x * height(x), breaks) == pytest.approx(
        cx * area + 2.0 * radius**3 / 3.0, rel=0.0, abs=1e-8
    )
    assert _integral(lambda x: 2.0 * cy * height(x), breaks) == pytest.approx(
        cy * area, rel=0.0, abs=1e-8
    )


def _base_bounds(x: float, top: float, bottom: float) -> tuple[float, float]:
    circle = math.sqrt(max(0.0, spec.CYL_R**2 - x * x))
    if x < 0.0:
        return -circle, circle
    return min(-circle, bottom), max(circle, top)


def test_exact_added_area_and_first_moments_match_independent_section_integration() -> None:
    section = profile.PROFILE
    breaks = [
        -spec.RIB_WRAP_R, -spec.CYL_R, 0.0, spec.CYL_R,
        math.sqrt(spec.CYL_R**2 - section.top_y**2),
        math.sqrt(spec.CYL_R**2 - section.bottom_y**2),
        section.upper.wrap_xy[0], section.lower.wrap_xy[0],
        section.upper.flank_xy[0], section.lower.flank_xy[0], section.reach,
    ]

    def slice_moment(x: float, kind: str) -> float:
        lo, hi = section.rib_bounds(x)
        blo, bhi = _base_bounds(x, section.top_y, section.bottom_y)
        if kind == "y":
            return (hi * hi - lo * lo - bhi * bhi + blo * blo) / 2.0
        area = hi - lo - bhi + blo
        return area * x if kind == "x" else area

    exact = section.section_moments() - section.base_section_moments()
    assert exact.area_mm2 == pytest.approx(_integral(lambda x: slice_moment(x, "area"), breaks), abs=0.003)
    assert exact.x_mm3 == pytest.approx(_integral(lambda x: slice_moment(x, "x"), breaks), abs=0.02)
    assert exact.y_mm3 == pytest.approx(_integral(lambda x: slice_moment(x, "y"), breaks), abs=0.003)


def _edge_added_moments() -> tuple[profile.SectionMoments, profile.SectionMoments]:
    """Analytic full edge section and its negative-X half-annulus."""
    section = profile.PROFILE
    edge = section.section_moments() - section.base_section_moments()
    wrap, cylinder = section.wrap_radius, section.cylinder_radius
    negative = profile.SectionMoments(
        math.pi * (wrap**2 - cylinder**2) / 2.0,
        -2.0 * (wrap**3 - cylinder**3) / 3.0,
        0.0,
    )
    return edge, negative


def _rib_prism_change(thickness: float) -> tuple[profile.SectionMoments, float]:
    """Current-minus-PR1769 material of owned common sections only.

    Both edge ribs include their full negative wrap. The middle contribution
    here is its positive-X branch only: the pure profile does not describe the
    negative counterarm, and shrinking that part of the middle extrusion is
    deliberately NOT claimed to cancel. Excludes roots, hole relocation and
    any assertion about final lever mass, CG, strength or spring reserve.
    """
    edge, negative = _edge_added_moments()
    positive = edge - negative
    back_before, front_before, middle_before = 9.00, 5.08, 5.08
    delta = (
        edge.scaled(2.0 * thickness - back_before - front_before)
        + positive.scaled(thickness - middle_before)
    )
    half_length = spec.PLATE_L / 2.0
    old_axial_moment = (
        back_before * (-half_length + back_before / 2.0)
        + front_before * (half_length - front_before / 2.0)
    )
    # Equal end depths and a centred middle leave zero new axial first moment.
    return delta, -edge.area_mm2 * old_axial_moment


@pytest.mark.parametrize("thickness", [4.80, spec.RIB_T, 5.30])
def test_all_three_uniform_rib_prisms_recompute_material_not_receiver_extension_only(
    thickness: float,
) -> None:
    section = profile.PROFILE
    breaks = [
        -section.wrap_radius, -section.cylinder_radius, 0.0, section.cylinder_radius,
        math.sqrt(section.cylinder_radius**2 - section.top_y**2),
        math.sqrt(section.cylinder_radius**2 - section.bottom_y**2),
        section.upper.wrap_xy[0], section.lower.wrap_xy[0],
        section.upper.flank_xy[0], section.lower.flank_xy[0], section.reach,
    ]
    # Independent axial spans, rather than the analytic helper's coefficients.
    half = spec.PLATE_L / 2.0
    old_spans = ((-half, -half + 9.0), (-5.08 / 2.0, 5.08 / 2.0), (half - 5.08, half))
    new_spans = (
        (-half, -half + thickness), (-thickness / 2.0, thickness / 2.0),
        (half - thickness, half),
    )

    def slice_change(x: float, kind: str) -> float:
        lo, hi = section.rib_bounds(x)
        blo, bhi = _base_bounds(x, section.top_y, section.bottom_y)
        area = hi - lo - bhi + blo
        y_moment = (hi**2 - lo**2 - bhi**2 + blo**2) / 2.0
        total = 0.0
        for index, (old, new) in enumerate(zip(old_spans, new_spans, strict=True)):
            if index == 1 and x < 0.0:
                continue  # negative middle counterarm is outside this section's scope
            if kind == "z":
                total += area * (new[1]**2 - new[0]**2 - old[1]**2 + old[0]**2) / 2.0
            else:
                moment = y_moment if kind == "y" else area * x if kind == "x" else area
                total += moment * ((new[1] - new[0]) - (old[1] - old[0]))
        return total

    delta, z_moment = _rib_prism_change(thickness)
    for kind, exact, tolerance in (
        ("area", delta.area_mm2, 0.03), ("x", delta.x_mm3, 0.2),
        ("y", delta.y_mm3, 0.03), ("z", z_moment, 2.0),
    ):
        assert exact == pytest.approx(_integral(lambda x: slice_change(x, kind), breaks), abs=tolerance)
    assert delta.area_mm2 < 0.0
    assert z_moment > 0.0


def test_uniform_thickness_perturbation_charges_both_edges_and_middle_branch() -> None:
    baseline, baseline_z = _rib_prism_change(spec.RIB_T)
    changed, changed_z = _rib_prism_change(spec.RIB_T + 0.10)
    edge, negative = _edge_added_moments()
    derivative = edge.scaled(2.0) + (edge - negative)
    for field in ("area_mm2", "x_mm3", "y_mm3"):
        assert getattr(changed - baseline, field) == pytest.approx(
            getattr(derivative, field) * 0.10, abs=1e-10,
        )
    assert changed_z == baseline_z
    assert edge.area_mm2 == pytest.approx(profile.edge_rib_added_area_mm2())
    assert negative.area_mm2 > 0.0
    assert negative.x_mm3 < 0.0


def test_uniform_rib_axial_spans_preserve_both_end_faces_and_centre() -> None:
    half = spec.PLATE_L / 2.0
    spans = (
        (-half, -half + spec.RIB_T), (-spec.RIB_T / 2.0, spec.RIB_T / 2.0),
        (half - spec.RIB_T, half),
    )
    assert spans[0] == pytest.approx((-76.2, -71.12))
    assert spans[1] == pytest.approx((-2.54, 2.54))
    assert spans[2] == pytest.approx((71.12, 76.2))
    assert all(end - start == pytest.approx(5.08) for start, end in spans)
    # The separate counterweb is not a rib: its retained top still meets +2.54.
    assert spec.COUNTER_WEB_T == 5.08
    assert spec.COUNTER_WEB_T / 2.0 == spec.COEFFICIENT_TOP_Y


@pytest.mark.parametrize("changes", [
    {"wrap_radius": 15.75}, {"reach": 36.26}, {"blend_radius": 0.5},
    {"blend_radius": 0.0}, {"top_y": 2.795}, {"bottom_y": -4.97},
])
def test_primitive_mutations_rederive_geometry_and_volume(changes: dict[str, float]) -> None:
    changed = replace(profile.PROFILE, **changes)
    _g1_contract(changed)
    assert changed.upper.wrap_xy != profile.UPPER.wrap_xy or changed.lower.wrap_xy != profile.LOWER.wrap_xy
    assert changed.edge_rib_added_area_mm2() != pytest.approx(profile.edge_rib_added_area_mm2(), abs=1e-6)
    assert changed.section_moments().area_mm2 != pytest.approx(profile.PROFILE.section_moments().area_mm2, abs=1e-6)


def test_cylinder_and_plate_width_mutations_change_union_not_rib_tangent_coordinates() -> None:
    for changed in (replace(profile.PROFILE, cylinder_radius=13.0),
                    replace(profile.PROFILE, plate_width=45.0)):
        assert changed.upper == profile.UPPER
        assert changed.lower == profile.LOWER
    assert replace(profile.PROFILE, cylinder_radius=13.0).edge_rib_added_area_mm2() < profile.edge_rib_added_area_mm2()
    assert replace(profile.PROFILE, plate_width=45.0).edge_rib_added_area_mm2() == pytest.approx(profile.edge_rib_added_area_mm2())
    with pytest.raises(ValueError):
        replace(profile.PROFILE, wrap_radius=12.0)
    with pytest.raises(ValueError):
        replace(profile.PROFILE, blend_radius=-0.1)


def test_pure_profile_source_has_no_cad_or_com_import_path() -> None:
    tree = ast.parse(Path(profile.__file__).read_text(encoding="utf-8"))
    modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    assert "sm_summing_lever_spec" in modules
    assert not any(
        module.startswith(("build_", "solidworks_mcp", "win32", "pythoncom", "_com", "_session"))
        for module in modules
    )
