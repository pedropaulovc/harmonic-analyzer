"""Offline contracts for the pinion-pivot-block drawing."""

from __future__ import annotations

import re
from pathlib import Path

import pinion_pivot_block_spec
import draw_pinion_pivot_block as drawing
import build_pinion_pivot_block as block
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_limits import REAM_SLIDE
from _hole_spec import blind_cut_dia_mm


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
    assert (drawing.BLOCK_WIDTH, drawing.FRONT_BBOX_CY, drawing.FRONT_BBOX_CX) == (
        pinion_pivot_block_spec.BLOCK_WIDTH,
        pinion_pivot_block_spec.FRONT_BBOX_CY,
        pinion_pivot_block_spec.FRONT_BBOX_CX,
    )


def test_sheet_runs_at_3_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source  # the isometric override
    assert pinion_pivot_block_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_use_us_customary_fasteners_and_functional_tolerances() -> None:
    notes = pinion_pivot_block_spec.DRAWING_NOTES
    # Fable review r4: the notes no longer restate the REAM and hold-down
    # callouts; they name each running bore's mate (rule 2).
    assert "Ø4.978" not in notes
    assert "REAM" not in notes
    assert "MHA-062 TORQUE SHAFT" in notes
    assert "MHA-060 LIFT ROD" in notes
    assert "TURNS FREELY BY HAND" in notes
    # R2 (converged-r7): REAM_SLIDE, one fit per shaft with MHA-056; the
    # stock 1/4 in reamer wording went with the line-to-line band.
    assert pinion_pivot_block_spec.BORE_DIA_BAND == REAM_SLIDE
    assert "1/4 IN" not in drawing.DIMENSION_CALLOUTS["PivotBoreDia"]
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert not re.search(r"\bBA\b", notes)
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


def test_block_carries_no_gdt_only_its_running_bore_finish() -> None:
    # Drawing-simplicity policy rules 3/4: blocks are not on the GD&T
    # allowlist, so no datum tags, no feature-control frames, no basic boxes.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "set_basic_dimension(" not in source
    assert not hasattr(pinion_pivot_block_spec, "GEOMETRIC_TOLERANCES_MM")
    assert "DATUM" not in pinion_pivot_block_spec.DRAWING_NOTES
    assert "add_surface_finish(" in source
    # The hold-downs are ordinary coordinates from the west end.
    assert '"west hold-down station"' in source
    assert '"east hold-down station"' in source


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    # The hold-down holes are a native Hole Wizard feature: their size comes
    # from the clearance standard, so no ScrewHoles dimension may be hand-marked.
    assert not any("Screw" in feature for feature in block.DRAWING_DIMENSIONS)


def test_screw_hole_contract_is_part_owned_and_resolved() -> None:
    spec = pinion_pivot_block_spec.SCREW_HOLE_SPEC
    assert block.SCREW_HOLE_SPEC is spec
    assert spec.kind == "clearance"
    assert spec.size == "#8"
    assert spec.fit == "normal"
    assert pinion_pivot_block_spec.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)
    assert drawing.SCREW_HOLE_DIA == blind_cut_dia_mm(spec)


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(block.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-pivot-block")
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 2  # the book uses two blocks


def test_notes_stay_within_policy_and_carry_the_assembly_transfer() -> None:
    notes = pinion_pivot_block_spec.DRAWING_NOTES.splitlines()
    assert len(notes) <= 4  # policy rule 6
    assert "SPOT BASE SEATS THROUGH BLOCK HOLES AT ASSEMBLY." in notes
    assert not any("FINISH" in line for line in notes)  # the title block owns it


def test_assembly_and_base_depend_on_geometry_not_drawing_notes() -> None:
    from _buildgraph import module_deps_of

    for script in ("build_drive_train_assembly.py", "build_harmonic_base.py"):
        deps = {
            Path(path).name for path in module_deps_of(Path(__file__).with_name(script))
        }
        assert "pinion_pivot_block_geometry.py" in deps, script
        assert "pinion_pivot_block_spec.py" not in deps, script
        assert "build_pinion_pivot_block.py" not in deps, script


def test_views_carry_no_hidden_lines_and_the_drill_callout_names_its_process() -> None:
    # Fable review r4 (rule 7): the holes are standard drills and reams fully
    # defined by their callouts, so every view is hidden-lines-removed.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hidden_lines_visible" not in source
    assert "for view in (front, top, right, iso):" in source
    assert 'process="DRILL"' in source
    assert "symbol_xy=(0.208, 0.170)" in source
    assert "char_height=0.0025" in source
    # The Ra leader must leave the block through its top face, left of the
    # corner where BlockHeight's extension line starts.
    rim = (
        drawing._front_x(0.0) + drawing.BORE_R_SHEET * 0.866,
        drawing._front_y(0.0) + drawing.BORE_R_SHEET * 0.5,
    )
    top_y = drawing._front_y(
        pinion_pivot_block_spec.BLOCK_HEIGHT - pinion_pivot_block_spec.BORE_UP
    )
    slope = (0.170 - rim[1]) / (0.208 - rim[0])
    exit_x = rim[0] + (top_y - rim[1]) / slope
    assert exit_x < drawing._front_x(pinion_pivot_block_spec.BLOCK_EAST) - 0.003
