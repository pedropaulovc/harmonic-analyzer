"""Offline contracts for the pinion-lift-cam drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_cam_geometry
import pinion_cam_spec
import draw_pinion_cam as drawing
import build_pinion_cam as cam
from _buildgraph import module_deps_of
from _fit_limits import REAM_SLIDE
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = pinion_cam_spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_cam_spec.BORE
    part_source = Path(cam.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bore")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-cam.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-cam.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-cam_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_cam"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert cam.DRAWING_DIMENSIONS is pinion_cam_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_cam_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.BOTTOM_KEEP)
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
    assert pinion_cam_geometry.THIN_SIDE_WALL >= 0.5
    assert pinion_cam_geometry.CAM_OD == 10.32


def test_sheet_runs_at_3_to_1_with_a_boss_showing_2_to_1_pictorial() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The boss points at -Y, so the built-in isometric hides the part's one
    # additional feature; the pictorial comes from the named FRONT-BOTTOM-RIGHT
    # octant instead, and the note must no longer excuse the hidden boss.
    assert '"*Isometric"' not in source
    assert "octant_view_name(1, -1, 1)" in source
    assert "scale=(2, 1)" in source  # the pictorial override
    assert pinion_cam_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "SLIDING FIT" not in notes
    # Only the two critical features carry a band: the reamed RUNNING bore and
    # the cam OD / eccentricity that sets the follower lift.  Everything else
    # takes the title block's general grade (cad/docs/tolerance-policy.md).
    assert model_toleranced_dimensions(cam) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
        ("CollarProfile", "CollarOd"): "COLLAR_OD_TOLERANCE_MM",
        ("CollarProfile", "CollarCy"): "COLLAR_AXIS_TOLERANCE_MM",
    }
    # The bore band is not a habit: it is the shared REAM_SLIDE fit class over
    # the Ø6.35 lift rod, re-expressed about this part's as-cut nominal.
    assert pinion_cam_spec.BORE_BAND == (
        round(pinion_cam_spec.LIFT_ROD_DIA + REAM_SLIDE[0] - pinion_cam_spec.BORE, 6),
        round(pinion_cam_spec.LIFT_ROD_DIA + REAM_SLIDE[1] - pinion_cam_spec.BORE, 6),
    )
    assert pinion_cam_spec.LIFT_ROD_NUMBER in drawing.DIMENSION_CALLOUTS["BoreDia"]
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
    assert "THROUGH THE BOSS INTO THE BORE" in notes
    source = Path(cam.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "M2.5TapDrill")' in source
    assert "TAP_DRILL_DIA" in source


def test_the_print_carries_no_gdt_and_dimensions_on_solid_edges() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # drawing-simplicity-policy rules 3-5: a set-screw boss on a collar is not
    # on the GD&T allowlist, so no datum, frame or basic dimension survives.
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "_front_end_edge(",
    ):
        assert helper not in source, helper
    assert not hasattr(pinion_cam_spec, "GEOMETRIC_TOLERANCES_MM")
    for line in ("DATUM A", "POSITION ", "AXIS C IS PARALLEL"):
        assert line not in pinion_cam_spec.DRAWING_NOTES, line
    # Each diameter is dimensioned on the view that draws it SOLID: the OD as
    # the length view's width, the boss on the boss end view, the bore on the
    # circular view (where it is then the only diagonal).
    assert set(drawing.BOTTOM_KEEP) == {"BossDia"}
    assert "CollarOd" in drawing.TOP_KEEP
    assert "BoreDia" in drawing.FRONT_KEEP
    assert "CollarOd" not in drawing.FRONT_KEEP
    assert "add_surface_finish(" in source
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].startswith("FINAL REAM THRU")
    assert "*Bottom" in source
    assert "BOSS END VIEW SCALE 2:1" in source
    assert "BOTH END FACES" in drawing.DIMENSION_CALLOUTS["CollarCy"]
    assert "BossProjection" in drawing.FRONT_KEEP
    assert "+/-0.05" not in source
    assert "BEYOND" in drawing.DIMENSION_CALLOUTS["BossProjection"]
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
