"""Offline contracts for the crank-drive-gear drawing (batch gear pattern)."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_crank_drive_gear as part
import crank_drive_gear_spec as spec
import draw_crank_drive_gear as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-drive-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-drive-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-drive-gear_drawing.png")
    assert DRAWINGS_BY_NAME["crank_drive_gear"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia"}


def test_gear_data_block_specifies_the_tooth_system() -> None:
    data = spec.GEAR_DATA
    for field in (
        "GEAR DATA", "NUMBER OF TEETH", "DIAMETRAL PITCH", "MODULE (mm",
        "PRESSURE ANGLE", "PITCH DIAMETER (mm", "OUTSIDE DIAMETER (mm)",
        "WHOLE DEPTH (mm)", "FACE WIDTH (mm)", "TOOTH FORM", "HELIX ANGLE",
        "HELIX TWIST",
    ):
        assert field in data, field
    assert "64" in data
    assert spec.HELIX_ANGLE_DEG == pytest.approx(part.HELIX_DEG, abs=0.01)
    assert spec.TOTAL_TWIST_DEG == pytest.approx(4.16, abs=0.01)
    assert "X.XX" not in data
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_manufacturing_notes_present() -> None:
    notes = spec.DRAWING_NOTES
    assert "CUT TEETH PER GEAR DATA" in notes
    assert "POSITIVE HELIX" in notes
    assert "DEBUR" not in notes
    assert "X.XX" not in notes


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

    config = _config.parts("crank-drive-gear")
    assert config["material_specification"] == "AISI 1018 cold-finished steel"
    assert config["finish"] == "gear teeth cut, oiled"
    assert int(config["quantity"]) == 1
