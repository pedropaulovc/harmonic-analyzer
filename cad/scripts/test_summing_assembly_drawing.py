"""Offline contract for the simple summing assembly drawing."""

from pathlib import Path

import draw_summing_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_summing_assembly_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["summing_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "summing"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert drawing.FRONT_CENTER == (0.060, 0.150)
    assert drawing.RIGHT_CENTER == (0.130, 0.150)
    assert drawing.ISO_CENTER == (0.225, 0.140)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "return await build_simple_three_view_drawing(" in source
