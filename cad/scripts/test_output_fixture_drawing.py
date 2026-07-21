"""Offline contracts for the output-fixture drawing."""

from __future__ import annotations

from pathlib import Path

import build_output_fixture as part
import draw_output_fixture as drawing
import output_fixture_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/output-fixture.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/output-fixture.pdf")
    assert drawing.PNG.as_posix().endswith("/png/output-fixture_drawing.png")
    assert (
        DRAWINGS_BY_NAME["output_fixture"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is output_fixture_spec.DRAWING_DIMENSIONS
    marked = set().union(*output_fixture_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP)
    assert kept == marked


def test_spec_is_the_single_source_of_collar_nominals() -> None:
    # The build consumes the spec nominals directly (codex review #361), and
    # the pure-data spec's tap-drill literal stays locked to the producer table.
    from _holes import TAP_DRILL_MM

    assert part.COLLAR_DIA is output_fixture_spec.COLLAR_DIA
    assert part.COLLAR_HEIGHT is output_fixture_spec.COLLAR_HEIGHT
    assert part.ROD_BORE_DIA is output_fixture_spec.ROD_BORE_DIA
    assert part.CROSS_HOLE_DIA is output_fixture_spec.CROSS_HOLE_DIA
    assert output_fixture_spec.CROSS_HOLE_DIA == TAP_DRILL_MM["#4-40"]


def test_notes_describe_bore_and_cross_hole() -> None:
    notes = output_fixture_spec.DRAWING_NOTES
    assert "FINISHED COLLAR" in notes
    assert "ROD BORE" in notes
    assert "CROSS-HOLE" in notes
    assert "RELATIVE TO THE ROD-BORE AXIS" in notes
    assert "TAP FIRST WALL ONLY #4-40 UNC-2B RH" in notes
    assert "CDA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(3, 1)" in source
    assert "scale=(2, 1)" in source
    assert output_fixture_spec.END_VIEW_NOTE == "END VIEW SCALE 3:1"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("output-fixture")
    assert config["material"] == "C36000 free-cutting brass"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1
