"""Offline contracts for the channel-spring (installed) spec sheet."""

from __future__ import annotations

from pathlib import Path

import channel_spring_installed_notes as csi_notes
import channel_spring_installed_spec as spec
import draw_channel_spring_installed as drawing
import build_channel_spring_installed as spring
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/channel-spring-installed.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/channel-spring-installed.pdf")
    assert drawing.PNG.as_posix().endswith("/png/channel-spring-installed_drawing.png")
    assert DRAWINGS_BY_NAME["channel_spring_installed"].script == Path(drawing.__file__).resolve()


def test_spec_sheet_has_no_graphical_marked_dimensions() -> None:
    assert csi_notes.DRAWING_DIMENSIONS == {}
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == set()


def test_spring_data_matches_the_build() -> None:
    import _config

    assert spec.FREE_BODY_LENGTH == float(
        _config.parts("channel-spring-installed")["free_length_mm"]
    )
    assert spec.FREE_BODY_LENGTH == spring.COIL_BODY_LENGTH
    # The installed body length in the spec matches the build's derived value.
    assert spec.INSTALLED_BODY_LENGTH == spring.INSTALLED_BODY_LENGTH
    assert spec.COIL_ID == spec.COIL_OD - 2 * spec.WIRE_DIA
    assert spec.HOOK_LEAD == spring.TOP_LEAD == spring.BOTTOM_LEAD
    assert spec.FREE_EYE_C2C == 36.0
    assert spec.INSTALLED_EYE_C2C == round(
        spring.INSTALLED_BODY_LENGTH + spring.TOP_LEAD + spring.BOTTOM_LEAD, 2
    )


def test_data_block_is_compact_and_distinguishes_supply_from_view_length() -> None:
    notes = csi_notes.DRAWING_NOTES
    lines = notes.split("\n")
    assert lines[0] == "EXTENSION SPRING DATA"
    assert len(lines) == 8
    for token in ("WIRE Ø", "OD", "FREE LENGTH", "ACTIVE COILS", "RIGHT HAND", "ENDS"):
        assert token in notes
    assert f"{spec.WIRE_DIA:.2f}" in notes
    assert f"{spec.COIL_OD:.2f}" in notes
    assert f"{spec.FREE_EYE_C2C:.2f} EYE C-C" in notes
    assert f"{spec.INSTALLED_EYE_C2C:.2f} EYE C-C (STRETCHED)" in notes
    assert str(spec.COIL_COUNT) in notes
    assert "270.0 DEG LOOPS" in notes
    assert "LEADS" in notes
    assert "EYES COPLANAR" in notes
    assert lines[-1].strip() == "SUPPLY RELAXED"
    assert max(len(line) for line in lines) <= 52
    assert "MATERIAL" not in notes
    assert "MUSIC WIRE" not in notes
    for removed in ("COIL ID", "MEAN DIA", "FREE PITCH", "RATE"):
        assert removed not in notes
    for banned in ("NOTE:", "DATUM", "BASIC", "WITHIN"):
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
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_sheet_runs_at_1_to_1() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert csi_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    cfg = _config.parts("channel-spring-installed")
    # MATERIAL is the music-wire spec (the "Alloy Steel" review finding was
    # against the registry's material name, which the title block no longer
    # shows); FINISH keeps the bright, oiled supply condition.
    assert cfg["material_specification"] == "ASTM A228 music-wire spring steel"
    assert cfg["finish"] == "bright (plain music wire, light oil)"
    assert int(cfg["quantity"]) == 20
