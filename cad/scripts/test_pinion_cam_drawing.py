"""Offline contracts for the pinion-lift-cam drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_cam_spec
import draw_pinion_cam as drawing
import build_pinion_cam as cam
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-cam.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-cam.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-cam_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_cam"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert cam.DRAWING_DIMENSIONS is pinion_cam_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_cam_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.CAM_OD, drawing.BORE, drawing.ECC) == (
        pinion_cam_spec.CAM_OD,
        pinion_cam_spec.BORE,
        pinion_cam_spec.ECC,
    )


def test_eccentricity_is_dimensioned_and_called_out() -> None:
    # The whole point of the cam: bore and OD are NOT concentric, so the offset
    # must be an explicit dimension, not implied by graphical alignment.
    assert "CollarCy" in drawing.FRONT_KEEP
    assert "ECCENTRICITY" in drawing.DIMENSION_CALLOUTS["CollarCy"]
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "NOT" in notes and "CONCENTRIC" in notes
    assert "OFFSET 1.0" in notes


def test_sheet_runs_at_3_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source  # the isometric override
    assert pinion_cam_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "SLIDING FIT" in notes
    assert "6.360-6.375" in notes
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_unresolved_cam_attachment_is_an_explicit_release_hold() -> None:
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "RELEASE HOLD - DO NOT MANUFACTURE" in notes
    assert "SET-PIN HOLE" in notes
    assert "PIN SPECIFICATION" in notes
    assert "ENGAGEMENT IN THE LIFT ROD" in notes


def test_direct_limits_replace_ambiguous_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "add_surface_finish(" not in source
    assert "6.360/6.375" in drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "+/-0.05" in drawing.DIMENSION_CALLOUTS["CollarCy"]


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(cam.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-cam")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 2
