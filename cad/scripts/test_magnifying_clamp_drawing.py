"""Offline contracts for the magnifying-clamp drawing."""

from __future__ import annotations

from pathlib import Path

import build_magnifying_clamp as part
import draw_magnifying_clamp as drawing
import magnifying_clamp_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = magnifying_clamp_spec.SURFACE_FINISHES
    assert control.key == "lever_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == magnifying_clamp_spec.LEVER_BORE_DIA
    assert control.face.contains_y_mm == magnifying_clamp_spec.LEVER_BORE_Y
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "lever_bore")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-clamp.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-clamp.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-clamp_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_clamp"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_clamp_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_clamp_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The block depth + bore stations the assembly imports live in the drawing-
    # FREE geom module, so a print-note edit cannot enter the assembly recipe.
    import magnifying_clamp_geom as geom

    assert (geom.BLOCK_WIDTH, geom.BLOCK_HEIGHT, geom.BLOCK_DEPTH) == (20.0, 26.0, 12.0)
    assembly = Path(part.__file__).with_name("build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from magnifying_clamp_geom import" in assembly
    assert "from build_magnifying_clamp import" not in assembly


def test_linked_notes_specify_slip_bores_and_thumb_screw() -> None:
    notes = magnifying_clamp_spec.DRAWING_NOTES
    assert "SLIP FIT" in notes
    assert "#4-40 UNC-2B, TAPPED" in notes
    assert "BRASS" not in notes and "C36000" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_note_based_thumb_screw() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="parallelism"' in source
    assert source.count("add_surface_finish(") == 1
    # The small #4-40 top-view circle is not a dependable associative-callout
    # pick at this scale; it rides the notes + the top-view centre mark instead.
    assert source.count("add_native_hole_callout(") == 0
    # Block depth added on the sheet across the right-view section.
    assert source.count("add_edge_dimension(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-clamp")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
