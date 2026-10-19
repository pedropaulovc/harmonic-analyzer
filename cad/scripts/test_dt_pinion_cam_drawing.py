"""Offline contracts for the pinion-lift-cam drawing."""

from __future__ import annotations

from pathlib import Path

import dt_pinion_cam_geometry
import dt_pinion_cam_spec
import draw_dt_pinion_cam as drawing
import build_dt_pinion_cam as cam
from _buildgraph import module_deps_of
import dt_pinion_lift_rod_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the follower rides the cam OD; the set-screwed bore never moves
    # on the rod, so the one roughness symbol sits on the OD.
    (control,) = dt_pinion_cam_spec.SURFACE_FINISHES
    assert control.key == "cam_od"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == dt_pinion_cam_spec.CAM_OD


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-cam.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-cam.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-cam_drawing.png")
    assert DRAWINGS_BY_NAME["dt_pinion_cam"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert cam.DRAWING_DIMENSIONS is dt_pinion_cam_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_pinion_cam_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.SIDE_KEEP) | set(drawing.BOTTOM_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.CAM_OD, drawing.ECC) == (
        dt_pinion_cam_spec.CAM_OD,
        dt_pinion_cam_spec.ECC,
    )
    assert dt_pinion_cam_spec.ECC == dt_pinion_cam_geometry.ECC


def test_drive_train_recipe_depends_on_geometry_not_drawing_notes() -> None:
    drive_train = Path(__file__).with_name("build_dt_drive_train_assembly.py")
    dependency_names = {Path(path).name for path in module_deps_of(drive_train)}
    assert "dt_pinion_cam_geometry.py" in dependency_names
    assert "build_dt_pinion_cam.py" not in dependency_names
    assert "dt_pinion_cam_spec.py" not in dependency_names


def test_eccentricity_is_dimensioned_and_called_out() -> None:
    # The whole point of the cam: bore and OD are NOT concentric, so the offset
    # must be an explicit dimension, not implied by graphical alignment.
    eccentricity = drawing.DIMENSION_CALLOUTS["CollarCy"]
    assert "ECCENTRICITY" in eccentricity
    assert "BORE AXIS TO OD AXIS" in eccentricity
    assert "BOTH END FACES" not in eccentricity
    # U27/U28: 2.0 target on the thin side, and the 1.5 floor holds at the
    # printed worst case (OD and eccentricity each +/-0.05, bore at its top).
    assert dt_pinion_cam_geometry.THIN_SIDE_WALL >= 2.0
    worst = (
        (dt_pinion_cam_geometry.CAM_OD - dt_pinion_cam_spec.COLLAR_OD_TOLERANCE_MM) / 2.0
        - (dt_pinion_cam_geometry.BORE + dt_pinion_cam_spec.BORE_BAND[0]) / 2.0
        - (dt_pinion_cam_geometry.ECC + dt_pinion_cam_spec.COLLAR_AXIS_TOLERANCE_MM)
    )
    assert worst >= 2.0  # 2.01 at the Ø6.43 bore limit
    assert dt_pinion_cam_geometry.CAM_OD == 14.6


def test_sheet_runs_at_3_to_1_with_a_set_screw_showing_2_to_1_pictorial() -> None:
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert dt_pinion_cam_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 2:1"


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = dt_pinion_cam_spec.DRAWING_NOTES
    assert "SLIDING FIT" not in notes
    # Only the critical features carry bands: the reamed RUNNING bore and the
    # cam OD / eccentricity that sets the follower lift.  Routine controlling
    # dimensions take the title-block grade.
    assert model_toleranced_dimensions(cam) == {
        ("BoreProfile", "BoreDia"): "BORE_TOLERANCE_MM",
        ("CollarProfile", "CollarOd"): "COLLAR_OD_TOLERANCE_MM",
        ("CollarProfile", "CollarCy"): "COLLAR_AXIS_TOLERANCE_MM",
    }
    # U27 (Main, 2026-09-23): a set-screwed cam only slips over the rod.  A
    # stock 6.4 reamer at +/-0.03 (the printed band is at least +/-0.025)
    # against the MHA-DT-017 rod's h band gives 0.02-0.10 diametral clearance.
    assert dt_pinion_cam_spec.BORE == 6.40
    assert dt_pinion_cam_spec.BORE_BAND == (0.03, -0.03)
    assert min(abs(d) for d in dt_pinion_cam_spec.BORE_BAND) >= 0.025
    rod_max = dt_pinion_lift_rod_spec.ROD_DIA + dt_pinion_lift_rod_spec.ROD_DIA_BAND[0]
    rod_min = dt_pinion_lift_rod_spec.ROD_DIA + dt_pinion_lift_rod_spec.ROD_DIA_BAND[1]
    bore_min = dt_pinion_cam_spec.BORE + dt_pinion_cam_spec.BORE_BAND[1]
    bore_max = dt_pinion_cam_spec.BORE + dt_pinion_cam_spec.BORE_BAND[0]
    assert round(bore_min - rod_max, 6) == 0.02
    assert round(bore_max - rod_min, 6) == 0.10
    assert dt_pinion_cam_spec.LIFT_ROD_NUMBER in drawing.DIMENSION_CALLOUTS["BoreDia"]
    bore = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "SLIP FIT" in bore
    assert "DIAMETRAL CLEARANCE" not in bore
    assert "LOCK AFTER POSITIONING" not in bore
    assert "LINEAR +/-" not in notes
    assert "BRASS" not in notes
    assert "X.XX" not in notes


def test_cam_attachment_is_fully_released_for_manufacture() -> None:
    notes = dt_pinion_cam_spec.DRAWING_NOTES
    assert "RELEASE HOLD" not in notes
    assert "ISO 4026" in notes
    tap = drawing.DIMENSION_CALLOUTS["TapDrillDia"]
    assert "M2.5 X 0.45-6H" in tap
    assert "THRU TO BORE" in tap
    assert "BOSS" not in tap
    assert "OPTIONAL" not in tap


def test_both_tight_collar_bands_name_the_follower_pin_they_serve() -> None:
    # Rule 4: the OD and eccentricity bands exist for the MHA-DT-025 follower
    # pin that rides the OD, so each callout names it (ENFORCE r1 blockers).
    import _config

    pin = _config.parts("dt-pinion-cam-pin")["number"]
    assert dt_pinion_cam_spec.FOLLOWER_PIN_NUMBER == pin
    for name in ("CollarOd", "CollarCy"):
        assert pin in drawing.DIMENSION_CALLOUTS[name], name


def test_od_callout_claims_the_follower_arc_the_assembly_proves() -> None:
    # ENFORCE r8: the callout's "clear of the tap" is the DT-000 layout proof,
    # not a free claim; keep the proof present while the sheet states it.
    import test_dt_drive_train_support_layout as layout

    assert drawing.DIMENSION_CALLOUTS["CollarOd"].endswith(
        "ON AN ARC CLEAR\nOF THE TAP"
    )
    assert callable(layout.test_cam_set_screw_hole_stays_clear_of_the_follower)


def test_tap_callout_points_at_the_drive_train_step_that_stakes_it() -> None:
    # Rule 23 (#1176): the stake is performed at MHA-DT-000's cam-collars-set
    # step; the pointer follows the step registry, never a typed number.
    import dt_drive_train_steps as steps

    tap = drawing.DIMENSION_CALLOUTS["TapDrillDia"]
    assert tap.endswith(f"STAKE AT ASSEMBLY PER\n{steps.step_ref('cam-collars-set')}")


def test_part_recipe_does_not_reach_the_assembly_sequence() -> None:
    # Codex P2 (#1686): the step number is sheet data; a steps import in the
    # spec would re-key the cam (and DT-000) on every step edit.
    from pathlib import Path

    import _buildgraph

    builder = Path(_buildgraph.__file__).with_name("build_dt_pinion_cam.py")
    deps = {Path(dep).stem for dep in _buildgraph.module_deps_of(builder)}
    assert "dt_pinion_cam_spec" in deps
    assert "dt_drive_train_steps" not in deps


def test_set_screw_thread_cannot_break_either_face_at_general_grade() -> None:
    # A 1.7 station once left 0.45 nominal wall between the M2.5 major and the
    # front face; the .X ±0.8 general grade the station prints under then
    # permitted a breakout (codex iter3 blocker).  U28 centres the screw.
    import dt_pinion_cam_geometry as geometry

    thread_major_r = 2.5 / 2.0
    general_grade_mm = 0.8
    assert geometry.SET_SCREW_Z - thread_major_r - general_grade_mm > 0.0
    assert (
        geometry.CAM_LEN - geometry.SET_SCREW_Z - thread_major_r - general_grade_mm
        > 0.0
    )


def test_set_screw_sits_below_the_od_in_the_heavy_side() -> None:
    # U28: no raised boss, so the supplied M2.5 x 5 screw must seat fully
    # inside the heavy-side wall with room to spare.
    import dt_pinion_cam_geometry as geometry

    assert "M2.5 X 5" in dt_pinion_cam_spec.DRAWING_NOTES
    assert geometry.THICK_SIDE_WALL - 5.0 >= 1.0
    assert not hasattr(geometry, "BOSS_DIA")


def test_the_print_carries_no_gdt_and_dimensions_on_solid_edges() -> None:
    assert not hasattr(dt_pinion_cam_spec, "GEOMETRIC_TOLERANCES_MM")
    for line in ("DATUM A", "POSITION ", "AXIS C IS PARALLEL"):
        assert line not in dt_pinion_cam_spec.DRAWING_NOTES, line
    # The set-screw end view owns both tapped-hole dimensions; the collar OD
    # stays in the length view and the bore in the circular front view.
    assert set(drawing.BOTTOM_KEEP) == {"TapDrillDia", "TapCz"}
    assert "TapCz" not in drawing.SIDE_KEEP
    assert "CollarOd" in drawing.SIDE_KEEP
    assert "BoreDia" in drawing.FRONT_KEEP
    assert "CollarOd" not in drawing.FRONT_KEEP
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].startswith("REAM THRU")
    assert "BOTH END FACES" not in drawing.DIMENSION_CALLOUTS["CollarCy"]
    assert "TapCz" not in drawing.DIMENSION_CALLOUTS


def test_the_part_owns_every_printed_decimal_place() -> None:
    """drawing-simplicity-policy.md `How the repository implements the guidelines`: the .SLDPRT owns places for every imported nominal.

    Two places serve the critical trio (the reamed running bore, the cam OD
    and the eccentricity that IS the lift) and the M2.5 tap drill, whose size
    is the drill's; routine controls use one place.
    """
    by_name = dt_pinion_cam_spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*dt_pinion_cam_spec.DRAWING_DIMENSIONS.values())
    assert {name for name, places in by_name.items() if places != 1} == {
        "BoreDia",
        "CollarOd",
        "CollarCy",
        "TapDrillDia",
    }
    assert max(by_name.values()) == 2
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_registry_retains_make_critical_properties() -> None:
    import _config

    spec = _config.parts("dt-pinion-cam")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 2


def test_front_view_shows_which_side_the_set_screw_enters() -> None:
    # Fable review r4 blocker: nothing tied the set-screw hole to the
    # eccentricity.  The front view keeps hidden lines so the tap drill shows
    # on the heavy side, opposite the bore offset; every other view is HLR.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "for view in (side, bottom, iso):" in source
    assert "VIEW ALONG SET-SCREW AXIS" in source
    import dt_pinion_cam_geometry as geometry
    import build_dt_pinion_cam

    # The tap plane sits on the heavy side: below the bore, where the collar
    # centre (-ECC) also lies.
    assert build_dt_pinion_cam._TAP_PLANE_Y < 0.0
    assert geometry.THICK_SIDE_WALL > geometry.THIN_SIDE_WALL
