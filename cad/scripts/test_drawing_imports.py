"""Focused contracts for drawing model-item import cleanup."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _drawing_common as drawing_common


class _Drawing:
    def __init__(self) -> None:
        self.delete_calls = 0
        self.rebuild_calls = 0

    def ClearSelection2(self, _clear_all: bool) -> None:
        return None

    def EditDelete(self) -> None:
        self.delete_calls += 1

    def EditRebuild3(self) -> None:
        self.rebuild_calls += 1


class _Annotation:
    def __init__(self, name: str | None) -> None:
        self.name = name
        self.select_calls = 0

    def Select2(self, _append: bool, _mark: int) -> bool:
        self.select_calls += 1
        return True


@pytest.fixture
def import_cleanup(monkeypatch: pytest.MonkeyPatch) -> _Drawing:
    drawing = _Drawing()
    monkeypatch.setattr(
        drawing_common._sw_type_info,
        "early_bound_or_flag",
        lambda annotation, *_args: annotation,
    )
    monkeypatch.setattr(
        drawing_common,
        "dimension_name",
        lambda _adapter, annotation: annotation.name,
    )
    return drawing


def test_named_imports_skip_redundant_drawing_rebuild(import_cleanup: _Drawing) -> None:
    annotations = [_Annotation("Rise"), _Annotation("RodDia")]
    adapter = SimpleNamespace(currentModel=import_cleanup)

    survivors = drawing_common.delete_unnamed_imports(adapter, annotations)

    assert survivors == annotations
    assert import_cleanup.delete_calls == 0
    assert import_cleanup.rebuild_calls == 0


def test_deleted_unnamed_imports_rebuild_once(import_cleanup: _Drawing) -> None:
    named = _Annotation("RodDia")
    unnamed = _Annotation(None)
    adapter = SimpleNamespace(currentModel=import_cleanup)

    survivors = drawing_common.delete_unnamed_imports(adapter, [named, unnamed])

    assert survivors == [named]
    assert unnamed.select_calls == 1
    assert import_cleanup.delete_calls == 1
    assert import_cleanup.rebuild_calls == 1
