"""Offline contracts for the pinion-pivot-block drawing.

A mounting block is not on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md): no datums, frames, basics or
roughness symbols; the ream and bore-height bands ride the model dimensions,
the hole callout names the drill, every hole axis is located from a face,
and the notes are one line.
"""

from __future__ import annotations

from pathlib import Path

import pinion_pivot_block_spec
import draw_pinion_pivot_block as drawing
import build_pinion_pivot_block as block
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-pivot-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-pivot-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-pivot-block_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_pivot_block"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert block.DRAWING_DIMENSIONS is pinion_pivot_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_pivot_block_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The from-mid-plane stations are not on the print: the bores are located
    # by edge dimensions from the left end (machinist review 2026-09-02).
    assert not {"PivotBoreX", "LiftBoreX"} & marked
    assert {"AnchorZ", "LiftBoreCz"} <= marked
    assert (drawing.BLOCK_WIDTH, drawing.FRONT_BBOX_CY, drawing.BORE_HALF_SPACING) == (
        pinion_pivot_block_spec.BLOCK_WIDTH,
        pinion_pivot_block_spec.FRONT_BBOX_CY,
        pinion_pivot_block_spec.BORE_HALF_SPACING,
    )
    assert pinion_pivot_block_spec.LIFT_BORE_FROM_END == 11.75
    assert pinion_pivot_block_spec.SCREW_FROM_END == 4.5


def test_sheet_runs_at_3_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = _source()
    assert "scale=(2, 1)" in source  # the isometric override
    assert pinion_pivot_block_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_pivot_block_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert notes.isascii()
    assert "REAM BOTH BORES IN ONE SETUP." in notes
    # Locations are dimensions from faces and the bore heights carry bands:
    # no mid-plane symmetry claim, no "matched pair" note (the two blocks are
    # interchangeable parts -- the shafts pass through both).
    for banned in (
        "MID-PLANE",
        "SYMMETRIC",
        "MATCHED",
        "BOTH BLOCKS",
        "DRILL",
        "FINISH",
        "RUNNING FIT",
        "DATUM",
        "+/-",
        "LINEAR",
        "HOLE CENTRES",
        "X.XX",
    ):
        assert banned not in notes, banned
    assert "BA" not in notes
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_callouts_state_size_and_process() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["PivotBoreDia"] == "REAM THRU (1/4 IN)"
    assert callouts["LiftBoreDia"] == "REAM THRU (1/4 IN)"
    assert "+0.05/-0.00" not in "\n".join(callouts.values())
    source = _source()
    assert source.count("add_native_hole_callout(") == 1
    assert 'process="#19 DRILL"' in source
    assert model_toleranced_dimensions(block) == {
        ("BlockProfile", "PivotBoreDia"): "*deviations(BORE_DIA_BAND)",
        ("BlockProfile", "LiftBoreDia"): "*deviations(BORE_DIA_BAND)",
        ("BlockProfile", "AnchorZ"): "PIVOT_BORE_HEIGHT_TOLERANCE_MM",
        ("BlockProfile", "LiftBoreCz"): "LIFT_BORE_RISE_TOLERANCE_MM",
    }
    assert pinion_pivot_block_spec.PIVOT_BORE_HEIGHT_TOLERANCE_MM <= 0.05
    assert pinion_pivot_block_spec.LIFT_BORE_RISE_TOLERANCE_MM <= 0.05


def test_every_hole_axis_is_located_from_a_face() -> None:
    # Front: lift bore from the left end, pivot bore from the lift bore (the
    # pair the strap swings on, printed in the .XXX class), both snapped to
    # the bore centres.  Top: the west hold-down hole from the left end, the
    # 27 spacing, and the 6 from the broad face.
    source = _source()
    assert source.count("add_edge_dimension(") == 5
    assert 'label="left end to lift bore axis"' in source
    assert 'label="lift bore axis to pivot bore axis"' in source
    assert 'label="left end to hold-down hole axis"' in source
    assert 'label="hold-down screw spacing"' in source
    assert 'label="hold-down depth location"' in source
    assert source.count("set_arc_endpoints_to_center(") == 3
    assert drawing.BORE_SPACING_DECIMALS == 3
    assert "_set_display_precision(" in source
    # Heights split sides so no extension line crosses the other bore's
    # dimension: pivot height right (with the block height), lift rise left.
    assert drawing.FRONT_KEEP["AnchorZ"][0] > drawing.FRONT_CENTER[0]
    assert drawing.FRONT_KEEP["LiftBoreCz"][0] < drawing.FRONT_CENTER[0]
    # The station chain sits inboard of the outermost block width.
    assert drawing.STATION_TEXT_Y > drawing.FRONT_KEEP["BlockWidth"][1]


def test_diameter_leaders_end_at_the_circumference() -> None:
    source = _source()
    assert "_ARROWS_OUTSIDE = 1" in source
    assert source.count("_leaders_to_circumference(") >= 2  # def + call
    assert drawing.FRONT_DIAMETERS == ("PivotBoreDia", "LiftBoreDia")


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "WITHIN" not in source
    assert not hasattr(pinion_pivot_block_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pinion_pivot_block_spec, "GEOMETRIC_CONTROLS")
    assert pinion_pivot_block_spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in Path(block.__file__).read_text(
        encoding="utf-8"
    )


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    # The hold-down holes are a native Hole Wizard feature: their size comes
    # from the drill standard, so no ScrewHoles dimension may be hand-marked.
    assert not any("Screw" in feature for feature in block.DRAWING_DIMENSIONS)
    source = Path(block.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("drilled_number", "#19")' in source


def test_spec_screw_diameter_matches_the_number_drill_table() -> None:
    # The spec hardcodes the #19 drill diameter (it must stay COM-free); this
    # pins it to the drill table the build actually cuts with.
    from _holes import NUMBER_DRILL_MM

    assert pinion_pivot_block_spec.SCREW_HOLE_DIA == NUMBER_DRILL_MM["#19"]
    assert block.SCREW_HOLE_DIA == pinion_pivot_block_spec.SCREW_HOLE_DIA


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(block.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-pivot-block")
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 2  # the book uses two blocks
