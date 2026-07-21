"""Offline contracts for the cylinder-gear drawing (batch gear-drawing pattern)."""

from __future__ import annotations

from pathlib import Path

import build_cylinder_gear as part
import cylinder_gear_spec as spec
import draw_cylinder_gear as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cylinder-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cylinder-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cylinder-gear_drawing.png")
    assert DRAWINGS_BY_NAME["cylinder_gear"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked == {"BoreDia"}


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
    ):
        assert field in data, field
    assert "120" in data
    assert "49.82" in data
    assert "X.XX" not in data
    # The gear-data block is stamped and read as its own linked note.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Gear Data"' in source
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_gear_data_block_is_inset_from_the_zone_border() -> None:
    assert drawing.GEAR_DATA_POS == (0.040, 0.262)
    assert drawing.GEAR_DATA_POS[0] < drawing.FRONT_CENTER[0]


def test_manufacturing_notes_cover_cam_and_teeth() -> None:
    notes = spec.DRAWING_NOTES
    assert "CUT TEETH PER GEAR DATA" in notes
    assert "ECCENTRIC CAM" in notes
    assert "NOTCH" in notes
    assert "RADIAL PLANE THROUGH BORE AXIS + NOTCH CENTERLINE" in notes
    assert "X.XX" not in notes
    assert "DEBUR" not in notes
    assert "20 REQUIRED" not in notes
    assert "30.60 +0/-0.05" in notes
    assert "8.640 +/-0.025" in notes
    assert "MATCH CAM ECCENTRICITY WITHIN 0.025" in notes


def test_running_bore_limits_match_the_shaft_fit_policy() -> None:
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": "THRU - REAM\n+0.05/+0.03"
    }
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 3}


def test_native_gdt_controls_bore_datum_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="perpendicularity"' in source
    assert source.count("add_surface_finish(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cylinder-gear")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "gear teeth cut; polished brass"
    assert int(config["quantity"]) == 20
