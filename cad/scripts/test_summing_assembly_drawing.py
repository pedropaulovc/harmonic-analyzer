"""Offline package contract for the summing assembly drawing."""

import asyncio

import draw_summing_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_summing_package_forwards_domain_instructions(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME["summing_assembly"]
    captured = {}

    async def build_package(adapter, **kwargs):
        captured.update(kwargs)
        return {"pdf": "summing"}

    monkeypatch.setattr(drawing, "build_assembly_package", build_package)
    assert asyncio.run(drawing.build(object())) == {"pdf": "summing"}
    assert captured["source"] == spec.source
    assert captured["outputs"] == drawing.OUTPUTS
    assert captured["sheet_scale"] == (1.0, 4.0)
    assert captured["layout"] is drawing.LAYOUT
    assert drawing.LAYOUT == drawing.AssemblyDrawingLayout(
        working_scale=(1.0, 4.0),
        exploded_scale=(1.0, 6.0),
        procedure_scale=(1.0, 5.0),
        reference_scale=(1.0, 12.0),
        exploded_center=(0.135, 0.180),
        reference_front_center=(0.080, 0.052),
        reference_right_center=(0.170, 0.052),
    )
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("12.0 mm" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("X=-15.0 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("hanger studs" in note for note in drawing.HARDWARE_NOTES)
