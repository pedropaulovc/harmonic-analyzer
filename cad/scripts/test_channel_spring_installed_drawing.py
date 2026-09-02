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


def test_data_table_distinguishes_free_and_installed_length() -> None:
    notes = csi_notes.DRAWING_NOTES
    assert "FREE BODY LENGTH" in notes
    assert "INSTALLED BODY" in notes
    assert f"{spec.FREE_BODY_LENGTH:.2f}" in notes
    assert f"{spec.INSTALLED_BODY_LENGTH:.2f}" in notes
    assert "RELAXED" in notes
    assert "STRETCHED" in notes
    assert "HOOK LEADS" in notes
    assert "270 DEG LOOP" in notes
    assert "FREE EYE C-C" in notes
    assert "INSTALLED EYE C-C" in notes
    assert "MATERIAL" not in notes
    assert "MUSIC WIRE" not in notes


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
    assert cfg["material_specification"] == "ASTM A228 music-wire spring steel"
    assert cfg["finish"] == "bright (plain music wire, light oil)"
    assert int(cfg["quantity"]) == 20
