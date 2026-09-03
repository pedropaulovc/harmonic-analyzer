from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

import pytest

import _assembly
import _config
from _assembly import (
    _discard_copy_source,
    _save_new_assembly_as_copy,
    reconcile_saved_rebuild_state,
)


class _PropertyManager:
    """Stand-in for ``ICustomPropertyManager``: ``Add3`` writes into the model."""

    def __init__(self, props: dict[str, str]) -> None:
        self._props = props

    def Add3(self, name: str, _type: int, value: str, _replace: int) -> int:
        self._props[name] = value
        return 0


class _Extension:
    def __init__(self, props: dict[str, str]) -> None:
        self._props = props

    def CustomPropertyManager(self, _configuration: str) -> _PropertyManager:
        return _PropertyManager(self._props)


class _Model:
    def __init__(self) -> None:
        self.options: int | None = None
        # 688e3847: the save chokepoint restamps the Revision custom property
        # (``_ensure_assembly_revision``) before SaveAs3, so the mock carries
        # a property store reachable via Extension.CustomPropertyManager.
        self.props: dict[str, str] = {}
        self.Extension = _Extension(self.props)

    def SaveAs3(self, path: str, version: int, options: int) -> int:
        self.options = options
        Path(path).write_bytes(b"assembly")
        return 0

    def GetCustomInfoValue(self, _configuration: str, name: str) -> str:
        return self.props.get(name, "")

    @staticmethod
    def GetTitle() -> str:
        return "Assembly1"


class _App:
    def __init__(self) -> None:
        self.closed: list[str] = []

    def CloseDoc(self, path: str) -> None:
        self.closed.append(path)

    def GetOpenDocument(self, title: str) -> None:
        return None


class _Adapter:
    def __init__(self) -> None:
        self.currentModel = _Model()
        self.swApp = _App()

    @staticmethod
    def _attempt(call: Callable[[], Any], default: Any = None) -> Any:
        try:
            return call()
        except Exception:
            return default


def test_new_assembly_save_is_silent_copy_without_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "patterned.SLDASM"
    target.write_bytes(b"stale")
    adapter = _Adapter()

    monkeypatch.setattr(_assembly, "_ensure_assembly_revision", lambda _adapter: None)
    _save_new_assembly_as_copy(adapter, target)

    assert adapter.currentModel.options == 1 | 2 | 8
    assert target.read_bytes() == b"assembly"
    assert (
        adapter.currentModel.GetCustomInfoValue("", "Revision")
        == _config.release_revision()
    )


def test_copy_source_is_discarded_by_document_title() -> None:
    adapter = _Adapter()

    _discard_copy_source(adapter)

    assert adapter.swApp.closed == ["Assembly1"]
    assert adapter.currentModel is None


class _RebuildExtension:
    def __init__(self) -> None:
        self.NeedsRebuild2 = 1


class _RebuildModel:
    def __init__(self, *, force_result: bool = True) -> None:
        self.Extension = _RebuildExtension()
        self.force_result = force_result
        self.force_calls: list[bool] = []
        self.save_calls: list[tuple[int, int, int]] = []

    def EditRebuild3(self) -> bool:
        return False

    def ForceRebuild3(self, top_only: bool) -> bool:
        self.force_calls.append(top_only)
        if self.force_result:
            self.Extension.NeedsRebuild2 = 0
        return self.force_result

    def Save3(self, options: int, errors: int, warnings: int) -> bool:
        self.save_calls.append((options, errors, warnings))
        return True


class _RebuildApp:
    @staticmethod
    def CloseAllDocuments(include_unsaved: bool) -> None:
        assert include_unsaved is True


class _RebuildAdapter:
    def __init__(self, model: _RebuildModel) -> None:
        self.currentModel = model
        self.swApp = _RebuildApp()

    @staticmethod
    def _attempt(call: Callable[[], Any], default: Any = None) -> Any:
        try:
            return call()
        except Exception:
            return default

    async def open_model(self, path: str) -> None:
        assert path.endswith(".SLDASM")


def test_reconcile_falls_back_to_top_only_force_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model = _RebuildModel()
    adapter = _RebuildAdapter(model)
    monkeypatch.setattr(_assembly, "_early_bound", lambda value, _name: value)

    asyncio.run(
        reconcile_saved_rebuild_state(
            adapter, "drive-train", tmp_path / "drive-train.SLDASM"
        )
    )

    assert model.force_calls == [True]
    assert model.save_calls == [(1, 0, 0)]
    assert model.Extension.NeedsRebuild2 == 0


def test_reconcile_fails_when_both_top_level_rebuilds_reject(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    model = _RebuildModel(force_result=False)
    adapter = _RebuildAdapter(model)
    monkeypatch.setattr(_assembly, "_early_bound", lambda value, _name: value)

    with pytest.raises(
        RuntimeError,
        match=r"reconcile ForceRebuild3\(True\) returned False",
    ):
        asyncio.run(
            reconcile_saved_rebuild_state(
                adapter, "drive-train", tmp_path / "drive-train.SLDASM"
            )
        )
