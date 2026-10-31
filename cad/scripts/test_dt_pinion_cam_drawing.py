"""Offline contracts for the pinion-lift-cam drawing."""

from __future__ import annotations

import itertools
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any
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
    # drawing-guidelines.md rule 6 (roughness symbols only where a surface
    # runs, slides or locates): the follower rides the cam OD; the set-screwed
    # bore never moves on the rod, so the one roughness symbol sits on the OD,
    # at the inch sheet's running grade.
    (control,) = dt_pinion_cam_spec.SURFACE_FINISHES
    assert control.key == "cam_od"
    assert control.roughness_um == 1.6
    assert control.display_unit == "in"
    assert control.roughness_ra == "63"
    assert control.face.diameter_mm == dt_pinion_cam_spec.CAM_OD


def test_the_package_declares_the_inch_sheet_its_drawing_prints() -> None:
    import _config
    from _drawing_units import drawing_unit

    row = _config.parts("dt-pinion-cam")
    assert drawing_unit("parts/dt-pinion-cam", row) == "in"
    assert dt_pinion_cam_spec.UNIT == "in"
    # The sheet names its own package to both the setup and the finalizer.
    assert drawing.PACKAGE == "dt-pinion-cam" == drawing.PART_STEM
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("package_name=PACKAGE") == 2


def _inch(mm: float) -> float:
    return mm / 25.4


def test_only_the_bore_moves_and_every_other_nominal_prints_rounded() -> None:
    # Owner ruling (#290 pilot, 2026-10-30): the bore alone moves onto the
    # owned .2510 reamer; the drive train's park/engage/rig geometry keeps its
    # millimetre values and the sheet prints each rounded to its own places.
    geometry = dt_pinion_cam_geometry
    assert (geometry.CAM_OD, geometry.ECC, geometry.CAM_LEN, geometry.SET_SCREW_Z) == (
        14.6,
        2.0,
        9.0,
        4.1,
    )
    assert _inch(geometry.BORE) == pytest.approx(0.2510, abs=1e-12)
    spec = dt_pinion_cam_spec
    places = spec.DRAWING_PRECISION_BY_NAME
    printed = {
        "BoreDia": spec.BORE,
        "CollarOd": spec.CAM_OD,
        "CollarCy": spec.ECC,
        "Depth": spec.CAM_LEN,
        "TapCz": spec.SET_SCREW_Z,
        "TapDrillDia": spec.TAP_DRILL_DIA,
    }
    assert {name: round(_inch(value), places[name]) for name, value in printed.items()} == {
        "BoreDia": 0.2510,
        "CollarOd": 0.575,
        "CollarCy": 0.079,
        "Depth": 0.35,
        "TapCz": 0.16,
        "TapDrillDia": 0.070,
    }


def test_every_printed_band_still_admits_the_model() -> None:
    # The off-grid model is an accepted part: each rounded print's limits
    # contain it (title-block .XX for the length and station).
    spec = dt_pinion_cam_spec
    for model, printed, band in (
        (spec.CAM_OD, 0.575, 0.002),
        (spec.ECC, 0.079, 0.002),
        (spec.CAM_LEN, 0.35, 0.01),
        (spec.SET_SCREW_Z, 0.16, 0.01),
    ):
        assert printed - band < _inch(model) < printed + band, model


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


def test_thin_side_wall_is_the_declared_owner_minor_at_the_printed_limits() -> None:
    # Rule 17 on an inch package: .080 target, .060 hard floor, judged at the
    # PRINTED limits -- OD .575 -.002, bore .2515, eccentricity .079 +.002 --
    # never at the off-grid model values.  The owner ruled the .00025 in
    # shortfall as minor RV-01; the floor stays hard.
    import _config

    spec = dt_pinion_cam_spec
    assert spec.WALL_TARGET_MM == pytest.approx(0.080 * 25.4)
    assert dt_pinion_cam_geometry.WALL_FLOOR_MM == pytest.approx(0.060 * 25.4)
    worst_in = (0.575 - 0.002) / 2.0 - (0.2510 + 0.0005) / 2.0 - (0.079 + 0.002)
    assert worst_in == pytest.approx(0.07975)
    assert spec.THIN_SIDE_WALL_MIN_MM == pytest.approx(worst_in * 25.4)
    assert spec.THIN_SIDE_WALL_MIN_MM == pytest.approx(spec.THIN_SIDE_WALL_EXCEPTION_MIN_MM)
    assert 0.080 - worst_in == pytest.approx(0.00025)
    assert worst_in - 0.060 == pytest.approx(0.01975)
    assert dt_pinion_cam_geometry.WALL_FLOOR_MM < spec.THIN_SIDE_WALL_MIN_MM
    assert spec.THIN_SIDE_WALL_MIN_MM < spec.WALL_TARGET_MM
    (exception,) = [
        entry
        for entry in _config.parts("dt-pinion-cam")["machinist_exceptions"]
        if entry["id"] == "RV-01"
    ]
    assert exception["kind"] == "minor"
    assert ".07975 in" in exception["finding"]
    assert ".00025 in" in exception["finding"]
    # No note text restates the wall: the WALL word lives only on the native
    # ThinWallMin dimension's callout.
    assert "WALL" not in spec.DRAWING_NOTES
    assert [
        name for name, text in drawing.DIMENSION_CALLOUTS.items() if "WALL" in text
    ] == ["ThinWallMin"]
    # The drive train holds the nominal to the hard floor.
    assert dt_pinion_cam_geometry.THIN_SIDE_WALL >= dt_pinion_cam_geometry.WALL_FLOOR_MM
    thick_in = (0.575 - 0.002) / 2.0 - (0.2510 + 0.0005) / 2.0 + (0.079 - 0.002)
    assert spec.THICK_SIDE_WALL_MIN_MM == pytest.approx(thick_in * 25.4)


def test_the_sheet_states_rv_01_on_a_native_min_limit_never_overstated() -> None:
    # Rule 20: the accepted shortfall is stated on the sheet by the part's own
    # dimension, a single MIN limit whose model value IS the printed limit.
    # Floored to its four places it never claims more wall than the printed
    # worst case leaves, nor less than the floor.
    spec = dt_pinion_cam_spec
    printed_in = round(spec.THIN_WALL_MIN_MM / 25.4, 6)
    assert printed_in == 0.0797
    assert round(printed_in, spec.THIN_WALL_MIN_PLACES) == printed_in
    assert (
        dt_pinion_cam_geometry.WALL_FLOOR_MM
        <= spec.THIN_WALL_MIN_MM
        <= spec.THIN_SIDE_WALL_MIN_MM
    )
    assert spec.THIN_SIDE_WALL_MIN_MM - spec.THIN_WALL_MIN_MM < 0.0001 * 25.4
    # The deliberate floor-to-print: the native nominal (2.02438 mm) sits
    # under the computed worst case (2.02565 mm), never over it, and the .060
    # floor stays hard under both.
    assert spec.THIN_WALL_MIN_MM == pytest.approx(2.02438)
    assert spec.THIN_SIDE_WALL_MIN_MM == pytest.approx(2.02565)
    assert spec.THIN_WALL_MIN_MM < spec.THIN_SIDE_WALL_MIN_MM
    # RV-01 states the same shortfall both ways, so a reviewer reading the
    # sheet's .0797 MIN meets the number the exception declares.
    import _config

    (exception,) = [
        entry
        for entry in _config.parts("dt-pinion-cam")["machinist_exceptions"]
        if entry["id"] == "RV-01"
    ]
    for text in (".07975 in (2.02565 mm)", ".0797 MIN (2.02438 mm)"):
        assert text in exception["finding"], text
    assert ".0797 MIN" in exception["where"]
    assert spec.THIN_WALL_MIN_TOL_TYPE == 5  # swTolType_e.swTolMIN
    best_in = (0.575 + 0.002) / 2.0 - 0.2510 / 2.0 - (0.079 - 0.002)
    assert spec.THIN_SIDE_WALL_MAX_MM == pytest.approx(best_in * 25.4)
    upper, lower = spec.THIN_WALL_MIN_BAND
    assert lower == 0.0
    assert spec.THIN_WALL_MIN_MM + upper == pytest.approx(spec.THIN_SIDE_WALL_MAX_MM)
    assert spec.DRAWING_DIMENSIONS["ThinWallReference"] == {"ThinWallMin"}
    # The front view, where the thin side is drawn, carries it.
    assert "ThinWallMin" in drawing.FRONT_KEEP
    assert drawing.DIMENSION_CALLOUTS["ThinWallMin"] == spec.THIN_WALL_CALLOUT


def test_the_sheet_proves_the_wall_minimum_it_imports() -> None:
    def annotation(name: str, value_mm: float, tol_type: int) -> Any:
        dimension = SimpleNamespace(
            SystemValue=value_mm / 1000.0, Tolerance=SimpleNamespace(Type=tol_type)
        )
        display = SimpleNamespace(GetDimension2=lambda _index: dimension)
        return SimpleNamespace(name=name, GetSpecificAnnotation=lambda: display)

    spec = dt_pinion_cam_spec
    adapter = SimpleNamespace()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(drawing, "_early_bound", lambda value, _interface: value)
        patch.setattr(drawing, "dimension_name", lambda _adapter, a: a.name)
        drawing._require_thin_wall_min(
            adapter, [annotation("ThinWallMin", spec.THIN_WALL_MIN_MM, 5)]
        )
        with pytest.raises(RuntimeError, match="MIN limit"):
            drawing._require_thin_wall_min(
                adapter, [annotation("ThinWallMin", spec.THIN_WALL_MIN_MM, 0)]
            )
        with pytest.raises(RuntimeError, match="does not measure"):
            drawing._require_thin_wall_min(
                adapter, [annotation("ThinWallMin", spec.THIN_SIDE_WALL_MIN_MM, 5)]
            )
        with pytest.raises(RuntimeError, match="found 0"):
            drawing._require_thin_wall_min(adapter, [])


def test_a_thinner_wall_than_rv_01_declares_is_refused(monkeypatch) -> None:
    # RV-01 covers exactly .07975 in: a wider bore band would cut the wall
    # under it and must fail the spec instead of sliding under the ruling.
    import importlib
    import sys

    import _fit_deviations

    real = _fit_deviations.deviations
    monkeypatch.setattr(
        _fit_deviations,
        "deviations",
        lambda band: (0.0, 0.0254) if band == (0.0127, 0.0) else real(band),
    )
    monkeypatch.delitem(sys.modules, "dt_pinion_cam_spec")
    with pytest.raises(AssertionError, match="RV-01"):
        importlib.import_module("dt_pinion_cam_spec")
    monkeypatch.setitem(sys.modules, "dt_pinion_cam_spec", dt_pinion_cam_spec)


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
    # U27 (Main, 2026-09-23): a set-screwed cam only slips over the rod.  #290:
    # the owned .2510 over reamer prints .2510 +.0005/.0000, and against the
    # MHA-DT-17 rod's ground h band the clearance stays inside U27's window
    # restated on the .0001-in grid (.0008-.0039 in).
    spec = dt_pinion_cam_spec
    assert _inch(spec.BORE) == pytest.approx(0.2510, abs=1e-12)
    assert tuple(_inch(d) for d in spec.BORE_BAND) == pytest.approx((0.0005, 0.0))
    assert tuple(_inch(w) for w in spec.SLIP_CLEARANCE_WINDOW_MM) == pytest.approx(
        (0.0008, 0.0039)
    )
    rod_max = dt_pinion_lift_rod_spec.ROD_DIA + dt_pinion_lift_rod_spec.ROD_DIA_BAND[0]
    rod_min = dt_pinion_lift_rod_spec.ROD_DIA + dt_pinion_lift_rod_spec.ROD_DIA_BAND[1]
    bore_min = spec.BORE + spec.BORE_BAND[1]
    bore_max = spec.BORE + spec.BORE_BAND[0]
    window = spec.SLIP_CLEARANCE_WINDOW_MM
    assert window[0] <= bore_min - rod_max <= bore_max - rod_min <= window[1]
    # The 1/4 rod's maximum is exactly .2500, so the tightest slip is .0010.
    assert _inch(bore_min - rod_max) == pytest.approx(0.0010)
    assert spec.SLIP_CLEARANCE_MIN == pytest.approx(round(bore_min - rod_max, 6))
    assert spec.SLIP_CLEARANCE_MAX == pytest.approx(round(bore_max - rod_min, 6))
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
    # The rear wall stacks length AND station, independently at .XX +/-.01 (the
    # inch sheet's two-place row; both feed this wall, so neither prints .X).
    # The unchanged 9.0 length and 4.1 station print .35 and .16, and the
    # walls are taken from those PRINTED numbers, with the thread at its .086
    # basic major: .107 in at the front, .127 in at the rear.
    from _printed_tolerance import printed_band_mm

    geometry = dt_pinion_cam_geometry
    spec = dt_pinion_cam_spec
    grade = printed_band_mm(2, unit="in")
    assert grade == pytest.approx(0.01 * 25.4)
    assert spec.DRAWING_PRECISION["Collar"]["Depth"] == 2
    assert spec.DRAWING_PRECISION["TapDrillProfile"]["TapCz"] == 2
    assert (geometry.SET_SCREW_Z, geometry.CAM_LEN) == (4.1, 9.0)
    radius = max(THREAD_MAJOR_MM[geometry.SET_SCREW_HOLE_SPEC.size], 0.086 * 25.4) / 2.0
    walls = [
        (station - radius, length - station - radius)
        for length, station in itertools.product(
            (0.35 * 25.4 - grade, 0.35 * 25.4 + grade),
            (0.16 * 25.4 - grade, 0.16 * 25.4 + grade),
        )
    ]
    assert min(front for front, _ in walls) == pytest.approx(0.107 * 25.4)
    assert min(rear for _, rear in walls) == pytest.approx(0.127 * 25.4)
    assert spec.SET_SCREW_FRONT_WALL_MIN_MM == pytest.approx(0.107 * 25.4)
    assert spec.SET_SCREW_REAR_WALL_MIN_MM == pytest.approx(0.127 * 25.4)
    assert all(min(pair) >= spec.WALL_TARGET_MM for pair in walls)


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
    # Every corner is a PRINTED limit: OD .575 +/-.002, bore .2510..2515 and
    # eccentricity .079 +/-.002.
    assert _inch(spec.COLLAR_OD_TOLERANCE_MM) == pytest.approx(0.002)
    assert _inch(spec.COLLAR_AXIS_TOLERANCE_MM) == pytest.approx(0.002)
    clearances = []
    for od, bore, eccentricity in itertools.product(
        (0.575 - 0.002, 0.575 + 0.002),
        (0.2510, 0.2515),
        (0.079 - 0.002, 0.079 + 0.002),
    ):
        rim_radius = spec.SET_SCREW_MAJOR_MAX_MM / 2.0
        outer_y = eccentricity * 25.4 + math.sqrt((od * 25.4 / 2.0) ** 2 - rim_radius**2)
        clearances.append(outer_y - bore * 25.4 / 2.0 - spec.SET_SCREW_LENGTH_MAX_MM)
    worst = min(clearances)
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

    Inch places: four on the reamed bore (its +.0005 band needs them), three
    on the banded cam OD and eccentricity (+/-.002) and the #2-56 tap drill
    (an inch drill diameter), two on the length and the tap station.  Every
    one feeds a fit, a wall or the rig stack, so none prints at the
    non-functional .X grade, and no nominal carries more places than its
    band or title-block grade.
    """
    by_name = dt_pinion_cam_spec.DRAWING_PRECISION_BY_NAME
    assert set(by_name) == set().union(*dt_pinion_cam_spec.DRAWING_DIMENSIONS.values())
    assert by_name == {
        "BoreDia": 4,
        "CollarCy": 3,
        "CollarOd": 3,
        "TapDrillDia": 3,
        "Depth": 2,
        "TapCz": 2,
        "ThinWallMin": 4,
    }
    assert min(by_name.values()) >= 2
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_bands_print_at_their_nominal_inch_places() -> None:
    # ASME inch: a plus-minus tolerance prints at its nominal's places.  The
    # bore's +.0005/.0000 needs four (and the reamer's sub-.001 band is why
    # its nominal has four); the OD's and eccentricity's .002 need three.
    from _drawing_tolerances import _tolerance_places

    spec = dt_pinion_cam_spec
    assert _tolerance_places(*spec.BORE_BAND, display_unit="in") == spec.BORE_PLACES
    od = spec.COLLAR_OD_TOLERANCE_MM
    assert _tolerance_places(-od, od, display_unit="in") == spec.COLLAR_OD_PLACES
    ecc = spec.COLLAR_AXIS_TOLERANCE_MM
    assert _tolerance_places(-ecc, ecc, display_unit="in") == spec.ECC_PLACES


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
    wall_min_mm = dt_pinion_cam_spec.THIN_WALL_MIN_MM
    adapter = SimpleNamespace(
        **{
            name: AsyncMock(return_value=success)
            for name in (
                "create_part", "create_sketch", "exit_sketch",
                "create_extrusion", "create_cut_extrude", "create_plane",
                "add_sketch_constraint",
            )
        },
        add_line=AsyncMock(return_value=SimpleNamespace(is_success=True, data="wall-line")),
        currentModel=SimpleNamespace(
            Parameter=lambda _name: SimpleNamespace(SystemValue=wall_min_mm / 1000.0)
        ),
        _sketch_entities={"tap-reference": segment, "wall-line": wall_segment},
    )
    for name in (
        "set_global", "force_rebuild", "drive_dimension", "ensure_fully_defined",
        "apply_material", "apply_color", "report_mass_properties",
        "dimension_between", "anchor_point_to_origin",
    ):
        monkeypatch.setattr(cam, name, AsyncMock())
    for name in (
        "set_dimension_symmetric_tolerance", "set_dimension_bilateral_tolerance",
        "apply_drawing_precision",
        "name_octant_views", "clear_dimensions_for_drawing",
        "mark_dimensions_for_drawing", "author_part_pmi", "apply_drawing_properties",
        "require_saved_drawing_properties", "blank_reference_geometry",
        "blank_reference_sketches", "wizard_hole_on_cylinder",
        "set_sketch_direct_db", "set_single_limit",
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
    cam.set_global.assert_any_await(adapter, "BoreDia", "6.3754mm")
    cam.drive_dimension.assert_any_await(
        adapter, "SetScrewZ@SetScrewStationPlane", '"SetScrewZ"'
    )
    reference = cam.define_circle.await_args_list[-1]
    assert reference.args[1:4] == (0.0, -4.1, 1.778 / 2.0)
    # The model owns the bands, shown in the row's inch unit at the
    # nominal's places.
    cam.set_dimension_bilateral_tolerance.assert_called_once_with(
        adapter, "BoreProfile", "BoreDia", 0.0, 0.0127, places=4, display_unit="in"
    )
    assert cam.set_dimension_symmetric_tolerance.call_args_list == [
        (
            (adapter, "CollarProfile", "CollarOd", 0.0508),
            {"places": 3, "display_unit": "in"},
        ),
        (
            (adapter, "CollarProfile", "CollarCy", 0.0508),
            {"places": 3, "display_unit": "in"},
        ),
    ]
    assert reference.kwargs["names"] == ("TapCx", "TapCz", "TapDrillDia")
    assert reference.kwargs["drives"] == (None, '"SetScrewZ"', '"TapDrillDia"')
    assert segment.ConstructionGeometry is True
    cam.blank_reference_sketches.assert_called_once_with(
        adapter, ("TapDrillProfile", "ThinWallReference")
    )
    # RV-01's wall minimum: a hidden construction line up the thin side (+Y)
    # from the bore's top, its one length dimension driven by the spec's
    # printed limit and anchored to the bore, then printed as swTolMIN.
    bore_r = dt_pinion_cam_geometry.BORE / 2.0
    adapter.add_line.assert_awaited_once_with(0.0, bore_r, 0.0, bore_r + wall_min_mm)
    assert wall_segment.ConstructionGeometry is True
    adapter.add_sketch_constraint.assert_awaited_once_with("wall-line", None, "vertical")
    cam.dimension_between.assert_awaited_once_with(
        adapter, "wall-line.start", "wall-line.end", "vertical_distance",
        wall_min_mm, "thin wall reference",
    )
    cam.anchor_point_to_origin.assert_awaited_once_with(
        adapter, "wall-line.start", 0.0, bore_r, "thin wall reference"
    )
    cam.set_global.assert_any_await(adapter, "ThinWallMin", f"{wall_min_mm}mm")
    cam.drive_dimension.assert_any_await(
        adapter, "ThinWallMin@ThinWallReference", '"ThinWallMin"'
    )
    cam.drive_dimension.assert_any_await(
        adapter, "ThinWallBore@ThinWallReference", '"BoreDia" / 2'
    )
    cam.set_single_limit.assert_called_once_with(
        adapter,
        "ThinWallReference",
        "ThinWallMin",
        limit=wall_min_mm,
        band=dt_pinion_cam_spec.THIN_WALL_MIN_BAND,
        tol_type=5,
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


class _SourcePart:
    def __init__(self, path: Path, dirty: bool = False) -> None:
        self.path = path
        self.dirty = dirty
        self.flag_reads = 0

    def GetPathName(self) -> str:
        return str(self.path)

    def GetSaveFlag(self) -> bool:
        self.flag_reads += 1
        return self.dirty


def _guarded_source(monkeypatch, tmp_path: Path) -> Path:
    source = tmp_path / "dt-pinion-cam.SLDPRT"
    source.write_bytes(b"part bytes")
    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing._telemetry, "event", lambda *_args, **_kwargs: None)
    return source


def test_the_sheet_refuses_any_write_to_its_source_part(monkeypatch, tmp_path) -> None:
    # #290 native acceptance: the drawing never saves the part.  The bytes are
    # hashed before the sheet presents the part and at every setup, save and
    # close checkpoint; both drawing calls receive the same observer.
    source = _guarded_source(monkeypatch, tmp_path)
    part = _SourcePart(source)
    checkpoint = drawing._clean_source_checkpoint(part)
    for phase in ("after_new_document", "before_drawing_save", "after_drawing_save"):
        checkpoint(phase)
    reads = part.flag_reads
    checkpoint("after_drawing_close")  # the closed handle is not dereferenced
    assert part.flag_reads == reads
    source.write_bytes(b"part bytes, resaved")
    with pytest.raises(RuntimeError, match="must never save its source part"):
        checkpoint("after_pdf_save")
    text = Path(drawing.__file__).read_text(encoding="utf-8")
    assert text.count("checkpoint=source_checkpoint") == 2


def test_the_sheet_refuses_a_dirty_or_foreign_source(monkeypatch, tmp_path) -> None:
    source = _guarded_source(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="save flag"):
        drawing._clean_source_checkpoint(_SourcePart(source, dirty=True))
    with pytest.raises(RuntimeError, match="is not"):
        drawing._clean_source_checkpoint(_SourcePart(tmp_path / "other.SLDPRT"))
