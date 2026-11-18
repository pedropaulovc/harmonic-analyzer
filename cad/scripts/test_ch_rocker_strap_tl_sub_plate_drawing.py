"""Offline contracts for the rocker-strap sub-plate (MHA-CH-13-TL-01)."""

from __future__ import annotations

import ast
import math
import re
import sys
from pathlib import Path

import pytest

import _buildgraph as bg
import _config
import build_ch_rocker_strap_tl_sub_plate as part
import ch_rocker_arm_spec as arm
import ch_rocker_strap_tl_sub_plate_spec as spec
import draw_ch_rocker_strap_tl_sub_plate as drawing
import export_features
from _drawing_contract import (
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _gtol_face import FaceGeometry
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import printed_band_mm

STEM = "ch_rocker_strap_tl_sub_plate"
INCH = 25.4
X1 = printed_band_mm(1, unit="in")
XX = printed_band_mm(2, unit="in")
XXX = printed_band_mm(3, unit="in")
# The B sheet's inner border and the title block's corner (sheet metres).
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.066)


def test_registry_row_is_inch_shop_tooling_on_a_landscape_learn_sheet() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-CH-13-TL-01"
    assert row["drawing_unit"] == spec.UNIT == "in"
    entry = DRAWINGS_BY_NAME[STEM]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.LEARN
    assert bg.is_shop_fixture(STEM)
    assert STEM in bg.references_of("ch_rocker_strap_tl_fixture")
    for machine in bg.MACHINE_ASSEMBLIES:
        assert STEM not in bg.references_of(machine)


def test_spec_build_and_drawing_never_read_the_shop_or_plan_tomls() -> None:
    """COM-leaf inputs: no TOML reader imported, no TOML path named."""
    for module in (spec, part, drawing):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all("toml" not in alias.name for alias in node.names), module
            elif isinstance(node, ast.ImportFrom):
                assert "toml" not in (node.module or ""), module
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not re.fullmatch(r"[\w./\\-]+\.toml", node.value), node.value


def test_strap_mirror_is_the_arm_spec_thinnest_finished_strap() -> None:
    assert spec.STRAP_THICKNESS_MIN == pytest.approx(
        arm.ARM_THICKNESS + arm.ARM_THICKNESS_BAND[1]
    )


def test_the_face_cut_clears_the_fence_and_stop_at_their_tallest() -> None:
    assert spec.FENCE_HEIGHT_MAX == pytest.approx(spec.FENCE_HEIGHT + XXX)
    assert spec.FENCE_HEIGHT_MAX == pytest.approx(0.079 * INCH)
    assert spec.FACE_CUT_CLEARANCE_MIN > 0.4


def test_each_notch_covers_its_plan_station_at_the_worst_case() -> None:
    """R.07 MAX corners, the notch ends .XX short, the depth .16."""
    assert spec.CORNER_RADIUS == pytest.approx(0.07 * INCH)
    assert spec.CORNER_CUTTER_RADIUS == pytest.approx(INCH / 16.0)
    left, right = spec.PLAN_NOTCH_STATIONS
    assert left == pytest.approx((2.4, 21.4))
    assert right == pytest.approx((283.4, 302.4))
    for (lo, hi), (x_range, depth, rounded) in zip(
        spec.PLAN_NOTCH_STATIONS, spec.NOTCH_EXTENTS_WORST, strict=True
    ):
        assert depth == pytest.approx(0.16 * INCH)
        for corner in (
            (lo, spec.PLAN_FENCE_NOTCH_DEPTH),
            (hi, spec.PLAN_FENCE_NOTCH_DEPTH),
        ):
            assert spec._in_rounded_notch(corner, x_range, depth, rounded), corner
    # Negative control: the contract's first .875 left end misses the station
    # once its R.07 corner is at the worst case.
    short = 0.87 * INCH - XX
    assert not spec._in_rounded_notch(
        (21.4, spec.PLAN_FENCE_NOTCH_DEPTH), (0.0, short), 0.16 * INCH, (0.0, short)
    )


def test_the_clamp_seats_on_its_pocket_and_its_tap() -> None:
    assert spec.POCKET_BACK_WALL_Y + spec.CLAMP_C == pytest.approx(spec.BLANK_EDGE_Y)
    assert spec.BLANK_EDGE_Y - spec.CLAMP_A == pytest.approx(spec.CLAMP_SCREW_Y)
    assert spec.POCKET_DEPTH == spec.CLAMP_B
    # A square body clears both R.07 MAX corners at the pocket's shortest.
    assert spec.POCKET_END_CLEARANCE == pytest.approx(
        (spec.POCKET_LENGTH - XX - spec.CLAMP_BODY_WIDTH - 2.0 * spec.CORNER_RADIUS)
        / 2.0
    )
    assert spec.POCKET_END_CLEARANCE > 0.4
    for station in spec.CLAMP_STATIONS:
        lo, hi = station - spec.POCKET_LENGTH / 2.0, station + spec.POCKET_LENGTH / 2.0
        assert 0.0 < lo and hi < spec.RIGHT_END_X
    assert spec.CLAMP_TAP_DRILL == TAP_DRILL_MM["#4-40"]
    assert spec.CLAMP_THREAD_LENGTH_MIN >= 1.5 * THREAD_MAJOR_MM["#4-40"]


def test_the_hub_tap_states_its_worst_case_engagement() -> None:
    """Owner ruling 2026-11-17: 1/4-20 through from the counterbore floor,
    .23 nominal (.92D), .21 at the worst case (.84D), stated as a fact."""
    assert spec.HUB_TAP_THREAD == "1/4-20"
    assert spec.HUB_TAP_DRILL == TAP_DRILL_MM["1/4-20"]
    assert spec.HUB_THREAD_LENGTH == pytest.approx(0.231 * INCH)
    assert spec.HUB_THREAD_LENGTH_MIN == pytest.approx(
        spec.HUB_THREAD_LENGTH - XX - XXX - XXX
    )
    assert spec.HUB_ENGAGEMENT_STATEMENT == "ENGAGEMENT .21 MIN (.84D)"
    for word in ("ACCEPT", "RULING", "RULE", "OWNER"):
        assert word not in spec.HUB_ENGAGEMENT_STATEMENT
    # The drill and reamer tips stop the plan's clearance above the floor.
    assert spec.HUB_CBORE_TIP_CLEARANCE_MIN >= spec.PLAN_RELIEF_FLOOR_CLEARANCE


def test_the_counterbore_is_what_the_plug_mirrors() -> None:
    import ch_rocker_strap_tl_hub_plug_spec as plug

    assert spec.HUB_CBORE_DIA == pytest.approx(0.500 * INCH)
    assert spec.HUB_CBORE_DEPTH == pytest.approx(0.185 * INCH)
    assert spec.COUNTERBORE_FLOOR_Z == pytest.approx(-spec.HUB_CBORE_DEPTH)
    assert plug.COUNTERBORE_DIA == spec.HUB_CBORE_DIA
    assert plug.COUNTERBORE_DEPTH == spec.HUB_CBORE_DEPTH


def test_the_frame_stacks_from_the_faced_top_to_the_underside() -> None:
    assert spec.PLATE_LENGTH == pytest.approx(13.0 * INCH)
    assert spec.RIGHT_END_X == pytest.approx(spec.LEFT_END_X + spec.PLATE_LENGTH)
    assert spec.FRONT_EDGE_Y == pytest.approx(-2.5 * INCH)
    assert spec.UNDERSIDE_Z == pytest.approx(spec.FENCE_HEIGHT - spec.PLATE_THICKNESS)
    assert spec.POCKET_FLOOR_Z == pytest.approx(-spec.POCKET_DEPTH)


def test_finished_volume_is_the_blank_less_every_cut() -> None:
    r = spec.CORNER_RADIUS
    corner = (1.0 - math.pi / 4.0) * r * r
    pocket_width = spec.POCKET_NEAR_WALL_Y - spec.POCKET_BACK_WALL_Y
    expected = (
        330.2 * 76.2 * 12.446
        - 317.5 * 63.5 * 1.8796
        - (23.368 + 36.068) * 4.318 * 1.8796
        + 3 * corner * 1.8796
        - 4 * (14.224 * pocket_width - 4 * corner) * 3.556
        - math.pi / 4.0 * 12.7**2 * 4.699
        - 4 * math.pi / 4.0 * 2.261**2 * (10.5664 - 3.556)
        - math.pi / 4.0 * 5.105**2 * (10.5664 - 4.699)
    )
    assert spec.V_FINISHED == pytest.approx(expected)
    assert pocket_width == pytest.approx(spec.CLAMP_C)


def test_printed_dimensions_sit_on_their_inch_grid() -> None:
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        value = spec.DIMENSION_VALUES[name]
        assert spec.inch_grid_mm(value, places) == pytest.approx(value, abs=1e-9), name


def test_explicit_bands_are_the_only_model_tolerances() -> None:
    assert model_toleranced_dimensions(part) == {
        ("PocketProfile", "PocketBackWallY"): "spec.POCKET_BACK_WALL_TOL",
        ("HubCboreProfile", "HubX"): "spec.HUB_LOCATION_TOL",
        ("HubCboreProfile", "HubY"): "spec.HUB_LOCATION_TOL",
    }
    assert set(spec.SYMMETRIC_BANDS) == set(model_toleranced_dimensions(part))
    for feature, name in (
        *spec.SYMMETRIC_BANDS,
        *spec.MAX_RADII,
        *spec.DIMENSION_PREFIXES,
    ):
        assert name in spec.DRAWING_DIMENSIONS[feature], (feature, name)
    # Every tight or three-place size states its mate or reason (rule 3).
    three_place = {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 3
    }
    explained = set(spec.DIMENSION_CALLOUTS) | {
        name for _f, name in spec.SYMMETRIC_BANDS
    }
    located = {"HubX", "HubY", "ClampTapY", *spec.CLAMP_TAP_X_NAMES}
    assert three_place - located <= explained


def test_every_drive_expression_names_a_global() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.update(re.findall(r'"([A-Za-z]+)"', node.value))
    names.discard("in")
    assert names, "no drive expressions found"
    assert names <= set(part.GLOBALS), sorted(names - set(part.GLOBALS))
    for index in range(1, len(spec.CLAMP_STATIONS) + 1):
        assert f"ClampStation{index}" in part.GLOBALS


def test_section_heights_live_in_hidden_reference_sketches_on_each_cut() -> None:
    """A section imports no extrusion depth (farm run 20261117T234245842Z),
    so each printed height is a reference line in its cutting plane, standing
    on a section edge inside the cut's span, and saved hidden."""
    assert spec.DRAWING_DIMENSIONS[spec.SECTION_A_REFERENCE] == set(
        drawing.SECTION_A_KEEP
    )
    assert spec.DRAWING_DIMENSIONS[spec.SECTION_B_REFERENCE] == set(
        drawing.SECTION_B_KEEP
    )
    for feature in ("Plate", "PlateTop", "ClampPockets", "HubCbore"):
        assert feature not in spec.DRAWING_DIMENSIONS, feature
    assert spec.SECTION_A_Y == drawing.SECTION_A_ANCHOR[1] == spec.CLAMP_SCREW_Y
    assert spec.SECTION_B_Y == drawing.SECTION_B_ANCHOR[1] == spec.HUB_Y
    lo, hi = drawing.SECTION_A_SPAN
    for x in (
        spec.FENCE_HEIGHT_REFERENCE_X,
        spec.THICKNESS_REFERENCE_X,
        spec.POCKET_DEPTH_REFERENCE_X,
    ):
        assert lo < x < hi, x
    assert spec.FENCE_HEIGHT_REFERENCE_X == 0.0  # the stop face
    assert spec.THICKNESS_REFERENCE_X == spec.LEFT_END_X
    assert spec.POCKET_DEPTH_REFERENCE_X == pytest.approx(
        spec.CLAMP_STATIONS[0] + spec.POCKET_LENGTH / 2.0
    )
    lo, hi = drawing.SECTION_B_SPAN
    assert lo < spec.CBORE_DEPTH_REFERENCE_X < hi
    assert spec.CBORE_DEPTH_REFERENCE_X == pytest.approx(
        spec.HUB_X - spec.HUB_CBORE_DIA / 2.0
    )
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    blanked = [
        ast.unparse(node.args[1])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "blank_reference_sketches"
    ]
    assert blanked == ["(spec.SECTION_A_REFERENCE, spec.SECTION_B_REFERENCE)"]


def test_every_marked_dimension_prints_once_on_the_sheet_in_bounds() -> None:
    keeps = (drawing.TOP_KEEP, drawing.SECTION_A_KEEP, drawing.SECTION_B_KEEP)
    names = [name for keep in keeps for name in keep]
    assert sorted(names) == sorted(drawing.sheet_dimension_names())
    points = [xy for keep in keeps for xy in keep.values()]
    points += [
        drawing.CLAMP_TAP_CALLOUT_XY,
        drawing.HUB_TAP_CALLOUT_XY,
        drawing.ISO_CENTER,
        drawing.ISO_NOTE_XY,
        drawing.SECTION_A_ORIGIN,
        drawing.SECTION_B_ORIGIN,
    ]
    for x, y in points:
        assert BORDER[0] < x < BORDER[2] and BORDER[1] < y < BORDER[3], (x, y)
        assert not (x > TITLE_BLOCK[0] and y < TITLE_BLOCK[1] + 0.006), (x, y)


# Farm run 20261118T000915664Z's layout audit, in sheet mm relative to what
# placed each item (the sections and the callout points have not moved since):
# each section caption's box from its section's origin; each hole callout's
# leader end from its callout point (the text's lower left, about half the
# text's width left of the point); NotchCornerR's shoulder from its text point.
_CAPTION_A = ((4.6, 50.0), (-31.4, -25.0))
_CAPTION_B = ((-21.9, 21.8), (-31.4, -24.9))
_CLAMP_LEADER_END = (-26.6, -5.6)
_HUB_LEADER_END = (-34.0, -8.4)
_NOTCH_R_SHOULDER = (-15.7, 14.0)


def _mm(point: tuple[float, float]) -> tuple[float, float]:
    return (point[0] * 1000.0, point[1] * 1000.0)


def _box(origin_m, offsets):
    (x0, x1), (y0, y1) = offsets
    ox, oy = _mm(origin_m)
    return (ox + x0, oy + y0, ox + x1, oy + y1)


def _segment_hits_box(a, b, box, margin=1.0) -> bool:
    """Whether segment a-b enters ``box`` (x0, y0, x1, y1) grown by ``margin``."""
    x0, y0, x1, y1 = box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin
    steps = 400
    for i in range(steps + 1):
        t = i / steps
        x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


def _leader(wall_xy_m, callout_xy_m, end_offset):
    end = _mm(callout_xy_m)
    return _mm(wall_xy_m), (end[0] + end_offset[0], end[1] + end_offset[1])


def test_tap_callout_leaders_run_clear_of_the_section_captions() -> None:
    """r5: both leaders ran through their section's caption."""
    clamp_wall = drawing.section_a_xy(drawing.CLAMP_TAP_EDGE_MODEL[0], spec.UNDERSIDE_Z)
    hub_wall = drawing.section_b_xy(drawing.HUB_TAP_EDGE_MODEL[0], spec.UNDERSIDE_Z)
    caption_a = _box(drawing.SECTION_A_ORIGIN, _CAPTION_A)
    caption_b = _box(drawing.SECTION_B_ORIGIN, _CAPTION_B)
    # The r5 placements reproduce the audit's findings (the check bites).
    assert _segment_hits_box(
        *_leader(clamp_wall, (0.150, 0.078), _CLAMP_LEADER_END), caption_a
    )
    assert _segment_hits_box(
        *_leader(hub_wall, (0.360, 0.088), _HUB_LEADER_END), caption_b
    )
    clamp = _leader(clamp_wall, drawing.CLAMP_TAP_CALLOUT_XY, _CLAMP_LEADER_END)
    hub = _leader(hub_wall, drawing.HUB_TAP_CALLOUT_XY, _HUB_LEADER_END)
    for leader in (clamp, hub):
        for caption in (caption_a, caption_b):
            assert not _segment_hits_box(*leader, caption), (leader, caption)
    # Each text (about twice its half width) stays inside the border and off
    # the title block, and starts right of its drill wall.
    for (start, end), half in (
        (clamp, -_CLAMP_LEADER_END[0]),
        (hub, -_HUB_LEADER_END[0]),
    ):
        assert end[0] > start[0]
        assert end[0] + 2.0 * half < BORDER[2] * 1000.0 - 2.0
        assert (
            end[1] > TITLE_BLOCK[1] * 1000.0
            or end[0] + 2.0 * half < TITLE_BLOCK[0] * 1000.0
        )
    # The clamp text's top (as far above its point as the leader end is
    # below) stays under section A-A; the hub text starts right of B-B.
    section_a_bottom = drawing.section_a_xy(0.0, spec.UNDERSIDE_Z)[1] * 1000.0
    assert (
        drawing.CLAMP_TAP_CALLOUT_XY[1] * 1000.0 - _CLAMP_LEADER_END[1]
        < section_a_bottom
    )
    section_b_right = drawing.section_b_xy(drawing.SECTION_B_SPAN[1], 0.0)[0] * 1000.0
    assert hub[1][0] > section_b_right + 5.0


def test_notch_radius_shoulder_clears_the_overall_length_extension() -> None:
    """r5: the shoulder at the back edge +4 mm crossed PlateLength's
    extension line, which rises from the plate's right end at the back edge."""
    right = drawing.top_xy(spec.RIGHT_END_X, 0.0)[0] * 1000.0
    back = drawing.top_xy(0.0, spec.BACK_EDGE_Y)[1] * 1000.0

    def crosses(text_xy_m) -> bool:
        x, y = _mm(text_xy_m)
        left, right_end = x + _NOTCH_R_SHOULDER[0], x + _NOTCH_R_SHOULDER[1]
        return left - 1.0 <= right <= right_end + 1.0 and y >= back - 1.0

    assert crosses(
        (drawing.top_xy(spec.RIGHT_END_X, 0.0)[0] + 0.014, back / 1000.0 + 0.004)
    )
    keep = drawing.TOP_KEEP["NotchCornerR"]
    assert not crosses(keep)
    # The text sits in the open right notch's band, right of the plate's end.
    assert (
        drawing.top_xy(0.0, 0.0)[1] < keep[1] < drawing.top_xy(0.0, spec.NOTCH_DEPTH)[1]
    )
    assert keep[0] * 1000.0 + _NOTCH_R_SHOULDER[0] > right


def test_top_view_stacks_x_above_and_below_and_y_to_the_left() -> None:
    top = drawing.TOP_KEEP
    left = drawing.top_xy(spec.LEFT_END_X, 0.0)[0]
    front = drawing.top_xy(0.0, spec.FRONT_EDGE_Y)[1]
    back = drawing.top_xy(0.0, spec.BACK_EDGE_Y)[1]
    for name in ("NotchLeftEnd", "NotchRightStart", "PlateLength", "LeftEnd"):
        assert top[name][1] > back, name
    below = ("ClampTapX1", "ClampTapX2", "HubX", "ClampTapX3", "ClampTapX4")
    rows = [top[name][1] for name in below]
    assert all(row < front for row in rows)
    assert rows == sorted(rows, reverse=True)
    beside = (
        "NotchDepth",
        "FenceWidth",
        "HubY",
        "PocketNearWallY",
        "ClampTapY",
        "PocketBackWallY",
        "PlateWidth",
    )
    columns = [top[name][0] for name in beside]
    assert all(column < left for column in columns)
    assert columns == sorted(columns, reverse=True)
    # The plate at 1:2 stands clear of the isometric.
    right = drawing.top_xy(spec.RIGHT_END_X, 0.0)[0]
    assert right < drawing.ISO_CENTER[0] - 0.06


def test_tap_callouts_open_with_the_count_then_thread_then_drill() -> None:
    """The native THRU tap layout (farm run 20261118T000009756Z): the thread
    in part 5, the drill in part 7 carrying the native count."""
    native = {
        5: "<hw-threaddesc> - <hw-threadclass> <hw-thru>",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-thrutapdrldia> <hw-thru>",
        8: "",
    }
    clamp = drawing.clamp_tap_definitions(native)
    assert clamp == {
        5: "4X <hw-threaddesc> <hw-thru>",
        6: "",
        7: "<MOD-DIAM><hw-thrutapdrldia> DRILL <hw-thru>",
        8: "",
    }
    hub = drawing.hub_tap_definitions(native)
    assert hub[5] == "<hw-threaddesc> <hw-thru>"
    assert hub[7] == "<MOD-DIAM><hw-thrutapdrldia> DRILL <hw-thru>"
    assert hub[8] == spec.HUB_ENGAGEMENT_STATEMENT
    countless = {**native, 7: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>"}
    assert drawing.clamp_tap_definitions(countless) == clamp
    assert "<NUM_INST>" not in "".join(drawing.hub_tap_definitions(countless).values())
    with pytest.raises(RuntimeError):
        drawing.clamp_tap_definitions(clamp)
    with pytest.raises(RuntimeError):
        drawing.tap_callout_definitions({5: "", 6: "", 7: "", 8: ""})
    with pytest.raises(RuntimeError):
        drawing.clamp_tap_definitions({**native, 5: "<NUM_INST>X " + native[5]})


def test_drawing_owns_no_manufacturing_literals() -> None:
    path = Path(drawing.__file__)
    assert (
        drawing_specification_violations(
            path.read_text(encoding="utf-8"), filename=str(path)
        )
        == ()
    )


def test_feature_export_names_every_requirement_the_plate_program_reads() -> None:
    manifest = export_features.requirement_manifest(STEM)
    features = manifest["features"]
    expected = {
        "plate_top",
        "faced_top",
        "underside",
        "fence_face",
        "stop_face",
        "front_edge",
        "back_edge",
        "fence_notch_left",
        "fence_notch_right",
        "hub_counterbore",
        "hub_tap",
        *(f"clamp_pocket_{i}" for i in range(1, 5)),
        *(f"clamp_tap_{i}" for i in range(1, 5)),
    }
    assert set(features) == expected
    assert manifest["material"]["thickness"] == spec.PLATE_THICKNESS
    assert manifest["volume_mm3"] == spec.V_FINISHED
    assert features["faced_top"]["height"] == pytest.approx(
        [spec.FENCE_HEIGHT - XXX, spec.FENCE_HEIGHT + XXX]
    )
    assert features["hub_counterbore"]["x"] == pytest.approx(
        [spec.HUB_X - spec.HUB_LOCATION_TOL, spec.HUB_X + spec.HUB_LOCATION_TOL]
    )
    pocket = features["clamp_pocket_1"]
    assert pocket["back_wall_y"] == pytest.approx(
        [
            -spec.POCKET_BACK_WALL_Y - spec.POCKET_BACK_WALL_TOL,
            -spec.POCKET_BACK_WALL_Y + spec.POCKET_BACK_WALL_TOL,
        ]
    )
    assert pocket["corner_radius_max"] == spec.CORNER_RADIUS
    assert features["fence_notch_left"]["end_x"] == pytest.approx(
        [spec.NOTCH_LEFT_END - XX, spec.NOTCH_LEFT_END + XX]
    )
    assert features["hub_tap"]["engagement_min"] == spec.HUB_THREAD_LENGTH_MIN
    assert features["clamp_tap_3"]["at"] == pytest.approx(
        [spec.CLAMP_STATIONS[2], spec.CLAMP_SCREW_Y, spec.POCKET_FLOOR_Z]
    )
    for feature in features.values():
        for key in feature["requirements"]:
            assert key in feature, (feature, key)


def _plane(normal, point_mm, box_mm=()):
    length = math.hypot(*normal)
    unit = tuple(value / length for value in normal)
    box = tuple(value / 1000.0 for value in box_mm)
    return FaceGeometry(None, 4001, (*unit, *(v / 1000.0 for v in point_mm)), unit, box)


def _cylinder(diameter_mm, centre_mm, depth_mm):
    x, y, z = centre_mm
    axis = (x / 1000.0, y / 1000.0, z / 1000.0, 0.0, 0.0, 1.0)
    r = diameter_mm / 2.0
    box = tuple(v / 1000.0 for v in (x - r, y - r, z - depth_mm, x + r, y + r, z))
    return FaceGeometry(None, 4002, (*axis, diameter_mm / 2000.0), None, box)


def _owners(geometry: FaceGeometry) -> list[str]:
    selectors = export_features.feature_selectors(STEM)
    return [
        name
        for name, specs in selectors.items()
        if any(selector.matches(geometry) for selector in specs)
    ]


def test_each_feature_face_has_one_owner() -> None:
    zf, zu = spec.FENCE_HEIGHT, spec.UNDERSIDE_Z
    faces = {
        "plate_top": _plane((0, 0, 1), (100.0, -30.0, 0.0)),
        "faced_top": _plane((0, 0, 1), (-5.0, 0.0, zf)),
        "underside": _plane((0, 0, -1), (0.0, 0.0, zu)),
        "fence_face": _plane((0, -1, 0), (100.0, 0.0, 1.0)),
        "stop_face": _plane((1, 0, 0), (0.0, -30.0, 1.0)),
        "front_edge": _plane((0, -1, 0), (0.0, spec.FRONT_EDGE_Y, 0.0)),
        "back_edge": _plane((0, 1, 0), (0.0, spec.BACK_EDGE_Y, 0.0)),
        "fence_notch_left": _plane(
            (0, -1, 0),
            (10.0, spec.NOTCH_DEPTH, 1.0),
            (0.0, spec.NOTCH_DEPTH, 0.0, spec.NOTCH_LEFT_END, spec.NOTCH_DEPTH, zf),
        ),
        "fence_notch_right": _plane(
            (0, -1, 0),
            (300.0, spec.NOTCH_DEPTH, 1.0),
            (
                spec.NOTCH_RIGHT_START,
                spec.NOTCH_DEPTH,
                0.0,
                spec.RIGHT_END_X,
                spec.NOTCH_DEPTH,
                zf,
            ),
        ),
        "hub_counterbore": _cylinder(
            spec.HUB_CBORE_DIA, (spec.HUB_X, spec.HUB_Y, 0.0), spec.HUB_CBORE_DEPTH
        ),
        "hub_tap": _cylinder(
            spec.HUB_TAP_DRILL,
            (spec.HUB_X, spec.HUB_Y, spec.COUNTERBORE_FLOOR_Z),
            spec.HUB_THREAD_LENGTH,
        ),
    }
    half = spec.POCKET_LENGTH / 2.0
    for index, station in enumerate(spec.CLAMP_STATIONS, 1):
        faces[f"clamp_pocket_{index}"] = _plane(
            (0, 0, 1),
            (station, spec.CLAMP_SCREW_Y, spec.POCKET_FLOOR_Z),
            (
                station - half,
                spec.POCKET_BACK_WALL_Y,
                spec.POCKET_FLOOR_Z,
                station + half,
                spec.POCKET_NEAR_WALL_Y,
                spec.POCKET_FLOOR_Z,
            ),
        )
        faces[f"clamp_tap_{index}"] = _cylinder(
            spec.CLAMP_TAP_DRILL,
            (station, spec.CLAMP_SCREW_Y, spec.POCKET_FLOOR_Z),
            spec.CLAMP_THREAD_LENGTH,
        )
    for name, geometry in faces.items():
        assert _owners(geometry) == [name], name
    # A corner fillet's cylinder belongs to no requirement.
    assert _owners(_cylinder(2.0 * spec.CORNER_RADIUS, (0.0, 0.0, 0.0), 1.0)) == []


def test_cli_accepts_only_its_stem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
    monkeypatch.setattr(sys, "argv", ["draw", "ch-rocker-strap"])
    with pytest.raises(SystemExit):
        drawing._parse_args()
