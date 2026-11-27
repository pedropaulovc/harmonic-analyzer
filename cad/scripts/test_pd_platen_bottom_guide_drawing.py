"""Offline manufacturing contracts for the MHA-PD-27 platen bottom guide."""

from __future__ import annotations

import math

import pytest

import _config
import build_pd_platen_bottom_guide as builder
import build_pd_platen_guide as top_builder
import draw_pd_platen_bottom_guide as drawing
import export_features
import pd_feed_rack_spec as rack
import pd_platen_bottom_guide_spec as spec
import pd_platen_guide_spec as top_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _gtol_face import FaceGeometry
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM
from _mcmaster_91794a060 import HEAD_DIA, SHANK_DIA
from pd_platen_spec import GUIDE_HOLE_X, GUIDE_HOLE_Y, PLATE_WIDTH


def test_identity_and_quantity() -> None:
    row = _config.parts(builder.PART_NAME)
    assert row["number"] == "MHA-PD-27"
    assert row["quantity"] == 1
    assert _config.parts("pd-platen-guide")["quantity"] == 1


def test_it_keeps_the_top_rail_section_and_lock_geometry() -> None:
    assert spec.GUIDE_LENGTH == PLATE_WIDTH
    assert spec.GUIDE_DEPTH == top_builder.GUIDE_DEPTH
    assert spec.GUIDE_DEPTH_BAND == top_spec.GUIDE_DEPTH_BAND
    assert spec.LOCK_TAP_X == top_builder.HOLE_X
    assert spec.LOCK_SCREW_DX == top_builder.LOCK_SCREW_DX
    assert spec.LOCK_TAP_SPEC == top_spec.LOCK_TAP_SPEC
    assert spec.PLATEN_TAP_SPEC == top_spec.TAPPED_HOLE_SPEC
    # The lock taps stand where the bottom MHA-PD-11 rail's did above the
    # platen, to the print's .XXX.
    former = 10.5 + top_spec.TAP_Y
    assert abs(spec.UNDERSIDE_ABOVE_PLATEN_BOTTOM + spec.LOCK_TAP_Y - former) <= spec.BAND


def test_underside_seats_the_rack_and_the_platen_taps_follow_mha_pd_02() -> None:
    assert spec.UNDERSIDE_ABOVE_PLATEN_BOTTOM < rack.RACK_HEIGHT
    assert spec.PLATEN_TAP_X == GUIDE_HOLE_X
    assert spec.PLATEN_TAP_Y == pytest.approx(
        GUIDE_HOLE_Y[0] - spec.UNDERSIDE_ABOVE_PLATEN_BOTTOM
    )
    # The transferred row pays the strip's room and the crest set, so it is
    # wider than a printed row.
    assert spec.PLATEN_TAP_Y_BAND > spec.BAND + (
        rack.PURCHASED_RACK_HEIGHT_MAX_MM - rack.RACK_HEIGHT
    )


def test_the_spot_punch_float_is_booked_at_the_drilled_platen_hole() -> None:
    import draw_pd_paper_drive_assembly as assembly_sheet
    from _printed_tolerance import drilled_oversize_mm
    from pd_platen_spec import GUIDE_HOLE_DIA
    from pd_platen_spec import UNIT as PLATEN_UNIT

    punch = float(assembly_sheet.GUIDE_SPOT_PUNCH) * 25.4
    assert punch < GUIDE_HOLE_DIA < punch + 25.4 / 64.0
    hole_max = GUIDE_HOLE_DIA + drilled_oversize_mm(unit=PLATEN_UNIT)
    assert spec.PLATEN_SPOT_PUNCH_FLOAT == pytest.approx((hole_max - punch) / 2.0)
    assert spec.PLATEN_SPOT_PUNCH_FLOAT > spec.HOLE_TRANSFER_BAND


def test_height_is_the_least_thousandth_that_keeps_every_tap_wall() -> None:
    walls = (
        spec.PLATEN_TAP_TOP_WALL_MIN,
        spec.PLATEN_TAP_BOTTOM_WALL_MIN,
        spec.LOCK_TAP_TOP_WALL_MIN,
    )
    assert min(walls) >= WALL_FLOOR_MM - 1e-9
    lower = spec.GUIDE_HEIGHT - 0.0254
    assert lower - spec.BAND - (spec.PLATEN_TAP_Y + spec.PLATEN_TAP_Y_BAND) - (
        THREAD_MAJOR_MM["#4-40"] / 2.0 + spec.EDGE_BREAK + spec.TAP_MOUTH_BREAK
    ) < WALL_FLOOR_MM
    assert round(spec.GUIDE_HEIGHT / 25.4, 6) == round(spec.GUIDE_HEIGHT / 25.4, 3)
    assert 0.0 <= spec.TOP_RISE < spec.BAND * 2.0


def test_rack_screw_holes_take_the_stock_screw_on_the_rack_floor() -> None:
    # The rail is placed Ry180 (as MHA-PD-11), so its local stations mirror
    # about its length onto the strip's taps.
    assert sorted(spec.GUIDE_LENGTH - x for x in spec.SCREW_HOLE_X) == pytest.approx(
        rack.TAP_X
    )
    assert spec.SCREW_HOLE_Z == pytest.approx(
        rack.FRONT_BEHIND_PLATEN + rack.RACK_THICKNESS / 2.0
    )
    assert spec.GUIDE_HEIGHT - spec.SCREW_CBORE_DEPTH == pytest.approx(rack.SCREW_FLOOR)
    assert SHANK_DIA < spec.SCREW_HOLE_DIA < HEAD_DIA < spec.SCREW_CBORE_DIA
    assert spec.SCREW_FLOAT_RADIAL >= math.hypot(
        spec.HOLE_TRANSFER_BAND, spec.HOLE_TRANSFER_BAND
    )
    assert spec.SCREW_HOLE_SPEC.overrides_mm == {
        "HoleDiameter": spec.SCREW_HOLE_DIA,
        "CounterBoreDiameter": spec.SCREW_CBORE_DIA,
        "CounterBoreDepth": spec.SCREW_CBORE_DEPTH,
    }
    assert spec.SCREW_HOLE_TAP_WALL_MIN >= WALL_FLOOR_MM


def test_counterbore_front_wall_shortfall_is_a_declared_minor() -> None:
    assert 0.0 < spec.SCREW_CBORE_FRONT_WALL_MIN < spec.SCREW_CBORE_FRONT_WALL_NOMINAL
    # The strip lies flipped, so its taps sit (width - TapFromFront) behind its
    # machine-front face: the narrowest strip with every band at its corner.
    tap_from_front = (
        rack.FRONT_BEHIND_PLATEN
        - rack.FRONT_SET_BAND
        + rack.PURCHASED_RACK_FACE_WIDTH_MIN_MM
        - (rack.TAP_Z + rack.TAP_BAND)
        - spec.HOLE_TRANSFER_BAND
    )
    # The counterbore at its printed largest, Ø.110 +.004 (owner ruling
    # 2026-11-25, #3620).
    cbore_radius = (spec.SCREW_CBORE_DIA + spec.SCREW_CBORE_DIA_BAND[0]) / 2.0
    assert spec.SCREW_CBORE_FRONT_WALL_MIN == pytest.approx(
        tap_from_front - cbore_radius - spec.EDGE_BREAK
    )
    declared = {
        entry["id"]: entry["kind"]
        for entry in _config.parts(builder.PART_NAME)["machinist_exceptions"]
    }
    if spec.SCREW_CBORE_FRONT_WALL_MIN < WALL_FLOOR_MM:
        assert declared["RV-01"] == "minor"
        assert spec.SCREW_CBORE_FRONT_WALL_TEXT in drawing.SCREW_CALLOUT_BELOW


def test_print_marks_the_kept_dimensions_and_names_the_transfers() -> None:
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert marked == kept == spec.DRAWING_NOMINALS_MM.keys() == spec.DRAWING_PRECISION_BY_NAME.keys()
    assert spec.DRAWING_PRECISION_BY_NAME["Height"] == 3
    assert _config.parts("pd-platen")["number"] in drawing.PLATEN_CALLOUT_BELOW
    assert _config.parts("pd-feed-rack")["number"] in drawing.SCREW_CALLOUT_BELOW
    assert "TRANSFER" not in drawing.LOCK_CALLOUT_BELOW
    assert "draw_pd_platen_bottom_guide.py" in PRECISION_MIGRATED_DRAWINGS
    assert drawing.SPEC.part == "pd_platen_bottom_guide"


def test_right_view_dimensions_stand_clear_of_the_front_view() -> None:
    # The front view's right end, where the length's extension line drops.
    rail_end = drawing._LEFT_X + spec.GUIDE_LENGTH / 1000.0
    right_left = drawing.RIGHT_CENTER[0] - spec.GUIDE_DEPTH / 2000.0
    # ~2.85 mm per character at the sheet's text height (r3, R5 renders).
    height_width = 0.00285 * max(
        len(line) for line in drawing.HEIGHT_CALLOUT.splitlines()
    )
    # The text hangs right of the dimension line, its left end on the x.
    height_x = drawing.FRONT_KEEP["Height"][0]
    assert rail_end < height_x
    assert height_x + height_width < right_left
    # Value plus reason (~5.6 mm a line) is taller than the rail, so the text
    # stands wholly above its top extension line (r5: between them the lower
    # one struck it; R5: below the rail the line ran beside the rows to the
    # shelf 8.4 mm under the given y and touched the widest).
    height_y = drawing.FRONT_KEEP["Height"][1]
    rows = 1 + len(drawing.HEIGHT_CALLOUT.splitlines())
    assert spec.GUIDE_HEIGHT / 1000.0 < 0.0056 * rows
    height_shelf = height_y - 0.0084
    height_top = height_shelf + 0.0056 * rows
    assert height_shelf > drawing.FRONT_CENTER[1] + spec.GUIDE_HEIGHT / 2000.0
    # The depth's text is wider than the right view, so it stands left of the
    # view's left extension line, right of the top view's end, above the
    # height's text (r4: centred, both extension lines struck it).
    depth_x, depth_y = drawing.RIGHT_KEEP["Depth"]
    half_depth = (
        0.0028 * max(len(line) for line in spec.GUIDE_DEPTH_CALLOUT.splitlines()) / 2.0
    )
    assert rail_end < depth_x - half_depth
    assert depth_x + half_depth < right_left
    # Its shelf stands ~10.2 mm under its given y, clear over the height's top.
    assert depth_y - 0.0102 > height_top + 0.003


def test_the_height_band_names_its_screw_by_number() -> None:
    assert drawing.HEIGHT_CALLOUT.splitlines() == ["SETS ENGAGEMENT", "OF MHA-PD-VN-72"]


def test_the_counterbore_prints_the_owners_bands_in_two_word_lines() -> None:
    # Owner ruling 2026-11-26 (#3738): Ø.125 +.005/−0 and depth .219 ±.005.
    # Without them the wizard pocket's ±.01 (rule 3) fails the tap lead, the
    # printed engagement and the printed wall.
    assert spec.SCREW_CBORE_DIA == pytest.approx(_in(0.125))
    assert spec.SCREW_CBORE_DIA_BAND == pytest.approx((_in(0.005), 0.0))
    assert spec.SCREW_CBORE_DEPTH == pytest.approx(_in(0.219))
    assert spec.SCREW_CBORE_DEPTH_BAND == pytest.approx((_in(0.005), -_in(0.005)))
    # The part bands the Hole Wizard feature; the sheet prints both bands at
    # the callout's three places.
    assert drawing.SCREW_CBORE_PLACES == {"hw-cbdia": 3, "hw-cbdepth": 3}
    # Rule 7: at most two word lines on a callout, and one reason once: the
    # engagement the floor sets is named by the height alone.
    assert drawing.SCREW_CALLOUT_BELOW.splitlines() == [
        "TRANSFER FROM MHA-PD-26 AT ASSEMBLY",
        "WALL .044 MIN TO FRONT FACE",
    ]
    assert "ENGAGEMENT" in drawing.HEIGHT_CALLOUT
    # The worst cases at the printed bands, inch. The tip margin is ZERO.
    assert spec.SCREW_HEAD_ENTRY_MIN / 25.4 == pytest.approx(0.022, abs=1e-4)
    assert rack.SCREW_TIP_MARGIN == pytest.approx(0.0, abs=1e-12)
    assert rack.ENGAGEMENT_WORST >= _in(0.032)
    assert rack.ENGAGEMENT_STATEMENT == "ENGAGEMENT .032 MIN (0.54D)"
    assert spec.SCREW_CBORE_FRONT_WALL_MIN >= _in(0.044)
    assert spec.SCREW_CBORE_FRONT_WALL_TEXT == "WALL .044 MIN TO FRONT FACE"


def _in(value_in: float) -> float:
    return value_in * 25.4


_FEATURE_KINDS = {
    "left_end": "face",
    "right_end": "face",
    "underside": "face",
    "top_face": "face",
    "front_face": "face",
    "rear_face": "face",
    **{f"lock_tap_{index}": "threaded_hole" for index in range(1, 5)},
    **{f"platen_tap_{index}": "threaded_hole" for index in range(1, 6)},
    **{f"rack_screw_hole_{index}": "hole" for index in range(1, 5)},
}


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def test_the_rail_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert "pd_platen_bottom_guide" in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest("pd_platen_bottom_guide")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == []
    selectors = export_features.feature_selectors("pd_platen_bottom_guide")
    length, height, depth = spec.GUIDE_LENGTH, spec.GUIDE_HEIGHT, spec.GUIDE_DEPTH
    expected = {
        "left_end": [_plane((-1.0, 0.0, 0.0), 0.0)],
        "right_end": [_plane((1.0, 0.0, 0.0), length)],
        "underside": [_plane((0.0, -1.0, 0.0), 0.0)],
        "top_face": [_plane((0.0, 1.0, 0.0), height)],
        "front_face": [_plane((0.0, 0.0, 1.0), 0.0)],
        "rear_face": [_plane((0.0, 0.0, -1.0), depth)],
    }
    tap_r = drawing._TAP_DRILL / 2
    for index, x in enumerate(spec.LOCK_TAP_X, 1):
        box = (
            x - tap_r,
            spec.LOCK_TAP_Y - tap_r,
            -depth,
            x + tap_r,
            spec.LOCK_TAP_Y + tap_r,
            0.0,
        )
        expected[f"lock_tap_{index}"] = [
            _cylinder(drawing._TAP_DRILL, (0.0, 0.0, 1.0), box)
        ]
    for index, x in enumerate(spec.PLATEN_TAP_X, 1):
        box = (
            x - tap_r,
            spec.PLATEN_TAP_Y - tap_r,
            -depth,
            x + tap_r,
            spec.PLATEN_TAP_Y + tap_r,
            0.0,
        )
        expected[f"platen_tap_{index}"] = [
            _cylinder(drawing._TAP_DRILL, (0.0, 0.0, 1.0), box)
        ]
    for index, x in enumerate(spec.SCREW_HOLE_X, 1):
        z = -spec.SCREW_HOLE_Z
        floor = height - spec.SCREW_CBORE_DEPTH
        hole_r, cbore_r = spec.SCREW_HOLE_DIA / 2, spec.SCREW_CBORE_DIA / 2
        expected[f"rack_screw_hole_{index}"] = [
            _cylinder(
                spec.SCREW_HOLE_DIA,
                (0.0, 1.0, 0.0),
                (x - hole_r, 0.0, z - hole_r, x + hole_r, floor, z + hole_r),
            ),
            _cylinder(
                spec.SCREW_CBORE_DIA,
                (0.0, 1.0, 0.0),
                (x - cbore_r, floor, z - cbore_r, x + cbore_r, height, z + cbore_r),
            ),
        ]
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name


def test_rail_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest("pd_platen_bottom_guide")[
        "features"
    ]
    assert features["right_end"]["length"] == pytest.approx([_in(10.61), _in(10.63)])
    assert features["top_face"]["height"] == pytest.approx([_in(0.619), _in(0.629)])
    assert features["rear_face"]["depth"] == pytest.approx([_in(0.39), _in(0.40)])
    stations = (2.909, 3.461, 7.155, 7.707)
    for index, station in enumerate(stations, 1):
        tap = features[f"lock_tap_{index}"]
        assert tap["thread"] == "#4-40 UNC-2B" and tap["thru"] is True
        # The #43 tap drill at the title block's DRILLED HOLES +.004/0.
        assert tap["dia"] == pytest.approx([_in(0.089), _in(0.093)], abs=1e-3)
        assert tap["station"] == pytest.approx(
            [_in(station - 0.005), _in(station + 0.005)], abs=1e-3
        )
        assert tap["height"] == pytest.approx([_in(0.461), _in(0.471)], abs=1e-3)
        assert tap["axis"] == [0.0, 0.0, 1.0] and tap["at"][2] == -spec.GUIDE_DEPTH
    for name, feature in features.items():
        if name.startswith(("platen_tap_", "rack_screw_hole_")):
            assert feature["made_at"] == "assembly"
            assert "station" not in feature and "height" not in feature
    assert features["rack_screw_hole_1"]["cbore_depth"] == pytest.approx(
        [_in(0.214), _in(0.224)], abs=1e-3
    )
    assert features["rack_screw_hole_1"]["cbore_dia"] == pytest.approx(
        [_in(0.125), _in(0.130)], abs=1e-3
    )
