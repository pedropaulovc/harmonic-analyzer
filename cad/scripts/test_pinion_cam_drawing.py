"""Offline contracts for the pinion-lift-cam drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_cam_geometry
import pinion_cam_spec
import draw_pinion_cam as drawing
import build_pinion_cam as cam
from _buildgraph import module_deps_of
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
    assert pinion_cam_spec.ECC == pinion_cam_geometry.ECC


def test_drive_train_recipe_depends_on_geometry_not_drawing_notes() -> None:
    drive_train = Path(__file__).with_name("build_drive_train_assembly.py")
    dependency_names = {Path(path).name for path in module_deps_of(drive_train)}
    assert "pinion_cam_geometry.py" in dependency_names
    assert "build_pinion_cam.py" not in dependency_names
    assert "pinion_cam_spec.py" not in dependency_names


def test_eccentricity_is_dimensioned_and_called_out() -> None:
    # The whole point of the cam: bore and OD are NOT concentric, so the offset
    # must be an explicit dimension, not implied by graphical alignment.
    assert "CollarCy" in drawing.FRONT_KEEP
    assert "BOTH END FACES" in drawing.DIMENSION_CALLOUTS["CollarCy"]
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "NOT" in notes and "CONCENTRIC" in notes
    assert "OFFSET 1.0" not in notes


def test_sheet_runs_at_3_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Isometric"' in source
    assert "scale=(2, 1)" in source  # the isometric override
    assert pinion_cam_spec.ISOMETRIC_VIEW_NOTE == (
        "ISOMETRIC VIEW SCALE 2:1\n(SET-SCREW BOSS HIDDEN AT REAR)"
    )
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "SLIDING FIT" not in notes
    assert "6.375 MAX / 6.360 MIN" in drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "LINEAR +/-" not in notes
    assert "BRASS" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_cam_attachment_is_fully_released_for_manufacture() -> None:
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "RELEASE HOLD" not in notes
    assert "M2.5 X 0.45-6H" in notes
    assert "ISO 4026" in notes
    assert "2.00 MIN FULL THREAD" in notes
    source = Path(cam.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "M2.5TapDrill")' in source
    assert "TAP_DRILL_DIA" in source


def test_direct_limits_and_native_gdt_control_the_cam_axes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 4
    assert source.count("add_feature_control_frame(") == 2
    assert (
        'symbol_xy=(0.085, 0.105),\n        datum="B",\n'
        '        label="cam final bore axis",\n'
        "        position_tolerance_m=0.003,"
        in source
    )
    assert source.count("position_tolerance_m=0.003") == 1
    assert "set_basic_dimension(" in source
    assert 'datums=("A", "B", "C")' in source
    assert 'datums=("D",)' in source
    assert 'quantity="BOSS OD AXIS"' in source
    assert 'quantity="M2.5 TAP PITCH AXIS"' in source
    assert "COMMON ZONE" not in pinion_cam_spec.DRAWING_NOTES
    assert "POSITION TAP PITCH AXIS TO DATUM D" in pinion_cam_spec.DRAWING_NOTES
    assert "add_surface_finish(" in source
    assert "6.375 MAX / 6.360 MIN" in drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].count("\n") == 1
    assert "*Bottom" in source
    assert "BOSS END VIEW SCALE 2:1" in source
    assert "A TO BOSS / TAP AXIS" in drawing.DIMENSION_CALLOUTS["BossCz"]
    assert "+/-0.05" in drawing.DIMENSION_CALLOUTS["CollarCy"]
    assert "{CAM_OD:.2f} OD" in source


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
