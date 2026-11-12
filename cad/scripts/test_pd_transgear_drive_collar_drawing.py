"""Offline contracts for the transgear drive collar (MHA-PD-22) and its drawing."""

from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    assert set(drawing.DIMENSION_CALLOUTS_BELOW) | set(drawing.DIMENSION_CALLOUTS_ABOVE) <= (
        set(drawing.END_KEEP) | set(drawing.SIDE_KEEP)
    )


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
    # The flat pin's ream reads below the axis.  Its size's one-line process,
    # value and mate rows stand below the ream as one block ending at its
    # dimension line, clear of the end view's outline, above the length row
    # and under the centre's text.
    hole_r = spec.FLAT_PIN_HOLE_DIA * drawing._S / 2000.0
    dia_x, dia_y = drawing.SIDE_KEEP["FlatPinDia"]
    rows = [
        drawing.DIMENSION_CALLOUTS_ABOVE["FlatPinDia"],
        *drawing.DIMENSION_CALLOUTS_BELOW["FlatPinDia"].splitlines(),
    ]
    assert dia_x - max(map(len, rows)) * DIM_CHAR_WIDTH > END_VIEW_RIGHT + 0.002
    assert dia_y < drawing._FLAT_PIN_Y - hole_r
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


class _SideViewSeat:
    """The actual axial section's end edges, built from the same source.

    Sheet right is model -Z and up is +Y. Each end face starts at the round
    bore's edge, except the rear face, which starts above the axis at the rear
    break's rim and below it at the flat pin's ream's outer edge; picking
    inside is bore, break or ream air.
    A pick lands on a line within half a sheet millimetre.
    """

    TOLERANCE_M = 0.0005

    def __init__(self) -> None:
        od_r, pilot_r = spec.OD / 2.0, spec.PILOT_DIA / 2.0
        bore_r = spec.BORE_DIA / 2.0
        ream_outer = spec.FLAT_PIN_CENTRE + spec.FLAT_PIN_HOLE_DIA / 2.0
        length, pilot = spec.LENGTH, spec.PILOT_LENGTH
        # (kind, (z, y), (z, y)) in model millimetres.
        self.segments = [
            ("EDGE", (-pilot, bore_r), (-pilot, pilot_r)),  # round bore
            ("EDGE", (-pilot, -pilot_r), (-pilot, -bore_r)),
            ("EDGE", (0.0, pilot_r), (0.0, od_r)),  # exposed seat annulus
            ("EDGE", (0.0, -od_r), (0.0, -pilot_r)),
            ("EDGE", (length, bore_r + spec.REAR_BREAK), (length, od_r)),
            ("EDGE", (length, -od_r), (length, -ream_outer)),
            ("SILHOUETTE", (0.0, od_r), (length, od_r)),
            ("SILHOUETTE", (0.0, -od_r), (length, -od_r)),
            ("SILHOUETTE", (-pilot, pilot_r), (0.0, pilot_r)),
            ("SILHOUETTE", (-pilot, -pilot_r), (0.0, -pilot_r)),
        ]
        self.selected: list[tuple[tuple[float, float], tuple[float, float]]] = []
        self.picked: list[tuple[tuple[float, float], tuple[float, float]]] = []
        self.display: _Display | None = None
        self.Extension = self

    @staticmethod
    def _sheet(point: tuple[float, float]) -> tuple[float, float]:
        z, y = point
        mid = (spec.LENGTH - spec.PILOT_LENGTH) / 2.0
        cx, cy = drawing.SIDE_CENTER
        return cx - (z - mid) * drawing._S / 1000.0, cy + y * drawing._S / 1000.0

    def _distance(self, xy, a, b) -> float:
        (ax, ay), (bx, by) = self._sheet(a), self._sheet(b)
        dx, dy = bx - ax, by - ay
        t = ((xy[0] - ax) * dx + (xy[1] - ay) * dy) / (dx * dx + dy * dy)
        t = min(1.0, max(0.0, t))
        return math.dist(xy, (ax + t * dx, ay + t * dy))

    def ActivateView(self, _name: str) -> bool:
        return True

    def ClearSelection2(self, _all: bool) -> bool:
        self.selected.clear()
        return True

    def SelectByID2(self, _name, kind, x, y, _z, append, *_rest) -> bool:
        hits = [
            (self._distance((x, y), a, b), (a, b))
            for k, a, b in self.segments
            if k == kind and self._distance((x, y), a, b) <= self.TOLERANCE_M
        ]
        if not hits:
            return False
        if not append:
            self.selected.clear()
        self.selected.append(min(hits)[1])
        return True

    def AddHorizontalDimension2(self, _x, _y, _z) -> _Display | None:
        stations = {a[0] for a, b in self.selected if a[0] == b[0]}
        if len(self.selected) != 2 or len(stations) != 2:
            return None
        self.picked = list(self.selected)
        self.display = _Display(abs(max(stations) - min(stations)) / 1000.0)
        return self.display


class _Display:
    def __init__(self, value_m: float) -> None:
        self.value_m = value_m
        self.precision = -1

    def GetDimension2(self, _index: int) -> SimpleNamespace:
        return SimpleNamespace(SystemValue=self.value_m)

    def GetAnnotation(self) -> object:
        return self

    def SetPrecision3(self, primary: int, *_rest: int) -> int:
        self.precision = primary
        return 0

    def GetPrimaryPrecision2(self) -> int:
        return self.precision


def test_the_overall_reference_picks_both_end_faces_as_drawn_edges(
    monkeypatch,
) -> None:
    """Both picks land on physical annular end-face edges, not bore air."""
    import _drawing_edge_dimensions

    monkeypatch.setattr(_drawing_edge_dimensions, "view_name", lambda _a, _v: "Drawing View2")
    monkeypatch.setattr(_drawing_edge_dimensions, "null_callout", lambda: None)
    references: list[str] = []
    monkeypatch.setattr(
        drawing,
        "set_reference_dimension",
        lambda _adapter, _annotation, *, label: references.append(label),
    )
    seat = _SideViewSeat()
    drawing._overall_reference(SimpleNamespace(currentModel=seat), object())
    assert [a[0] for a, _b in seat.picked] == pytest.approx(
        [-spec.PILOT_LENGTH, spec.LENGTH]
    )
    assert references == ["drive-collar overall length reference"]
    assert seat.display is not None
    assert seat.display.precision == spec.DRAWING_REFERENCE_PRECISION

    # Negative control: on the axis the rear face is the bore's air.
    front_pick, (rear_x, _rear_y) = drawing.OVERALL_PICKS
    monkeypatch.setattr(
        drawing, "OVERALL_PICKS", (front_pick, (rear_x, drawing.SIDE_CENTER[1]))
    )
    with pytest.raises(RuntimeError, match=r"reference edge 1 at sheet"):
        drawing._overall_reference(
            SimpleNamespace(currentModel=_SideViewSeat()), object()
        )


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
    assert spec.BORE_DIA == pytest.approx(0.192 * 25.4)
    assert spec.BORE_DIA_BAND == pytest.approx((0.0127, 0.0))
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
    assert _fresh_collar_spec().BORE_CORE_CLEARANCE == pytest.approx((0.0254, 0.05842))
    monkeypatch.setattr(shaft, "CORE_DIA_BAND", (0.030, 0.0))
    with pytest.raises(AssertionError, match="bore binds"):
        _fresh_collar_spec()
    monkeypatch.undo()
    monkeypatch.setattr(shaft, "CORE_FLAT_BAND", (0.040, 0.0))
    with pytest.raises(AssertionError, match="crest binds"):
        _fresh_collar_spec()


def test_round_stud_must_pass_the_flat_pin_crest(monkeypatch) -> None:
    assert spec.STUD_FLAT_PIN_AIR == pytest.approx(0.0031 * 25.4)
    monkeypatch.setattr(shaft, "THREAD_BLANK_LIMITS", (4.30, 4.40))
    with pytest.raises(AssertionError, match="stud cannot pass"):
        _fresh_collar_spec()


def test_the_flat_pin_crest_drives_the_core_flat_with_bounded_play() -> None:
    inch = 25.4
    assert spec.FLAT_PIN_CREST_LIMITS == pytest.approx((0.08465 * inch, 0.08875 * inch))
    assert spec.FLAT_PIN_CREST_CLEARANCE == pytest.approx((0.00065 * inch, 0.00535 * inch))
    # Over half the pin lies in its ream at the bore's largest radius.
    assert spec.FLAT_PIN_RETAINED_MARGIN == pytest.approx(0.01975 * inch)
    # The pin's front end stands on the core's flat over a real length at
    # every corner of the fitted body, floor, pin and core-front bands, behind
    # the rear break's relief of its crest.
    assert spec.FLAT_PIN_CORE_ENGAGEMENT_MIN == pytest.approx(0.04063 * inch, abs=1e-4)
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
    assert spec.FLAT_PIN_PLAY_DEG == pytest.approx((6.07, 17.17), abs=0.01)
    assert spec.FLAT_PIN_CONTACT_EDGE_MARGIN == pytest.approx(0.2326, abs=1e-4)  # .0092


def test_the_flat_pin_centre_takes_the_shop_row_for_a_reamed_location() -> None:
    # drawing-guidelines.md's row for a reamed hole's location is ±.002: the
    # centre carries it, and the crest still clears the flat over the band.
    assert spec.FLAT_PIN_CENTRE == pytest.approx(0.118 * 25.4)
    assert spec.FLAT_PIN_CENTRE_TOL == pytest.approx(0.002 * 25.4)
    assert min(spec.FLAT_PIN_CREST_CLEARANCE) > 0.0


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
    assert spec.FLAT_PIN_CREST_CORNER_AIR_MIN == pytest.approx(0.3355, abs=1e-4)  # .0132
    # Negative control: the bare crest, no break cone, has no air there.
    assert min(spec.FLAT_PIN_CREST_LIMITS) - reach <= 1e-9


def test_the_rear_break_ends_inside_the_neck() -> None:
    # The .010 leg at 44°, the widest and shallowest, ends .0104 in: inside the
    # neck's .011, so the bore keeps its whole support on the core.
    assert spec.REAR_BREAK == pytest.approx(0.008 * 25.4)
    assert spec.REAR_BREAK_TOL == pytest.approx(0.002 * 25.4)
    assert spec.REAR_BREAK_DEPTH_MAX == pytest.approx(0.2630, abs=1e-4)  # .0104
    assert spec.REAR_BREAK_DEPTH_MAX <= shaft.FRONT_RELIEF_WIDTH_MIN
    # The widest, shallowest cone from the largest bore reaches down to the
    # lowest crest .0224 in from F; the pin bears on the flat only behind it,
    # past the neck's widest .021.
    bore_r_max = spec.BORE_DIA / 2.0 + max(spec.BORE_DIA_BAND) / 2.0
    assert spec.rear_break_radius(
        spec.FLAT_PIN_CREST_RELIEF_MAX, bore_r_max, max(spec.REAR_BREAK_LIMITS),
        min(spec.REAR_BREAK_ANGLE_LIMITS),
    ) == pytest.approx(min(spec.FLAT_PIN_CREST_LIMITS))
    assert spec.FLAT_PIN_CREST_RELIEF_MAX == pytest.approx(0.02237 * 25.4, abs=1e-4)
    assert spec.FLAT_PIN_CREST_RELIEF_MAX > shaft.FRONT_RELIEF_WIDTH_MAX


def test_the_knob_reversal_play_costs_a_fraction_of_a_millimetre_of_paper() -> None:
    """RV-04 states the stack: both ways at the knob, through 15:150 to the
    feed sleeve, and on the feed pinion's pitch circle on the rack."""
    knob = spec.KNOB_REVERSAL_PLAY_DEG
    assert knob == pytest.approx(2.0 * max(spec.FLAT_PIN_PLAY_DEG))
    sleeve = knob * paper_drive_geom.GEAR_RATIO
    paper = math.pi * paper_drive_geom.FEED_PITCH_DIA * sleeve / 360.0
    assert (knob, sleeve, paper) == pytest.approx((34.35, 3.43, 0.29), abs=0.01)
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
    assert spec.FLAT_PIN_WEB_WORST == pytest.approx(0.076 * 25.4)
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
    assert model_toleranced_dimensions(part) == {
        ("BodyProfile", "CollarDia"): "*deviations(OD_BAND)",
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
        ("PinHoleProfile", "PinPosDia"): "*deviations(PIN_HOLE_BAND)",
        ("PinHoleProfile", "PinPosY"): "PIN_OFFSET_TOL",
        ("PinHoleProfile", "PinNegY"): "PIN_OFFSET_TOL",
        ("FlatPinProfile", "FlatPinDia"): "*deviations(FLAT_PIN_HOLE_BAND)",
        ("FlatPinProfile", "FlatPinCentre"): "FLAT_PIN_CENTRE_TOL",
        ("RearBreakProfile", "RearBreak"): "REAR_BREAK_TOL",
    }
    # The seat O.D. and the drive-pin layout are the crank spigot's, so the
    # removable wheels fit either shaft.
    assert spec.OD == removable.SEAT_SPIGOT_DIA
    assert spec.PIN_CIRCLE_RADIUS == removable.PIN_CIRCLE_RADIUS
    assert spec.PIN_HOLE_DIA == removable.DRIVE_PIN_HOLE_DIA
    assert spec.DRAWING_PRECISION_BY_NAME["CollarLength"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosY"] == 4
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
    assert _config.parts("pd-transgear-removable")["number"] in (
        drawing.DIMENSION_CALLOUTS_BELOW["PinPosDia"]
    )
    # The pressed pin is the collar's for good; its location is tight because
    # its crest drives the shaft (named there): two lines of words (rule 7).
    pin_rows = drawing.DIMENSION_CALLOUTS_BELOW["FlatPinDia"].splitlines()
    assert len(pin_rows) == 2
    assert pin_rows[0] == f"PERMANENT PIN {spec.FLAT_PIN_NUMBER}"
    shaft_number = _config.parts("pd-transgear-knob-shaft")["number"]
    assert pin_rows[1] == f"CREST DRIVES {shaft_number}"
    # The ream is blind, on one line over the value (an above-callout with a
    # line break does not print); its depth follows the value as a REF from
    # the section's nominal fitted rear face, the .XX floor controlling.
    above = drawing.DIMENSION_CALLOUTS_ABOVE["FlatPinDia"]
    assert "\n" not in above and above.startswith("BLIND REAM")
    assert drawing.DIMENSION_CALLOUTS_ABOVE.keys() == {"FlatPinDia"}
    depth = spec.LENGTH - spec.FLAT_PIN_FLOOR
    assert depth == pytest.approx(0.163 * 25.4)
    assert drawing.DIMENSION_SUFFIXES["FlatPinDia"] == " <HOLE-DEPTH> (.163)"
    # The bore's clearance range reads as its reference third row.
    bore_rows = drawing.DIMENSION_CALLOUTS_BELOW["BoreDia"].splitlines()
    assert bore_rows[-1].startswith("(CLEARANCE ") and bore_rows[-1].endswith(")")
    # The rear break's leg and angle share one line; its mate rows name the
    # shaft corner it clears, short enough to hang left of its dimension line.
    assert drawing.DIMENSION_SUFFIXES["RearBreak"] == " X 45°"
    assert drawing.DIMENSION_SUFFIXES.keys() == {"RearBreak", "FlatPinDia"}
    assert "ROOT CORNER" in drawing.DIMENSION_CALLOUTS_BELOW["RearBreak"]
    assert all(len(r) <= 21 for r in drawing.DIMENSION_CALLOUTS_BELOW["RearBreak"].splitlines())
    for location in ("PinPosY", "PinNegY", "FlatPinCentre", "FlatPinFloor"):
        assert location not in drawing.DIMENSION_CALLOUTS_BELOW
    # Rule 7: size and process lines plus at most two lines of words.
    assert all(
        len(text.splitlines()) <= 3 for text in drawing.DIMENSION_CALLOUTS_BELOW.values()
    )
    # The locations' tight band is the sprocket's own (until D14 carries the
    # shared interface in inch, no looser than it): the dowels must enter its
    # drilled holes, each part spending half the 0.119 clearance.
    assert spec.PIN_OFFSET_TOL <= removable.DRIVE_PIN_OFFSET_TOL
    assert spec.PIN_OFFSET_TOL < printed_band_mm(3, unit=spec.UNIT)


def test_drive_pin_rim_is_the_seat_shortfall() -> None:
    # 17.5 / 2 - 7.0 - 2.38 / 2 = 0.56, the seat interface's recorded rim.
    assert spec.DRIVE_PIN_COLLAR_RIM == pytest.approx(removable.SEAT_SPIGOT_RIM)
    # The O.D. keeps only the spigot's maximum; its minimum is held to -.004
    # to keep the rim (owner ruling 2026-11-01).
    assert spec.OD_BAND == pytest.approx((max(removable.SPIGOT_DIA_BAND), -0.1016))
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST == pytest.approx(0.4826)  # .019
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST > 0.0


def test_pilot_wall_worst_and_the_one_decimal_control() -> None:
    assert spec.PILOT_WALL == pytest.approx((spec.PILOT_DIA - spec.BORE_DIA) / 2.0)
    assert spec.PILOT_WALL_WORST == pytest.approx(2.3622)  # .093, over .080
    assert spec.PILOT_WALL_WORST >= 0.080 * 25.4
    assert spec.PILOT_WALL_WORST >= 2.0
    # Negative control: a pilot narrower than the bore leaves no wall.
    assert (spec.BORE_DIA - (spec.BORE_DIA + max(spec.BORE_DIA_BAND))) / 2.0 < 0.0



def test_drive_pin_holes_clear_the_bore_and_the_pilot() -> None:
    # The unchanged dowel circle clears the bore and pilot.
    assert spec.BORE_PIN_WALL_WORST == pytest.approx(3.34494)
    assert spec.BORE_PIN_WALL_WORST >= spec.WALL_FLOOR
    assert spec.PIN_HOLE_INNER_R_MIN == pytest.approx(5.78969)
    assert spec.PIN_HOLE_INNER_R_MIN > spec.PILOT_R_MAX
    # Negative controls: holes on a 6.0 radius break into the pilot; on the
    # pilot's own 5.0 radius they leave 0.605 to the bore.
    assert 6.0 - 0.025 - 1.19 < spec.PILOT_R_MAX
    assert 4.0 - 0.025 - 1.19 - (spec.BORE_DIA + max(spec.BORE_DIA_BAND)) / 2.0 < spec.WALL_FLOOR


def test_bore_slides_on_the_core_and_the_pilot_in_the_wheel() -> None:
    assert spec.BORE_CORE_CLEARANCE == pytest.approx((0.0254, 0.05842))
    # Radial: (10.3124 - 10.16) / 2 and (10.3124 + 0.1016 - 9.652) / 2. The pilot
    # only clears the bore, so the title block's .XX row governs both limits
    # (Codjiflo, #2148): .39 ±.01, never an authored band.
    assert spec.PILOT_DIA_PLACES == 2
    assert spec.PILOT_DIA_BAND == pytest.approx((0.254, -0.254))
    assert spec.PILOT_BORE_CLEARANCE == pytest.approx((0.0762, 0.381))
    # Negative controls: a press-type bore band binds on the core; a pilot
    # at the wheel's bore size has no air.
    press_bore = spec.BORE_DIA - 0.030 - (shaft.CORE_DIA + max(shaft.CORE_DIA_BAND))
    assert press_bore < 0.0
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
        "1. ", "2. ", "3. ", "4. "
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


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _part_properties
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = {
        ast.literal_eval(key): getattr(part, value.id)
        for key, value in zip(stamp.args[2].keys, stamp.args[2].values, strict=True)
    }
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert carried["Manufacturing Notes"] == spec.DRAWING_NOTES
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE


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


def test_saved_fitted_lengths_are_native_reference_not_fixed_sizes(monkeypatch) -> None:
    for name, nominal in (
        ("CollarLength", spec.LENGTH),
        ("PilotLength", spec.PILOT_LENGTH),
    ):
        display = _ReferenceDisplay()
        dimension = SimpleNamespace(
            SystemValue=nominal / 1000.0,
            Tolerance=SimpleNamespace(Type=0),
        )
        monkeypatch.setattr(
            part, "_named_dimension", lambda *_args: (display, dimension)
        )
        part._fitted_length_reference(object(), name, nominal)
        assert (display.GetText(1), display.GetText(2)) == ("(", ")")
        assert dimension.Tolerance.Type == 0
    # Both fitted lengths are made REF by the build, after precision.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '_fitted_length_reference(adapter, "CollarLength", LENGTH)' in source
    assert '_fitted_length_reference(adapter, "PilotLength", PILOT_LENGTH)' in source


def test_body_reference_refuses_a_void_setter_that_does_not_persist(monkeypatch) -> None:
    display = _ReferenceDisplay(persists=False)
    dimension = SimpleNamespace(
        SystemValue=spec.LENGTH / 1000.0,
        Tolerance=SimpleNamespace(Type=0),
    )
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (display, dimension))
    with pytest.raises(RuntimeError, match="reference"):
        part._fitted_length_reference(object(), "CollarLength", spec.LENGTH)


@pytest.mark.parametrize("band_type", [2, 4, 6])
def test_body_reference_refuses_an_independent_size_band(monkeypatch, band_type) -> None:
    dimension = SimpleNamespace(
        SystemValue=spec.LENGTH / 1000.0,
        Tolerance=SimpleNamespace(Type=band_type),
    )
    monkeypatch.setattr(
        part, "_named_dimension", lambda *_args: (_ReferenceDisplay(), dimension)
    )
    with pytest.raises(RuntimeError, match="independent"):
        part._fitted_length_reference(object(), "CollarLength", spec.LENGTH)


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


def test_pilot_reference_refuses_a_nominal_outside_the_model(monkeypatch) -> None:
    dimension = SimpleNamespace(
        SystemValue=spec.LENGTH / 1000.0,
        Tolerance=SimpleNamespace(Type=0),
    )
    monkeypatch.setattr(
        part, "_named_dimension", lambda *_args: (_ReferenceDisplay(), dimension)
    )
    with pytest.raises(RuntimeError, match="fitted nominal"):
        part._fitted_length_reference(object(), "PilotLength", spec.PILOT_LENGTH)


def _capture_fixture(
    monkeypatch, *, length=None, rear_gap=0.0, front_error=0.0, clock_error=0.0, missing=None
):
    import build_pd_paper_drive_assembly as assembly
    import _gtol_face_resolve

    length = spec.LENGTH if length is None else length

    class NativeModel:
        def Parameter(self, name):
            assert name == "CollarLength@BodyProfile"
            return None if missing == "dimension" else SimpleNamespace(SystemValue=length / 1000.0)

        def GetBodies2(self, body_type: int, visible_only: bool):
            assert (body_type, visible_only) == (0, False)
            return ()  # Explicit negative: no actual solid/face to react on F.

    class Component:
        def GetModelDoc2(self):
            return None if missing == "model" else NativeModel()

    native = SimpleNamespace(
        GetComponentByName=lambda _name: None if missing == "component" else Component()
    )
    monkeypatch.setattr(assembly, "_early_bound", lambda value, _kind: value)
    if missing == "face":
        # Use the real face resolver for the missing-metal refusal, not a
        # test-only accepted-face flag or a replacement reaction annotation.
        monkeypatch.setattr(_gtol_face_resolve, "_early_bound", lambda value, _kind: value)
    else:
        monkeypatch.setattr(_gtol_face_resolve, "resolve_faces", lambda _model, requests: requests)
    calls = []

    def world_point(_adapter, name, local):
        calls.append((name, tuple(local)))
        if name == "collar":
            return (
                math.sin(clock_error) * -local[1],
                math.cos(clock_error) * local[1],
                assembly.KNOB_COLLAR_Z0 + local[2] + rear_gap,
            )
        if name == "wheel":
            return (local[0], local[1], assembly.REMOVABLE_Z0 + local[2] + front_error)
        return (local[0], local[1], assembly.KNOB_SHAFT_Z0 + local[2])

    monkeypatch.setattr(assembly, "world_point", world_point)
    adapter = SimpleNamespace(currentModel=native)
    assembly._assert_knob_collar_capture(adapter, "collar", "shaft", "wheel")
    return calls


def test_actual_native_collar_rear_face_is_measured_on_f(monkeypatch) -> None:
    calls = _capture_fixture(monkeypatch)
    assert ("collar", (0.0, 0.0, spec.LENGTH)) in calls
    assert ("shaft", (0.0, 0.0, 0.0)) in calls
    assert ("collar", (0.0, -1.0, 0.0)) in calls
    # The faced remainder stands at the collar's front, off the wheel's rear.
    assert ("collar", (0.0, 0.0, 0.0)) in calls
    assert ("wheel", (0.0, 0.0, removable.PLATE)) in calls


@pytest.mark.parametrize(
    "kwargs, message",
    [({"rear_gap": 0.01}, "rear is not on gear F"),
     ({"front_error": 0.0169}, "behind the wheel"),
     ({"clock_error": math.radians(3.0)}, "not clocked"),
     ({"length": spec.LENGTH_FITTED_MIN - 0.01}, "outside"),
     ({"length": spec.LENGTH - 0.01}, "source version"),
     ({"missing": "component"}, "component"),
     ({"missing": "model"}, "part"),
     ({"missing": "face"}, "matched 0 faces"),
     ({"missing": "dimension"}, "dimension")],
)
def test_native_reaction_capture_refuses_gap_wrong_clock_and_missing_metal(
    monkeypatch, kwargs, message
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _capture_fixture(monkeypatch, **kwargs)


def test_the_round_bore_clears_the_root_corner_and_bears_on_the_whole_core(monkeypatch) -> None:
    inch = 25.4
    # The rear mouth's 45° break, not an entry chamfer, meets the neck; it
    # ends inside the neck so the bore bears on the core's length.
    assert spec.REAR_BREAK_DEPTH_MAX <= shaft.FRONT_RELIEF_WIDTH_MIN
    assert spec.ROUND_FIT_FLOAT_MAX == pytest.approx(0.00115 * inch)
    assert spec.ROOT_CORNER_BORE_AIR_MIN == pytest.approx(0.01135 * inch)
    assert spec.BORE_AXIS_AT_F_FROM_JOURNAL_MAX == pytest.approx(0.06742, abs=1e-5)  # .0027
    # The rear face's bearing annulus on the gear starts outside the mouth,
    # its break, the bore's tilt at F and the gear's runout.
    assert spec.FRONT_BEARING_INNER_RADIUS_MAX > spec.BORE_DIA / 2.0 + max(spec.REAR_BREAK_LIMITS)
    assert spec.FRONT_BEARING_AREA_MIN == pytest.approx(22.92, abs=0.01)
    # Negative control: a neck narrower than the mouth's break would leave
    # the break on the core, shortening the bore's support.
    monkeypatch.setattr(shaft, "FRONT_RELIEF_WIDTH_MIN", spec.REAR_BREAK_DEPTH_MAX / 2.0)
    with pytest.raises(AssertionError, match="shortens the bore's support"):
        _fresh_collar_spec()


class _CollarSection:
    """Method/property forms match IView/IDrSection; void reversal is read back."""

    def __init__(self, *, reverses=True, moves=True, has_cut=True):
        self.Angle = 0.0
        self.Position = drawing.SIDE_CENTER
        self.seat = drawing.SIDE_CENTER
        self.reversed = False
        self.reverses, self.moves, self.has_cut = reverses, moves, has_cut

    def project(self, xyz):
        x, y = xyz[2], xyz[1] * (-1.0 if self.reversed else 1.0)
        cosine, sine = math.cos(self.Angle), math.sin(self.Angle)
        return (
            self.seat[0] + drawing._S * (cosine * x - sine * y),
            self.seat[1] + drawing._S * (sine * x + cosine * y),
        )

    def GetSection(self):
        return self if self.has_cut else None

    def GetReversedCutDirection(self) -> bool:
        return self.reversed

    def SetReversedCutDirection(self, value: bool) -> None:
        if self.reverses:
            self.reversed = value

    def GetOutline(self):
        points = [
            self.project((0.0, y / 1000.0, z / 1000.0))
            for z, radius in ((-spec.PILOT_LENGTH, spec.PILOT_DIA / 2.0),
                              (0.0, spec.OD / 2.0), (spec.LENGTH, spec.OD / 2.0))
            for y in (-radius, radius)
        ]
        return (
            min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points),
        )

    def SetViewPosition(self, position, move_children: bool) -> bool:
        assert move_children is False
        if self.moves:
            self.seat = tuple(
                self.seat[i] + position[i] - self.Position[i] for i in (0, 1)
            )
        self.Position = tuple(position)
        return True


def _orient_collar_section(monkeypatch, section):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(
        drawing, "model_point_in_view", lambda _adapter, view, xyz, **_kwargs: view.project(xyz)
    )
    drawing._orient_section(object(), section)


def test_actual_collar_section_has_rear_left_pilot_right_and_flat_pin_below(monkeypatch):
    section = _CollarSection()
    _orient_collar_section(monkeypatch, section)
    assert section.reversed is True
    assert section.project((0.0, 0.0, 0.0)) == pytest.approx(
        (drawing._SEAT_X, drawing.SIDE_CENTER[1])
    )
    assert section.project((0.0, 0.0, spec.LENGTH / 1000.0))[0] == pytest.approx(drawing._REAR_X)
    assert section.project((0.0, 0.0, -spec.PILOT_LENGTH / 1000.0))[0] == pytest.approx(drawing._PILOT_X)
    assert section.project((0.0, -spec.FLAT_PIN_CENTRE / 1000.0, 0.0))[1] < drawing.SIDE_CENTER[1]


@pytest.mark.parametrize(
    "kwargs, message",
    [({"reverses": False}, "direction"),
     ({"moves": False}, "source frame"),
     ({"has_cut": False}, "no native")],
)
def test_actual_collar_section_refuses_void_mutators_that_do_not_persist(
    monkeypatch, kwargs, message
):
    with pytest.raises(RuntimeError, match=message):
        _orient_collar_section(monkeypatch, _CollarSection(**kwargs))
