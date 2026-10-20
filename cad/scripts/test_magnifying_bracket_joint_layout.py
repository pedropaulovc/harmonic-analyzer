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
import build_sm_summing_lever as lever_build
import _cone_axis_constants as installation
import magnifying_bracket_joint_layout as joint
import sm_knife_mount_spec as knife_mount
import sm_summing_lever_spec as lever
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
    assert joint.RIB_DEPTH == 8.2
    assert joint.RIB_DEPTH_BAND == joint.LINEAR_BAND == 0.51
    assert joint.THREAD_RIB_MARGIN_MIN == pytest.approx(2.69)
    assert joint.SCREW_TIP_GAP_MIN == pytest.approx(0.0075)
    assert joint.DRILL_DEPTH_DEVIATIONS == (-0.51, 0.51)
    assert joint.DRILL_DEPTH_MIN == pytest.approx(5.99)
    assert joint.DRILL_DEPTH_MAX == pytest.approx(7.01)
    assert joint.TAP_LEAD_MARGIN_MIN == pytest.approx(0.082857142857)
    # This is point containment, not a rule-17 bottom-wall thickness.
    assert joint.DRILL_POINT_RIB_MARGIN == pytest.approx(1.16583546)
    assert joint.DRILL_POINT_RIB_MARGIN_MIN == pytest.approx(0.076133, abs=1e-6)
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
                _joint_with_values(DRILL_DEPTH_DEVIATIONS=tuple(depths))
            else:
                with pytest.raises(AssertionError, match=failure):
                    _joint_with_values(DRILL_DEPTH_DEVIATIONS=tuple(depths))

    feasible_band = min(joint.DRILL_DEPTH - shallow_limit, deep_limit - joint.DRILL_DEPTH)
    assert joint.LINEAR_BAND < feasible_band
    ordinary = _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-joint.LINEAR_BAND, joint.LINEAR_BAND))
    assert ordinary["TAP_LEAD_MARGIN_MIN"] > 0
    assert ordinary["DRILL_POINT_RIB_MARGIN_MIN"] > 0
    wider = feasible_band + epsilon
    with pytest.raises(AssertionError, match="bottoming-tap lead|breaks out of the front rib"):
        _joint_with_values(DRILL_DEPTH_DEVIATIONS=(-wider, wider))


def test_rib_depth_and_band_discriminate_point_containment_boundary() -> None:
    minimum_rib = (
        joint.DRILL_DEPTH_MAX + joint.DRILL_POINT_DEPTH_MAX
    ) * (1 + math.tan(math.radians(joint.DRILL_WANDER_DEG)))
    epsilon = 1e-6
    for name, boundary, direction in (
        ("RIB_DEPTH", minimum_rib + joint.RIB_DEPTH_BAND, 1),
        ("RIB_DEPTH_BAND", joint.RIB_DEPTH - minimum_rib, -1),
    ):
        _joint_with_values(**{name: boundary + direction * epsilon})
        with pytest.raises(AssertionError, match="breaks out of the front rib"):
            _joint_with_values(**{name: boundary - direction * epsilon})


def test_stations_clear_the_pivot_cylinder_and_channel_spring_taps() -> None:
    thread_radius = joint.SCREW_MAJOR_DIA / 2.0
    assert min(
        point[0] for point in joint.LEVER_HOLE_POINTS
    ) - thread_radius - lever.CYL_R == pytest.approx(2.2078)
    assert (
        min(point[0] for point in joint.LEVER_HOLE_POINTS) - thread_radius > lever.CYL_R
    )
    # Perpendicular spring taps run along Y: their nearest possible X/Z point
    # remains far outside either longitudinal bracket drill's major envelope.
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
    assert spring_web == pytest.approx(7.3053, abs=1e-4)
    assert spring_web >= 2.0
    # The receiver rib is the build's own -Z edge-rib profile: a slant from the
    # arc top, clipped by a vertical end face at RIB_PLATE_REACH. Its x-intercept
    # comes from two profile points, so a rib pulled in to a point at the end
    # face (slant_reach == reach) is measured as built, not as the plate's width.
    reach = lever_build.RIB_PLATE_REACH
    rise = lever_build.edge_rib_half_height(0.0)
    end_rise = lever_build.edge_rib_half_height(reach)
    slant_reach = reach * rise / (rise - end_rise)
    tap_x = max(point[0] for point in joint.LEVER_HOLE_POINTS)
    # The whole thread envelope sits inboard of the end face, under the slant.
    assert tap_x + thread_radius + joint.POSITION_BAND < reach - joint.LINEAR_BAND
    rib_half_height = lever_build.edge_rib_half_height(tap_x)
    rib_normal_margin = (
        rib_half_height / math.hypot(1.0, rise / slant_reach) - thread_radius
    )
    assert rib_normal_margin == pytest.approx(3.69158, abs=1e-5)
    arc_min = rise - joint.LINEAR_BAND
    width_max = slant_reach + joint.LINEAR_BAND
    from_slant_end_min = slant_reach - tap_x - joint.POSITION_BAND
    # The row is located from the plate top, which the plate's title-block
    # thickness band moves by half that band about the pivot mid-plane; the
    # drill wanders laterally at its deepest reach.
    row_max = joint.POSITION_BAND + joint.LINEAR_BAND / 2.0
    rib_wall_min = (
        (arc_min * from_slant_end_min - width_max * row_max)
        / math.hypot(arc_min, width_max) - thread_radius - joint.DRILL_WANDER_MAX
    )
    assert rib_wall_min == pytest.approx(3.15502, abs=1e-5)
    assert rib_wall_min >= 2.0
    # The native spring frame is Ø0.15 RFS (code review C06), not MMC.
    # Separate X/Z extremes are conservative.
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
        - thread_radius - spring_radius - joint.DRILL_WANDER_MAX
    )
    assert spring_web_min == pytest.approx(6.63064, abs=1e-5)
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
