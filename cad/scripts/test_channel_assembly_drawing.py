"""Offline package contract for the channel assembly drawing."""

import asyncio

import draw_channel_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_channel_package_forwards_domain_instructions(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME["channel_assembly"]
    captured = {}

    async def build_package(adapter, **kwargs):
        captured.update(kwargs)
        return {"pdf": "channel"}

    monkeypatch.setattr(drawing, "build_assembly_package", build_package)
    assert asyncio.run(drawing.build(object())) == {"pdf": "channel"}
    assert captured["source"] == spec.source
    assert captured["outputs"] == drawing.OUTPUTS
    assert captured["sheet_scale"] == (1.0, 6.0)
    assert captured["layout"] is drawing.LAYOUT
    assert drawing.LAYOUT == drawing.AssemblyDrawingLayout(
        working_scale=(1.0, 7.0),
        exploded_scale=(1.0, 20.0),
        procedure_scale=(1.0, 12.0),
        reference_scale=(1.0, 20.0),
        exploded_center=(0.130, 0.170),
        working_display_mode="shaded-with-edges",
    )
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("20 rockers" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("7.0565 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("J-hooks" in note for note in drawing.HARDWARE_NOTES)
