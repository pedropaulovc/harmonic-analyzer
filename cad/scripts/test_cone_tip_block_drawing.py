"""Offline contracts for the cone-tip-block drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_tip_block as part
import cone_tip_block_spec
import draw_cone_tip_block as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import CLEARANCE_MM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-block_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_tip_block"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_tip_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_tip_block_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    # PinchZ is marked and remains part-owned, but SolidWorks does not import
    # that Hole Wizard placement dimension into the end view. The sheet creates
    # the foot-to-pinch-axis height natively instead.
    assert kept | {"PinchZ"} == marked
    assert marked == {
        "Width",
        "Depth",
        "BlockHt",
        "PassageDiaDim",
        "PassageZ",
        "PinchZ",
        "SlitW",
    }
    assert part.ADJUSTER_AXIS_HEIGHT == cone_tip_block_spec.ADJUSTER_AXIS_HEIGHT


def test_non_bearing_tip_passage_replaces_the_fictional_journal() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "JournalBore" not in source
    assert "BoreDiaDim" not in source
    assert 'name_last_feature(adapter, "ShaftPassage")' in source
    assert part.SHAFT_PASSAGE_DIA == cone_tip_block_spec.SHAFT_PASSAGE_DIA == 2.0
    assert drawing.DIMENSION_CALLOUTS["PassageDiaDim"] == "DRILL THRU"
    assert "BlockHt" not in drawing.DIMENSION_CALLOUTS


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = cone_tip_block_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "5/16-18" in notes  # the adjuster tap
    assert "#3-48" in notes  # the pinch tap
    assert "#32 DRILL" in notes  # the pinch clearance has no callout of its own
    assert "OPPOSITE JAW" in notes
    assert "SLIT" in notes
    # Nothing the title block, a dimension or a deleted frame used to say.
    for banned in ("+/-", "DATUM", "FRAME", "SIMULTANEOUS", "MATERIAL", "OXIDE", "X.XX", "UOS"):
        assert banned not in notes, banned
    # #3 normal clearance (2.946 = 0.1160 in) is exactly the #32 drill.
    assert cone_tip_block_spec.PINCH_CLEARANCE_DIA == CLEARANCE_MM[("#3", "normal")]
    assert round(0.116 * 25.4, 3) == cone_tip_block_spec.PINCH_CLEARANCE_DIA
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'adapter, "Manufacturing Notes", 0.020, 0.088, char_height=0.0025' in source
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="PinchClearance"' in part_source
    assert '"clearance", "#3", end="blind"' in part_source
    assert "depth_mm=(BLOCK_X - SLIT_W) / 2.0" in part_source


def test_slit_callout_carries_the_depth_the_views_do_not_dimension() -> None:
    assert drawing.DIMENSION_CALLOUTS["SlitW"] == "WIDE X 8.00 DEEP"
    assert cone_tip_block_spec.SLIT_DEPTH == 8.0


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rules 3-5: a clamp block is not on the GD&T
    # allowlist and nothing runs in its passage.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_note(",
    ):
        assert helper not in source, helper
    assert not hasattr(cone_tip_block_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(cone_tip_block_spec, "SURFACE_FINISHES")
    # The pinch-axis height survives as an ordinary entity-selected dimension.
    assert 'label="pinch-axis height"' in source
    assert "draw.AddVerticalDimension2(" in source


def test_only_the_fitted_block_height_prints_three_decimals() -> None:
    assert drawing.DIMENSION_PRECISION == {"PassageZ": 2, "BlockHt": 3}
    assert cone_tip_block_spec.BLOCK_HEIGHT_BAND == (0.05, 0.00)


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(2, 1)") == 4  # elevation + plan + side + pictorial


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-tip-block")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
