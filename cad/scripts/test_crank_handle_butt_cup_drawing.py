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
    assert "TO SUIT" in notes
    assert "MIN POCKET WALL 0.8; MIN FLOOR 1.5; CORNERS EXCEPTED." in notes
    # Machinist review of crank-v4-16: the depth band states its reason.
    assert "DEPTH BAND KEEPS THE LONGEST MHA-139 HEAD BELOW THE FACE." in notes
    # crank-v4-17: a 78-character line pushed the block 4.8 mm into the title
    # block (2.55 mm a character from x=21.9, title block at x=216).
    assert max(len(line.replace("<MOD-DIAM>", "@")) for line in notes.splitlines()) <= 74
    assert "turned clear of it" in _config.parts("crank-handle-butt-cup")["process"]
    assert "6.5 MAX" in notes
    assert "FACE FLUSH, CENTRED ON THE" in notes
    # The oak's end round is turned clear of the cup (local review of
    # fbf82ad96): its face stays flat.
    assert "WAXED MHA-139 SCREW.  THE FACE STAYS FLAT; THE OAK ROUNDS OVER IT." in notes
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


def test_cup_is_one_configuration_the_oak_rounds_clear_of() -> None:
    # Local review of fbf82ad96 (recommended option taken when the question
    # timed out): with the cup's possible offset in the stack the end round
    # could skim only ~0.001 off the steel, so it is turned on the oak only
    # and the cup keeps its flat face.  No INSTALLED configuration remains.
    import build_drive_train_assembly as drive_train
    import crank_handle_spec as handle

    assert not hasattr(spec, "INSTALLED_CONFIG")
    assert not hasattr(drive_train, "HANDLE_CUP_INSTALLED_CONFIG")
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "create_configuration" not in source
    # The crest, turned its whole allowance small and off the mandrel by the
    # bore's eccentricity, stays outside the largest counterbore.
    assert handle.END_ROUND_CY - 0.25 - 0.10 >= handle.COUNTERBORE_DIA_MAX / 2.0 - 1e-9
    assert _config.parts("crank-handle-butt-cup")["description"] == "CRANK HANDLE BUTT CUP"
