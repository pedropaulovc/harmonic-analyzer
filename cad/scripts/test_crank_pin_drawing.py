"""Offline contracts for the crank-pin drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a hand-fitted taper
pin carries no datums, frames or roughness symbols (its taper is a drive fit,
not a running surface); the two end diameters and the length are the spec.
"""

from __future__ import annotations

from pathlib import Path

import build_crank_pin as part
import crank_pin_spec
import draw_crank_pin as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-pin_drawing.png")
    assert DRAWINGS_BY_NAME["crank_pin"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is crank_pin_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_pin_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked
    assert drawing.PIN_LENGTH == crank_pin_spec.PIN_LENGTH


def test_end_diameters_are_drawing_native_true_diameter_callouts() -> None:
    """The model's end dims are half-profile radii, so the print measures the
    projected end-face circles instead -- one diameter dimension per pin end."""
    source = _source()
    assert source.count("_add_end_diameter(") >= 3  # definition + both ends
    assert 'below="BIG END"' in source
    assert 'below="SMALL END"' in source
    # Custom 1:48 taper over the 45 mm length -> 0.9375 on diameter, matching the
    # crank-arm cross-hole taper-reamed to the same 1:48 to suit this pin.
    taper_on_dia = crank_pin_spec.BIG_END_DIA - crank_pin_spec.SMALL_END_DIA
    assert round(taper_on_dia, 4) == round(crank_pin_spec.PIN_LENGTH / 48.0, 4)
    assert round(taper_on_dia, 4) == 0.9375


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = crank_pin_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The taper ratio is what the compound is set to; the rise on diameter is
    # what the two end dimensions already show.
    assert "1:48" in notes
    assert "HAND-FIT" in notes
    # How the taper is cut is the machinist's call (review 2026-09-02): the
    # ends, the ratio and the hand fit control the result, not the method.
    assert "ONE PASS" not in notes
    for banned in ("0.9375", "DEBURR", "WITHIN", "+/-", "UOS", "DATUM", "MHA-", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    """A drive-fit taper pin: no datums, no frames, no Ra (policy rules 3, 5)."""
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert crank_pin_spec.SURFACE_FINISHES == ()
    assert not hasattr(crank_pin_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(crank_pin_spec, "GEOMETRIC_CONTROLS")
    assert "roughness_ra=" not in source
    # The part build keeps its author_part_pmi call shape on the empty tuple.
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.END_VIEW_SCALE == 4.0
    source = _source()
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
