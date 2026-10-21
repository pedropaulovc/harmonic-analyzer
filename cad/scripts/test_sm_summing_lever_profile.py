"""Host-hermetic geometry and receiver regressions; never import a CAD recipe.

Independent quadrature is deliberately test-only. Its cosine change of variable
regularizes circular endpoint square roots before applying Gauss-Legendre.
Production area/moment gates use finite analytic line/circle integrals, not a
sampled mesh. Historical before/after estimates stay local to this evidence.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from itertools import product
import math
from pathlib import Path

import pytest

import _config
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
    assert (spec.COUNTER_WEB_T, spec.RIB_WRAP_R, spec.RIB_REACH, spec.RIB_BLEND_R) == pytest.approx((5.08, 15.24, 35.75, 1.0))
    assert profile.UPPER.wrap_xy == pytest.approx((5.516255, 14.206637), abs=1e-6)
    assert profile.LOWER.wrap_xy == pytest.approx((4.709362, -14.494120), abs=1e-6)
    _g1_contract(profile.PROFILE)
    assert profile.rib_bounds(spec.RIB_REACH) == pytest.approx((-4.46, 2.54))
    lower, upper = profile.rib_bounds(29.7)
    assert upper != pytest.approx(-lower)
    assert profile.rib_bounds(-spec.RIB_WRAP_R) == pytest.approx((0.0, 0.0))
    with pytest.raises(ValueError):
        profile.rib_bounds(spec.RIB_REACH + 0.01)


def test_receiver_deepens_only_inward_without_moving_installed_interfaces() -> None:
    assert (spec.PLATE_W, spec.PLATE_L, spec.CYL_R) == pytest.approx((44.45, 152.4, 12.7))
    assert (spec.HOLE_X, spec.HOLE_COUNT, spec.HOLE_Z_OFFSET) == pytest.approx((39.85, 20, -3.52825))
    assert (spec.CHANNEL_Z0, spec.CHANNEL_PITCH) == pytest.approx((-67.1, 7.0565))
    assert (spec.HEX_W, spec.HEX_H, spec.HEX_DEPTH) == pytest.approx((8.080, 10.268, 21.717))
    assert (spec.TIP_X, spec.ANCHOR_H) == pytest.approx((-76.2, 19.05))
    assert joint.LEVER_HOLE_POINTS == ((16.0, 0.0, -76.2), (29.7, 0.0, -76.2))
    assert (joint.RIB_DEPTH, joint.DRILL_DEPTH, joint.THREAD_DEPTH) == (9.0, 6.5, 4.95)
    assert joint.LEVER_FRONT_LOCAL_Z + joint.RIB_DEPTH == pytest.approx(-67.20)
    assert joint.DRILL_DEPTH_DEVIATIONS == (-0.51, 0.51)
    assert joint.BRACKET_ORIGIN == (40.0, 979.7, -173.51)
    assert spec.HOLE_X - (joint.SCREW_MAJOR_DIA + joint.DRILLED_DIAMETER_PLUS) / 2.0 > spec.RIB_REACH


def test_nearest_distance_is_not_a_vertical_height_or_infinite_line_shortcut() -> None:
    radius = joint.SCREW_MAJOR_DIA / 2.0
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


def _receiver_envelope_radius() -> float:
    pilot_radius = (
        max(joint.TAP_DRILL_DIA, round(joint.TAP_DRILL_DIA, 2))
        + joint.DRILLED_DIAMETER_PLUS
    ) / 2.0
    pilot_wander = math.tan(math.radians(joint.DRILL_WANDER_DEG)) * (
        joint.DRILL_DEPTH_MAX + pilot_radius * joint.DRILL_POINT_H
    )
    return max(
        joint.THREAD_CUTTING_ENVELOPE_DIA_MAX / 2.0 + joint.THREAD_CUTTING_PROOF_RESERVE,
        pilot_radius + pilot_wander,
    )


def _witness_clearance(
    nominal_x: float, witness: tuple[float, ...], side: str
) -> float:
    wrap, reach, blend, width, top, thickness, ex, ey = witness
    section = profile.RibProfile(
        wrap_radius=wrap, reach=reach, blend_radius=blend, plate_width=width,
        top_y=top, bottom_y=top - thickness,
    )
    x = width - (spec.PLATE_W - nominal_x) + ex
    y = top - spec.COEFFICIENT_TOP_Y + ey
    radius = _receiver_envelope_radius()
    if side == "minimum":
        return section.receiver_wall_margin(x, y, radius)
    boundary = section.upper_boundary if side == "upper" else section.lower_boundary
    return min(segment.distance(x, y) for segment in boundary) - radius


def _plate_top_y_limits() -> tuple[float, float]:
    """Independent union of native .XX and printed title-block limits."""
    row = _config.title_block("linear_2pl")
    native_band = float(row["value_in"]) * spec.MM_PER_IN
    printed_band = float(str(row["display"]).removeprefix("±"))
    printed_top = round(spec.COEFFICIENT_TOP_Y, 2)
    return (
        min(spec.COEFFICIENT_TOP_Y - native_band, printed_top - printed_band),
        max(spec.COEFFICIENT_TOP_Y + native_band, printed_top + printed_band),
    )


def test_required_envelope_ordinary_bands_have_replayable_correlated_wall_witnesses() -> None:
    budgets = profile.receiver_wall_budget()
    top_limits = _plate_top_y_limits()
    assert len(budgets) == len(joint.LEVER_HOLE_POINTS) == 2
    for budget, point in zip(budgets, joint.LEVER_HOLE_POINTS):
        assert budget.x_mm == point[0]
        for side in ("upper", "lower", "minimum"):
            clearance = getattr(budget, side + "_mm")
            witness = getattr(budget, side + "_witness")
            assert clearance == pytest.approx(_witness_clearance(point[0], witness, side))
            assert clearance > 2.0
            assert witness[2] in (0.0, 1.0)  # R1 MAX, never R1 +/-0.51.
            assert any(witness[4] == pytest.approx(limit) for limit in top_limits)
            assert abs(witness[5] - spec.COEFFICIENT_T) == pytest.approx(0.51)
        assert budget.minimum_mm <= min(budget.upper_mm, budget.lower_mm) + 1e-12
    assert budgets[1].minimum_mm < budgets[0].minimum_mm
    # Check interior dimensions too: the finite corner budget must not hide a
    # lower mid-band wall, nor rely on top and tap motion being independent.
    worst = budgets[1]
    for radius, reach, blend, top, thickness in product(
        (14.73, 15.24, 15.75), (35.24, 35.75, 36.26), (0.0, 0.5, 1.0),
        (top_limits[0], spec.COEFFICIENT_TOP_Y, top_limits[1]), (6.49, 7.0, 7.51),
    ):
        witness = (radius, reach, blend, 44.96, top, thickness, 0.05, 0.05)
        assert _witness_clearance(29.7, witness, "upper") >= worst.upper_mm - 1e-10


def test_independent_plate_top_boundary_catches_obsolete_half_band(monkeypatch) -> None:
    # Construct the permitted outer receiver's upper-wall corner from the
    # title block, independently of the production top allowance/enumerator.
    top = _plate_top_y_limits()[1]
    wrap = spec.RIB_WRAP_R - joint.LINEAR_BAND
    reach = spec.RIB_REACH - joint.LINEAR_BAND
    blend = spec.RIB_BLEND_R
    width = spec.PLATE_W + joint.LINEAR_BAND
    thickness = spec.COEFFICIENT_T - joint.LINEAR_BAND
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
    permitted_wall = distance - _receiver_envelope_radius()
    assert permitted_wall > joint.RECEIVER_WALL_MIN == 2.0

    budget = profile.receiver_wall_budget()[-1]
    assert budget.upper_mm == pytest.approx(permitted_wall, abs=1e-12)
    assert budget.minimum_mm == pytest.approx(permitted_wall, abs=1e-12)
    assert budget.upper_witness == pytest.approx(witness, abs=1e-12)
    assert _witness_clearance(nominal_x, witness, "upper") == pytest.approx(
        permitted_wall, abs=1e-12
    )

    # Both a missing top band and the former symmetric-5.08 half-band miss
    # this allowed configuration, reporting more wall than it actually has.
    row = _config.title_block("linear_2pl")
    printed_band = float(str(row["display"]).removeprefix("±"))
    for too_small in (0.0, printed_band / 2.0):
        with monkeypatch.context() as patch:
            patch.setattr(profile, "PLATE_TOP_Y_ALLOWANCE", too_small)
            incomplete = profile.receiver_wall_budget()[-1]
        assert incomplete.upper_mm > permitted_wall + 1e-6
        assert incomplete.minimum_mm > permitted_wall + 1e-6


def _axial_margins(rib_depth: float, thread_depth: float, drill_depth: float) -> tuple[float, ...]:
    """Replay native thread metadata, lead design allowance and pilot containment."""
    return (
        rib_depth - joint.RIB_DEPTH_BAND - thread_depth - joint.THREAD_DEPTH_BAND,
        thread_depth - joint.THREAD_DEPTH_BAND - joint.SCREW_REACH_MAX,
        drill_depth + joint.DRILL_DEPTH_DEVIATIONS[0] - thread_depth
        - joint.THREAD_DEPTH_BAND - 2.0 * joint.SCREW_PITCH,
        rib_depth - joint.RIB_DEPTH_BAND - drill_depth - joint.DRILL_DEPTH_DEVIATIONS[1]
        - joint.DRILL_POINT_DEPTH_MAX - joint.DRILL_WANDER_MAX,
    )


def test_native_thread_stack_and_pilot_fit_separately_from_required_envelope_walls() -> None:
    margins = _axial_margins(joint.RIB_DEPTH, joint.THREAD_DEPTH, joint.DRILL_DEPTH)
    assert margins == pytest.approx((
        joint.THREAD_RIB_MARGIN_MIN, joint.SCREW_TIP_GAP_MIN,
        joint.TAP_LEAD_MARGIN_MIN, joint.DRILL_POINT_RIB_MARGIN_MIN,
    ))
    assert min(margins) > 0.0
    # Conforming cutting removal is bounded independently of the longer pilot.
    # Native cosmetic/full-thread metadata does not qualify an actual tool.
    assert joint.SCREW_MAJOR_DIA >= joint.TAP_DRILL_DIA
    assert all(wall.minimum_mm > 2.0 for wall in profile.receiver_wall_budget())
    assert joint.receiver_thread_cutting_step_wall_budget() >= joint.RECEIVER_WALL_MIN
    assert joint.receiver_pilot_step_wall_budget() >= joint.RECEIVER_WALL_MIN == 2.0
    assert min(_axial_margins(7.0, joint.THREAD_DEPTH, joint.DRILL_DEPTH)) < 0.0
    assert _axial_margins(joint.RIB_DEPTH, 4.0, joint.DRILL_DEPTH)[1] < 0.0
    assert _axial_margins(joint.RIB_DEPTH, joint.THREAD_DEPTH, 5.5)[2] < 0.0
    # Positive axial room cannot excuse a lateral breakout in a changed profile.
    narrowed = replace(profile.PROFILE, reach=18.0)
    assert narrowed.receiver_wall_margin(29.7, 0.0, joint.SCREW_MAJOR_DIA / 2.0) < 1.5


def test_larger_cutting_envelope_reduces_required_walls_without_changing_pilot_proof(monkeypatch) -> None:
    pilot = joint.receiver_pilot_step_wall_budget()
    before = profile.receiver_wall_budget()
    monkeypatch.setattr(joint, "THREAD_CUTTING_ENVELOPE_DIA_MAX", 4.0)
    after = profile.receiver_wall_budget()
    for old, new in zip(before, after, strict=True):
        assert new.minimum_mm == pytest.approx(old.minimum_mm - (4.0 - 2.4) / 2.0)
    assert min(wall.minimum_mm for wall in after) < joint.RECEIVER_WALL_MIN
    assert joint.receiver_pilot_step_wall_budget() == pilot


def test_envelope_longitudinal_reserve_is_charged_once_without_duplicate_runout(monkeypatch) -> None:
    before = profile.receiver_wall_budget()
    monkeypatch.setattr(joint, "THREAD_CUTTING_PROOF_RESERVE", 0.08)
    after = profile.receiver_wall_budget()
    for old, new in zip(before, after, strict=True):
        assert new.minimum_mm == pytest.approx(old.minimum_mm - 0.04, abs=1e-12)
    # Runout/deflection already lie inside the actual-axis cutting envelope.
    # Pilot wander is a separate max branch, not added to that envelope.
    monkeypatch.setattr(joint, "DRILL_WANDER_DEG", 0.0)
    assert profile.receiver_wall_budget() == after


@pytest.mark.parametrize("pilot", [1.778, 1.784])
def test_longitudinal_pilot_branch_uses_printed_diameter_and_its_own_wander(monkeypatch, pilot) -> None:
    monkeypatch.setattr(joint, "THREAD_CUTTING_ENVELOPE_DIA_MAX", 1.0)
    monkeypatch.setattr(joint, "TAP_DRILL_DIA", pilot)
    for budget in profile.receiver_wall_budget():
        for side in ("minimum", "upper", "lower"):
            assert getattr(budget, side + "_mm") == pytest.approx(
                _witness_clearance(budget.x_mm, getattr(budget, side + "_witness"), side),
                abs=1e-12,
            )


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


def _base_bounds(x: float, top: float, bottom: float, old_pad: bool = False) -> tuple[float, float]:
    circle = math.sqrt(max(0.0, spec.CYL_R**2 - x * x))
    if x < 0.0:
        return -circle, circle
    lower = -4.46 if old_pad and x >= spec.PLATE_W - 10.0 else bottom
    return min(-circle, lower), max(circle, top)


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


def _legacy_rib_bounds(x: float, middle: bool) -> tuple[float, float]:
    radius, reach = spec.RIB_WRAP_R, spec.RIB_REACH
    if x < 0.0:
        half_height = math.sqrt(max(0.0, radius * radius - x * x))
        return -half_height, half_height
    if middle:
        tangent_x = radius * radius / reach
        if x <= tangent_x:
            half_height = math.sqrt(radius * radius - x * x)
        else:
            half_height = max(0.0, radius * (1.0 - x / reach) / math.sqrt(1.0 - radius**2 / reach**2))
    else:
        half_height = radius * (1.0 - x / spec.PLATE_W) if x <= reach else 0.0
    pad_bottom = -4.46 if x >= spec.PLATE_W - 10.0 else -2.54
    return min(-half_height, pad_bottom), max(half_height, 2.54)


@dataclass(frozen=True)
class _IdealPrismChange:
    """New minus old; centroid is of SIGNED changed volume, not the whole lever."""

    volume_mm3: float
    x_moment_mm4: float
    y_moment_mm4: float
    z_moment_mm4: float

    @property
    def centroid_mm(self) -> tuple[float, float, float]:
        return tuple(value / self.volume_mm3 for value in (
            self.x_moment_mm4, self.y_moment_mm4, self.z_moment_mm4
        ))

    def gravity_moment_increment_n_mm(
        self, density_kg_m3: float, gravity_m_s2: float = 9.80665
    ) -> float:
        """Signed Z torque change under -Y gravity: -rho*g*integral(x dV)."""
        return -density_kg_m3 * 1e-9 * gravity_m_s2 * self.x_moment_mm4


def _legacy_section(middle: bool) -> profile.SectionMoments:
    """Frozen pre-cutover section, including its 10 mm underside spring pad.

    Only the positive half of the middle rib is relevant to this subtraction:
    its unchanged negative-X extension cancels, so use the same semicircle
    closure for both designs. This is test-only historical evidence.
    """
    radius, width, reach = spec.RIB_WRAP_R, spec.PLATE_W, spec.RIB_REACH
    top, bottom, pad_bottom = 2.54, -2.54, -4.46
    pad_x = width - 10.0
    if middle:
        tx = radius * radius / reach
        ty = radius * math.sqrt(1.0 - radius * radius / (reach * reach))
        nx, ny = tx / radius, ty / radius
        plate_x = (radius - ny * top) / nx
        angle = math.atan2(ty, tx)
        upper: profile.Boundary = (
            *profile._polyline(((width, top), (plate_x, top), (tx, ty))),
            profile.Arc((0.0, 0.0), radius, angle, math.pi / 2.0 - angle),
        )
        lower: profile.Boundary = (
            profile.Arc((0.0, 0.0), radius, -math.pi / 2.0, math.pi / 2.0 - angle),
            *profile._polyline(((tx, -ty), (plate_x, bottom), (pad_x, bottom),
                               (pad_x, pad_bottom), (width, pad_bottom))),
        )
    else:
        end_h = radius * (1.0 - reach / width)
        pad_h = radius * (1.0 - pad_x / width)
        upper = profile._polyline(((width, top), (reach, top), (reach, end_h), (0.0, radius)))
        lower = profile._polyline(((0.0, -radius), (pad_x, -pad_h),
                                   (pad_x, pad_bottom), (width, pad_bottom)))
    return profile._moments((
        *upper, profile.Arc((0.0, 0.0), radius, math.pi / 2.0, math.pi),
        *lower, profile.Line((width, pad_bottom), (width, top)),
    ))


def _ideal_prism_change(receiver_depth: float = joint.RIB_DEPTH) -> _IdealPrismChange:
    """Source-only material/gravity delta with the frozen 8.20 legacy receiver.

    This nominal changed prism union excludes out-of-plane root fillets.
    The old plate was 5.08 with a 10 mm-wide, 7 mm-deep spring seat; its
    clipped edge slants and pointed positive middle profile are removed.
    The approved receiver adds an inward-only 0.80 strip beyond the historical
    8.20 cutover across the WHOLE closed edge-rib profile, including the -X wrap
    outside the cylinder. The opposite/middle ribs stay 5.08. The long negative-X
    counterweb, boss, knives and unchanged holes cancel; the receiver wrap does
    not. The spring catalog span supplies no reserve and is absent here.
    """
    # A wrap-radius mutation would also change the negative middle arm, which
    # this approved nominal cutover preserves.
    section = profile.PROFILE
    old_plate = profile.RibProfile(top_y=2.54, bottom_y=-2.54).base_section_moments()
    pad_x = spec.PLATE_W - 10.0
    pad = profile._moments(profile._polyline((
        (pad_x, -4.46), (spec.PLATE_W, -4.46),
        (spec.PLATE_W, -2.54), (pad_x, -2.54), (pad_x, -4.46),
    )))
    old_plate += pad
    base_delta = section.base_section_moments() - old_plate
    edge_delta = section.section_moments() - _legacy_section(middle=False)
    middle_delta = section.section_moments() - _legacy_section(middle=True)
    old_back, front, middle = 8.20, spec.COUNTER_WEB_T, spec.COUNTER_WEB_T
    ordinary_length = spec.PLATE_L - old_back - front - middle
    receiver_extension = receiver_depth - old_back
    extra_section = section.section_moments() - section.base_section_moments()
    total = (
        base_delta.scaled(ordinary_length)
        + edge_delta.scaled(old_back + front)
        + middle_delta.scaled(middle)
        + extra_section.scaled(receiver_extension)
    )
    # Retain the historical asymmetric end-span moment and then add only the
    # new inward receiver strip at its actual negative-Z centroid.
    back_center = -spec.PLATE_L / 2.0 + old_back / 2.0
    front_center = spec.PLATE_L / 2.0 - front / 2.0
    extension_center = -spec.PLATE_L / 2.0 + old_back + receiver_extension / 2.0
    z_moment = (
        (edge_delta.area_mm2 - base_delta.area_mm2)
        * (old_back * back_center + front * front_center)
        + extra_section.area_mm2 * receiver_extension * extension_center
    )
    return _IdealPrismChange(total.area_mm2, total.x_mm3, total.y_mm3, z_moment)


@pytest.mark.parametrize("receiver_depth", [8.20, 8.60, joint.RIB_DEPTH])
def test_new_minus_old_prism_union_and_gravity_increment_do_not_count_catalog_reserve(
    receiver_depth: float,
) -> None:
    section = profile.PROFILE
    tx = spec.RIB_WRAP_R**2 / spec.RIB_REACH
    ny = math.sqrt(1.0 - (spec.RIB_WRAP_R / spec.RIB_REACH) ** 2)
    middle_plate_x = (spec.RIB_WRAP_R - ny * 2.54) / (spec.RIB_WRAP_R / spec.RIB_REACH)
    breaks = [
        -spec.RIB_WRAP_R, -spec.CYL_R, 0.0, spec.CYL_R, tx, middle_plate_x,
        math.sqrt(spec.CYL_R**2 - 2.54**2), math.sqrt(spec.CYL_R**2 - 4.46**2),
        section.upper.wrap_xy[0], section.lower.wrap_xy[0],
        section.upper.flank_xy[0], section.lower.flank_xy[0],
        spec.PLATE_W - 10.0, section.reach, spec.PLATE_W,
    ]
    old_receiver_depth = 8.20
    new_depths = (spec.PLATE_L - receiver_depth - 2.0 * spec.COUNTER_WEB_T,
                  receiver_depth + spec.COUNTER_WEB_T, spec.COUNTER_WEB_T)
    old_depths = (spec.PLATE_L - old_receiver_depth - 2.0 * spec.COUNTER_WEB_T,
                  old_receiver_depth + spec.COUNTER_WEB_T, spec.COUNTER_WEB_T)

    def change(x: float, kind: str) -> float:
        new_base = _base_bounds(x, 2.54, -4.46)
        old_base = _base_bounds(x, 2.54, -2.54, old_pad=True)
        new_rib = section.rib_bounds(x) if x <= section.reach else (-4.46, 2.54)
        new_sections = (new_base, new_rib, new_rib)
        old_sections = (old_base, _legacy_rib_bounds(x, False), _legacy_rib_bounds(x, True))
        if kind == "z":
            front = spec.COUNTER_WEB_T
            front_moment = front * (spec.PLATE_L / 2.0 - front / 2.0)
            new_end_moment = receiver_depth * (
                -spec.PLATE_L / 2.0 + receiver_depth / 2.0
            ) + front_moment
            old_end_moment = old_receiver_depth * (
                -spec.PLATE_L / 2.0 + old_receiver_depth / 2.0
            ) + front_moment
            return (
                ((new_rib[1] - new_rib[0]) - (new_base[1] - new_base[0])) * new_end_moment
                - ((old_sections[1][1] - old_sections[1][0]) - (old_base[1] - old_base[0]))
                * old_end_moment
            )
        value = 0.0
        for new, old, new_length, old_length in zip(
            new_sections, old_sections, new_depths, old_depths,
        ):
            if kind == "y":
                delta = (
                    (new[1] ** 2 - new[0] ** 2) * new_length
                    - (old[1] ** 2 - old[0] ** 2) * old_length
                ) / 2.0
            else:
                delta = (new[1] - new[0]) * new_length - (old[1] - old[0]) * old_length
                if kind == "x":
                    delta *= x
            value += delta
        return value

    delta = _ideal_prism_change(receiver_depth)
    assert delta.volume_mm3 == pytest.approx(_integral(lambda x: change(x, "area"), breaks), abs=0.03)
    assert delta.x_moment_mm4 == pytest.approx(_integral(lambda x: change(x, "x"), breaks), abs=0.2)
    assert delta.y_moment_mm4 == pytest.approx(_integral(lambda x: change(x, "y"), breaks), abs=0.03)
    assert delta.z_moment_mm4 == pytest.approx(_integral(lambda x: change(x, "z"), breaks), abs=2.0)
    historical = _ideal_prism_change(old_receiver_depth)
    assert historical.volume_mm3 / 1000.0 == pytest.approx(6.768846, abs=0.01)
    assert delta.centroid_mm[0] > 0.0
    assert delta.centroid_mm[1] < 0.0
    assert delta.gravity_moment_increment_n_mm(7200.0) == pytest.approx(
        -7200.0e-9 * 9.80665 * delta.x_moment_mm4
    )
    assert delta.gravity_moment_increment_n_mm(7200.0) < 0.0
    # Root fillets are excluded; this is a delta CG, not a claim about the
    # complete lever's CG, spring extension, or available catalog travel.
    assert delta.gravity_moment_increment_n_mm(0.0) == 0.0


def test_receiver_extension_includes_both_x_halves_and_matches_native_increment() -> None:
    section = profile.PROFILE
    old_depth = 8.20
    extension = joint.RIB_DEPTH - old_depth
    assert extension == pytest.approx(0.80)
    entry = -spec.PLATE_L / 2.0
    start, end = entry + old_depth, entry + joint.RIB_DEPTH
    center = (start + end) / 2.0
    assert (start, end) == pytest.approx((-68.00, -67.20))

    def extension_slice(x: float, kind: str) -> float:
        # The actual closed sketch wraps behind the cylinder as well as
        # flaring into the +X slab. Only the existing cylinder/slab cancels.
        lo, hi = section.rib_bounds(x)
        blo, bhi = _base_bounds(x, section.top_y, section.bottom_y)
        if kind == "y":
            return (hi**2 - lo**2 - bhi**2 + blo**2) / 2.0
        area = hi - lo - bhi + blo
        return x * area if kind == "x" else area

    negative_breaks = [-section.wrap_radius, -section.cylinder_radius, 0.0]
    positive_breaks = [
        0.0, section.cylinder_radius,
        math.sqrt(section.cylinder_radius**2 - section.top_y**2),
        math.sqrt(section.cylinder_radius**2 - section.bottom_y**2),
        section.upper.wrap_xy[0], section.lower.wrap_xy[0],
        section.upper.flank_xy[0], section.lower.flank_xy[0], section.reach,
    ]
    negative, positive = (
        profile.SectionMoments(*(
            extension * _integral(lambda x: extension_slice(x, kind), breaks)
            for kind in ("area", "x", "y")
        ))
        for breaks in (negative_breaks, positive_breaks)
    )
    wrap, cylinder = section.wrap_radius, section.cylinder_radius
    # A point left of the cylinder is real receiver material: the long
    # counterweb is not an excuse to omit the edge rib's negative half-wrap.
    x = -(wrap + cylinder) / 2.0
    assert _base_bounds(x, section.top_y, section.bottom_y) == (0.0, 0.0)
    assert extension_slice(x, "area") == pytest.approx(
        2.0 * math.sqrt(wrap**2 - x**2)
    )
    assert extension_slice(-wrap, "area") == pytest.approx(0.0)
    assert negative.area_mm2 == pytest.approx(
        extension * math.pi * (wrap**2 - cylinder**2) / 2.0, abs=1e-8
    )
    assert negative.x_mm3 == pytest.approx(
        -extension * 2.0 * (wrap**3 - cylinder**3) / 3.0, abs=1e-8
    )
    assert negative.y_mm3 == pytest.approx(0.0, abs=1e-10)
    full_extension = negative + positive
    delta, historical = _ideal_prism_change(), _ideal_prism_change(old_depth)
    assert delta.volume_mm3 - historical.volume_mm3 == pytest.approx(
        full_extension.area_mm2, abs=0.003
    )
    assert delta.x_moment_mm4 - historical.x_moment_mm4 == pytest.approx(
        full_extension.x_mm3, abs=0.02
    )
    assert delta.y_moment_mm4 - historical.y_moment_mm4 == pytest.approx(
        full_extension.y_mm3, abs=0.003
    )
    assert delta.z_moment_mm4 - historical.z_moment_mm4 == pytest.approx(
        full_extension.area_mm2 * center, abs=0.2
    )
    assert negative.area_mm2 > 0.0
    assert negative.x_mm3 < 0.0
    assert negative.area_mm2 * center < 0.0

    # Captured native evidence: r3/r8-part-task.log in
    # C:/temp/summing-lever-simplify-20261020, respectively lines 219/219
    # (before counterweb and roots), 341/342 (after blind taps), and
    # 334/335 (the only changed R1-root allowance). Each volume is rounded to
    # 0.1 mm^3, so two readbacks permit at most 0.1 mm^3 difference error.
    before_roots = 118747.2 - 118432.3
    finished = 146204.8 - 145889.9
    changed_root = 38.398222 - 38.398143
    assert full_extension.area_mm2 == pytest.approx(before_roots, rel=0.0, abs=0.1)
    assert full_extension.area_mm2 + changed_root == pytest.approx(
        finished, rel=0.0, abs=0.1
    )


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
