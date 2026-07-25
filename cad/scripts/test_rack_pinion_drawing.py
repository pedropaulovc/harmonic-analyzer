"""Offline contracts for the rack-pinion drawing (batch gear pattern)."""

from __future__ import annotations

from pathlib import Path

import build_rack_pinion as part
import draw_rack_pinion as drawing
import rack_pinion_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rack-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rack-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rack-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["rack_pinion"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia"}


def test_gear_data_block_specifies_the_tooth_system() -> None:
    data = spec.GEAR_DATA
    for field in (
        "GEAR DATA", "NUMBER OF TEETH", "DIAMETRAL PITCH", "MODULE (mm",
        "PRESSURE ANGLE", "PITCH DIAMETER (mm", "OUTSIDE DIAMETER (mm)",
        "WHOLE DEPTH (mm)", "FACE WIDTH (mm)", "TOOTH FORM",
    ):
        assert field in data, field
    assert "120" in data
    assert "X.XX" not in data
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_manufacturing_notes_present() -> None:
    assert "CUT TEETH PER GEAR DATA" in spec.DRAWING_NOTES
    assert "DEBUR" not in spec.DRAWING_NOTES
    assert "X.XX" not in spec.DRAWING_NOTES


def test_native_gdt_controls_bore_datum_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert source.count("add_surface_finish(") == 1
    assert "visible_circle_edge" not in source
    assert "entity=bore_edge" not in source
    assert source.count("edge_xy=bore_top") == 2


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("rack-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "gear teeth cut; polished brass"
    assert int(config["quantity"]) == 1
