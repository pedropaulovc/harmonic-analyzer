"""Offline contracts for the purchased 9432K31 reference sheet."""

from __future__ import annotations

import math

import channel_spring_installed_spec as spec
from spring_mount_geom import channel_force_n


def test_installed_spring_stays_within_catalogue_load_envelope() -> None:
    assert spec.FREE_LENGTH_MM <= spec.INSTALLED_LENGTH_MM <= spec.MAX_LENGTH_MM
    assert channel_force_n(spec.INSTALLED_LENGTH_MM) < spec.MAXIMUM_LOAD_N


def test_two_point_qc_measures_the_catalogue_rate() -> None:
    measured = (channel_force_n(80.0) - channel_force_n(60.0)) / 20.0
    assert math.isclose(measured, spec.SPRING_RATE_N_PER_MM, rel_tol=1e-12)
