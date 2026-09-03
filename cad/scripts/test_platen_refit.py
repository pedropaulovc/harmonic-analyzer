"""SolidWorks-free contracts for the ch30-p002 platen-system refit."""

from __future__ import annotations

import math

import build_paper_drive_assembly as assembly
import build_platen as platen
import build_platen_clip as clip
import build_platen_guide as guide
import build_platen_paper as paper
import build_platen_rack as rack
import build_support_bar as support


def test_platen_envelope_preserves_fitted_top_left_and_ratio() -> None:
    assert math.isclose(platen.PLATE_HEIGHT * 2.0, platen.PLATE_WIDTH)
    assert math.isclose(assembly.PLATE_X0, -33.213)
    assert math.isclose(assembly.PLATE_Y0 + platen.PLATE_HEIGHT, 408.054)


def test_platen_furniture_cascades_with_resized_envelope() -> None:
    assert math.isclose(rack.BAR_LENGTH, platen.PLATE_WIDTH)
    assert math.isclose(guide.GUIDE_LENGTH, platen.PLATE_WIDTH)
    assert guide.SCREW_STATION_X == platen.GUIDE_HOLE_X

    clip_y0 = platen.PLATE_HEIGHT - clip.CLIP_LENGTH
    assert math.isclose(platen.SOCKET_XY[0][1], clip_y0 + clip.HOLE_INSET)
    assert math.isclose(platen.SOCKET_XY[1][1], platen.PLATE_HEIGHT - clip.HOLE_INSET)
    side_margin = (platen.PLATE_WIDTH - paper.PAPER_WIDTH) / 2.0
    assert math.isclose(side_margin, 18.2007)
    assert math.isclose(
        platen.PLATE_HEIGHT - paper.PAPER_HEIGHT - 3.0,
        51.32,
    )


def test_platen_clip_is_one_center_bridged_sheet() -> None:
    assert clip.CLIP_THICKNESS == clip.SHEET_T == 0.8
    assert math.isclose(
        clip.SCREW_RAIL_WIDTH + clip.NOTCH_WIDTH + clip.SPRING_RAIL_WIDTH,
        clip.CLIP_WIDTH,
    )
    assert math.isclose(
        2.0 * clip.NOTCH_LENGTH + clip.CENTER_BRIDGE_LENGTH,
        clip.CLIP_LENGTH,
    )
    assert clip.CENTER_BRIDGE_LENGTH == 5.0
    assert clip.MODEL_FEATURES == (
        "FlatRail",
        "CenterBridge",
        "SpringArch",
        "RoundedSpringEnds",
        "ScrewHoles",
    )
    assert clip.BOSS_DRIVES == {
        "FlatRail": ('"SheetT"',),
        "CenterBridge": ('"SheetT"',),
        "SpringArch": ('"SpringRailW"', '"SpringRailY0"'),
        "RoundedSpringEnds": ('"SheetT"',),
    }
    spring_plan_area = (
        (clip.CLIP_LENGTH - 2.0 * clip.SPRING_END_RADIUS)
        * clip.SPRING_RAIL_WIDTH
        + math.pi * clip.SPRING_END_RADIUS**2
    )
    expected = (
        clip.CLIP_LENGTH * clip.SCREW_RAIL_WIDTH
        + clip.CENTER_BRIDGE_LENGTH * clip.NOTCH_WIDTH
        + spring_plan_area
        - 2.0 * math.pi * (clip.HOLE_DIA / 2.0) ** 2
    ) * clip.SHEET_T
    assert math.isclose(clip.V_FINAL, expected)


def test_platen_clip_free_halves_arch_and_return_to_sheet_plane() -> None:
    stations = clip.ARCH_FRONT_XZ
    assert stations[0] == (clip.SPRING_END_RADIUS, 0.0)
    assert stations[-1] == (clip.CLIP_LENGTH - clip.SPRING_END_RADIUS, 0.0)
    bridge_x0 = (clip.CLIP_LENGTH - clip.CENTER_BRIDGE_LENGTH) / 2.0
    bridge_x1 = bridge_x0 + clip.CENTER_BRIDGE_LENGTH
    assert stations[3] == (bridge_x0, 0.0)
    assert stations[4] == (bridge_x1, 0.0)
    assert [z for _, z in stations].count(-clip.ARCH_RISE) == 2
    assert clip.ARCH_RISE == 1.5
    assert math.isclose(clip.SPRING_END_RADIUS * 2.0, clip.SPRING_RAIL_WIDTH)


def test_platen_clip_holes_and_handed_assembly_placements_follow_flat_rail() -> None:
    assert clip.HOLE_Y == clip.SCREW_RAIL_WIDTH / 2.0
    assert clip.HOLE_Y - clip.HOLE_DIA / 2.0 > 0.0
    assert clip.HOLE_Y + clip.HOLE_DIA / 2.0 < clip.SCREW_RAIL_WIDTH
    assert tuple(row[3] for row in assembly.CLIP_PLACEMENTS) == (90.0, -90.0)
    assert math.isclose(
        clip.SPRING_RAIL_Y0 - (clip.HOLE_Y + clip.CLIP_SCREW_HEAD_DIA / 2.0),
        clip.CLIP_SCREW_HEAD_CLEARANCE,
    )

    plate_mid_x = assembly.PLATE_X0 + assembly.PLATE_WIDTH / 2.0
    expected_y = sorted(
        (
            assembly.PLATE_Y0 + assembly.PLATEN_SOCKET_XY[0][1],
            assembly.PLATE_Y0 + assembly.PLATEN_SOCKET_XY[1][1],
        )
    )
    for sx, origin_x, origin_y, rz in assembly.CLIP_PLACEMENTS:
        sin_rz = math.sin(math.radians(rz))
        socket_x = assembly.PLATE_X0 + assembly.PLATE_WIDTH - sx
        assert math.isclose(origin_x - sin_rz * clip.HOLE_Y, socket_x)
        actual_y = sorted(
            origin_y + sin_rz * local_x
            for local_x in (clip.HOLE_INSET, clip.CLIP_LENGTH - clip.HOLE_INSET)
        )
        assert all(
            math.isclose(actual, expected)
            for actual, expected in zip(actual_y, expected_y, strict=True)
        )
        spring_direction_x = -sin_rz
        assert (socket_x - plate_mid_x) * spring_direction_x < 0.0


def test_cascaded_drive_geometry_closes() -> None:
    assert rack.GAP_COUNT == 101
    assembly._assert_rack_mesh()
    assembly._assert_gear_mesh()
    assembly._assert_knob_shaft_clearance()
    assembly._assert_chain_layout()


def test_refitted_platen_clears_fixed_support_hardware() -> None:
    assert support.CLAMP_CBORE_DEPTH > 2.5
    assert support.CLAMP_CBORE_DIA > support.CLAMP_HOLE_DIA
    assert math.isclose(assembly.STUD_XY[0], support.BRACKET_STUD_X)
    assert support.BRACKET_HOLE_X == tuple(
        support.BRACKET_STUD_X + dx for dx in (-10.0, 10.0)
    )
    assert guide.LOCK_STATION_X == tuple(
        guide.GUIDE_LENGTH * fraction for fraction in (0.3, 0.7)
    )
