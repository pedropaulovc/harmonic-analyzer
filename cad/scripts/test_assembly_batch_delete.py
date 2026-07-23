from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest

from _assembly import delete_assembly_features


@dataclass
class _Feature:
    _oleobj_: str


@dataclass
class _Variant:
    kind: int
    values: list[str]


class _Extension:
    def __init__(self, model: _Model) -> None:
        self.model = model
        self.multi_calls: list[tuple[_Variant, bool, None]] = []
        self.delete_calls = 0

    def MultiSelect2(self, objects: _Variant, append: bool, data: None) -> int:
        self.multi_calls.append((objects, append, data))
        self.model.selected = list(objects.values)
        return len(self.model.selected)

    def DeleteSelection2(self, _options: int) -> bool:
        self.delete_calls += 1
        selected = set(self.model.selected)
        self.model.features = {
            name: feature
            for name, feature in self.model.features.items()
            if feature._oleobj_ not in selected
        }
        return True


class _Model:
    def __init__(self, names: list[str]) -> None:
        self.features = {name: _Feature(f"dispatch:{name}") for name in names}
        self.selected: list[str] = []
        self.clear_calls = 0
        self.Extension = _Extension(self)

    def FeatureByName(self, name: str) -> _Feature | None:
        return self.features.get(name)

    def ClearSelection2(self, _all_marks: bool) -> None:
        self.clear_calls += 1
        self.selected = []


class _Adapter:
    def __init__(self, names: list[str]) -> None:
        self.currentModel = _Model(names)

    @staticmethod
    def _attempt(call: Callable[[], Any], default: Any = None) -> Any:
        try:
            return call()
        except Exception:
            return default


def test_delete_assembly_features_uses_one_dispatch_safearray(monkeypatch) -> None:
    import pythoncom
    from win32com import client

    adapter = _Adapter(["DRIVE_a", "DRIVE_b", "DRIVE_c"])
    monkeypatch.setattr(client, "VARIANT", _Variant)

    delete_assembly_features(adapter, ["DRIVE_c", "DRIVE_b", "DRIVE_a"])

    extension = adapter.currentModel.Extension
    assert adapter.currentModel.features == {}
    assert adapter.currentModel.clear_calls == 1
    assert extension.delete_calls == 1
    assert len(extension.multi_calls) == 1
    objects, append, data = extension.multi_calls[0]
    assert objects.kind == pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH
    assert objects.values == ["dispatch:DRIVE_c", "dispatch:DRIVE_b", "dispatch:DRIVE_a"]
    assert append is False
    assert data is None


def test_delete_assembly_features_rejects_partial_selection(monkeypatch) -> None:
    from win32com import client

    adapter = _Adapter(["DRIVE_a", "DRIVE_b"])
    monkeypatch.setattr(client, "VARIANT", _Variant)
    monkeypatch.setattr(
        adapter.currentModel.Extension,
        "MultiSelect2",
        lambda _objects, _append, _data: 1,
    )

    with pytest.raises(RuntimeError, match="selected 1/2"):
        delete_assembly_features(adapter, ["DRIVE_a", "DRIVE_b"])

    assert adapter.currentModel.Extension.delete_calls == 0
    assert set(adapter.currentModel.features) == {"DRIVE_a", "DRIVE_b"}
