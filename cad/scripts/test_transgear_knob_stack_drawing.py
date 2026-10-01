"""Worst-case contracts of the transgear knob stack (R9-52, R9-53, R9-54).

The MHA-078 knob shaft's stud, the MHA-177 drive collar's rear slot, the
MHA-154 spring pin across it and the MHA-126 thumbnut, each pair judged at the
printed worst case (policy rule 12).  Every corner is recomputed here from the
printed values and places and from the catalogue limits, not read back from the
specs' derived constants; the reloads prove each import-time assert fires.
"""

from __future__ import annotations

import importlib.util

import pytest

import transgear_collar_cross_pin_spec as cross_pin
import transgear_drive_collar_spec as collar
import transgear_knob_shaft_spec as shaft
import transgear_removable_spec as removable
import transgear_thumbnut_spec as nut
from _printed_tolerance import printed_band_mm

INCH = 25.4
PITCH = INCH / 20.0
# ASME B18.8.2 1/16 slotted spring pin, free (uncompressed) diameter
# (https://fullerfasteners.com/tech/ansi-b18-8-2-specifications-slotted-type-spring-pins/).
PIN_FREE_DIA = (0.066 * INCH, 0.069 * INCH)
# ASME B1.1 1/4-20 UNC limits as tabled by Engineers Edge
# (https://www.engineersedge.com/screw_threads_chart.htm and
# https://www.engineersedge.com/thread_strength/internal_screw_threads_chart.htm).
MAJOR_2A = (0.2408 * INCH, 0.2489 * INCH)
PD_2A_MIN = 0.2127 * INCH
MINOR_2B_MIN = 0.1960 * INCH
# The deepest root a die cuts: a basic half-depth under the smallest 2A pitch
# diameter (the assumption crank_handle_pivot_screw_spec makes for #4-40).
ROOT_2A_MIN = PD_2A_MIN - 0.649519 * PITCH
ENGAGEMENT_FLOOR = 1.5 * 0.25 * INCH


def _limits(value: float, places: int) -> tuple[float, float]:
    band = printed_band_mm(places)
    return value - band, value + band


def _stud_places(name: str) -> int:
    return shaft.DRAWING_PRECISION["StudProfile"][name]


def _reloaded_collar(monkeypatch, module, name: str, value):
    """A fresh execution of the collar spec with one upstream value patched."""
    monkeypatch.setattr(module, name, value)
    fresh_spec = importlib.util.spec_from_file_location(
        "_drive_collar_perturbed", collar.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_slot_clears_the_free_spring_pin_at_both_limits(monkeypatch) -> None:
    """R9-52: the pin's ends spring out toward their free diameter in the slot,
    whose walls drive; the slot must take the largest free pin at its
    narrowest, 1.80 - 1.753 = +0.047, and 1.90 - 1.676 = +0.224 at its widest."""
    slot = (
        collar.SLOT_WIDTH + min(collar.SLOT_WIDTH_BAND),
        collar.SLOT_WIDTH + max(collar.SLOT_WIDTH_BAND),
    )
    tight = slot[0] - PIN_FREE_DIA[1]
    loose = slot[1] - PIN_FREE_DIA[0]
    assert tight == pytest.approx(0.0474, abs=1e-4)
    assert loose == pytest.approx(0.2236, abs=1e-4)
    assert tight > 0.0
    # Negative control: the 1.7 slot of fc9c2d700 grips the largest free pin.
    assert 1.7 - PIN_FREE_DIA[1] < 0.0
    # The spec's assert fires on a pin whose free diameter fills the slot.
    with pytest.raises(AssertionError, match="MHA-177 slot / MHA-154 pin"):
        _reloaded_collar(monkeypatch, cross_pin, "FREE_DIA_MAX", 1.81)


def test_thread_blank_lies_inside_the_2a_major() -> None:
    """R9-54: the die cuts 1/4-20 UNC-2A on a blank inside 6.116..6.322."""
    blank = (
        shaft.THREAD_BLANK_DIA + min(shaft.THREAD_BLANK_DIA_BAND),
        shaft.THREAD_BLANK_DIA + max(shaft.THREAD_BLANK_DIA_BAND),
    )
    assert _stud_places("ThreadBlankDia") == 2
    assert MAJOR_2A[0] <= blank[0] and blank[1] <= MAJOR_2A[1]
    # The tip chamfer still runs 45 degrees down to the basic minor.
    basic_minor = 0.25 * INCH - 1.082532 * PITCH
    assert shaft.THREAD_BLANK_DIA - 2.0 * shaft.TIP_CHAMFER == pytest.approx(
        basic_minor
    )
    # Negative control: fc9c2d700 cut the thread on the Ø6.35 core at its
    # sliding band, 6.335..6.345, above the 2A major maximum.
    head_blank_min = shaft.CORE_DIA + min(shaft.CORE_DIA_BAND)
    assert head_blank_min > MAJOR_2A[1]


def test_relief_holds_the_die_lead_under_the_deepest_root() -> None:
    """R9-53: full thread ends on the relief's front shoulder; the narrowest
    relief takes a 1.5-pitch die lead, and its largest floor stands under the
    deepest die-cut root and inside the nut's smallest minor."""
    core_max = _limits(shaft.CORE_LENGTH, _stud_places("CoreLength"))[1]
    thread_end_min = _limits(shaft.PLAIN_CORE, _stud_places("PlainCore"))[0]
    assert thread_end_min - core_max == pytest.approx(1.99)
    assert thread_end_min - core_max >= 1.5 * PITCH
    relief_max = _limits(shaft.RELIEF_DIA, _stud_places("ReliefDia"))[1]
    assert relief_max == pytest.approx(4.51)
    assert relief_max < ROOT_2A_MIN < MINOR_2B_MIN
    # Negative control: a relief at the thread's tabled 2A minor maximum
    # (0.1876 in), printed at .XX, rises over the deepest root.
    assert 0.1876 * INCH + printed_band_mm(2) > ROOT_2A_MIN


def test_thumbnut_runs_clear_of_the_core_step_at_the_rearward_stop(
    monkeypatch,
) -> None:
    """R9-53: at the rearward stop (the shortest collar's rear face on F, the
    thinnest plate) the nut's seat stands 3.87 + 2.70 = 6.57 in front of F,
    clear of the longest core 5.38; its thread runs only on full thread or
    over the relief."""
    seat = collar.LENGTH - printed_band_mm(collar.LENGTH_PLACES)
    nut_seat = seat + removable.PLATE + min(removable.PLATE_BAND)
    core_max = _limits(shaft.CORE_LENGTH, _stud_places("CoreLength"))[1]
    assert nut_seat - core_max == pytest.approx(1.19)
    assert nut_seat - core_max > 0.0
    # Negative control: at fc9c2d700 the full thread ended 6.5 (.XXX) in front
    # of F with a one-pitch die run-out behind it, so the run-out reached
    # 6.37..7.90 and the nut's first full thread (0.2 in from its seat, 6.77)
    # sat on it.
    head_runout_end = 6.5 + printed_band_mm(3) + PITCH
    assert nut_seat + nut.REAR_THREAD_LOSS < head_runout_end
    with pytest.raises(AssertionError, match="MHA-126 thumbnut / MHA-078 core step"):
        _reloaded_collar(monkeypatch, shaft, "CORE_LENGTH", 6.5)


def test_cross_hole_stays_in_the_full_core_over_the_travel(monkeypatch) -> None:
    """The cross hole, drilled along the slot at the setting, keeps its front
    edge on the full Ø6.35 core from the rearward stop to the seat maximum:
    5.12 - (6.90 - 1.88) = +0.10 at the worst."""
    slot_floor = collar.LENGTH - collar.SLOT_DEPTH
    hole_axis = slot_floor + cross_pin.HOLE_DIA / 2.0
    front_in_collar = (
        hole_axis
        - (cross_pin.HOLE_DIA + max(cross_pin.HOLE_BAND)) / 2.0
        - max(collar.SLOT_DEPTH_BAND)
        - printed_band_mm(3) / 2.0
        - printed_band_mm(collar.LENGTH_PLACES)
    )
    assert front_in_collar == pytest.approx(1.88)
    core_min = _limits(shaft.CORE_LENGTH, _stud_places("CoreLength"))[0]
    rear_stop = collar.LENGTH - printed_band_mm(collar.LENGTH_PLACES)
    settings = [
        rear_stop + (collar.SEAT_MAX_FROM_F - rear_stop) * i / 50.0 for i in range(51)
    ]
    margins = [core_min - (seat - front_in_collar) for seat in settings]
    assert min(margins) == pytest.approx(0.10)
    assert min(margins) > 0.0
    # Negative control: a core 0.25 shorter puts the hole in the relief.
    with pytest.raises(AssertionError, match="MHA-154 cross hole / MHA-078"):
        _reloaded_collar(monkeypatch, shaft, "CORE_LENGTH", shaft.CORE_LENGTH - 0.25)


def test_thumbnut_engages_one_and_a_half_diameters_over_the_travel(
    monkeypatch,
) -> None:
    """Full stud thread inside the nut's full thread at every accepted setting:
    the forward end is the shortest tip (or the deepest cut below the shortest
    nut's rim) less a pitch, inside the rim's countersink; the rear end the
    nut's seat countersink on the thickest plate, or the shortest stud's
    full-thread end.  Least 11.97 (1.89 D) on the shortest .X nut."""
    tip_min = _limits(shaft.TIP_STATION, shaft.TIP_STATION_PLACES)[0]
    thread_end_max = _limits(shaft.PLAIN_CORE, _stud_places("PlainCore"))[1]
    nut_min = _limits(nut.OVERALL_LENGTH, nut.OVERALL_LENGTH_PLACES)[0]
    plate = (
        removable.PLATE + min(removable.PLATE_BAND),
        removable.PLATE + max(removable.PLATE_BAND),
    )
    cut_deepest = collar.STUD_CUT_BELOW_RIM[1]

    def engagement(seat: float) -> float:
        rim = seat + plate[0] + nut_min
        tip = min(tip_min, rim - cut_deepest)
        front = min(tip - PITCH, rim - nut.CSK_DEPTH)
        rear = max(seat + plate[1] + nut.CSK_DEPTH, thread_end_max)
        return front - rear

    rear_stops = _limits(collar.LENGTH, collar.LENGTH_PLACES)
    settings = [
        rear_stops[0] + (collar.SEAT_MAX_FROM_F - rear_stops[0]) * i / 100.0
        for i in range(101)
    ]
    worst = min(engagement(seat) for seat in [*settings, rear_stops[1]])
    assert worst == pytest.approx(11.97)
    assert worst >= ENGAGEMENT_FLOOR
    assert collar.THUMBNUT_ENGAGEMENT_WORST == pytest.approx(worst)
    # Negative control: a stud tip 4 shorter leaves 8.22, under 1.5 D.
    with pytest.raises(AssertionError, match="MHA-126 thumbnut / MHA-078 stud"):
        _reloaded_collar(monkeypatch, shaft, "TIP_STATION", shaft.TIP_STATION - 4.0)
