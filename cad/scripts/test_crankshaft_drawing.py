"""Offline contracts for the through-hub crankshaft drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_crankshaft as part
import crank_hub_geometry as geometry
import crankshaft_notes as notes
import crankshaft_spec as spec
import draw_crankshaft as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crankshaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crankshaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crankshaft_drawing.png")
    assert DRAWINGS_BY_NAME["crankshaft"].script == Path(drawing.__file__).resolve()




def test_policy_migrated_sheet_carries_no_gdt_and_model_owned_places() -> None:
    # Rule 3: a shaft carries no frames, datums or basic dimensions.
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
    ):
        assert helper not in source
    # Rule 2: the part authors every printed dimension's places.
    assert "draw_crankshaft.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    functional_fits = {"ShaftDiaDim", "JournalDiaDim", "PinionSeatDiaDim"}
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        assert places == (3 if name in functional_fits else 1), name
    assert spec.REFERENCE_DIMENSIONS <= marked
    assert spec.SPHERICAL_DIMENSIONS <= spec.REFERENCE_DIMENSIONS


def test_far_end_stations_restate_the_modelled_geometry() -> None:
    # The StationReference sketch drives each printed station from the same
    # globals as the features; these are the values the equations evaluate to.
    far = spec.SHAFT_LENGTH
    assert far - spec.SEAT_STEP == pytest.approx(24.1)
    # The station the spec chose prints exactly at its places.
    assert spec.PINION_SEAT_STATION == round(spec.PINION_SEAT_STATION, spec.STATION_PLACES)
    assert set(part._STATIONS) == set(part._STATION_DRIVES)
    assert set(part._STATIONS) <= spec.DRAWING_DIMENSIONS["StationReference"]
    assert far - spec.PIN_HOLE_HEIGHT == pytest.approx(123.1)
    assert far + spec.SHAFT_DOME_HEIGHT == pytest.approx(138.7)
    assert part.DOME_SPHERE_R == pytest.approx(6.6710, abs=1e-3)


def test_notes_stay_within_rule_six() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert all(len(line) <= 66 for line in lines)


def test_face_shift_preserves_every_inboard_world_station() -> None:
    # W15: the far end sits recessed inside the 16T's boss, so the length
    # follows the pinion (crank_pinion_spec), not a literal -- floored to the
    # places it prints, so the sheet's nominal is the model's (Codex P2, #892).
    pinion = spec.crank_pinion_spec
    assert spec.SHAFT_LENGTH == pytest.approx(
        pinion.floor_to_places(
            spec.SEAT_PINION + pinion.OVERALL_LENGTH - pinion.SHAFT_END_RECESS_MIN,
            pinion.SHAFT_LENGTH_PLACES,
        )
    )
    assert spec.SHAFT_LENGTH == round(spec.SHAFT_LENGTH, pinion.SHAFT_LENGTH_PLACES)
    assert spec.DRAWING_PRECISION["Shaft"]["Depth"] == pinion.SHAFT_LENGTH_PLACES
    assert spec.SHAFT_LENGTH == pytest.approx(136.7)
    assert pinion.SHAFT_END_RECESS_MIN <= spec.SHAFT_END_RECESS <= pinion.SHAFT_END_RECESS_MAX
    assert part.SEAT_PINION == spec.SEAT_PINION
    assert -183.0 + spec.POST_BORE_END == pytest.approx(-70.210494428)
    assert part.SEAT_T12 == pytest.approx(25.5)
    assert part.SEAT_PINION == pytest.approx(112.939505572)
    assert -183.0 + part.SEAT_T12 == pytest.approx(-157.5)
    assert -183.0 + part.SEAT_PINION == pytest.approx(-70.060494428)
    assert -183.0 + spec.SHAFT_LENGTH == pytest.approx(-46.3)


def test_integral_dome_is_the_only_outboard_shaft_projection() -> None:
    assert spec.SHAFT_DIA == geometry.SHAFT_DIA
    assert spec.SHAFT_DIA == pytest.approx(9.525, abs=1e-12)
    assert spec.SHAFT_DOME_HEIGHT == geometry.SHAFT_DOME_HEIGHT == 2.0
    assert geometry.SHAFT_DIA + geometry.SHAFT_DIA_BAND[0] < (
        geometry.HUB_BORE_DIA + geometry.HUB_BORE_BAND[1]
    )
    assert not hasattr(spec, "CRANK_END_NOTE")


def test_mha024_station_and_notes_belong_to_hub_and_shaft() -> None:
    assert part.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing.PIN_HOLE_SPEC is spec.PIN_HOLE_SPEC
    assert drawing._PIN_HOLE_DIA == blind_cut_dia_mm(spec.PIN_HOLE_SPEC)
    assert spec.PIN_HOLE_HEIGHT == geometry.SERVICE_PIN_STATION == pytest.approx(13.6)
    # The drill size reads first (the prefix of the native callout); the
    # matched fit, naming both mating parts, reads under it.
    assert spec.CROSS_HOLE_PROCESS == "#9 DRILL"
    callout = notes.CROSS_HOLE_CALLOUT
    assert "TAPER-REAM" in callout
    assert "LIGHT DRIVE FIT" in callout
    assert "MHA-137" in callout
    assert "MHA-024" in callout
    assert "MHA-020" not in callout


def test_shaft_end_fiducial_is_a_simple_punch_not_a_dimensioned_dimple() -> None:
    assert spec.FIDUCIAL_MODEL_DIA == geometry.FIDUCIAL_MODEL_DIA == 0.8
    assert spec.FIDUCIAL_MODEL_DEPTH == geometry.FIDUCIAL_MODEL_DEPTH == 0.2
    assert spec.SHAFT_FIDUCIAL_RADIUS == geometry.SHAFT_FIDUCIAL_RADIUS == 2.5
    assert "PUNCH FIDUCIAL MARK" in spec.DRAWING_NOTES
    assert "BY EYE" in spec.DRAWING_NOTES
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert all("Fiducial" not in name for name in marked)
    assert "DIMPLE" not in spec.DRAWING_NOTES


def test_side_view_sheet_stations_follow_the_model() -> None:
    scale = drawing.SHEET_SCALE[0]
    span = spec.SHAFT_LENGTH + spec.SHAFT_DOME_HEIGHT
    assert drawing.DOME_TIP_X == pytest.approx(
        drawing.SIDE_CENTER[0] - span * scale / 2000.0
    )
    assert drawing.FAR_END_X == pytest.approx(
        drawing.SIDE_CENTER[0] + span * scale / 2000.0
    )
    assert drawing.DOME_ROOT_X == pytest.approx(
        drawing.DOME_TIP_X + spec.SHAFT_DOME_HEIGHT * scale / 1000.0
    )
    assert drawing.PIN_X == pytest.approx(
        drawing.DOME_ROOT_X + spec.PIN_HOLE_HEIGHT * scale / 1000.0
    )


def test_horizontal_profile_and_left_end_view_are_third_angle_aligned() -> None:
    # *Right rotated -90 deg puts model +Y (far end) at paper-right and +Z up;
    # *Bottom (X right, Z up) is then the true left view, on the same axis.
    assert drawing.SIDE_VIEW_ANGLE == pytest.approx(-math.pi / 2.0)
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    end_radius = spec.SHAFT_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + end_radius < drawing.DOME_TIP_X


def test_sheet_placements_stay_inside_the_border() -> None:
    inner = (0.0127, 0.0127, 0.4191, 0.2667)  # ASME B landscape inner border
    title_block = (0.218, 0.065)  # x >= and y <=
    points = [
        drawing.END_CENTER,
        drawing.ISO_CENTER,
        drawing.HOLE_CALLOUT_XY,
        drawing.PINION_PIN_NOTE_XY,
        drawing.NOTES_XY,
        drawing.ISO_NOTE_XY,
        drawing.FINISH_SYMBOL,
        *drawing.SIDE_KEEP.values(),
        *drawing.DIAMETER_POSITIONS.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # Both dragged diameters land on the section their profile sketch starts,
    # so their axis-parallel extension lines hide under the silhouette.  The
    # Ø9.525's run from the dome root, so it sits LEFT of the cross-hole: its
    # lines then stop short of the hole the callout's leader leaves (af13c8ff8
    # leader-crosses-line).
    shaft_x = drawing.DIAMETER_POSITIONS["ShaftDiaDim"][0]
    seat_x = drawing.DIAMETER_POSITIONS["PinionSeatDiaDim"][0]
    hole_radius = drawing._PIN_HOLE_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.DOME_ROOT_X < shaft_x < drawing.PIN_X - hole_radius
    pinion_hole_left = drawing.PINION_PIN_HOLE_WINDOW[0]
    assert drawing.SEAT_STEP_X < seat_x < pinion_hole_left
    # The cross-hole callout sits right of the hole so its leader cannot run
    # near-parallel to the station extension line through the hole.
    assert drawing.HOLE_CALLOUT_XY[0] > drawing.PIN_X
    # The finish lands on the inboard running land, never on the relief.
    assert drawing._sheet_x(spec.RELIEF_END) < drawing.FINISH_PICK[0]
    assert drawing.FINISH_PICK[0] < drawing._sheet_x(spec.JOURNAL_END)
    finish_y = spec.SURFACE_FINISHES[0].face.contains_y_mm
    assert spec.RELIEF_END < finish_y < spec.JOURNAL_END


def test_integral_lands_run_in_the_restored_post_at_every_size_limit() -> None:
    import cone_pivot_post_spec as post

    bore_min = post.CRANK_BORE_DIA + post.RUNNING_BORE_BAND[1]
    bore_max = post.CRANK_BORE_DIA + post.RUNNING_BORE_BAND[0]
    shaft_min = spec.JOURNAL_DIA + spec.JOURNAL_DIA_BAND[1]
    shaft_max = spec.JOURNAL_DIA + spec.JOURNAL_DIA_BAND[0]
    assert (bore_min - shaft_max, bore_max - shaft_min) == pytest.approx((0.025, 0.075))
    assert spec.SURFACE_FINISHES[0].face.diameter_mm == spec.JOURNAL_DIA
    assert spec.JOURNAL_START < spec.RELIEF_START < spec.RELIEF_END < spec.JOURNAL_END
    assert min(spec.JOURNAL_LANDS_WORST) >= spec.JOURNAL_DIA
    assert spec.JOURNAL_END + spec.STATION_ROW < spec.POST_BORE_END
    assert spec.STEP_WEB_WORST >= spec.WEB_TARGET_MM - 1e-9
    assert spec.RELIEF_DIA + spec.STATION_ROW < shaft_min
    assert spec.RELIEF_DIA - spec.STATION_ROW > spec.SHAFT_DIA


def test_view_scales_and_linked_notes_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.VIEW_SCALE == (2, 1)
    assert drawing.ISO_SCALE == (1, 1)
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW\nSCALE 1:1"




def test_seat_step_never_pushes_the_pinion_past_its_seat_gap() -> None:
    # The pinion is set on its feeler and pinned; the step never locates it.
    # A step printed at its north limit plus a corner up to the title block's
    # R0.25 stands the bore edge off, which the seat gap's north range (the
    # range the W15 pin-wall and recess stacks carry) must hold.
    import _config

    pinion = spec.crank_pinion_spec
    assert spec.STEP_CORNER_RADIUS_MAX == _config.title_block("edge_break")["radius_mm"]
    standoff = spec.SEAT_STEP + spec.STATION_ROW + spec.STEP_CORNER_RADIUS_MAX - part.SEAT_PINION
    assert standoff == pytest.approx(spec.SEAT_STEP_STANDOFF_WORST)
    assert standoff <= pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM
    # At the pinion's own seat the step would stand it off 1.05: too far.
    at_seat = part.SEAT_PINION + spec.STATION_ROW + spec.STEP_CORNER_RADIUS_MAX
    assert at_seat - part.SEAT_PINION > pinion.SEAT_GAP_MAX_MM - pinion.SEAT_FEELER_MM
    # The seat is the pinion's bore mate, at the through shaft's size band.
    assert spec.PINION_SEAT_DIA == pinion.BORE_DIA == 9.0
    assert spec.PINION_SEAT_DIA_BAND == spec.SHAFT_DIA_BAND


def test_retention_pin_note_clears_the_profile_and_title_block() -> None:
    assert drawing.PINION_PIN_X == pytest.approx(
        drawing.DOME_ROOT_X + part.PINION_PIN_STATION_Y * drawing.SHEET_SCALE[0] / 1000.0
    )
    assert drawing.JOURNAL_END_X < drawing.PINION_PIN_X < drawing.FAR_END_X
    # The note block (top-left anchored; sized for up to 3.5 mm note text)
    # stays inside its field: right of the cross-hole callout's text, above
    # the diameter row, left of the isometric and inside the border.
    lines = drawing.CRANKSHAFT_PIN_HOLE_PROCESS.split("\n")
    height = 0.0035
    char_w, line_h = 0.8 * height, 1.7 * height
    x0, y0 = drawing.PINION_PIN_NOTE_XY
    right = x0 + char_w * max(map(len, lines))
    bottom = y0 - line_h * len(lines)
    field_x0, field_y0, field_x1, field_y1 = drawing.PINION_PIN_NOTE_FIELD
    assert field_x0 == pytest.approx(drawing.HOLE_CALLOUT_XY[0] + 0.032)
    assert field_x1 == pytest.approx(drawing.ISO_CENTER[0] - 0.012)
    assert field_y1 < 0.2667
    assert field_x0 < x0 and right < field_x1
    assert y0 <= field_y1
    # Every diameter under the note's span keeps its text below the note.
    for name, (dx, dy) in drawing.DIAMETER_POSITIONS.items():
        if dx > x0 - 0.030:
            assert bottom > dy + 0.010, name


def test_note_text_is_shifted_into_its_field_from_the_measured_box() -> None:
    # run1b-e7fd1a2ec: the note's extent INCLUDES its leader, whose tip sits on
    # the hole below the field floor, so the text is placed from its own box.
    field = (0.26, 0.17, 0.378, 0.2657)
    margin = drawing.NOTE_FIELD_MARGIN
    inside = (0.30, 0.235, 0.35, 0.25)
    assert drawing._shift_into_field(inside, field, margin) == (0.0, 0.0)
    dx, dy = drawing._shift_into_field((0.30, 0.24, 0.35, 0.2665), field, margin)
    assert dx == 0.0 and dy == pytest.approx(0.2657 - margin - 0.2665)
    dx, dy = drawing._shift_into_field((0.25, 0.20, 0.30, 0.21), field, margin)
    assert dx == pytest.approx(0.26 + margin - 0.25) and dy == 0.0
    dx, dy = drawing._shift_into_field((0.34, 0.165, 0.39, 0.18), field, margin)
    assert dx == pytest.approx(0.378 - margin - 0.39)
    assert dy == pytest.approx(0.17 + margin - 0.165)
    with pytest.raises(RuntimeError, match="over by 0.0020 wide"):
        drawing._shift_into_field((0.26, 0.20, 0.378 + 0.0, 0.21), field, margin)


def test_leader_tip_is_the_point_nearest_the_hole_and_must_land_on_it() -> None:
    window = drawing.PINION_PIN_HOLE_WINDOW
    centre = ((window[0] + window[2]) / 2.0, (window[1] + window[3]) / 2.0)
    assert centre[0] == pytest.approx(drawing.PINION_PIN_X)
    assert centre[1] == pytest.approx(drawing.SIDE_CENTER[1])
    # run1b's measured tip, 3.0 mm below the axis on the 2:1 sheet, is on it.
    tip_y = drawing.SIDE_CENTER[1] - 0.00301
    leader = (0.3004, 0.2472, 0.0, drawing.PINION_PIN_X - 0.001, tip_y, 0.0)
    tip = drawing._leader_tip(leader, centre)
    assert tip == (drawing.PINION_PIN_X - 0.001, tip_y)
    assert drawing._inside(tip, window)
    assert not drawing._inside((drawing.PINION_PIN_X, 0.20), window)
    with pytest.raises(RuntimeError, match="no leader points"):
        drawing._leader_tip((), centre)


def test_shaft_length_is_unilateral_and_printed_from_the_model() -> None:
    # W15 band (a): a long shaft would stand proud of the 16T boss, so the
    # length only comes out short, and the model's Depth carries the band.
    assert spec.SHAFT_LENGTH_BAND == (0.00, -0.40)
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Shaft", "Depth", *deviations(SHAFT_LENGTH_BAND)' in build
    assert "Depth" in spec.DRAWING_DIMENSIONS["Shaft"]
    assert "Depth" not in spec.REFERENCE_DIMENSIONS


def test_shaft_band_ruling_holds_because_the_general_tolerance_fails_both_stacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # RULING W15-SHAFT-BAND (machinist review of f0c105531 flagged the band as
    # over-specified): the unilateral +0/-0.4 is functional. With the shaft at
    # the title block's .X +/-0.8 instead, both W15 stacks fail.
    import build_drive_train_assembly as bdt

    assert spec.SHAFT_LENGTH_BAND == (0.0, -0.4)
    shaft, pinion = spec.SHAFT_LENGTH, bdt.PINION_OVERALL_LENGTH
    edge_nominal, recess_nominal = bdt.PINION_PIN_EDGE_NOMINAL_ACTUAL, bdt.PINION_RECESS_NOMINAL
    assert sum(bdt.pinion_pin_edge_stack(edge_nominal, shaft, pinion).values()) >= (
        bdt.PINION_PIN_EDGE_MIN_WORST
    )
    assert sum(bdt.pinion_recess_stack(recess_nominal, shaft, pinion).values()) >= (
        bdt.PINION_RECESS_MIN_WORST
    )
    monkeypatch.setattr(bdt, "_SHAFT_LENGTH_LIMITS", (-0.8, 0.8))
    edge = sum(bdt.pinion_pin_edge_stack(edge_nominal, shaft, pinion).values())
    recess = sum(bdt.pinion_recess_stack(recess_nominal, shaft, pinion).values())
    assert edge == pytest.approx(1.773, abs=1e-3)
    assert edge < bdt.PINION_PIN_EDGE_MIN_WORST
    assert recess == pytest.approx(-0.461, abs=1e-3)
    assert recess < bdt.PINION_RECESS_MIN_WORST






def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880: a reference sketch owns printed dimensions but no geometry, so the
    # part saves it hidden (no assembly instance renders it) and the drawing
    # shows it per view through _drawing_hidden_sketches to import them.
    build = Path(drawing.__file__).with_name("build_crankshaft.py").read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "StationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source.replace("\r\n", "\n")
    assert "StationReference" in spec.DRAWING_DIMENSIONS
