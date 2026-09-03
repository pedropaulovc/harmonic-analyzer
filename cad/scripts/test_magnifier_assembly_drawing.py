"""Offline package contract for the magnifier assembly drawing."""

import asyncio

import draw_magnifier_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_magnifier_package_forwards_domain_instructions(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME["magnifier_assembly"]
    captured = {}

    async def build_package(adapter, **kwargs):
        captured.update(kwargs)
        return {"pdf": "magnifier"}

    monkeypatch.setattr(drawing, "build_assembly_package", build_package)
    assert asyncio.run(drawing.build(object())) == {"pdf": "magnifier"}
    assert captured["source"] == spec.source
    assert captured["outputs"] == drawing.OUTPUTS
    assert captured["sheet_scale"] == (1.0, 3.0)
    assert captured["reference_scale"] == (1.0, 8.0)
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("WIRE 1" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("4×" in check for check in drawing.CRITICAL_CHECKS)
    assert any("column-clamp halves" in note for note in drawing.HARDWARE_NOTES)
