"""Offline contracts for the magnifying-clamp drawing."""

from __future__ import annotations

import draw_mg_magnifying_clamp as drawing
import mg_magnifying_clamp_spec


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = mg_magnifying_clamp_spec.SURFACE_FINISHES
    assert control.key == "lever_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == mg_magnifying_clamp_spec.LEVER_BORE_DIA
    assert control.face.contains_y_mm == mg_magnifying_clamp_spec.LEVER_BORE_Y


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    marked = set().union(*mg_magnifying_clamp_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
