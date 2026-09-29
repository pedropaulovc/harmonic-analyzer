"""Offline contracts for MHA-153, the crank handle butt cup, and its drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_crank_handle_butt_cup as part
import crank_handle_butt_cup_spec as spec
import crank_handle_pivot_screw_spec as screw
import draw_crank_handle_butt_cup as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
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
    # The one band: the body diameter that holds the pocket wall.
    assert source.count("set_dimension_symmetric_tolerance(adapter") == 1
    assert '"CupProfile", "BodyDia", BODY_DIA_TOL' in source
    assert "set_dimension_bilateral_tolerance" not in source


def test_every_section_holds_1_5_at_its_worst_case() -> None:
    # User ruling 2026-09-29 (MHA-153 review): the butt grew instead of
    # accepting 0.54 / 0.85 / 0.75 sections.
    assert spec.FLANGE_THICKNESS - 0.8 == pytest.approx(1.5)
    assert spec.FLOOR_THICKNESS - 0.8 == pytest.approx(1.5)
    assert screw.CUP_POCKET_WALL_MIN == pytest.approx(1.5)
    assert screw.HEAD_BEARING_RADIAL_MIN > 0.0
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX


def test_head_sits_recessed_and_end_play_is_fitted() -> None:
    assert screw.HEAD_RECESS_NOMINAL == pytest.approx(0.5)
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
    assert "TO SUIT" in notes and "1.5 POCKET WALL" in notes
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
    assert drawing.END_CENTER[0] + drawing.FLANGE_R < drawing.SECTION_KEEP["FloorHoleDia"][0] - 0.005
    assert drawing.SECTION_KEEP["PocketDia"][0] + 0.020 < drawing.ISO_NOTE_POS[0]
