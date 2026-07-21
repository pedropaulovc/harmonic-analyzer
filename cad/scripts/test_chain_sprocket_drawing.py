"""Offline contracts for the chain-sprocket drawing (sprocket analog)."""

from __future__ import annotations

from pathlib import Path

import build_chain_sprocket as part
import chain_sprocket_spec as spec
import draw_chain_sprocket as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/chain-sprocket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/chain-sprocket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/chain-sprocket_drawing.png")
    assert DRAWINGS_BY_NAME["chain_sprocket"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"BoreDia"}


def test_sprocket_data_block_specifies_the_tooth_system() -> None:
    data = spec.GEAR_DATA
    for field in (
        "SPROCKET DATA", "NUMBER OF TEETH", "CHAIN PITCH (mm)",
        "ROLLER DIAMETER (mm)", "PITCH DIAMETER (mm", "OUTSIDE DIAMETER (mm)",
        "FACE WIDTH (mm)", "REFERENCE CHAIN", "TOOTH FORM",
        "NOTCH AT SEAT", "NOTCH OUTER",
    ):
        assert field in data, field
    assert "17" in data
    assert spec.SEAT_RADIUS == part.SEAT_RADIUS
    assert spec.NOTCH_OUTER_RADIUS == part.NOTCH_OUTER
    assert spec.SEAT_WIDTH == 2.0 * part.SEAT_HALF_WIDTH
    assert spec.NOTCH_OUTER_WIDTH == 2.0 * part.TIP_HALF_WIDTH
    assert "X.XX" not in data
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_manufacturing_notes_present() -> None:
    assert "CUT 17 EQ-SPACED NOTCHES PER SPROCKET DATA" in spec.DRAWING_NOTES
    assert "STRAIGHT-FLANKED" in spec.DRAWING_NOTES
    assert "DEBUR" not in spec.DRAWING_NOTES
    assert "X.XX" not in spec.DRAWING_NOTES


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

    config = _config.parts("chain-sprocket")
    assert config["material_specification"] == "AISI 1018 cold-finished steel"
    assert config["finish"] == "machined, oiled"
    assert int(config["quantity"]) == 2
