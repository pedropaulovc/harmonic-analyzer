"""Offline manufacturing contracts for the cylinder-gear drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_cylinder_gear as part
import cylinder_gear_spec as spec
import draw_cylinder_gear as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout



def test_required_paths_and_explicit_sheet_orientation() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cylinder-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cylinder-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cylinder-gear_drawing.png")
    registered = DRAWINGS_BY_NAME["cylinder_gear"]
    assert registered.script == Path(drawing.__file__).resolve()
    assert registered.layout is DrawingLayout.PORTRAIT
    assert drawing.SHEET_SCALE == (3.0, 2.0)
    assert drawing.VIEW_SCALE == (3, 2)


def test_spec_is_the_single_source_of_native_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked == {
        "BoreDia",
        "CamDia",
        "CamCy",
        "CamThickness",
        "FaceWidth",
        "NotchDepth",
        "NotchWidth",
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert set(drawing.DIMENSION_PRECISION) == marked


def test_model_dimensions_carry_the_manufacturing_tolerances() -> None:
    assert model_toleranced_dimensions(part) == {
        ("GearBlank", "FaceWidth"): "FACE_WIDTH_TOLERANCE_MM",
        ("CamProfile", "CamDia"): "*deviations(CAM_DIA_BAND)",
        ("CamProfile", "CamCy"): "ECCENTRICITY_TOLERANCE_MM",
        ("NotchProfile", "NotchWidth"): "*deviations(NOTCH_WIDTH_BAND)",
        ("NotchProfile", "NotchDepth"): "NOTCH_DEPTH_TOLERANCE_MM",
    }


def test_gear_data_is_the_only_tooth_system_authority() -> None:
    data = spec.GEAR_DATA
    for field in (
        "GEAR DATA",
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "MODULE (mm",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (mm",
        "OUTSIDE DIAMETER (mm)",
        "WHOLE DEPTH (mm)",
        "TOOTH FORM",
        "INVOLUTE, FULL DEPTH",
    ):
        assert field in data, field
    assert "120" in data
    assert "49.82" in data
    assert "FACE WIDTH" not in data
    assert "CAM" not in data
    assert "NOTCH" not in data
    assert "X.XX" not in data


def test_dimension_precision_matches_functional_tolerance() -> None:
    assert drawing.DIMENSION_PRECISION == {
        "BoreDia": 3,
        "CamDia": 2,
        "FaceWidth": 2,
        "CamCy": 3,
        "CamThickness": 1,
        "NotchWidth": 2,
        "NotchDepth": 1,
    }
    assert spec.OVERALL_THICKNESS == spec.FACE_WIDTH + spec.CAM_THICKNESS


def test_projected_views_remain_aligned() -> None:
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]
    assert drawing.FRONT_CENTER[0] < drawing.RIGHT_CENTER[0]
    assert drawing.ISO_CENTER[1] < drawing.FRONT_CENTER[1]


def test_no_geometric_control_is_specified_for_the_gear() -> None:
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")


def test_only_functional_running_surfaces_receive_roughness() -> None:
    controls = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(controls) == {"cylinder_gear_bore", "cam_follower"}
    assert controls["cylinder_gear_bore"].face.diameter_mm == spec.BORE_DIA
    assert controls["cam_follower"].face.diameter_mm == spec.CAM_DIA
    assert {control.roughness_um for control in controls.values()} == {1.6}
    assert len(controls) == len(spec.SURFACE_FINISHES)


def test_short_notes_only_define_phase_tooth_data_and_set_consistency() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.splitlines()
    assert len(lines) <= 4
    assert 2.0 * spec.ECCENTRICITY_TOLERANCE_MM > spec.SET_ECCENTRICITY_RANGE_MM
    for redundant in (
        "DATUM",
        "BASIC",
        "DEBUR",
        "MATERIAL",
        "FINISH",
        "+/-",
        "Ra ",
        "DIAMETER",
        "THICKNESS",
        "DEPTH",
    ):
        assert redundant not in notes


def test_notch_geometry_matches_first_root_counterclockwise_phase() -> None:
    assert math.isclose(
        spec.TIP_RADIUS - spec.NOTCH_FLOOR_RADIUS,
        spec.NOTCH_DEPTH,
        abs_tol=1e-12,
    )
    expected_phase = math.pi / 2.0 + math.pi / spec.TEETH
    expected_x = (
        (spec.NOTCH_FLOOR_RADIUS + spec.TIP_RADIUS)
        / 2.0
        * math.cos(expected_phase)
    )
    assert math.isclose(spec.NOTCH_CENTER_X, expected_x, abs_tol=1e-12)
    assert spec.NOTCH_CENTER_X < 0.0


def test_running_bore_limits_follow_the_finished_arbor() -> None:
    # The same bore must not be specified for arbors at opposite ends of the
    # shaft tolerance: all 20 gears are matched to the shaft actually supplied.
    small_min, small_max = spec.matched_bore_limits(9.505)
    large_min, large_max = spec.matched_bore_limits(9.525)
    assert math.isclose(small_min, 9.535, abs_tol=1e-12)
    assert math.isclose(small_max, 9.575, abs_tol=1e-12)
    assert math.isclose(large_min, 9.555, abs_tol=1e-12)
    assert math.isclose(large_max, 9.595, abs_tol=1e-12)


def test_title_block_owns_material_finish_and_general_tolerance() -> None:
    import _config

    config = _config.parts("cylinder-gear")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert int(config["quantity"]) == 20
    assert spec.FACE_WIDTH == part.FACE_WIDTH
    assert spec.CAM_THICKNESS == part.CAM_THICKNESS
