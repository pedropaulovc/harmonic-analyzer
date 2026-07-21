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
    assert part.CRANK_BORE_DIA == cone_pivot_post_spec.CRANK_BORE_DIA == 10.025
    assert round(
        cone_pivot_post_spec.CRANK_BORE_DIA
        - cone_pivot_post_spec.CRANK_SHAFT_MAX_DIA,
        3,
    ) == 0.500


def test_marked_dimensions_cover_the_column_and_journal() -> None:
    marked = set().union(*cone_pivot_post_spec.DRAWING_DIMENSIONS.values())
    # Column OD + height, and the journal bore diameter + station: the four
    # machinable dimensions that fully size the turned features.
    assert marked == {"BlockDia", "BlockHt", "BoreDia", "BoreZ"}


def test_notes_specify_both_bores_and_the_oblique_crank_bore() -> None:
    notes = cone_pivot_post_spec.DRAWING_NOTES
    axis = cone_pivot_post_spec.CRANK_AXIS_BASIC_NOTE
    assert "9.545-9.555" in notes
    assert "FINISH RA 1.6" in notes
    assert "BASIC CRANK-BORE AXIS DEFINITION" in axis
    assert "INTERSECTION OF DATUM A AND DATUM AXIS B" in axis
    assert "+Z PARALLEL C, DOWN IN UPPER PLAN" in axis
    assert "LINE = (-0.927, 85.835, -0.206)" in axis
    assert "+ t(-0.21675, 0, +0.97623)" in axis
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    assert "MACHINE FROM CONTINUOUS-CAST ROUND STOCK" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert 'text="CRANK BORE <MOD-DIAM>10.025 +/-0.025 THRU"' in source
    assert "note.SetBalloon(4, 0)" in source


def test_datum_and_notes_control_the_journal_bore() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert "add_datum_feature_to_annotation(" not in source
    assert source.count("add_feature_control_frame(") == 2
    assert "post_od_entity = _circular_edge(" in source
    assert 'label="column outside diameter",\n        entity=post_od_entity' in source
    assert "position_tolerance_m=0.016" in source
    assert "_front_y(BORE_HEIGHT) - _bore_r" in source
    assert "_front_y(BORE_HEIGHT) - _bore_r - 0.015" in source
    assert source.count("position_tolerance_m=0.016") == 2
    assert 'datums=("A", "B")' in source
    assert 'datums=("A", "B", "C")' in source
    assert 'diameter=True' in source
    assert "CRANK_AXIS_BASIC_NOTE" in source
    assert "add_surface_finish(" not in source
    assert "B IS COLUMN OD" in cone_pivot_post_spec.DRAWING_NOTES
    assert "C IS JOURNAL-BORE AXIS" in cone_pivot_post_spec.DRAWING_NOTES


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
    assert "datum b od" in str(config["finish"]).lower()
    assert int(config["quantity"]) == 1
