"""Offline contracts for the cone-gear drawing (batch gear-drawing pattern)."""

from __future__ import annotations

from pathlib import Path

import build_cone_gear as part
import cone_gear_spec as spec
import draw_cone_gear as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-gear_drawing.png")
    assert DRAWINGS_BY_NAME["cone_gear"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked == {"BoreCutDia"}


def test_gear_data_block_specifies_the_tooth_system() -> None:
    data = spec.GEAR_DATA
    for field in (
        "GEAR DATA",
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "MODULE (mm",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (mm",
        "OUTSIDE DIAMETER (mm)",
        "WHOLE DEPTH (mm)",
        "TOOTH FORM",
        "INVOLUTE, FULL DEPTH",
        "FAMILY T006",
        "FAMILY T012",
        "FAMILY T018",
        "FAMILY T024-T120",
    ):
        assert field in data, field
    assert "120" in data
    assert "X.XX" not in data
    for teeth, bore_mm in spec.FAMILY_BORES_MM.items():
        assert bore_mm == part.bore_dia_in(teeth) * spec.MM_PER_IN
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_manufacturing_notes_cover_teeth_and_family() -> None:
    notes = spec.DRAWING_NOTES
    assert "CUT TEETH PER GEAR DATA" in notes
    assert "CONE SET" in notes
    assert "1 OF EACH CONFIGURATION" in notes
    assert "20 GEARS TOTAL" in notes
    assert "NO KEYWAY" in notes
    assert "SOLDER TO MATCHING SHAFT SEATS" in notes
    assert "X.XX" not in notes
    assert "SET TABLE" not in notes
    assert "CONE-SHAFT DRAWING" not in notes
    assert "DEBUR" not in notes


def test_native_gdt_controls_bore_datum_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert source.count("add_surface_finish(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-gear")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "gear teeth cut; polished brass"
    assert int(config["quantity"]) == 1
