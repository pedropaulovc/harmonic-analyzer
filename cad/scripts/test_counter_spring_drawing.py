"""Offline contracts for the counter-spring spec sheet."""

from __future__ import annotations

from pathlib import Path

import counter_spring_notes
import counter_spring_spec
import draw_counter_spring as drawing
import build_counter_spring as spring
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/counter-spring.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/counter-spring.pdf")
    assert drawing.PNG.as_posix().endswith("/png/counter-spring_drawing.png")
    assert DRAWINGS_BY_NAME["counter_spring"].script == Path(drawing.__file__).resolve()


def test_spec_sheet_has_no_graphical_marked_dimensions() -> None:
    # A coil spring is defined by its data table, so the marked set is empty and
    # the kept set is empty too.
    assert spring.DRAWING_DIMENSIONS is counter_spring_notes.DRAWING_DIMENSIONS
    assert counter_spring_notes.DRAWING_DIMENSIONS == {}
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == set()


def test_spring_data_matches_the_build() -> None:
    assert counter_spring_spec.COIL_OD == spring.COIL_OD
    assert counter_spring_spec.WIRE_DIA == spring.WIRE_DIA
    assert counter_spring_spec.COIL_BODY_LENGTH == spring.COIL_BODY_LENGTH
    assert counter_spring_spec.COIL_COUNT == spring.COIL_COUNT
    assert counter_spring_spec.COIL_ID == counter_spring_spec.COIL_OD - 2 * counter_spring_spec.WIRE_DIA
    assert counter_spring_spec.BOTTOM_HOOK_LEAD == spring.BOTTOM_LEAD
    assert counter_spring_spec.TOP_HOOK_LEAD == spring.TOP_LEAD
    assert counter_spring_spec.FREE_EYE_C2C == (
        spring.COIL_BODY_LENGTH + spring.BOTTOM_LEAD + spring.TOP_LEAD
    )


def test_data_block_is_compact_and_carries_the_spring_parameters() -> None:
    notes = counter_spring_notes.DRAWING_NOTES
    lines = notes.split("\n")
    assert lines[0] == "EXTENSION SPRING DATA"
    assert len(lines) == 6
    for token in ("WIRE Ø", "OD", "FREE LENGTH", "ACTIVE COILS", "RIGHT HAND", "ENDS"):
        assert token in notes
    assert f"{counter_spring_spec.WIRE_DIA:.2f}" in notes
    assert f"{counter_spring_spec.COIL_OD:.2f}" in notes
    assert f"{counter_spring_spec.FREE_EYE_C2C:.2f} EYE C-C" in notes
    assert str(counter_spring_spec.COIL_COUNT) in notes
    assert "270.0 DEG LOOPS" in notes
    assert "LEADS" in notes
    assert "COPLANAR" in notes
    assert max(len(line) for line in lines) <= 52
    assert "MATERIAL" not in notes
    assert "MUSIC WIRE" not in notes
    for removed in ("COIL ID", "MEAN DIA", "FREE PITCH", "RATE"):
        assert removed not in notes
    for banned in ("NOTE:", "GOOSENECK", "TOWERS", "DATUM", "BASIC", "WITHIN"):
        assert banned not in notes, banned


def test_spec_sheet_carries_no_gdt_or_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(counter_spring_spec, "GEOMETRIC_TOLERANCES_MM")
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_sheet_runs_at_1_to_2_with_1_to_3_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 3)" in source  # the isometric override
    assert counter_spring_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:3"
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("counter-spring")
    assert spec["material_specification"] == "ASTM A228 music-wire spring steel"
    assert spec["finish"] == "black japanned"
    assert int(spec["quantity"]) == 1
