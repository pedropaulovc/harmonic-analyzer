"""Regression tests for the reusable channel's configured build state."""

import pytest

from build_channel_assembly import _shared_channel_states, solve_state


def test_single_nonzero_amplitude_builds_at_configured_state() -> None:
    amplitude, state, neutral_state = _shared_channel_states([12.0])

    assert amplitude == 12.0
    assert state == solve_state(12.0)
    assert state["bar_origin_x"] != pytest.approx(neutral_state["bar_origin_x"])
    assert neutral_state == solve_state(0.0)


def test_nonuniform_amplitudes_reject_one_seed_pattern() -> None:
    with pytest.raises(RuntimeError, match="one shared amplitude_mm"):
        _shared_channel_states([0.0, 12.0])
