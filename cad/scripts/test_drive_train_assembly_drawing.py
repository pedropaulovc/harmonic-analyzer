"""Offline package contract for the drive-train assembly drawing."""

import asyncio

import draw_drive_train_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_drive_train_package_forwards_domain_instructions(monkeypatch) -> None:
    spec = DRAWINGS_BY_NAME["drive_train_assembly"]
    captured = {}

    async def build_package(adapter, **kwargs):
        captured.update(kwargs)
        return {"pdf": "drive-train"}

    monkeypatch.setattr(drawing, "build_assembly_package", build_package)
    assert asyncio.run(drawing.build(object())) == {"pdf": "drive-train"}
    assert captured["source"] == spec.source
    assert captured["outputs"] == drawing.OUTPUTS
    assert captured["sheet_scale"] == (2.0, 5.0)
    assert captured["layout"] is drawing.LAYOUT
    assert drawing.LAYOUT == drawing.AssemblyDrawingLayout(
        working_scale=(1.0, 3.0),
        exploded_scale=(1.0, 10.0),
        procedure_scale=(1.0, 6.0),
        reference_scale=(1.0, 8.0),
        working_front_center=(0.095, 0.168),
        working_right_center=(0.278, 0.168),
        exploded_center=(0.130, 0.180),
        working_display_mode="shaded-with-edges",
    )
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("1:48" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("0.79 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("taper pin" in note for note in drawing.HARDWARE_NOTES)
