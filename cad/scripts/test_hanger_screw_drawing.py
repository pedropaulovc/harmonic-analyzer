"""Focused drawing contracts for the hanger-screw thread repair."""

from __future__ import annotations

from pathlib import Path

import draw_hanger_screw as drawing
import hanger_screw_spec as spec


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_external_thread_depiction_uses_catalog_geometry() -> None:
    source = _source()
    assert "add_external_thread_depiction(" in source
    assert drawing.THREAD_AXIS_XY == (
        (drawing._JUNCTION_X, drawing.SIDE_CENTER[1]),
        (drawing._SHANK_END_X, drawing.SIDE_CENTER[1]),
    )
    assert drawing.THREAD_MODEL_DIAMETER_SHEET == spec.SHANK_DIA * drawing._S
    assert drawing.SIDE_KEEP["ShankLg"][0] == drawing._SHANK_MID_X
