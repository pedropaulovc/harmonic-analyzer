"""Offline contract for the simple frame assembly drawing."""

from pathlib import Path

import draw_frame_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_frame_assembly_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["frame_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "frame"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 6.0)
    assert drawing.FRONT_CENTER == (0.065, 0.155)
    assert drawing.RIGHT_CENTER == (0.150, 0.155)
    assert drawing.ISO_CENTER == (0.300, 0.145)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "return await build_simple_three_view_drawing(" in source
