"""Offline contracts for the pinion-lift-cam drawing."""

from __future__ import annotations

import itertools
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import dt_pinion_cam_geometry
import dt_pinion_cam_spec
import draw_dt_pinion_cam as drawing
import build_dt_pinion_cam as cam
from _buildgraph import module_deps_of
import dt_pinion_lift_rod_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    # drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the follower rides the cam OD; the set-screwed bore never moves
    # on the rod, so the one roughness symbol sits on the OD.
    (control,) = dt_pinion_cam_spec.SURFACE_FINISHES
    assert control.key == "cam_od"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == dt_pinion_cam_spec.CAM_OD
    assert control.roughness_ra == "63"  # #290: µin Ra on the inch sheet


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
    assert dt_pinion_cam_geometry.CAM_OD == 14.6


def test_thin_side_wall_is_owner_minor_rv_01_at_the_printed_limits() -> None:
    # Rule 17 on the inch sheet: .080 target, .060 floor.  At the printed
    # limits (OD .575 -.002, bore .2510 +.0005, eccentricity .079 +.002) the
    # thin side keeps .07975: owner minor RV-01, printed as .0797 MIN.
    import _config

    spec = dt_pinion_cam_spec
    worst_in = (0.575 - 0.002) / 2.0 - (0.2510 + 0.0005) / 2.0 - (0.079 + 0.002)
    assert worst_in == pytest.approx(0.07975)
    assert spec.THIN_SIDE_WALL_MIN_MM == pytest.approx(worst_in * 25.4)
    assert 0.060 < worst_in < 0.080
    assert dt_pinion_cam_geometry.THIN_SIDE_WALL >= 0.080 * 25.4
    (rv_01,) = [
        entry
        for entry in _config.parts("dt-pinion-cam")["machinist_exceptions"]
        if entry["id"] == "RV-01"
    ]
    assert rv_01["kind"] == "minor"
    # The sheet states the wall on its own native single-limit dimension,
    # floored so it never claims more than the worst case leaves.
    assert spec.THIN_WALL_MIN_MM == pytest.approx(0.0797 * 25.4)
    assert spec.THIN_WALL_MIN_MM <= spec.THIN_SIDE_WALL_MIN_MM
    assert spec.THIN_WALL_MIN_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert "ThinWallMin" in drawing.FRONT_KEEP
    assert drawing.DIMENSION_CALLOUTS["ThinWallMin"] == "THIN-SIDE WALL"
    assert "WALL" not in spec.DRAWING_NOTES


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
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
        ("CollarProfile", "CollarOd"): "COLLAR_OD_TOLERANCE_MM",
        ("CollarProfile", "CollarCy"): "COLLAR_AXIS_TOLERANCE_MM",
    }
    # U27 (Main, 2026-09-23): a set-screwed cam only slips over the rod, with
    # 0.02-0.10 diametral clearance on the MHA-DT-17 rod's h band.  #290: the
    # owned .2510 reamer, .2510 +.0005/.0000.
    assert dt_pinion_cam_spec.BORE / 25.4 == pytest.approx(0.2510)
    assert dt_pinion_cam_spec.BORE_BAND == (0.0127, 0.0)
    rod_max = dt_pinion_lift_rod_spec.ROD_DIA + dt_pinion_lift_rod_spec.ROD_DIA_BAND[0]
    rod_min = dt_pinion_lift_rod_spec.ROD_DIA + dt_pinion_lift_rod_spec.ROD_DIA_BAND[1]
    bore_min = dt_pinion_cam_spec.BORE + dt_pinion_cam_spec.BORE_BAND[1]
    bore_max = dt_pinion_cam_spec.BORE + dt_pinion_cam_spec.BORE_BAND[0]
    assert round(bore_min - rod_max, 6) == 0.0254
    assert round(bore_max - rod_min, 6) == 0.05842
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
    assert "ASME B18.3 #2-56 UNC X 3/16" in notes
    assert "FLAT-POINT SOCKET SET SCREW LOOSE" in notes
    assert len(notes.splitlines()) == 2
    tap = drawing.DIMENSION_CALLOUTS["TapDrillDia"]
    assert "#2-56 UNC" in tap
    assert "2B" not in tap  # Title block owns the default unified thread class.
    assert "THRU TO BORE" in tap
    assert "BOSS" not in tap
    assert "OPTIONAL" not in tap


def test_both_tight_collar_bands_name_the_follower_pin_they_serve() -> None:
    # Rule 4: the OD and eccentricity bands exist for the MHA-DT-25 follower
    # pin that rides the OD, so each callout names it (ENFORCE r1 blockers).
    import _config

    pin = _config.parts("dt-pinion-cam-pin")["number"]
    assert dt_pinion_cam_spec.FOLLOWER_PIN_NUMBER == pin
    for name in ("CollarOd", "CollarCy"):
        assert pin in drawing.DIMENSION_CALLOUTS[name], name


def test_od_callout_claims_the_follower_arc_the_assembly_proves() -> None:
    # ENFORCE r8: the callout's "clear of the tap" is the MHA-DT-00 layout proof,
    # not a free claim; keep the proof present while the sheet states it.
    import test_dt_drive_train_support_layout as layout

    assert drawing.DIMENSION_CALLOUTS["CollarOd"].endswith(
        "ON AN ARC CLEAR\nOF THE TAP"
    )
    assert callable(layout.test_cam_set_screw_hole_stays_clear_of_the_follower)


def test_tap_callout_points_at_the_drive_train_step_that_stakes_it() -> None:
    # Rule 23 (#1176): the stake is performed at MHA-DT-00's cam-collars-set
    # step; the pointer follows the step registry, never a typed number.
    import dt_drive_train_steps as steps

    tap = drawing.DIMENSION_CALLOUTS["TapDrillDia"]
    assert tap.endswith(f"STAKE AT ASSEMBLY PER\n{steps.step_ref('cam-collars-set')}")


def test_part_recipe_does_not_reach_the_assembly_sequence() -> None:
    # Codex P2 (#1686): the step number is sheet data; a steps import in the
    # spec would re-key the cam (and MHA-DT-00) on every step edit.
    from pathlib import Path

    import _buildgraph

    builder = Path(_buildgraph.__file__).with_name("build_dt_pinion_cam.py")
    deps = {Path(dep).stem for dep in _buildgraph.module_deps_of(builder)}
    assert "dt_pinion_cam_spec" in deps
    assert "dt_drive_train_steps" not in deps


def test_set_screw_thread_cannot_break_either_face_at_the_printed_grade() -> None:
    # The rear wall stacks length AND station, independently at .XX +/-.01:
    # #290 prints the 9.0 length and 4.1 station as .35 and .16, and both
    # worst-case walls keep the .080 in target.
    from _printed_tolerance import printed_band_mm

    geometry = dt_pinion_cam_geometry
    spec = dt_pinion_cam_spec
    grade = printed_band_mm(2, unit="in")
    assert grade == pytest.approx(0.01 * 25.4)
    assert (geometry.SET_SCREW_Z, geometry.CAM_LEN) == (4.1, 9.0)
    radius = THREAD_MAJOR_MM[geometry.SET_SCREW_HOLE_SPEC.size] / 2.0
    walls = [
        (station - radius, length - station - radius)
        for length, station in itertools.product(
            (0.35 * 25.4 - grade, 0.35 * 25.4 + grade),
            (0.16 * 25.4 - grade, 0.16 * 25.4 + grade),
        )
    ]
    front, rear = (min(side) for side in zip(*walls, strict=True))
    assert front == pytest.approx(spec.SET_SCREW_FRONT_WALL_MIN_MM)
    assert rear == pytest.approx(spec.SET_SCREW_REAR_WALL_MIN_MM)
    assert all(min(pair) >= 0.080 * 25.4 for pair in walls)


def test_supplied_screw_uses_asme_basic_length_and_full_thread_allowance() -> None:
    # Table 14 notes 6/7/11: supply nominal 3/16, basic .19, overall .18..20.
    # Full threads are not overall length. Point taper plus the explicitly
    # assumed 1.5p socket-end loss leaves only 0.018143 mm above 1.5D.
    spec = dt_pinion_cam_spec
    assert spec.SET_SCREW_LENGTH_IN == 3.0 / 16.0
    assert spec.SET_SCREW_BASIC_LENGTH_IN == 0.19
    assert spec.SET_SCREW_LENGTH_TOLERANCE_IN == 0.01
    assert spec.SET_SCREW_LENGTH_MIN_MM == pytest.approx(4.572)
    assert spec.SET_SCREW_LENGTH_MAX_MM == pytest.approx(5.08)
    major = max(dt_pinion_cam_geometry.SET_SCREW_MAJOR_DIA, 0.086 * 25.4)
    point_taper = (major - 0.039 * 25.4) / (2.0 * math.tan(math.radians(45.0)))
    socket_end_allowance = 1.5 * 25.4 / 56.0
    available = 0.18 * 25.4 - point_taper - socket_end_allowance
    required = 1.5 * major
    assert spec.SET_SCREW_POINT_TAPER_MAX_MM == pytest.approx(point_taper)
    assert spec.SET_SCREW_SOCKET_END_ALLOWANCE_MM == pytest.approx(socket_end_allowance)
    assert spec.SET_SCREW_FULL_THREAD_MIN_MM == pytest.approx(3.294742857142857)
    assert spec.SET_SCREW_FULL_THREAD_MIN_MM == pytest.approx(available)
    assert spec.SET_SCREW_FULL_THREAD_REQUIRED_MM == pytest.approx(3.2766)
    assert spec.SET_SCREW_FULL_THREAD_REQUIRED_MM == pytest.approx(required)
    assert spec.SET_SCREW_FULL_THREAD_MARGIN_MM == pytest.approx(0.018142857142857)
    assert available >= required


def test_set_screw_sits_below_the_od_in_the_heavy_side() -> None:
    geometry = dt_pinion_cam_geometry
    spec = dt_pinion_cam_spec
    assert "3/16" in spec.DRAWING_NOTES
    # Preserve the functional OD/bore/eccentricity bands; do not tighten any
    # of them to rescue screw seating. The rim sees the OD's sag, not just
    # its centre tangent. Rod clearance can only deepen the seated screw.
    assert spec.COLLAR_OD_TOLERANCE_MM == pytest.approx(0.002 * 25.4)
    assert spec.COLLAR_AXIS_TOLERANCE_MM == pytest.approx(0.002 * 25.4)
    clearances = []
    for od, bore, eccentricity in itertools.product(
        (0.573 * 25.4, 0.577 * 25.4),
        (0.2510 * 25.4, 0.2515 * 25.4),
        (0.077 * 25.4, 0.081 * 25.4),
    ):
        rim_radius = spec.SET_SCREW_MAJOR_MAX_MM / 2.0
        outer_y = eccentricity + math.sqrt((od / 2.0) ** 2 - rim_radius**2)
        clearances.append(outer_y - bore / 2.0 - spec.SET_SCREW_LENGTH_MAX_MM)
    worst = min(clearances)
    assert spec.THICK_SIDE_WALL_MIN_MM == pytest.approx(
        (0.573 / 2.0 - 0.2515 / 2.0 + 0.077) * 25.4
    )
    assert spec.SET_SCREW_SUBFLUSH_MIN_MM == pytest.approx(worst)
    assert worst > 0.87  # about 0.876 mm, including the curved OD at the rim
    # The next longer stock length would fail even before the OD sag.
    assert (0.25 + 0.01) * 25.4 > spec.THICK_SIDE_WALL_MIN_MM
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

    Inch places (#290): four on the reamed bore (its +.0005/.0000 band) and
    the .0797 MIN wall, three on the +/-.002 cam OD and eccentricity and on the
    #2-56 tap drill, two (.XX) on the length and tap station.
    """
    from _drawing_tolerances import _tolerance_places
    from _fit_deviations import deviations

    spec = dt_pinion_cam_spec
    by_name = spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*spec.DRAWING_DIMENSIONS.values())
    assert by_name == {
        "BoreDia": 4,
        "ThinWallMin": 4,
        "CollarOd": 3,
        "CollarCy": 3,
        "TapDrillDia": 3,
        "Depth": 2,
        "TapCz": 2,
    }
    printed = {
        "BoreDia": spec.BORE,
        "CollarOd": spec.CAM_OD,
        "CollarCy": spec.ECC,
        "TapDrillDia": spec.TAP_DRILL_DIA,
        "Depth": spec.CAM_LEN,
        "TapCz": spec.SET_SCREW_Z,
    }
    assert {name: round(mm / 25.4, by_name[name]) for name, mm in printed.items()} == {
        "BoreDia": 0.2510,
        "CollarOd": 0.575,
        "CollarCy": 0.079,
        "TapDrillDia": 0.070,
        "Depth": 0.35,
        "TapCz": 0.16,
    }
    # Each band prints at its nominal's places.
    assert _tolerance_places(*deviations(spec.BORE_BAND), display_unit="in") == 4
    for band in (spec.COLLAR_OD_TOLERANCE_MM, spec.COLLAR_AXIS_TOLERANCE_MM):
        assert _tolerance_places(-band, band, display_unit="in") == 3
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


def test_native_tap_identity_and_drill_come_from_one_geometry_spec() -> None:
    geometry = dt_pinion_cam_geometry
    hole = geometry.SET_SCREW_HOLE_SPEC
    assert cam.SET_SCREW_HOLE_SPEC is hole
    assert (hole.kind, hole.size, hole.end, hole.thread_class) == (
        "tapped", "#2-56", "through_next", "2B"
    )
    assert geometry.TAP_DRILL_DIA == blind_cut_dia_mm(hole) == 1.778
    assert geometry.SET_SCREW_MAJOR_DIA == THREAD_MAJOR_MM[hole.size] == 2.184
    assert cam.TAP_DRILL_DIA == dt_pinion_cam_spec.TAP_DRILL_DIA
    assert not hole.overrides_mm


@pytest.mark.asyncio
async def test_build_uses_a_native_radial_tap_and_hidden_construction_reference(
    monkeypatch,
) -> None:
    # Exercise the recipe without a COM seat. The one remaining manual cut is
    # the rod bore; the tap must be native and stop at that bore.
    success = SimpleNamespace(is_success=True, data=None)
    segment = SimpleNamespace(ConstructionGeometry=False)
    wall_segment = SimpleNamespace(ConstructionGeometry=False)
    adapter = SimpleNamespace(
        **{
            name: AsyncMock(return_value=success)
            for name in (
                "create_part", "create_sketch", "exit_sketch",
                "create_extrusion", "create_cut_extrude", "create_plane",
                "add_sketch_constraint",
            )
        },
        add_line=AsyncMock(return_value=SimpleNamespace(is_success=True, data="wall")),
        _sketch_entities={"tap-reference": segment, "wall": wall_segment},
    )
    for name in (
        "set_global", "force_rebuild", "drive_dimension", "ensure_fully_defined",
        "apply_material", "apply_color", "report_mass_properties",
        "dimension_between", "anchor_point_to_origin",
    ):
        monkeypatch.setattr(cam, name, AsyncMock())
    for name in (
        "set_dimension_symmetric_tolerance", "set_dimension_bilateral_tolerance",
        "set_single_limit", "apply_drawing_precision",
        "name_octant_views", "clear_dimensions_for_drawing",
        "mark_dimensions_for_drawing", "author_part_pmi", "apply_drawing_properties",
        "require_saved_drawing_properties", "blank_reference_geometry",
        "blank_reference_sketches", "wizard_hole_on_cylinder",
        "set_sketch_direct_db", "apply_package_model_units",
    ):
        monkeypatch.setattr(cam, name, Mock())
    monkeypatch.setattr(cam, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        cam, "SketchDims", lambda: SimpleNamespace(apply=lambda *_args: [])
    )
    monkeypatch.setattr(
        cam, "name_last_feature", Mock(side_effect=lambda _adapter, name: name)
    )
    monkeypatch.setattr(
        cam, "name_dimensions",
        Mock(side_effect=lambda _adapter, feature, names: [
            f"{name}@{feature}" for name in names
        ]),
    )
    monkeypatch.setattr(cam, "define_circle", AsyncMock(return_value="tap-reference"))
    monkeypatch.setattr(
        cam, "volume_check",
        AsyncMock(side_effect=lambda _adapter, _label, volume, _tolerance: volume),
    )
    monkeypatch.setattr(cam, "name_bore_axis", AsyncMock(return_value="Axis1"))
    monkeypatch.setattr(cam, "save_part_and_images", AsyncMock(return_value={}))

    await cam.build(adapter)

    cam.wizard_hole_on_cylinder.assert_called_once_with(
        adapter,
        dt_pinion_cam_geometry.SET_SCREW_HOLE_SPEC,
        [0.0, -(cam.ECC + cam.CAM_OD / 2.0), cam.SET_SCREW_Z],
        "heavy-side set-screw tap (#2-56)",
        name="SetScrewTap",
        point_planes=("SetScrewStationPlane", "Right Plane"),
    )
    assert adapter.create_cut_extrude.await_count == 1
    station = adapter.create_plane.await_args_list[-1].args[0]
    assert (station.mode, station.base_plane, station.offset) == (
        "offset", "Front Plane", 4.1
    )
    cam.set_global.assert_any_await(adapter, "SetScrewZ", "4.1mm")
    cam.drive_dimension.assert_any_await(
        adapter, "SetScrewZ@SetScrewStationPlane", '"SetScrewZ"'
    )
    reference = cam.define_circle.await_args_list[-1]
    assert reference.args[1:4] == (0.0, -4.1, 1.778 / 2.0)
    assert reference.kwargs["names"] == ("TapCx", "TapCz", "TapDrillDia")
    assert reference.kwargs["drives"] == (None, '"SetScrewZ"', '"TapDrillDia"')
    assert segment.ConstructionGeometry is True
    assert wall_segment.ConstructionGeometry is True
    cam.blank_reference_sketches.assert_called_once_with(
        adapter, ("TapDrillProfile", "ThinWallReference")
    )
    hidden = cam.blank_reference_geometry.call_args.args[1]
    assert ("TapDrillPlane", "PLANE") in hidden
    assert ("SetScrewStationPlane", "PLANE") in hidden
    assert "SetScrewStationPlane" not in dt_pinion_cam_spec.DRAWING_DIMENSIONS
    assert "SetScrewZ" not in dt_pinion_cam_spec.DRAWING_PRECISION_BY_NAME


def test_hidden_reference_import_and_native_note_cleanup_preserve_the_views() -> None:
    from _drawing_hidden_sketches import curate_view_dimensions

    assert drawing.curate_view_dimensions is curate_view_dimensions
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("dimensions_by_feature=DRAWING_DIMENSIONS") == 3
    assert 'redundant_note_substrings=("Tapped Hole",)' in source
    assert "expected_redundant_notes=1" in source
