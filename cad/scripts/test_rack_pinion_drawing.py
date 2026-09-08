"""Offline contracts for the rack-pinion drawing (batch gear pattern)."""

from __future__ import annotations

from pathlib import Path

import build_rack_pinion as part
import draw_rack_pinion as drawing
import rack_pinion_spec as spec
from _drawing_contract import model_toleranced_dimensions
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
        "GEAR DATA",
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "MODULE (mm",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (mm",
        "OUTSIDE DIAMETER (mm)",
        "WHOLE DEPTH (mm)",
        "FACE WIDTH (mm)",
        "TOOTH FORM",
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
    assert source.count("add_native_axis_datum(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert source.count("add_surface_finish(") == 1
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "THRU - REAM"}
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)"
    }


def test_native_axis_datum_preserves_stability_limit_and_clear_layout() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    datum_a = source[source.index("add_native_axis_datum("):]
    datum_a = datum_a[:datum_a.index("    )")]
    assert "entity=bore_edge" in datum_a
    assert "source_path=SOURCE" in datum_a
    assert "radius_m=BORE_DIA / 2000.0" in datum_a
    assert "stability_tolerance_m=0.0001" in datum_a
    assert "shoulder=True" in datum_a
    assert "edge_xy=" not in datum_a
    assert "symbol_xy=" not in datum_a
    assert drawing.FRONT_KEEP["BoreDia"] == (
        drawing.FRONT_CENTER[0] - 0.062, drawing.FRONT_CENTER[1] + 0.038,
    )
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 2}


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("rack-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "gear teeth cut; polished brass"
    assert int(config["quantity"]) == 1


def test_finish_layout_preserves_semantic_bore_and_separates_native_datum() -> None:
    assert drawing.BORE_FINISH_POSITION == (
        drawing.FRONT_CENTER[0] + 0.058, drawing.FRONT_CENTER[1] - 0.062,
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    finish = source[source.index("finish = add_surface_finish("):]
    assert "symbol_xy=BORE_FINISH_POSITION" in finish
    assert "entity=bore_edge" in finish
    assert "leader_attach_xy=model_point_in_view(" in finish
    assert "(BORE_DIA / 2000.0, 0.0, FACE_WIDTH / 1000.0)" in finish
    assert "IsSame(finish_entities[0], bore_edge)) != 1" in finish
    assert "finish_annotation.IsDangling()" in finish


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spec.BORE_DIA
    assert part.BORE_DIAMETER == spec.BORE_DIA
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert 'control=surface_finish_by_key(SURFACE_FINISHES,"bore")' in sheet_source
    assert "roughness_ra=" not in sheet_source
