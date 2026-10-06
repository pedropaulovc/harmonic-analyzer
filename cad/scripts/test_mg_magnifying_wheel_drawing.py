"""Offline contracts for the magnifying-wheel drawing."""

from __future__ import annotations

import draw_mg_magnifying_wheel as drawing
import mg_magnifying_wheel_spec


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = mg_magnifying_wheel_spec.SURFACE_FINISHES
    assert control.key == "hub_drum"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == mg_magnifying_wheel_spec.HUB_DIA


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    marked = set().union(*mg_magnifying_wheel_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
