"""Offline package contract for the complete-machine assembly drawing."""

import asyncio

import draw_harmonic_analyzer_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_top_level_package_forwards_domain_instructions(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME["harmonic_analyzer_assembly"]
    captured = {}

    async def build_package(adapter, **kwargs):
        captured.update(kwargs)
        return {"pdf": "harmonic-analyzer"}

    monkeypatch.setattr(drawing, "build_assembly_package", build_package)
    assert asyncio.run(drawing.build(object())) == {"pdf": "harmonic-analyzer"}
    assert captured["source"] == spec.source
    assert captured["outputs"] == drawing.OUTPUTS
    assert captured["sheet_scale"] == (1.0, 7.0)
    assert captured["reference_scale"] == (1.0, 16.0)
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("Z=-155 mm" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("1.596 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("seven subassemblies" in note for note in drawing.HARDWARE_NOTES)
