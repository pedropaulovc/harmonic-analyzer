"""Uncalibrated stations must never acquire a guessed native placement."""

import pytest

import _config
from settled_spring_seats import channel_seat, counter_seat


def test_unknown_channel_station_is_not_interpolated():
    with pytest.raises(ValueError, match="No native spring calibration for amplitude"):
        channel_seat(1.0)


def test_changed_bank_cannot_reuse_a_known_station_or_counter_seat(monkeypatch):
    amplitudes = list(_config.amplitudes())
    amplitudes[-1] = 1.0
    monkeypatch.setattr(_config, "amplitudes", lambda: amplitudes)

    for read_seat in (lambda: channel_seat(0.0), counter_seat):
        with pytest.raises(
            ValueError, match="does not match its calibrated amplitude vector"
        ):
            read_seat()
