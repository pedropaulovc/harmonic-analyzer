"""Offline contracts for the pen-frame part and drawing."""

from __future__ import annotations

import ast
import inspect
import math
from pathlib import Path

import pytest

import build_pn_pen_frame as part
import draw_pn_pen_frame as drawing
import pn_pen_carriage_geom as carriage
import pn_pen_frame_spec as spec
import pn_pen_v_block_spec as v_block
from _drawing_registry import DRAWINGS_BY_NAME
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
    "BottomWall": spec.RAIL_END,
    "WindowCornerR": spec.WINDOW_CORNER_R,
    "Depth": spec.FRAME_DEPTH,
    "ScrewX": spec.OUTER_WIDTH / 2.0,
    "ScrewZ": spec.FRAME_DEPTH / 2.0,
    "TapWallMin": spec.TAP_WALL_MIN_MM,
}


def _half_width(text: str) -> float:
    return len(text) * _CHAR_WIDTH / 2.0


def _printed_text(name: str) -> str:
    """The decimal-inch text the sheet prints, leading zero dropped."""
    places = spec.DRAWING_PRECISION_BY_NAME[name]
    prefix = drawing.DIMENSION_PREFIXES.get(name, "")
    text = f"{_MODEL_VALUES[name] / 25.4:.{places}f}"
    return prefix + (text[1:] if text.startswith("0.") else text)


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
        spec.DRAWING_DIMENSIONS["RingProfile"] | spec.DRAWING_DIMENSIONS["WindowCorner"]
    )
    for name in (
        "OUTER_WIDTH",
        "OUTER_HEIGHT",
        "RAIL_SIDE",
        "RAIL_END",
        "FRAME_DEPTH",
        "WINDOW_CORNER_R",
    ):
        assert getattr(part, name) is getattr(spec, name)
    assert drawing.WINDOW_CORNER_R is spec.WINDOW_CORNER_R
    assert part.SET_SCREW_TAP_SPEC is spec.SET_SCREW_TAP_SPEC
    assert drawing.SET_SCREW_TAP_SPEC is spec.SET_SCREW_TAP_SPEC
    # The frame spec's copy of the neck depth it passes stays the block's.
    assert spec.V_BLOCK_DEPTH == v_block.NECK_DEPTH
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    local = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert not local & {
        "OUTER_WIDTH",
        "OUTER_HEIGHT",
        "RAIL_SIDE",
        "RAIL_END",
        "FRAME_DEPTH",
        "WINDOW_CORNER_R",
        "SET_SCREW_TAP_SPEC",
        "TRIM_NEAR",
    }


def test_part_names_every_marked_dimension_and_its_drive() -> None:
    source = inspect.getsource(part.build)
    assert "TrimNear" not in source
    assert 'names=["OuterSpanX", "OuterHeightDim"]' in source
    assert "drives=['\"OuterWidth\"', '\"OuterHeight\"']" in source
    # Window size on its left and bottom edges, its corner anchored from the
    # left and bottom outer faces: six dims, no redundancy.
    assert 'names=["WindowHeight", "WindowWidth", "LeftWall", "BottomWall"]' in source
    assert "anchor=1," in source
    assert "(0.0, 0.0)," in source  # the outer chain anchors at the origin
    assert 'name_dimensions(adapter, "Ring", ["Depth"])' in source
    assert "'\"FrameDepth\"'" in source
    assert '("ScrewX", \'"OuterWidth" / 2\')' in source
    assert '("ScrewZ", \'"FrameDepth" / 2\')' in source
    for feature in ("RingProfile", "Ring", "SetScrewAxis"):
        assert f'name_last_feature(adapter, "{feature}")' in source
    assert 'name="ScrewHole"' in source
    # The printed fillet is the top-right corner alone; the other three share
    # the drive.
    assert '("WindowCorner", "WindowCornerR", ((window_x[1], window_y[1]),))' in source
    assert '"OtherWindowCorners"' in source
    assert "add_fillet(WINDOW_CORNER_R, edges)" in source
    assert "'\"WindowCornerR\"'" in source
    assert 'set_global(adapter, "WindowCornerR"' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "clear_dimensions_for_drawing" in source
    assert "require_saved_drawing_properties" in source


def test_part_inner_chain_puts_the_window_dims_on_its_left_and_bottom_edges() -> None:
    # define_rectilinear_chain dims segments 0 and 1 and anchors vertex 1
    # (anchor=1): segment 0 is the window's LEFT edge (top-left down to
    # bottom-left), segment 1 its BOTTOM edge and vertex 1 its bottom-left
    # corner, or the sheet's extension lines would cross the window.
    assert "\n".join(
        f"        ({x}, {y}),"
        for x, y in (
            ("RAIL_SIDE", "OUTER_HEIGHT - RAIL_END"),
            ("RAIL_SIDE", "RAIL_END"),
            ("OUTER_WIDTH - RAIL_SIDE", "RAIL_END"),
            ("OUTER_WIDTH - RAIL_SIDE", "OUTER_HEIGHT - RAIL_END"),
        )
    ) in inspect.getsource(part.build)


def test_volume_expectations_are_analytic() -> None:
    window = (spec.OUTER_WIDTH - 2 * spec.RAIL_SIDE) * (
        spec.OUTER_HEIGHT - 2 * spec.RAIL_END
    )
    ring = (spec.OUTER_WIDTH * spec.OUTER_HEIGHT - window) * spec.FRAME_DEPTH
    assert part.V_RING == pytest.approx(ring) == pytest.approx(4470.391)
    r = spec.WINDOW_CORNER_R
    corners = 4 * (r * r - math.pi * r * r / 4.0) * spec.FRAME_DEPTH
    hole = math.pi * (TAP_DRILL_MM["#4-40"] / 2.0) ** 2 * spec.RAIL_END
    assert part.V_FINAL == pytest.approx(ring + corners - hole)


def test_tapped_hole_is_a_wizard_feature_with_a_native_callout() -> None:
    assert spec.SET_SCREW_TAP_SPEC.kind == "tapped"
    assert spec.SET_SCREW_TAP_SPEC.size == "#4-40"
    assert spec.SET_SCREW_TAP_SPEC.end == "through_next"
    assert "wizard_holes(" in inspect.getsource(part.build)
    source = inspect.getsource(drawing.build)
    assert "add_native_hole_callout(" in source
    assert '"*Bottom"' in source
    assert drawing.HOLE_CENTER_MM == (
        spec.OUTER_WIDTH / 2.0,
        0.0,
        spec.FRAME_DEPTH / 2.0,
    )
    assert drawing.HOLE_R_SHEET == pytest.approx(
        blind_cut_dia_mm(spec.SET_SCREW_TAP_SPEC) * drawing.VIEW_SCALE / 2000.0
    )
    # SolidWorks pins its own "#4-40 Tapped Hole" note once the tap carries
    # the callout; finalize deletes exactly that one, never the callout.
    assert 'redundant_note_substrings=("Tapped Hole",)' in source
    assert "expected_redundant_notes=1" in source
    # The title block's THREADS row owns the 2B class.
    assert (
        'omit_title_block_thread_class(tap_callout, label="thumb-screw tapped hole")'
        in source
    )


def test_no_geometry_rides_in_notes_and_no_gdt() -> None:
    assert spec.DRAWING_NOTES == ""
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source
        for banned in ("author_part_pmi", "PART_DATUMS", "GEOMETRIC_CONTROLS", "_gtol"):
            assert banned not in source


def test_printed_precision_is_authored_for_every_marked_dimension() -> None:
    assert spec.DRAWING_PRECISION.keys() == spec.DRAWING_DIMENSIONS.keys()
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        assert set(spec.DRAWING_PRECISION[feature]) == names
    # Every rail, window and envelope size feeds a printed-worst-case stack,
    # so nothing prints .X; everything prints .XX except the stated tap wall's
    # limit, .XXX.
    three_place = {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 3
    }
    assert three_place == {"TapWallMin"}
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {2, 3}
    assert "assert_imported_precision" in inspect.getsource(drawing.build)


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
    assert spec.TOP_WALL_PRINTED_MIN >= WALL_TARGET_MM
    # Rule 18: 1.5D of full thread in the bottom rail, and not at .X.
    major = THREAD_MAJOR_MM[spec.SET_SCREW_TAP_SPEC.size]
    lead = 1.5 * 25.4 / 40.0
    assert spec.BOTTOM_RAIL_FULL_THREAD_MIN == pytest.approx(spec.RAIL_END - two - lead)
    assert spec.BOTTOM_RAIL_FULL_THREAD_MIN >= 1.5 * major
    assert spec.RAIL_END - one - lead < 1.5 * major
    # Rule 17: the tap station prints .16 (.XX) about the .155 mid-plane, so
    # the near wall keeps the target and the far wall falls between the floor
    # and the target (RV-01), stated natively as .074 MIN.
    printed = 0.16 * 25.4
    assert spec.SET_SCREW_NEAR_WALL_MIN == pytest.approx(printed - two - major / 2.0)
    assert spec.SET_SCREW_NEAR_WALL_MIN >= WALL_TARGET_MM
    far = (spec.FRAME_DEPTH - two) - (printed + two) - major / 2.0
    assert spec.SET_SCREW_FAR_WALL_MIN == pytest.approx(far)
    assert spec.SET_SCREW_PRINTED_WALL_MIN == pytest.approx(far)
    assert WALL_FLOOR_MM <= far < WALL_TARGET_MM
    assert spec.TAP_WALL_MIN_MM == pytest.approx(0.074 * 25.4)
    assert far == pytest.approx(spec.TAP_WALL_MIN_MM, abs=0.001)
    assert spec.TAP_WALL_MIN_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert spec.TAP_WALL_START_Z == pytest.approx(spec.FRAME_DEPTH / 2.0 + major / 2.0)


def test_window_height_band_keeps_the_thumb_screw_throw() -> None:
    # The stirrup hangs from the window's top edge, so a short window lifts
    # its bottom rail toward the marker: the printed band must stay inside the
    # carriage's throw slack, with the block's own printed height band on top.
    slack = carriage.MARKER_BOTTOM_LOCAL_Y - 1.0 - carriage.FRAME_WINDOW_BOTTOM_LOCAL_Y
    window_band = printed_band_mm(
        spec.DRAWING_PRECISION_BY_NAME["WindowHeight"], unit=spec.UNIT
    )
    block_band = max(
        abs(d) for d in printed_deviations(v_block.BLOCK_HEIGHT, 2, unit=v_block.UNIT)
    )
    assert slack >= window_band + block_band


def test_window_corner_radius_clears_the_v_block_top_edges() -> None:
    # The window's top edge seats on the block top; a corner radius larger
    # than the side gap would ride on the block's top edges.
    side_gap = (spec.WINDOW_WIDTH - v_block.NECK_DEPTH) / 2.0
    assert spec.WINDOW_CORNER_R == pytest.approx(side_gap) == pytest.approx(1.016)


def test_views_and_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = inspect.getsource(drawing.build)
    assert source.count("scale=(2, 1)") == 2
    assert "scale=ISO_SCALE" in source
    assert drawing.ISO_SCALE == (2, 1)
    assert '"*Right"' not in source
    assert spec.FRONT_VIEW_NOTE == "FRONT VIEW SCALE 2:1"
    assert spec.BOTTOM_VIEW_NOTE == "BOTTOM VIEW SCALE 2:1"
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert not hasattr(spec, "RIGHT_VIEW_NOTE")
    # finalize_drawing owns the pictorial's Shaded With Edges; an early call
    # read cosmetic-thread quality False on the farm (run 20261014T002650255Z).
    assert "set_high_quality_shaded_with_edges" not in source
    assert "for view in (front, bottom, iso):" in source


def test_isometric_stays_clear_of_the_front_view_border_and_title_block() -> None:
    cx, cy = drawing.ISO_CENTER
    hx, hy = drawing.ISO_HALF_EXTENT
    assert hx == pytest.approx(0.0255, abs=0.001)
    assert hy == pytest.approx(0.0473, abs=0.001)
    # Right of the 40.0 dimension line and the front view's note.
    assert cx - hx > drawing.FRONT_KEEP["OuterHeightDim"][0] + 0.05
    front_note_end = drawing.FRONT_VIEW_NOTE_XY[0] + len(spec.FRONT_VIEW_NOTE) * 0.0025
    assert cx - hx > front_note_end + 0.03
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
    low, high = drawing.FRONT_BOTTOM_Y, drawing._front_xy(0.0, spec.RAIL_END)[1]
    assert low + 0.0035 < keep["BottomWall"][1] < high - 0.0035
    # The left wall stays clear above the bottom view.
    assert keep["LeftWall"][1] - drawing.BOTTOM_HIGH_Y > 0.010


def test_corner_radius_leader_leaves_through_the_right_rail_only() -> None:
    x, y = drawing.FRONT_KEEP["WindowCornerR"]
    half = _half_width(_printed_text("WindowCornerR"))
    cx, cy = drawing.CORNER_ARC_CENTER_XY
    height_line_x = drawing.FRONT_KEEP["OuterHeightDim"][0]
    # Text between the ring's right face and the 40.0's dimension line, under
    # that dimension's top extension line.
    assert x - half > drawing.FRONT_RIGHT_X + 0.003
    assert x + half < height_line_x - 0.005
    assert y + 0.0035 / 2.0 < drawing.FRONT_TOP_Y - 0.002
    # Aimed at the text's centre or its near end, the radial leader lands on
    # the printed arc (0..90 deg) and leaves the ring through its right face,
    # below the top: it crosses no other dimension's extension line.
    for tx in (x - half, x):
        angle = math.degrees(math.atan2(y - cy, tx - cx))
        assert 10.0 < angle < 80.0, angle
        exit_y = cy + (drawing.FRONT_RIGHT_X - cx) * math.tan(math.radians(angle))
        assert exit_y < drawing.FRONT_TOP_Y - 0.002
    assert drawing.DIMENSION_PREFIXES == {"WindowCornerR": "4X R"}
    assert "_set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)" in (
        inspect.getsource(drawing.build)
    )


def test_hole_callout_clears_the_views_and_their_dimensions() -> None:
    x, y = drawing.HOLE_CALLOUT_XY
    assert x > drawing.BOTTOM_RIGHT_X + 0.015
    assert drawing.BOTTOM_HIGH_Y < y < drawing.FRONT_BOTTOM_Y - 0.010
    # Its two lines stand right of the window width's right extension line.
    callout_left = x - _half_width("TAP 4-40 UNC THRU")
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
    assert drawing.HOLE_CALLOUT_PROCESS == "TAP"


def test_tap_wall_text_stands_on_a_shelf_clear_of_every_line() -> None:
    # The wall's run is shorter than its two-row text: the text is offset on
    # a leader, left of where its extension lines end (1 mm past its line).
    line_x, line_y = drawing.BOTTOM_KEEP["TapWallMin"]
    x, y = drawing.TAP_WALL_TEXT_XY
    half = _half_width(".074 MIN")
    assert y == line_y
    assert x + half < line_x - 0.001 - 0.002
    assert x - half > 0.0127  # inside the left border
    # Its rows (value on the anchor, TAP WALL below) stand left of the .16's
    # text and under the front view's lowest dimension row.
    screw_x, _ = drawing.BOTTOM_KEEP["ScrewZ"]
    assert x + half < screw_x - _half_width(_printed_text("ScrewZ")) - 0.002
    assert y + 0.0035 < drawing.FRONT_KEEP["LeftWall"][1] - 0.0035 - 0.005
    assert "_offset_tap_wall_text(adapter, annotations)" in inspect.getsource(
        drawing.build
    )


def test_part_stamps_make_critical_properties() -> None:
    import _config

    config = _config.parts("pn-pen-frame")
    assert config["material"] == "C36000 free-machining brass"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    # No face runs or locates on a lay: the fleet's plain finish, no method.
    assert config["finish"] == "as machined"
    assert int(config["quantity"]) == 1
