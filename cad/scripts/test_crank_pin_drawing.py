"""Offline contracts for the crank-pin drawing."""

from __future__ import annotations

from pathlib import Path

import build_crank_pin as part
import crank_pin_spec
import draw_crank_pin as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-pin_drawing.png")
    assert DRAWINGS_BY_NAME["crank_pin"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is crank_pin_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_pin_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked
    assert (drawing.PIN_LENGTH, drawing.BIG_END_DIA, drawing.SMALL_END_DIA) == (
        crank_pin_spec.PIN_LENGTH,
        crank_pin_spec.BIG_END_DIA,
        crank_pin_spec.SMALL_END_DIA,
    )


def test_end_diameters_are_drawing_native_true_diameter_callouts() -> None:
    """The model's end dims are half-profile radii, so the print measures the
    projected end-face circles instead — one Ø dimension per pin end."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("_add_end_diameter(") >= 3  # definition + both ends
    assert 'below="BIG END"' in source
    assert 'below="SMALL END"' in source
    taper_on_dia = crank_pin_spec.BIG_END_DIA - crank_pin_spec.SMALL_END_DIA
    assert round(taper_on_dia, 2) == 1.00
    assert "TAPER 1.0 ON DIA OVER 45.0" in crank_pin_spec.DRAWING_NOTES


def test_linked_notes_define_remaining_pin_operations() -> None:
    notes = crank_pin_spec.DRAWING_NOTES
    assert "DEBURR" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_finish_symbol_controls_taper_seat() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_surface_finish(") == 1
    assert 'roughness_ra="1.6"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.END_VIEW_SCALE == 4.0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(2, 1)") == 2
    assert source.count("scale=(4, 1)") == 1
    assert crank_pin_spec.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("crank-pin")
    assert config["number"] == "MHA-024"
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
