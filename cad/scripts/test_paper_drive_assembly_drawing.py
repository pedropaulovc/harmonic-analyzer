"""Offline package contract for the paper-drive assembly drawing."""

import asyncio

import draw_paper_drive_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_paper_drive_package_forwards_domain_instructions(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME["paper_drive_assembly"]
    captured = {}

    async def build_package(adapter, **kwargs):
        captured.update(kwargs)
        return {"pdf": "paper-drive"}

    monkeypatch.setattr(drawing, "build_assembly_package", build_package)
    assert asyncio.run(drawing.build(object())) == {"pdf": "paper-drive"}
    assert captured["source"] == spec.source
    assert captured["outputs"] == drawing.OUTPUTS
    assert captured["sheet_scale"] == (1.0, 4.0)
    assert captured["layout"] is drawing.LAYOUT
    assert drawing.LAYOUT == drawing.AssemblyDrawingLayout(
        working_scale=(1.0, 4.0),
        exploded_scale=(1.0, 22.0),
        procedure_scale=(1.0, 5.0),
        reference_scale=(1.0, 12.0),
        exploded_center=(0.105, 0.155),
    )
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("T24 sprocket" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("1.596 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("T18 sprocket" in note for note in drawing.HARDWARE_NOTES)
