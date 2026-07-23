"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

from pathlib import Path

import rocker_arm_notes
import rocker_arm_spec
import draw_rocker_arm as drawing
import build_rocker_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*rocker_arm_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept | drawing.NOTE_ONLY_DIMENSIONS == marked


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        rocker_arm_spec.ROD_HOLE_X,
        rocker_arm_spec.TOP_END_Y,
    )
    assert rocker_arm_spec.CURVE_RADIUS == arm.CURVE_RADIUS
    assert rocker_arm_spec.ARM_DEPTH == arm.ARM_DEPTH
    assert rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_metric_and_not_title_block_duplicates() -> None:
    notes = rocker_arm_notes.DRAWING_NOTES
    assert "R800" in notes
    assert "R816" in notes
    # The rod hole rides its native Ø1.99 THRU ALL callout; the notes state
    # count and process only, never a second copy of a sheet dimension.
    assert "(1X)" in notes
    assert "#47" not in notes
    assert "REAM +0.03/0" in notes
    assert "16.00 REF" in notes
    assert "11.5 IN" not in notes
    assert "0.22 IN" not in notes
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = pivot bore axis, B = broad face (right end view), C = rod-side tip
    # face; the rod-pin position frame references all three.
    assert source.count("add_datum_feature(") == 3
    assert "expected_position_xy=(0.2648747931647749, 0.1929447587278372)" in source
    assert source.count("position_tolerance_m=0.0001") == 1
    assert "pivot_datum_angle = math.radians(135.0)" in source
    assert 'label="pivot bore cylindrical datum feature"' in source
    assert source.count("shoulder=True") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'datums=("A", "B", "C")' in source
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "add_native_hole_callout(" in source
    assert source.count("edge_xy=rod_rim") == 2


def test_large_radius_values_are_note_only() -> None:
    assert drawing.NOTE_ONLY_DIMENSIONS == {"TopRadius", "BottomRadius"}
    assert "R800" in rocker_arm_notes.DRAWING_NOTES
    assert "R816" in rocker_arm_notes.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("rocker-arm")
    assert spec["material_specification"] == "AISI 1018 cold-rolled steel strap"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20
