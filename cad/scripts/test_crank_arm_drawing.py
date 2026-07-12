"""Offline contracts for the crank-arm drawing."""

from __future__ import annotations

from pathlib import Path

import crank_arm_spec
import draw_crank_arm as drawing
import build_crank_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["crank_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert arm.DRAWING_DIMENSIONS is crank_arm_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_arm_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    )
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.ARM_END_X, drawing.HALF_WIDTH) == (
        crank_arm_spec.ARM_END_X,
        crank_arm_spec.HALF_WIDTH,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert crank_arm_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_use_us_customary_fasteners_and_functional_tolerances() -> None:
    notes = crank_arm_spec.DRAWING_NOTES
    assert "TAPER PIN" in notes
    assert "1:48" in notes
    assert "3/8 IN" in drawing.DIMENSION_CALLOUTS["ShaftBoreDia"]
    assert "15/64 DRILL THRU" in notes
    assert "#9 DRILL" in notes
    assert "LINEAR +/-0.25" in notes
    assert "HOLE CENTRES +/-0.10" in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["ShaftBoreDia"].startswith("THRU")
    assert callouts["DimpleDia"] == "0.5 DEEP"


def test_native_gdt_replaces_form_orientation_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert source.count("add_feature_control_frame(") == 2
    assert "characteristic=\"parallelism\"" in source
    assert "characteristic=\"position\"" in source
    assert "add_surface_finish(" in source


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "BoreProfile" not in arm.DRAWING_DIMENSIONS
    assert "PinHoleProfile" not in arm.DRAWING_DIMENSIONS
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("drilled_fractional", "15/64")' in source
    assert 'HoleSpec("drilled_number", "#9")' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("crank-arm")
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
