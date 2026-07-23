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
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
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
    assert marked == {"HandleLength", "CollarLength", "PeakStation", "PivotBoreDia"}
    notes = crank_handle_spec.DRAWING_NOTES
    assert "BASIC TRUE GRIP PROFILE" in notes
    assert "ALL VALUES BASIC" in notes
    assert f"R{crank_handle_spec.FRONT_PROFILE_R:.6f}" in notes
    assert f"R{crank_handle_spec.REAR_PROFILE_R:.6f}" in notes


def test_peak_station_uses_visible_construction_geometry() -> None:
    build_source = Path(handle.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'profile.record("PeakStation",' in build_source
    assert 'profile.record("FrontArcCx",' in build_source
    assert '"PeakStation":' in drawing_source
    assert '"FrontArcCx":' not in drawing_source
    assert "peak station construction line" in build_source


def test_bored_profile_has_end_view_center_marks() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks" in source
    assert "add_view_centerline" in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert crank_handle_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = crank_handle_spec.DRAWING_NOTES
    assert "CDA 260" not in notes
    assert "TURN COLLAR INTEGRAL" in notes
    assert "COIL" not in notes
    assert "LINEAR +/-" not in notes
    assert "BRASS" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_pivot_interface_is_fully_released_for_manufacture() -> None:
    notes = crank_handle_spec.DRAWING_NOTES
    assert "RELEASE HOLD" not in notes
    assert "BORE AXIS CONCENTRIC" not in notes
    assert "NO BLEND, RADIUS, OR CHAMFER" in notes
    assert "FINAL BORE LIMITS APPLY FULL LENGTH" in notes
    assert "STRAIGHT GRAIN PARALLEL TO TURNING AXIS" in notes
    assert "X90.00" in notes
    assert "ACTUAL BUTT FACE AT 90.00+0.00/-0.25 TRIMS" in notes
    assert "ACTUAL BUTT TRIM FACE" in notes
    assert "GENERAL Ra 3.2" not in notes
    assert "PROFILE 0.50 | A | B APPLIES" in notes
    assert "NOMINAL REF ONLY" in drawing.DIMENSION_CALLOUTS["PivotBoreDia"]
    assert "6.15 MAX / 6.10 MIN THRU" in drawing.DIMENSION_CALLOUTS[
        "PivotBoreDia"
    ]


def test_feature_requirements_use_datum_based_full_length_controls() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert "expected_position_xy=(RIGHT_CENTER[0], 0.245)" in source
    assert source.count("position_tolerance_m=0.001") == 1
    assert source.count("add_feature_control_frame(") == 3
    assert 'characteristic="perpendicularity"' in source
    assert 'quantity="DATUM B FACE"' in source
    assert 'characteristic="total_runout"' in source
    assert 'characteristic="profile_surface"' in source
    assert 'quantity="FULL BORE LENGTH"' in source
    assert 'quantity="TURNED GRIP PROFILE - SEE NOTE"' in source
    assert "set_basic_dimension(" in source
    assert "add_surface_finish(" not in source
    assert drawing.RIGHT_KEEP["PivotBoreDia"] == (0.360, 0.220)
    assert "frame_xy=(0.350, 0.263)" in source
    assert "frame_xy=(0.180, 0.263)" in source
    assert "SetDisplayTangentEdges2(0)" in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("crank-handle")
    assert handle.MATERIAL == "Oak"
    assert "white oak" in spec["material_specification"]
    assert "6-8% MC" in spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
