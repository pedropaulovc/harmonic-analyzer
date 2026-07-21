"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

from pathlib import Path

import build_harmonic_base as part
import draw_harmonic_base as drawing
import harmonic_base_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/harmonic-base.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/harmonic-base.pdf")
    assert drawing.PNG.as_posix().endswith("/png/harmonic-base_drawing.png")
    assert DRAWINGS_BY_NAME["harmonic_base"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is harmonic_base_spec.DRAWING_DIMENSIONS
    marked = set().union(*harmonic_base_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked
    assert (drawing.BOTTOM_LENGTH, drawing.BOTTOM_WIDTH) == (
        harmonic_base_spec.BOTTOM_LENGTH,
        harmonic_base_spec.BOTTOM_WIDTH,
    )


def test_plate_geometry_is_single_sourced() -> None:
    # The build imports its plate nominals from the spec, so the drawing's view
    # math and the part geometry cannot drift.
    assert part.BOTTOM_LENGTH is harmonic_base_spec.BOTTOM_LENGTH
    assert part.TOP_THICKNESS is harmonic_base_spec.TOP_THICKNESS
    assert harmonic_base_spec.BOTTOM_LENGTH == 18.0 * 25.4
    assert harmonic_base_spec.TOP_LENGTH == 17.5 * 25.4
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("bbox_extent_check(") == 2
    assert "measure_check(" not in source


def test_notes_cover_the_top_plate_reveal_and_seats() -> None:
    notes = harmonic_base_spec.DRAWING_NOTES
    assert "GRAY IRON" not in notes
    assert "ASTM A48" not in notes
    assert "GREEN ENAMEL" not in notes
    assert "DEBURR" not in notes
    assert "UOS" not in notes
    assert "ONE-PIECE CASTING" in notes
    assert "INTEGRAL;" in notes
    assert "JOINED" not in notes
    assert "REVEAL" in notes
    assert "BLIND FROM THE TOP FACE" in notes
    assert "A1-A4" not in notes
    assert "FOUR DIA 13 THRU / DIA 23 X 6.5 DEEP COUNTERBORES" in notes
    assert "LOCATION TOLERANCE +/-0.25" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert 'add_property_linked_note(adapter, "Side View Note", 0.300, 0.090)' in source
    assert "insert_hole_table(" in source
    assert "_visible_hole_table_entities(adapter, top)" in source
    assert "datum_entity=datum_entity" in source
    assert "hole_entities=hole_entities" in source
    assert "GetVisibleEntities2(c, 2)" in source
    assert "GetVisibleEntities2(c, 1)" in source


def test_hole_table_covers_mounting_holes_and_every_hardware_seat() -> None:
    assert len(part.HOLE_XZ) == 4
    assert len(drawing.ALL_HOLES) == 13
    assert drawing.ALL_HOLES[:4] == tuple(
        (x, z, part.HOLE_DIA) for x, z in part.HOLE_XZ
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "basic_locations=False" in source
    assert '"*Front"' in source
    assert len(drawing.TOP_KEEP) == 2
    assert drawing._plan_xy(0.0, 10.0)[1] < drawing.TOP_CENTER[1]


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("harmonic-base")
    assert config["material"] == config["material_specification"]
    assert "gray cast iron" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_dirty_reopened_scale_is_reexported_to_pdf() -> None:
    common_source = Path(drawing.__file__).with_name("_drawing_common.py").read_text(
        encoding="utf-8"
    )
    first_reopen = common_source.index(
        "await reopen_drawing(adapter, outputs.slddrw)"
    )
    dirty_branch = common_source.index("if sheet_scale_dirty:", first_reopen)
    persisted_pdf_export = common_source.index(
        "adapter, str(outputs.slddrw), pdf_path=str(outputs.pdf)",
        first_reopen + 1,
    )
    second_reopen = common_source.index(
        "await reopen_drawing(adapter, outputs.slddrw)", first_reopen + 1
    )
    assert dirty_branch < persisted_pdf_export < second_reopen
    assert "persisted-scale drawing save/export incomplete" in common_source
