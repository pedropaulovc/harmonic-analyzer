"""Offline contracts for the transgear drive collar (MHA-PD-022) and its drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_pd_transgear_drive_collar as part
import draw_pd_transgear_drive_collar as drawing
import pd_paper_drive_assembly_steps as steps
import vn_transgear_collar_cross_pin_spec as cross_pin
import pd_transgear_drive_collar_spec as spec
import pd_transgear_knob_shaft_spec as shaft
import pd_transgear_removable_spec as removable
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _printed_tolerance import printed_band_mm
from _drawing_annotation_extent import (
    annotation_ink_from_record,
    boxes_clear,
    require_annotation_clear,
    require_annotation_in_field,
)

# Default-format note text, measured on r743-rocker-fix3's render, as
# test_paper_drive_assembly_drawing and test_channel_assembly_drawing use them.
NOTE_CHAR_WIDTH = 0.00276
NOTE_LINE_PITCH = 0.0045
BORDER = 0.0127


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
    assert set(drawing.DIMENSION_CALLOUTS_BELOW) <= (
        set(drawing.END_KEEP) | set(drawing.SIDE_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS_ABOVE) <= set(drawing.SIDE_KEEP)


def test_turned_diameters_and_lengths_print_on_the_side_view() -> None:
    # Rule 7: the turned O.D. and pilot sit on the profile the side view
    # looks at, beside both lengths; the end view keeps only the holes.
    body = spec.DRAWING_DIMENSIONS["BodyProfile"]
    assert body == {"CollarDia", "CollarLength", "PilotDia", "PilotLength"}
    assert body <= set(drawing.SIDE_KEEP)
    assert spec.OVERALL_LENGTH == pytest.approx(spec.LENGTH + spec.PILOT_LENGTH)
    # The overall reads outside both lengths, below them.
    lowest_length = min(
        drawing.SIDE_KEEP[n][1] for n in ("CollarLength", "PilotLength")
    )
    assert drawing.OVERALL_TEXT_XY[1] < lowest_length - 0.008
    assert drawing.OVERALL_TEXT_XY[1] > BORDER + 0.010
    # The O.D. reads outside the slot width, both left of the rear face.
    assert (
        drawing.SIDE_KEEP["CollarDia"][0]
        < drawing.SIDE_KEEP["SlotWidth"][0]
        < drawing._REAR_X
    )
    assert drawing.SIDE_KEEP["PilotDia"][0] > drawing._PILOT_X


class _SideViewSeat:
    """The *Right side view's hit test, hidden lines removed, built from the spec.

    The view centres on the part's box (run 20261001T142942518Z projected the
    rear face to sheet x 0.2232), sheet right is model -Z and up is +Y.  Each
    planar face's circles stand edge-on as model EDGEs; only the turned flanks
    are SILHOUETTEs.  A pick lands on a line within half a sheet millimetre.
    """

    TOLERANCE_M = 0.0005

    def __init__(self) -> None:
        od_r, pilot_r = spec.OD / 2.0, spec.PILOT_DIA / 2.0
        slot_r, floor = spec.SLOT_WIDTH / 2.0, spec.SLOT_FLOOR_Z
        length, pilot = spec.LENGTH, spec.PILOT_LENGTH
        # (kind, (z, y), (z, y)) in model millimetres.
        self.segments = [
            ("EDGE", (-pilot, -pilot_r), (-pilot, pilot_r)),  # pilot front
            ("EDGE", (0.0, -od_r), (0.0, od_r)),  # seat face
            ("EDGE", (floor, -slot_r), (floor, slot_r)),  # slot floor
            ("EDGE", (length, slot_r), (length, od_r)),  # rear face, either
            ("EDGE", (length, -od_r), (length, -slot_r)),  # side of the slot
            ("EDGE", (floor, slot_r), (length, slot_r)),  # slot walls
            ("EDGE", (floor, -slot_r), (length, -slot_r)),
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

    def SetPrecision3(self, primary: int, *_rest: int) -> bool:
        self.precision = primary
        return True

    def GetPrimaryPrecision2(self) -> int:
        return self.precision


def test_the_overall_reference_picks_both_end_faces_as_drawn_edges(
    monkeypatch,
) -> None:
    """Run 20261001T142942518Z: the rear-face pick asked for a SILHOUETTE
    where only the face's edge-on circle (a model EDGE) is drawn, and the
    sheet stopped.  Both picks land on end-face edges and measure 5.9."""
    import _drawing_common

    monkeypatch.setattr(_drawing_common, "view_name", lambda _a, _v: "Drawing View2")
    monkeypatch.setattr(_drawing_common, "null_callout", lambda: None)
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

    # Negative control: on the axis the rear face is the slot's air.
    monkeypatch.setattr(
        drawing,
        "OVERALL_PICKS",
        tuple((x, drawing.SIDE_CENTER[1]) for x, _y in drawing.OVERALL_PICKS),
    )
    with pytest.raises(RuntimeError, match=r"reference edge 1 at sheet"):
        drawing._overall_reference(
            SimpleNamespace(currentModel=_SideViewSeat()), object()
        )


def _segments_cross(a, b, c, d) -> bool:
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def test_end_view_leaders_run_straight_in_without_crossing() -> None:
    cx, cy = drawing.END_CENTER
    bore_r = spec.BORE_DIA * drawing._S / 2000.0
    bore_text = drawing.END_KEEP["BoreDia"]
    angle = math.atan2(bore_text[1] - cy, bore_text[0] - cx)
    bore_tip = (cx + bore_r * math.cos(angle), cy + bore_r * math.sin(angle))
    pin_text = drawing.END_KEEP["PinPosDia"]
    pin_tip = (cx, cy - drawing.PIN_R)  # the lower hole's centre
    assert not _segments_cross(bore_text, bore_tip, pin_text, pin_tip)
    # Neither diameter leader passes through the other pin hole.
    hole_r = spec.PIN_HOLE_DIA * drawing._S / 2000.0
    upper = (cx, cy + drawing.PIN_R)
    (x0, y0), (x1, y1) = bore_text, bore_tip
    t = ((upper[0] - x0) * (x1 - x0) + (upper[1] - y0) * (y1 - y0)) / (
        (x1 - x0) ** 2 + (y1 - y0) ** 2
    )
    t = min(1.0, max(0.0, t))
    nearest = (x0 + t * (x1 - x0), y0 + t * (y1 - y0))
    assert math.dist(nearest, upper) > hole_r


def test_slot_placement_prints_the_stacks_centring_term() -> None:
    # The slot-to-pin wall stack spends POSITION_TOL on the slot's centring;
    # the sheet must hold the slot to that, not leave it to appearance.
    assert f"{spec.POSITION_TOL:.3f}" in spec.SLOT_CALLOUT
    assert spec.POSITION_TOL == pytest.approx(0.065)
    # Review of 8b5e1f354: the two-line above callout never printed, so the
    # slot read as unlocated.  The centring is one printable above line, and
    # the slot's square to the pin line prints under the pin holes' callout.
    above = drawing.DIMENSION_CALLOUTS_ABOVE
    assert above == {"SlotDepth": spec.SLOT_CALLOUT}
    assert drawing._printable_above_callouts(above) == above
    with pytest.raises(RuntimeError, match="SlotDepth"):
        drawing._printable_above_callouts({"SlotDepth": "A\nB"})
    pin_lines = drawing.DIMENSION_CALLOUTS_BELOW["PinPosDia"].splitlines()
    assert pin_lines == ["2X REAM THROUGH", spec.SLOT_ORIENTATION]
    assert "90\u00b0" in spec.SLOT_ORIENTATION
    for line in (spec.SLOT_CALLOUT, *pin_lines):
        assert len(line) <= 70


def test_side_view_od_band_stands_clear_of_the_slot_width() -> None:
    # Both stacked tolerance rows matter, not just the "1.8" nominal.
    # PD-6 moves the slot block below its witnesses; test 2-D reservations
    # rather than requiring the obsolete same-height horizontal allocation.
    char = 0.0035 * 0.746
    cx, cy = drawing.SIDE_KEEP["CollarDia"]
    half = char * len("\u00d817.50 -0.1") / 2.0
    od_box = (cx - half, cy - 0.005, cx + half, cy + 0.005)
    assert boxes_clear(od_box, drawing.SIDE_TEXT_FIELDS["SlotWidth"], gap=0.0035)
    end_view_right = drawing.END_CENTER[0] + drawing.HALF_OD
    od_left = drawing.SIDE_KEEP["CollarDia"][0] - char * len("\u00d817.50 -0.1") / 2.0
    assert od_left - end_view_right >= 0.010


def test_fits_carry_named_bands_and_the_lengths_print_their_places() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BodyProfile", "CollarDia"): "*deviations(OD_BAND)",
        ("BodyProfile", "PilotDia"): "*deviations(PILOT_DIA_BAND)",
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
        ("SlotProfile", "SlotWidth"): "*deviations(SLOT_WIDTH_BAND)",
        ("SlotProfile", "SlotDepth"): "*deviations(SLOT_DEPTH_BAND)",
        ("PinHoleProfile", "PinPosDia"): "*deviations(PIN_HOLE_BAND)",
        ("PinHoleProfile", "PinPosY"): "PIN_OFFSET_TOL",
        ("PinHoleProfile", "PinNegY"): "PIN_OFFSET_TOL",
    }
    # The seat O.D. and the drive-pin layout are the crank spigot's, so the
    # removable T24 fits either shaft.
    assert spec.OD == removable.SEAT_SPIGOT_DIA
    assert spec.PIN_CIRCLE_RADIUS == removable.PIN_CIRCLE_RADIUS
    assert spec.PIN_HOLE_DIA == removable.DRIVE_PIN_HOLE_DIA
    assert spec.DRAWING_PRECISION_BY_NAME["CollarLength"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PinPosY"] == 3


def test_drive_pin_rim_is_the_seat_shortfall_and_needs_three_place_offsets() -> None:
    # 17.5 / 2 - 7.0 - 2.38 / 2 = 0.56, the seat interface's recorded rim.
    assert spec.DRIVE_PIN_COLLAR_RIM == pytest.approx(removable.SEAT_SPIGOT_RIM)
    # 8.70 - 7.0 - 0.025 - 1.19 = 0.485, printed 0.48.
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST == pytest.approx(0.48)
    assert spec.DRIVE_PIN_COLLAR_RIM_WORST > 0.0
    # Negative control: the offsets at the .XX row (±0.51) leave no rim.
    at_xx = 8.70 - 7.0 - printed_band_mm(2) - 1.19
    assert at_xx <= 1e-9


def test_pilot_wall_worst_and_the_one_decimal_control() -> None:
    # (9.90 - 6.36) / 2 = 1.77.
    assert spec.PILOT_WALL == pytest.approx(1.825)
    assert spec.PILOT_WALL_WORST == pytest.approx(1.77)
    assert spec.PILOT_WALL_WORST >= spec.WALL_FLOOR
    # Negative control: a pilot left at the .X row (-0.8): (9.2 - 6.36) / 2.
    at_x = (spec.PILOT_DIA - printed_band_mm(1) - 6.36) / 2.0
    assert at_x == pytest.approx(1.42)
    assert at_x < spec.WALL_FLOOR


def test_slot_floor_to_front_face_worst_and_the_one_decimal_control() -> None:
    # 3.87 - (1.8 + 0.10) = 1.97.
    assert spec.SLOT_FLOOR_WALL == pytest.approx(2.2)
    assert spec.SLOT_FLOOR_WALL_WORST == pytest.approx(1.97)
    assert spec.SLOT_FLOOR_WALL_WORST >= spec.WALL_FLOOR
    # Negative control: the collar length at the .X row: 3.2 - 1.9 = 1.3.
    at_x = spec.LENGTH - printed_band_mm(1) - 1.9
    assert at_x < spec.WALL_FLOOR


def test_slot_runs_between_the_drive_pins_not_through_them() -> None:
    # Slot along X, pins on ±Y: 7.0 - 0.025 - 1.19 - 0.95 - 0.065 = 4.77.
    assert spec.SLOT_PIN_WALL_WORST == pytest.approx(4.77)
    assert spec.SLOT_PIN_WALL_WORST >= spec.WALL_FLOOR
    # Negative control: a slot cut along the pins' line puts them in it.
    along_pins = 0.0 - 0.025 - 1.19 - 0.95 - 0.065
    assert along_pins < 0.0


def test_drive_pin_holes_clear_the_bore_and_the_pilot() -> None:
    # 7.0 - 0.025 - 1.19 - 3.18 = 2.605 of wall to the bore; the holes'
    # inner edge r 5.785 lies outside the pilot's r 5.0.
    assert spec.BORE_PIN_WALL_WORST == pytest.approx(2.605)
    assert spec.BORE_PIN_WALL_WORST >= spec.WALL_FLOOR
    assert spec.PIN_HOLE_INNER_R_MIN == pytest.approx(5.785)
    assert spec.PIN_HOLE_INNER_R_MIN > spec.PILOT_R_MAX
    # Negative controls: holes on a 6.0 radius break into the pilot; on the
    # pilot's own 5.0 radius they leave 0.605 to the bore.
    assert 6.0 - 0.025 - 1.19 < spec.PILOT_R_MAX
    assert 5.0 - 0.025 - 1.19 - 3.18 < spec.WALL_FLOOR


def test_bore_slides_on_the_core_and_the_pilot_in_the_wheel() -> None:
    # 6.350..6.360 over 6.335..6.345.
    assert spec.BORE_CORE_CLEARANCE == pytest.approx((0.005, 0.025))
    # Radial: (10.3 - 10.0) / 2 and (10.3 + 0.10 - 9.90) / 2.
    assert spec.PILOT_BORE_CLEARANCE == pytest.approx((0.15, 0.25))
    # Negative controls: a press-type bore band binds on the core; a pilot
    # at the wheel's bore size has no air.
    press_bore = spec.BORE_DIA - 0.010 - (shaft.CORE_DIA + max(shaft.CORE_DIA_BAND))
    assert press_bore < 0.0
    assert (removable.BORE_DIA - removable.BORE_DIA) / 2.0 <= 0.0


def test_the_pilot_is_faced_to_stand_proud_of_the_t24_from_the_blank() -> None:
    """R9-70: the fitted band is the T24 plate band plus the proud range, the
    model's pilot lies inside it, and the blank faces to the longest fit with
    one finishing cut left."""
    plate_lo, plate_hi = 2.7, 2.8  # the T24 plate, 2.8 +0/-0.1
    assert spec.PILOT_LENGTH_FITTED_MIN == pytest.approx(
        plate_lo + min(spec.PILOT_PROUD_RANGE)
    )
    assert spec.PILOT_LENGTH_FITTED_MAX == pytest.approx(
        plate_hi + max(spec.PILOT_PROUD_RANGE)
    )
    assert (spec.PILOT_LENGTH_FITTED_MIN, spec.PILOT_LENGTH_FITTED_MAX) == (
        pytest.approx((2.75, 2.95))
    )
    assert (
        spec.PILOT_LENGTH_FITTED_MIN
        <= spec.PILOT_LENGTH
        <= spec.PILOT_LENGTH_FITTED_MAX
    )
    assert spec.PILOT_LENGTH == pytest.approx(2.8 + 0.10)
    assert (
        spec.PILOT_BLANK_LENGTH_MIN
        >= spec.PILOT_LENGTH_FITTED_MAX + spec.FACING_ALLOWANCE - 1e-9
    )
    assert f"{spec.PILOT_BLANK_LENGTH_MIN:.2f} MIN" in spec.DRAWING_NOTES
    callout = drawing.DIMENSION_CALLOUTS_BELOW["PilotLength"]
    fitted = f"{spec.PILOT_LENGTH_FITTED_MIN:.2f}-{spec.PILOT_LENGTH_FITTED_MAX:.2f}"
    assert fitted in callout
    assert "FACED TO FIT" in callout


def test_the_pilot_length_callout_points_at_its_facing_step() -> None:
    """The pilot is faced before the collar is pinned; the pointer follows
    any renumbering."""
    assert drawing.FIT_STEP_KEY == "pilot-faced-to-fit"
    assert steps.step_number(drawing.FIT_STEP_KEY) < steps.step_number(
        "collar-pinned"
    )
    callout = drawing.DIMENSION_CALLOUTS_BELOW["PilotLength"]
    assert callout.endswith(f"PER {steps.step_ref(drawing.FIT_STEP_KEY)}")


def test_the_thumbnut_bears_on_the_pilot_and_the_t24_floats() -> None:
    # Pilot 9.90 min over the nut's countersink: an annulus of bearing.
    assert spec.NUT_PILOT_BEARING_WORST == pytest.approx(1.575)
    assert spec.NUT_PILOT_BEARING_WORST > 0.0
    assert min(spec.T24_FLOAT_RANGE) > 0.0
    # Negative control: a pilot faced flush with the T24 leaves no float.
    assert spec.PILOT_LENGTH_FITTED_MIN - min(spec.PILOT_PROUD_RANGE) - 2.7 <= 0.0


def test_setting_and_rearward_travel() -> None:
    # The forward travel stops where the cross hole would meet the relief.
    assert spec.SEAT_MAX_FROM_F == pytest.approx(6.90)
    assert spec.SEAT_MAX_FROM_F == pytest.approx(
        spec.SET_NOMINAL + spec.FORWARD_TRAVEL_MAX
    )
    # 6.2 - 4.0 = 2.2; the .XXX length moves it 2.07 .. 2.33.
    assert spec.REARWARD_TRAVEL_NOMINAL == pytest.approx(2.2)
    assert spec.REARWARD_TRAVEL_RANGE == pytest.approx((2.07, 2.33))
    assert min(spec.REARWARD_TRAVEL_RANGE) > 0.0
    # Negative control: a collar as long as the plain core cannot move back.
    assert spec.SET_NOMINAL - shaft.PLAIN_CORE < 0.0


def test_sheet_notes_print_the_floored_worst_walls_then_the_fit_up() -> None:
    notes = spec.DRAWING_NOTES.splitlines()
    assert notes[:4] == [
        f"DRIVE-PIN HOLE TO COLLAR RIM {spec.DRIVE_PIN_COLLAR_RIM_WORST:.2f} MIN.",
        f"PILOT WALL {spec.PILOT_WALL_WORST:.2f} MIN.",
        f"SLOT FLOOR TO FRONT FACE {spec.SLOT_FLOOR_WALL_WORST:.2f} MIN.",
        f"SUPPLY THE PILOT {spec.PILOT_BLANK_LENGTH_MIN:.2f} MIN LONG.",
    ]
    # A MIN never rounds up past the arithmetic; control: rounding would.
    assert spec.floor_2(0.489) == pytest.approx(0.48)
    assert round(0.489, 2) > spec.floor_2(0.489)
    assert spec.floor_2(1.97) == pytest.approx(1.97)
    # R9-29: the collar ships unpinned, so its sheet carries the whole fit-up
    # instruction the assembly prints, with the spec's seat maximum and drill.
    assert notes[4:] == spec.FIT_UP_NOTE.splitlines()
    assert "THE THUMBNUT SEATS ON THE PILOT" in " ".join(notes[4:])
    assert f"T24 SEAT {spec.SEAT_MAX_FROM_F:.2f}" in spec.DRAWING_NOTES
    assert (
        f"\u00d8{cross_pin.HOLE_DIA:.1f} +{cross_pin.HOLE_BAND[0]:.2f}/0 THROUGH"
        in spec.CROSS_PIN_DRILL_PHRASE
    )
    flowed = " ".join(spec.FIT_UP_NOTE.split())
    for phrase in (
        spec.FIT_UP_OFFSET_SET_TEXT,
        spec.CROSS_PIN_DRILL_PHRASE,
        spec.STUD_CUT_PHRASE,
    ):
        assert phrase in flowed, phrase


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
    right, bottom, top = _notes_box(spec.DRAWING_NOTES, left, top)
    assert left > BORDER and right < template.title_block_left_m
    assert bottom > BORDER
    # The notes stay below both orthographic views' silhouettes.
    assert top < min(drawing.END_CENTER[1], drawing.SIDE_CENTER[1]) - drawing.HALF_OD
    # Negative control: two more fit-up lines run the block into the border.
    _, longer, _ = _notes_box(spec.DRAWING_NOTES + "\nX\nX", left, top)
    assert longer < BORDER


def test_volume_gate_strip_area_is_a_disc_band() -> None:
    radius = spec.OD / 2.0
    assert part._strip_area(radius, radius) == pytest.approx(math.pi * radius**2)
    # The thin-band limit is the chord's rectangle, 2r wide.
    assert part._strip_area(radius, 1e-4) == pytest.approx(
        2.0 * radius * 2e-4, rel=1e-6
    )
    assert 0.0 < part.V_TOTAL < part.V_COLLAR + part.V_PILOT


def test_registry_row_is_the_turned_brass_mha_152() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-022"
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
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
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


def test_native_slot_witness_cannot_strike_through_its_tolerance_stack() -> None:
    # R11 actual SlotWidth ink, including the +0.1/0.0 rows, not a centred
    # nominal-only estimate. The lower horizontal witness strikes the ink.
    ink = annotation_ink_from_record(
        {
            "type": 4,
            "display": {
                "texts": [
                    {"t": " 1.8 ", "pos": [0.1973806, 0.1605278, 0], "h": 0.0035},
                    {"t": "+", "pos": [0.2064319, 0.165, 0], "h": 0.0035},
                    {"t": "0.1", "pos": [0.2092611, 0.165, 0], "h": 0.0035},
                    {"t": "0.0", "pos": [0.2092611, 0.1604743, 0], "h": 0.0035},
                ],
                "lines": [
                    [0, 0, 0, 0, 0.2274, 0.1614, 0, 0.2062, 0.1614, 0]
                ],
            },
        },
        label="SlotWidth",
    )
    assert ink.row_count == 2
    with pytest.raises(RuntimeError):
        require_annotation_clear(ink, [ink], check_own_lines=True)


@pytest.mark.parametrize("reverse", [False, True])
def test_native_collar_witness_cannot_cross_the_pilot_fit_block(reverse) -> None:
    # R11 measured nominal row and actual CollarLength witness. The guard
    # must work when either the fit block or the witness is the selected ink.
    fit = annotation_ink_from_record(
        {
            "type": 4,
            "display": {
                "texts": [
                    {"t": "2.90", "pos": [0.2384743, 0.1235562, 0], "h": 0.0035}
                ]
            },
        },
        label="PilotLength",
    )
    witness = annotation_ink_from_record(
        {
            "type": 4,
            "display": {
                "lines": [
                    [0, 0, 0, 0, 0.2372, 0.199, 0, 0.2372, 0.0902219, 0]
                ]
            },
        },
        label="CollarLength witness",
        allow_no_text=True,
    )
    selected, neighbour = (witness, fit) if reverse else (fit, witness)
    with pytest.raises(RuntimeError):
        require_annotation_clear(selected, [neighbour])


def test_leading_blank_cannot_falsely_place_native_length_text_inside_a_field() -> None:
    # The actual native start of R11's " 4.000 " is conservative containment
    # ink even when the ordinary collision rows skip the leading blank.
    ink = annotation_ink_from_record(
        {
            "type": 4,
            "display": {
                "texts": [
                    {"t": " 4.000 ", "pos": [0.2220882, 0.0912219, 0], "h": 0.0035}
                ]
            },
        },
        label="CollarLength",
    )
    assert ink.text[0] == pytest.approx(0.2220882)
    assert ink.rows[0][0] > 0.223
    with pytest.raises(RuntimeError):
        require_annotation_in_field(ink, (0.223, 0.090, 0.260, 0.099))
