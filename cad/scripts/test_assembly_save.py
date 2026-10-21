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


class _DisplayConfiguration:
    def __init__(self, name: str, model: Any) -> None:
        self.Name = name
        self.model = model
        self.mark = False

    @property
    def LargeDesignReviewMark(self) -> bool:
        if self.model.mark_defect == "read_error":
            raise RuntimeError("display mark read failed")
        if self.model.mark_defect == "readback_error" and self.mark:
            raise RuntimeError("display mark readback failed")
        return self.mark

    @LargeDesignReviewMark.setter
    def LargeDesignReviewMark(self, value: bool) -> None:
        self.model.events.append(("mark", self.Name, value))
        if self.model.mark_defect == "write_error":
            raise RuntimeError("display mark write failed")
        if self.model.mark_defect != "refused":
            self.mark = value
        if self.model.mark_defect == "truthy_readback":
            self.mark = "True"
        if self.model.mark_defect == "active_changed":
            self.model.ConfigurationManager.ActiveConfiguration.Name = "Unexpected"


class _Model:
    def __init__(self, names=("Default", "Default Simplified", "Exploded")) -> None:
        from types import SimpleNamespace

        self.events = []
        self.mark_defect = None
        self.configurations = {
            name: _DisplayConfiguration(name, self) for name in names
        }
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=self.configurations.get("Default")
        )
        self.options: int | None = None
        # The save chokepoint restamps frozen identity via CustomPropertyManager.
        self.props: dict[str, str] = {}
        self.Extension = _Extension(self.props)
        # The chokepoint also restamps the summary Title with the slug.
        self.summary: dict[int, str] = {0: "patterned assembly"}

    def GetConfigurationNames(self):
        return list(self.configurations)

    def GetConfigurationByName(self, name):
        return self.configurations[name]

    def ShowConfiguration2(self, name):
        pytest.fail(f"display marking switched configuration to {name}")

    def EditRebuild3(self):
        pytest.fail("display marking rebuilt the model")

    def ForceRebuild3(self, _top_only):
        pytest.fail("display marking force-rebuilt the model")

    def SummaryInfo(self, field: int) -> str:
        return self.summary.get(field, "")

    def SetSummaryInfo(self, field: int, value: str) -> None:
        self.summary[field] = value

    def SaveAs3(self, path: str, version: int, options: int) -> int:
        self.events.append(("save_copy", version, options))
        assert all(cfg.mark for cfg in self.configurations.values()) if len(
            self.configurations
        ) > 1 else not any(cfg.mark for cfg in self.configurations.values())
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
    assert adapter.currentModel.events == [
        ("mark", name, True) for name in adapter.currentModel.configurations
    ] + [("save_copy", 0, 11)]
    assert adapter.currentModel.ConfigurationManager.ActiveConfiguration.Name == "Default"


@pytest.mark.parametrize("stale_field", ["Title", "Number", "Revision"])
def test_in_place_save_restamps_stale_metadata_and_forces_the_save(
    tmp_path: Path, monkeypatch, stale_field, saved_native_bytes
) -> None:
    import _assembly

    sldasm = tmp_path / "fr-frame.SLDASM"
    sldasm.write_bytes(saved_native_bytes())
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
        assert _options == 9
        assert model.events == [("mark", name, True) for name in model.configurations]
        assert all(cfg.mark for cfg in model.configurations.values())
        assert model.ConfigurationManager.ActiveConfiguration.Name == "Default"
        sldasm.write_bytes(saved_native_bytes(1, 1))
        import os

        stat = sldasm.stat()
        os.utime(sldasm, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
        return (True, 0, 0)

    model.Save3 = save3

    assert _assembly.save_assembly_in_place(adapter, "fr-frame", False) is True
    assert sldasm.read_bytes() == saved_native_bytes(1, 1)
    assert model.summary[0] == "fr-frame"
    assert model.props["Number"] == assembly_contract("fr-frame").number
    assert model.props["Revision"] == _config.release_revision()


def test_in_place_save_leaves_current_identity_and_title_untouched(
    tmp_path: Path, monkeypatch, saved_native_bytes
) -> None:
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    target = tmp_path / "fr-frame.SLDASM"
    original = saved_native_bytes()
    target.write_bytes(original)
    adapter = _Adapter()
    model = adapter.currentModel
    model.props["Revision"] = _config.release_revision()
    model.props["Number"] = assembly_contract("fr-frame").number
    model.summary[0] = "fr-frame"
    model.Save3 = lambda *_args: pytest.fail("clean complete assembly was saved")

    assert _assembly.save_assembly_in_place(adapter, "fr-frame", False) is False
    assert target.read_bytes() == original
    assert model.events == []


def test_copy_source_is_discarded_by_document_title() -> None:
    adapter = _Adapter()

    _discard_copy_source(adapter)

    assert adapter.swApp.closed == ["Assembly1"]
    assert adapter.currentModel is None


@pytest.mark.parametrize(
    "result",
    [(False, 0, 0), (True, 8, 0), True, [True, 0, 0], (1, 0, 0), (True, "0", 0)],
)
def test_in_place_native_save_failure_never_returns_success(
    tmp_path, monkeypatch, result, saved_native_bytes
) -> None:
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(_assembly, "rebuild_if_needed_before_save", lambda *_args: None)
    adapter = _Adapter()
    model = adapter.currentModel
    target = tmp_path / "fr-frame.SLDASM"
    original = saved_native_bytes()
    target.write_bytes(original)
    proof = tmp_path / ".fr-frame.massprops.sha"
    proof.write_text("stale-proof\n", encoding="utf-8")
    calls = []
    model.Save3 = lambda *_args: calls.append(True) or result
    with pytest.raises(RuntimeError, match="Save3"):
        _assembly.save_assembly_in_place(adapter, "fr-frame", True)
    assert calls == [True]
    assert target.read_bytes() == original
    assert not proof.exists()


def test_native_save_warnings_are_nonfatal_and_logged(monkeypatch) -> None:
    import _assembly

    adapter = _Adapter()
    adapter.currentModel.Save3 = lambda *_args: (True, 0, 4)
    messages = []
    monkeypatch.setattr(_assembly._telemetry, "info", messages.append)
    assert _assembly._save_native_assembly(adapter, adapter.currentModel, "fr-frame", 1) == (
        True, 0, 4
    )
    assert any("warnings=4" in message for message in messages)


@pytest.mark.parametrize(
    ("flag", "changed"), [(0, False), (0, True), (2, False), (2, True)]
)
def test_in_place_preflight_refuses_incomplete_or_unsupported_bytes(
    tmp_path, monkeypatch, saved_native_bytes, flag, changed
) -> None:
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    adapter = _Adapter()
    model = adapter.currentModel
    model.props["Revision"] = _config.release_revision()
    model.props["Number"] = assembly_contract("fr-frame").number
    model.summary[0] = "fr-frame"
    model.Save3 = lambda *_args: pytest.fail("invalid saved data reached native save")
    target = tmp_path / "fr-frame.SLDASM"
    original = saved_native_bytes(flag)
    target.write_bytes(original)
    proof = tmp_path / ".fr-frame.massprops.sha"
    proof.write_text("old-proof\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="display"):
        _assembly.save_assembly_in_place(adapter, "fr-frame", changed)
    assert target.read_bytes() == original
    assert proof.read_text(encoding="utf-8") == "old-proof\n"
    assert model.events == []


@pytest.mark.parametrize("consumer", ["copy", "native"])
@pytest.mark.parametrize(
    "defect",
    ["refused", "read_error", "readback_error", "write_error", "truthy_readback",
     "active_changed", "null_config", "missing_active", "foreign_active",
     "empty_names", "missing_names", "enum_error"],
)
def test_display_mark_failure_refuses_the_real_save_consumer(tmp_path, consumer, defect):
    import _assembly

    adapter = _Adapter()
    model = adapter.currentModel
    model.mark_defect = defect
    if defect == "null_config":
        model.GetConfigurationByName = lambda _name: None
    elif defect == "missing_active":
        model.ConfigurationManager.ActiveConfiguration = None
    elif defect == "foreign_active":
        model.ConfigurationManager.ActiveConfiguration.Name = "Absent"
    elif defect in ("empty_names", "missing_names"):
        model.GetConfigurationNames = lambda: [] if defect == "empty_names" else None
    elif defect == "enum_error":
        def unavailable():
            raise RuntimeError("configuration enumeration failed")
        model.GetConfigurationNames = unavailable
    model.Save3 = lambda *_args: pytest.fail("mark failure reached Save3")
    model.SaveAs3 = lambda *_args: pytest.fail("mark failure reached SaveAs3")
    with pytest.raises(RuntimeError):
        if consumer == "copy":
            _assembly._save_new_assembly_as_copy(adapter, tmp_path / "fr-frame.SLDASM")
        else:
            _assembly._save_native_assembly(adapter, model, "fr-frame", 9)


@pytest.mark.parametrize("consumer", ["copy", "native"])
def test_single_configuration_save_never_assigns_unsupported_display_mark(tmp_path, consumer):
    import _assembly

    adapter = _Adapter()
    adapter.currentModel = model = _Model(("Default",))
    model.Save3 = lambda *_args: model.events.append(("save_native",)) or (True, 0, 0)
    if consumer == "copy":
        _assembly._save_new_assembly_as_copy(adapter, tmp_path / "fr-frame.SLDASM")
        assert model.events == [("save_copy", 0, 11)]
    else:
        _assembly._save_native_assembly(adapter, model, "fr-frame", 9)
        assert model.events == [("save_native",)]
    assert model.ConfigurationManager.ActiveConfiguration.Name == "Default"


@pytest.mark.parametrize("flag", [0, 2])
def test_changed_in_place_save_rejects_invalid_output_and_retires_proof(
    tmp_path, monkeypatch, saved_native_bytes, flag
):
    import os
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(_assembly, "rebuild_if_needed_before_save", lambda *_args: None)
    adapter = _Adapter()
    target = tmp_path / "fr-frame.SLDASM"
    target.write_bytes(saved_native_bytes())
    proof = tmp_path / ".fr-frame.massprops.sha"
    proof.write_text("old-proof\n", encoding="utf-8")
    calls = []

    def save3(options, _errors, _warnings):
        calls.append(options)
        assert all(cfg.mark for cfg in adapter.currentModel.configurations.values())
        target.write_bytes(saved_native_bytes(flag))
        stat = target.stat()
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
        return True, 0, 0

    adapter.currentModel.Save3 = save3
    with pytest.raises(RuntimeError, match="display"):
        _assembly.save_assembly_in_place(adapter, "fr-frame", True)
    assert calls == [9]
    assert not proof.exists()


@pytest.mark.parametrize("consumer", ["copy", "native"])
@pytest.mark.parametrize("initial", [True, False, 1, "True", lambda: True])
def test_save_marks_only_configurations_without_a_literal_true_mark(
    tmp_path, consumer, initial
):
    import _assembly

    adapter = _Adapter()
    model = adapter.currentModel
    for cfg in model.configurations.values():
        cfg.mark = initial
    model.Save3 = lambda *_args: model.events.append(("save_native",)) or (True, 0, 0)
    if consumer == "copy":
        _assembly._save_new_assembly_as_copy(adapter, tmp_path / "fr-frame.SLDASM")
        saved = ("save_copy", 0, 11)
    else:
        _assembly._save_native_assembly(adapter, model, "fr-frame", 9)
        saved = ("save_native",)
    expected_marks = [] if initial is True else [
        ("mark", name, True) for name in model.configurations
    ]
    assert model.events == expected_marks + [saved]
    assert all(cfg.mark is True for cfg in model.configurations.values())
    assert model.ConfigurationManager.ActiveConfiguration.Name == "Default"


def test_changed_in_place_mark_readback_failure_retires_proof_before_save(
    tmp_path, monkeypatch, saved_native_bytes
):
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(_assembly, "rebuild_if_needed_before_save", lambda *_args: None)
    adapter = _Adapter()
    adapter.currentModel.mark_defect = "truthy_readback"
    adapter.currentModel.Save3 = lambda *_args: pytest.fail("invalid mark reached Save3")
    target = tmp_path / "fr-frame.SLDASM"
    original = saved_native_bytes()
    target.write_bytes(original)
    proof = tmp_path / ".fr-frame.massprops.sha"
    proof.write_text("old-proof\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="mark"):
        _assembly.save_assembly_in_place(adapter, "fr-frame", True)
    assert target.read_bytes() == original
    assert not proof.exists()


@pytest.mark.parametrize("flag", [0, 2, None])
def test_refresh_strict_preflight_refuses_before_native_open(
    tmp_path, monkeypatch, saved_native_bytes, flag
):
    import asyncio
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    adapter = _Adapter()
    async def forbidden_open(_path):
        pytest.fail("invalid refresh preflight reached native open")
    adapter.open_model = forbidden_open
    target = tmp_path / "fr-frame.SLDASM"
    original = b"malformed native data" if flag is None else saved_native_bytes(flag)
    target.write_bytes(original)
    proof = tmp_path / ".fr-frame.massprops.sha"
    proof.write_text("old-proof\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        asyncio.run(_assembly.refresh_assembly(adapter, "fr-frame"))
    assert target.read_bytes() == original
    assert adapter.currentModel.events == []
    assert proof.read_text(encoding="utf-8") == "old-proof\n"
