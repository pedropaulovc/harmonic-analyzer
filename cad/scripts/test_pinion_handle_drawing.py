"""Offline contracts for the pinion-turning-handle drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_handle_spec
import draw_pinion_handle as drawing
import build_pinion_handle as handle
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-handle_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_handle"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert handle.DRAWING_DIMENSIONS is pinion_handle_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_handle_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (
        drawing.TUBE_ID,
        drawing.ROD_UP,
        drawing.ROD_DOWN,
        drawing.ROD_DIA,
        drawing.ROD_HOLE_DIA,
    ) == (
        pinion_handle_spec.TUBE_ID,
        pinion_handle_spec.ROD_UP,
        pinion_handle_spec.ROD_DOWN,
        pinion_handle_spec.ROD_DIA,
        pinion_handle_spec.ROD_HOLE_DIA,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.TOP_CENTER[1] >= 0.110
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_handle_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_handle_spec.DRAWING_NOTES
    assert "SPHERICAL CROWN" in notes
    assert "DATUM A" in notes and "DATUM B" in notes
    assert "LINEAR +/-" not in notes
    assert "BREAK ALL" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_handle_interfaces_are_fully_released_for_manufacture() -> None:
    notes = pinion_handle_spec.DRAWING_NOTES
    assert "RELEASE HOLD" not in notes
    assert "AT ASSEMBLY" not in notes
    assert "DOWEL" not in notes
    assert "PRESSED CROSS ROD" in notes
    assert "6.010 MAX / 6.000 MIN" in drawing.DIMENSION_CALLOUTS["RodDia"]
    assert "6.020 MAX / 6.015 MIN" in drawing.DIMENSION_CALLOUTS["RodDia"]
    assert 6.015 <= pinion_handle_spec.ROD_DIA <= 6.020
    assert 6.000 <= pinion_handle_spec.ROD_HOLE_DIA <= 6.010
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "merge_result=False" in source
    assert 'name_last_feature(adapter, "RodHole")' in source


def test_drive_train_clearance_uses_the_released_rod_diameter() -> None:
    assembly = Path(handle.__file__).with_name("build_drive_train_assembly.py")
    source = assembly.read_text(encoding="utf-8")
    assert "ROD_DIA as HANDLE_ROD_DIA" in source
    assert "HANDLE_Z - HANDLE_ROD_DIA / 2.0" in source


def test_unique_feature_dimensions_and_direct_bore_limits() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert source.count("add_feature_control_frame(") == 4
    assert "add_surface_finish(" not in source
    assert {"GripLen", "TubeLen", "RodSpan"} <= set().union(
        *pinion_handle_spec.DRAWING_DIMENSIONS.values()
    )
    assert "8.025 MAX / 8.010 MIN" in drawing.DIMENSION_CALLOUTS["TubeId"]
    assert "CYL. LENGTH" in drawing.DIMENSION_CALLOUTS["GripLen"]
    assert drawing.DIMENSION_CALLOUTS["TubeLen"] == "+0.10/-0.00 BORE DEPTH"
    assert drawing.DIMENSION_CALLOUTS["RodSpan"] == "+/-0.10 OAL"
    assert "HUB PROJECTION: DATUM B TO GRIP FACE 12.00 +0.10/-0.00" in (
        pinion_handle_spec.DRAWING_NOTES
    )
    assert "DATUM A TO LOWER END 42.00+/-0.10" in pinion_handle_spec.DRAWING_NOTES


def test_transverse_axis_uses_basic_location_and_position_control() -> None:
    notes = pinion_handle_spec.DRAWING_NOTES
    assert "BASIC 19.00 FROM DATUM B" in notes
    assert "POSITION IS CONTROLLED" in notes
    assert "MID-LENGTH WITHIN" not in notes
    assert "INTERSECTS A WITHIN" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'characteristic="position"' in source
    assert 'datums=("A", "B")' in source
    assert "diameter=True" in source
    assert drawing.FRONT_KEEP["RodSpan"] == (0.115, 0.245)
    assert drawing.FRONT_KEEP["TubeId"][0] >= 0.075
    assert "frame_xy=(0.315, 0.155)" in source
    assert 'quantity="BODY CROSS-HOLE AXIS BEFORE PRESSING"' in source
    assert "BODY CROSS-HOLE VIEW - LOOKING ALONG HOLE AXIS - SCALE 2:1" in source


def test_crown_has_one_toleranced_form_control() -> None:
    notes = pinion_handle_spec.DRAWING_NOTES
    assert f"SR{pinion_handle_spec.CAP_RADIUS:.2f}+/-0.10" in notes
    assert "2.00 REF HIGH" in notes
    assert "2.00+/-0.10 HIGH" not in notes


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(handle.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-handle")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
