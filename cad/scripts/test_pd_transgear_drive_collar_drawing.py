"""Offline contracts for the transgear drive collar (MHA-PD-022) and its drawing."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_pd_transgear_drive_collar as part
import draw_pd_transgear_drive_collar as drawing
import pd_paper_drive_assembly_steps as steps
import pd_transgear_drive_collar_spec as spec
import pd_transgear_knob_shaft_spec as shaft
import pd_transgear_removable_spec as removable
from _assembly_contract import assembly_contract
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _printed_tolerance import printed_band_mm

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


def test_turned_diameters_and_lengths_print_on_the_side_view() -> None:
    # Rule 7: the turned outline and fitted lengths print on the axial cut.
    body = spec.DRAWING_DIMENSIONS["BodyProfile"]
    assert body == {"CollarDia", "CollarLength", "PilotDia", "PilotLength"}
    assert body <= set(drawing.SIDE_KEEP)
    assert spec.OVERALL_LENGTH == pytest.approx(spec.LENGTH + spec.PILOT_LENGTH)
    # Both lengths share one row under the section, above the native
    # "SECTION A-A" label (16.6 mm under the view); the overall reads above.
    rows = {drawing.SIDE_KEEP[n][1] for n in ("CollarLength", "PilotLength")}
    assert len(rows) == 1
    (row,) = rows
    view_bottom = drawing.SIDE_CENTER[1] - drawing.HALF_OD
    assert view_bottom - 0.016 < row < view_bottom
    assert drawing.OVERALL_TEXT_XY[1] > drawing.SIDE_CENTER[1] + drawing.HALF_OD
    # The pilot's length text stands right of its own short span.
    assert drawing.SIDE_KEEP["PilotLength"][0] > drawing._PILOT_X + 0.0145
    # Both diameters read right of the pilot face, the O.D. outboard.
    assert drawing.SIDE_KEEP["CollarDia"][0] > drawing.SIDE_KEEP["PilotDia"][0] + 0.026
    assert drawing.SIDE_KEEP["PilotDia"][0] > drawing._PILOT_X
    # The rear entry break's text ends left of the overall's rear witness.
    assert drawing.SIDE_KEEP["BoreEntryBreak"][0] + 0.030 < drawing._REAR_X


class _SideViewSeat:
    """The actual axial section's end edges, built from the same source.

    Sheet right is model -Z and up is +Y. The rear annulus starts beyond
    the physical entry break; picking inside it is bore/chamfer air.
    A pick lands on a line within half a sheet millimetre.
    """

    TOLERANCE_M = 0.0005

    def __init__(self) -> None:
        od_r, pilot_r = spec.OD / 2.0, spec.PILOT_DIA / 2.0
        bore_r = spec.BORE_DIA / 2.0
        length, pilot = spec.LENGTH, spec.PILOT_LENGTH
        # (kind, (z, y), (z, y)) in model millimetres.
        self.segments = [
            ("EDGE", (-pilot, bore_r), (-pilot, pilot_r)),  # true D opening
            ("EDGE", (-pilot, -pilot_r), (-pilot, -spec.FLAT_TO_AXIS)),
            ("EDGE", (0.0, pilot_r), (0.0, od_r)),  # exposed seat annulus
            ("EDGE", (0.0, -od_r), (0.0, -pilot_r)),
            ("EDGE", (length, bore_r + spec.BORE_ENTRY_BREAK), (length, od_r)),
            ("EDGE", (length, -od_r), (length, -spec.FLAT_TO_AXIS - spec.BORE_ENTRY_BREAK)),
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

    # Negative control: on the axis the rear face is the D-bore's air.
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


def test_true_d_sizes_are_not_a_full_round_hole_or_an_unlocated_flat() -> None:
    assert spec.DRAWING_DIMENSIONS["BoreProfile"] == {"BoreDia", "FlatToAxis"}
    assert {"BoreDia", "FlatToAxis"} <= set(drawing.END_KEEP)
    assert spec.BORE_DIA == pytest.approx(4.860)
    assert spec.BORE_DIA_BAND == pytest.approx((0.012, 0.0))
    assert spec.FLAT_TO_AXIS == pytest.approx(2.1525)
    assert spec.FLAT_LIMITS == pytest.approx((2.145, 2.160))
    assert spec.FLAT_BAND == pytest.approx((0.0075, -0.0075))
    assert spec.FLAT_TOL_TYPE == 3
    assert spec.FLAT_CLEARANCE == pytest.approx((0.020, 0.050))
    assert spec.STUD_D_BORE_AIR == pytest.approx(0.085)
    # The source gate, not a test-only reimplementation, refuses a round
    # stud which fits the diameter but cannot pass the retained D-flat.
    assert 2.0 * (spec.FLAT_TO_AXIS + min(spec.FLAT_BAND)) < spec.BORE_DIA


def _fresh_collar_spec():
    fresh_spec = importlib.util.spec_from_file_location("_collar_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_d_fit_refuses_round_and_flat_binding_independently(monkeypatch) -> None:
    assert _fresh_collar_spec().BORE_CORE_CLEARANCE == pytest.approx((0.010, 0.030))
    monkeypatch.setattr(shaft, "CORE_DIA_BAND", (0.020, 0.0))
    with pytest.raises(AssertionError, match="bore binds"):
        _fresh_collar_spec()
    monkeypatch.undo()
    monkeypatch.setattr(shaft, "CORE_FLAT_BAND", (0.040, 0.0))
    with pytest.raises(AssertionError, match="D-flat binds"):
        _fresh_collar_spec()


def test_round_stud_must_pass_the_actual_d_flat(monkeypatch) -> None:
    monkeypatch.setattr(shaft, "THREAD_BLANK_LIMITS", (4.30, 4.40))
    with pytest.raises(AssertionError, match="stud cannot pass"):
        _fresh_collar_spec()


def test_fits_carry_named_bands_and_the_lengths_print_their_places() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BodyProfile", "CollarDia"): "*deviations(OD_BAND)",
        ("BodyProfile", "PilotDia"): "*deviations(PILOT_DIA_BAND)",
        ("BoreProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
        ("RearBoreChamfer", "BoreEntryBreak"): "*deviations(BORE_ENTRY_BREAK_BAND)",
        ("PinHoleProfile", "PinPosDia"): "*deviations(PIN_HOLE_BAND)",
        ("PinHoleProfile", "PinPosY"): "PIN_OFFSET_TOL",
        ("PinHoleProfile", "PinNegY"): "PIN_OFFSET_TOL",
    }
    # The seat O.D. and the drive-pin layout are the crank spigot's, so the
    # removable wheels fit either shaft.
    assert spec.OD == removable.SEAT_SPIGOT_DIA
    assert spec.PIN_CIRCLE_RADIUS == removable.PIN_CIRCLE_RADIUS
    assert spec.PIN_HOLE_DIA == removable.DRIVE_PIN_HOLE_DIA
    assert spec.DRAWING_PRECISION_BY_NAME["CollarLength"] == 2
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
    assert spec.PILOT_WALL == pytest.approx((10.0 - 4.860) / 2.0)
    assert spec.PILOT_WALL_WORST == pytest.approx(2.51)
    assert spec.PILOT_WALL_WORST >= 2.0
    # Negative control: a pilot narrower than the D-bore leaves no wall.
    assert (spec.BORE_DIA - (spec.BORE_DIA + max(spec.BORE_DIA_BAND))) / 2.0 < 0.0



def test_drive_pin_holes_clear_the_bore_and_the_pilot() -> None:
    # The unchanged dowel circle clears the smaller D-bore and pilot.
    assert spec.BORE_PIN_WALL_WORST == pytest.approx(3.349)
    assert spec.BORE_PIN_WALL_WORST >= spec.WALL_FLOOR
    assert spec.PIN_HOLE_INNER_R_MIN == pytest.approx(5.785)
    assert spec.PIN_HOLE_INNER_R_MIN > spec.PILOT_R_MAX
    # Negative controls: holes on a 6.0 radius break into the pilot; on the
    # pilot's own 5.0 radius they leave 0.605 to the bore.
    assert 6.0 - 0.025 - 1.19 < spec.PILOT_R_MAX
    assert 4.0 - 0.025 - 1.19 - (spec.BORE_DIA + max(spec.BORE_DIA_BAND)) / 2.0 < spec.WALL_FLOOR


def test_bore_slides_on_the_core_and_the_pilot_in_the_wheel() -> None:
    assert spec.BORE_CORE_CLEARANCE == pytest.approx((0.010, 0.030))
    # Radial: (10.3 - 10.0) / 2 and (10.3 + 0.10 - 9.90) / 2.
    assert spec.PILOT_BORE_CLEARANCE == pytest.approx((0.15, 0.25))
    # Negative controls: a press-type bore band binds on the core; a pilot
    # at the wheel's bore size has no air.
    press_bore = spec.BORE_DIA - 0.020 - (shaft.CORE_DIA + max(shaft.CORE_DIA_BAND))
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
    assert f"{spec.PILOT_BLANK_LENGTH_MIN:.2f} MIN" in drawing.FIT_NOTES
    fitted = f"{spec.PILOT_LENGTH_FITTED_MIN:.2f}-{spec.PILOT_LENGTH_FITTED_MAX:.2f}"
    assert fitted in drawing.FIT_NOTES
    assert "FACED TO FIT" in drawing.FIT_NOTES
    assert drawing.DIMENSION_CALLOUTS_BELOW["PilotLength"] == (
        f"SEE NOTE {drawing.PILOT_NOTE}"
    )


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
    # The part's own notes are 1 and 2; the fit notes continue the list.
    assert spec.DRAWING_NOTES.splitlines()[-1].startswith("2. ")
    assert (drawing.PILOT_NOTE, drawing.BODY_NOTE) == (3, 4)


def test_the_thumbnut_bears_on_the_pilot_and_the_knob_wheel_floats() -> None:
    # The nut's rear countersink leaves a real annulus on the pilot.
    assert spec.NUT_PILOT_BEARING_WORST == pytest.approx((9.90 - 4.566) / 2.0)
    assert spec.NUT_PILOT_BEARING_WORST > 0.0
    assert min(spec.KNOB_FLOAT_RANGE) > 0.0
    # Negative control: a pilot faced flush with the wheel leaves no float.
    assert spec.PILOT_LENGTH_FITTED_MIN - min(spec.PILOT_PROUD_RANGE) - 2.7 <= 0.0


def test_body_rear_face_reacts_at_f_over_the_whole_fitted_domain() -> None:
    assert spec.LENGTH == pytest.approx(6.2)
    assert (spec.LENGTH_FITTED_MIN, spec.LENGTH_FITTED_MAX) == pytest.approx((3.87, 6.9))
    assert spec.BODY_REAR_FACE_FROM_F == 0.0
    assert spec.BODY_BLANK_LENGTH_MIN >= spec.LENGTH_FITTED_MAX + spec.FACING_ALLOWANCE
    assert drawing.BODY_FIT_STEP_KEY == "collar-rear-faced-to-fit"
    assert drawing.DIMENSION_CALLOUTS_BELOW["CollarLength"] == (
        f"SEE NOTE {drawing.BODY_NOTE}"
    )
    note = _note(drawing.BODY_NOTE)
    assert spec.BODY_LENGTH_CALLOUT.replace("\n", ", ") in note
    assert note.endswith(f"PER {steps.step_ref(drawing.BODY_FIT_STEP_KEY)}.")
    assert "SEATED ON GEAR FRONT F" in note
    assert f"{spec.BODY_BLANK_LENGTH_MIN:.3f} MIN" in note
    assert spec.THUMBNUT_ENGAGEMENT_WORST >= shaft.ENGAGEMENT_FLOOR_D * shaft.THREAD_MAJOR
    assert spec.FRONT_BEARING_AREA_MIN > 0.0
    assert spec.NUT_CORE_STEP_AIR > 0.0


def test_notes_and_recipe_have_no_obsolete_front_pin_or_slot() -> None:
    notes = f"{spec.DRAWING_NOTES}\n{drawing.FIT_NOTES}"
    assert f"{spec.DRIVE_PIN_COLLAR_RIM_WORST:.2f} MIN" in notes
    assert f"{spec.BODY_BLANK_LENGTH_MIN:.3f} MIN" in notes
    # Rule 6: four numbered notes, no method words in the bore callout.
    assert [line[:3] for line in notes.splitlines() if not line.startswith(" ")] == [
        "1. ", "2. ", "3. ", "4. "
    ]
    assert "BROACH" not in spec.BORE_CALLOUT and "EDM" not in spec.BORE_CALLOUT
    assert drawing.NOTES_TEXT.startswith('$PRPSHEET:"Manufacturing Notes"\n3. ')
    for path in (part.__file__, drawing.__file__, spec.__file__):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any("collar_cross_pin" in name for name in imports)
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


def test_volume_gate_uses_the_true_major_arc_area() -> None:
    radius, flat = spec.BORE_DIA / 2.0, spec.FLAT_TO_AXIS
    segment = radius**2 * math.acos(flat / radius) - flat * math.sqrt(radius**2 - flat**2)
    assert part._d_bore_area(radius, flat) == pytest.approx(math.pi * radius**2 - segment)
    assert part.V_BORE < math.pi * radius**2 * (spec.LENGTH + spec.PILOT_LENGTH)
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


def test_saved_body_length_is_native_reference_not_a_fixed_size(monkeypatch) -> None:
    display = _ReferenceDisplay()
    dimension = SimpleNamespace(
        SystemValue=spec.LENGTH / 1000.0,
        Tolerance=SimpleNamespace(Type=0),
    )
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (display, dimension))
    part._collar_length_reference(object())
    assert (display.GetText(1), display.GetText(2)) == ("(", ")")
    assert dimension.Tolerance.Type == 0


def test_body_reference_refuses_a_void_setter_that_does_not_persist(monkeypatch) -> None:
    display = _ReferenceDisplay(persists=False)
    dimension = SimpleNamespace(
        SystemValue=spec.LENGTH / 1000.0,
        Tolerance=SimpleNamespace(Type=0),
    )
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (display, dimension))
    with pytest.raises(RuntimeError, match="reference"):
        part._collar_length_reference(object())


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
        part._collar_length_reference(object())


def test_body_reference_refuses_method_shaped_text_readback(monkeypatch) -> None:
    display = _ReferenceDisplay()
    display.GetText = lambda _which: display.SetText
    dimension = SimpleNamespace(
        SystemValue=spec.LENGTH / 1000.0,
        Tolerance=SimpleNamespace(Type=0),
    )
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (display, dimension))
    with pytest.raises(RuntimeError, match="reference"):
        part._collar_length_reference(object())


def test_construction_witness_requires_a_native_true_property(monkeypatch) -> None:
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)

    class Segment:
        def __init__(self, persist: bool) -> None:
            self.persist = persist
            self.construction = False

        @property
        def ConstructionGeometry(self) -> bool:
            return self.construction

        @ConstructionGeometry.setter
        def ConstructionGeometry(self, value: bool) -> None:
            if self.persist:
                self.construction = value

    segment = Segment(True)
    part._as_construction(SimpleNamespace(_sketch_entities={"witness": segment}), "witness")
    assert segment.ConstructionGeometry is True
    with pytest.raises(RuntimeError, match="construction"):
        part._as_construction(
            SimpleNamespace(_sketch_entities={"witness": Segment(False)}), "witness"
        )


class _LimitTolerance:
    def __init__(self, *, persists: bool = True, accepts: bool = True) -> None:
        self.Type = 0
        self.minimum = self.maximum = 0.0
        self.persists, self.accepts = persists, accepts

    def SetValues(self, minimum: float, maximum: float) -> bool:
        if self.persists:
            self.minimum, self.maximum = minimum, maximum
        return self.accepts

    def GetMinValue(self) -> float:
        return self.minimum

    def GetMaxValue(self) -> float:
        return self.maximum


class _LimitsDisplay:
    def SetPrecision3(self, primary: int, dual: int, tolerance: int, dual_tol: int) -> int:
        assert (primary, dual, tolerance, dual_tol) == (3, -1, 3, -1)
        self.tolerance_precision = tolerance
        return 0

    def GetPrimaryTolPrecision2(self) -> int:
        return self.tolerance_precision


def _native_flat_limits(monkeypatch, tolerance) -> None:
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        part, "_named_dimension",
        lambda *_args: (_LimitsDisplay(), SimpleNamespace(
            SystemValue=spec.FLAT_TO_AXIS / 1000.0, Tolerance=tolerance,
        )),
    )
    part._flat_limits(object())


def test_actual_d_flat_midpoint_carries_native_limits(monkeypatch) -> None:
    tolerance = _LimitTolerance()
    _native_flat_limits(monkeypatch, tolerance)
    assert tolerance.Type == spec.FLAT_TOL_TYPE
    assert (
        spec.FLAT_TO_AXIS + tolerance.GetMinValue() * 1000.0,
        spec.FLAT_TO_AXIS + tolerance.GetMaxValue() * 1000.0,
    ) == pytest.approx(spec.FLAT_LIMITS)


@pytest.mark.parametrize(
    "tolerance, message",
    [(None, "tolerance"), (_LimitTolerance(accepts=False), "rejected"),
     (_LimitTolerance(persists=False), "persist")],
)
def test_native_flat_limits_refuse_missing_or_unwritten_controls(
    monkeypatch, tolerance, message
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _native_flat_limits(monkeypatch, tolerance)


def _capture_fixture(monkeypatch, *, length=None, rear_gap=0.0, clock_error=0.0, missing=None):
    import build_pd_paper_drive_assembly as assembly
    import _part_pmi

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
        monkeypatch.setattr(_part_pmi, "_early_bound", lambda value, _kind: value)
    else:
        monkeypatch.setattr(_part_pmi, "_resolve_faces", lambda _model, requests: requests)
    calls = []

    def world_point(_adapter, name, local):
        calls.append((name, tuple(local)))
        if name == "collar":
            return (
                math.sin(clock_error) * -local[1],
                math.cos(clock_error) * local[1],
                assembly.KNOB_COLLAR_Z0 + local[2] + rear_gap,
            )
        return (local[0], local[1], assembly.KNOB_SHAFT_Z0 + local[2])

    monkeypatch.setattr(assembly, "world_point", world_point)
    adapter = SimpleNamespace(currentModel=native)
    assembly._assert_knob_collar_capture(adapter, "collar", "shaft")
    return calls


def test_actual_native_collar_rear_face_is_measured_on_f(monkeypatch) -> None:
    calls = _capture_fixture(monkeypatch)
    assert ("collar", (0.0, 0.0, spec.LENGTH)) in calls
    assert ("shaft", (0.0, 0.0, 0.0)) in calls
    assert ("collar", (0.0, -1.0, 0.0)) in calls


@pytest.mark.parametrize(
    "kwargs, message",
    [({"rear_gap": 0.01}, "not on gear F"),
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


def _native_entry(
    monkeypatch, *, selected=True, missing=None, distance=None,
    angle_deg=spec.BORE_ENTRY_BREAK_ANGLE_DEG, chamfer_type=1, linked_distance=None,
):
    from solidworks_mcp.adapters.solidworks import features
    from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

    calls = []

    def select(_adapter, points, *, tol_mm):
        assert points == [[0.0, part.BORE_R, spec.LENGTH], [0.0, -spec.FLAT_TO_AXIS, spec.LENGTH]]
        assert tol_mm == 0.001
        return selected

    class Definition:
        @property
        def Type(self) -> int:
            return chamfer_type

        @property
        def EdgeChamferAngle(self) -> float:
            return math.radians(angle_deg)

        def GetEdgeChamferDistance(self, side: int) -> float:
            assert side == 0  # only side 0 is documented for angle-distance
            value = spec.BORE_ENTRY_BREAK if distance is None else distance
            return value / 1000.0

    class Feature:
        def __bool__(self):
            raise AssertionError("VT_DISPATCH must not be truth-tested")

        def GetDefinition(self):
            return None if missing == "definition" else Definition()

    class Adapter:
        currentModel = SimpleNamespace(
            FeatureManager=None if missing == "manager" else object()
        )

        async def add_chamfer(self, distance, edge_points, *, tangent_propagation):
            calls.append((distance, edge_points, tangent_propagation))
            if missing == "feature":
                return AdapterResult(
                    status=AdapterResultStatus.ERROR, error="native chamfer failed"
                )
            return AdapterResult(status=AdapterResultStatus.SUCCESS, data=Feature())

    monkeypatch.setattr(features, "_select_edges_geometric", select)
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(part, "name_last_feature", lambda _adapter, name: name)
    monkeypatch.setattr(
        part, "_feature_by_name",
        lambda _adapter, name: None if missing == "native feature" else Feature(),
    )
    monkeypatch.setattr(part, "name_dimensions", lambda _adapter, _feature, names: names)
    monkeypatch.setattr(
        part, "_named_dimension",
        lambda _adapter, _feature, _name: (
            None,
            None if missing == "linked dimension" else SimpleNamespace(
                SystemValue=(
                    spec.BORE_ENTRY_BREAK if linked_distance is None else linked_distance
                ) / 1000.0
            ),
        ),
    )
    result = asyncio.run(part._rear_bore_chamfer(Adapter()))
    assert result == ["BoreEntryBreak"]
    assert calls == [(
        spec.BORE_ENTRY_BREAK,
        [[0.0, part.BORE_R, spec.LENGTH], [0.0, -spec.FLAT_TO_AXIS, spec.LENGTH]],
        False,
    )]


def test_native_rear_entry_has_both_actual_legs_on_both_d_edges(monkeypatch) -> None:
    _native_entry(monkeypatch)
    assert (
        spec.BORE_ENTRY_BREAK + min(spec.BORE_ENTRY_BREAK_BAND),
        spec.BORE_ENTRY_BREAK + max(spec.BORE_ENTRY_BREAK_BAND),
    ) == pytest.approx((0.150, 0.250))
    assert spec.DRAWING_DIMENSIONS["RearBoreChamfer"] == {"BoreEntryBreak"}
    assert "BOTH LEGS" in drawing.DIMENSION_CALLOUTS_BELOW["BoreEntryBreak"]
    assert drawing.DIMENSION_CALLOUTS_BELOW["BoreEntryBreak"] == spec.BORE_ENTRY_BREAK_CALLOUT
    assert spec.BORE_ENTRY_BREAK_CALLOUT.splitlines()[0] == "X 45 DEG"
    assert spec.BORE_ENTRY_BREAK_ANGLE_BAND_DEG == _config.title_block("angular")["value_deg"]
    assert spec.BORE_ENTRY_BREAK_ANGLE_LIMITS == pytest.approx((44.0, 46.0))
    assert spec.BORE_ENTRY_BREAK_LEG_MIN == pytest.approx(0.144853316221)
    assert spec.BORE_ENTRY_BREAK_LEG_MAX == pytest.approx(0.258882578448)
    # The single native width and read-back 45-degree angle bound both legs.
    assert spec.BORE_ENTRY_BREAK == pytest.approx(
        shaft.FRONT_CORNER_RADIUS_MAX
        + max(spec.BORE_ENTRY_BREAK_BAND) - min(spec.BORE_ENTRY_BREAK_BAND)
    )
    assert spec.BORE_ENTRY_BREAK_REQUIRED_MIN == pytest.approx(0.080)
    assert spec.BORE_ENTRY_FLAT_EDGE_MIN == pytest.approx(2.226477037834)
    assert spec.BORE_ENTRY_ARC_EDGE_MIN == pytest.approx(12.890700407832)
    assert spec.BORE_ENTRY_AXIAL_SPAN_MIN == pytest.approx(3.870)
    assert spec.BORE_ENTRY_PROFILE_DEPTH_MIN == pytest.approx(0.270)
    assert spec.BORE_ENTRY_BREAK_GEOMETRY_MAX == pytest.approx(0.270)
    assert spec.BORE_ENTRY_WALL_WORST == pytest.approx(3.090117421552)
    assert spec.NECK_CORNER_D_BORE_AIR_MIN == pytest.approx(0.064853316221)
    assert spec.D_DRIVE_AREA_MIN == pytest.approx(7.339179692138)
    assert spec.D_SUPPORT_LENGTH_MIN == pytest.approx(4.072234843105)
    assert spec.D_AXIS_AT_F_FROM_JOURNAL_MAX == pytest.approx(0.058542058772)
    assert spec.BORE_ENTRY_BREAK_LEG_MIN > spec.BORE_ENTRY_BREAK_REQUIRED_MIN
    assert spec.BORE_ENTRY_BREAK_LEG_MAX < spec.BORE_ENTRY_BREAK_GEOMETRY_MAX
    for width in (spec.BORE_ENTRY_BREAK_MIN, spec.BORE_ENTRY_BREAK_MAX):
        for angle in spec.BORE_ENTRY_BREAK_ANGLE_LIMITS:
            for leg in (width, width * math.tan(math.radians(angle))):
                assert spec.BORE_ENTRY_BREAK_LEG_MIN - 1e-12 <= leg
                assert leg <= spec.BORE_ENTRY_BREAK_LEG_MAX + 1e-12
                assert leg > spec.BORE_ENTRY_BREAK_REQUIRED_MIN
                assert leg < spec.BORE_ENTRY_BREAK_GEOMETRY_MAX
    for diameter in (
        spec.BORE_DIA + min(spec.BORE_DIA_BAND),
        spec.BORE_DIA + max(spec.BORE_DIA_BAND),
    ):
        radius = diameter / 2.0
        for flat in spec.FLAT_LIMITS:
            chord = 2.0 * math.sqrt(radius**2 - flat**2)
            arc = 2.0 * radius * (math.pi - math.acos(flat / radius))
            assert chord >= spec.BORE_ENTRY_FLAT_EDGE_MIN - 1e-12
            assert arc >= spec.BORE_ENTRY_ARC_EDGE_MIN - 1e-12
            assert flat + spec.BORE_ENTRY_BREAK_LEG_MAX < radius


@pytest.mark.parametrize(
    "kwargs, message",
    [({"selected": False}, "resolve"),
     ({"missing": "manager"}, "manager"),
     ({"missing": "feature"}, "failed"),
     ({"missing": "definition"}, "definition"),
     ({"missing": "native feature"}, "feature"),
     ({"chamfer_type": 2}, "angle-distance"),
     ({"angle_deg": 30.0}, "angle"),
     ({"distance": 0.010}, "leg 0"),
     ({"angle_deg": math.nan}, "angle"),
     ({"distance": math.nan}, "leg 0"),
     ({"missing": "linked dimension"}, "controlled native size"),
     ({"linked_distance": math.pi * 250.0}, "controlled native size"),
     ({"linked_distance": math.nan}, "controlled native size")],
)
def test_native_entry_refuses_missing_edge_feature_and_false_second_leg(
    monkeypatch, kwargs, message
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _native_entry(monkeypatch, **kwargs)


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


def test_actual_collar_section_has_rear_left_pilot_right_and_d_flat_below(monkeypatch):
    section = _CollarSection()
    _orient_collar_section(monkeypatch, section)
    assert section.reversed is True
    assert section.project((0.0, 0.0, 0.0)) == pytest.approx(
        (drawing._SEAT_X, drawing.SIDE_CENTER[1])
    )
    assert section.project((0.0, 0.0, spec.LENGTH / 1000.0))[0] == pytest.approx(drawing._REAR_X)
    assert section.project((0.0, 0.0, -spec.PILOT_LENGTH / 1000.0))[0] == pytest.approx(drawing._PILOT_X)
    assert section.project((0.0, -spec.FLAT_TO_AXIS / 1000.0, 0.0))[1] < drawing.SIDE_CENTER[1]


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
