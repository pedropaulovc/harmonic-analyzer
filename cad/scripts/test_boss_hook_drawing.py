"""Offline contracts for the boss-hook drawing."""

from __future__ import annotations

from pathlib import Path

import boss_hook_spec
import build_boss_hook as part
import draw_boss_hook as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/boss-hook.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/boss-hook.pdf")
    assert drawing.PNG.as_posix().endswith("/png/boss-hook_drawing.png")
    assert DRAWINGS_BY_NAME["boss_hook"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is boss_hook_spec.DRAWING_DIMENSIONS
    marked = set().union(*boss_hook_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked


def test_notes_describe_the_wire_hook() -> None:
    notes = boss_hook_spec.DRAWING_NOTES
    assert "WIRE" in notes
    assert "R3 +/-0.20" in notes
    assert "END-FACE AXIAL" in notes
    assert "WIRE CENTERLINE, FROM END FACE" in notes
    assert "(MAX DIA - MIN DIA)/3.00 <= 0.05" in notes
    assert "FLAT SURFACE PLATE; 0.25 MAX GAP" in notes
    assert "5X MAGNIFICATION" in notes
    assert "AISI" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(4, 1)" in source
    assert "scale=(2, 1)" in source
    assert boss_hook_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("boss-hook")
    assert config["material"] == "ASTM A108 Grade 1018 cold-finished steel round"
    assert config["material"] == config["material_specification"]
    assert "steel" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
