"""Offline package contract for the pen assembly drawing."""

import asyncio

import draw_pen_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_pen_package_forwards_domain_instructions(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME["pen_assembly"]
    captured = {}

    async def build_package(adapter, **kwargs):
        captured.update(kwargs)
        return {"pdf": "pen"}

    monkeypatch.setattr(drawing, "build_assembly_package", build_package)
    assert asyncio.run(drawing.build(object())) == {"pdf": "pen"}
    assert captured["source"] == spec.source
    assert captured["outputs"] == drawing.OUTPUTS
    assert captured["sheet_scale"] == (2.0, 3.0)
    assert captured["layout"] is drawing.LAYOUT
    assert drawing.LAYOUT == drawing.AssemblyDrawingLayout(
        working_scale=(2.0, 3.0),
        exploded_scale=(1.0, 3.0),
        procedure_scale=(2.0, 3.0),
        reference_scale=(1.0, 7.0),
        exploded_center=(0.140, 0.175),
    )
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("13.0 mm" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("Z=-157.0 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("WIRE 2" in note for note in drawing.HARDWARE_NOTES)
