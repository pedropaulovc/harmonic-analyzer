"""Offline telemetry contracts for the surface-finish PMI positive control."""

from __future__ import annotations

import ast
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from diagnostics import probe_surface_finish_pmi as probe


def test_probe_splits_major_com_phases_into_child_spans() -> None:
    source = Path(probe.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    phase_spans = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "_telemetry"
        and node.func.attr == "span"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }

    assert phase_spans == {
        "diagnostic.surface_finish_pmi.part_authoring",
        "diagnostic.surface_finish_pmi.part_save_reopen",
        "diagnostic.surface_finish_pmi.drawing_import",
        "diagnostic.surface_finish_pmi.drawing_final_reopen",
    }


def test_part_annotation_walk_has_an_operation_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def capture_span(name: str, **attributes: Any):
        spans.append((name, attributes))
        yield

    class Annotation:
        def GetType(self) -> int:
            return probe._SFS_ANNOTATION

        def GetName(self) -> str:
            return probe.ANNOTATION_NAME

        def GetNext3(self) -> None:
            return None

    class Model:
        def GetFirstAnnotation2(self) -> Annotation:
            return Annotation()

    monkeypatch.setattr(probe._telemetry, "span", capture_span)
    monkeypatch.setattr(probe, "_early_bound", lambda value, _type: value)

    found = probe._surface_annotations(Model())

    assert tuple(found) == (probe.ANNOTATION_NAME,)
    assert spans == [("diagnostic.surface_finish_pmi.walk_part_annotations", {})]


def test_drawing_annotation_walk_has_an_operation_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def capture_span(name: str, **attributes: Any):
        spans.append((name, attributes))
        yield

    class Annotation:
        def GetType(self) -> int:
            return probe._SFS_ANNOTATION

        def GetName(self) -> str:
            return probe.ANNOTATION_NAME

    class ModelView:
        def GetNextView(self) -> None:
            return None

        def GetAnnotations(self) -> tuple[Annotation]:
            return (Annotation(),)

        def GetName2(self) -> str:
            return "Front"

    class SheetView:
        def GetNextView(self) -> ModelView:
            return ModelView()

    class Drawing:
        def GetFirstView(self) -> SheetView:
            return SheetView()

    monkeypatch.setattr(probe._telemetry, "span", capture_span)
    monkeypatch.setattr(probe, "_early_bound", lambda value, _type: value)

    found = probe._drawing_surface_annotations(Drawing())

    assert tuple(found) == (f"Front/{probe.ANNOTATION_NAME}",)
    assert spans == [("diagnostic.surface_finish_pmi.walk_drawing_annotations", {})]


def test_symbol_validation_has_a_stage_labeled_operation_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def capture_span(name: str, **attributes: Any):
        spans.append((name, attributes))
        yield

    class Symbol:
        def GetText(self, _field: int) -> str:
            return probe.ROUGHNESS

        def IsAttached(self) -> bool:
            return True

    class Annotation:
        def GetSpecificAnnotation(self) -> Symbol:
            return Symbol()

        def GetAttachedEntities3(self) -> tuple[object]:
            return (object(),)

    monkeypatch.setattr(probe._telemetry, "span", capture_span)
    monkeypatch.setattr(probe, "_early_bound", lambda value, _type: value)

    probe._assert_symbol(Annotation(), stage="drawing reopened")

    assert spans == [
        (
            "diagnostic.surface_finish_pmi.assert_symbol",
            {"label": "drawing reopened"},
        )
    ]
