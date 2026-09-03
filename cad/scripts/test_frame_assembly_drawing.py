"""Offline package contract for the frame assembly drawing."""

import asyncio

import draw_frame_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_frame_package_forwards_domain_instructions(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME["frame_assembly"]
    captured = {}

    async def build_package(adapter, **kwargs):
        captured.update(kwargs)
        return {"pdf": "frame"}

    monkeypatch.setattr(drawing, "build_assembly_package", build_package)
    assert asyncio.run(drawing.build(object())) == {"pdf": "frame"}
    assert captured["source"] == spec.source
    assert captured["outputs"] == drawing.OUTPUTS
    assert captured["sheet_scale"] == (1.0, 5.0)
    assert captured["reference_scale"] == (1.0, 12.0)
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("window faces ±X" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("1044.8 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("9/16-12" in note for note in drawing.HARDWARE_NOTES)
