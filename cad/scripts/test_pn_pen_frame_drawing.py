"""Offline contracts for the pen-frame part and drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_pn_pen_frame as part
import draw_pn_pen_frame as drawing
import export_features
import pn_pen_carriage_geom as carriage
import pn_pen_frame_spec as spec
import pn_pen_v_block_spec as v_block
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_face import FaceGeometry
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import printed_band_mm, printed_deviations

_CHAR_WIDTH = 0.00276  # sheet m per character of 3.5-mm dimension text

# Model value behind every printed dimension, for its printed text.
_MODEL_VALUES = {
    "OuterSpanX": spec.OUTER_WIDTH,
    "OuterHeightDim": spec.OUTER_HEIGHT,
    "WindowWidth": spec.WINDOW_WIDTH,
    "WindowHeight": spec.WINDOW_HEIGHT,
    "LeftWall": spec.RAIL_SIDE,
    "BottomWall": spec.RAIL_BOTTOM,
    "Depth": spec.FRAME_DEPTH,
    "ScrewX": spec.OUTER_WIDTH / 2.0,
    "ScrewZ": spec.FRAME_DEPTH / 2.0,
    "WindowCornerR": spec.WINDOW_CORNER_R,
}


def _half_width(text: str) -> float:
    return len(text) * _CHAR_WIDTH / 2.0


def _printed_text(name: str) -> str:
    """The decimal-inch text the sheet prints, leading zero dropped, behind
    its native prefix (the window corners' 4X R)."""
    places = spec.DRAWING_PRECISION_BY_NAME[name]
    text = f"{_MODEL_VALUES[name] / 25.4:.{places}f}"
    text = text[1:] if text.startswith("0.") else text
    return spec.DIMENSION_PREFIXES.get(name, "") + text


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-pen-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-pen-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-pen-frame_drawing.png")
    assert DRAWINGS_BY_NAME["pn_pen_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_geometry_and_marked_dimensions() -> None:
    # The drift alarm: the part marks and the drawing keeps exactly the spec's
    # map, and both read the spec's geometry, not divergent copies.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.BOTTOM_KEEP)
    assert kept == marked == set(_MODEL_VALUES)
    assert not set(drawing.FRONT_KEEP) & set(drawing.BOTTOM_KEEP)
    assert set(drawing.FRONT_KEEP) == (
        spec.DRAWING_DIMENSIONS["RingProfile"] | spec.DRAWING_DIMENSIONS["WindowCorners"]
    )
    for name in (
        "OUTER_WIDTH",
        "OUTER_HEIGHT",
        "RAIL_SIDE",
        "RAIL_BOTTOM",
        "RAIL_TOP",
        "FRAME_DEPTH",
        "WINDOW_CORNER_R",
    ):
        assert getattr(part, name) is getattr(spec, name)
    assert part.SET_SCREW_TAP_SPEC is spec.SET_SCREW_TAP_SPEC
    assert drawing.SET_SCREW_TAP_SPEC is spec.SET_SCREW_TAP_SPEC
    # The frame spec's copy of the neck depth it passes stays the block's.
    assert spec.V_BLOCK_DEPTH == v_block.NECK_DEPTH


def test_volume_expectations_are_analytic() -> None:
    window = (spec.OUTER_WIDTH - 2 * spec.RAIL_SIDE) * (
        spec.OUTER_HEIGHT - spec.RAIL_BOTTOM - spec.RAIL_TOP
    )
    ring = (spec.OUTER_WIDTH * spec.OUTER_HEIGHT - window) * spec.FRAME_DEPTH
    assert part.V_RING == pytest.approx(ring) == pytest.approx(3816.088, abs=1e-3)
    r = spec.WINDOW_CORNER_R
    corners = 4 * (r * r - math.pi * r * r / 4.0) * spec.FRAME_DEPTH
    hole = math.pi * (TAP_DRILL_MM["#4-40"] / 2.0) ** 2 * spec.RAIL_BOTTOM
    assert part.V_FINAL == pytest.approx(ring + corners - hole)


def test_tapped_hole_is_a_wizard_feature_with_a_native_callout() -> None:
    assert spec.SET_SCREW_TAP_SPEC.kind == "tapped"
    assert spec.SET_SCREW_TAP_SPEC.size == "#4-40"
    assert spec.SET_SCREW_TAP_SPEC.end == "through_next"
    assert drawing.HOLE_CENTER_MM == (
        spec.OUTER_WIDTH / 2.0,
        0.0,
        spec.FRAME_DEPTH / 2.0,
    )
    assert drawing.HOLE_R_SHEET == pytest.approx(
        blind_cut_dia_mm(spec.SET_SCREW_TAP_SPEC) * drawing.VIEW_SCALE / 2000.0
    )


def test_no_geometry_rides_in_notes_and_no_gdt() -> None:
    assert spec.DRAWING_NOTES == ""


def test_printed_precision_is_authored_for_every_marked_dimension() -> None:
    assert spec.DRAWING_PRECISION.keys() == spec.DRAWING_DIMENSIONS.keys()
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        assert set(spec.DRAWING_PRECISION[feature]) == names
    # Every rail, window and envelope size feeds a printed-worst-case stack,
    # so nothing prints .X: everything prints the title block's .XX, the
    # window corners' R.065 its .XXX (.060-.070, owner ruling 2026-11-23,
    # tool audit Q9).
    assert {
        name: places
        for name, places in spec.DRAWING_PRECISION_BY_NAME.items()
        if places != 2
    } == {"WindowCornerR": 3}


def test_printed_worst_case_keeps_the_window_rails_thread_and_tap_wall() -> None:
    unit = spec.UNIT
    one, two = (printed_band_mm(n, unit=unit) for n in (1, 2))
    # The window width prints directly: it passes the block at both parts'
    # loosest printed limits.
    assert spec.WINDOW_WIDTH_PRINTED_MIN == pytest.approx(spec.WINDOW_WIDTH - two)
    assert spec.WINDOW_WIDTH_PRINTED_MIN > v_block.NECK_WIDTH_PRINTED_MAX
    # The unprinted right and top rails meet the rule 17 .080 target.
    assert spec.RIGHT_WALL_PRINTED_MIN == pytest.approx(
        (spec.OUTER_WIDTH - two) - (spec.RAIL_SIDE + two) - (spec.WINDOW_WIDTH + two)
    )
    assert spec.RIGHT_WALL_PRINTED_MIN >= WALL_TARGET_MM
    # At .X the envelope would leave the right rail under the floor.
    assert (spec.OUTER_WIDTH - one) - (spec.RAIL_SIDE + two) - (
        spec.WINDOW_WIDTH + two
    ) < WALL_FLOOR_MM
    # The top rail, thinned to .22 (owner ruling 2026-11-23, PN-01 B1), is
    # unprinted: 1.57 - .25 - 1.13 = .19 at the printed worst, over the target.
    assert spec.RAIL_TOP == pytest.approx(0.22 * 25.4)
    assert spec.WINDOW_HEIGHT == pytest.approx(1.12 * 25.4)
    assert spec.OUTER_HEIGHT == pytest.approx(1.58 * 25.4)
    assert spec.TOP_WALL_PRINTED_MIN == pytest.approx(
        (spec.OUTER_HEIGHT - two)
        - (spec.RAIL_BOTTOM + two)
        - (spec.WINDOW_HEIGHT + two)
    )
    assert spec.TOP_WALL_PRINTED_MIN == pytest.approx(0.19 * 25.4)
    assert spec.TOP_WALL_PRINTED_MIN >= WALL_TARGET_MM
    # Per unit thumb-screw load the thinned top rail, at its printed worst,
    # bends less than the unchanged bottom rail at its printed best: 0.44 of
    # its stress, 0.55 of its deflection.
    assert spec.TOP_RAIL_STRESS_RATIO == pytest.approx(0.439, abs=1e-3)
    assert spec.TOP_RAIL_DEFLECTION_RATIO == pytest.approx(0.546, abs=1e-3)
    # Rule 18: 1.5D of full thread in the bottom rail, and not at .X.
    major = THREAD_MAJOR_MM[spec.SET_SCREW_TAP_SPEC.size]
    lead = 1.5 * 25.4 / 40.0
    assert spec.BOTTOM_RAIL_FULL_THREAD_MIN == pytest.approx(
        spec.RAIL_BOTTOM - two - lead
    )
    assert spec.BOTTOM_RAIL_FULL_THREAD_MIN >= 1.5 * major
    assert spec.RAIL_BOTTOM - one - lead < 1.5 * major
    # Rule 17: the tap station prints .16 (.XX) about the .155 mid-plane, so
    # the near wall keeps the target and the far wall falls between the floor
    # and the target (RV-01), stated once on the .16 that sets it (rule 20).
    printed = 0.16 * 25.4
    assert spec.SET_SCREW_NEAR_WALL_MIN == pytest.approx(printed - two - major / 2.0)
    assert spec.SET_SCREW_NEAR_WALL_MIN >= WALL_TARGET_MM
    far = (spec.FRAME_DEPTH - two) - (printed + two) - major / 2.0
    assert spec.SET_SCREW_FAR_WALL_MIN == pytest.approx(far)
    assert spec.SET_SCREW_PRINTED_WALL_MIN == pytest.approx(far)
    assert WALL_FLOOR_MM <= far < WALL_TARGET_MM
    assert spec.TAP_WALL_MIN_MM == pytest.approx(0.074 * 25.4)
    assert far == pytest.approx(spec.TAP_WALL_MIN_MM, abs=0.001)
    assert list(spec.DIMENSION_CALLOUTS) == ["ScrewZ", "WindowCornerR"]
    assert ".074 MIN" in spec.DIMENSION_CALLOUTS["ScrewZ"]


def test_window_height_band_keeps_the_thumb_screw_throw() -> None:
    # The stirrup hangs from the window's top edge, so a short window lifts
    # its bottom rail toward the marker: the printed band must stay inside the
    # carriage's throw slack, with the block's own printed height band and the
    # window corners' worst ride on the neck (below) on top.  Owner ruling
    # 2026-11-23, PN-01 B1: the 1.12 window (the top rail .22, the outside
    # unchanged) drops the bottom rail .02 farther from the marker.  At R.070
    # the slack is 2.553 against 0.254 + 0.288 + 1.778, so 0.233 spare.  The
    # 1.10 window would have left -0.275 (sketch q9-pn01-throw-stack.png).
    slack = carriage.MARKER_BOTTOM_LOCAL_Y - 1.0 - carriage.FRAME_WINDOW_BOTTOM_LOCAL_Y
    window_band = printed_band_mm(
        spec.DRAWING_PRECISION_BY_NAME["WindowHeight"], unit=spec.UNIT
    )
    block_band = max(
        abs(d) for d in printed_deviations(v_block.BLOCK_HEIGHT, 2, unit=v_block.UNIT)
    )
    needed = window_band + block_band + carriage.WINDOW_CORNER_RIDE_MAX
    assert (slack, window_band, block_band) == pytest.approx(
        (2.553, 0.254, 0.288), abs=1e-3
    )
    assert carriage.WINDOW_CORNER_RIDE_MAX == pytest.approx(0.070 * 25.4)
    assert slack - needed == pytest.approx(0.233, abs=1e-3)
    assert slack >= needed
    assert slack - 0.02 * 25.4 - needed == pytest.approx(-0.275, abs=1e-3)


def _corner_ride(r: float, gap: float) -> float:
    """Lift of a radius-``r`` window corner riding a neck top edge ``gap`` in
    from its side wall: the edge sits on the corner's arc."""
    return 0.0 if gap >= r else r - math.sqrt(r * r - (r - gap) ** 2)


def test_window_corners_print_r065_and_ride_the_neck_at_most_a_full_radius() -> None:
    # Owner ruling 2026-11-23, tool audit Q9: the window corners print 4X
    # R.065 at three places (.060-.070, the title block's .XXX), naming why
    # they stand over INSIDE CORNERS R.040 MAX.  With the window at its
    # printed minimum, the neck at its printed maximum and the stirrup
    # anywhere across the neck (nothing centres it), the corners ride the
    # neck's top edges and lift the stirrup: the carriage takes the worst
    # lift, at the band's greatest R.070.
    assert spec.WINDOW_CORNER_R == pytest.approx(0.065 * 25.4)
    assert (spec.WINDOW_CORNER_R_MIN, spec.WINDOW_CORNER_R_MAX) == pytest.approx(
        (0.060 * 25.4, 0.070 * 25.4)
    )
    assert spec.DRAWING_DIMENSIONS["WindowCorners"] == {"WindowCornerR"}
    assert spec.DIMENSION_PREFIXES == {"WindowCornerR": "4X R"}
    assert spec.DIMENSION_CALLOUTS["WindowCornerR"] == "NOTHING SEATS IN\nTHESE CORNERS"
    r = spec.WINDOW_CORNER_R_MAX
    band = printed_band_mm(2, unit=spec.UNIT)
    float_total = spec.WINDOW_WIDTH - band - (v_block.NECK_DEPTH + 2.0 * band)
    assert float_total > 0.0
    shifts = [float_total * i / 100.0 for i in range(101)]
    worst = max(
        max(_corner_ride(r, s), _corner_ride(r, float_total - s)) for s in shifts
    )
    assert carriage.window_corner_ride_max() == pytest.approx(worst)
    # Centred, the corners would lift it far less.
    assert _corner_ride(r, float_total / 2.0) < worst / 1.5


def test_views_and_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.ISO_SCALE == (2, 1)
    # Rule 9: every view is at the sheet scale, so no caption states one, and
    # the projected front and bottom views carry no label.
    assert "SCALE" not in spec.ISOMETRIC_VIEW_NOTE
    for retired in ("FRONT_VIEW_NOTE", "BOTTOM_VIEW_NOTE", "RIGHT_VIEW_NOTE"):
        assert not hasattr(spec, retired)


def test_isometric_stays_clear_of_the_front_view_border_and_title_block() -> None:
    cx, cy = drawing.ISO_CENTER
    hx, hy = drawing.ISO_HALF_EXTENT
    assert hx == pytest.approx(0.0235, abs=0.001)
    assert hy == pytest.approx(0.0473, abs=0.001)
    # Right of the 40.0 dimension line.
    assert cx - hx > drawing.FRONT_KEEP["OuterHeightDim"][0] + 0.05
    assert cy + hy < 0.267 - 0.02  # under the top border
    # Its note sits below the view, centred under it, well above the title block.
    nx, ny = drawing.ISO_VIEW_NOTE_XY
    note_width = len(spec.ISOMETRIC_VIEW_NOTE) * 0.0025
    assert abs(nx + note_width / 2.0 - cx) < 0.006
    assert cy - hy - 0.010 > ny > 0.065 + 0.03


def test_bottom_view_projects_under_the_front_view_on_the_hole_axis() -> None:
    assert drawing.BOTTOM_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.BOTTOM_HIGH_Y < drawing.FRONT_BOTTOM_Y - 0.02
    assert drawing.HOLE_SHEET_XY == pytest.approx(drawing.BOTTOM_CENTER)


def test_dimension_text_stands_outside_the_silhouettes() -> None:
    front = (
        drawing.FRONT_LEFT_X,
        drawing.FRONT_BOTTOM_Y,
        drawing.FRONT_RIGHT_X,
        drawing.FRONT_TOP_Y,
    )
    bottom = (
        drawing.BOTTOM_LEFT_X,
        drawing.BOTTOM_LOW_Y,
        drawing.BOTTOM_RIGHT_X,
        drawing.BOTTOM_HIGH_Y,
    )
    half_h = 0.0035 / 2.0
    for name, (x, y) in (*drawing.FRONT_KEEP.items(), *drawing.BOTTOM_KEEP.items()):
        half = _half_width(_printed_text(name))
        for left, low, right, high in (front, bottom):
            outside = (
                x + half < left
                or x - half > right
                or y + half_h < low
                or y - half_h > high
            )
            assert outside, (name, x, y)
        assert x - half > 0.0127  # inside the left border


def test_front_dimensions_stack_smaller_nearer_the_ring() -> None:
    keep = drawing.FRONT_KEEP
    # Left: window height inboard of the bottom wall; below: window width
    # inboard of the left wall; each text clear of its neighbour's line.
    assert keep["BottomWall"][0] < keep["WindowHeight"][0] < drawing.FRONT_LEFT_X
    assert (
        keep["WindowHeight"][0] - _half_width(_printed_text("WindowHeight"))
        > keep["BottomWall"][0] + 0.003
    )
    assert (
        keep["WindowHeight"][0] + _half_width(_printed_text("WindowHeight"))
        < drawing.FRONT_LEFT_X - 0.003
    )
    assert keep["LeftWall"][1] < keep["WindowWidth"][1] < drawing.FRONT_BOTTOM_Y
    assert keep["WindowWidth"][1] - keep["LeftWall"][1] >= 0.008
    # The bottom wall's text sits between its own extension lines.
    low, high = drawing.FRONT_BOTTOM_Y, drawing._front_xy(0.0, spec.RAIL_BOTTOM)[1]
    assert low + 0.0035 < keep["BottomWall"][1] < high - 0.0035
    # The left wall stays clear above the bottom view.
    assert keep["LeftWall"][1] - drawing.BOTTOM_HIGH_Y > 0.010


def test_hole_callout_clears_the_views_and_their_dimensions() -> None:
    x, y = drawing.HOLE_CALLOUT_XY
    assert x > drawing.BOTTOM_RIGHT_X + 0.015
    assert drawing.BOTTOM_HIGH_Y < y < drawing.FRONT_BOTTOM_Y - 0.010
    # Its two lines stand right of the window width's right extension line.
    callout_left = x - _half_width("4-40 UNC THRU")
    assert (
        callout_left
        > drawing._front_xy(spec.OUTER_WIDTH - spec.RAIL_SIDE, 0)[0] + 0.005
    )
    depth_x, _ = drawing.BOTTOM_KEEP["Depth"]
    # The straight leader from the tap mouth passes the depth's dimension line
    # well above the bottom view's top edge.
    hx, hy = drawing.HOLE_SHEET_XY
    leader_y = hy + (y - hy) * (depth_x - hx) / (x - hx)
    assert leader_y > drawing.BOTTOM_HIGH_Y + 0.008


def test_station_text_stands_on_a_shelf_clear_of_every_line() -> None:
    # The .16's run is shorter than its two rows: the text is offset on a
    # leader, left of where its extension lines end (1 mm past its line).
    line_x, line_y = drawing.BOTTOM_KEEP["ScrewZ"]
    x, y = drawing.SCREW_Z_TEXT_XY
    half = _half_width(spec.DIMENSION_CALLOUTS["ScrewZ"])
    assert y == line_y
    assert x + half < line_x - 0.001 - 0.002
    assert x - half > 0.0127  # inside the left border
    # Its rows (value on the anchor, the wall below) stand under the front
    # view's lowest dimension row.
    assert y + 0.0035 < drawing.FRONT_KEEP["LeftWall"][1] - 0.0035 - 0.005


def test_part_stamps_make_critical_properties() -> None:
    import _config

    config = _config.parts("pn-pen-frame")
    assert config["material"] == "C36000 free-machining brass"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    # No face runs or locates on a lay: the fleet's plain finish, no method.
    assert config["finish"] == "as machined"
    assert int(config["quantity"]) == 1


def test_tap_precision_goes_to_the_drill_variable_the_callout_carries() -> None:
    assert (
        drawing._tap_drill_variable({7: "<MOD-DIAM><hw-tapdrldia> <hw-thru>"})
        == "hw-tapdrldia"
    )
    assert (
        drawing._tap_drill_variable({8: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>"})
        == "hw-thrutapdrldia"
    )
    with pytest.raises(RuntimeError):
        drawing._tap_drill_variable({5: "TAP <hw-threaddesc> <hw-thru>"})


def _in(value_in: float) -> float:
    return value_in * 25.4


_FEATURE_KINDS = {
    "left_face": "face",
    "bottom_face": "face",
    "front_face": "face",
    "right_face": "face",
    "top_face": "face",
    "back_face": "face",
    "window": "pocket",
    "thumb_screw_tap": "threaded_hole",
}


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def test_the_ring_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert "pn_pen_frame" in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest("pn_pen_frame")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == []
    selectors = export_features.feature_selectors("pn_pen_frame")
    w, h, d = spec.OUTER_WIDTH, spec.OUTER_HEIGHT, spec.FRAME_DEPTH
    x0, x1 = spec.RAIL_SIDE, spec.RAIL_SIDE + spec.WINDOW_WIDTH
    y0, y1 = spec.RAIL_BOTTOM, spec.RAIL_BOTTOM + spec.WINDOW_HEIGHT
    r = spec.WINDOW_CORNER_R
    corners = [
        _cylinder(
            2 * r,
            (0.0, 0.0, 1.0),
            (
                min(x, x + sx * r),
                min(y, y + sy * r),
                0.0,
                max(x, x + sx * r),
                max(y, y + sy * r),
                d,
            ),
        )
        for x, sx in ((x0, 1.0), (x1, -1.0))
        for y, sy in ((y0, 1.0), (y1, -1.0))
    ]
    tap = blind_cut_dia_mm(spec.SET_SCREW_TAP_SPEC)
    tr = tap / 2
    expected = {
        "left_face": [_plane((-1.0, 0.0, 0.0), 0.0)],
        "bottom_face": [_plane((0.0, -1.0, 0.0), 0.0)],
        "front_face": [_plane((0.0, 0.0, -1.0), 0.0)],
        "right_face": [_plane((1.0, 0.0, 0.0), w)],
        "top_face": [_plane((0.0, 1.0, 0.0), h)],
        "back_face": [_plane((0.0, 0.0, 1.0), d)],
        "window": [
            _plane((1.0, 0.0, 0.0), x0),
            _plane((-1.0, 0.0, 0.0), -x1),
            _plane((0.0, 1.0, 0.0), y0),
            _plane((0.0, -1.0, 0.0), -y1),
            *corners,
        ],
        "thumb_screw_tap": [
            _cylinder(
                tap,
                (0.0, 1.0, 0.0),
                (w / 2 - tr, 0.0, d / 2 - tr, w / 2 + tr, y0, d / 2 + tr),
            )
        ],
    }
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name


def test_ring_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest("pn_pen_frame")["features"]
    assert features["right_face"]["width"] == pytest.approx([_in(0.99), _in(1.01)])
    assert features["top_face"]["height"] == pytest.approx([_in(1.57), _in(1.59)])
    assert features["back_face"]["depth"] == pytest.approx([_in(0.30), _in(0.32)])
    window = features["window"]
    assert window["width"] == pytest.approx([_in(0.73), _in(0.75)])
    assert window["height"] == pytest.approx([_in(1.11), _in(1.13)])
    assert window["left_wall"] == pytest.approx([_in(0.12), _in(0.14)])
    assert window["bottom_wall"] == pytest.approx([_in(0.23), _in(0.25)])
    assert window["corner_r"] == pytest.approx([_in(0.060), _in(0.070)])
    assert window["corner_count"] == 4
    tap = features["thumb_screw_tap"]
    assert tap["thread"] == "#4-40 UNC-2B" and tap["thru"] is True
    assert tap["breaks_into"] == "window"
    assert tap["dia"] == pytest.approx([_in(0.089), _in(0.093)], abs=1e-3)
    assert tap["station"] == pytest.approx([_in(0.49), _in(0.51)])
    # The .16 prints rounded from the .155 mid-plane; its band is the printed one.
    assert tap["depth_station"] == pytest.approx([_in(0.15), _in(0.17)])
    assert tap["wall_note"] == spec.TAP_WALL_CALLOUT
