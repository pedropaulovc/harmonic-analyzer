"""Offline manufacturing contracts for the cylinder-gear drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_cylinder_gear as part
import cylinder_gear_spec as spec
import draw_cylinder_gear as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout


def _source(module: object) -> str:
    return Path(module.__file__).read_text(encoding="utf-8")


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
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.BACK_KEEP)
    assert kept == marked == {
        "BoreDia",
        "CamDia",
        "CamCy",
        "CamThickness",
        "NotchWidth",
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert set(drawing.DIMENSION_PRECISION) == marked


def test_model_dimensions_carry_the_manufacturing_tolerances() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
        ("CamProfile", "CamDia"): "*deviations(CAM_DIA_BAND)",
        ("CamProfile", "CamCy"): "ECCENTRICITY_TOLERANCE_MM",
        ("CamBoss", "CamThickness"): "CAM_THICKNESS_TOLERANCE_MM",
        ("NotchProfile", "NotchWidth"): "*deviations(NOTCH_WIDTH_BAND)",
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


def test_checked_dimensions_cover_geometry_without_named_model_dimensions() -> None:
    source = _source(drawing)
    assert source.count("_checked_edge_dimension(") == 3  # helper plus two uses
    assert "expected_mm=FACE_WIDTH" in source
    assert "expected_mm=NOTCH_DEPTH" in source
    assert 'label="gear face width"' in source
    assert 'label="alignment notch depth"' in source
    assert drawing.DIMENSION_PRECISION["BoreDia"] == 3
    assert drawing.DIMENSION_PRECISION["CamCy"] == 3


def test_views_are_aligned_and_show_hidden_orthographic_geometry() -> None:
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1] == drawing.BACK_CENTER[1]
    assert drawing.FRONT_CENTER[0] < drawing.RIGHT_CENTER[0] < drawing.BACK_CENTER[0]
    assert drawing.ISO_CENTER[1] < drawing.FRONT_CENTER[1]
    source = _source(drawing)
    for orientation in ("*Front", "*Right", "*Back", "*Isometric"):
        assert f'"{orientation}"' in source
    assert "for view in (front, right, back):" in source
    assert "set_hidden_lines_visible(adapter, view)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_no_datum_or_geometric_frame_is_authored_for_the_gear() -> None:
    source = _source(drawing)
    for forbidden in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert forbidden not in source
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")


def test_only_functional_running_surfaces_receive_roughness() -> None:
    controls = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(controls) == {"cylinder_gear_bore", "cam_follower"}
    assert controls["cylinder_gear_bore"].face.diameter_mm == spec.BORE_DIA
    assert controls["cam_follower"].face.diameter_mm == spec.CAM_DIA
    assert {control.roughness_um for control in controls.values()} == {1.6}
    drawing_source = _source(drawing)
    assert drawing_source.count("add_surface_finish(") == 2
    assert '"cylinder_gear_bore"' in drawing_source
    assert '"cam_follower"' in drawing_source
    assert "roughness_ra=" not in drawing_source
    assert "author_part_pmi(surface_finishes=SURFACE_FINISHES)" in _source(part)


def test_short_notes_only_define_phase_tooth_data_and_set_consistency() -> None:
    notes = spec.DRAWING_NOTES
    lines = notes.splitlines()
    assert 1 <= len(lines) <= 4
    assert "TOOTH FORM PER GEAR DATA." in lines
    assert "FIRST TOOTH ROOT CCW FROM CAM LOBE" in notes
    assert f"{spec.SET_ECCENTRICITY_RANGE_MM:.3f} MAX" in notes
    assert 2.0 * spec.ECCENTRICITY_TOLERANCE_MM > spec.SET_ECCENTRICITY_RANGE_MM
    assert "ACROSS THE SET" in notes
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
    actual_phase = math.atan2(
        (spec.NOTCH_FLOOR_RADIUS + spec.TIP_RADIUS) / 2.0,
        spec.NOTCH_CENTER_X,
    )
    assert math.isclose(actual_phase, expected_phase, abs_tol=1e-12)
    assert spec.NOTCH_CENTER_X < 0.0


def test_title_block_owns_material_finish_and_general_tolerance() -> None:
    import _config

    config = _config.parts("cylinder-gear")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "POLISHED BRASS"
    assert int(config["quantity"]) == 20
    assert spec.FACE_WIDTH == part.FACE_WIDTH
    assert spec.CAM_THICKNESS == part.CAM_THICKNESS
