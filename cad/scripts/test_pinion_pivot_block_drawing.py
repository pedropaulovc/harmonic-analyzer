"""Offline contracts for the pinion-pivot-block drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_pivot_block_spec
import draw_pinion_pivot_block as drawing
import build_pinion_pivot_block as block
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = pinion_pivot_block_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_pivot_block_spec.BORE_DIA
    assert control.face.contains_y_mm == -pinion_pivot_block_spec.BORE_DIA / 2.0
    part_source = Path(block.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "pivot_bore")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-pivot-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-pivot-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-pivot-block_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_pivot_block"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert block.DRAWING_DIMENSIONS is pinion_pivot_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_pivot_block_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.BLOCK_WIDTH, drawing.FRONT_BBOX_CY, drawing.BORE_HALF_SPACING) == (
        pinion_pivot_block_spec.BLOCK_WIDTH,
        pinion_pivot_block_spec.FRONT_BBOX_CY,
        pinion_pivot_block_spec.BORE_HALF_SPACING,
    )


def test_sheet_runs_at_3_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source  # the isometric override
    assert pinion_pivot_block_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_use_us_customary_fasteners_and_functional_tolerances() -> None:
    notes = pinion_pivot_block_spec.DRAWING_NOTES
    assert "#8 NORMAL CLEARANCE Ø4.978 THRU" in notes
    assert "1/4 IN REAM THRU" in notes
    assert "1/4 IN" in drawing.DIMENSION_CALLOUTS["PivotBoreDia"]
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["PivotBoreDia"].startswith("THRU")
    assert callouts["LiftBoreDia"].startswith("THRU")
    assert "+0.05/-0.00" not in "\n".join(callouts.values())
    assert model_toleranced_dimensions(block) == {
        ("BlockProfile", "PivotBoreDia"): "*deviations(BORE_DIA_BAND)",
        ("BlockProfile", "LiftBoreDia"): "*deviations(BORE_DIA_BAND)",
    }


def test_native_gdt_replaces_form_orientation_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 2
    assert (
        "        edge_xy=pivot_edge,\n"
        "        symbol_xy=(_front_x(BORE_HALF_SPACING) + 0.0145, _front_y(0.0) - 0.026),\n"
        '        datum="B",\n'
        '        label="pivot bore axis",\n'
        "        position_tolerance_m=0.003," in source
    )
    assert source.count("position_tolerance_m=0.003") == 1
    assert 'characteristic="parallelism"' in source
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "set_basic_dimension(" in source  # the 27 hold-down spacing


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    # The hold-down holes are a native Hole Wizard feature: their size comes
    # from the clearance standard, so no ScrewHoles dimension may be hand-marked.
    assert not any("Screw" in feature for feature in block.DRAWING_DIMENSIONS)
    source = Path(block.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("clearance", "#8")' in source


def test_spec_screw_diameter_matches_the_clearance_table() -> None:
    # The spec stays COM-free and records the #8 normal-clearance diameter used
    # for drawing layout; pin it to the table the part build actually cuts with.
    from _holes import CLEARANCE_MM

    assert pinion_pivot_block_spec.SCREW_HOLE_DIA == CLEARANCE_MM[("#8", "normal")]
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
