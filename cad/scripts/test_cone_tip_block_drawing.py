"""Offline contracts for the cone-tip-block drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_tip_block as part
import cone_tip_block_spec
import draw_cone_tip_block as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-block_drawing.png")
    assert DRAWINGS_BY_NAME["cone_tip_block"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_tip_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_tip_block_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    # PinchZ is marked and remains part-owned, but SolidWorks does not import
    # that Hole Wizard placement dimension into the end view. The sheet creates
    # its BASIC datum-to-hole locator natively instead.
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
    assert drawing.DIMENSION_CALLOUTS["PassageDiaDim"] == ("THRU - CLEARANCE PASSAGE")
    assert drawing.DIMENSION_CALLOUTS["BlockHt"] == "+0.05/-0.00"
    assert "A SHAFT-BEARING SURFACE" in cone_tip_block_spec.DRAWING_NOTES


def test_notes_specify_adjuster_and_functional_pinch_joint() -> None:
    notes = cone_tip_block_spec.DRAWING_NOTES
    assert "5/16-18" in notes  # the adjuster tapped hole
    assert "#3-48" in notes  # the pinch tapped hole
    assert "SLOT" in notes
    assert "CLEARANCE" in notes
    assert "OPPOSITE JAW" in notes
    assert "E IS +X PINCH-ENTRY FACE" in notes
    assert "SIMULTANEOUS REQUIREMENT" in notes
    assert "TOTAL MEDIAN-PLANE ZONE" in notes
    assert "DIA 2.946 +0.10/-0.00" in notes
    assert "MATERIAL" not in notes
    assert "OXIDE" not in notes
    assert "DATUM A" in notes
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'adapter, "Manufacturing Notes", 0.020, 0.110' in source
    assert "char_height=" not in source
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="PinchClearance"' in part_source
    assert '"clearance", "#3", end="blind"' in part_source
    assert "depth_mm=(BLOCK_X - SLIT_W) / 2.0" in part_source


def test_datum_and_position_controls_are_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'datum="A"' in source
    assert 'datum="B"' in source
    assert "symbol_xy=(FRONT_CENTER[0], _front_y(0.0) + 0.024)" in source
    assert source.count("position_tolerance_m=0.001") == 2
    assert "_dimension_position" not in source
    assert "GetPosition" not in source
    assert 'width_annotation = front_by_name["Width"]' in source
    assert 'depth_annotation = top_by_name["Depth"]' in source
    assert "annotation=width_annotation" in source
    assert "annotation=depth_annotation" in source
    assert "symbol_xy=DATUM_D_SYMBOL_XY" in source
    assert drawing.DATUM_D_SYMBOL_XY == (0.152, 0.245)
    assert 'datum="C"' in source
    assert 'datum="D"' in source
    assert 'datum="E"' in source
    assert "shoulder=True" in source
    assert source.count('characteristic="position"') == 3
    assert source.count("set_basic_dimension(") == 2
    assert 'label="pinch-axis height"' in source
    assert "CYLINDRICAL ZONE" not in cone_tip_block_spec.DRAWING_NOTES
    assert "CONCENTRIC" not in cone_tip_block_spec.DRAWING_NOTES
    assert 'quantity="2 COAXIAL FEATURES; SIM REQT"' in source
    assert 'quantity="SLOT MEDIAN PLANE; BASIC 0 TO B"' in source
    assert 'datums=("A", "D", "E")' in source


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
