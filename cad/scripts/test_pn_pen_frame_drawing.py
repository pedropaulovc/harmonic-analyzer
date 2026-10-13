"""Offline contracts for the pen-frame part and drawing."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import build_pn_pen_frame as part
import draw_pn_pen_frame as drawing
import pn_pen_frame_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import TAP_DRILL_MM, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm

_CHAR_WIDTH = 0.00276  # sheet m per character of 3.5-mm dimension text


def _half_width(text: str) -> float:
    return len(text) * _CHAR_WIDTH / 2.0


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
    assert kept == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.BOTTOM_KEEP)
    assert set(drawing.FRONT_KEEP) == spec.DRAWING_DIMENSIONS["RingProfile"]
    for name in ("OUTER_WIDTH", "OUTER_HEIGHT", "RAIL_SIDE", "RAIL_END", "FRAME_DEPTH"):
        assert getattr(part, name) is getattr(spec, name)
    assert part.SET_SCREW_TAP_SPEC is spec.SET_SCREW_TAP_SPEC
    assert drawing.SET_SCREW_TAP_SPEC is spec.SET_SCREW_TAP_SPEC
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
        "SET_SCREW_TAP_SPEC",
        "TRIM_NEAR",
    }


def test_part_names_every_marked_dimension_and_its_drive() -> None:
    source = inspect.getsource(part.build)
    assert "TrimNear" not in source
    assert 'names=["OuterSpanX", "OuterHeightDim"]' in source
    assert "drives=['\"OuterWidth\"', '\"OuterHeight\"']" in source
    assert (
        'names=["InnerSpanX", "InnerSpanY", "InnerAnchorX", "InnerAnchorY"]' in source
    )
    assert "(0.0, 0.0)," in source  # the outer chain anchors at the origin
    assert 'name_dimensions(adapter, "Ring", ["Depth"])' in source
    assert "'\"FrameDepth\"'" in source
    assert '("ScrewX", \'"OuterWidth" / 2\')' in source
    assert '("ScrewZ", \'"FrameDepth" / 2\')' in source
    for feature in ("RingProfile", "Ring", "SetScrewAxis"):
        assert f'name_last_feature(adapter, "{feature}")' in source
    assert 'name="ScrewHole"' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "clear_dimensions_for_drawing" in source
    assert "require_saved_drawing_properties" in source


def test_volume_expectations_are_analytic() -> None:
    window = (spec.OUTER_WIDTH - 2 * spec.RAIL_SIDE) * (
        spec.OUTER_HEIGHT - 2 * spec.RAIL_END
    )
    ring = (spec.OUTER_WIDTH * spec.OUTER_HEIGHT - window) * spec.FRAME_DEPTH
    assert part.V_RING == pytest.approx(ring) == pytest.approx(4480.0)
    hole = 3.141592653589793 * (TAP_DRILL_MM["#4-40"] / 2.0) ** 2 * spec.RAIL_END
    assert part.V_FINAL == pytest.approx(ring - hole)


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
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {2}
    assert "assert_imported_precision" in inspect.getsource(drawing.build)


def test_printed_worst_case_keeps_the_window_and_the_tap_wall() -> None:
    band = printed_band_mm(2)
    assert spec.WINDOW_WIDTH_PRINTED_MIN == pytest.approx(
        spec.OUTER_WIDTH - band - 2.0 * (spec.RAIL_SIDE + band)
    )
    # At one place (+/-0.8) the window would not pass the 18-deep block.
    one = printed_band_mm(1)
    assert spec.OUTER_WIDTH - one - 2.0 * (spec.RAIL_SIDE + one) < 18.0
    assert spec.WINDOW_WIDTH_PRINTED_MIN > 18.0
    assert spec.SET_SCREW_PRINTED_WALL_MIN >= 1.5


def test_views_and_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = inspect.getsource(drawing.build)
    assert source.count("scale=(2, 1)") == 2
    assert '"*Right"' not in source
    assert spec.FRONT_VIEW_NOTE == "FRONT VIEW SCALE 2:1"
    assert spec.BOTTOM_VIEW_NOTE == "BOTTOM VIEW SCALE 2:1"
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert not hasattr(spec, "RIGHT_VIEW_NOTE")


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
    half = _half_width("40.00")
    half_h = 0.0035 / 2.0
    for x, y in (*drawing.FRONT_KEEP.values(), *drawing.BOTTOM_KEEP.values()):
        for left, low, right, high in (front, bottom):
            outside = (
                x + half < left
                or x - half > right
                or y + half_h < low
                or y - half_h > high
            )
            assert outside, (x, y)
        assert x - half > 0.0127  # inside the left border


def test_hole_callout_clears_the_views_and_their_dimensions() -> None:
    x, y = drawing.HOLE_CALLOUT_XY
    assert x > drawing.BOTTOM_RIGHT_X + 0.015
    assert drawing.BOTTOM_HIGH_Y < y < drawing.FRONT_BOTTOM_Y - 0.010
    depth_x, _ = drawing.BOTTOM_KEEP["Depth"]
    # The straight leader from the tap mouth crosses the depth's dimension
    # line well above the bottom view's top edge.
    hx, hy = drawing.HOLE_SHEET_XY
    leader_y = hy + (y - hy) * (depth_x - hx) / (x - hx)
    assert leader_y > drawing.BOTTOM_HIGH_Y + 0.008
    assert drawing.HOLE_CALLOUT_PROCESS == "TAP"


def test_part_stamps_make_critical_properties() -> None:
    import _config

    config = _config.parts("pn-pen-frame")
    assert config["material"] == "C36000 free-machining brass"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
