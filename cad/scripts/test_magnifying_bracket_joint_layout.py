"""Offline geometry, stock and recipe contracts for the magnifier's angle joint."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from _column_clamp_interface import BAR_DEPTH
import _interference_contracts as interference
import build_mg_magnifier_assembly as magnifier
import build_mg_magnifying_bracket as bracket
import build_sm_summing_assembly as summing
import _cone_axis_constants as installation
import magnifying_bracket_joint_layout as joint
import sm_knife_mount_spec as knife_mount
import sm_summing_lever_spec as lever
import sm_summing_lever_profile as lever_profile
import mg_vn_magnifying_bracket_screw_spec as screw
from _buildgraph import SCRIPTS_DIR, module_deps_of
from _hole_spec import THREAD_MAJOR_MM
from spring_mount_geom import KNIFE


def test_part_recipe_seat_literals_match_the_live_installation() -> None:
    assert joint.SEAT_PLANE_Z == pytest.approx(
        installation.SUMMING_Z - lever.PLATE_L / 2.0
    )
    assert joint.LEVER_FRONT_LOCAL_Z == pytest.approx(-lever.PLATE_L / 2.0)
    assert joint.LEVER_ORIGIN_X == KNIFE[0]
    assert joint.BRACKET_ORIGIN == (
        magnifier.BRACKET_X,
        magnifier.LEVER_ROD_Y,
        magnifier.LEVER_ROD_Z,
    )
    assert joint.BRACKET_ORIGIN[1] == KNIFE[1]
    for script in ("build_mg_magnifying_bracket.py", "build_sm_summing_lever.py"):
        names = {Path(path).stem for path in module_deps_of(SCRIPTS_DIR / script)}
        assert "magnifying_bracket_joint_layout" in names
        assert "dt_cone_pivot_post_installation" not in names
        assert "_cone_axis_constants" not in names
        assert "build_mg_magnifier_assembly" not in names
    # Do not re-key unrelated knife mounts/anchors when the bracket changes.
    names = {Path(path).stem for path in module_deps_of(SCRIPTS_DIR / "sm_summing_lever_spec.py")}
    assert "magnifying_bracket_joint_layout" not in names


def test_side_plate_is_flush_and_matches_neck_width_without_moving_the_arm() -> None:
    assert bracket.FLANGE_X == joint.SIDE_PLATE_X == (-48.0, bracket.NECK_HALF_X)
    assert bracket.FLANGE_Y == joint.SIDE_PLATE_Y == (-5.5, 5.5)
    assert joint.SIDE_PLATE_HEIGHT == 2.0 * bracket.NOSE_R == 11.0
    assert joint.SIDE_PLATE_HEIGHT_DEVIATIONS == pytest.approx((-0.8, 0.8))
    assert bracket.FLANGE_Z == joint.SIDE_PLATE_Z
    back = joint.BRACKET_ORIGIN[2] + bracket.FLANGE_Z[1]
    front = joint.BRACKET_ORIGIN[2] + bracket.FLANGE_Z[0]
    assert back == pytest.approx(joint.SEAT_PLANE_Z)
    assert back - front == pytest.approx(joint.SIDE_PLATE_THICKNESS)
    assert joint.SIDE_PLATE_MACHINE_X == tuple(joint.BRACKET_ORIGIN[0] + x for x in bracket.FLANGE_X)
    mount_back = (
        installation.SUMMING_Z - summing.HEX_Z_MID + knife_mount.SUPPORT_Z_THICK / 2.0
    )
    assert front - mount_back == pytest.approx(0.6985, abs=1e-4)
    # Their plan projections may overlap; positive axial air keeps them separate.
    assert front > mount_back


def test_side_by_side_stations_have_head_clearance_and_head_bearing() -> None:
    assert joint.SCREW_MACHINE_X == (1.0, 14.7)
    assert joint.SCREW_PITCH_X == pytest.approx(13.7)
    assert joint.RECEIVER_ROW_FROM_TOP == 3.25
    assert joint.RECEIVER_ROW_Y == pytest.approx(-0.71)
    assert tuple(point[0] for point in joint.LEVER_HOLE_POINTS) == (16.0, 29.7)
    for point in joint.LEVER_HOLE_POINTS:
        assert point[1:] == pytest.approx((-0.71, -76.2))
    for bracket_point, lever_point, pose in zip(
        joint.BRACKET_HOLE_POINTS,
        joint.LEVER_HOLE_POINTS,
        joint.SCREW_POSITIONS,
        strict=True,
    ):
        assert bracket_point[0] + joint.BRACKET_ORIGIN[0] == pytest.approx(
            lever_point[0] + KNIFE[0]
        )
        assert bracket_point[1] == lever_point[1] == joint.RECEIVER_ROW_Y
        assert bracket_point[1] + joint.BRACKET_ORIGIN[1] == pytest.approx(
            lever_point[1] + KNIFE[1]
        )
        assert lever.COEFFICIENT_TOP_Y - lever_point[1] == pytest.approx(3.25)
        assert pose == (
            lever_point[0] + KNIFE[0],
            KNIFE[1] + joint.RECEIVER_ROW_Y,
            joint.SIDE_PLATE_FRONT_Z,
        )
    assert joint.CLEARANCE_SPEC.kind == "clearance"
    assert joint.CLEARANCE_SPEC.size == "#2"
    assert joint.CLEARANCE_SPEC.fit == "normal"
    assert joint.CLEARANCE_SPEC.end == "through_all"
    assert joint.CLEARANCE_SPEC.overrides_mm == {}
    assert joint.CLEARANCE_DIA == 2.591
    assert joint.SCREW_MAJOR_DIA < joint.CLEARANCE_DIA < joint.SCREW_HEAD_DIA
    assert joint.COUNTERBORE_DIA - joint.SCREW_HEAD_DIA == pytest.approx(0.244)
    assert joint.HEAD_FLOAT_MIN == pytest.approx(0.122)
    assert joint.HEAD_POSITION_MISMATCH_MAX == pytest.approx(0.10)
    assert joint.HEAD_FLOAT_MIN >= joint.HEAD_POSITION_MISMATCH_MAX
    assert joint.GRIP_MIN == pytest.approx(3.045)
    assert joint.COUNTERBORE_END_WALL_MIN == pytest.approx(7.0)
    # The bracket ordinate is from its actual lower edge, not its midplane.
    head_radius = (joint.COUNTERBORE_DIA + joint.DRILLED_DIAMETER_PLUS) / 2.0
    row_from_lower = joint.RECEIVER_ROW_Y - joint.SIDE_PLATE_Y[0]
    lower_wall = row_from_lower - joint.POSITION_BAND - head_radius
    upper_wall = (
        joint.SIDE_PLATE_HEIGHT + joint.SIDE_PLATE_HEIGHT_DEVIATIONS[0]
        - row_from_lower - joint.POSITION_BAND - head_radius
    )
    assert (row_from_lower, lower_wall, upper_wall) == pytest.approx((4.79, 2.79, 3.41))
    assert joint.COUNTERBORE_HEIGHT_WALL_MIN == pytest.approx(min(lower_wall, upper_wall))
    assert joint.HEAD_PROTRUSION == pytest.approx(2.1082)
    # A flush head would run the screw past the tap's full thread.
    flush_reach = joint.SCREW_LENGTH - joint.SIDE_PLATE_THICKNESS + joint.SCREW_HEAD_HEIGHT
    assert flush_reach == pytest.approx(6.8707)
    assert flush_reach > joint.THREAD_DEPTH
    head_air = (
        min(joint.SCREW_MACHINE_X) - joint.SCREW_HEAD_DIA / 2.0
        - (KNIFE[0] + knife_mount.BLK_HALF_X)
    )
    # The 25.4-wide knife mount's +X face stands at -2.3 (KNIFE x -15).
    assert head_air == pytest.approx(1.522)
    # Receiver stations follow the lever's real free edge: its width band
    # adds a whole-part translation relative to the pivot/knife line.
    assert head_air - joint.POSITION_BAND - 2.0 * joint.LINEAR_BAND == pytest.approx(0.452)


def test_accepted_foot_corners_retain_head_bearing_and_clearance_hole_material() -> None:
    # MountingY is from the actual lower edge: width variation moves the
    # opposite edge, not half of each edge about the nominal centreline.
    lower_head_walls, upper_head_walls = [], []
    lower_hole_walls, upper_hole_walls = [], []
    for width in (10.2, 11.8):
        for row_from_lower in (4.74, 4.84):
            # The 3.8 circle plus its .10 allowance is a conservative screen,
            # not an invented catalog head-major maximum.
            lower_head_walls.append(row_from_lower - 3.90 / 2.0)
            upper_head_walls.append(width - row_from_lower - 3.90 / 2.0)
            # Native 2.591 prints 2.59 +.10/0: the accepted hole is 2.69 MAX.
            lower_hole_walls.append(row_from_lower - 2.69 / 2.0)
            upper_hole_walls.append(width - row_from_lower - 2.69 / 2.0)
    assert (min(lower_head_walls), min(upper_head_walls)) == pytest.approx((2.79, 3.41))
    assert (min(lower_hole_walls), min(upper_hole_walls)) == pytest.approx((3.395, 4.015))
    assert joint.COUNTERBORE_HEIGHT_WALL_MIN == pytest.approx(
        min(*lower_head_walls, *upper_head_walls),
    )
    assert joint.CLEARANCE_HOLE_RADIUS_MAX == pytest.approx(1.345)
    assert joint.CLEARANCE_HOLE_HEIGHT_WALL_MIN == pytest.approx(
        min(*lower_hole_walls, *upper_hole_walls),
    )


def test_stock_screw_and_blind_tap_are_one_joint_stack() -> None:
    assert screw.SKU == joint.SCREW_SKU == "91794A078"
    assert screw.THREAD == joint.SCREW_THREAD == "#2-56"
    assert (screw.MAJOR_DIA, screw.LENGTH, screw.HEAD_H, screw.HEAD_DIA) == (
        joint.SCREW_MAJOR_DIA,
        joint.SCREW_LENGTH,
        joint.SCREW_HEAD_HEIGHT,
        joint.SCREW_HEAD_DIA,
    ) == (2.1844, 7.9375, 2.1082, 3.556)
    assert joint.GRIP == pytest.approx(3.175)
    assert joint.GRIP_BAND == pytest.approx(0.13)
    assert joint.ENGAGEMENT == pytest.approx(4.7625)
    assert joint.ENGAGEMENT_MIN == pytest.approx(3.305)
    assert joint.ENGAGEMENT_MIN >= 1.5 * joint.SCREW_MAJOR_DIA
    assert joint.TAP_SPEC.thread_class == "2B"
    assert joint.TAP_SPEC.end == "blind"
    assert joint.TAP_SPEC.depth_mm == joint.DRILL_DEPTH == 6.50
    assert joint.TAP_SPEC.overrides_mm["ThreadDepth"] == joint.THREAD_DEPTH == 4.95
    assert joint.THREAD_DEPTH_BAND == 0.05
    assert lever.RIB_T == 5.00
    assert joint.LEVER_FRONT_LOCAL_Z + lever.RIB_T == pytest.approx(-71.20)
    assert lever.RIB_T - joint.LINEAR_BAND < joint.THREAD_DEPTH
    assert joint.SCREW_TIP_GAP_MIN == pytest.approx(0.0075)
    assert joint.DRILL_DEPTH_DEVIATIONS == (-0.51, 0.51)
    assert joint.DRILL_DEPTH_MIN == pytest.approx(5.99)
    assert joint.DRILL_DEPTH_MAX == pytest.approx(7.01)
    assert joint.TAP_LEAD_MARGIN_MIN == pytest.approx(0.082857142857)
    # Both the pilot cylinder and point run beyond the rib into the plate.
    assert joint.DRILL_DEPTH_MIN > lever.RIB_T + joint.LINEAR_BAND
    assert joint.DRILL_POINT_DEPTH_MAX == pytest.approx(0.94 * 0.60086)
    assert joint.DRILL_WANDER_MAX == pytest.approx(0.0396619665)
    assert joint.RECEIVER_PILOT_MATERIAL_WALL_MIN == pytest.approx(2.2103380335)


def _joint_with_values(**values):
    """Exercise the real guards with changed inputs, independent of spelling."""
    tree = ast.parse(Path(joint.__file__).read_text(encoding="utf-8"))
    replaced = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in values:
                    node.value = ast.parse(repr(values[target.id]), mode="eval").body
                    replaced.add(target.id)
    assert replaced == values.keys()
    namespace = {}
    exec(compile(ast.fix_missing_locations(tree), str(joint.__file__), "exec"), namespace)
    return namespace


def test_width_shortfall_can_make_upper_edge_the_limiting_material_wall() -> None:
    # Deliberately beyond the ordinary -.8 corner, but still above the wall
    # floor: make the upper edge active so a lower-only budget cannot pass.
    narrowed = _joint_with_values(SIDE_PLATE_HEIGHT_DEVIATIONS=(-2.0, 0.8))
    assert narrowed["COUNTERBORE_HEIGHT_WALL_MIN"] == pytest.approx(9.0 - 4.84 - 1.95)
    assert narrowed["CLEARANCE_HOLE_HEIGHT_WALL_MIN"] == pytest.approx(9.0 - 4.84 - 1.345)
    for name in (
        "BRACKET_ORIGIN", "SIDE_PLATE_Y", "BRACKET_HOLE_POINTS", "LEVER_HOLE_POINTS",
        "SCREW_POSITIONS", "GRIP", "ENGAGEMENT_MIN", "SCREW_TIP_GAP_MIN",
    ):
        assert narrowed[name] == getattr(joint, name)


@pytest.mark.parametrize("values,failure", [
    ({"SCREW_LENGTH": 7.85}, "1.5D full engagement"),
    ({"FLANGE_THICKNESS_BAND": 0.20}, "1.5D full engagement"),
    ({"SIDE_PLATE_HEIGHT_DEVIATIONS": (-8.0, 8.0)}, "rule 17"),
    ({"SIDE_PLATE_LENGTH_DEVIATIONS": (-40.0, 40.0)}, "rule 17"),
    ({"THREAD_DEPTH": 4.85}, "bottoms"),
    ({"SIDE_PLATE_HEIGHT": 8.0}, r"rule 17 \(walls and webs\) wall"),
    ({"COUNTERBORE_DIA": 3.70}, "head float"),
    ({"RECEIVER_ROW_FROM_TOP": 3.50}, "receiver pilot material wall"),
    ({"RECEIVER_ROW_FROM_TOP": 2.95}, "receiver pilot material wall"),
])
def test_joint_guards_reject_numeric_loss_of_function(values, failure: str) -> None:
    with pytest.raises(AssertionError, match=failure):
        _joint_with_values(**values)


def test_row_input_relocates_every_axis_without_changing_screw_grip_or_l_pose() -> None:
    moved = _joint_with_values(RECEIVER_ROW_FROM_TOP=3.30)
    delta = -0.05
    for name in ("BRACKET_HOLE_POINTS", "LEVER_HOLE_POINTS", "SCREW_POSITIONS"):
        for before, after in zip(getattr(joint, name), moved[name], strict=True):
            assert after == pytest.approx((before[0], before[1] + delta, before[2]))
    for name in (
        "BRACKET_ORIGIN", "SIDE_PLATE_X", "SIDE_PLATE_Y", "SIDE_PLATE_Z",
        "SEAT_PLANE_Z", "GRIP", "ENGAGEMENT", "ENGAGEMENT_MIN", "SCREW_REACH_MAX",
    ):
        assert moved[name] == getattr(joint, name)
    # A larger downward relocation consumes the lower head wall, not the upper.
    assert moved["COUNTERBORE_HEIGHT_WALL_MIN"] < joint.COUNTERBORE_HEIGHT_WALL_MIN


def _material_wall_oracle(
    rib: float, face: float, cylinder: float, radius: float, point_ratio: float, wander: float,
) -> float:
    """Independent convex minimization of the finite pilot to excluded material."""
    if cylinder >= rib:
        return face - radius - wander

    def distance(fraction: float) -> float:
        z = cylinder + fraction * radius * point_ratio
        r = radius * (1.0 - fraction)
        return math.hypot(max(rib - z, 0.0), max(face - r, 0.0))

    left, right = 0.0, 1.0
    for _ in range(100):
        a, b = (2.0 * left + right) / 3.0, (left + 2.0 * right) / 3.0
        if distance(a) < distance(b):
            right = b
        else:
            left = a
    return min(distance(0.0), distance(1.0), distance((left + right) / 2.0)) - wander


@pytest.mark.parametrize("rib,face,cylinder,radius,point_ratio,expected", [
    (5.0, 3.0, 4.0, 1.0, 0.5, math.hypot(1.0, 2.0)),
    (6.0, 1.5, 4.0, 1.0, 1.0, math.hypot(1.25, 1.25)),
    (8.0, 1.5, 4.0, 1.0, 1.0, math.hypot(3.0, 1.5)),
    (5.0, 3.0, 4.0, 1.0, 0.0, math.hypot(1.0, 2.0)),
    (5.0, 2.0, 4.0, 0.0, 0.5, math.hypot(1.0, 2.0)),
    (4.0, 3.0, 7.0, 1.0, 0.6, 2.0),
    (4.0, 0.8, 7.0, 1.0, 0.6, -0.2),
    (4.2, 0.8, 4.0, 1.0, 2.0, 0.0),
], ids=[
    "shoulder", "interior-cone", "finite-tip", "flat-point", "zero-radius",
    "plate-plane", "plane-breakout", "cone-breakout",
])
def test_material_wall_covers_actual_plane_and_finite_transition(
    rib: float, face: float, cylinder: float, radius: float, point_ratio: float, expected: float,
) -> None:
    wander = 0.125
    actual = joint.receiver_material_wall_margin(rib, face, cylinder, radius, point_ratio, wander)
    assert actual == pytest.approx(expected - wander, abs=1e-12)
    assert actual == pytest.approx(
        _material_wall_oracle(rib, face, cylinder, radius, point_ratio, wander), abs=1e-12,
    )


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, -0.1])
def test_material_wall_refuses_invalid_physical_inputs(index: int, bad: float) -> None:
    arguments = [6.0, 1.5, 4.0, 1.0, 1.0, 0.125]
    arguments[index] = bad
    with pytest.raises(ValueError, match="finite nonnegative"):
        joint.receiver_material_wall_margin(*arguments)


def test_material_wall_transition_is_continuous_and_wander_is_charged_once() -> None:
    args = (5.0, 3.0, 5.0, 1.0, 0.60086)
    assert joint.receiver_material_wall_margin(*args, 0.0) == 2.0
    assert joint.receiver_material_wall_margin(*args, 0.125) == 1.875
    epsilon = 1e-7
    before = joint.receiver_material_wall_margin(5.0, 3.0, 5.0 - epsilon, 1.0, 0.60086, 0.0)
    after = joint.receiver_material_wall_margin(5.0, 3.0, 5.0 + epsilon, 1.0, 0.60086, 0.0)
    assert before == pytest.approx(after, abs=epsilon)
    assert joint.receiver_material_wall_margin(0.0, 3.0, 7.0, 1.0, 0.6, 0.0) == 2.0


@pytest.mark.parametrize("index,value", [
    (0, 5.9), (1, 1.4), (2, 4.1), (3, 1.1), (4, 1.1), (5, 0.225),
], ids=["shallower-rib", "nearer-plane", "deeper-cylinder", "larger-radius", "longer-point", "wander"])
def test_transition_material_reacts_to_each_numeric_input(index: int, value: float) -> None:
    arguments = [6.0, 1.5, 4.0, 1.0, 1.0, 0.125]
    baseline = joint.receiver_material_wall_margin(*arguments)
    arguments[index] = value
    actual = joint.receiver_material_wall_margin(*arguments)
    assert actual < baseline
    assert actual == pytest.approx(_material_wall_oracle(*arguments), abs=1e-12)


def _printed_material_budget_oracle() -> tuple[float, float, float, float]:
    radius = (
        max(joint.TAP_DRILL_DIA, round(joint.TAP_DRILL_DIA, 2)) + joint.DRILLED_DIAMETER_PLUS
    ) / 2.0
    point = radius * joint.DRILL_POINT_H
    wander = math.tan(math.radians(joint.DRILL_WANDER_DEG)) * (joint.DRILL_DEPTH_MAX + point)
    faces = []
    for side in ("upper", "lower"):
        clearances = []
        for _x, y, _z in joint.LEVER_HOLE_POINTS:
            from_top = lever.COEFFICIENT_TOP_Y - y
            face = (
                from_top - joint.POSITION_BAND if side == "upper"
                else lever.COEFFICIENT_T - joint.LINEAR_BAND - from_top - joint.POSITION_BAND
            )
            clearances.append(_material_wall_oracle(
                lever.RIB_T - joint.LINEAR_BAND, face, joint.DRILL_DEPTH_MAX,
                radius, joint.DRILL_POINT_H, wander,
            ))
        faces.append(min(clearances))
    free_edge = min(
        lever.PLATE_W - x - joint.POSITION_BAND - radius - wander
        for x, _y, _z in joint.LEVER_HOLE_POINTS
    )
    far_end = lever.PLATE_L - 0.8 - joint.DRILL_DEPTH_MAX - point - wander
    return *faces, free_edge, far_end


def test_printed_pilot_has_continuous_material_beyond_every_uniform_rib() -> None:
    walls = _printed_material_budget_oracle()
    assert walls[:2] == pytest.approx((2.2203380335, 2.2103380335))
    assert min(walls) == pytest.approx(joint.receiver_pilot_material_wall_budget(), abs=1e-12)
    assert joint.RECEIVER_PILOT_MATERIAL_WALL_MIN == pytest.approx(min(walls), abs=1e-12)
    assert min(walls) >= joint.RECEIVER_PILOT_WALL_MIN == 2.0
    assert joint.DRILL_DEPTH_MIN > lever.RIB_T + joint.LINEAR_BAND
    assert joint.THREAD_DEPTH > lever.RIB_T - joint.LINEAR_BAND


@pytest.mark.parametrize("pilot", [1.778, 1.784])
def test_material_screen_uses_printed_pilot_and_one_deepest_point_wander(monkeypatch, pilot: float) -> None:
    monkeypatch.setattr(joint, "TAP_DRILL_DIA", pilot)
    assert joint.receiver_pilot_material_wall_budget() == pytest.approx(
        min(_printed_material_budget_oracle()), abs=1e-12,
    )


def test_material_budget_cancels_correlated_actual_top_translation(monkeypatch) -> None:
    before = joint.receiver_pilot_material_wall_budget()
    top, points = lever.COEFFICIENT_TOP_Y, joint.LEVER_HOLE_POINTS
    for offset in (-joint.LINEAR_BAND, joint.LINEAR_BAND):
        monkeypatch.setattr(lever, "COEFFICIENT_TOP_Y", top + offset)
        monkeypatch.setattr(joint, "LEVER_HOLE_POINTS", tuple(
            (x, y + offset, z) for x, y, z in points
        ))
        assert joint.receiver_pilot_material_wall_budget() == pytest.approx(before, abs=1e-12)


@pytest.mark.parametrize("name,value", [
    ("POSITION_BAND", 0.15), ("DRILLED_DIAMETER_PLUS", 0.20),
    ("DRILL_POINT_H", 2.0), ("DRILL_DEPTH_MAX", 7.40), ("DRILL_WANDER_DEG", 0.6),
])
def test_material_budget_rederives_live_pilot_inputs(monkeypatch, name: str, value: float) -> None:
    before = joint.receiver_pilot_material_wall_budget()
    monkeypatch.setattr(joint, name, value)
    assert joint.receiver_pilot_material_wall_budget() < before
    assert joint.receiver_pilot_material_wall_budget() == pytest.approx(
        min(_printed_material_budget_oracle()), abs=1e-12,
    )


def test_thinner_plate_loses_material_even_with_unchanged_rib_and_screw(monkeypatch) -> None:
    monkeypatch.setattr(lever, "COEFFICIENT_T", 6.70)
    assert joint.receiver_pilot_material_wall_budget() < joint.RECEIVER_PILOT_WALL_MIN
    with pytest.raises(AssertionError, match="receiver pilot material wall"):
        _joint_with_values()


def test_opposite_end_is_real_material_not_an_infinite_plate_assumption(monkeypatch) -> None:
    monkeypatch.setattr(lever, "PLATE_L", 10.0)
    assert joint.receiver_pilot_material_wall_budget() < joint.RECEIVER_PILOT_WALL_MIN
    with pytest.raises(AssertionError, match="receiver pilot material wall"):
        _joint_with_values()


def test_free_edge_is_real_material_not_an_infinite_plate_assumption() -> None:
    points = tuple((41.50, y, z) for _x, y, z in joint.LEVER_HOLE_POINTS)
    with pytest.raises(AssertionError, match="receiver pilot material wall"):
        _joint_with_values(LEVER_HOLE_POINTS=points)


def test_shorter_rib_does_not_remove_plate_or_change_screw_capacity(monkeypatch) -> None:
    before = joint.receiver_pilot_material_wall_budget()
    monkeypatch.setattr(lever, "RIB_T", 3.0)
    after = _joint_with_values()
    assert after["RECEIVER_PILOT_MATERIAL_WALL_MIN"] == pytest.approx(before)
    assert after["ENGAGEMENT_MIN"] == joint.ENGAGEMENT_MIN
    assert after["GRIP"] == joint.GRIP


def test_material_screen_is_independent_of_finished_thread_metadata(monkeypatch) -> None:
    before = joint.receiver_pilot_material_wall_budget()
    monkeypatch.setattr(joint, "THREAD_DEPTH", 8.0)
    monkeypatch.setattr(joint, "THREAD_DEPTH_BAND", 0.5)
    monkeypatch.setattr(joint, "SCREW_MAJOR_DIA", 4.0)
    assert joint.receiver_pilot_material_wall_budget() == before


def test_drill_limits_separate_tap_lead_from_material_wander() -> None:
    shallow = joint.THREAD_DEPTH + joint.THREAD_DEPTH_BAND + 2.0 * joint.SCREW_PITCH
    epsilon = 1e-6
    _joint_with_values(DRILL_DEPTH_DEVIATIONS=(shallow - joint.DRILL_DEPTH + epsilon, 0.51))
    with pytest.raises(AssertionError, match="bottoming-tap lead"):
        _joint_with_values(DRILL_DEPTH_DEVIATIONS=(shallow - joint.DRILL_DEPTH - epsilon, 0.51))
    ordinary = _joint_with_values()
    deeper = _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-0.51, 0.80))
    assert deeper["TAP_LEAD_MARGIN_MIN"] == ordinary["TAP_LEAD_MARGIN_MIN"]
    assert deeper["RECEIVER_PILOT_MATERIAL_WALL_MIN"] < ordinary["RECEIVER_PILOT_MATERIAL_WALL_MIN"]
    with pytest.raises(AssertionError, match="bottoming-tap lead"):
        _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-0.80, 0.80))


def test_printed_pilot_clears_pivot_and_native_spring_tap_geometry() -> None:
    pilot_radius = (
        max(joint.TAP_DRILL_DIA, round(joint.TAP_DRILL_DIA, 2))
        + joint.DRILLED_DIAMETER_PLUS
    ) / 2.0
    pilot_radius += math.tan(math.radians(joint.DRILL_WANDER_DEG)) * (
        joint.DRILL_DEPTH_MAX + pilot_radius * joint.DRILL_POINT_H
    )
    assert min(
        point[0] for point in joint.LEVER_HOLE_POINTS
    ) - pilot_radius - lever.CYL_R >= joint.RECEIVER_PILOT_WALL_MIN
    # Spring taps retain their native basic-major geometry for this independent
    # pilot clearance check. The j=0 station lies alongside the drill's depth,
    # so its conservative web is the X gap alone.
    spring_radius = THREAD_MAJOR_MM[lever.HOLE_SPEC.size] / 2.0
    spring_stations = tuple(
        lever.CHANNEL_Z0 + lever.HOLE_Z_OFFSET + j * lever.CHANNEL_PITCH
        for j in range(lever.HOLE_COUNT)
    )
    bottom = joint.LEVER_FRONT_LOCAL_Z + joint.DRILL_DEPTH + joint.DRILL_POINT_DEPTH
    spring_web = min(
        math.hypot(
            lever.HOLE_X - x, max(joint.LEVER_FRONT_LOCAL_Z - z, 0.0, z - bottom)
        )
        - pilot_radius
        - spring_radius
        for x, _y, _z in joint.LEVER_HOLE_POINTS
        for z in spring_stations
    )
    assert spring_web == pytest.approx(
        lever.HOLE_X - max(point[0] for point in joint.LEVER_HOLE_POINTS)
        - pilot_radius - spring_radius
    )
    assert spring_web >= 2.0
    # Both coefficient faces are fixed by the new asymmetric section. Test
    # the actual circle/line/R1 union, not the obsolete symmetric half-height.
    for x, y, _z in joint.LEVER_HOLE_POINTS:
        lower, upper = lever_profile.rib_bounds(x)
        assert lower < lever.COEFFICIENT_BOTTOM_Y < y
        assert y < lever.COEFFICIENT_TOP_Y < upper
        assert upper != pytest.approx(-lower)
        assert x + pilot_radius + joint.POSITION_BAND < (
            lever_profile.PROFILE.reach - joint.LINEAR_BAND
        )
        # At these two stations the closest nominal boundary lies on a flank,
        # between its circle and runout tangencies. Use its true normal.
        flank_margins = []
        for branch in (lever_profile.UPPER, lever_profile.LOWER):
            assert branch.wrap_xy[0] < x < branch.flank_xy[0]
            nx, ny = branch.normal_xy
            flank_margins.append(
                lever_profile.PROFILE.wrap_radius - nx * x - ny * y - pilot_radius
            )
        nominal_wall = lever_profile.receiver_wall_margin(x, y, pilot_radius)
        assert nominal_wall == pytest.approx(min(flank_margins))
        assert nominal_wall >= 2.0
    # Ordinary shape/plate bands retain real top/free-edge correlations.
    walls = lever_profile.receiver_pilot_wall_budget()
    assert tuple(wall.x_mm for wall in walls) == tuple(
        point[0] for point in joint.LEVER_HOLE_POINTS
    )
    for wall in walls:
        assert wall.upper_mm >= 2.0
        assert wall.lower_mm >= 2.0
        assert wall.minimum_mm >= 2.0
        assert wall.minimum_mm == pytest.approx(min(wall.upper_mm, wall.lower_mm))
    # The native spring frame is Ø0.15 RFS (code review C06), not MMC.
    # Separate X/Z extremes conservatively bound the pilot and its wander.
    spring_position = float(lever.GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"]) / 2.0
    spring_dx_min = (
        lever.HOLE_X - max(point[0] for point in joint.LEVER_HOLE_POINTS)
        - joint.LINEAR_BAND - joint.POSITION_BAND - spring_position
    )
    spring_dz_min = (
        min(spring_stations) - joint.LEVER_FRONT_LOCAL_Z - joint.LINEAR_BAND
        - spring_position - joint.DRILL_DEPTH_MAX
        - joint.DRILL_POINT_DEPTH_MAX
    )
    assert spring_dz_min < 0.0  # the j=0 station overlaps the drill's depth
    spring_web_min = (
        math.hypot(spring_dx_min, max(spring_dz_min, 0.0))
        - pilot_radius - spring_radius
    )
    assert spring_web_min == pytest.approx(spring_dx_min - pilot_radius - spring_radius)
    assert spring_web_min >= 2.0


def test_real_jam_nut_footprint_stays_clear_of_every_rib_at_ordinary_bands() -> None:
    import ch_anchor_jam_nut_spec as nut

    position_radius = float(lever.GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"]) / 2.0
    nut_inner_x = lever.HOLE_X - position_radius - nut.OD_MAX / 2.0
    reach_max = lever.RIB_REACH + joint.LINEAR_BAND
    assert nut_inner_x == pytest.approx(36.45)
    assert reach_max == pytest.approx(36.26)
    assert nut_inner_x - reach_max == pytest.approx(0.19)
    # This is positive geometric separation, not a newly invented clearance floor.
    section = lever_profile.RibProfile(reach=reach_max, blend_radius=0.0)
    probe = (nut_inner_x, lever.COEFFICIENT_BOTTOM_Y - 1e-4)
    assert section.signed_boundary_distance(*probe) < 0.0
    intrusion = lever_profile.RibProfile(reach=reach_max + 0.20, blend_radius=0.0)
    assert intrusion.signed_boundary_distance(*probe) > 0.0


def test_only_top_level_thread_overlap_is_allowed() -> None:
    pairs = interference.allowed_interference_pairs("ha-harmonic-analyzer")
    lever_path = "sm-summing-1/sm-summing-lever-1"
    expected = {
        frozenset((f"mg-magnifier-1/mg-vn-magnifying-bracket-screw-{index}", lever_path))
        for index in (1, 2)
    }
    actual = {
        pair
        for pair in pairs
        if any("mg-vn-magnifying-bracket-screw-" in name for name in pair)
    }
    assert actual == expected
    limit = interference._smooth_annulus_limit_mm3(
        joint.SCREW_MAJOR_DIA, joint.TAP_DRILL_DIA, joint.ENGAGEMENT
    )
    assert all(pairs[pair] == pytest.approx(limit) for pair in expected)
    local = interference.allowed_interference_pairs("mg-magnifier")
    assert not any(
        "mg-vn-magnifying-bracket-screw" in name for pair in local for name in pair
    )


def test_assembly_places_the_two_screws_head_out_shank_into_the_lever() -> None:
    assert magnifier.BRACKET_SCREW_POSITIONS == joint.SCREW_POSITIONS
    rows = magnifier.BRACKET_SCREW_ROWS
    # Stock frame shank points -Y; rotated axis must point machine +Z.
    shank_axis = tuple(-rows[1][index] for index in range(3))
    assert shank_axis == (0.0, 0.0, 1.0)


def test_wheel_pin_press_pair_pins_the_pin_and_bar_bore() -> None:
    import mg_wheel_axle_spec as pin
    import mg_wheel_bar_geom as bar

    pairs = interference.allowed_interference_pairs("mg-magnifier")
    limit = pairs[frozenset(("mg-wheel-axle-1", "mg-wheel-bar-1"))]
    # The pin stands in the bore over its nominal 8.9 (back end 0.60 inside
    # the 9.5 bar), inside the contract's 9.0.
    assert -pin.BACK_Y <= 9.0 < BAR_DEPTH
    assert limit == pytest.approx(
        interference._smooth_annulus_limit_mm3(pin.PIN_DIA, bar.AXLE_BORE_DIA, 9.0)
    )
