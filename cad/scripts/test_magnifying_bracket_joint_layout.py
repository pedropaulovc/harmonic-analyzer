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


def test_side_plate_is_flush_and_taller_without_moving_the_arm() -> None:
    assert bracket.FLANGE_X == joint.SIDE_PLATE_X == (-43.0, 5.0)
    assert bracket.FLANGE_Y == joint.SIDE_PLATE_Y == (-6.35, 6.35)
    assert bracket.FLANGE_Z == joint.SIDE_PLATE_Z
    back = joint.BRACKET_ORIGIN[2] + bracket.FLANGE_Z[1]
    front = joint.BRACKET_ORIGIN[2] + bracket.FLANGE_Z[0]
    assert back == pytest.approx(joint.SEAT_PLANE_Z)
    assert back - front == pytest.approx(joint.SIDE_PLATE_THICKNESS)
    assert joint.SIDE_PLATE_MACHINE_X == (-3.0, 45.0)
    mount_back = (
        installation.SUMMING_Z - summing.HEX_Z_MID + knife_mount.SUPPORT_Z_THICK / 2.0
    )
    assert front - mount_back == pytest.approx(0.6835, abs=1e-4)
    # Their plan projections may overlap; positive axial air keeps them separate.
    assert front > mount_back


def test_side_by_side_stations_have_head_clearance_and_head_bearing() -> None:
    assert joint.SCREW_MACHINE_X == (1.0, 14.7)
    assert joint.SCREW_PITCH_X == pytest.approx(13.7)
    assert joint.LEVER_HOLE_POINTS == ((16.0, 0.0, -76.2), (29.7, 0.0, -76.2))
    for bracket_point, lever_point, pose in zip(
        joint.BRACKET_HOLE_POINTS,
        joint.LEVER_HOLE_POINTS,
        joint.SCREW_POSITIONS,
        strict=True,
    ):
        assert bracket_point[0] + joint.BRACKET_ORIGIN[0] == pytest.approx(
            lever_point[0] + KNIFE[0]
        )
        assert pose == (
            lever_point[0] + KNIFE[0],
            KNIFE[1],
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
    assert joint.COUNTERBORE_END_WALL_MIN == pytest.approx(2.000)
    assert joint.COUNTERBORE_HEIGHT_WALL_MIN == pytest.approx(3.840)
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
    assert joint.RIB_DEPTH == 9.0
    assert joint.LEVER_FRONT_LOCAL_Z + joint.RIB_DEPTH == pytest.approx(-67.20)
    assert joint.RIB_DEPTH_BAND == joint.LINEAR_BAND == 0.51
    assert joint.THREAD_RIB_MARGIN_MIN == pytest.approx(3.49)
    assert joint.SCREW_TIP_GAP_MIN == pytest.approx(0.0075)
    assert joint.DRILL_DEPTH_DEVIATIONS == (-0.51, 0.51)
    assert joint.DRILL_DEPTH_MIN == pytest.approx(5.99)
    assert joint.DRILL_DEPTH_MAX == pytest.approx(7.01)
    assert joint.TAP_LEAD_MARGIN_MIN == pytest.approx(0.082857142857)
    # This is point containment, not a rule-17 bottom-wall thickness.
    assert joint.DRILL_POINT_RIB_MARGIN == pytest.approx(1.96583546)
    assert joint.DRILL_POINT_RIB_MARGIN_MIN == pytest.approx(0.876133, abs=1e-6)
    assert joint.DRILL_WANDER_MAX == pytest.approx(0.039659, abs=1e-6)


@pytest.mark.parametrize(
    ("replacement", "failure"),
    (
        ("SCREW_LENGTH = 7.9375", "1.5D full engagement"),
        ("FLANGE_THICKNESS_BAND = 0.13", "1.5D full engagement"),
        ("THREAD_DEPTH = 4.95", "bottoms"),
        ("SIDE_PLATE_HEIGHT = 12.7", r"drawing-guidelines\.md rule 17 \(walls and webs\) wall"),
        ("COUNTERBORE_DIA = 3.8", "head float"),
    ),
)
def test_joint_guards_reject_lost_margins(replacement: str, failure: str) -> None:
    source = Path(joint.__file__).read_text(encoding="utf-8")
    bad_value = {
        "SCREW_LENGTH": 7.85,
        "FLANGE_THICKNESS_BAND": 0.20,
        "THREAD_DEPTH": 4.85,
        "SIDE_PLATE_HEIGHT": 8.0,
        "COUNTERBORE_DIA": 3.70,
    }[replacement.split(" = ")[0]]
    assert source.count(replacement) == 1
    changed = source.replace(replacement, f'{replacement.split(" = ")[0]} = {bad_value}')
    with pytest.raises(AssertionError, match=failure):
        exec(compile(changed, str(joint.__file__), "exec"), {})


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


def test_drill_limits_discriminate_tap_lead_and_point_wander_boundaries() -> None:
    # Independently solve the two physical inequalities, not the guard's
    # cached margin: two pitches after the longest full thread, and the
    # whole drill point plus conservative axial wander inside the shortest rib.
    # Disable only the independent step-wall floor for these axial boundary
    # probes; ordinary-depth and dedicated step tests retain the real 2 mm.
    wander_slope = math.tan(math.radians(joint.DRILL_WANDER_DEG))
    shallow_limit = joint.THREAD_DEPTH + joint.THREAD_DEPTH_BAND + 2 * joint.SCREW_PITCH
    deep_limit = (
        (joint.RIB_DEPTH - joint.RIB_DEPTH_BAND) / (1 + wander_slope)
        - joint.DRILL_POINT_DEPTH_MAX
    )
    epsilon = 1e-6
    for limit, side, failure in (
        (shallow_limit, 0, "bottoming-tap lead"),
        (deep_limit, 1, "breaks out of the front rib"),
    ):
        for safe in (True, False):
            depths = list(joint.DRILL_DEPTH_DEVIATIONS)
            direction = 1 if side == 0 else -1
            depths[side] = limit - joint.DRILL_DEPTH + direction * epsilon * (1 if safe else -1)
            if safe:
                _joint_with_values(
                    DRILL_DEPTH_DEVIATIONS=tuple(depths), RECEIVER_WALL_MIN=0.0,
                )
            else:
                with pytest.raises(AssertionError, match=failure):
                    _joint_with_values(
                        DRILL_DEPTH_DEVIATIONS=tuple(depths), RECEIVER_WALL_MIN=0.0,
                    )

    feasible_band = min(joint.DRILL_DEPTH - shallow_limit, deep_limit - joint.DRILL_DEPTH)
    assert joint.LINEAR_BAND < feasible_band
    ordinary = _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-joint.LINEAR_BAND, joint.LINEAR_BAND))
    assert ordinary["TAP_LEAD_MARGIN_MIN"] > 0
    assert ordinary["DRILL_POINT_RIB_MARGIN_MIN"] > 0
    wider = feasible_band + epsilon
    with pytest.raises(AssertionError, match="bottoming-tap lead|breaks out of the front rib"):
        _joint_with_values(
            DRILL_DEPTH_DEVIATIONS=(-wider, wider), RECEIVER_WALL_MIN=0.0,
        )


def test_rib_depth_and_band_discriminate_point_containment_boundary() -> None:
    minimum_rib = (
        joint.DRILL_DEPTH_MAX + joint.DRILL_POINT_DEPTH_MAX
    ) * (1 + math.tan(math.radians(joint.DRILL_WANDER_DEG)))
    epsilon = 1e-6
    for name, boundary, direction in (
        ("RIB_DEPTH", minimum_rib + joint.RIB_DEPTH_BAND, 1),
        ("RIB_DEPTH_BAND", joint.RIB_DEPTH - minimum_rib, -1),
    ):
        # Isolate the pre-existing axial containment gate from the stricter,
        # independent 2 mm step-wall gate proved separately below.
        _joint_with_values(RECEIVER_WALL_MIN=0.0, **{name: boundary + direction * epsilon})
        with pytest.raises(AssertionError, match="breaks out of the front rib"):
            _joint_with_values(RECEIVER_WALL_MIN=0.0, **{name: boundary - direction * epsilon})


def _finite_step_wall_oracle(
    rib: float, floor: float, cylinder: float, radius: float, point_ratio: float, wander: float,
) -> float:
    """Project the step corner onto the physical shoulder-to-tip segment."""
    shoulder = (cylinder, radius)
    tip = (cylinder + radius * point_ratio, 0.0)
    segment = tuple(end - start for start, end in zip(shoulder, tip))
    corner = (rib, floor)
    squared_length = sum(component * component for component in segment)
    if squared_length:
        fraction = sum(
            (coordinate - start) * component
            for coordinate, start, component in zip(corner, shoulder, segment)
        ) / squared_length
        fraction = min(1.0, max(0.0, fraction))
    else:
        fraction = 0.0
    closest = tuple(start + fraction * component for start, component in zip(shoulder, segment))
    return math.dist(corner, closest) - wander


@pytest.mark.parametrize(
    "rib,floor,cylinder,radius,point_ratio,expected",
    [
        (5.0, 3.0, 4.0, 1.0, 0.5, math.hypot(1.0, 2.0)),
        (6.0, 1.5, 4.0, 1.0, 1.0, math.hypot(1.25, 1.25)),
        (8.0, 1.5, 4.0, 1.0, 1.0, math.hypot(3.0, 1.5)),
        (5.0, 3.0, 4.0, 1.0, 0.0, math.hypot(1.0, 2.0)),
        (5.0, 2.0, 4.0, 0.0, 0.5, math.hypot(1.0, 2.0)),
    ],
    ids=["shoulder", "interior-cone", "finite-tip", "full-thread-cylinder", "zero-radius"],
)
def test_step_wall_minimizes_the_exact_finite_envelope(
    rib: float, floor: float, cylinder: float, radius: float, point_ratio: float, expected: float,
) -> None:
    wander = 0.125
    actual = joint.receiver_step_wall_margin(rib, floor, cylinder, radius, point_ratio, wander)
    assert actual == pytest.approx(expected - wander, abs=1e-12)
    assert actual == pytest.approx(
        _finite_step_wall_oracle(rib, floor, cylinder, radius, point_ratio, wander),
        abs=1e-12,
    )
    if rib == 6.0:
        # A shoulder-only rule misses a closer point inside the drill cone.
        assert actual < math.hypot(rib - cylinder, floor - radius) - wander
        assert actual < math.hypot(rib - cylinder - radius * point_ratio, floor) - wander
    if rib == 8.0:
        # The perpendicular foot is beyond the physical tip; an infinite
        # cone would report an invented, smaller wall.
        infinite_line = ((rib - cylinder) + point_ratio * (floor - radius)) / math.hypot(
            1.0, point_ratio,
        )
        assert actual > infinite_line - wander + 0.1


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("nonfinite", [math.nan, math.inf, -math.inf])
def test_step_wall_refuses_every_nonfinite_geometry_input(index: int, nonfinite: float) -> None:
    arguments = [6.0, 1.5, 4.0, 1.0, 1.0, 0.125]
    arguments[index] = nonfinite
    with pytest.raises(ValueError):
        joint.receiver_step_wall_margin(*arguments)


@pytest.mark.parametrize("arguments", [
    (3.9, 1.5, 4.0, 1.0, 1.0, 0.0),
    (6.0, 1.5, -0.1, 1.0, 1.0, 0.0),
    (-0.1, 1.5, 0.0, 1.0, 1.0, 0.0),
    (6.0, 0.9, 4.0, 1.0, 1.0, 0.0),
    (6.0, -0.1, 4.0, 0.0, 1.0, 0.0),
    (6.0, 1.5, 4.0, -0.1, 1.0, 0.0),
    (6.0, 1.5, 4.0, 1.0, -0.1, 0.0),
    (6.0, 1.5, 4.0, 1.0, 1.0, -0.1),
])
def test_step_wall_refuses_violated_finite_envelope_premises(arguments: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        joint.receiver_step_wall_margin(*arguments)


def test_step_wall_accepts_closed_premise_boundaries_and_charges_wander_once() -> None:
    assert joint.receiver_step_wall_margin(4.0, 1.0, 4.0, 1.0, 0.0, 0.0) == 0.0
    bare = joint.receiver_step_wall_margin(6.0, 1.5, 4.0, 1.0, 1.0, 0.0)
    wandered = joint.receiver_step_wall_margin(6.0, 1.5, 4.0, 1.0, 1.0, 0.125)
    assert bare - wandered == pytest.approx(0.125, abs=1e-12)


@pytest.mark.parametrize("index,value", [
    (0, 5.9), (1, 1.4), (2, 4.1), (3, 1.1), (4, 1.1), (5, 0.225),
], ids=["shallower-rib", "nearer-floor", "deeper-cylinder", "larger-radius", "longer-point", "wander"])
def test_step_wall_reacts_to_each_physical_input(index: int, value: float) -> None:
    arguments = [6.0, 1.5, 4.0, 1.0, 1.0, 0.125]
    baseline = joint.receiver_step_wall_margin(*arguments)
    arguments[index] = value
    actual = joint.receiver_step_wall_margin(*arguments)
    assert actual < baseline
    assert actual == pytest.approx(_finite_step_wall_oracle(*arguments), abs=1e-12)


def _printed_pilot_step_budget_oracle() -> float:
    drill_radius = (
        max(joint.TAP_DRILL_DIA, round(joint.TAP_DRILL_DIA, 2)) + joint.DRILLED_DIAMETER_PLUS
    ) / 2.0
    wander = math.tan(math.radians(joint.DRILL_WANDER_DEG)) * (
        joint.DRILL_DEPTH_MAX + drill_radius * joint.DRILL_POINT_H
    )
    return min(
        _finite_step_wall_oracle(
            joint.RIB_DEPTH - joint.RIB_DEPTH_BAND, floor,
            joint.DRILL_DEPTH_MAX, drill_radius, joint.DRILL_POINT_H, wander,
        )
        for _, y, _ in joint.LEVER_HOLE_POINTS
        for floor in (
            lever.COEFFICIENT_TOP_Y - y - joint.POSITION_BAND,
            lever.COEFFICIENT_T - joint.LINEAR_BAND
            - (lever.COEFFICIENT_TOP_Y - y) - joint.POSITION_BAND,
        )
    )


def _thread_cutting_step_budget_oracle() -> float:
    return min(
        _finite_step_wall_oracle(
            joint.RIB_DEPTH - joint.RIB_DEPTH_BAND, floor,
            joint.THREAD_CUTTING_ENVELOPE_DEPTH_MAX,
            joint.THREAD_CUTTING_ENVELOPE_DIA_MAX / 2.0,
            0.0, joint.THREAD_CUTTING_PROOF_RESERVE,
        )
        for _, y, _ in joint.LEVER_HOLE_POINTS
        for floor in (
            lever.COEFFICIENT_TOP_Y - y - joint.POSITION_BAND,
            lever.COEFFICIENT_T - joint.LINEAR_BAND
            - (lever.COEFFICIENT_TOP_Y - y) - joint.POSITION_BAND,
        )
    )


@pytest.mark.parametrize("pilot", [1.778, 1.784])
def test_pilot_step_budget_uses_printed_pilot_plus_allowance_and_one_whole_wander(
    monkeypatch, pilot: float,
) -> None:
    calls = []
    original = joint.receiver_step_wall_margin

    def record(*arguments):
        calls.append(arguments)
        return original(*arguments)

    monkeypatch.setattr(joint, "TAP_DRILL_DIA", pilot)
    monkeypatch.setattr(joint, "receiver_step_wall_margin", record)
    actual = joint.receiver_pilot_step_wall_budget()
    radius = (max(pilot, round(pilot, 2)) + 0.10) / 2.0
    wander = math.tan(math.radians(0.3)) * (7.01 + radius * joint.DRILL_POINT_H)
    assert actual == pytest.approx(_printed_pilot_step_budget_oracle(), abs=1e-12)
    assert len(calls) == len(joint.LEVER_HOLE_POINTS)
    for rib, floor, depth, envelope_radius, point_ratio, drift in calls:
        assert rib == pytest.approx(8.49)
        assert floor == pytest.approx(2.49)  # actual-top row, no extra top-position band
        assert drift == pytest.approx(wander, abs=1e-12)
        assert point_ratio == joint.DRILL_POINT_H
        assert envelope_radius == pytest.approx(radius)
        assert depth == pytest.approx(7.01)
    if pilot == 1.778:
        assert radius == pytest.approx((1.78 + 0.10) / 2.0)
        assert actual != pytest.approx(
            math.hypot(8.49 - 7.01, 2.49 - (pilot + 0.10) / 2.0) - wander,
            abs=1e-5,
        )


def test_pilot_step_budget_cancels_top_translation_but_checks_thin_plate_lower_floor(monkeypatch) -> None:
    baseline = joint.receiver_pilot_step_wall_budget()
    top = lever.COEFFICIENT_TOP_Y
    points = joint.LEVER_HOLE_POINTS
    for offset in (-joint.LINEAR_BAND / 2.0, joint.LINEAR_BAND / 2.0):
        monkeypatch.setattr(lever, "COEFFICIENT_TOP_Y", top + offset)
        monkeypatch.setattr(joint, "LEVER_HOLE_POINTS", tuple(
            (x, y + offset, z) for x, y, z in points
        ))
        assert joint.receiver_pilot_step_wall_budget() == pytest.approx(baseline, abs=1e-12)
    monkeypatch.setattr(lever, "COEFFICIENT_TOP_Y", top)
    monkeypatch.setattr(joint, "LEVER_HOLE_POINTS", points)
    monkeypatch.setattr(lever, "COEFFICIENT_T", 4.90)
    lower_floor = 4.90 - joint.LINEAR_BAND - top - joint.POSITION_BAND
    assert lower_floor == pytest.approx(1.80)
    assert lower_floor < top - joint.POSITION_BAND
    assert joint.receiver_pilot_step_wall_budget() == pytest.approx(_printed_pilot_step_budget_oracle(), abs=1e-12)
    assert joint.receiver_pilot_step_wall_budget() < joint.RECEIVER_WALL_MIN
    with pytest.raises(AssertionError, match="receiver pilot step wall"):
        _joint_with_values()


@pytest.mark.parametrize("name,value", [
    ("RIB_DEPTH", 8.8), ("POSITION_BAND", 0.15), ("DRILLED_DIAMETER_PLUS", 0.20),
    ("DRILL_POINT_H", 2.0), ("DRILL_DEPTH_MAX", 7.10),
])
def test_pilot_step_budget_rederives_changed_geometry(monkeypatch, name: str, value: float) -> None:
    baseline = joint.receiver_pilot_step_wall_budget()
    monkeypatch.setattr(joint, name, value)
    actual = joint.receiver_pilot_step_wall_budget()
    assert actual < baseline
    assert actual == pytest.approx(_printed_pilot_step_budget_oracle(), abs=1e-12)


def test_pilot_step_proof_is_independent_of_actual_thread_cutting_envelope(monkeypatch) -> None:
    pilot = joint.receiver_pilot_step_wall_budget()
    baseline = joint.receiver_thread_cutting_step_wall_budget()
    assert baseline == pytest.approx(2.764318, abs=1e-6)
    assert baseline == pytest.approx(_thread_cutting_step_budget_oracle(), abs=1e-12)
    monkeypatch.setattr(joint, "THREAD_CUTTING_ENVELOPE_DIA_MAX", 2.60)
    assert joint.receiver_thread_cutting_step_wall_budget() < baseline
    assert joint.receiver_thread_cutting_step_wall_budget() == pytest.approx(
        _thread_cutting_step_budget_oracle(), abs=1e-12,
    )
    assert joint.receiver_pilot_step_wall_budget() == pilot
    monkeypatch.setattr(joint, "THREAD_CUTTING_ENVELOPE_DEPTH_MAX", 7.0)
    assert joint.receiver_thread_cutting_step_wall_budget() < joint.RECEIVER_WALL_MIN
    assert joint.receiver_thread_cutting_step_wall_budget() == pytest.approx(
        _thread_cutting_step_budget_oracle(), abs=1e-12,
    )
    assert joint.receiver_pilot_step_wall_budget() == pilot
    # Native full-thread metadata/basic screw diameter are not pilot inputs.
    monkeypatch.setattr(joint, "THREAD_DEPTH", 8.0)
    monkeypatch.setattr(joint, "THREAD_DEPTH_BAND", 0.5)
    monkeypatch.setattr(joint, "SCREW_MAJOR_DIA", 4.0)
    assert joint.receiver_pilot_step_wall_budget() == pilot
    with pytest.raises(AssertionError, match="receiver thread-cutting step wall"):
        _joint_with_values(THREAD_CUTTING_ENVELOPE_DIA_MAX=2.60,
                           THREAD_CUTTING_ENVELOPE_DEPTH_MAX=7.0)


def test_cutting_envelope_axial_budget_has_real_lead_boundary() -> None:
    assert joint.THREAD_CUTTING_ENVELOPE_DIA_MAX == 2.40
    assert joint.THREAD_CUTTING_ENVELOPE_DEPTH_MAX == 6.00
    assert joint.THREAD_CUTTING_PROOF_RESERVE == 0.04
    assert joint.THREAD_CUTTING_AUXILIARY_DEPTH_MAX == pytest.approx(1.05)
    assert joint.THREAD_CUTTING_LEAD_MARGIN_MIN == pytest.approx(0.092857142857)
    boundary = joint.THREAD_DEPTH + joint.THREAD_DEPTH_BAND + 2 * joint.SCREW_PITCH
    safe = _joint_with_values(THREAD_CUTTING_ENVELOPE_DEPTH_MAX=boundary + 1e-6)
    assert safe["THREAD_CUTTING_LEAD_MARGIN_MIN"] == pytest.approx(1e-6)
    with pytest.raises(AssertionError, match="thread-cutting.*lead|lead.*thread-cutting"):
        _joint_with_values(THREAD_CUTTING_ENVELOPE_DEPTH_MAX=boundary - 1e-6)


@pytest.mark.parametrize("name", [
    "THREAD_CUTTING_ENVELOPE_DEPTH_MAX", "THREAD_CUTTING_ENVELOPE_DIA_MAX",
])
def test_thread_cutting_step_guard_discriminates_depth_and_diameter_boundaries(name: str) -> None:
    rib, floor, reserve = 8.49, 2.49, 0.04
    target = joint.RECEIVER_WALL_MIN + reserve
    if name.endswith("DEPTH_MAX"):
        boundary = rib - math.sqrt(target**2 - (floor - 1.20)**2)
    else:
        # At the approved depth even a zero floor ligament is >2 mm;
        # deepen within the rib first so diameter can independently lose wall.
        boundary = 2 * (floor - math.sqrt(target**2 - (rib - 7.0)**2))
    values = {} if name.endswith("DEPTH_MAX") else {"THREAD_CUTTING_ENVELOPE_DEPTH_MAX": 7.0}
    safe = _joint_with_values(**values, **{name: boundary - 1e-6})
    assert safe["RECEIVER_THREAD_CUTTING_STEP_WALL_MIN"] > 2.0
    assert safe["RECEIVER_PILOT_STEP_WALL_MIN"] == joint.RECEIVER_PILOT_STEP_WALL_MIN
    with pytest.raises(AssertionError, match="receiver thread-cutting step wall"):
        _joint_with_values(**values, **{name: boundary + 1e-6})


def test_thread_cutting_step_uses_actual_axis_bands_and_reserve_once_not_pilot_wander(monkeypatch) -> None:
    calls = []
    original = joint.receiver_step_wall_margin

    def record(*arguments):
        calls.append(arguments)
        return original(*arguments)

    monkeypatch.setattr(joint, "receiver_step_wall_margin", record)
    baseline = joint.receiver_thread_cutting_step_wall_budget()
    assert len(calls) == len(joint.LEVER_HOLE_POINTS)
    for arguments in calls:
        assert arguments == pytest.approx((8.49, 2.49, 6.0, 1.2, 0.0, 0.04))
    assert baseline == pytest.approx(math.hypot(8.49 - 6.0, 2.49 - 1.2) - 0.04)
    monkeypatch.setattr(joint, "DRILL_WANDER_DEG", 3.0)
    monkeypatch.setattr(joint, "DRILL_WANDER_MAX", 1.0)
    assert joint.receiver_thread_cutting_step_wall_budget() == baseline
    monkeypatch.setattr(joint, "THREAD_CUTTING_PROOF_RESERVE", 0.08)
    assert joint.receiver_thread_cutting_step_wall_budget() == pytest.approx(baseline - 0.04)


def test_real_pilot_step_guard_rejects_old_receiver_even_though_the_point_stays_contained() -> None:
    old = _joint_with_values(RIB_DEPTH=8.20, RECEIVER_WALL_MIN=0.0)
    assert old["DRILL_POINT_RIB_MARGIN_MIN"] > 0.0
    assert old["RECEIVER_PILOT_STEP_WALL_MIN"] == pytest.approx(1.653, abs=0.001)
    assert old["RECEIVER_PILOT_STEP_WALL_MIN"] < 2.0
    with pytest.raises(AssertionError, match="receiver pilot step wall"):
        _joint_with_values(RIB_DEPTH=8.20)
    approved = _joint_with_values(RIB_DEPTH=9.00)
    assert approved["RECEIVER_WALL_MIN"] == 2.0
    assert approved["RECEIVER_PILOT_STEP_WALL_MIN"] == pytest.approx(2.103, abs=0.001)
    assert approved["RECEIVER_PILOT_STEP_WALL_MIN"] == pytest.approx(_printed_pilot_step_budget_oracle(), abs=1e-12)
    assert approved["RECEIVER_PILOT_STEP_WALL_MIN"] >= approved["RECEIVER_WALL_MIN"]


def test_real_pilot_step_guard_uses_maximum_positive_drill_deviation_not_the_low_limit() -> None:
    ordinary = _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-0.51, 0.51))
    shallower_low = _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-0.40, 0.51))
    deeper_high = _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-0.51, 0.60))
    assert shallower_low["TAP_LEAD_MARGIN_MIN"] > ordinary["TAP_LEAD_MARGIN_MIN"]
    assert shallower_low["RECEIVER_PILOT_STEP_WALL_MIN"] == ordinary["RECEIVER_PILOT_STEP_WALL_MIN"]
    assert deeper_high["RECEIVER_PILOT_STEP_WALL_MIN"] < ordinary["RECEIVER_PILOT_STEP_WALL_MIN"]
    # +/-0.80 still loses tap lead; even retaining the valid -0.51 limit
    # cannot make a +0.80 drill pass the independent pilot step-wall requirement.
    with pytest.raises(AssertionError, match="bottoming-tap lead"):
        _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-0.80, 0.80))
    axial_only = _joint_with_values(
        DRILL_DEPTH_DEVIATIONS=(-0.51, 0.80), RECEIVER_WALL_MIN=0.0,
    )
    assert axial_only["DRILL_POINT_RIB_MARGIN_MIN"] > 0.0
    assert axial_only["RECEIVER_PILOT_STEP_WALL_MIN"] < 2.0
    with pytest.raises(AssertionError, match="receiver pilot step wall"):
        _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-0.51, 0.80))


def test_required_cutting_envelope_clears_pivot_and_native_spring_tap_geometry() -> None:
    thread_radius = (
        joint.THREAD_CUTTING_ENVELOPE_DIA_MAX / 2.0 + joint.THREAD_CUTTING_PROOF_RESERVE
    )
    assert min(
        point[0] for point in joint.LEVER_HOLE_POINTS
    ) - thread_radius - lever.CYL_R == pytest.approx(2.06)
    assert (
        min(point[0] for point in joint.LEVER_HOLE_POINTS) - thread_radius > lever.CYL_R
    )
    # The bracket removal requirement is bounded; spring taps retain their
    # native basic-major geometry here, not an unqualified physical-tool claim.
    # Their perpendicular Y axes remain outside the bracket cutting envelope.
    # On the cam plane (#1292) the j=0 station lies alongside the drill's depth,
    # so that web is the X gap alone.
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
        - thread_radius
        - spring_radius
        for x, _y, _z in joint.LEVER_HOLE_POINTS
        for z in spring_stations
    )
    assert spring_web == pytest.approx(7.1575, abs=1e-4)
    assert spring_web >= 2.0
    # Both coefficient faces are fixed by the new asymmetric section. Test
    # the actual circle/line/R1 union, not the obsolete symmetric half-height.
    for x, y, _z in joint.LEVER_HOLE_POINTS:
        lower, upper = lever_profile.rib_bounds(x)
        assert lower < lever.COEFFICIENT_BOTTOM_Y < y
        assert y < lever.COEFFICIENT_TOP_Y < upper
        assert upper != pytest.approx(-lower)
        assert x + thread_radius + joint.POSITION_BAND < (
            lever_profile.PROFILE.reach - joint.LINEAR_BAND
        )
        # At these two stations the closest nominal boundary lies on a flank,
        # between its circle and runout tangencies. Use its true normal.
        flank_margins = []
        for branch in (lever_profile.UPPER, lever_profile.LOWER):
            assert branch.wrap_xy[0] < x < branch.flank_xy[0]
            nx, ny = branch.normal_xy
            flank_margins.append(
                lever_profile.PROFILE.wrap_radius - nx * x - ny * y - thread_radius
            )
        nominal_wall = lever_profile.receiver_wall_margin(x, y, thread_radius)
        assert nominal_wall == pytest.approx(min(flank_margins))
        assert nominal_wall >= 2.0
    # Ordinary shape/plate bands retain real top/free-edge correlations.
    # This bounds conforming removal, not a claim that a stock tap is qualified.
    walls = lever_profile.receiver_wall_budget()
    assert tuple(wall.x_mm for wall in walls) == tuple(
        point[0] for point in joint.LEVER_HOLE_POINTS
    )
    for wall in walls:
        assert wall.upper_mm >= 2.0
        assert wall.lower_mm >= 2.0
        assert wall.minimum_mm >= 2.0
        assert wall.minimum_mm == pytest.approx(min(wall.upper_mm, wall.lower_mm))
    # The native spring frame is Ø0.15 RFS (code review C06), not MMC.
    # Separate X/Z extremes conservatively bound the same requirement radius.
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
        - thread_radius - spring_radius
    )
    assert spring_web_min == pytest.approx(spring_dx_min - thread_radius - spring_radius)
    assert spring_web_min >= 2.0


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
