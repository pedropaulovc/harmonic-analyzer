"""Offline contracts for the purchased 1330K524 reference sheet."""

from __future__ import annotations

import counter_spring_spec as spec
from spring_mount_geom import counter_force_n


def test_installed_spring_stays_within_catalogue_load_envelope() -> None:
    assert spec.FREE_LENGTH_MM <= spec.INSTALLED_LENGTH_MM <= spec.MAX_LENGTH_MM
    assert counter_force_n(spec.INSTALLED_LENGTH_MM) < spec.MAXIMUM_LOAD_N
