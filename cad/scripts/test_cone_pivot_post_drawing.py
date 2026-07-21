"""Offline contracts for the cone-pivot-post drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_pivot_post as part
import cone_pivot_post_spec
import draw_cone_pivot_post as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-pivot-post.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-pivot-post.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-pivot-post_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_pivot_post"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_pivot_post_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_pivot_post_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert part.BORE_DIA == cone_pivot_post_spec.BORE_DIA == 9.550


def test_marked_dimensions_cover_the_column_and_journal() -> None:
    marked = set().union(*cone_pivot_post_spec.DRAWING_DIMENSIONS.values())
    # Column OD + height, and the journal bore diameter + station: the four
    # machinable dimensions that fully size the turned features.
    assert marked == {"BlockDia", "BlockHt", "BoreDia", "BoreZ"}


def test_notes_specify_both_bores_and_the_oblique_crank_bore() -> None:
    notes = cone_pivot_post_spec.DRAWING_NOTES
    assert "9.545-9.555" in notes
    # The oblique, offset crank bore is fully called out by note (dia, height,
    # tip, offset direction) since it projects as an ellipse in every square view.
    assert "CRANK BORE" in notes
    assert "10.025" in notes
    assert "85.835" in notes
    assert "12.52 +/-0.10 DEG" in notes
    assert "CLOCKWISE FROM B" in notes
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_controls_the_journal_bore() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert source.count("add_feature_control_frame(") == 1
    # The horizontal bore axis is PARALLEL to the horizontal foot seat (datum A).
    assert source.count('characteristic="parallelism"') == 1
    assert source.count("add_surface_finish(") == 1
    assert 'datum="B"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 2  # front elevation + round plan
    assert source.count("scale=(1, 2)") == 1  # reduced pictorial


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-pivot-post")
    assert "A48" in str(config["material_specification"])
    assert "A48" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
