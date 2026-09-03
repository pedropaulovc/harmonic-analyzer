"""Offline contracts for the pinion-lift-cam drawing.

The cam is on the GD&T allowlist (cad/docs/drawing-simplicity-policy.md rule
3, "cams"): the print carries ONE datum (the reamed bore) and ONE position
frame (the OD axis to it) fed by the boxed basic eccentricity, one roughness
symbol on the OD the follower stud rides, and three lines of notes.
"""

from __future__ import annotations

from pathlib import Path

import pinion_cam_geometry
import pinion_cam_spec
import draw_pinion_cam as drawing
import build_pinion_cam as cam
from _buildgraph import module_deps_of
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_surface_finish_is_on_the_cam_od_only() -> None:
    # Rule 5: the OD is the cam_follower_contact face; the set-pinned bore
    # does not run on the lift rod.
    (control,) = pinion_cam_spec.SURFACE_FINISHES
    assert control.key == "od"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_cam_spec.CAM_OD
    part_source = Path(cam.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    source = _source()
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "od")' in source
    assert "roughness_ra=" not in source


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


def test_eccentricity_is_the_one_basic_dimension_feeding_the_one_frame() -> None:
    # The whole point of the cam: bore and OD are NOT concentric.  The offset
    # is a boxed BASIC dimension (rule 4) and the OD axis carries the single
    # allowlisted position frame to the bore (rule 3).
    assert "CollarCy" in drawing.FRONT_KEEP
    source = _source()
    assert source.count("set_basic_dimension(") == 1
    assert 'front_by_name["CollarCy"]' in source
    assert source.count("add_datum_feature(") == 1
    assert 'datum="B"' in source
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="position"' in source
    assert 'datums=("B",)' in source
    assert "diameter=True" in source
    assert 'tolerance=GEOMETRIC_TOLERANCES_MM["cam OD axis position"]' in source
    assert pinion_cam_spec.GEOMETRIC_TOLERANCES_MM == {"cam OD axis position": "0.10"}
    # The retired scheme: end-face / OD / boss datums, boss + tap frames.
    for gone in ('datum="A"', 'datum="C"', 'datum="D"', "_front_end_edge", "bottom_tap"):
        assert gone not in source, gone
    assert "project_part_pmi(" not in source
    assert not hasattr(pinion_cam_spec, "GEOMETRIC_CONTROLS")
    assert pinion_cam_geometry.THIN_SIDE_WALL >= 0.5
    assert pinion_cam_geometry.CAM_OD == 10.32


def test_basic_offset_carries_no_model_band_the_rest_do() -> None:
    # A boxed basic and a +/- on the same 1.40 would contradict each other, so
    # CollarCy has no model tolerance; every other marked dimension keeps its.
    assert not hasattr(pinion_cam_spec, "COLLAR_AXIS_TOLERANCE_MM")
    assert model_toleranced_dimensions(cam) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
        ("CollarProfile", "CollarOd"): "COLLAR_OD_TOLERANCE_MM",
        ("Collar", "Depth"): "COLLAR_DEPTH_TOLERANCE_MM",
        ("BossProfile", "BossDia"): "BOSS_DIA_TOLERANCE_MM",
        (
            "SetPinBossProjection",
            "BossProjection",
        ): "BOSS_PROJECTION_TOLERANCE_MM",
    }


def test_sheet_runs_at_3_to_1_with_2_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = _source()
    assert '"*Isometric"' in source
    assert "scale=(2, 1)" in source  # the isometric override
    assert "*Bottom" in source
    assert "BOSS END VIEW SCALE 2:1" in source
    assert pinion_cam_spec.ISOMETRIC_VIEW_NOTE == (
        "ISOMETRIC VIEW SCALE 2:1\n(SET-SCREW BOSS HIDDEN AT REAR)"
    )
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top, bottom):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_cam_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "NOT CONCENTRIC" in notes
    assert f"OFFSET {pinion_cam_spec.ECC:.2f}" in notes
    assert "M2.5 X 0.45" in notes
    assert "SET SCREW SUPPLIED LOOSE" in notes
    for banned in ("DATUM", "AXIS C", "POSITION", "WITHIN", "+/-", "UOS", "LINEAR", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_hole_callouts_state_the_process() -> None:
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == "REAM THRU"
    assert "BEYOND" in drawing.DIMENSION_CALLOUTS["BossProjection"]
    assert "{CAM_OD:.2f} OD" in _source()
    assert "+/-" not in "\n".join(drawing.DIMENSION_CALLOUTS.values())
    assert "BossProjection" in drawing.FRONT_KEEP


def test_cam_attachment_is_built_as_a_tapped_boss() -> None:
    source = Path(cam.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "M2.5TapDrill")' in source
    assert "TAP_DRILL_DIA" in source


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
