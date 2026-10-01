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
# test_transgear_arm_drawing uses them); the landscape border.  SolidWorks
# centres a hole callout's lines on its point (8b5e1f354: the knob shaft's
# three lines centred on x 15).
_CHAR_WIDTH = 0.00276
_LINE_PITCH = 0.0045
_BORDER = 0.0127


def test_the_rear_tap_callout_stands_inside_the_left_border() -> None:
    """Review of 8b5e1f354 (blocker): the callout, centred 30 mm left of the
    end view, ran through the left border; the thread line and the
    countersink's 90 degrees were cut off.  Every line stands inside the
    border with air, short of the side view's rear end and its extension
    lines, and under the end view's tooth tips."""
    lines = [
        f"\u00d8{spec.TAP_DRILL_DIA:.2f} \u21a7 {spec.TAP_DRILL_DEPTH:.1f}",
        f"{spec.TAP_SIZE} UNC - 2B \u21a7 {spec.TAP_FULL_THREAD:.1f}",
        *spec.TAP_CSK_QUALIFIER.splitlines(),
    ]
    assert spec.TAP_CSK_QUALIFIER.startswith("90\u00b0 CSK")
    x, y = drawing.TAP_CALLOUT_XY
    half_width = max(map(len, lines)) * _CHAR_WIDTH / 2.0
    half_height = len(lines) * _LINE_PITCH / 2.0
    assert x - half_width >= _BORDER + 0.003
    assert x + half_width <= drawing.REAR_X - 0.003
    assert y + half_height <= drawing.END_CENTER[1] - drawing.HALF_OD - 0.003


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
        ("JournalProfile", "JournalLength"): "JOURNAL_LENGTH_TOL",
    }
    # The journal's ±0.05 holds the knob float inside its .XXX row.
    assert spec.JOURNAL_LENGTH_TOL < printed_band_mm(spec.JOURNAL_LENGTH_PLACES)


def test_stations_land_on_the_contract_machine_stations() -> None:
    stations = {
        "stud tip": (spec.TIP_Z, -172.0),
        "full-thread end": (spec.THREAD_END_Z, -155.6),
        "12T rear tooth ends": (spec.PINION_REAR_Z, -142.2),
        "journal rear face": (spec.REAR_END_Z, -107.76),
    }
    for name, (local, machine) in stations.items():
        assert F_MACHINE_Z + local == pytest.approx(machine, abs=0.005), name
    assert spec.OVERALL_LENGTH == pytest.approx(64.24, abs=0.005)
    assert spec.THREAD_LENGTH_REF == pytest.approx(16.4)


def test_journal_spans_the_ring_the_plate_hub_and_the_float() -> None:
    """R9-25: the rear face stands the thrust ring plus the plate's hub-to-boss
    plus the end float behind the 12T's rear tooth ends, and the float stays
    open with the journal short and the ring and the hub long."""
    assert spec.JOURNAL_LENGTH == pytest.approx(
        ring.LENGTH + plate.HUB_TO_BOSS + spec.END_FLOAT
    )
    shortest_float = (spec.JOURNAL_LENGTH - spec.JOURNAL_LENGTH_TOL) - (
        ring.LENGTH + ring.LENGTH_TOL + plate.HUB_TO_BOSS + plate.HUB_TO_BOSS_BAND
    )
    assert shortest_float > 0.0


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


def test_walls_meet_the_floor_at_the_worst_case() -> None:
    for wall in (
        spec.JOURNAL_TAP_WALL_WORST,
        spec.JOURNAL_CSK_WALL_WORST,
        spec.TAP_TO_PINION_WORST,
    ):
        assert wall >= spec.WALL_FLOOR


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
