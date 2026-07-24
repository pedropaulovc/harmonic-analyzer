"""Offline contract for the simple complete-machine assembly drawing."""

from pathlib import Path

import draw_harmonic_analyzer_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_top_level_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["harmonic_analyzer_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "harmonic_analyzer"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 8.0)
    assert drawing.FRONT_CENTER == (0.060, 0.150)
    assert drawing.RIGHT_CENTER == (0.130, 0.150)
    assert drawing.ISO_CENTER == (0.215, 0.150)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "return await build_simple_three_view_drawing(" in source
