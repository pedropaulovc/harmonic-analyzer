"""Host-hermetic geometry and receiver regressions; never import a CAD recipe.

Independent quadrature is deliberately test-only. Production area/moment gates
use the profile's finite analytic line/circle integrals, not a sampled mesh.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from itertools import product
import math
from pathlib import Path

import pytest

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


def test_installed_interfaces_and_extended_receiver_are_unchanged() -> None:
    assert (spec.PLATE_W, spec.PLATE_L, spec.CYL_R) == pytest.approx((44.45, 152.4, 12.7))
    assert (spec.HOLE_X, spec.HOLE_COUNT, spec.HOLE_Z_OFFSET) == pytest.approx((39.85, 20, -3.52825))
    assert (spec.CHANNEL_Z0, spec.CHANNEL_PITCH) == pytest.approx((-67.1, 7.0565))
    assert (spec.HEX_W, spec.HEX_H, spec.HEX_DEPTH) == pytest.approx((8.080, 10.268, 21.717))
    assert (spec.TIP_X, spec.ANCHOR_H) == pytest.approx((-76.2, 19.05))
    assert joint.LEVER_HOLE_POINTS == ((16.0, 0.0, -76.2), (29.7, 0.0, -76.2))
    assert (joint.RIB_DEPTH, joint.DRILL_DEPTH, joint.THREAD_DEPTH) == (8.2, 6.5, 4.95)
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
    radius = (max(joint.SCREW_MAJOR_DIA, joint.TAP_DRILL_DIA) + joint.DRILLED_DIAMETER_PLUS) / 2.0
    radius += joint.DRILL_WANDER_MAX
    if side == "minimum":
        return section.receiver_wall_margin(x, y, radius)
    boundary = section.upper_boundary if side == "upper" else section.lower_boundary
    return min(segment.distance(x, y) for segment in boundary) - radius


def test_independent_ordinary_bands_have_replayable_correlated_wall_witnesses() -> None:
    budgets = profile.receiver_wall_budget()
    assert len(budgets) == len(joint.LEVER_HOLE_POINTS) == 2
    for budget, point in zip(budgets, joint.LEVER_HOLE_POINTS):
        assert budget.x_mm == point[0]
        for side in ("upper", "lower", "minimum"):
            clearance = getattr(budget, side + "_mm")
            witness = getattr(budget, side + "_witness")
            assert clearance == pytest.approx(_witness_clearance(point[0], witness, side))
            assert clearance > 2.0
            assert witness[2] in (0.0, 1.0)  # R1 MAX, never R1 +/-0.51.
            assert abs(witness[4] - spec.COEFFICIENT_TOP_Y) == pytest.approx(0.255)
            assert abs(witness[5] - spec.COEFFICIENT_T) == pytest.approx(0.51)
        assert budget.minimum_mm <= min(budget.upper_mm, budget.lower_mm) + 1e-12
    assert budgets[1].minimum_mm < budgets[0].minimum_mm
    # Check interior dimensions too: the finite corner budget must not hide a
    # lower mid-band wall, nor rely on top and tap motion being independent.
    worst = budgets[1]
    for radius, reach, blend, top, thickness in product(
        (14.73, 15.24, 15.75), (35.24, 35.75, 36.26), (0.0, 0.5, 1.0),
        (2.285, 2.54, 2.795), (6.49, 7.0, 7.51),
    ):
        witness = (radius, reach, blend, 44.96, top, thickness, 0.05, 0.05)
        assert _witness_clearance(29.7, witness, "upper") >= worst.upper_mm - 1e-10


def _axial_margins(rib_depth: float, thread_depth: float, drill_depth: float) -> tuple[float, ...]:
    """Independent replay of the JOINT's full-cylinder/point stack, not a 2D disk."""
    return (
        rib_depth - joint.RIB_DEPTH_BAND - thread_depth - joint.THREAD_DEPTH_BAND,
        thread_depth - joint.THREAD_DEPTH_BAND - joint.SCREW_REACH_MAX,
        drill_depth + joint.DRILL_DEPTH_DEVIATIONS[0] - thread_depth
        - joint.THREAD_DEPTH_BAND - 2.0 * joint.SCREW_PITCH,
        rib_depth - joint.RIB_DEPTH_BAND - drill_depth - joint.DRILL_DEPTH_DEVIATIONS[1]
        - joint.DRILL_POINT_DEPTH_MAX - joint.DRILL_WANDER_MAX,
    )


def test_full_cylindrical_threads_and_drill_points_fit_axially_and_laterally() -> None:
    margins = _axial_margins(joint.RIB_DEPTH, joint.THREAD_DEPTH, joint.DRILL_DEPTH)
    assert margins == pytest.approx((
        joint.THREAD_RIB_MARGIN_MIN, joint.SCREW_TIP_GAP_MIN,
        joint.TAP_LEAD_MARGIN_MIN, joint.DRILL_POINT_RIB_MARGIN_MIN,
    ))
    assert min(margins) > 0.0
    # The section is invariant through the rib depth. The max-major cylindrical
    # envelope, expanded by the deepest wander, encloses both full thread and
    # the smaller drill cylinder/cone at EVERY depth, not just a tip sample.
    assert joint.SCREW_MAJOR_DIA >= joint.TAP_DRILL_DIA
    assert all(wall.minimum_mm > 2.0 for wall in profile.receiver_wall_budget())
    assert min(_axial_margins(7.0, joint.THREAD_DEPTH, joint.DRILL_DEPTH)) < 0.0
    assert _axial_margins(joint.RIB_DEPTH, 4.0, joint.DRILL_DEPTH)[1] < 0.0
    assert _axial_margins(joint.RIB_DEPTH, joint.THREAD_DEPTH, 5.5)[2] < 0.0
    # Positive axial room cannot excuse a lateral breakout in a changed profile.
    narrowed = replace(profile.PROFILE, reach=18.0)
    assert narrowed.receiver_wall_margin(29.7, 0.0, joint.SCREW_MAJOR_DIA / 2.0) < 1.5


# Fixed four-point Gauss-Legendre quadrature, only an independent test oracle.
_GAUSS = (
    (-0.8611363115940526, 0.3478548451374538),
    (-0.3399810435848563, 0.6521451548625461),
    (0.3399810435848563, 0.6521451548625461),
    (0.8611363115940526, 0.3478548451374538),
)


def _integral(function, breaks: list[float]) -> float:
    result = 0.0
    for start, end in zip(sorted(set(breaks)), sorted(set(breaks))[1:]):
        for index in range(32):
            a = start + (end - start) * index / 32.0
            b = start + (end - start) * (index + 1) / 32.0
            result += (b - a) / 2.0 * sum(
                weight * function((a + b) / 2.0 + node * (b - a) / 2.0)
                for node, weight in _GAUSS
            )
    return result


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
    assert section.edge_rib_added_area_mm2() == exact.area_mm2
    assert profile.edge_rib_added_area_mm2() == exact.area_mm2
    assert exact.area_mm2 == pytest.approx(_integral(lambda x: slice_moment(x, "area"), breaks), abs=0.003)
    assert exact.x_mm3 == pytest.approx(_integral(lambda x: slice_moment(x, "x"), breaks), abs=0.02)
    assert exact.y_mm3 == pytest.approx(_integral(lambda x: slice_moment(x, "y"), breaks), abs=0.003)
    assert exact.area_mm2 > 400.0


def _legacy_rib_bounds(x: float, middle: bool) -> tuple[float, float]:
    radius, reach = spec.RIB_WRAP_R, spec.RIB_REACH
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


def test_new_minus_old_prism_union_and_gravity_increment_do_not_count_catalog_reserve() -> None:
    section = profile.PROFILE
    tx = spec.RIB_WRAP_R**2 / spec.RIB_REACH
    ny = math.sqrt(1.0 - (spec.RIB_WRAP_R / spec.RIB_REACH) ** 2)
    middle_plate_x = (spec.RIB_WRAP_R - ny * 2.54) / (spec.RIB_WRAP_R / spec.RIB_REACH)
    breaks = [
        0.0, spec.CYL_R, tx, middle_plate_x,
        math.sqrt(spec.CYL_R**2 - 2.54**2), math.sqrt(spec.CYL_R**2 - 4.46**2),
        section.upper.wrap_xy[0], section.lower.wrap_xy[0],
        section.upper.flank_xy[0], section.lower.flank_xy[0],
        spec.PLATE_W - 10.0, section.reach, spec.PLATE_W,
    ]
    depths = (spec.PLATE_L - joint.RIB_DEPTH - 2.0 * spec.COUNTER_WEB_T,
              joint.RIB_DEPTH + spec.COUNTER_WEB_T, spec.COUNTER_WEB_T)

    def change(x: float, kind: str) -> float:
        new_base = _base_bounds(x, 2.54, -4.46)
        old_base = _base_bounds(x, 2.54, -2.54, old_pad=True)
        new_rib = section.rib_bounds(x) if x <= section.reach else (-4.46, 2.54)
        value = 0.0
        for new, old, length in zip(
            (new_base, new_rib, new_rib),
            (old_base, _legacy_rib_bounds(x, False), _legacy_rib_bounds(x, True)), depths,
        ):
            if kind == "y":
                delta = (new[1] ** 2 - new[0] ** 2 - old[1] ** 2 + old[0] ** 2) / 2.0
            else:
                delta = new[1] - new[0] - old[1] + old[0]
                if kind == "x":
                    delta *= x
            value += delta * length
        return value

    delta = profile.ideal_prism_change()
    assert delta.volume_mm3 == pytest.approx(_integral(lambda x: change(x, "area"), breaks), abs=0.03)
    assert delta.x_moment_mm4 == pytest.approx(_integral(lambda x: change(x, "x"), breaks), abs=0.2)
    assert delta.y_moment_mm4 == pytest.approx(_integral(lambda x: change(x, "y"), breaks), abs=0.03)
    assert delta.volume_mm3 / 1000.0 == pytest.approx(6.768846, abs=0.01)
    assert delta.centroid_mm[0] > 0.0
    assert delta.centroid_mm[1] < 0.0
    assert delta.gravity_moment_increment_n_mm(7200.0) == pytest.approx(
        -7200.0e-9 * 9.80665 * delta.x_moment_mm4
    )
    assert delta.gravity_moment_increment_n_mm(7200.0) < 0.0
    # Root fillets are excluded; this is a delta CG, not a claim about the
    # complete lever's CG, spring extension, or available catalog travel.
    assert delta.gravity_moment_increment_n_mm(0.0) == 0.0


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
