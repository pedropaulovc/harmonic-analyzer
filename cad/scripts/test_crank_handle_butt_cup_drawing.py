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
    assert set(drawing.SIDE_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    for banded in ("FlangeThickness", "PocketDepth", "BodyDia", "OverallLength", "PocketDia"):
        assert f'"CupProfile", "{banded}"' in source


def test_cup_takes_the_recessed_screw_head() -> None:
    # User ruling 2026-09-29 (ch11 p.14/p.15): the slotted head sits recessed
    # in a bright steel cup with a visible ring of clearance.
    assert screw.HEAD_POCKET_RADIAL_MIN > 0.0
    assert screw.HEAD_BEARING_RADIAL_MIN > 0.0
    assert screw.HEAD_RECESS_NOMINAL == pytest.approx(0.1)
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX
    assert spec.POCKET_WALL >= 0.5
    assert spec.FLOOR_THICKNESS == pytest.approx(1.0)
    assert part.V_CUP > 0.0


def test_end_play_stack_through_ferrule_oak_and_cup() -> None:
    assert screw.END_PLAY_NOMINAL == pytest.approx(0.5)
    assert screw.END_PLAY_MIN == pytest.approx(0.25)
    assert screw.END_PLAY_MAX == pytest.approx(1.0)


def test_note_names_the_mating_counterbore() -> None:
    assert spec.HANDLE_NUMBER == _config.parts("crank-handle")["number"]
    assert spec.HANDLE_NUMBER in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) == 1


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("crank-handle-butt-cup")
    assert row["number"] == "MHA-153"
    assert row["title"] == "Crank Handle Butt Cup"
    assert len(str(row["material"])) <= 36
    assert int(row["quantity"]) == 1


def test_sheet_layout_keeps_annotations_inside_the_field() -> None:
    for x, y in (
        *drawing.SIDE_KEEP.values(),
        drawing.MANUFACTURING_NOTES_POS,
        drawing.ISO_NOTE_POS,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070)
    assert drawing.SIDE_KEEP["PocketDia"][0] + 0.010 < drawing.END_CENTER[0] - drawing.FLANGE_R
