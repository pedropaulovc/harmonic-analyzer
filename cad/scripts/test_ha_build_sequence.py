"""The master build order keeps every sub-assembly step once, in an order the
steps' own prerequisites allow, with every mill step done while the frame is
apart (ha_build_sequence, #2391, #850)."""

from __future__ import annotations

from collections import Counter

import ch_channel_assembly_steps as ch_steps
import dt_drive_train_steps as dt_steps
import fr_frame_assembly_steps as fr_steps
import ha_build_sequence as build
import ha_harmonic_analyzer_assembly_sheet as ha_sheet
import ha_harmonic_analyzer_assembly_steps as ha_steps

_CUT_SHEETS = (fr_steps, dt_steps, ch_steps)


def _phase_of(steps, key: str) -> int:
    found = [
        index
        for index, phase in enumerate(build.PHASES)
        for run in phase.runs
        if run.steps is steps and key in run.keys
    ]
    assert len(found) == 1, (steps.DRAWING_NUMBER, key, found)
    return found[0]


def _reerected() -> int:
    return _phase_of(fr_steps, "frame-reassembled")


def test_every_cut_sheet_step_runs_exactly_once():
    for steps in _CUT_SHEETS:
        counts = Counter(
            key
            for phase in build.PHASES
            for run in phase.runs
            if run.steps is steps
            for key in run.keys
        )
        assert set(counts) == set(steps.SEQUENCE), steps.DRAWING_NUMBER
        assert set(counts.values()) == {1}, steps.DRAWING_NUMBER


def test_each_sheets_runs_keep_its_own_order():
    # MHA-FR-00's deck parts (its steps from "support-seated") go on the loose
    # castings before the frame goes back up, so only its other runs keep
    # sheet order.
    for steps in (dt_steps, ch_steps, ha_steps):
        numbers = [
            number
            for phase in build.PHASES
            for run in phase.runs
            if run.steps is steps
            for number in run.numbers
        ]
        assert numbers == sorted(numbers), steps.DRAWING_NUMBER


def test_frame_lift_comes_first_and_reerection_follows_every_mill_phase():
    lifted = _phase_of(fr_steps, build.FRAME_LIFTED_KEY)
    mill = [i for i, phase in enumerate(build.PHASES) if "MILL" in phase.where]
    assert mill
    assert all(lifted < i < _reerected() for i in mill)


def test_every_match_located_step_runs_before_the_frame_goes_back_up():
    for steps, key in build.MATCH_LOCATED:
        assert key in steps.SEQUENCE, (steps.DRAWING_NUMBER, key)
        if steps is not fr_steps:
            assert _phase_of(steps, key) < _reerected(), (steps.DRAWING_NUMBER, key)


def test_cross_sheet_prerequisites_hold():
    # Rod forks pinned to the rockers before the rods go onto the cams.
    assert _phase_of(ch_steps, "rod-forks-pinned") < _phase_of(
        dt_steps, ch_steps.CYLINDER_STACK_KEY
    )
    # The deck support is on the base before the north pivot bracket seats on it.
    assert _phase_of(fr_steps, "support-screwed") < _phase_of(
        dt_steps, ch_steps.NORTH_BRACKET_SET_KEY
    )
    # The north pivot bracket is set before the rocker bank holds it.
    assert _phase_of(dt_steps, ch_steps.NORTH_BRACKET_SET_KEY) <= _phase_of(
        ch_steps, "north-bracket-held"
    )
    # Everything hung from the top frame comes after it is back up.
    assert _phase_of(ha_steps, "summing-hung") > _reerected()
    assert _phase_of(ch_steps, "bar-notches-set") > _reerected()


def test_ha_sheet_prints_every_run_before_integration():
    printed = " ".join(" ".join(ha_sheet.step_lines(key)) for key in ha_steps.SEQUENCE)
    for phase in build.PHASES[:-1]:
        for run in phase.runs:
            assert run.text in printed, run.text
    assert build.CH_ON_FRAME.text in printed
