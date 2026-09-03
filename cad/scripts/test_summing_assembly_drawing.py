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
    assert captured["reference_scale"] == (1.0, 10.0)
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("12.0 mm" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("X=-15.0 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("hanger studs" in note for note in drawing.HARDWARE_NOTES)
