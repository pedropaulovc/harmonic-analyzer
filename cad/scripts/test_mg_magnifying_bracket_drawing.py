"""Offline contracts for the magnifying-bracket drawing."""

from __future__ import annotations

import draw_mg_magnifying_bracket as drawing
import mg_magnifying_bracket_spec


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    marked = set().union(*mg_magnifying_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert marked == {"ArmWidth", "ArmDepth", "FlangeWidth", "FlangeDepth"}
