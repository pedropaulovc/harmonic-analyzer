"""Offline contracts for the pinion-lift-cam drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_cam_geometry
import pinion_cam_spec
import draw_pinion_cam as drawing
import build_pinion_cam as cam
from _buildgraph import module_deps_of
from _fit_limits import REAM_SLIDE
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = pinion_cam_spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_cam_spec.BORE


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-cam.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-cam.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-cam_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_cam"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert cam.DRAWING_DIMENSIONS is pinion_cam_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_cam_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.SIDE_KEEP) | set(drawing.BOTTOM_KEEP)
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
    eccentricity = drawing.DIMENSION_CALLOUTS["CollarCy"]
    assert "ECCENTRICITY" in eccentricity
    assert "BORE AXIS TO OD AXIS" in eccentricity
    assert "BOTH END FACES" not in eccentricity
    assert pinion_cam_geometry.THIN_SIDE_WALL >= 0.5
    assert pinion_cam_geometry.CAM_OD == 10.32


def test_sheet_runs_at_3_to_1_with_a_boss_showing_2_to_1_pictorial() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert pinion_cam_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "SLIDING FIT" not in notes
    # Only the critical features carry bands: the reamed RUNNING bore and the
    # cam OD / eccentricity that sets the follower lift.  Routine controlling
    # dimensions take the title-block grade; the cosmetic projection is reference.
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
    bore = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "SLIDE FIT" in bore
    assert "DIAMETRAL CLEARANCE" not in bore
    assert "LOCK AFTER POSITIONING" not in bore
    assert "LINEAR +/-" not in notes
    assert "BRASS" not in notes
    assert "X.XX" not in notes


def test_cam_attachment_is_fully_released_for_manufacture() -> None:
    notes = pinion_cam_spec.DRAWING_NOTES
    assert "RELEASE HOLD" not in notes
    assert "ISO 4026" in notes
    boss = drawing.DIMENSION_CALLOUTS["BossDia"]
    assert "COSMETIC RAISED BOSS" in boss
    assert "SIZE/SHAPE NONCRITICAL" in boss
    assert "OPTIONAL" not in boss
    assert "M2.5 X 0.45-6H THRU TO BORE" in boss
    assert "THROUGH THE BOSS" not in boss


def test_set_screw_thread_cannot_break_the_front_face_at_general_grade() -> None:
    # BOSS_Z 1.7 left 0.45 nominal wall between the M2.5 major and the front
    # face; the .X ±0.8 general grade the station prints under then permitted a
    # breakout (codex iter3 blocker).  The station is bounded above by the
    # assembly's follower-pin and spring-foot bands (build_drive_train_assembly).
    import pinion_cam_geometry as geometry

    thread_major_r = 2.5 / 2.0
    general_grade_mm = 0.8
    assert geometry.BOSS_Z - thread_major_r - general_grade_mm > 0.0


def test_the_print_carries_no_gdt_and_dimensions_on_solid_edges() -> None:
    assert not hasattr(pinion_cam_spec, "GEOMETRIC_TOLERANCES_MM")
    for line in ("DATUM A", "POSITION ", "AXIS C IS PARALLEL"):
        assert line not in pinion_cam_spec.DRAWING_NOTES, line
    # The visible boss-end view owns both boss dimensions; the collar OD stays
    # in the length view and the bore in the circular front view.
    assert set(drawing.BOTTOM_KEEP) == {"BossDia", "BossCz"}
    assert "BossCz" not in drawing.SIDE_KEEP
    assert "CollarOd" in drawing.SIDE_KEEP
    assert "BoreDia" in drawing.FRONT_KEEP
    assert "CollarOd" not in drawing.FRONT_KEEP
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].startswith("REAM THRU")
    assert "BOTH END FACES" not in drawing.DIMENSION_CALLOUTS["CollarCy"]
    assert drawing.DIMENSION_CALLOUTS["BossCz"] == "BOSS AXIS STATION"
    assert "BossProjection" in drawing.FRONT_KEEP
    assert drawing.DIMENSION_CALLOUTS["BossProjection"] == (
        "RAISED BOSS PROJECTION (REF)"
    )


def test_the_part_owns_every_printed_decimal_place() -> None:
    """Policy rule 2: the .SLDPRT owns places for every imported nominal.

    Two places serve the critical trio (the reamed running bore, the cam OD
    and the eccentricity that IS the lift); routine controls use one place and
    the cosmetic boss-projection nominal is parenthesized as reference.
    """
    by_name = pinion_cam_spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*pinion_cam_spec.DRAWING_DIMENSIONS.values())
    assert {name for name, places in by_name.items() if places != 1} == {
        "BoreDia",
        "CollarOd",
        "CollarCy",
    }
    assert max(by_name.values()) == 2
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_registry_retains_make_critical_properties() -> None:
    import _config

    spec = _config.parts("pinion-cam")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 2
