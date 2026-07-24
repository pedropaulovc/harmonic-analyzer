"""Offline contract for the simple drive-train assembly drawing."""

from pathlib import Path

import draw_drive_train_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_drive_train_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["drive_train_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "drive_train"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 3.0)
    assert drawing.FRONT_CENTER == (0.060, 0.165)
    assert drawing.RIGHT_CENTER == (0.190, 0.165)
    assert drawing.ISO_CENTER == (0.335, 0.165)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "return await build_simple_three_view_drawing(" in source
