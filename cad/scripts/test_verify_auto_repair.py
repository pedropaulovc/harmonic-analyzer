"""SolidWorks-free contracts for verify's opt-in cache-dangle repair."""

from __future__ import annotations

import asyncio

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import verify
from _assembly import (
    assert_manifest_dof_state,
    assert_saved_rebuild_clean,
    final_rebuild_before_save,
    rebuild_if_needed_before_save,
)


class _Adapter:
    def __init__(self, status: int = 0) -> None:
        self.currentModel = SimpleNamespace(
            ForceRebuild3=lambda _top_only: True,
            Extension=SimpleNamespace(NeedsRebuild2=status),
        )

    @staticmethod
    def _attempt(operation, default=None):
        try:
            return operation()
        except Exception:
            return default


@pytest.fixture(autouse=True)
def _activate_without_solidworks(monkeypatch):
    def activate(adapter, model, _label):
        adapter.currentModel = model
        return model

    monkeypatch.setattr(verify, "_activate_document", activate)


def test_dangling_faults_accept_only_nonwarning_code_48(monkeypatch) -> None:
    adapter = _Adapter()
    faults = [
        ("Coincident1", 48, False),
        ("WarningMate", 48, True),
        ("OtherError", 2, False),
    ]
    monkeypatch.setattr(verify, "whats_wrong", lambda *_args: faults)
    assert verify._dangling_faults(adapter) == ["top:Coincident1"]


def test_dangling_faults_preserve_production_string_names(monkeypatch) -> None:
    adapter = _Adapter()
    monkeypatch.setattr(
        verify, "whats_wrong", lambda *_args: [("Distance from shaft", 48, False)]
    )
    assert verify._dangling_faults(adapter) == ["top:Distance from shaft"]


def test_auto_repair_requires_clean_reread(monkeypatch) -> None:
    adapter = _Adapter()
    dangling = ("Coincident1", 48, False)
    reads = iter([[dangling], []])
    monkeypatch.setattr(verify, "whats_wrong", lambda *_args: next(reads))
    monkeypatch.setattr(verify, "repair_dangling_mates", lambda _adapter, _model: 1)
    result = verify._repair_cache_dangles(adapter, "ch-channel")
    assert result["rebuilt"] is True
    assert result["documents"] == (("ch-channel", adapter.currentModel),)


def test_auto_repair_rejects_remaining_faults(monkeypatch) -> None:
    adapter = _Adapter()
    dangling = ("Coincident1", 48, False)
    monkeypatch.setattr(verify, "whats_wrong", lambda *_args: [dangling])
    monkeypatch.setattr(verify, "repair_dangling_mates", lambda _adapter, _model: 1)
    with pytest.raises(RuntimeError, match="did not produce a clean assembly"):
        verify._repair_cache_dangles(adapter, "ch-channel")


def test_auto_repair_refuses_mixed_fault_codes(monkeypatch) -> None:
    adapter = _Adapter()
    monkeypatch.setattr(
        verify,
        "whats_wrong",
        lambda *_args: [("Dangling", 48, False), ("Other fault", 2, False)],
    )
    repaired = []
    monkeypatch.setattr(
        verify,
        "repair_dangling_mates",
        lambda *_args: repaired.append(True),
    )
    with pytest.raises(RuntimeError, match="non-48 faults coexist"):
        verify._repair_cache_dangles(adapter, "ch-channel")
    assert repaired == []


def test_auto_repair_repairs_child_assembly_fault(monkeypatch, tmp_path) -> None:
    adapter = _Adapter()
    child = SimpleNamespace(
        GetType=lambda: 2,
        GetPathName=lambda: str(tmp_path / "child.SLDASM"),
        ForceRebuild3=lambda _top_only: True,
    )
    component = SimpleNamespace(Name2="child-1", GetModelDoc2=lambda: child)
    adapter.currentModel.GetComponents = lambda _top_only: [component]
    reads = {
        id(adapter.currentModel): [[], []],
        id(child): [[("ChildMate", 48, False)], []],
    }

    def faults(_adapter, model):
        return reads[id(model)].pop(0)

    repaired_models = []
    monkeypatch.setattr(verify, "whats_wrong", faults)
    monkeypatch.setattr(
        verify,
        "repair_dangling_mates",
        lambda _adapter, model: repaired_models.append(model) or 1,
    )
    result = verify._repair_cache_dangles(adapter, "parent")
    assert repaired_models == [child]
    assert result["rebuilt"] is True
    assert result["documents"] == (("child", child),)


def test_health_failure_points_to_explicit_opt_in(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise RuntimeError("model unhealthy: Coincident1 [48]")

    monkeypatch.setattr(verify, "assert_model_healthy", fail)
    with pytest.raises(RuntimeError, match=r"--auto-repair"):
        verify._assert_soundness_health(_Adapter(), "ch-channel", True)


def test_saved_rebuild_gate_reads_before_any_rebuild() -> None:
    with pytest.raises(RuntimeError, match="NeedsRebuild2=1"):
        assert_saved_rebuild_clean(_Adapter(status=1), "ha-harmonic-analyzer")


def test_final_rebuild_refuses_a_persistently_dirty_model() -> None:
    with pytest.raises(RuntimeError, match="refusing save"):
        final_rebuild_before_save(_Adapter(status=1), "ha-harmonic-analyzer")


def test_final_rebuild_accepts_fully_rebuilt_state() -> None:
    final_rebuild_before_save(_Adapter(status=0), "ha-harmonic-analyzer")


def test_save_chokepoint_skips_rebuild_when_solve_state_is_clean() -> None:
    calls = []
    adapter = _Adapter(status=0)
    adapter.currentModel.ForceRebuild3 = lambda _top_only: calls.append(True) or True
    rebuild_if_needed_before_save(adapter, "ha-harmonic-analyzer")
    assert calls == []




def test_refresh_dof_gate_uses_saved_manifest(tmp_path, monkeypatch) -> None:
    import _assembly

    component = SimpleNamespace(
        Name2="crank-1",
        IsFixed=False,
        IsPatternInstance=lambda: False,
        GetConstrainedStatus=lambda: 2,
    )
    adapter = _Adapter()
    adapter.currentModel.GetComponents = lambda _top_only: [component]
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    # A synthetic assembly with no contract file pins no exact free set.
    monkeypatch.setattr(_assembly, "allowed_free_stems", lambda _name: ())
    (tmp_path / ".free.dof.json").write_text(
        json.dumps({"stem": "free", "specs": [{"verify": ["crank-1", []]}]}),
        encoding="utf-8",
    )
    assert_manifest_dof_state(adapter, "free")


def test_refresh_dof_gate_can_reuse_an_already_resolved_model(
    tmp_path, monkeypatch
) -> None:
    import _assembly

    rebuilds = []
    component = SimpleNamespace(
        Name2="crank-1",
        IsFixed=False,
        IsPatternInstance=lambda: False,
        GetConstrainedStatus=lambda: 2,
    )
    adapter = _Adapter()
    adapter.currentModel.GetComponents = lambda _top_only: [component]
    adapter.currentModel.ForceRebuild3 = lambda _top_only: rebuilds.append(True) or True
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    # A synthetic assembly with no contract file pins no exact free set.
    monkeypatch.setattr(_assembly, "allowed_free_stems", lambda _name: ())
    (tmp_path / ".free.dof.json").write_text(
        json.dumps({"stem": "free", "specs": [{"verify": ["crank-1", []]}]}),
        encoding="utf-8",
    )

    assert_manifest_dof_state(adapter, "free", resolve=False)

    assert rebuilds == []


def test_refresh_dof_gate_rejects_stray_free_component(tmp_path, monkeypatch) -> None:
    import _assembly

    def component(name):
        return SimpleNamespace(
            Name2=name,
            IsFixed=False,
            IsPatternInstance=lambda: False,
            GetConstrainedStatus=lambda: 2,
        )

    adapter = _Adapter()
    adapter.currentModel.GetComponents = lambda _top_only: [
        component("ch-rocker-arm-1"),
        component("structural-bracket-1"),
    ]
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    (tmp_path / ".ch-channel.dof.json").write_text(
        json.dumps({"stem": "ch-channel", "specs": [{"verify": ["ch-rocker-arm-1", []]}]}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="structural-bracket-1"):
        assert_manifest_dof_state(adapter, "ch-channel")


@pytest.mark.parametrize(
    ("flag", "failure"),
    [(1, "nanometre contact failed"), (0, "flag=0"), (2, "unsupported display flag")],
)
def test_unchanged_channel_refresh_refuses_invalid_display_or_contact_and_never_publishes(
    tmp_path, monkeypatch, saved_native_bytes, flag, failure
) -> None:
    import _assembly

    assembly_path = tmp_path / "ch-channel.SLDASM"
    original = saved_native_bytes(flag)
    assembly_path.write_bytes(original)
    proof = tmp_path / ".ch-channel.massprops.sha"
    proof.write_text("same-digest\n", encoding="utf-8")
    saves = []
    contacts = []
    renders = []

    class Adapter(_Adapter):
        async def open_model(self, _path):
            return True

        async def list_configurations(self):
            return ["Default"]

    adapter = Adapter(status=0)
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(_assembly, "check", lambda _label, result: result)
    monkeypatch.setattr(_assembly, "saved_rebuild_status", lambda *_args: 0)
    monkeypatch.setattr(
        _assembly, "active_configuration_name", lambda _adapter: "Default"
    )
    monkeypatch.setattr(_assembly, "_rebuild_faults", lambda _adapter: [])
    monkeypatch.setattr(
        _assembly, "final_rebuild_before_save", lambda _adapter, _name: None
    )

    async def digest(_adapter, _name):
        return "same-digest"

    async def images(_adapter, _name, _views):
        renders.append(True)
        return {}

    monkeypatch.setattr(_assembly, "assembly_geometry_digest", digest)
    # The saved assembly already carries an up-to-date "Default Simplified".
    monkeypatch.setattr(
        _assembly, "sync_simplified_configuration", lambda _adapter, _name: 0
    )
    monkeypatch.setattr(_assembly, "_export_assembly_images", images)
    monkeypatch.setattr(
        _assembly,
        "save_assembly_in_place",
        lambda _adapter, _name, changed: saves.append(changed) or False,
    )
    monkeypatch.setattr(
        _assembly,
        "assert_manifest_dof_state",
        lambda *_args, **_kwargs: pytest.fail("unchanged refresh ran broad DOF gate"),
    )
    monkeypatch.setattr(
        _assembly,
        "check_no_interference",
        lambda *_args, **_kwargs: pytest.fail(
            "unchanged refresh ran broad interference gate"
        ),
    )
    monkeypatch.setattr(
        _assembly,
        "assert_model_healthy",
        lambda *_args, **_kwargs: pytest.fail(
            "unchanged refresh ran broad health gate"
        ),
    )

    def fail_native_contact(_adapter, _name):
        contacts.append(True)
        raise RuntimeError("nanometre contact failed")

    with pytest.raises(RuntimeError, match=failure):
        asyncio.run(
            _assembly.refresh_assembly(
                adapter,
                "ch-channel",
                views=[],
                native_contact_check=fail_native_contact,
            )
        )

    assert saves == ([False] if flag == 1 else [])
    assert contacts == ([True] if flag == 1 else [])
    assert renders == []
    assert assembly_path.read_bytes() == original
    if flag == 1:
        assert not proof.exists()
    else:  # Invalid preflight refuses before touching the old proof.
        assert proof.read_text(encoding="utf-8") == "same-digest\n"


@pytest.mark.parametrize(
    ("operation", "assembly_name"),
    [
        ("save_assembly_and_images", "ch-channel"),
        ("refresh_assembly", "sm-summing"),
    ],
)
def test_spring_assembly_rejects_missing_native_checker(operation, assembly_name):
    import _assembly

    with pytest.raises(ValueError):
        kwargs = (
            {"author": lambda _configuration: None}
            if operation == "save_assembly_and_images"
            else {}
        )
        asyncio.run(getattr(_assembly, operation)(None, assembly_name, **kwargs))


@pytest.mark.parametrize("persisted_failure", ["ch-channel", "sm-summing", None])
def test_auto_repair_saves_every_document_before_persisted_contact_gate(
    persisted_failure, monkeypatch, tmp_path, saved_native_bytes
) -> None:
    import os

    import _assembly

    from test_simplified_helpers import FakeOpenAssembly

    events = []
    rendered = {}
    proof_states_on_saved_open = []
    ordinary_saved_states = {}
    repaired_names = ("ch-channel", "sm-summing")
    proofs = {name: tmp_path / f".{name}.massprops.sha" for name in repaired_names}
    files = {}
    for name in (*repaired_names, "ha-harmonic-analyzer"):
        path = tmp_path / f"{name}.SLDASM"
        path.write_bytes(saved_native_bytes())
        files[name] = SimpleNamespace(
            path=path,
            native=saved_native_bytes,
            stale={"Default": False, "Default Simplified": False},
            display_marks={"Default": False, "Default Simplified": False},
            display_mark_readback=True,
            active="Default",
            events=[],
            save_result=(True, 0, 0),
            stuck=set(),
            saved_flag=None,
            repaired=name not in repaired_names,
        )
    for proof in proofs.values():
        proof.write_text("stale-proof\n", encoding="utf-8")

    class Model(FakeOpenAssembly):
        def __init__(self, file):
            super().__init__(file)
            self.name = file.path.stem
            self.persisted = True
            self.repaired = file.repaired
            self.closed = False

        def GetCustomInfoValue(self, _configuration, property_name):
            return {
                "Revision": _assembly._config.release_revision(),
                "Number": _assembly.assembly_contract(self.name).number,
            }[property_name]

        def SummaryInfo(self, _field):
            return self.name

        def GetSaveFlag(self):
            return not self.persisted

        def SetSaveFlag(self):
            self.persisted = False

        def ForceRebuild3(self, _top_only):
            if self.closed:
                raise RuntimeError(f"{self.name}: document was discarded")
            for configuration in self.configurations.values():
                configuration.NeedsRebuild = False
            return True

        def Save3(self, options, errors, warnings):
            if self.closed:
                raise RuntimeError(f"{self.name}: unsaved repair document was discarded")
            if options == 9:
                # A deep-rebuilt live repair has clean geometry, but its saved
                # child rebuild stamps stay stale until a fresh native solve.
                before = self.file.path.stat().st_mtime_ns
                self.file.repaired = self.repaired
                self.file.stale = dict.fromkeys(self.file.stale, True)
                self.file.display_marks = {
                    name: configuration.LargeDesignReviewMark
                    for name, configuration in self.configurations.items()
                }
                self.file.path.write_bytes(
                    self.file.native(int(all(self.file.display_marks.values())))
                )
                os.utime(self.file.path, ns=(before + 2_000_000_000,) * 2)
                ordinary_saved_states[self.name] = dict(self.file.stale)
                self.persisted = True
                events.append(("save", self.name))
                return True, 0, 0
            # The existing stateful double persists each configuration's solve
            # only when active or rebuild-save marked, and serializes the real
            # display-data requests made by the production save helper.
            return super().Save3(options, errors, warnings)

    class Adapter(_Adapter):
        def __init__(self):
            super().__init__()
            self.open_documents = []
            self.swApp = SimpleNamespace(CloseAllDocuments=self.close_all_documents)

        def close_all_documents(self, _save):
            events.append(("close", None))
            for model in self.open_documents:
                model.closed = True
                model.repaired = model.file.repaired
            self.open_documents.clear()
            return True

        async def open_model(self, path):
            name = Path(path).stem
            events.append(("open", path))
            if name in proofs:
                proof_states_on_saved_open.append(
                    tuple(proof.exists() for proof in proofs.values())
                )
            # Opening copies persisted state; it cannot solve or save anything.
            self.currentModel = Model(files[name])
            self.open_documents.append(self.currentModel)
            return SimpleNamespace(is_success=True, data=None)

        async def list_configurations(self):
            return SimpleNamespace(is_success=True, data=["Default", "Default Simplified"])

    adapter = Adapter()
    monkeypatch.setattr(verify, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)

    monkeypatch.setattr(verify, "_assert_fresh", lambda *_args: True)
    monkeypatch.setattr(verify, "save_assembly_in_place", _assembly.save_assembly_in_place)
    monkeypatch.setattr(
        verify, "reconcile_saved_rebuild_state", _assembly.reconcile_saved_rebuild_state
    )
    monkeypatch.setattr(verify, "_expected_free_dof", lambda _name: 0)
    monkeypatch.setattr(
        verify, "assert_components_fully_defined", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        verify, "assert_no_over_constrained", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(verify, "_assert_soundness_health", lambda *_args: None)
    monkeypatch.setattr(verify, "check_no_interference", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(verify, "assert_channel_independence", lambda *_args: None)
    monkeypatch.setattr(verify, "_dangling_faults", lambda _adapter: ["top:dangle"])

    def repair(_adapter, _name):
        documents = []
        for name in repaired_names:
            model = Model(files[name])
            model.repaired = True
            model.persisted = False
            _adapter.open_documents.append(model)
            documents.append((name, model))
        return {"rebuilt": True, "documents": tuple(documents)}

    monkeypatch.setattr(verify, "_repair_cache_dangles", repair)
    monkeypatch.setattr(verify, "_massprops_sidecar", lambda name: proofs[name])

    def contact(_adapter, name):
        phase = "persisted" if _adapter.currentModel.persisted else "pre-save"
        events.append((f"contact-{phase}", name))
        model = _adapter.currentModel
        if model.closed or model.name != name or not model.repaired:
            raise RuntimeError(f"{name}: repaired geometry unavailable")
        if phase == "persisted" and (
            any(files[name].stale.values()) or model.NeedsRebuild2 != 0
        ):
            raise RuntimeError(f"{name}: persisted rebuild state is dirty")
        if phase == "persisted" and name == persisted_failure:
            raise RuntimeError(f"{name} persisted contact failed")

    monkeypatch.setattr(verify, "assert_assembly_spring_contacts", contact)

    async def render(_adapter, name, _views):
        if any(
            not files[sibling].repaired or any(files[sibling].stale.values())
            for sibling in repaired_names
        ):
            raise RuntimeError("render refuses unsolved persisted repairs")
        if (
            _adapter.currentModel.closed
            or not _adapter.currentModel.persisted
            or _adapter.currentModel.NeedsRebuild2 != 0
        ):
            raise RuntimeError(f"{name}: render requires a clean saved document")
        events.append(("render", name))
        rendered[name] = _adapter.currentModel.name
        return {}

    monkeypatch.setattr(verify, "_export_assembly_images", render)
    monkeypatch.setattr(
        verify, "discard_open_documents", lambda _adapter: _adapter.close_all_documents(True)
    )

    report = verify.Report()
    asyncio.run(
        verify._verify_static_one(
            adapter, "ha-harmonic-analyzer", report, auto_repair=True
        )
    )

    pre_save_indices = [
        events.index(("contact-pre-save", name)) for name in ("ch-channel", "sm-summing")
    ]
    save_indices = [events.index(("save", name)) for name in repaired_names]
    assert max(pre_save_indices) < min(save_indices)
    assert ordinary_saved_states == {
        name: {"Default": True, "Default Simplified": True} for name in repaired_names
    }
    for name in repaired_names:
        assert files[name].repaired
        assert not any(files[name].stale.values())
        assert all(files[name].display_marks.values())
    assert proof_states_on_saved_open
    assert all(not any(states) for states in proof_states_on_saved_open)
    assert ("contact-persisted", "ch-channel") in events
    assert ("contact-persisted", "sm-summing") in events
    assert all(not proof.exists() for proof in proofs.values())
    if persisted_failure is None:
        assert report.failed == []
        assert rendered == {
            "ch-channel": "ch-channel",
            "sm-summing": "sm-summing",
            "ha-harmonic-analyzer": "ha-harmonic-analyzer",
        }
        last_certification = max(
            index
            for index, event in enumerate(events)
            if event[0] == "contact-persisted"
        )
        first_render = next(
            index for index, event in enumerate(events) if event[0] == "render"
        )
        assert last_certification < first_render
        return
    assert rendered == {}
    failed_label = f"{persisted_failure}:auto-repair-persisted-spring-native-contacts"
    assert (
        failed_label,
        f"{persisted_failure} persisted contact failed",
    ) in report.failed
    assert failed_label not in report.passed
