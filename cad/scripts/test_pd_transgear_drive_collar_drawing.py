"""Offline contracts for the transgear drive collar (MHA-PD-22) and its drawing."""

from __future__ import annotations

import importlib.util
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import _config
import build_pd_transgear_drive_collar as part
import draw_pd_transgear_drive_collar as drawing
import paper_drive_geom
import pd_paper_drive_assembly_steps as steps
import pd_transgear_drive_collar_spec as spec
import pd_transgear_knob_shaft_spec as shaft
import pd_vn_transgear_collar_flat_pin_spec as flat_pin
import _sprocket_seat_geometry as removable
from _assembly_contract import assembly_contract
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _printed_tolerance import printed_band_mm

# Default-format note text, measured on r743-rocker-fix3's render, as
# test_paper_drive_assembly_drawing and test_channel_assembly_drawing use them.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045
BORDER = 0.0127
# This sheet's dimension text, measured on the r4/r5 renders
# (20261111T234324465Z, snapshot 673d5e6c7a0d): callout rows print 2.58-2.76
# mm a character ("CREST DRIVES MHA-PD-08" 56.7 mm, "PERMANENT PAIR" 38.6
# mm) and ".118 ±.002" 22.6 mm; a vertical dimension's outside text block ends
# at its dimension line.  The end view's drawn outline stands 5.6 mm outside
# its O.D.; its 2X dowel callout's longest row is centred on its text point.
DIM_CHAR_WIDTH = 0.00266
CENTRE_TEXT_WIDTH = 0.0226
END_VIEW_RIGHT = drawing.END_CENTER[0] + drawing.HALF_OD + 0.0056


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-drive-collar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-drive-collar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-transgear-drive-collar_drawing.png")
    row = DRAWINGS_BY_NAME["pd_transgear_drive_collar"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert row.artifact_stem == part.PART_NAME
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_prints_in_exactly_one_view() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.SIDE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.SIDE_KEEP)
    kept = set(drawing.END_KEEP) | set(drawing.SIDE_KEEP)
    assert set(drawing.DIMENSION_CALLOUTS_BELOW) <= kept
    assert not hasattr(drawing, "DIMENSION_CALLOUTS_ABOVE")


def test_turned_diameters_and_lengths_print_on_the_side_view() -> None:
    # drawing-guidelines.md rule 11 (turned parts read like the lathe): the turned outline and fitted lengths print on the axial cut.
    body = spec.DRAWING_DIMENSIONS["BodyProfile"]
    assert body == {"CollarDia", "CollarLength", "PilotDia", "PilotLength"}
    assert body <= set(drawing.SIDE_KEEP)
    assert spec.OVERALL_LENGTH == pytest.approx(spec.LENGTH + spec.PILOT_LENGTH)
    # Both lengths share one row under the section; the native "SECTION A-A"
    # caption is moved under the row's dimension line (machinist review of
    # bcdc09b35: the line struck "SECTION"); the overall reads above.
    rows = {drawing.SIDE_KEEP[n][1] for n in ("CollarLength", "PilotLength")}
    assert len(rows) == 1
    (row,) = rows
    view_bottom = drawing.SIDE_CENTER[1] - drawing.HALF_OD
    assert view_bottom - 0.016 < row < view_bottom
    assert drawing.SECTION_CAPTION_XY[1] < row - 0.012
    assert drawing.SECTION_CAPTION_XY[1] - 0.015 > drawing.NOTES_XY[1]
    assert drawing.OVERALL_TEXT_XY[1] > drawing.SIDE_CENTER[1] + drawing.HALF_OD
    # The pilot's length text stands right of its own short span.
    assert drawing.SIDE_KEEP["PilotLength"][0] > drawing._PILOT_X + 0.0145
    # Both diameters read right of the pilot face, the O.D. outboard.
    assert drawing.SIDE_KEEP["CollarDia"][0] > drawing.SIDE_KEEP["PilotDia"][0] + 0.026
    assert drawing.SIDE_KEEP["PilotDia"][0] > drawing._PILOT_X
    # The flat pin's ream reads below the axis.  Its size line (value, band,
    # process, REF depth) and mate rows stand below the ream as one block
    # ending at its dimension line, clear of the end view's outline, above the
    # length row and under the centre's text.
    hole_r = spec.FLAT_PIN_HOLE_DIA * drawing._S / 2000.0
    dia_x, dia_y = drawing.SIDE_KEEP["FlatPinDia"]
    size_row = "Ø.0615 +.0005" + drawing.DIMENSION_SUFFIXES["FlatPinDia"].replace(
        "<HOLE-DEPTH>", "D"
    )
    rows = [size_row, *drawing.DIMENSION_CALLOUTS_BELOW["FlatPinDia"].splitlines()]
    # Its widest rows, measured on run 20261117T123054105Z: the size row
    # 63.9 mm (Ø to ")"), a 27-character mate row 63.6 mm.  Longer rows
    # need a new measurement.  The two spaces of ink air ending every row
    # print 1.3 mm each, and the block's widest row ends at the line.
    assert max(len(r.rstrip()) for r in rows) <= 27
    block = 0.0639 + 2 * 0.0013
    assert dia_x - block > END_VIEW_RIGHT + 0.002
    # The block centres on its text point; the stacked size row's top prints
    # 5.6 mm above it (run 20261117T122426763Z) and stands clear under the
    # ream's lower witness, which struck "(.163)" there.
    assert dia_y + 0.0056 < drawing._FLAT_PIN_Y - hole_r - 0.0005
    assert dia_y - len(rows) * NOTE_LINE_PITCH > row + NOTE_LINE_PITCH
    # The centre's span crosses the size's: its dimension line stands between
    # the rear face and where the size's witnesses start, so neither crosses
    # the other's witness; its text reads above the axis, over the size's
    # block, under the rear break's witnesses and 2 mm right of that break's
    # dimension line, whose lower arrow runs down past its span.
    centre_x, centre_y = drawing.SIDE_KEEP["FlatPinCentre"]
    assert drawing._REAM_RUN_X + 0.001 < centre_x < drawing._REAR_X - 0.001
    assert dia_x < drawing._REAM_RUN_X - 0.002
    assert drawing.SIDE_CENTER[1] + 0.003 < centre_y < drawing._BORE_EDGE_Y - 0.0028
    assert dia_y + 3.5 * NOTE_LINE_PITCH < centre_y - 0.002
    break_x, break_y = drawing.SIDE_KEEP["RearBreak"]
    assert centre_x - CENTRE_TEXT_WIDTH > break_x + 0.002
    # The floor station's text stands outside left of its span, between the
    # floor's and the rear face's witnesses.
    floor_x, floor_y = drawing.SIDE_KEEP["FlatPinFloor"]
    floor_half = len(".08") * DIM_CHAR_WIDTH / 2.0
    assert drawing._REAR_X + 0.001 < floor_x - floor_half
    assert floor_x + floor_half < drawing._FLAT_PIN_FLOOR_X - 0.001
    assert row + NOTE_LINE_PITCH < floor_y < view_bottom - 0.002
    # The rear break's one-line text and its two mate rows stand up and left
    # of the +Y mouth as one block ending at its dimension line, in air left
    # of the rear face, under the overall reference's row; the rows clear the
    # break's own witnesses below them.
    break_text = f".008±.002{drawing.DIMENSION_SUFFIXES['RearBreak']}"
    break_rows = drawing.DIMENSION_CALLOUTS_BELOW["RearBreak"].splitlines()
    block = max(len(break_text), *map(len, break_rows)) * DIM_CHAR_WIDTH
    assert break_x < drawing._REAR_X - 0.003
    assert break_x - block > END_VIEW_RIGHT + 0.002
    assert drawing._BORE_EDGE_Y + 0.008 < break_y < drawing.OVERALL_TEXT_XY[1] - NOTE_LINE_PITCH
    rim_y = drawing._BORE_EDGE_Y + spec.REAR_BREAK * drawing._S / 1000.0
    assert break_y - (len(break_rows) + 0.5) * NOTE_LINE_PITCH > rim_y + 0.001


def _segments_cross(a, b, c, d) -> bool:
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def _through_centre(text, centre, radius):
    """A SolidWorks diameter leader: text to the far rim through the centre."""
    angle = math.atan2(text[1] - centre[1], text[0] - centre[0])
    return text, (centre[0] - radius * math.cos(angle), centre[1] - radius * math.sin(angle))


def _clearance(segment, point) -> float:
    (x0, y0), (x1, y1) = segment
    t = ((point[0] - x0) * (x1 - x0) + (point[1] - y0) * (y1 - y0)) / (
        (x1 - x0) ** 2 + (y1 - y0) ** 2
    )
    t = min(1.0, max(0.0, t))
    return math.dist((x0 + t * (x1 - x0), y0 + t * (y1 - y0)), point)


def test_end_view_texts_stay_inside_the_left_border() -> None:
    """The end view sits 5 mm left of its old place to make room for the
    section's flat-pin block; its dowel callout and pin locations still clear
    the sheet's left border."""
    dowel_x, _ = drawing.END_KEEP["PinPosDia"]
    rows = drawing.DIMENSION_CALLOUTS_BELOW["PinPosDia"].splitlines()
    assert dowel_x - max(map(len, rows)) * DIM_CHAR_WIDTH / 2.0 > BORDER + 0.002
    for name in ("PinPosY", "PinNegY"):
        x, _ = drawing.END_KEEP[name]
        assert x - len(".2756±.0009") * DIM_CHAR_WIDTH / 2.0 > BORDER + 0.002, name


def test_end_view_leaders_run_straight_in_without_crossing() -> None:
    """Farm run 20261009T224545531Z: each diameter leader runs from the near
    end of its text through the centre to the far rim, so the bore's crossed
    the upper pin hole and the (+Y) pin's crossed the bore."""
    cx, cy = drawing.END_CENTER
    bore_r = spec.BORE_DIA * drawing._S / 2000.0
    hole_r = spec.PIN_HOLE_DIA * drawing._S / 2000.0
    upper = (cx, cy + drawing.PIN_R)  # PinPosDia dimensions the +Y hole
    lower = (cx, cy - drawing.PIN_R)
    bore_x, bore_y = drawing.END_KEEP["BoreDia"]
    pin_x, pin_y = drawing.END_KEEP["PinPosDia"]
    for start in (bore_x - drawing._BORE_TEXT_HALF, bore_x):
        bore = _through_centre((start, bore_y), (cx, cy), bore_r)
        for hole in (upper, lower):
            assert _clearance(bore, hole) > hole_r
        for pin_start in (pin_x + drawing._PIN_TEXT_HALF, pin_x):
            pin = _through_centre((pin_start, pin_y), upper, hole_r)
            assert not _segments_cross(*bore, *pin)
            assert _clearance(pin, (cx, cy)) > bore_r
    # Neither text stands across section line A (x = centre) from its leader.
    assert bore_x - drawing._BORE_TEXT_HALF > cx + drawing.HALF_OD
    assert pin_x + drawing._PIN_TEXT_HALF < cx
    # Negative control: the run's pin leader left its text's near end at
    # about (108, 122) mm on the sheet and crossed the bore.
    run7_pin = _through_centre((0.108, 0.122), upper, hole_r)
    assert _clearance(run7_pin, (cx, cy)) < bore_r


def test_the_round_bore_and_the_flat_pin_ream_are_the_marked_sizes() -> None:
    assert spec.DRAWING_DIMENSIONS["BoreProfile"] == {"BoreDia"}
    assert "BoreDia" in drawing.END_KEEP
    assert spec.DRAWING_DIMENSIONS["FlatPinProfile"] == {
        "FlatPinDia", "FlatPinCentre", "FlatPinFloor"
    }
    assert spec.DRAWING_DIMENSIONS["FlatPinProfile"] <= set(drawing.SIDE_KEEP)
    # The bore is the #11 drill at the DRILLED HOLES row; the shaft's core is
    # turned to fit it and modelled line to line with it.
    assert spec.BORE_DRILL == "#11"
    assert spec.BORE_DIA == pytest.approx(0.191 * 25.4) == shaft.CORE_DIA
    assert spec.BORE_DIA_BAND == pytest.approx((0.004 * 25.4, 0.0))
    assert spec.FLAT_PIN_HOLE_DIA == pytest.approx(0.0615 * 25.4)
    assert spec.FLAT_PIN_CENTRE == pytest.approx(0.118 * 25.4)
    assert spec.FLAT_PIN_FLOOR == pytest.approx(0.08 * 25.4)
    # The pin as modelled is the catalogue pin faced flush with the model's
    # nominal rear face.
    assert spec.FLAT_PIN_LENGTH == pytest.approx(spec.LENGTH - spec.FLAT_PIN_FLOOR)
    assert spec.FLAT_PIN_LENGTH < flat_pin.LENGTH
    # The ream breaks into the bore: the crest stands inside it.
    assert spec.FLAT_PIN_CENTRE - flat_pin.DIA / 2.0 < spec.BORE_DIA / 2.0


def _fresh_collar_spec():
    fresh_spec = importlib.util.spec_from_file_location("_collar_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_fits_refuse_round_and_crest_binding_independently(monkeypatch) -> None:
    """Both fits are made by feel on MHA-PD-08; the shaft's analysis bands
    must be this collar's sizes less the fitted air, and each fitted air
    must leave the feel .001 to land in."""
    inch = 25.4
    assert _fresh_collar_spec().BORE_CORE_CLEARANCE == pytest.approx(
        (0.0005 * inch, 0.0023 * inch)
    )
    monkeypatch.setattr(shaft, "CORE_DIA_BAND", (0.030, 0.0))
    with pytest.raises(AssertionError, match="core analysis band is not"):
        _fresh_collar_spec()
    monkeypatch.undo()
    monkeypatch.setattr(shaft, "CORE_FIT_CLEARANCE", (0.0127, 0.030))
    monkeypatch.setattr(shaft, "CORE_DIA_BAND", (max(spec.BORE_DIA_BAND) - 0.0127, -0.030))
    with pytest.raises(AssertionError, match="fit by feel has no .001 to land in"):
        _fresh_collar_spec()
    monkeypatch.undo()
    monkeypatch.setattr(shaft, "CORE_FLAT_BAND", (0.040, 0.0))
    with pytest.raises(AssertionError, match="flat analysis band is not"):
        _fresh_collar_spec()
    monkeypatch.undo()
    crest_low, crest_high = spec.FLAT_PIN_CREST_LIMITS
    monkeypatch.setattr(shaft, "CORE_FLAT_FIT_AIR", (0.0, 0.010))
    monkeypatch.setattr(
        shaft,
        "CORE_FLAT_BAND",
        (crest_high - shaft.CORE_FLAT_FROM_AXIS, crest_low - 0.010 - shaft.CORE_FLAT_FROM_AXIS),
    )
    with pytest.raises(AssertionError, match="fitted crest air is negative or under .001"):
        _fresh_collar_spec()


def test_round_stud_must_pass_the_flat_pin_crest(monkeypatch) -> None:
    assert spec.STUD_FLAT_PIN_AIR == pytest.approx(0.0031 * 25.4)
    monkeypatch.setattr(shaft, "THREAD_BLANK_LIMITS", (4.30, 4.40))
    with pytest.raises(AssertionError, match="stud cannot pass"):
        _fresh_collar_spec()


def test_the_flat_pin_crest_drives_the_core_flat_with_bounded_play() -> None:
    inch = 25.4
    assert spec.FLAT_PIN_CREST_LIMITS == pytest.approx((0.08465 * inch, 0.08875 * inch))
    # The flat is milled last until the collar slides on: the air is what
    # that trial leaves (two .001 cuts), not a stack of printed bands.
    assert spec.FLAT_PIN_CREST_CLEARANCE == pytest.approx((0.0, 0.002 * inch))
    assert spec.FLAT_PIN_CREST_CLEARANCE == shaft.CORE_FLAT_FIT_AIR
    # Over half the pin lies in its ream at the drilled bore's largest radius.
    assert spec.FLAT_PIN_RETAINED_MARGIN == pytest.approx(0.0185 * inch)
    # The pin's front end stands on the core's flat over a real length at
    # every corner of the fitted body, floor, pin and core-front bands, behind
    # the rear break's relief of its crest.
    assert spec.FLAT_PIN_CORE_ENGAGEMENT_MIN == pytest.approx(0.03623 * inch, abs=1e-4)
    nominal = spec.flat_pin_core_engagement(
        spec.LENGTH, spec.FLAT_PIN_FLOOR, spec.FLAT_PIN_LENGTH, shaft.CORE_FRONT_FROM_F
    )
    assert nominal > spec.FLAT_PIN_CORE_ENGAGEMENT_MIN
    # Negative control: a floor at the rear face puts the pin behind F.
    assert spec.flat_pin_core_engagement(
        spec.LENGTH, spec.LENGTH, spec.FLAT_PIN_LENGTH, shaft.CORE_FRONT_FROM_F
    ) <= 0.0
    # Lost motion: square at zero clearance, growing as the crest backs off.
    flat = shaft.CORE_FLAT_FROM_AXIS
    pin_r = flat_pin.DIA / 2.0
    assert spec.flat_pin_play_deg(flat + pin_r, pin_r, flat) == pytest.approx(0.0)
    assert spec.FLAT_PIN_PLAY_DEG == pytest.approx((0.0, 10.65), abs=0.01)
    # Never more than RV-04 accepted when the flat carried a printed band.
    assert max(spec.FLAT_PIN_PLAY_DEG) < spec.FLAT_PIN_PLAY_ACCEPTED_DEG == 17.2
    assert spec.FLAT_PIN_CONTACT_EDGE_MARGIN == pytest.approx(0.2497, abs=1e-4)  # .0098


def test_the_flat_pin_centre_takes_the_shop_row_for_a_reamed_location() -> None:
    # drawing-guidelines.md's row for a reamed hole's location is ±.002: the
    # centre carries it, and the flat fitted to the crest never leaves the
    # crest in the flat.
    assert spec.FLAT_PIN_CENTRE == pytest.approx(0.118 * 25.4)
    assert spec.FLAT_PIN_CENTRE_TOL == pytest.approx(0.002 * 25.4)
    assert min(spec.FLAT_PIN_CREST_CLEARANCE) >= 0.0


def test_the_rear_break_lifts_the_pin_crest_off_the_root_corner() -> None:
    """Within the shaft's largest root corner of F, its corner reaches the
    neck's largest radius plus that corner, both runouts and the whole float;
    the rear break's cone, at its smallest leg and steepest angle, stands the
    crest clear of it.  Without the break the crest meets it exactly."""
    reach = (
        shaft.FRONT_RELIEF_DIA_MAX / 2.0 + shaft.FRONT_CORNER_RADIUS_MAX
        + (shaft.CORE_TOTAL_RUNOUT + shaft.FRONT_RELIEF_TOTAL_RUNOUT) / 2.0
        + spec.ROUND_FIT_FLOAT_MAX
    )
    bore_r_min = spec.BORE_DIA / 2.0 + min(spec.BORE_DIA_BAND) / 2.0
    cone_r = spec.rear_break_radius(
        shaft.FRONT_CORNER_RADIUS_MAX, bore_r_min, min(spec.REAR_BREAK_LIMITS),
        max(spec.REAR_BREAK_ANGLE_LIMITS),
    )
    assert cone_r > min(spec.FLAT_PIN_CREST_LIMITS)
    assert spec.FLAT_PIN_CREST_CORNER_AIR_MIN == pytest.approx(cone_r - reach)
    assert spec.FLAT_PIN_CREST_CORNER_AIR_MIN == pytest.approx(0.2466, abs=1e-4)  # .0097
    # Negative control: the bare crest, no break cone, has no air there.
    assert min(spec.FLAT_PIN_CREST_LIMITS) - reach <= 1e-9


def test_the_rear_break_ends_inside_the_neck() -> None:
    # The break takes the title block's ±.005 (fit audit 2026-11-23, pending
    # owner confirmation).  Its .013 leg at 44°, the widest and shallowest,
    # ends .0135 in: inside the neck's widest .021, so the bore's support on
    # the core, counted from that width, is whole.
    assert spec.REAR_BREAK == pytest.approx(0.008 * 25.4)
    assert spec.REAR_BREAK_TOL == pytest.approx(printed_band_mm(3, unit=spec.UNIT))
    assert spec.REAR_BREAK_DEPTH_MAX == pytest.approx(0.3419, abs=1e-4)  # .0135
    assert spec.REAR_BREAK_DEPTH_MAX <= shaft.FRONT_RELIEF_WIDTH_MAX
    # The widest, shallowest cone from the largest drilled bore reaches down
    # to the lowest crest .0268 in from F; the pin bears on the flat only
    # behind it, past the neck's widest .021.
    bore_r_max = spec.BORE_DIA / 2.0 + max(spec.BORE_DIA_BAND) / 2.0
    assert spec.rear_break_radius(
        spec.FLAT_PIN_CREST_RELIEF_MAX, bore_r_max, max(spec.REAR_BREAK_LIMITS),
        min(spec.REAR_BREAK_ANGLE_LIMITS),
    ) == pytest.approx(min(spec.FLAT_PIN_CREST_LIMITS))
    assert spec.FLAT_PIN_CREST_RELIEF_MAX == pytest.approx(0.02677 * 25.4, abs=1e-4)
    assert spec.FLAT_PIN_CREST_RELIEF_MAX > shaft.FRONT_RELIEF_WIDTH_MAX


def test_the_knob_reversal_play_costs_a_fraction_of_a_millimetre_of_paper() -> None:
    """RV-04 states the stack: both ways at the knob, through 15:150 to the
    feed sleeve, and on the feed pinion's pitch circle on the rack."""
    knob = spec.KNOB_REVERSAL_PLAY_DEG
    assert knob == pytest.approx(2.0 * max(spec.FLAT_PIN_PLAY_DEG))
    sleeve = knob * paper_drive_geom.GEAR_RATIO
    paper = math.pi * paper_drive_geom.FEED_PITCH_DIA * sleeve / 360.0
    assert (knob, sleeve, paper) == pytest.approx((21.31, 2.13, 0.18), abs=0.01)
    ruling = next(
        r for r in _config.parts(part.PART_NAME)["machinist_exceptions"] if r["id"] == "RV-04"
    )
    assert ruling["kind"] == "accept"
    stated = f"{ruling['finding']} {ruling['reason']}"
    for figure in (
        f"±{max(spec.FLAT_PIN_PLAY_DEG):.0f}°",
        f"{knob:.0f}°",
        f"{sleeve:.1f}°",
        f"{paper:.2f} mm",
    ):
        assert figure in stated, figure


def test_the_flat_pin_ream_keeps_its_walls_and_stays_in_the_body() -> None:
    # The web to the -Y drive-pin hole is the one shortfall: over the floor,
    # printed as a MIN note; the O.D. and pilot-shoulder walls meet target.
    assert spec.FLAT_PIN_WEB_WORST == pytest.approx(0.075 * 25.4)
    assert spec.WALL_FLOOR <= spec.FLAT_PIN_WEB_WORST < spec.WALL_TARGET_MM
    assert f"{_in(spec.FLAT_PIN_WEB_WORST)} MIN" in spec.DRAWING_NOTES
    assert spec.FLAT_PIN_OD_WALL_WORST >= spec.WALL_TARGET_MM
    assert spec.FLAT_PIN_SHOULDER_WALL_WORST >= spec.WALL_TARGET_MM
    # The drill point stays behind the front face and the pressed pin's rear
    # end inside the supplied body.
    assert spec.FLAT_PIN_DRILL_TIP_MIN > 0.0
    assert spec.FLAT_PIN_BLANK_INSET_MIN >= 0.0


def test_a_larger_flat_pin_ream_is_refused_at_the_drive_pin_web(monkeypatch) -> None:
    monkeypatch.setattr(flat_pin, "PRESS_HOLE_DIA", 3.0)
    with pytest.raises(AssertionError, match="flat-pin hole to drive-pin hole"):
        _fresh_collar_spec()


def test_fits_carry_named_bands_and_the_lengths_print_their_places() -> None:
    # Fit audit 2026-11-23: the drilled bore takes the DRILLED HOLES row, the
    # reamed pin holes print their reamer size with no band (their dowels are
    # the gauges) and the drive-pin offsets are REF targets, so none carries a
    # native tolerance.
    assert model_toleranced_dimensions(part) == {
        ("BodyProfile", "CollarDia"): "*deviations(OD_BAND)",
        ("FlatPinProfile", "FlatPinCentre"): "FLAT_PIN_CENTRE_TOL",
    }
    # The seat O.D. and the drive-pin layout are the crank spigot's, so the
    # removable wheels fit either shaft.
    assert spec.OD == removable.SEAT_SPIGOT_DIA
    assert spec.PIN_CIRCLE_RADIUS == removable.PIN_CIRCLE_RADIUS
    assert spec.PIN_HOLE_DIA == removable.DRIVE_PIN_HOLE_DIA
    assert spec.DRAWING_PRECISION_BY_NAME["CollarLength"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosY"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["FlatPinDia"] == 4
    assert spec.DRAWING_PRECISION_BY_NAME["FlatPinCentre"] == 3
    # The floor station takes the title block's .XX row: over .07-.09 the
    # drill point stays in the body, the pilot-shoulder wall holds the .080
    # target and the pin still bears on the core.
    assert spec.DRAWING_PRECISION_BY_NAME["FlatPinFloor"] == 2
    assert spec.FLAT_PIN_FLOOR_LIMITS == pytest.approx((0.07 * 25.4, 0.09 * 25.4))
    assert spec.FLAT_PIN_DRILL_TIP_MIN > 0.0
    assert spec.FLAT_PIN_SHOULDER_WALL_WORST >= spec.WALL_TARGET_MM
    assert spec.FLAT_PIN_CORE_ENGAGEMENT_MIN > 0.0
    assert spec.FLAT_PIN_BLANK_INSET_MIN >= 0.0
    assert spec.DRAWING_PRECISION_BY_NAME["RearBreak"] == 3


def test_every_tight_band_names_its_registered_mate_at_its_callout() -> None:
    """drawing-guidelines.md rule 4: the mate's drawing number prints at the
    callout itself or in the numbered note it links to; a location dimension
    carries only its value and band (rule 7)."""
    mates = {
        "BoreDia": "pd-transgear-knob-shaft",
        "PinPosDia": "pd-vn-transgear-knob-drive-pin",
        "PilotDia": "pd-transgear-removable",
        "CollarDia": "pd-transgear-removable",
        "FlatPinDia": "pd-vn-transgear-collar-flat-pin",
        "RearBreak": "pd-transgear-knob-shaft",
    }
    for name, stem in mates.items():
        callout = " ".join(drawing.DIMENSION_CALLOUTS_BELOW[name].split())
        assert _config.parts(stem)["number"] in callout, name
    # The pressed pin is the collar's for good: its pin and fit, then the
    # linked gauge note (rule 7).  Why it is tight is the registry's.
    pin_rows = [row.rstrip() for row in drawing.DIMENSION_CALLOUTS_BELOW["FlatPinDia"].splitlines()]
    assert pin_rows == [
        f"PRESS FIT, PIN {spec.FLAT_PIN_NUMBER}", f"SEE NOTE {spec.REAM_NOTE}"
    ]
    # rule 16: the package declares the pin permanent, in the part notes.
    assert f"PERMANENT PIN {spec.FLAT_PIN_NUMBER}" in spec.DRAWING_NOTES
    shaft_number = _config.parts("pd-transgear-knob-shaft")["number"]
    # Rule 26: size, process, depth.  The ream's process follows the value on
    # its line, as the sheet's other reams read, then its depth: a REF from the
    # section's nominal fitted rear face, the .XX floor controlling.  The depth
    # symbol marks it blind.
    depth = spec.LENGTH - spec.FLAT_PIN_FLOOR
    assert depth == pytest.approx(0.163 * 25.4)
    assert drawing.DIMENSION_SUFFIXES["FlatPinDia"] == " REAM <HOLE-DEPTH> (.163)  "
    assert all("REAM" not in row for row in pin_rows)
    # The block hangs left of its own dimension line, whose arrowhead the
    # widest row's last glyph met (run 20261117T123054105Z): every printed row
    # ends in two spaces of ink air.
    printed = (
        *drawing.DIMENSION_CALLOUTS_BELOW["FlatPinDia"].splitlines(),
        drawing.DIMENSION_SUFFIXES["FlatPinDia"],
    )
    assert all(row.endswith("  ") for row in printed)
    # The drilled bore names its drill, then the mate made to fit it: no
    # range prints on either sheet.
    bore_rows = drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].splitlines()
    assert bore_rows[0] == f"{spec.BORE_DRILL} DRILL THRU"
    assert shaft_number in bore_rows[1] and "TO FIT" in bore_rows[-1]
    assert not re.search(r"\.\d", drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"])
    # The reamed dowel holes: process and the linked gauge note, then the
    # mate and fit.  No reason line prints (owner ruling 2026-11-24): each
    # ream and tight band has its row in the necessity registry.
    dowel_rows = drawing.DIMENSION_CALLOUTS_BELOW["PinPosDia"].splitlines()
    assert dowel_rows == [
        f"2X REAM THRU, SEE NOTE {spec.REAM_NOTE}",
        f"PRESS FIT, DOWEL {spec.DOWEL_NUMBER}",
    ]
    registry = yaml.safe_load(
        (_config.CONFIG_DIR / "necessity" / "pd-transgear-drive-collar.yaml").read_text(
            encoding="utf-8"
        )
    )["necessity"]
    assert [row["id"] for row in registry] == ["N-01", "N-02", "N-03", "N-04"]
    for row in registry:
        assert row["kind"] in {"trace", "mesh", "gap", "joint", "bought_seat"}
        assert len(row["reason"].split()) <= 10, row["id"]
    for needle in ("Ø.0930", "Ø.0615", ".118 ±.002", "Ø.689"):
        assert sum(needle in row["feature"] for row in registry) == 1, needle
    # Their acceptance is the pins themselves and the wheels' trial (notes).
    ream_note = spec.DRAWING_NOTES.splitlines()[spec.REAM_NOTE - 1]
    assert ream_note == "3. PRESS FIT: THE PIN IS THE GAUGE; NONE ENTERS ITS HOLE BY HAND."
    assert f"ALL 3 {spec.SPROCKET_NUMBER} WHEELS DROP ON FREELY" in spec.DRAWING_NOTES
    # The rear break's leg and angle share one line; its mate rows name the
    # shaft corner it clears, short enough to hang left of its dimension line.
    assert drawing.DIMENSION_SUFFIXES["RearBreak"] == " X 45°"
    assert drawing.DIMENSION_SUFFIXES.keys() == {"RearBreak", "FlatPinDia"}
    assert "ROOT CORNER" in drawing.DIMENSION_CALLOUTS_BELOW["RearBreak"]
    assert all(len(r) <= 21 for r in drawing.DIMENSION_CALLOUTS_BELOW["RearBreak"].splitlines())
    for location in ("FlatPinCentre", "FlatPinFloor"):
        assert location not in drawing.DIMENSION_CALLOUTS_BELOW
    # Each REF offset links the flag note that gives its trial (rule 4).
    link = f"SEE NOTE {spec.TRIAL_NOTE}"
    assert drawing.DIMENSION_CALLOUTS_BELOW["PinPosY"] == link
    assert drawing.DIMENSION_CALLOUTS_BELOW["PinNegY"] == link
    assert spec.DRAWING_NOTES.splitlines()[spec.TRIAL_NOTE - 1].startswith(
        f"{spec.TRIAL_NOTE}. LOCATE BY TRIAL: "
    )
    # Rule 7: size and process lines plus at most two lines of words.
    assert all(
        len(text.splitlines()) <= 3 for text in drawing.DIMENSION_CALLOUTS_BELOW.values()
    )
    # The offsets print as REF targets.  PIN_OFFSET_TOL is the spacing
    # analysis the wheels' slip is charged (what the trial accepts), the
    # sprocket's own; the walls are charged PIN_CENTRE_SHIFT_MAX, the shop's
    # reamed-hole location row, which the trial does not bound (Codjiflo P1
    # on #3485).
    assert spec.PIN_OFFSET_TOL <= removable.DRIVE_PIN_OFFSET_TOL
    assert spec.PIN_OFFSET_TOL < printed_band_mm(3, unit=spec.UNIT)
    assert spec.PIN_CENTRE_SHIFT_MAX == pytest.approx(0.002 * 25.4)
    assert spec.PIN_OFFSET_TOL < spec.PIN_CENTRE_SHIFT_MAX
    import pd_transgear_removable_spec as wheel

    # The wheels' holes keep their printed band (the trial bounds only the
    # spacing, and their shift floats the chain toward MHA-DT-11's spigot).
    assert wheel.PIN_LOCATION_TOL == pytest.approx(0.0009 * 25.4)
    # No wall reads the spacing analysis: each moves by the whole shift.
    hole_r = (spec.PIN_HOLE_DIA + max(spec.PIN_HOLE_BAND)) / 2.0
    inner = spec.PIN_CIRCLE_RADIUS - spec.PIN_CENTRE_SHIFT_MAX - hole_r
    assert spec.PIN_HOLE_INNER_R_MIN == pytest.approx(inner)
    assert spec.BORE_PIN_WALL_WORST == pytest.approx(
        inner - (spec.BORE_DIA + max(spec.BORE_DIA_BAND)) / 2.0
    )
    rim = (spec.OD + min(spec.OD_BAND)) / 2.0 - (
        spec.PIN_CIRCLE_RADIUS + spec.PIN_CENTRE_SHIFT_MAX + hole_r
    )
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST <= rim < spec.DRIVE_PIN_COLLAR_RIM_WORST + 0.0254


def test_drive_pin_rim_is_the_seat_shortfall() -> None:
    # 17.5 / 2 - 7.0 - 2.38 / 2 = 0.56, the seat interface's recorded rim.
    assert spec.DRIVE_PIN_COLLAR_RIM == pytest.approx(removable.SEAT_SPIGOT_RIM)
    # The O.D. keeps only the spigot's maximum; its minimum is held to -.004
    # to keep the rim (owner ruling 2026-11-01).
    assert spec.OD_BAND == pytest.approx((max(removable.SPIGOT_DIA_BAND), -0.1016))
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST == pytest.approx(0.4572)  # .018
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST > 0.0


def test_pilot_wall_worst_and_the_one_decimal_control() -> None:
    assert spec.PILOT_WALL == pytest.approx((spec.PILOT_DIA - spec.BORE_DIA) / 2.0)
    assert spec.PILOT_WALL_WORST == pytest.approx(2.3368)  # .092, over .080
    assert spec.PILOT_WALL_WORST >= 0.080 * 25.4
    assert spec.PILOT_WALL_WORST >= 2.0
    # Negative control: a pilot narrower than the bore leaves no wall.
    assert (spec.BORE_DIA - (spec.BORE_DIA + max(spec.BORE_DIA_BAND))) / 2.0 < 0.0


def test_drive_pin_holes_clear_the_bore_and_the_pilot() -> None:
    # The unchanged dowel circle clears the bore and pilot.
    assert spec.BORE_PIN_WALL_WORST == pytest.approx(3.28525)  # .1293
    assert spec.BORE_PIN_WALL_WORST >= spec.WALL_FLOOR
    assert spec.PIN_HOLE_INNER_R_MIN == pytest.approx(5.76175)
    assert spec.PIN_HOLE_INNER_R_MIN > spec.PILOT_R_MAX
    # Negative controls: holes on a 6.0 radius break into the pilot; on the
    # pilot's own 5.0 radius they leave 0.605 to the bore.
    assert 6.0 - 0.051 - 1.19 < spec.PILOT_R_MAX
    assert 4.0 - 0.051 - 1.19 - (spec.BORE_DIA + max(spec.BORE_DIA_BAND)) / 2.0 < spec.WALL_FLOOR


def test_bore_slides_on_the_core_and_the_pilot_in_the_wheel() -> None:
    # Diametral, as the core's fit by hand leaves it: .0005-.0023.
    assert spec.BORE_CORE_CLEARANCE == pytest.approx((0.0127, 0.05842))
    assert spec.BORE_CORE_CLEARANCE == shaft.CORE_FIT_CLEARANCE
    # Radial: (10.3124 - 10.16) / 2 and (10.3124 + 0.1016 - 9.652) / 2. The pilot
    # only clears the bore, so the title block's .XX row governs both limits
    # (Codjiflo, #2148): .39 ±.01, never an authored band.
    assert spec.PILOT_DIA_PLACES == 2
    assert spec.PILOT_DIA_BAND == pytest.approx((0.254, -0.254))
    assert spec.PILOT_BORE_CLEARANCE == pytest.approx((0.0762, 0.381))
    # Negative controls: a core over the drilled bore's largest size binds; a
    # pilot at the wheel's bore size has no air.
    assert spec.BORE_DIA + max(spec.BORE_DIA_BAND) - (
        shaft.CORE_DIA + max(shaft.CORE_DIA_BAND)
    ) == pytest.approx(min(spec.BORE_CORE_CLEARANCE))
    assert (removable.BORE_DIA - removable.BORE_DIA) / 2.0 <= 0.0


def test_the_pilot_is_faced_to_stand_proud_of_the_knob_wheel_from_the_blank() -> None:
    """R9-70: the fitted band is the shared plate band plus the proud range, the
    model's pilot lies inside it, and the blank faces to the longest fit with
    one finishing cut left."""
    plate_lo = removable.PLATE + min(removable.PLATE_BAND)
    plate_hi = removable.PLATE + max(removable.PLATE_BAND)
    assert spec.PILOT_LENGTH_FITTED_MIN == pytest.approx(
        plate_lo + min(spec.PILOT_PROUD_RANGE)
    )
    assert spec.PILOT_LENGTH_FITTED_MAX == pytest.approx(
        plate_hi + max(spec.PILOT_PROUD_RANGE)
    )
    assert (spec.PILOT_LENGTH_FITTED_MIN, spec.PILOT_LENGTH_FITTED_MAX) == (
        pytest.approx((2.7508, 2.9524))
    )
    assert (
        spec.PILOT_LENGTH_FITTED_MIN
        <= spec.PILOT_LENGTH
        <= spec.PILOT_LENGTH_FITTED_MAX
    )
    assert spec.PILOT_LENGTH == pytest.approx(2.9016)
    assert (
        spec.PILOT_BLANK_LENGTH_MIN
        >= spec.PILOT_LENGTH_FITTED_MAX + spec.FACING_ALLOWANCE - 1e-9
    )
    assert f"{_in(spec.PILOT_BLANK_LENGTH_MIN)} MIN" in drawing.FIT_NOTES
    fitted = steps.inch_window((spec.PILOT_LENGTH_FITTED_MIN, spec.PILOT_LENGTH_FITTED_MAX), 3)
    assert f"FACED TO {fitted}" in drawing.FIT_NOTES
    assert drawing.DIMENSION_CALLOUTS_BELOW["PilotLength"] == (
        f"SEE NOTE {drawing.PILOT_NOTE}"
    )


def _in(value_mm: float) -> str:
    """A length in the sheet's three-place inches."""
    return f"{value_mm / 25.4:.3f}".removeprefix("0")


def _note(number: int) -> str:
    """Sheet note ``number`` as one line, its wrapped lines rejoined."""
    text = " ".join(drawing.FIT_NOTES.split())
    start = text.index(f"{number}. ")
    end = text.find(f" {number + 1}. ", start)
    return text[start : None if end < 0 else end]


def test_the_pilot_length_callout_points_at_its_facing_step() -> None:
    """Both matched facing operations are source-linked and renumber safely."""
    assert drawing.FIT_STEP_KEY == "pilot-faced-to-fit"
    assert steps.step_number(drawing.FIT_STEP_KEY) < steps.step_number(
        drawing.BODY_FIT_STEP_KEY
    )
    assert _note(drawing.PILOT_NOTE).endswith(
        f"PER {assembly_contract('pd-paper-drive').number} "
        f"STEP {steps.step_number(drawing.FIT_STEP_KEY)}."
    )
    # The part's own notes come first; the fit notes continue the list.
    part_notes = spec.DRAWING_NOTES.splitlines()
    assert part_notes[-1].startswith(f"{len(part_notes)}. ")
    assert (drawing.PILOT_NOTE, drawing.BODY_NOTE) == (
        len(part_notes) + 1, len(part_notes) + 2
    )


def test_the_thumbnut_bears_on_the_pilot_and_the_knob_wheel_floats() -> None:
    # The nut's rear countersink leaves a real annulus on the pilot.
    pilot_min = spec.PILOT_DIA + min(spec.PILOT_DIA_BAND)
    assert spec.NUT_PILOT_BEARING_WORST == pytest.approx((pilot_min - 4.572) / 2.0)
    assert spec.NUT_PILOT_BEARING_WORST > 0.0
    assert min(spec.KNOB_FLOAT_RANGE) > 0.0
    # Negative control: a pilot faced flush with the wheel leaves no float.
    assert spec.PILOT_LENGTH_FITTED_MIN - min(spec.PILOT_PROUD_RANGE) - 2.7 <= 0.0


def test_body_rear_face_reacts_at_f_over_the_whole_fitted_domain() -> None:
    assert spec.LENGTH == pytest.approx(6.1722)
    assert (spec.LENGTH_FITTED_MIN, spec.LENGTH_FITTED_MAX) == pytest.approx((3.8862, 6.8834))
    assert spec.BODY_REAR_FACE_FROM_F == 0.0
    assert spec.BODY_BLANK_LENGTH_MIN >= spec.LENGTH_FITTED_MAX + spec.FACING_ALLOWANCE
    assert drawing.BODY_FIT_STEP_KEY == "collar-rear-faced-to-fit"
    assert drawing.DIMENSION_CALLOUTS_BELOW["CollarLength"] == (
        f"SEE NOTE {drawing.BODY_NOTE}"
    )
    note = _note(drawing.BODY_NOTE)
    assert spec.BODY_LENGTH_CALLOUT.replace("\n", ", ") in note
    assert note.endswith(f"PER {steps.step_ref(drawing.BODY_FIT_STEP_KEY)}.")
    assert "SEATED ON MHA-PD-08 15T FRONT FACE" in note
    assert f"{_in(spec.BODY_BLANK_LENGTH_MIN)} MIN" in note
    assert f"FITTED {steps.inch_window((spec.LENGTH_FITTED_MIN, spec.LENGTH_FITTED_MAX), 3)}" in note
    assert spec.THUMBNUT_ENGAGEMENT_WORST >= shaft.ENGAGEMENT_FLOOR_D * shaft.THREAD_MAJOR
    assert spec.FRONT_BEARING_AREA_MIN > 0.0
    assert spec.NUT_CORE_STEP_AIR > 0.0


def test_notes_and_recipe_have_no_obsolete_front_pin_or_slot() -> None:
    notes = f"{spec.DRAWING_NOTES}\n{drawing.FIT_NOTES}"
    assert f"{_in(spec.DRIVE_PIN_COLLAR_RIM_WORST)} MIN" in notes
    assert f"{_in(spec.FLAT_PIN_WEB_WORST)} MIN" in notes
    assert f"{_in(spec.BODY_BLANK_LENGTH_MIN)} MIN" in notes
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method):
    # the part's notes, then the drawing's numbered fit notes, each linked
    # from its feature by SEE NOTE n.
    assert [line[:3] for line in notes.splitlines() if not line.startswith(" ")] == [
        "1. ", "2. ", "3. ", "4. ", "5. ", "6. "
    ]
    assert "BROACH" not in notes and "EDM" not in notes
    assert drawing.NOTES_TEXT.startswith(
        f'$PRPSHEET:"Manufacturing Notes"\n{drawing.PILOT_NOTE}. '
    )
    assert "SLOT" not in notes
    assert "SPRING PIN" not in notes
    assert "PILOT WALL" not in notes  # the former named shortfall is gone

def _notes_box(text: str, left: float, top: float) -> tuple[float, float, float]:
    """(right, bottom, top) of a top-left anchored default-format note."""
    lines = text.splitlines()
    return (
        left + max(map(len, lines)) * NOTE_CHAR_WIDTH,
        top - len(lines) * NOTE_LINE_PITCH,
        top,
    )


def test_the_notes_fit_left_of_the_title_block_and_under_the_views() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    left, top = drawing.NOTES_XY
    right, bottom, top = _notes_box(
        f"{spec.DRAWING_NOTES}\n{drawing.FIT_NOTES}", left, top
    )
    assert left > BORDER and right < template.title_block_left_m
    assert bottom > BORDER
    # The notes stay below both orthographic views' silhouettes.
    assert top < min(drawing.END_CENTER[1], drawing.SIDE_CENTER[1]) - drawing.HALF_OD
    # A deliberately oversized block is refused by the same border arithmetic.
    _, longer, _ = _notes_box("\n".join(["X"] * 100), left, top)
    assert longer < BORDER


def test_volume_gate_removes_only_the_ream_and_break_outside_the_bore() -> None:
    # Two unit circles a radius apart share 2*acos(1/2) - sqrt(3)/2; apart
    # they share nothing, one inside the other the smaller whole.
    assert spec.circle_overlap_area(1.0, 1.0, 1.0) == pytest.approx(
        2.0 * math.acos(0.5) - math.sqrt(3.0) / 2.0
    )
    assert spec.circle_overlap_area(1.0, 0.5, 2.5) == 0.0
    assert spec.circle_overlap_area(1.0, 0.5, 0.1) == pytest.approx(math.pi * 0.25)
    # A 45° cone wholly inside a coaxial cylinder is the cone's own frustum.
    assert spec.cone_cylinder_volume(1.0, 0.5, 5.0, 0.0) == pytest.approx(
        math.pi * 0.5 * (1.0 + 0.5 + 0.25) / 3.0
    )
    bore_r, ream_r = spec.BORE_DIA / 2.0, spec.FLAT_PIN_HOLE_DIA / 2.0
    assert part.V_BORE == pytest.approx(math.pi * bore_r**2 * (spec.LENGTH + spec.PILOT_LENGTH))
    full_ream = math.pi * ream_r**2 * (spec.LENGTH - spec.FLAT_PIN_FLOOR)
    assert 0.0 < part.V_FLAT_PIN_HOLE < full_ream
    # The break's whole ring, less what the ream has already opened.
    leg = spec.REAR_BREAK
    full_ring = math.pi * leg**2 * (bore_r + leg / 3.0)
    assert 0.8 * full_ring < part.V_REAR_BREAK < full_ring
    assert 0.0 < part.V_TOTAL < part.V_COLLAR + part.V_PILOT


def test_registry_row_is_the_turned_brass_mha_152() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-22"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


class _ReferenceDisplay:
    """Native SetText is void; success is visible only through GetText."""

    def __init__(self, *, persists: bool = True) -> None:
        self.text = {1: "", 2: ""}
        self.persists = persists

    def SetText(self, which: int, value: str) -> None:
        if self.persists:
            self.text[which] = value

    def GetText(self, which: int) -> str:
        return self.text[which]


def test_body_reference_refuses_method_shaped_text_readback(monkeypatch) -> None:
    display = _ReferenceDisplay()
    display.GetText = lambda _which: display.SetText
    dimension = SimpleNamespace(
        SystemValue=spec.LENGTH / 1000.0,
        Tolerance=SimpleNamespace(Type=0),
    )
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (display, dimension))
    with pytest.raises(RuntimeError, match="reference"):
        part._fitted_length_reference(object(), "CollarLength", spec.LENGTH)


def test_the_round_bore_clears_the_root_corner_and_bears_on_the_whole_core(monkeypatch) -> None:
    inch = 25.4
    # The rear mouth's 45° break, not an entry chamfer, meets the neck; it
    # ends inside the neck so the bore bears on the core's length.
    assert spec.REAR_BREAK_DEPTH_MAX <= shaft.FRONT_RELIEF_WIDTH_MAX
    assert spec.ROUND_FIT_FLOAT_MAX == pytest.approx(0.00115 * inch)
    assert spec.ROOT_CORNER_BORE_AIR_MIN == pytest.approx(0.01085 * inch)
    assert spec.BORE_AXIS_AT_F_FROM_JOURNAL_MAX == pytest.approx(0.06742, abs=1e-5)  # .0027
    # The rear face's bearing annulus on the gear starts outside the mouth,
    # its break, the bore's tilt at F and the gear's runout.
    assert spec.FRONT_BEARING_INNER_RADIUS_MAX > spec.BORE_DIA / 2.0 + max(spec.REAR_BREAK_LIMITS)
    # The largest drilled bore (.195) and the .013 break start the annulus
    # further out than the former .1925 ream and .010 break did.
    assert spec.FRONT_BEARING_AREA_MIN == pytest.approx(20.99, abs=0.01)
    # Negative control: a neck narrower than the mouth's break would leave
    # the break on the core, shortening the bore's support.
    monkeypatch.setattr(shaft, "FRONT_RELIEF_WIDTH_MAX", spec.REAR_BREAK_DEPTH_MAX / 2.0)
    with pytest.raises(AssertionError, match="recompute the bore's support"):
        _fresh_collar_spec()


def _plane(normal: tuple[float, float, float], offset_mm: float):
    from _gtol_face import FaceGeometry

    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(dia_mm: float, y_mm: float, z0_mm: float, z1_mm: float):
    from _gtol_face import FaceGeometry

    r = dia_mm / 2
    box = tuple(v / 1000 for v in (-r, y_mm - r, z0_mm, r, y_mm + r, z1_mm))
    params = (0.0, y_mm / 1000, 0.0, 0.0, 0.0, 1.0, r / 1000)
    return FaceGeometry(None, 4002, params, None, box)


def test_the_collar_declares_one_owner_per_face() -> None:
    import export_features
    from _gtol_face import FaceGeometry

    manifest = export_features.requirement_manifest("pd_transgear_drive_collar")
    assert list(manifest["features"]) == [
        "seat_face",
        "pilot_face",
        "rear_face",
        "outer",
        "pilot",
        "bore",
        "dowel_a",
        "dowel_b",
        "flat_pin_hole",
        "flat_pin_floor",
        "rear_break",
    ]
    length, pilot = spec.LENGTH, spec.PILOT_LENGTH
    r = spec.PIN_CIRCLE_RADIUS
    faces = {
        "seat_face": _plane((0.0, 0.0, -1.0), 0.0),
        "pilot_face": _plane((0.0, 0.0, -1.0), pilot),
        "rear_face": _plane((0.0, 0.0, 1.0), length),
        "flat_pin_floor": _plane((0.0, 0.0, 1.0), spec.FLAT_PIN_FLOOR),
        "outer": _cylinder(spec.OD, 0.0, 0.0, length),
        "pilot": _cylinder(spec.PILOT_DIA, 0.0, -pilot, 0.0),
        "bore": _cylinder(spec.BORE_DIA, 0.0, -pilot, length),
        "dowel_a": _cylinder(spec.PIN_HOLE_DIA, r, 0.0, length),
        "dowel_b": _cylinder(spec.PIN_HOLE_DIA, -r, 0.0, length),
        "flat_pin_hole": _cylinder(
            spec.FLAT_PIN_HOLE_DIA, -spec.FLAT_PIN_CENTRE, spec.FLAT_PIN_FLOOR, length
        ),
        "rear_break": FaceGeometry(
            None,
            4003,
            (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 2.6, math.radians(45.0), 1.0, 0.0, 0.0),
            None,
            (),
        ),
    }
    selectors = export_features.feature_selectors("pd_transgear_drive_collar")
    for name, face in faces.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name


def test_collar_feature_bands_are_the_printed_ones() -> None:
    import export_features

    def _in(value: float) -> float:
        return value * 25.4

    manifest = export_features.requirement_manifest("pd_transgear_drive_collar")
    features = manifest["features"]
    assert features["outer"]["dia"] == pytest.approx([_in(0.685), _in(0.689)], abs=1e-3)
    assert features["pilot"]["dia"] == pytest.approx([_in(0.38), _in(0.40)])
    # The drilled bore: the #11 at the DRILLED HOLES row.
    assert features["bore"]["dia"] == pytest.approx([_in(0.191), _in(0.195)])
    assert features["bore"]["thru"] is True and features["bore"]["process"] == "drill"
    for name, sign in (("dowel_a", 1.0), ("dowel_b", -1.0)):
        dowel = features[name]
        # ANALYSIS bands, bound only because the adapter requires limits: the
        # sheet prints neither (the dowel is the gauge, the offset a REF
        # target tried with the wheels).  The offset's is the shop's
        # reamed-hole location row, what the walls are charged.
        assert dowel["dia"] == pytest.approx([_in(0.0930), _in(0.0935)])
        offset = [_in(0.2756 - 0.002), _in(0.2756 + 0.002)]
        assert dowel["offset"] == pytest.approx(offset, abs=2e-3)
        assert dowel["at"] == pytest.approx([0.0, sign * spec.PIN_CIRCLE_RADIUS, 0.0])
        assert dowel["thru"] is True and dowel["process"] == "ream"
        assert dowel["mate"] == "MHA-PD-VN-54"
    flat = features["flat_pin_hole"]
    assert flat["dia"] == pytest.approx([_in(0.0615), _in(0.0620)])
    assert flat["centre"] == pytest.approx([_in(0.116), _in(0.120)])
    assert flat["depth_nominal"] == pytest.approx(_in(0.163), abs=1e-3)
    assert flat["process"] == "ream" and flat["mate"] == "MHA-PD-VN-70"
    floor = features["flat_pin_floor"]
    assert floor["station"] == pytest.approx([_in(0.07), _in(0.09)])
    # Supplied long, faced to fit at assembly (notes 5 and 6).
    pilot, rear = features["pilot_face"], features["rear_face"]
    assert pilot["supply_length_min"] == pytest.approx(_in(0.134))
    assert rear["supply_length_min"] == pytest.approx(_in(0.292))
    assert rear["fitted_length"] == pytest.approx([_in(0.153), _in(0.271)])
    assert pilot["note"].startswith(f"{drawing.PILOT_NOTE}. PILOT: SUPPLY .134 MIN")
    assert rear["note"].startswith(f"{drawing.BODY_NOTE}. BODY: SUPPLY .292 MIN")
    assert pilot["faced_at"] == rear["faced_at"] == "assembly"
    # The rear mouth's break is cut at assembly (MHA-PD-00 step 29).
    assert features["rear_break"]["made_at"] == "assembly"
    assert features["rear_break"]["leg"] == pytest.approx([_in(0.003), _in(0.013)])
