"""Offline contracts for the pen-rod drawing."""

from __future__ import annotations

from pathlib import Path

import build_pen_rod as part
import draw_pen_rod as drawing
import pen_rod_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import NUMBER_DRILL_MM


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = pen_rod_spec.SURFACE_FINISHES
    assert control.key == "slide_face"
    assert control.roughness_um == 1.6
    assert control.face.normal == (-1, 0, 0)
    assert control.face.offset_mm == pen_rod_spec.ROD_SECTION / 2.0
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "slide_face")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pen-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pen-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pen-rod_drawing.png")
    assert DRAWINGS_BY_NAME["pen_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pen_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*pen_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert (part.ROD_SECTION, part.ROD_LENGTH, part.WIRE_HOLE_Y) == (
        pen_rod_spec.ROD_SECTION,
        pen_rod_spec.ROD_LENGTH,
        pen_rod_spec.WIRE_HOLE_Y,
    )


def test_wire_hole_matches_the_number_drill_standard() -> None:
    assert pen_rod_spec.WIRE_HOLE_DIA == NUMBER_DRILL_MM[pen_rod_spec.WIRE_HOLE_DRILL]
    assert pen_rod_spec.WIRE_HOLE_DRILL == "#47"
    assert pen_rod_spec.WIRE_HOLE_Y < pen_rod_spec.ROD_LENGTH
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_native_hole_callout(") == 1
    # Two located dims for the wire hole: along the rod (length) AND across the
    # section (centerline), so the cross-hole cannot drift off-centre.
    assert source.count("add_edge_dimension(") == 2


def test_linked_notes_define_remaining_square_rod_operations() -> None:
    notes = pen_rod_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    assert drawing.TOP_DIMENSION_CALLOUTS == {}
    assert pen_rod_spec.SECTION_BAND == (0.00, -0.05)
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "Section"): "*deviations(SECTION_BAND)",
        ("Rod", "Depth"): "*deviations(SECTION_BAND)",
    }
    assert "V-BLOCK" in notes
    assert "#47" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_slide_faces_and_ends() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from pen_rod_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {"opposite_slide_face_parallelism", "bottom_end_squareness"}
    assert by_key["opposite_slide_face_parallelism"].characteristic == "parallelism"
    assert by_key["opposite_slide_face_parallelism"].tolerance == "0.03"
    assert by_key["opposite_slide_face_parallelism"].datums == ("A",)
    assert by_key["bottom_end_squareness"].characteristic == "perpendicularity"
    assert by_key["bottom_end_squareness"].tolerance == "0.05"
    assert by_key["bottom_end_squareness"].datums == ("A",)
    # Datum A is the -X slide face; its +X opposite rides parallel to it.
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A",)
    assert PART_DATUMS[0].face.normal == (-1, 0, 0)
    assert PART_DATUMS[0].face.offset_mm == pen_rod_spec.ROD_SECTION / 2.0
    assert by_key["opposite_slide_face_parallelism"].face.normal == (1, 0, 0)
    assert by_key["bottom_end_squareness"].face.normal == (0, -1, 0)

    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi(" in source
    assert "controls=GEOMETRIC_CONTROLS" in source
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 3
    assert source.count("scale=(4, 1)") == 1
    assert pen_rod_spec.TOP_VIEW_NOTE == "TOP VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "Top View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pen-rod")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
