"""Offline contracts for the measuring-stick drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a ruled brass bar
carries no datums, frames or roughness symbols, and its notes are four lines
of engraving fact (the graduation swarm is not dimensioned tick by tick).
"""

from __future__ import annotations

from pathlib import Path

import build_measuring_stick as part
import draw_measuring_stick as drawing
import measuring_stick_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/measuring-stick.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/measuring-stick.pdf")
    assert drawing.PNG.as_posix().endswith("/png/measuring-stick_drawing.png")
    assert (
        DRAWINGS_BY_NAME["measuring_stick"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is measuring_stick_spec.DRAWING_DIMENSIONS
    marked = set().union(*measuring_stick_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = measuring_stick_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The scale is defined by pitch + slot section + numeral size; the ticks
    # themselves are shown, not dimensioned one by one.
    assert "11 FULL TICKS" in notes
    assert "14.20 PITCH" in notes
    assert "HALF TICK" in notes
    assert "SQUARE BOTTOM" in notes
    assert "BLACK-FILL" in notes
    # Numeral facts track the build (pass-3 photo re-derive).
    assert f"NUMERALS {part.NUMERAL_HEIGHT_MM:.2f} HIGH X {part.TICK_DEPTH:.2f} DEEP" in notes
    assert f"TURNED {part.NUMERAL_ROTATION_DEG} DEG" in notes
    assert f"{part.NUMERAL_GAP_MM:.2f} PAST THEIR TICK" in notes
    for banned in ("UOS", "DIMENSIONS IN", "+/-", "NONCUMULATIVE", "ASME Y14.2", "CDA", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(measuring_stick_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hidden_lines_stay_on_in_the_ruled_face_view() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert "scale=(1, 1)" in source
    assert "scale=(1, 2)" in source
    assert measuring_stick_spec.FRONT_VIEW_NOTE == "RULED FACE SCALE 1:1"
    assert '"*Back"' in source
    assert "_rotate_ruled_face(adapter, front)" in source
    assert "_add_scale_labels(adapter)" in source


def test_stock_thickness_is_explicit_on_the_sheet() -> None:
    assert drawing.STOCK_THICKNESS_NOTE == (
        f"STOCK THICKNESS {part.BODY_THICKNESS:.2f}"
    )
    assert part.BODY_THICKNESS == 3.0
    source = _source()
    assert "add_note(adapter, STOCK_THICKNESS_NOTE, *STOCK_THICKNESS_NOTE_XY)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("measuring-stick")
    assert config["material"] == "C26000 brass, half-hard"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
