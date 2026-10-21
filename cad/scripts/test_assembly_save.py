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


def _refresh_in_place_pipeline(
    tmp_path, monkeypatch, saved_native_bytes, asm_name="ha-harmonic-analyzer"
):
    """Keep real rebuild/gate/in-place/native-save helpers around a fake COM model."""
    import os
    import _assembly
    from types import SimpleNamespace as NS

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    adapter = _Adapter()
    adapter.currentModel = model = _Model(("Default",))
    model.props.update(
        Revision=_config.release_revision(), Number=assembly_contract(asm_name).number
    )
    model.summary[0] = asm_name
    model.Extension.NeedsRebuild2 = 0
    model.IsExploded = lambda: False
    model.GetSaveFlag = lambda: True
    model.rebuild_count = 0
    model.receiver_gap_mm = 0.1
    target = tmp_path / f"{asm_name}.SLDASM"
    original = saved_native_bytes()
    target.write_bytes(original)
    proof = tmp_path / f".{asm_name}.massprops.sha"
    proof.write_text("previous\n", encoding="utf-8")
    events = []
    certified_gaps = []

    def rebuild(top_only):
        assert top_only is False
        model.rebuild_count += 1
        model.Extension.NeedsRebuild2 = 0
        events.append("rebuild")
        return True

    def save3(options, errors, warnings):
        assert (options, errors, warnings) == (9, 0, 0)
        assert model.Extension.NeedsRebuild2 == 0
        assert not proof.exists()
        events.append("save")
        before = target.stat()
        target.write_bytes(saved_native_bytes(1, 1))
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns + 10**9))
        return True, 0, 0

    def isometric(_adapter):
        events.append("iso")
        model.Extension.NeedsRebuild2 = 1

    def native(current, name):
        assert current is adapter and name == asm_name
        assert not proof.exists()
        events.append("native")
        certified_gaps.append(model.receiver_gap_mm)
        if model.receiver_gap_mm <= 0:
            raise RuntimeError("receiver added-strip collision")

    async def opened(_path):
        events.append("open")
        return NS(is_success=True, data={}, error=None)

    async def configurations():
        return NS(is_success=True, data=["Default"], error=None)

    async def digest(*_args):
        events.append("digest")
        return "current"

    async def reconcile(*_args):
        events.append("reconcile")

    async def images(*_args):
        events.append("images")
        return {}

    model.ForceRebuild3 = rebuild
    model.Save3 = save3
    adapter.open_model = opened
    adapter.list_configurations = configurations
    monkeypatch.setattr(_assembly, "sync_simplified_configuration", lambda *_a, **_k: 0)
    monkeypatch.setattr(_assembly, "_rebuild_faults", lambda *_a: [])
    for gate in ("assert_manifest_dof_state", "check_no_interference", "assert_model_healthy"):
        monkeypatch.setattr(_assembly, gate, lambda *_a, **_k: None)
    monkeypatch.setattr(_assembly, "assembly_geometry_digest", digest)
    monkeypatch.setattr(_assembly, "set_isometric_view", isometric)
    monkeypatch.setattr(_assembly, "reconcile_saved_rebuild_state", reconcile)
    monkeypatch.setattr(_assembly, "_export_assembly_images", images)
    return NS(
        adapter=adapter, model=model, target=target, original=original, proof=proof,
        events=events, certified_gaps=certified_gaps, native=native, asm_name=asm_name,
    )


@pytest.mark.parametrize("fingerprint_changed", [False, True])
def test_refresh_final_rebuild_collision_refuses_before_overwrite_or_proof(
    tmp_path, monkeypatch, saved_native_bytes, fingerprint_changed
):
    import asyncio
    import _assembly

    p = _refresh_in_place_pipeline(tmp_path, monkeypatch, saved_native_bytes)
    if not fingerprint_changed:
        # A no-op fingerprint can still need a metadata-only overwrite. Its
        # real title restamp happens after the first native certification.
        p.proof.write_text("current\n", encoding="utf-8")
        p.model.summary[0] = "stale title"
        set_summary = p.model.SetSummaryInfo

        def dirtying_summary(field, value):
            set_summary(field, value)
            p.model.Extension.NeedsRebuild2 = 1

        p.model.SetSummaryInfo = dirtying_summary
    rebuild = p.model.ForceRebuild3

    def geometry_changes_on_last_rebuild(top_only):
        result = rebuild(top_only)
        if p.certified_gaps:
            p.model.receiver_gap_mm = -0.01
        return result

    p.model.ForceRebuild3 = geometry_changes_on_last_rebuild
    with pytest.raises(RuntimeError, match="receiver added-strip collision"):
        asyncio.run(_assembly.refresh_assembly(
            p.adapter, p.asm_name, [], native_contact_check=p.native,
        ))
    assert p.model.rebuild_count == 3
    assert p.certified_gaps == [0.1, -0.01]
    assert p.target.read_bytes() == p.original
    assert not p.proof.exists()
    assert not {"save", "reconcile", "images"}.intersection(p.events)
    assert ("iso" in p.events) is fingerprint_changed


@pytest.mark.parametrize("dirty_view", [False, True])
def test_refresh_recertifies_only_after_a_last_mile_rebuild(
    tmp_path, monkeypatch, saved_native_bytes, dirty_view
):
    import asyncio
    import _assembly

    p = _refresh_in_place_pipeline(tmp_path, monkeypatch, saved_native_bytes)
    if not dirty_view:
        monkeypatch.setattr(
            _assembly, "set_isometric_view", lambda _adapter: p.events.append("iso")
        )
    asyncio.run(_assembly.refresh_assembly(
        p.adapter, p.asm_name, [], native_contact_check=p.native,
    ))
    assert p.events == (
        ["open", "rebuild", "rebuild", "digest", "native", "iso"]
        + (["rebuild", "native"] if dirty_view else [])
        + ["save", "reconcile", "native", "images"]
    )
    assert p.model.rebuild_count == (3 if dirty_view else 2)
    assert p.target.read_bytes() == saved_native_bytes(1, 1)
    assert p.proof.read_text(encoding="utf-8") == "current\n"


@pytest.mark.parametrize("always_dirty", [False, True])
def test_refresh_last_mile_gate_retries_or_refuses_a_dirty_callback(
    tmp_path, monkeypatch, saved_native_bytes, always_dirty
):
    import asyncio
    import _assembly

    p = _refresh_in_place_pipeline(tmp_path, monkeypatch, saved_native_bytes)
    final_gate_calls = []

    def dirtying_native(adapter, name):
        p.native(adapter, name)
        if "iso" in p.events and "save" not in p.events:
            final_gate_calls.append(p.model.rebuild_count)
            if always_dirty or len(final_gate_calls) == 1:
                p.model.Extension.NeedsRebuild2 = 1

    def refresh():
        return asyncio.run(_assembly.refresh_assembly(
            p.adapter, p.asm_name, [], native_contact_check=dirtying_native,
        ))

    if always_dirty:
        with pytest.raises(RuntimeError, match="NeedsRebuild2=1"):
            refresh()
        assert p.target.read_bytes() == p.original
        assert not p.proof.exists()
        assert not {"save", "reconcile", "images"}.intersection(p.events)
    else:
        refresh()
        assert p.target.read_bytes() == saved_native_bytes(1, 1)
        assert p.proof.read_text(encoding="utf-8") == "current\n"
    assert final_gate_calls == [3, 4]
    assert p.model.rebuild_count == 4


@pytest.mark.parametrize("asm_name", ["ch-channel", "sm-summing"])
@pytest.mark.parametrize("changed", [False, True])
def test_refresh_preserves_channel_and_summing_post_reconcile_native_contract(
    tmp_path, monkeypatch, saved_native_bytes, asm_name, changed
):
    import asyncio
    import _assembly

    p = _refresh_in_place_pipeline(tmp_path, monkeypatch, saved_native_bytes, asm_name)
    if not changed:
        p.proof.write_text("current\n", encoding="utf-8")
    asyncio.run(_assembly.refresh_assembly(
        p.adapter, asm_name, [], native_contact_check=p.native,
    ))
    assert p.events == (
        ["open", "rebuild", "rebuild", "digest"]
        + (["iso", "rebuild", "save", "reconcile"] if changed else [])
        + ["native", "images"]
    )
    assert p.certified_gaps == [0.1]
    assert p.target.read_bytes() == (saved_native_bytes(1, 1) if changed else p.original)
    assert p.proof.read_text(encoding="utf-8") == "current\n"
