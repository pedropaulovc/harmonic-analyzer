"""Offline geometry, stock and recipe contracts for the magnifier's angle joint."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _interference_contracts as interference
import build_mg_magnifier_assembly as magnifier
import build_mg_magnifying_bracket as bracket
import build_sm_summing_assembly as summing
import build_sm_summing_lever as lever_build
import dt_cone_pivot_post_installation as installation
import magnifying_bracket_joint_layout as joint
import sm_knife_mount_spec as knife_mount
import sm_summing_lever_spec as lever
import vn_magnifying_bracket_screw_spec as screw
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


def test_side_by_side_stations_have_counterbore_and_head_bearing() -> None:
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
            joint.SIDE_PLATE_FRONT_Z + joint.COUNTERBORE_DEPTH,
        )
    assert joint.CLEARANCE_SPEC.kind == "counterbore_fillister"
    assert joint.CLEARANCE_SPEC.size == "#2"
    assert joint.CLEARANCE_SPEC.fit == "normal"
    assert joint.CLEARANCE_SPEC.end == "through_all"
    assert joint.CLEARANCE_SPEC.overrides_mm == {
        "HoleDiameter": 2.591,
        "CounterBoreDiameter": 3.8,
        "CounterBoreDepth": 1.55,
    }
    assert joint.SCREW_MAJOR_DIA < joint.CLEARANCE_DIA < joint.SCREW_HEAD_DIA
    assert joint.COUNTERBORE_DIA - joint.SCREW_HEAD_DIA == pytest.approx(0.244)
    assert joint.HEAD_FLOAT_MIN == pytest.approx(0.122)
    assert joint.HEAD_POSITION_MISMATCH_MAX == pytest.approx(0.10)
    assert joint.HEAD_FLOAT_MIN >= joint.HEAD_POSITION_MISMATCH_MAX
    assert joint.GRIP_MIN == pytest.approx(1.525)
    assert joint.COUNTERBORE_END_WALL_MIN == pytest.approx(2.000)
    assert joint.COUNTERBORE_HEIGHT_WALL_MIN == pytest.approx(3.840)
    assert joint.HEAD_PROTRUSION == pytest.approx(0.5582)
    # A flush head cannot keep the full-thread envelope inside the 5.08 rib.
    flush_reach = joint.SCREW_LENGTH - joint.SIDE_PLATE_THICKNESS + joint.SCREW_HEAD_HEIGHT
    assert flush_reach == pytest.approx(5.2832)
    assert flush_reach > joint.RIB_DEPTH
    head_air = (
        min(joint.SCREW_MACHINE_X) - joint.SCREW_HEAD_DIA / 2.0
        - (KNIFE[0] + knife_mount.BLK_HALF_X)
    )
    assert head_air == pytest.approx(2.222)
    # Receiver stations follow the lever's real free edge: its width band
    # adds a whole-part translation relative to the pivot/knife line.
    assert head_air - joint.POSITION_BAND - 2.0 * joint.LINEAR_BAND == pytest.approx(1.152)


def test_stock_screw_and_blind_tap_are_one_joint_stack() -> None:
    assert screw.SKU == joint.SCREW_SKU == "91794A077"
    assert screw.THREAD == joint.SCREW_THREAD == "#2-56"
    assert (screw.MAJOR_DIA, screw.LENGTH, screw.HEAD_H, screw.HEAD_DIA) == (
        joint.SCREW_MAJOR_DIA,
        joint.SCREW_LENGTH,
        joint.SCREW_HEAD_HEIGHT,
        joint.SCREW_HEAD_DIA,
    ) == (2.1844, 6.35, 2.1082, 3.556)
    assert joint.GRIP == pytest.approx(1.625)
    assert joint.GRIP_BAND == pytest.approx(0.10)
    assert joint.ENGAGEMENT == pytest.approx(4.725)
    assert joint.ENGAGEMENT_MIN == pytest.approx(3.2975)
    assert joint.ENGAGEMENT_MIN >= 1.5 * joint.SCREW_MAJOR_DIA
    assert joint.TAP_SPEC.thread_class == "2B"
    assert joint.TAP_SPEC.end == "blind"
    assert joint.TAP_SPEC.depth_mm == joint.DRILL_DEPTH == 6.05
    assert joint.TAP_SPEC.overrides_mm["ThreadDepth"] == joint.THREAD_DEPTH == 4.95
    assert joint.THREAD_RIB_MARGIN_MIN == pytest.approx(0.03)
    assert joint.SCREW_TIP_GAP_MIN == pytest.approx(0.075)
    assert joint.TAP_LEAD_MARGIN_MIN == pytest.approx(0.042857142857)
    assert joint.DRILL_POINT_RIB_MARGIN == pytest.approx(-1.50416454)
    assert joint.DRILL_POINT_RIB_MARGIN_MIN == pytest.approx(-1.68420754)
    # The user permits ONLY this small-diameter continuation in the thin plate.
    assert joint.DRILL_LATERAL_WALL_MIN == pytest.approx(1.501)


@pytest.mark.parametrize(
    ("replacement", "failure"),
    (
        ("SCREW_LENGTH = 6.35", "1.5D full engagement"),
        ("COUNTERBORE_DEPTH = 1.55", "1.5D full engagement"),
        ("THREAD_DEPTH = 4.95", "bottoms"),
        ("RIB_DEPTH = 5.08", "beyond the front rib"),
        ("DRILL_DEPTH = 6.05", "bottoming-tap lead"),
        ("LEVER_PLATE_THICKNESS_BAND = 0.05", "rule-12 wall"),
        ("COUNTERBORE_DIA = 3.8", "head float"),
    ),
)
def test_joint_guards_reject_lost_margins(replacement: str, failure: str) -> None:
    source = Path(joint.__file__).read_text(encoding="utf-8")
    bad_value = {
        "SCREW_LENGTH": 6.30,
        "COUNTERBORE_DEPTH": 1.50,
        "THREAD_DEPTH": 4.85,
        "RIB_DEPTH": 5.04,
        "DRILL_DEPTH": 6.00,
        "LEVER_PLATE_THICKNESS_BAND": 0.10,
        "COUNTERBORE_DIA": 3.70,
    }[replacement.split(" = ")[0]]
    assert source.count(replacement) == 1
    changed = source.replace(replacement, f'{replacement.split(" = ")[0]} = {bad_value}')
    with pytest.raises(AssertionError, match=failure):
        exec(compile(changed, str(joint.__file__), "exec"), {})


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
    row_max = joint.POSITION_BAND + joint.LEVER_PLATE_THICKNESS_BAND / 2.0
    rib_wall_min = (
        (arc_min * from_slant_end_min - width_max * row_max)
        / math.hypot(arc_min, width_max) - thread_radius
    )
    assert rib_wall_min == pytest.approx(3.41324, abs=1e-5)
    assert rib_wall_min >= 2.0
    # The native spring frame is Ø0.30 RFS, not the older assessment's
    # proposed Ø0.15 MMC. Separate X/Z extremes are conservative.
    spring_position = float(lever.GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"]) / 2.0
    spring_dx_min = (
        lever.HOLE_X - max(point[0] for point in joint.LEVER_HOLE_POINTS)
        - joint.LINEAR_BAND - joint.POSITION_BAND - spring_position
    )
    spring_dz_min = (
        min(spring_stations) - joint.LEVER_FRONT_LOCAL_Z - joint.LINEAR_BAND
        - spring_position - joint.DRILL_DEPTH - joint.DRILL_DEPTH_BAND
        - joint.DRILL_POINT_DEPTH_MAX
    )
    assert spring_dz_min < 0.0  # the j=0 station overlaps the drill's depth
    spring_web_min = (
        math.hypot(spring_dx_min, max(spring_dz_min, 0.0)) - thread_radius - spring_radius
    )
    assert spring_web_min == pytest.approx(6.59530, abs=1e-5)
    assert spring_web_min >= 2.0


def test_only_top_level_thread_overlap_is_allowed() -> None:
    pairs = interference.allowed_interference_pairs("ha-harmonic-analyzer")
    lever_path = "sm-summing-1/sm-summing-lever-1"
    expected = {
        frozenset((f"mg-magnifier-1/vn-magnifying-bracket-screw-{index}", lever_path))
        for index in (1, 2)
    }
    actual = {
        pair
        for pair in pairs
        if any("vn-magnifying-bracket-screw-" in name for name in pair)
    }
    assert actual == expected
    limit = interference._smooth_annulus_limit_mm3(
        joint.SCREW_MAJOR_DIA, joint.TAP_DRILL_DIA, joint.ENGAGEMENT
    )
    assert all(pairs[pair] == pytest.approx(limit) for pair in expected)
    local = interference.allowed_interference_pairs("mg-magnifier")
    assert not any(
        "vn-magnifying-bracket-screw" in name for pair in local for name in pair
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
    assert limit == pytest.approx(
        interference._smooth_annulus_limit_mm3(
            pin.PIN_DIA, bar.AXLE_BORE_DIA, bar.BAR_DEPTH
        )
    )
