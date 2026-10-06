"""Offline contracts for the channel-lever drawing."""

from __future__ import annotations

from pathlib import Path

import ch_channel_lever_spec
import draw_ch_channel_lever as drawing
import build_ch_channel_lever as lever
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-channel-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-channel-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-channel-lever_drawing.png")
    assert DRAWINGS_BY_NAME["ch_channel_lever"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is ch_channel_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*ch_channel_lever_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert "TipCentreX" in marked


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.LEVER_SPRING_X, drawing.BAR_PIN_X) == (
        ch_channel_lever_spec.LEVER_SPRING_X,
        ch_channel_lever_spec.BAR_PIN_X,
    )
    assert lever.BAR_PIN_HOLE_SPEC is ch_channel_lever_spec.BAR_PIN_HOLE_SPEC
    assert lever.SPRING_EYE_HOLE_SPEC is ch_channel_lever_spec.SPRING_EYE_HOLE_SPEC
    assert drawing._BAR_PIN_DIA == blind_cut_dia_mm(
        ch_channel_lever_spec.BAR_PIN_HOLE_SPEC
    )
    assert drawing._SPRING_HOLE_DIA == blind_cut_dia_mm(
        ch_channel_lever_spec.SPRING_EYE_HOLE_SPEC
    )


def test_sheet_runs_at_1_to_1_with_1_to_4_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISOMETRIC_SCALE == (1, 4)


def test_manufacturing_note_lane_clears_border_title_block_and_dimensions() -> None:
    left, bottom, right, top = drawing.MANUFACTURING_NOTE_FIELD
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    inner_border = 0.0127
    assert left >= inner_border + 0.004
    assert bottom >= inner_border + 0.004
    assert right + 0.002 <= template.title_block_left_m - 0.004
    assert top + 0.010 <= 0.118


def test_part_registry_keeps_critical_drawing_properties() -> None:
    import _config

    spec = _config.parts("ch-channel-lever")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["material"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == (
        "RAL 6005 alkyd enamel, SSPC-SP3, 40-60 um DFT; mask all bores"
    )
    assert int(spec["quantity"]) == 20


