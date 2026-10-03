from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

import _config
from _assembly import _discard_copy_source, _save_new_assembly_as_copy
from _assembly_contract import assembly_contract


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
        # The save chokepoint restamps frozen identity via CustomPropertyManager.
        self.props: dict[str, str] = {}
        self.Extension = _Extension(self.props)
        # The chokepoint also restamps the summary Title with the slug.
        self.summary: dict[int, str] = {0: "patterned assembly"}

    def SummaryInfo(self, field: int) -> str:
        return self.summary.get(field, "")

    def SetSummaryInfo(self, field: int, value: str) -> None:
        self.summary[field] = value

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


def test_new_assembly_save_is_silent_copy_without_references(tmp_path: Path) -> None:
    target = tmp_path / "fr-frame.SLDASM"
    target.write_bytes(b"stale")
    adapter = _Adapter()

    _save_new_assembly_as_copy(adapter, target)

    assert adapter.currentModel.options == 1 | 2 | 8
    assert target.read_bytes() == b"assembly"
    assert (
        adapter.currentModel.GetCustomInfoValue("", "Revision")
        == _config.release_revision()
    )
    # The PART cell prints the slug, not "<name> assembly".
    assert adapter.currentModel.summary[0] == "fr-frame"
    assert adapter.currentModel.props["Number"] == assembly_contract("fr-frame").number


@pytest.mark.parametrize("stale_field", ["Title", "Number", "Revision"])
def test_in_place_save_restamps_stale_metadata_and_forces_the_save(
    tmp_path: Path, monkeypatch, stale_field
) -> None:
    import _assembly

    sldasm = tmp_path / "fr-frame.SLDASM"
    sldasm.write_bytes(b"old")
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(
        _assembly, "rebuild_if_needed_before_save", lambda *_args: None
    )
    adapter = _Adapter()
    model = adapter.currentModel
    model.props["Revision"] = _config.release_revision()
    model.props["Number"] = assembly_contract("fr-frame").number
    model.summary[0] = "fr-frame"
    if stale_field == "Title":
        model.summary[0] = "old title"
    else:
        model.props[stale_field] = "old metadata"
    model.GetSaveFlag = lambda: True

    def save3(_options: int, _err: int, _warn: int):
        sldasm.write_bytes(b"new")
        import os

        stat = sldasm.stat()
        os.utime(sldasm, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
        return (True, 0, 0)

    model.Save3 = save3

    assert _assembly.save_assembly_in_place(adapter, "fr-frame", False) is True
    assert sldasm.read_bytes() == b"new"
    assert model.summary[0] == "fr-frame"
    assert model.props["Number"] == assembly_contract("fr-frame").number
    assert model.props["Revision"] == _config.release_revision()


def test_in_place_save_leaves_current_identity_and_title_untouched(
    tmp_path: Path, monkeypatch
) -> None:
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    adapter = _Adapter()
    model = adapter.currentModel
    model.props["Revision"] = _config.release_revision()
    model.props["Number"] = assembly_contract("fr-frame").number
    model.summary[0] = "fr-frame"

    assert _assembly.save_assembly_in_place(adapter, "fr-frame", False) is False


def test_copy_source_is_discarded_by_document_title() -> None:
    adapter = _Adapter()

    _discard_copy_source(adapter)

    assert adapter.swApp.closed == ["Assembly1"]
    assert adapter.currentModel is None
