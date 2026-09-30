"""Offline contracts for MHA-153, the crank handle butt cup, and its drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_crank_handle_butt_cup as part
import crank_handle_butt_cup_spec as spec
import crank_handle_pivot_screw_spec as screw
import draw_crank_handle_butt_cup as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-handle-butt-cup.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-handle-butt-cup.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-handle-butt-cup_drawing.png")
    assert (
        DRAWINGS_BY_NAME["crank_handle_butt_cup"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_crank_handle_butt_cup.py" in PRECISION_MIGRATED_DRAWINGS


def test_part_and_drawing_share_the_marked_dimension_contract() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SECTION_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.REFERENCE_DIMENSIONS == {"PocketDia"}
    assert drawing.DIMENSION_CALLOUTS == {"FloorHoleDia": "DRILL THRU"}
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    # Two bands: the body diameter that holds the pocket wall, and the pocket
    # depth that keeps the MHA-139 head below the face (Codex P2 on #1139).
    assert model_toleranced_dimensions(part) == {
        ("CupProfile", "BodyDia"): "BODY_DIA_TOL",
        ("CupProfile", "PocketDepth"): "POCKET_DEPTH_TOL",
    }
    assert {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 2
    } == {"BodyDia", "PocketDepth"}
    assert "set_dimension_bilateral_tolerance" not in source


def test_the_floor_holds_1_5_and_the_wall_its_named_exception() -> None:
    # User rulings 2026-09-30 (ch30 eight-views-4, concept v4): a plain cup
    # sized to the photographed Ø6 head.  The pocket wall is the named 0.8
    # exception; the floor keeps the 1.5 floor.
    assert not hasattr(spec, "FLANGE_DIA") and not hasattr(spec, "FLANGE_THICKNESS")
    # The floor is what the overall (.X) leaves after the banded pocket depth,
    # both from the face (re-review: one faced end).
    assert spec.FLOOR_THICKNESS_MIN == pytest.approx(1.7)
    assert spec.POCKET_WALL_FLOOR_MM == 0.8
    assert spec.POCKET_WALL_MIN == pytest.approx(0.8)
    assert screw.CUP_POCKET_WALL_MIN == pytest.approx(0.8)
    assert screw.POCKET_MAX <= spec.POCKET_DIA_MAX
    policy = (Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md")
    assert "| MHA-153 crank handle butt cup, pocket bored to suit" in policy.read_text(
        encoding="utf-8"
    )
    # 3/8-in stock clears the Ø8.20 body at its upper limit.
    assert "3/8 in" in _config.parts("crank-handle-butt-cup")["material"]
    assert spec.BODY_DIA + spec.BODY_DIA_TOL < 0.375 * 25.4
    assert screw.HEAD_BEARING_RADIAL_MIN > 0.0
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX


def test_head_sits_recessed_and_end_play_is_fitted() -> None:
    assert screw.HEAD_RECESS_NOMINAL == pytest.approx(1.0)
    # Codex P2 on #1139 (user ruling 2026-09-30): pocket 5.5 +/-0.10 over a
    # 4.0 +/-0.10 head keeps the head 0.3 below the face with the handle
    # pushed to the arm at the widest 1.00 end play; at 5.0 .X over 4.0 .X
    # it stood 1.6 proud.
    assert (spec.POCKET_DEPTH, spec.POCKET_DEPTH_TOL) == (5.5, 0.10)
    assert (screw.HEAD_LENGTH, screw.HEAD_LENGTH_TOL) == (4.0, 0.10)
    assert screw.HEAD_RECESS_WORST == pytest.approx(0.3)
    assert screw.END_PLAY_NOMINAL == pytest.approx(0.5)
    assert screw.SHOULDER_LENGTH == pytest.approx(screw.HANDLE_STACK_NOMINAL + 0.5)


def test_pocket_and_floor_hole_read_on_a_section() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "create_section_view(" in source
    assert "set_hidden_lines_visible" not in source
    assert "create_section_axis_centerline(" in source


def test_notes_name_the_mates_and_the_band_reason() -> None:
    assert spec.HANDLE_NUMBER == _config.parts("crank-handle")["number"]
    assert spec.SCREW_NUMBER == _config.parts("crank-handle-pivot-screw")["number"]
    notes = spec.DRAWING_NOTES
    assert f"{spec.HANDLE_NUMBER} {spec.HANDLE_NAME}" in notes
    assert f"{spec.SCREW_NUMBER} {spec.SCREW_NAME}" in notes
    assert "TO SUIT" in notes and "MIN POCKET WALL 0.8; MIN FLOOR 1.5." in notes
    assert "6.5 MAX" in notes
    assert "FACE FLUSH; TURN ITS END" in notes
    assert all(len(line) <= 90 for line in notes.splitlines())


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("crank-handle-butt-cup")
    assert row["number"] == "MHA-153"
    assert row["title"] == "Crank Handle Butt Cup"
    assert len(str(row["material"])) <= 36
    assert int(row["quantity"]) == 1


def test_sheet_layout_keeps_annotations_inside_the_field() -> None:
    for x, y in (
        *drawing.SECTION_KEEP.values(),
        drawing.MANUFACTURING_NOTES_POS,
        drawing.ISO_NOTE_POS,
        drawing.CAPTION_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070)
    assert drawing.END_CENTER[0] + drawing.BODY_R < drawing.SECTION_KEEP["FloorHoleDia"][0] - 0.005
    assert drawing.SECTION_KEEP["PocketDia"][0] + 0.020 < drawing.ISO_NOTE_POS[0]


def test_installed_configuration_turns_the_end_round_across_the_cup() -> None:
    # Codex P2 on #1139: the drive train shows the cup as assembly leaves it,
    # the handle's end round turned across its face; the default stays the
    # as-turned cup the drawing prints (the MHA-135/MHA-139 precedent).
    import build_drive_train_assembly as drive_train
    import crank_handle_spec as handle

    assert spec.INSTALLED_CONFIG == "INSTALLED"
    assert part.END_ROUND_CX_LOCAL == pytest.approx(
        handle.END_ROUND_CENTER[0] - handle.HANDLE_LENGTH
    )
    # The crown is the steel outside the handle's own end round: under a cubic
    # millimetre, and never touching the pocket rim.
    assert 0.5 < part.V_CROWN < 1.5
    assert handle.END_ROUND_CENTER[1] > spec.POCKET_DIA / 2.0
    assert part.V_INSTALLED == pytest.approx(part.V_CUP - part.V_CROWN)
    source = Path(part.__file__).read_text(encoding="utf-8")
    split = source.index("create_configuration {INSTALLED_CONFIG}")
    for edit in (
        "set_dimension_symmetric_tolerance(adapter,",
        "apply_material(adapter,",
        "apply_color(adapter,",
        "mark_dimensions_for_drawing(adapter,",
        "apply_drawing_precision(adapter,",
    ):
        assert source.index(edit) < split, edit
    assert "SetSuppression2(0, 3, bstr_array([default_config]))" in source
    assert "SetSuppression2(1, 3, bstr_array([INSTALLED_CONFIG]))" in source
    assert "apply_grouped_bom_properties(" in source
    assert "require_material_in_every_configuration(" in source
    assert "assert_saved_configurations_regenerate(adapter, PART_NAME)" in source
    assert drive_train.HANDLE_CUP_INSTALLED_CONFIG == spec.INSTALLED_CONFIG
    dt_source = Path(drive_train.__file__).read_text(encoding="utf-8")
    assert "configuration=HANDLE_CUP_INSTALLED_CONFIG," in dt_source
    assert _config.parts("crank-handle-butt-cup")["description"] == "CRANK HANDLE BUTT CUP"
