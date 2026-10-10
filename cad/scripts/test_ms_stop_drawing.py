"""Offline observable contracts for the separate brass stop block and cover."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import build_ms_stop_block as block
import build_ms_stop_plate as plate
import draw_ms_stop_block as block_drawing
import draw_ms_stop_plate as plate_drawing
import ms_stick_spec as stick
import ms_stop_spec as spec
import vn_ms_stop_plate_screw_spec as screw
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import DRILL_POINT_H


def test_shared_frame_and_open_rebate_closure() -> None:
    assert (spec.BLOCK_LENGTH, spec.BLOCK_HEIGHT, spec.BLOCK_DEPTH) == (21.0, 14.1, 11.0)
    assert (spec.PLATE_Z_MIN, spec.PLATE_Z_MAX, spec.PLATE_THICKNESS) == (-1.0, 0.0, 1.0)
    assert spec.TOTAL_DEPTH == 12.0
    assert (spec.WINDOW_Z_MIN, spec.WINDOW_Z_MAX) == (0.0, 8.4)
    assert (spec.WINDOW_Y_MIN, spec.WINDOW_Y_MAX) == pytest.approx((8.6, 12.0))
    assert spec.WINDOW_Y_MAX + spec.ROOF_THICKNESS == spec.BLOCK_HEIGHT
    assert spec.ROOF_THICKNESS == 2.1
    assert spec.ROOF_THICKNESS - 0.51 >= 1.5
    assert "WindowFloor" not in set().union(*spec.BLOCK_DRAWING_DIMENSIONS.values())
    assert "RoofThickness" in spec.BLOCK_DRAWING_DIMENSIONS["RoofThicknessReference"]
    assert spec.BACK_WALL_THICKNESS == pytest.approx(2.6)
    assert spec.ROOF_END_CHAMFER == 1.0 and spec.ROOF_CHAMFER_ANGLE == 45.0
    assert spec.STOP_MARK == 2.0
    assert block.MATERIAL == plate.MATERIAL == "Brass"


def test_native_taps_and_plate_clearance_follow_stock_screws() -> None:
    assert screw.SKU == "90114A124"
    assert spec.PLATE_SCREW_THREAD == screw.THREAD
    assert spec.PLATE_SCREW_MAJOR_DIA == screw.MAJOR_DIA
    assert spec.PLATE_SCREW_LENGTH == screw.LENGTH
    assert spec.PLATE_TAP_SPEC.kind == "tapped_bottoming"
    assert spec.PLATE_TAP_SPEC.size == screw.THREAD
    assert spec.PLATE_TAP_SPEC.end == "blind"
    assert spec.PLATE_TAP_SPEC.depth_mm == spec.PLATE_TAP_DRILL_DEPTH == 7.8
    assert spec.PLATE_TAP_SPEC.overrides_mm["ThreadDepth"] == spec.PLATE_TAP_THREAD_DEPTH == 6.3
    assert spec.PLATE_TAP_SPEC.overrides_mm["TapDrillDiameter"] == spec.PLATE_TAP_DRILL_DIA == 1.85
    assert spec.PLATE_CLEARANCE_SPEC.overrides_mm["HoleDiameter"] == spec.PLATE_CLEARANCE_DIA == 2.4
    assert spec.THUMB_TAP_SPEC.kind == "tapped" and spec.THUMB_TAP_SPEC.size == "#4-40"
    # Through-all would drill the opposite roof as well as the thick floor.
    assert spec.THUMB_TAP_SPEC.end == "through_next"
    assert (spec.THUMB_AXIS_X, spec.THUMB_AXIS_Z) == (10.5, 4.2)
    assert spec.THUMB_HOLE_POINTS == ((10.5, 0.0, 4.2),)
    assert spec.THUMB_HOLE_NORMAL == (0.0, -1.0, 0.0)
    assert spec.PLATE_HOLE_XS == (3.5, 17.5) and spec.PLATE_HOLE_Y == 4.0
    assert spec.PLATE_HOLE_PITCH == 14.0
    assert spec.PLATE_HOLE_NORMAL == (0.0, 0.0, -1.0)
    assert spec.BLOCK_PLATE_HOLE_POINTS == ((3.5, 4.0, 0.0), (17.5, 4.0, 0.0))
    assert spec.PLATE_HOLE_POINTS == ((3.5, 4.0, -1.0), (17.5, 4.0, -1.0))


def test_receiver_engagement_and_separation_are_real_geometry() -> None:
    assert spec.PLATE_SCREW_PENETRATION == pytest.approx(5.35)
    assert 1.5 * screw.MAJOR_DIA < spec.PLATE_SCREW_PENETRATION < spec.PLATE_TAP_THREAD_DEPTH
    assert spec.PLATE_SCREW_PENETRATION < spec.PLATE_TAP_DRILL_DEPTH
    tip = spec.PLATE_TAP_DRILL_DEPTH + spec.PLATE_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
    assert spec.PLATE_TAP_TIP_Z == pytest.approx(tip)
    assert spec.BLOCK_DEPTH - tip > 2.0
    assert spec.PLATE_HOLE_Y + screw.MAJOR_DIA / 2.0 < spec.WINDOW_Y_MIN - 2.0
    for x in spec.PLATE_HOLE_XS:
        assert abs(x - spec.THUMB_AXIS_X) - (screw.MAJOR_DIA + spec.THUMB_MAJOR_DIA) / 2.0 > 2.0


def test_print_worst_joint_stack_preserves_bottoming_tap_and_ligaments() -> None:
    assert spec.PLATE_THICKNESS_MIN == pytest.approx(0.9)
    assert spec.PLATE_THICKNESS_MAX == pytest.approx(1.1)
    assert spec.PLATE_FULL_THREAD_MIN == pytest.approx(5.79)
    assert spec.PLATE_SCREW_PENETRATION_MAX == pytest.approx(5.704)
    assert spec.PLATE_SCREW_PENETRATION_MIN >= 1.5 * screw.MAJOR_DIA
    assert spec.PLATE_SCREW_PENETRATION_MAX < spec.PLATE_FULL_THREAD_MIN
    assert spec.PLATE_TAP_LEAD_MIN == pytest.approx(0.48)
    assert spec.PLATE_TAP_LEAD_MIN >= screw.PITCH
    assert spec.PLATE_TAP_BACK_WALL_MIN == pytest.approx(1.59416, abs=1e-5)
    assert spec.PLATE_TAP_BACK_WALL_MIN >= 1.5
    assert spec.ROOF_THICKNESS_MIN == pytest.approx(1.59)
    assert spec.PLATE_TAP_WINDOW_WEB_MIN == pytest.approx(2.2878)
    assert spec.PLATE_TAP_END_WEB_MIN == pytest.approx(1.7978)
    assert spec.PLATE_RADIAL_CLEARANCE_MIN == pytest.approx(0.1078)
    assert spec.ROOF_OPEN_END_EDGE == pytest.approx(1.1)


def test_matched_pair_uses_functional_positions_and_a_real_shop_sequence() -> None:
    assert spec.PLATE_HOLE_POSITION_TOLERANCE_MM == 0.1
    assert all(block_point[:2] == plate_point[:2] for block_point, plate_point
               in zip(spec.BLOCK_PLATE_HOLE_POINTS, spec.PLATE_HOLE_POINTS, strict=True))
    assert "MATCH-DRILL" in spec.DRAWING_NOTES
    assert "CLAMPED TOGETHER" in spec.DRAWING_NOTES
    assert "OPEN PLATE CLEARANCE AFTER PILOT" in spec.DRAWING_NOTES
    assert "BOTTOMING-TAP BLOCK" in spec.DRAWING_NOTES
    assert "NOT INTERCHANGEABLE" in spec.DRAWING_NOTES
    assert "BLIND DEPTHS FROM BLOCK MATING FACE" in spec.DRAWING_NOTES
    for drawing in (block_drawing, plate_drawing):
        source = Path(drawing.__file__).read_text(encoding="utf-8")
        assert '"Manufacturing Notes"' in source
        assert "2X MATCH-DRILL" in source


def test_window_keeps_functional_clearance_at_printed_size_limits() -> None:
    window_lower, _window_upper = spec.WINDOW_SIZE_TOLERANCE_MM
    assert spec.WINDOW_WIDTH + window_lower - (stick.BODY_WIDTH + stick.BODY_FIT_TOLERANCE_MM) >= 0.3 - 1e-9
    assert spec.WINDOW_HEIGHT + window_lower - (stick.BODY_THICKNESS + stick.BODY_FIT_TOLERANCE_MM) >= 0.3 - 1e-9
    assert spec.PLATE_CLEARANCE_DIA > screw.MAJOR_DIA


def test_analytic_volume_has_no_merged_thumbscrew_or_hidden_extra_wall() -> None:
    assert spec.BLOCK_CHAMFER_VOLUME == spec.ROOF_END_CHAMFER**2 * spec.BLOCK_DEPTH
    assert spec.THUMB_HOLE_VOLUME == pytest.approx(math.pi * (spec.THUMB_TAP_DRILL / 2.0)**2 * spec.FLOOR_THICKNESS)
    assert spec.BLOCK_FINISHED_VOLUME == pytest.approx(
        spec.BLOCK_VOLUME - spec.WINDOW_VOLUME - spec.BLOCK_CHAMFER_VOLUME - spec.THUMB_HOLE_VOLUME - spec.PLATE_TAP_VOLUME)
    assert spec.PLATE_FINISHED_VOLUME == pytest.approx(
        spec.PLATE_VOLUME - spec.PLATE_CHAMFER_VOLUME - spec.PLATE_HOLE_VOLUME)
    assert 0.0 < spec.BLOCK_FINISHED_VOLUME < spec.BLOCK_VOLUME
    assert 0.0 < spec.PLATE_FINISHED_VOLUME < spec.PLATE_VOLUME


@pytest.mark.parametrize("builder,drawing,dimensions,precision,values,stem", [
    (block, block_drawing, spec.BLOCK_DRAWING_DIMENSIONS, spec.BLOCK_DRAWING_PRECISION_BY_NAME, spec.BLOCK_DRAWING_VALUES_BY_NAME, "ms-stop-block"),
    (plate, plate_drawing, spec.PLATE_DRAWING_DIMENSIONS, spec.PLATE_DRAWING_PRECISION_BY_NAME, spec.PLATE_DRAWING_VALUES_BY_NAME, "ms-stop-plate"),
])
def test_each_sheet_imports_the_complete_model_contract(builder, drawing, dimensions, precision, values, stem) -> None:
    assert builder.PART_NAME == drawing.PART_STEM == stem
    assert DRAWINGS_BY_NAME[stem.replace("-", "_")].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.name == f"{stem}.SLDDRW" and drawing.PDF.name == f"{stem}.pdf"
    assert builder.DRAWING_DIMENSIONS is dimensions
    marked = set().union(*dimensions.values())
    keeps = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    if hasattr(drawing, "BOTTOM_KEEP"):
        keeps |= set(drawing.BOTTOM_KEEP)
    assert marked == keeps == set(precision) == set(values)
    assert all(places == 2 for places in precision.values())
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]
    assert not any(character.isdigit() for character in spec.DRAWING_NOTES)


@pytest.mark.parametrize("module", [spec, block_drawing, plate_drawing])
def test_no_com_in_spec_or_render_time_size_overrides(module) -> None:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    if module is spec:
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any(name.startswith(("build_", "solidworks", "_common", "_drawing")) for name in imports)
    else:
        calls = {node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                 for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, (ast.Attribute, ast.Name))}
        assert not calls & {"SetPrecision3", "set_dimension_precision", "SetValues", "set_hole_callout_precision", "add_gdt_frame", "add_datum_tag"}
