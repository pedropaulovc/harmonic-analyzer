"""Offline contracts for the lever-bushing drawing."""

from __future__ import annotations

from pathlib import Path

import build_lever_bushing as part
import draw_lever_bushing as drawing
import lever_bushing_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/lever-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/lever-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/lever-bushing_drawing.png")
    assert DRAWINGS_BY_NAME["lever_bushing"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is lever_bushing_spec.DRAWING_DIMENSIONS
    marked = set().union(*lever_bushing_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.OUTER_DIA, drawing.BORE_DIA, drawing.LENGTH) == (
        lever_bushing_spec.OUTER_DIA,
        lever_bushing_spec.BORE_DIA,
        lever_bushing_spec.LENGTH,
    )


def test_linked_notes_define_remaining_turned_part_operations() -> None:
    notes = lever_bushing_spec.DRAWING_NOTES
    assert "REAM BORE THRU" in notes
    assert drawing.DIMENSION_CALLOUTS["Depth"] == "+/-0.03"
    assert "+0.03/-0.00" in drawing.DIMENSION_CALLOUTS["BoreDia"]
    clearance_min = lever_bushing_spec.BORE_DIA - 6.35
    clearance_max = clearance_min + 0.03 + 0.02
    assert round(clearance_min, 2) == 0.15
    assert round(clearance_max, 2) == 0.20
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_bushing_functional_surfaces() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from lever_bushing_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {"od_runout", "end_face_parallelism"}
    assert by_key["od_runout"].characteristic == "circular_runout"
    assert by_key["od_runout"].tolerance == "0.05"
    assert by_key["od_runout"].datums == ("A",)
    assert by_key["end_face_parallelism"].characteristic == "parallelism"
    assert by_key["end_face_parallelism"].tolerance == "0.03"
    assert by_key["end_face_parallelism"].datums == ("B",)
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A", "B")

    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "import_part_pmi(" in source
    assert "controls=GEOMETRIC_CONTROLS" in source
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert source.count("add_surface_finish(") == 1


def test_sheet_and_views_pin_scale() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(4, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("lever-bushing")
    material = "UNS C36000 H02 per ASTM B16/B16M-24"
    assert config["material"] == material
    assert config["material_specification"] == material
    assert config["finish"]
    assert int(config["quantity"]) == 19
