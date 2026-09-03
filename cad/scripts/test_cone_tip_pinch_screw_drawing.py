"""Focused contracts for the flat-end pinch-screw drawing repair."""

from __future__ import annotations

from pathlib import Path

import cone_tip_pinch_screw_spec as spec
import draw_cone_tip_pinch_screw as drawing


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_external_thread_depiction_uses_catalog_geometry() -> None:
    source = _source()
    assert "add_external_thread_depiction(" in source
    assert drawing.THREAD_AXIS_XY == (
        (drawing.SIDE_CENTER[0], drawing._JUNCTION_Y),
        (drawing.SIDE_CENTER[0], drawing._SHANK_END_Y),
    )
    assert drawing.THREAD_MODEL_DIAMETER_SHEET == spec.SHANK_DIA * drawing._S


def test_part_intent_remains_flat_end_pinch_screw() -> None:
    assert drawing.RECIPE.title == "Flat-End Pinch Screw Manufacturing Drawing"
    assert drawing.RECIPE.keywords.startswith("flat-end pinch screw;")
    assert spec.DRAWING_NOTES.splitlines()[0] == (
        "THREADED TO THE HEAD; LAST 2 PITCHES MAY BE INCOMPLETE."
    )
