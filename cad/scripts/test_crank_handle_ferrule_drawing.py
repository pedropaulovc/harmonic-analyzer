"""Offline contracts for MHA-152, the crank handle ferrule, and its drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_crank_handle_ferrule as part
import crank_handle_ferrule_spec as spec
import draw_crank_handle_ferrule as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-handle-ferrule.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-handle-ferrule.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-handle-ferrule_drawing.png")
    assert (
        DRAWINGS_BY_NAME["crank_handle_ferrule"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_crank_handle_ferrule.py" in PRECISION_MIGRATED_DRAWINGS


def test_part_and_drawing_share_the_marked_dimension_contract() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SECTION_KEEP) == marked == {"OuterDia", "BoreDia", "Length"}
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_only_the_bore_is_banded() -> None:
    # User ruling 2026-09-29 (MHA-152 review): the tenon is turned to suit this
    # bore and the end play is fitted on the MHA-139 shoulder.  The bore keeps
    # +/-0.10 (Codex P1/P2 on #1139, user ruling 2026-09-30): at .X the fitted
    # tenon could outgrow the MHA-022 seat shoulder or thin the oak over the
    # pivot bore to 1.45.
    assert spec.DRAWING_PRECISION_BY_NAME == {"OuterDia": 1, "BoreDia": 2, "Length": 1}
    assert (spec.BORE_DIA, spec.BORE_DIA_TOL) == (7.5, 0.10)
    assert model_toleranced_dimensions(part) == {
        ("FerruleProfile", "BoreDia"): "BORE_DIA_TOL"
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "set_dimension_bilateral_tolerance" not in source
    assert spec.WALL_WORST == pytest.approx(2.05)


def test_fitted_tenon_keeps_its_seat_and_wall() -> None:
    import crank_handle_spec as handle

    # The oak leaves the ferrule face flush with its OD (user ruling
    # 2026-09-30, concept v3), so the seat is the whole face over the tenon;
    # the Ø7.5 bore keeps 1.5 of oak over the Ø4.1 pivot bore.
    assert handle.SHOULDER_R == pytest.approx(spec.OUTER_DIA / 2.0)
    assert handle.FERRULE_SEAT_RADIAL_MIN == pytest.approx(2.225)
    assert handle.TENON_WALL_MIN == pytest.approx(1.55)


def test_bore_reads_on_a_section_not_hidden_lines() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "create_section_view(" in source
    assert "set_hidden_lines_visible" not in source
    assert "create_section_axis_centerline(" in source


def test_ring_matches_the_photographed_brass_collar() -> None:
    assert spec.OUTER_DIA == pytest.approx(12.5)  # eight-views-4, user 2026-09-30
    assert spec.LENGTH == pytest.approx(7.0)
    assert part.V_FERRULE == pytest.approx(math.pi * (6.25**2 - 3.75**2) * 7.0)
    assert part.MATERIAL == "Brass"


def test_note_names_the_mating_tenon() -> None:
    row = _config.parts("crank-handle")
    assert spec.HANDLE_NUMBER == row["number"]
    assert f"{spec.HANDLE_NUMBER} {spec.HANDLE_NAME}" in spec.DRAWING_NOTES
    assert len(spec.DRAWING_NOTES.splitlines()) == 2
    assert "TURNED TO SUIT THIS BORE" in spec.DRAWING_NOTES


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("crank-handle-ferrule")
    assert row["number"] == "MHA-152"
    assert row["title"] == "Crank Handle Ferrule"
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
    assert drawing.END_CENTER[0] + drawing.OUTER_R < drawing.SECTION_KEEP["OuterDia"][0] - 0.010
    assert drawing.SECTION_KEEP["BoreDia"][0] + 0.020 < drawing.ISO_NOTE_POS[0]
