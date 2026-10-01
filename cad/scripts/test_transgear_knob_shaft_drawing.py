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


def test_sheet_authors_no_manufacturing_value() -> None:
    # Rule 2: places and bands come from the part; the sheet reads them back.
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_bands_come_from_named_spec_constants() -> None:
    assert model_toleranced_dimensions(part) == {
        ("StudProfile", "CoreDia"): "*deviations(CORE_DIA_BAND)",
        ("JournalProfile", "JournalDia"): "*deviations(JOURNAL_DIA_BAND)",
        ("JournalProfile", "JournalLength"): "JOURNAL_LENGTH_TOL",
    }
    # The journal's ±0.05 holds the knob float inside its .XXX row.
    assert spec.JOURNAL_LENGTH_TOL < printed_band_mm(spec.JOURNAL_LENGTH_PLACES)


def test_stations_land_on_the_contract_machine_stations() -> None:
    stations = {
        "stud tip": (spec.TIP_Z, -172.0),
        "full-thread end": (spec.THREAD_END_Z, -154.6),
        "12T rear tooth ends": (spec.PINION_REAR_Z, -142.2),
        "journal rear face": (spec.REAR_END_Z, -107.76),
    }
    for name, (local, machine) in stations.items():
        assert F_MACHINE_Z + local == pytest.approx(machine, abs=0.005), name
    assert spec.OVERALL_LENGTH == pytest.approx(64.24, abs=0.005)
    assert spec.THREAD_LENGTH_REF == pytest.approx(17.4)


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


def test_thread_run_out_is_one_pitch_behind_the_full_thread() -> None:
    assert spec.DIE_RUNOUT_MAX == pytest.approx(spec.THREAD_PITCH)
    # The run-out's worst end stays in front of F: the core is plain from
    # there to the 12T.
    assert spec.THREAD_END_Z + spec.DIE_RUNOUT_MAX < 0.0


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
    assert spec.THREAD_END_Z < faces["core"].contains_z_mm < 0.0
    assert drawing.DIMENSION_CALLOUTS_BELOW == {"TipChamfer": spec.CHAMFER_CALLOUT}
