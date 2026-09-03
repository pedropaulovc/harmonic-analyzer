"""Offline package contract for the complete-machine assembly drawing."""

import asyncio

import build_harmonic_analyzer_assembly as assembly
import draw_harmonic_analyzer_assembly as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_subassembly_source_is_loaded_and_deeply_rebuilt(monkeypatch) -> None:
    events = []

    class Model:
        def ForceRebuild3(self, top_only):  # noqa: N802
            events.append(("rebuild", top_only))
            return -1

    model = Model()

    class Application:
        def DocumentVisible(self, visible, document_type):  # noqa: N802
            events.append(("visible", visible, document_type))

        def OpenDoc6(self, *args):  # noqa: N802
            events.append(("open", *args))
            return model

    class Adapter:
        swApp = Application()

        @staticmethod
        def _attempt(operation, default=None):
            try:
                return operation()
            except Exception:
                return default

    monkeypatch.setattr(assembly, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(assembly, "whats_wrong", lambda _adapter, _model: [])

    assembly._prepare_subassembly_document(Adapter(), "drive-train.SLDASM")

    assert events == [
        ("visible", False, 2),
        ("open", "drive-train.SLDASM", 2, 1, "", 0, 0),
        ("visible", True, 2),
        ("rebuild", True),
    ]

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
    assert captured["layout"] is drawing.LAYOUT
    assert drawing.LAYOUT == drawing.AssemblyDrawingLayout(
        working_scale=(1.0, 8.0),
        exploded_scale=(1.0, 24.0),
        procedure_scale=(1.0, 12.0),
        reference_scale=(1.0, 22.0),
        working_front_center=(0.100, 0.167),
        working_right_center=(0.275, 0.167),
        exploded_center=(0.130, 0.175),
    )
    assert captured["assembly_steps"] is drawing.ASSEMBLY_STEPS
    assert captured["critical_checks"] is drawing.CRITICAL_CHECKS
    assert captured["hardware_notes"] is drawing.HARDWARE_NOTES
    assert any("Z=-155 mm" in step for step in drawing.ASSEMBLY_STEPS)
    assert any("1.596 mm" in check for check in drawing.CRITICAL_CHECKS)
    assert any("seven subassemblies" in note for note in drawing.HARDWARE_NOTES)
