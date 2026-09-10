"""Offline contracts for the rocker-arm-support drawing."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import _config
import _drawing_common

import draw_rocker_arm_support as drawing
import build_rocker_arm_support as support
import build_frame_assembly as frame
import build_lag_screw as screw
import rocker_arm_support_spec as placement
import rocker_arm_support_drawing_spec as drawing_spec


def test_drawing_keeps_only_one_dimension_for_each_square() -> None:
    expected = {
        "FootSpan",
        "TopSpan",
        "WallHeight",
        "Depth",
        "WinWidth",
        "CavWidth",
    }
    marked = set().union(*support.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked == expected
    assert drawing.DIMENSION_CALLOUTS == {
        "WinWidth": "SQ POCKET",
        "CavWidth": "SQ CAVITY THRU",
    }
    # Cast envelopes at one place; the machined 6.35 web is a held thickness
    # at two (routine ±0.51), never "6.4".
    assert drawing.DIMENSION_PRECISION == {
        **dict.fromkeys(expected, 1),
        "WebThickness": 2,
    }


def test_manufacturing_notes_define_only_part_specific_processes() -> None:
    lines = support.DRAWING_NOTES.splitlines()
    notes = " ".join(lines)
    assert len(lines) == 3
    assert "SYMMETRIC ABOUT CENTRE PLANE" in notes
    assert "88.9 FROM MOUNTING FACE" in notes
    assert "CAVITY R12.7, 4X" in notes
    assert "BOTH OUTER POCKET RIMS" in notes
    assert "BOTH TOP OUTER EDGES" not in notes
    # Material may be steel or iron and the seat carries its own symbol, so
    # the notes neither assert a casting nor restate the mounting face; the
    # web instruction is flagged from the side view, not buried here.
    assert "CASTING" not in notes
    assert "AS-CAST" not in notes
    assert "MACHINE MOUNTING FACE" not in notes
    assert "6.35 WEB" not in notes


def test_web_instruction_is_a_view_callout() -> None:
    assert support.WEB_CALLOUT == (
        "MACHINE BOTH POCKETS;\nWALLS NORMAL TO MOUNTING FACE"
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'property_name="Web Callout"' in source
    assert "LEAVE" not in support.WEB_CALLOUT
    assert "6.35" not in support.WEB_CALLOUT


def test_thread_class_lives_in_the_title_block_not_on_the_feature() -> None:
    assert _config.parts(support.PART_NAME)["finish"] == (
        "GREEN ENAMEL; MASK MOUNTING FACE + THREADS; LIGHT OIL BARE MACHINED SURFACES"
    )
    # 2B is the receiver fit the frame assembly asserts against the 2A lag
    # screw; the sheet prints it once, in the title block's THREADS row, so
    # the Hole Wizard feature carries no class (a native callout would repeat it).
    assert support.HOLE_THREAD_CLASS == "2B"
    source = Path(support.__file__).read_text(encoding="utf-8")
    assert 'definition.ThreadClass = ""' in source
    assert "TITLE_BLOCK_THREAD_CLASS" not in source


def test_mounting_face_carries_the_seat_finish_symbol_not_a_note() -> None:
    # The foot seats on harmonic-base: the one face that MUST be cut on a part
    # the title block otherwise leaves CAST/MACHINED. It is the -Y face at
    # y = -HALF_Y (PlanarFace offsets run along the outward normal, so +HALF_Y),
    # and the drawing places the symbol, not a text callout.
    (control,) = drawing_spec.SURFACE_FINISHES
    assert control.key == "mounting_face"
    assert control.roughness_um == 3.2
    assert control.face.normal == (0, -1, 0)
    assert control.face.offset_mm == support.HALF_Y == drawing_spec.HALF_Y
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'surface_finish_by_key(SURFACE_FINISHES, "mounting_face")' in source
    assert source.count("add_surface_finish(") == 1
    assert "MOUNTING_FACE_CALLOUT" not in source
    assert "add_attached_note" not in source


def test_native_hole_table_covers_every_foot_hole() -> None:
    expected_holes = {
        (60.32, 17.46),
        (-60.32, 17.46),
        (60.32, -17.46),
        (-60.32, -17.46),
    }
    assert set(support.HOLES) == expected_holes
    assert set(drawing.EXPECTED_HOLE_TABLE_LOCATIONS_MM) == {
        (147.95, 47.94),
        (27.31, 47.94),
        (147.95, 13.02),
        (27.31, 13.02),
    }
    points = {drawing._bottom_sheet_xy(hole) for hole in expected_holes}
    assert len(points) == 4
    half_w = support.BOSS_DEPTH / 2.0 * drawing.VIEW_SCALE / 1000.0
    half_h = support.WIDE * drawing.VIEW_SCALE / 1000.0
    for x, y in points:
        assert abs(x - drawing.BOTTOM_CENTER[0]) <= half_w
        assert abs(y - drawing.BOTTOM_CENTER[1]) <= half_h


def test_projected_views_remain_aligned() -> None:
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    assert drawing.BOTTOM_CENTER[0] == drawing.FRONT_CENTER[0]


def test_support_has_no_unapproved_gdt_contract() -> None:
    assert not hasattr(placement, "GEOMETRIC_TOLERANCES_MM")


def test_stock_hold_down_matches_receiver_and_engages_only_foot_material() -> None:
    assert screw.SPEC.skus == ("91783A722",)
    assert support.HOLE_SSIZE == screw.THREAD_SIZE == "1/2-13"
    assert (screw.THREAD_CLASS, support.HOLE_THREAD_CLASS) == ("2A", "2B")
    assert support.HOLE_TAP_DRILL_DIA < screw.SHANK_DIA < frame.LAG_CLEARANCE_DIA
    assert screw.HEAD_DIA < frame.LAG_COUNTERBORE_DIA
    assert frame.LAG_HEAD_RECESS == pytest.approx(0.5)
    assert frame.LAG_SUPPORT_ENGAGEMENT == pytest.approx(6.35)
    assert frame.LAG_SCREW_TIP_Y - screw.THREAD_LEN < frame.BASE_TOP_Y
    assert frame.LAG_TIP_REACH_ABOVE_BASE > frame.LAG_SUPPORT_ENGAGEMENT


def test_bottom_view_picks_actual_tap_drill_rim_at_each_station() -> None:
    for x_mm, z_mm in support.HOLES:
        sheet_x, sheet_y = drawing._bottom_sheet_xy((x_mm, z_mm))
        picked_x = (sheet_x - drawing.BOTTOM_CENTER[0]) * 1000 / drawing.VIEW_SCALE
        picked_z = (sheet_y - drawing.BOTTOM_CENTER[1]) * 1000 / drawing.VIEW_SCALE
        assert math.hypot(picked_x - x_mm, picked_z - z_mm) == pytest.approx(
            support.HOLE_TAP_DRILL_DIA / 2.0
        )


def test_support_keeps_original_world_placement_and_hold_down_pattern() -> None:
    assert placement.SUPPORT_WORLD_Z == 0.0
    assert {z for _, z in placement.SUPPORT_HOLD_DOWN_XZ} == {
        -60.32,
        60.32,
    }


@pytest.mark.parametrize("scale", [0.5, 1.0])
def test_section_cut_uses_parent_sketch_coordinates(monkeypatch, scale) -> None:
    """A centre cut must stay centred on a translated, scaled parent view.

    Native CreateLine interprets sheet coordinates a second time: the old
    helper cut x=42.5 mm off centre at 1:2 and left an unsectioned taper.
    """
    origin = drawing.FRONT_CENTER
    transform = object()
    points = []

    def make_point(values):
        points.append(tuple(values))

        def multiply(actual_transform):
            assert actual_transform is transform
            return SimpleNamespace(
                ArrayData=(
                    (values[0] - origin[0]) / scale,
                    (values[1] - origin[1]) / scale,
                    0.0,
                )
            )

        return SimpleNamespace(MultiplyTransform=multiply)

    math_utility = SimpleNamespace(CreatePoint=make_point)
    sketch = SimpleNamespace(ModelToSketchTransform=transform)
    parent = SimpleNamespace(GetSketch=lambda: sketch)
    section_definition = Mock()
    section_definition.SetLabel2.return_value = 0
    section = Mock()
    section.GetSection.return_value = section_definition
    section.SetViewPosition.return_value = True
    model = Mock()
    model.ActivateView.return_value = True
    model.CreateSectionViewAt5.return_value = section
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(GetMathUtility=lambda: math_utility),
    )
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(_drawing_common, "view_name", lambda *_: "Front")
    monkeypatch.setattr(_drawing_common, "double_array", tuple)
    monkeypatch.setattr(
        _drawing_common._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj
    )
    start = (origin[0], origin[1] - 0.050)
    end = (origin[0], origin[1] + 0.050)
    result = _drawing_common.create_section_view(
        adapter,
        parent,
        line_start=start,
        line_end=end,
        view_xy=drawing.RIGHT_CENTER,
        section_label="A",
        scale=(1, 2),
        label="centre cut regression",
    )
    assert result is section
    assert points == [(*start, 0.0), (*end, 0.0)]
    assert model.SketchManager.CreateLine.call_args.args == pytest.approx(
        (0.0, -0.050 / scale, 0.0, 0.0, 0.050 / scale, 0.0)
    )
    section_definition.SetAutoHatch.assert_called_once_with(True)
    section_definition.SetLabel2.assert_called_once_with("A")
