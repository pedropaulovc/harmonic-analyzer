"""Focused drawing contracts for the swing-stop screw repairs."""

from __future__ import annotations

from pathlib import Path

import draw_swing_stop_screw as drawing
import swing_stop_screw_spec as spec


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
    assert drawing.SIDE_KEEP["ShankLg"][1] == drawing._SHANK_MID_Y


def test_end_view_repairs_stay_in_the_shared_annotation_layer() -> None:
    source = _source()
    assert "end_diameter_leaders_at_rim(" in source
    assert "add_circle_center_mark(" in source
    assert drawing.END_DIAMETERS == ("HeadDiaDim",)
