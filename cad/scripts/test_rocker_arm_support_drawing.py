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


def test_drawing_keeps_only_make_critical_model_dimensions() -> None:
    expected = {
        "FootSpan",
        "TopSpan",
        "WallHeight",
        "Depth",
        "WinWidth",
        "CavWidth",
        "PocketRadius",
        "CavityRadius",
        "RimChamferSize",
    }
    marked = set().union(*support.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked == expected
    assert drawing.DIMENSION_CALLOUTS == {
        "WinWidth": "SQ POCKET",
        "PocketRadius": "8X",
        "CavityRadius": "4X",
        "CavWidth": "SQ CAVITY THRU",
        "RimChamferSize": " X 45 DEG\n2 FACES",
    }
    assert drawing.DIMENSION_PRECISION == {
        **dict.fromkeys(expected - {"PocketRadius", "RimChamferSize"}, 1),
        "PocketRadius": 2,
        "RimChamferSize": 2,
        "WebThickness": 2,
        "FootThickness": 2,
    }


def test_pocket_and_cavity_reliefs_are_distinct() -> None:
    assert support.FILLET_R == 12.7
    assert {tuple(edge) for edge in support.FILLET_EDGES} == {
        (x_sign * support.CAV, y_sign * support.CAV, 0.0)
        for x_sign in (-1, 1)
        for y_sign in (-1, 1)
    }
    assert support.POCKET_FILLET_R == 6.35
    assert len(support.POCKET_FILLET_EDGES) == 8
    assert {abs(edge[0]) for edge in support.POCKET_FILLET_EDGES} == {support.BIG}
    assert {abs(edge[1]) for edge in support.POCKET_FILLET_EDGES} == {support.BIG}
    assert all(abs(edge[2]) > support.WEB for edge in support.POCKET_FILLET_EDGES)


def test_no_process_callout_on_the_sheet() -> None:
    # "Machine both pockets" dictates method (ASME Y14.5 1.4(e)); the section's
    # web dimension defines what the pockets leave, so no callout exists.
    assert not hasattr(support, "WEB_CALLOUT")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_property_linked_callout" not in source
    assert "Web Callout" not in source


def test_support_finish_masks_only_the_machined_mounting_face() -> None:
    assert _config.parts(support.PART_NAME)["finish"] == (
        "GREEN ENAMEL; MASK MOUNTING FACE; LIGHT OIL BARE MACHINED SURFACES"
    )
    assert support.HOLE_SPEC.kind == "drilled_fractional"
    assert support.HOLE_SPEC.size == "5/16"
    assert support.HOLE_DIA == pytest.approx(7.938)
    source = Path(support.__file__).read_text(encoding="utf-8")
    assert "ThreadClass" not in source
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
    assert drawing.HOLE_TABLE_DATUM_XZ_MM == (
        -support.BOSS_DEPTH / 2.0,
        -support.WIDE,
    )
    x_centres = {x for x, _ in expected_holes}
    y_centres = {y for _, y in expected_holes}
    assert round(max(x_centres) - min(x_centres), 2) == 120.64
    assert round(max(y_centres) - min(y_centres), 2) == 34.92
    expected_locations = {
        (
            round(x + support.BOSS_DEPTH / 2.0, 2),
            round(z + support.WIDE, 2),
        )
        for x, z in expected_holes
    }
    assert set(drawing.EXPECTED_HOLE_TABLE_LOCATIONS_MM) == expected_locations
    xs = {x for x, _ in expected_locations}
    ys = {y for _, y in expected_locations}
    assert round(min(xs) + max(xs), 2) == support.BOSS_DEPTH
    assert round(min(ys) + max(ys), 2) == 2.0 * support.WIDE
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


def test_stock_hold_down_clears_support_and_engages_blind_base_tap() -> None:
    import build_harmonic_base as base

    assert screw.SPEC.skus == ("92240A539",)
    assert screw.THREAD_SIZE == base.HOLD_DOWN_THREAD == "1/4-20"
    assert (screw.THREAD_CLASS, base.HOLD_DOWN_THREAD_CLASS) == ("2A", "2B")
    assert screw.THREAD_LEN == screw.SHANK_LEN
    assert screw.SHANK_DIA < support.HOLE_DIA < screw.HEAD_AF
    assert frame.LAG_SUPPORT_CLEARANCE_DIA == support.HOLE_DIA
    assert frame.LAG_SCREW_UNDER_HEAD_Y - screw.BEARING_OFFSET == pytest.approx(
        frame.BASE_TOP_Y + support.FOOT_THICKNESS
    )
    assert frame.LAG_BASE_ENGAGEMENT == pytest.approx(base.HOLD_DOWN_ENGAGEMENT)
    assert base.HOLD_DOWN_ENGAGEMENT == pytest.approx(
        screw.SHANK_LEN - support.FOOT_THICKNESS - screw.BEARING_OFFSET
    )
    assert base.HOLD_DOWN_ENGAGEMENT / screw.SHANK_DIA > 1.45
    assert base.HOLD_DOWN_THREAD_DEPTH == pytest.approx(
        base.HOLD_DOWN_ENGAGEMENT + base.HOLD_DOWN_TIP_CLEARANCE
    )
    assert base.HOLD_DOWN_DRILL_DEPTH == pytest.approx(
        base.HOLD_DOWN_THREAD_DEPTH + 5.0 * screw.THREAD_PITCH
    )
    assert frame.LAG_SCREW_TIP_Y == pytest.approx(
        frame.BASE_TOP_Y - base.HOLD_DOWN_ENGAGEMENT
    )


def test_bottom_view_picks_actual_clearance_rim_at_each_station() -> None:
    for x_mm, z_mm in support.HOLES:
        sheet_x, sheet_y = drawing._bottom_sheet_xy((x_mm, z_mm))
        picked_x = (sheet_x - drawing.BOTTOM_CENTER[0]) * 1000 / drawing.VIEW_SCALE
        picked_z = (sheet_y - drawing.BOTTOM_CENTER[1]) * 1000 / drawing.VIEW_SCALE
        assert math.hypot(picked_x - x_mm, picked_z - z_mm) == pytest.approx(
            support.HOLE_DIA / 2.0
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
