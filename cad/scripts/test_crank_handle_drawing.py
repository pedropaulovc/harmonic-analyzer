"""Offline contracts for the crank-handle drawing."""

from __future__ import annotations

from pathlib import Path

import crank_handle_spec
import draw_crank_handle as drawing
import build_crank_handle as handle
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-handle_drawing.png")
    assert (
        DRAWINGS_BY_NAME["crank_handle"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert handle.DRAWING_DIMENSIONS is crank_handle_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_handle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The build re-imports its primitive nominals from the spec.
    assert (handle.HANDLE_LENGTH, handle.COLLAR_LENGTH, handle.PEAK_X) == (
        crank_handle_spec.HANDLE_LENGTH,
        crank_handle_spec.COLLAR_LENGTH,
        crank_handle_spec.PEAK_X,
    )


def test_diameters_are_a_turning_schedule_not_marked_dims() -> None:
    # The pear arcs derive the diameters, so only the axial stations are marked;
    # the diameters live in the turning-schedule note.
    marked = set().union(*crank_handle_spec.DRAWING_DIMENSIONS.values())
    assert marked == {"HandleLength", "CollarLength", "PeakStation"}
    notes = crank_handle_spec.DRAWING_NOTES
    assert "TURNING SCHEDULE" in notes
    assert "SMOOTH PEAR CURVE" in notes


def test_peak_station_uses_visible_construction_geometry() -> None:
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'profile.record("PeakStation",' in build_source
    assert 'profile.record("FrontArcCx",' in build_source
    assert '"PeakStation":' in drawing_source
    assert '"FrontArcCx":' not in drawing_source
    assert "peak station construction line" in build_source


def test_solid_profile_does_not_request_hole_center_marks() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks" not in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert crank_handle_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = crank_handle_spec.DRAWING_NOTES
    assert "CDA 260" not in notes
    assert "COLLAR PROFILE INTEGRAL WITH THE OAK HANDLE" in notes
    assert "COIL" not in notes
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_unresolved_pivot_interface_is_an_explicit_release_hold() -> None:
    notes = crank_handle_spec.DRAWING_NOTES
    assert "RELEASE HOLD - DO NOT MANUFACTURE" in notes
    assert "HANDLE PIVOT BORE/PIN" in notes
    assert "RUNNING CLEARANCE" in notes
    assert "AXIAL RETENTION" in notes


def test_feature_requirements_do_not_use_ambiguous_unused_datums() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "add_surface_finish(" not in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("crank-handle")
    assert spec["material"] == handle.MATERIAL == "Oak"
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
