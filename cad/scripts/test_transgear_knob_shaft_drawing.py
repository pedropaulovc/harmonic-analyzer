"""Offline contracts for the transgear knob shaft (MHA-078) and its drawing."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

import _config
import build_transgear_knob_shaft as part
import draw_transgear_knob_shaft as drawing
import transgear_arm_plate_geometry as plate
import transgear_knob_shaft_spec as spec
import transgear_knob_thrust_ring_spec as ring
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm

# The contract's machine stations (§1.1, round 10): F, the 12T's front face,
# stands at machine z -148.1 and the part's +Z is machine +Z.
F_MACHINE_Z = -148.1


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-knob-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-knob-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/transgear-knob-shaft_drawing.png")
    assert (
        DRAWINGS_BY_NAME["transgear_knob_shaft"].script
        == Path(drawing.__file__).resolve()
    )


def test_every_marked_dimension_is_placed_once_and_has_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert not set(drawing.SIDE_KEEP) & set(drawing.END_KEEP)
    assert set(drawing.SIDE_KEEP) | set(drawing.END_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


# Right of the view's centre a Ø's text hangs LEFT of its line.  The thread
# blank's banded text and shoulder run 27.5 mm, the shoulder 4.5 mm under the
# text point; an unbanded Ø's line rises to 2.8 mm under its text point, a
# banded one's less far (19e33c6c2).
_BLANK_SHOULDER_RUN_M = 0.0275
_BLANK_SHOULDER_DROP_M = 0.0045
_PLAIN_LINE_DROP_M = 0.0028


def test_the_thread_blank_shoulder_crosses_no_diameter_line() -> None:
    """The layout audit refuses a shoulder that crosses another dimension's
    line.  At 19e33c6c2 the blank's line stood at its land's mid and its
    shoulder ran across the relief Ø's line, which rises past it to its own
    text one step higher.  Every Ø line rising above the shoulder keeps 2 mm
    off it; the blank's line stands on its land, left of the thread
    callout's leader to the chamfer."""
    x, y = drawing.SIDE_KEEP["ThreadBlankDia"]
    assert x > drawing.SIDE_CENTER[0]
    left = x - _BLANK_SHOULDER_RUN_M
    shoulder_y = y - _BLANK_SHOULDER_DROP_M
    for name in ("OutsideDia", "CoreDia", "ReliefDia", "JournalDia"):
        line_x, text_y = drawing.SIDE_KEEP[name]
        if text_y - _PLAIN_LINE_DROP_M <= shoulder_y:
            continue
        gap = max(left - line_x, line_x - x)
        assert gap >= 0.002, (name, gap)
    assert drawing.THREAD_END_X < x < drawing.CHAMFER_START_X
    assert x + 0.002 <= drawing.THREAD_PICK[0]


# Default-format text, measured on r743-rocker-fix3's render (as
# test_transgear_arm_drawing uses them).
_CHAR_WIDTH = 0.00276


# Measured text boxes (8b5e1f354's PDF), relative to the keep point: a plain
# Ø's text runs 13.0 mm, a banded one's 30.2 mm, ending 1.3 mm short of its
# line on the side the text hangs; plain text spans -3.1..+3.2 mm about the
# point, banded -4.9..+6.0.  Right of the view's centre text hangs left.
_PLAIN_BOX = (-0.0143, -0.0031, -0.0013, 0.0032)
_BANDED_BOX = (-0.0315, -0.0049, -0.0013, 0.0060)
_DIAMETERS = ("OutsideDia", "CoreDia", "ReliefDia", "ThreadBlankDia", "JournalDia")


def _diameter_text_box(name: str) -> tuple[float, float, float, float]:
    banded = {key[1] for key in model_toleranced_dimensions(part)}
    x0, y0, x1, y1 = _BANDED_BOX if name in banded else _PLAIN_BOX
    x, y = drawing.SIDE_KEEP[name]
    if x < drawing.SIDE_CENTER[0]:
        x0, x1 = -x1, -x0
    return (x + x0, y + y0, x + x1, y + y1)


def test_no_diameter_text_overlaps_another_or_its_line() -> None:
    """Review of 8b5e1f354: the core's Ø8.350 text ran over the 12T's Ø9.36.
    Every pair of Ø texts keeps 1 mm of air, and no Ø line, rising from the
    axis to its own text, crosses another Ø's text."""
    boxes = {name: _diameter_text_box(name) for name in _DIAMETERS}
    for a in _DIAMETERS:
        ax0, ay0, ax1, ay1 = boxes[a]
        line_x = drawing.SIDE_KEEP[a][0]
        for b in _DIAMETERS:
            if a >= b:
                continue
            bx0, by0, bx1, by1 = boxes[b]
            air = max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1)
            assert air >= 0.001, (a, b, air)
        for b in _DIAMETERS:
            if b == a:
                continue
            bx0, by0, bx1, _ = boxes[b]
            assert not (bx0 <= line_x <= bx1 and by0 <= ay0), (a, b)


def test_the_journal_finish_leader_lands_on_the_journal_circle() -> None:
    """234a39c87: SolidWorks landed the finish's leader at the circle's
    bottom and crossed the whole end view; it lands at 60 degrees, under its
    symbol, on the journal circle and on the sheet."""
    attach = drawing.JOURNAL_FINISH_ATTACH
    radius = spec.JOURNAL_DIA * drawing._S / 2000.0
    centre = drawing.END_CENTER
    assert math.hypot(attach[0] - centre[0], attach[1] - centre[1]) == pytest.approx(
        radius, abs=1e-9
    )
    assert attach[1] > centre[1]
    assert attach[0] > 0.010


def test_the_end_view_stands_clear_of_the_side_views_rear_end() -> None:
    """The K-1 journal runs 6.5 further back; the side view's rear end must
    still clear the end view's journal circle."""
    assert drawing.END_CENTER[0] + drawing.HALF_OD + 0.005 < drawing.REAR_X



def test_sheet_authors_no_manufacturing_value() -> None:
    # Rule 2: places and bands come from the part; the sheet reads them back.
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_bands_come_from_named_spec_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("StudProfile", "CoreDia"): "*deviations(CORE_DIA_BAND)",
        ("StudProfile", "ThreadBlankDia"): "*deviations(THREAD_BLANK_DIA_BAND)",
        ("JournalProfile", "JournalDia"): "*deviations(JOURNAL_DIA_BAND)",
        ("StudProfile", "FullDepth"): "FULL_DEPTH_BAND",
    }
    # The journal length prints at the title block's .XXX: the knob float is
    # set at fit-up, the cup pinned on a feeler (R9-70 K-1), not held by it.
    assert spec.JOURNAL_LENGTH_PLACES == 3


def test_stations_land_on_the_contract_machine_stations() -> None:
    stations = {
        "stud tip": (spec.TIP_Z, -172.0),
        "full-thread end": (spec.THREAD_END_Z, -155.6),
        "12T rear tooth ends": (spec.PINION_REAR_Z, -142.2),
        "journal rear face": (spec.REAR_END_Z, -101.26),
    }
    for name, (local, machine) in stations.items():
        assert F_MACHINE_Z + local == pytest.approx(machine, abs=0.005), name
    assert spec.OVERALL_LENGTH == pytest.approx(70.74, abs=0.005)
    assert spec.THREAD_LENGTH_REF == pytest.approx(16.4)


def test_cup_face_station_spans_the_ring_the_plate_hub_and_the_float() -> None:
    """R9-25 / K-1: the cup's front face stands the thrust ring plus the
    plate's hub-to-boss plus the 0.2 end float behind the 12T's rear tooth
    ends, set on a feeler within ±0.05, so the float stays open with the ring
    and the hub at their long limits; the journal runs 6.5 on behind it."""
    assert spec.CUP_FACE_STATION == pytest.approx(
        ring.LENGTH + plate.HUB_TO_BOSS + spec.END_FLOAT
    )
    assert spec.END_FLOAT - spec.END_FLOAT_SET_TOL > 0.0
    assert spec.CUP_FACE_STATION_BAND == pytest.approx(
        ring.LENGTH_TOL + plate.HUB_TO_BOSS_BAND + spec.END_FLOAT_SET_TOL
    )
    assert spec.JOURNAL_LENGTH == pytest.approx(
        spec.CUP_FACE_STATION + spec.JOURNAL_REAR_EXTENSION
    )
    assert spec.REAR_END_Z == pytest.approx(spec.PINION_REAR_Z + spec.JOURNAL_LENGTH)
    # The journal behind the cup's front face at the printed worst case.
    reach = printed_band_mm(spec.JOURNAL_LENGTH_PLACES) + spec.CUP_FACE_STATION_BAND
    assert spec.JOURNAL_REAR_EXTENSION_MIN == pytest.approx(
        spec.JOURNAL_REAR_EXTENSION - reach
    )
    assert spec.JOURNAL_REAR_EXTENSION_MIN > 0.0


def _shaft_spec_with(monkeypatch, module, name: str, value):
    """A fresh execution of the knob-shaft spec with one upstream value patched."""
    monkeypatch.setattr(module, name, value)
    fresh_spec = importlib.util.spec_from_file_location(
        "_knob_shaft_perturbed", spec.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_cutter_window_holds_at_the_worst_case() -> None:
    """R9-21: full depth covers the disc's worst rear face, and the largest
    cutter's run-out ends inside the printed limit, in front of the hub bore."""
    assert spec.FULL_DEPTH_MIN >= spec.DISC_REAR_FROM_F_WORST
    assert spec.CUTTER_RUNOUT_END_WORST <= spec.CUTTER_RUNOUT_MAX
    assert spec.HUB_BORE_FROM_F_WORST - spec.CUTTER_RUNOUT_MAX >= 0.42
    # Negative control: a Ø1.75 in cutter at the deepest full-depth limit runs
    # out past the printed limit.
    big = 1.75 * spec.MM_PER_IN
    assert (
        spec.FULL_DEPTH_MAX + spec.cutter_runout(big, spec.RUNOUT_RISE_WORST)
        > spec.CUTTER_RUNOUT_MAX
    )


def test_run_out_limit_refuses_a_ring_that_brings_the_hub_bore_in(
    monkeypatch,
) -> None:
    clean = _shaft_spec_with(monkeypatch, ring, "LENGTH_TOL", ring.LENGTH_TOL)
    assert clean.HUB_BORE_FROM_F_WORST > clean.CUTTER_RUNOUT_MAX
    # Negative control: a ring band 0.5 wide pulls the hub bore to F + 10.47,
    # inside the printed run-out limit.
    with pytest.raises(AssertionError, match="hub bore"):
        _shaft_spec_with(monkeypatch, ring, "LENGTH_TOL", 0.5)


def test_cutter_stations_are_native_banded_model_dimensions() -> None:
    """Codex P2 on R9-21/R9-67: the full-depth window and the run-out limit
    print as the model's own dimensions, band and places on the part, not as
    numbers frozen into note text (policy rules 2 and 7)."""
    assert {"FullDepth", "CutterRunout"} <= spec.DRAWING_DIMENSIONS["StudProfile"]
    places = spec.DRAWING_PRECISION_BY_NAME
    assert places["FullDepth"] == spec.FULL_DEPTH_PLACES == 3
    assert places["CutterRunout"] == spec.CUTTER_RUNOUT_PLACES == 2
    # The window is the .XXX row's band; the run-out a MAX limit
    # (swTolType_e.swTolMAX) whose nominal is the limit it prints.
    assert spec.FULL_DEPTH_BAND == printed_band_mm(spec.FULL_DEPTH_PLACES)
    assert spec.CUTTER_RUNOUT_TOL_TYPE == 6
    lower, upper = spec.CUTTER_RUNOUT_DEVIATIONS
    assert upper == 0.0
    assert spec.CUTTER_RUNOUT_MAX + lower == pytest.approx(spec.FULL_DEPTH_MIN)
    # No number the model owns is retyped into the notes.
    lines = spec.DRAWING_NOTES.split("\n")
    for value in (f"{spec.FULL_DEPTH:.3f}", f"{spec.CUTTER_RUNOUT_MAX:.2f}"):
        assert value not in spec.DRAWING_NOTES, value
    assert spec.CUTTER_NOTE in lines
    assert f"\u00d8{spec.CUTTER_DIA_MAX_IN:.2f} in MAX" in spec.CUTTER_NOTE
    # One-line names, printed before the value on its own row.
    for prefix in (spec.FULL_DEPTH_PREFIX, spec.CUTTER_RUNOUT_PREFIX):
        assert "\n" not in prefix and prefix.endswith(" ")


# Each length below the side view: its two stations (model z) and its whole
# text, the cutter stations' with their prefixes.  Text centres on its keep
# point, _CHAR_WIDTH a character (8b5e1f354), the plain box's height.
_LENGTHS = {
    "CoreLength": ((0.0, -spec.CORE_LENGTH), f"{spec.CORE_LENGTH:.3f}"),
    "PlainCore": ((0.0, spec.THREAD_END_Z), f"{spec.PLAIN_CORE:.3f}"),
    "TipStation": ((0.0, spec.TIP_Z), f"{spec.TIP_STATION:.2f}"),
    "FaceWidth": ((0.0, spec.FACE_WIDTH), f"{spec.FACE_WIDTH:.3f}"),
    "JournalLength": (
        (spec.PINION_REAR_Z, spec.REAR_END_Z),
        f"{spec.JOURNAL_LENGTH:.3f}",
    ),
    "FullDepth": (
        (0.0, spec.FULL_DEPTH),
        f"{spec.FULL_DEPTH_PREFIX}{spec.FULL_DEPTH:.3f} "
        f"\u00b1{spec.FULL_DEPTH_BAND:.2f}",
    ),
    "CutterRunout": (
        (0.0, spec.CUTTER_RUNOUT_MAX),
        f"{spec.CUTTER_RUNOUT_PREFIX}{spec.CUTTER_RUNOUT_MAX:.2f} max.",
    ),
}
_TITLE_BLOCK_TOP, _TITLE_BLOCK_LEFT = 0.0649, 0.2183  # B sheet


def _length_text_box(name: str) -> tuple[float, float, float, float]:
    x, y = drawing.SIDE_KEEP[name]
    half = len(_LENGTHS[name][1]) * _CHAR_WIDTH / 2.0
    return (x - half, y + _PLAIN_BOX[1], x + half, y + _PLAIN_BOX[3])


def test_lengths_stack_without_text_on_a_foreign_extension_line() -> None:
    """Each side of F the lengths nest shortest innermost; no text stands on
    an extension line running to a deeper row; the cutter stations' prefixed
    text clears the border and the title block; and the only extension line
    crossing another length's dimension line is the run-out's over the
    journal length (two datums, F and the 12T's rear face)."""
    below = drawing.SIDE_CENTER[1] - drawing.HALF_OD
    rows = {n: xy for n, xy in drawing.SIDE_KEEP.items() if xy[1] < below - 0.005}
    assert set(rows) == set(_LENGTHS)
    for side in (1.0, -1.0):
        from_f = [
            n for n, ((z0, z1), _) in _LENGTHS.items() if z0 == 0.0 and side * z1 > 0.0
        ]
        by_row = sorted(from_f, key=lambda n: -rows[n][1])
        reach = [abs(_LENGTHS[n][0][1]) for n in by_row]
        assert reach == sorted(reach), by_row
    boxes = {n: _length_text_box(n) for n in rows}
    # A dimension line runs between its stations and on to text set outside.
    spans = {}
    for n, ((z0, z1), _) in _LENGTHS.items():
        xs = (drawing._sheet_x(z0), drawing._sheet_x(z1), *boxes[n][::2])
        spans[n] = (min(xs), max(xs))
    crossings = set()
    for deep, ((z0, z1), _) in _LENGTHS.items():
        for x in (drawing._sheet_x(z0), drawing._sheet_x(z1)):
            for inner, ((w0, w1), _) in _LENGTHS.items():
                if rows[inner][1] <= rows[deep][1]:
                    continue
                x0, _, x1, _ = boxes[inner]
                assert not x0 - 0.0005 < x < x1 + 0.0005, (inner, deep)
                # A shared station is one extension line, not a crossing.
                own = (drawing._sheet_x(w0), drawing._sheet_x(w1))
                lo, hi = spans[inner]
                if lo < x < hi and min(abs(x - o) for o in own) > 1e-9:
                    crossings.add((deep, inner))
    assert crossings == {("CutterRunout", "JournalLength")}
    names = sorted(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            ax0, ay0, ax1, ay1 = boxes[a]
            bx0, by0, bx1, by1 = boxes[b]
            air = max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1)
            assert air >= 0.001, (a, b, air)
    for name in ("FullDepth", "CutterRunout"):
        x0, y0, x1, _ = boxes[name]
        assert x0 > drawing.F_X + 0.002 and x1 < 0.4191 - 0.003, name
        assert x1 < _TITLE_BLOCK_LEFT or y0 > _TITLE_BLOCK_TOP + 0.002, name


def test_modelled_run_out_slots_stay_under_the_thrust_ring() -> None:
    assert spec.PINION_REAR_Z < spec.RUNOUT_SLOT_END_Z < spec.HUB_BORE_FROM_F_WORST
    # The slot's flat walls are the gap's width where the cutter leaves the
    # journal: wider than at the root, narrower than at the tips.
    root = spec.gap_chord(spec.ROOT_DIA / 2.0)
    tip = spec.gap_chord(spec.OUTSIDE_DIA / 2.0)
    assert root < spec.RUNOUT_SLOT_WIDTH < tip
    # At the pitch circle the gap is half the circular pitch.
    pitch_r = spec.PITCH_DIA / 2.0
    assert spec.gap_chord(pitch_r) == pytest.approx(
        2.0 * pitch_r * math.sin(math.pi / (2.0 * spec.TEETH))
    )
    assert 0.0 < part.V_RUNOUT_SLOT < part.V_JOURNAL / spec.TEETH


@pytest.mark.parametrize("swap", [False, True])
@pytest.mark.parametrize("flip_u", [1.0, -1.0])
@pytest.mark.parametrize("flip_v", [1.0, -1.0])
def test_cutter_arc_runs_counter_clockwise_round_the_rear(
    swap: bool, flip_u: float, flip_v: float
) -> None:
    """Whatever orientation the gap plane's sketch takes, the arc handed to
    the counter-clockwise ``CreateArc`` sweeps the cutter's rear side."""
    azimuth = math.radians(spec.GAP_AZIMUTH_DEG)

    def to_sketch(point: tuple[float, float, float]) -> tuple[float, float]:
        radial = point[0] * math.cos(azimuth) + point[1] * math.sin(azimuth)
        u, v = (point[2], radial) if swap else (radial, point[2])
        return (flip_u * u, flip_v * v)

    centre, start, end = part.cutter_arc_points(to_sketch)

    def ccw(a: tuple[float, float], b: tuple[float, float]) -> float:
        angle_a = math.atan2(a[1] - centre[1], a[0] - centre[0])
        angle_b = math.atan2(b[1] - centre[1], b[0] - centre[0])
        return (angle_b - angle_a) % math.tau

    rear = to_sketch(
        (
            spec.CUTTER_AXIS_R * math.cos(azimuth),
            spec.CUTTER_AXIS_R * math.sin(azimuth),
            spec.CUTTER_AXIS_Z + spec.CUTTER_DIA_MAX / 2.0,
        )
    )
    front = to_sketch(
        (
            spec.CUTTER_AXIS_R * math.cos(azimuth),
            spec.CUTTER_AXIS_R * math.sin(azimuth),
            spec.CUTTER_AXIS_Z - spec.CUTTER_DIA_MAX / 2.0,
        )
    )
    assert ccw(start, rear) < ccw(start, end)
    assert ccw(start, front) > ccw(start, end)


def test_part_record_and_finishes() -> None:
    config = _config.parts("transgear-knob-shaft")
    assert config["number"] == "MHA-078"
    assert config["material_specification"] == "SAE 1018 CF bar, ASTM A108-24"
    assert int(config["quantity"]) == 1
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    assert faces["journal"].diameter_mm == spec.JOURNAL_DIA
    assert faces["core"].diameter_mm == spec.CORE_DIA
    assert spec.CORE_END_Z < faces["core"].contains_z_mm < 0.0
    assert drawing.DIMENSION_CALLOUTS_BELOW == {"TipChamfer": spec.CHAMFER_CALLOUT}


def test_every_note_line_fits_the_note_field() -> None:
    lines = spec.DRAWING_NOTES.split("\n")
    assert len(lines) <= 4
    assert [line for line in lines if len(line) > 70] == []
