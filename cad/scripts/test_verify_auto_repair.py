"""SolidWorks-free contracts for verify's opt-in cache-dangle repair."""

from __future__ import annotations

import asyncio

import json
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
    result = verify._repair_cache_dangles(adapter, "channel")
    assert result["rebuilt"] is True
    assert result["documents"] == (("channel", adapter.currentModel),)


def test_auto_repair_rejects_remaining_faults(monkeypatch) -> None:
    adapter = _Adapter()
    dangling = ("Coincident1", 48, False)
    monkeypatch.setattr(verify, "whats_wrong", lambda *_args: [dangling])
    monkeypatch.setattr(verify, "repair_dangling_mates", lambda _adapter, _model: 1)
    with pytest.raises(RuntimeError, match="did not produce a clean assembly"):
        verify._repair_cache_dangles(adapter, "channel")


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
        verify._repair_cache_dangles(adapter, "channel")
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
        verify._assert_soundness_health(_Adapter(), "channel", True)


def test_saved_rebuild_gate_reads_before_any_rebuild() -> None:
    with pytest.raises(RuntimeError, match="NeedsRebuild2=1"):
        assert_saved_rebuild_clean(_Adapter(status=1), "harmonic-analyzer")


def test_final_rebuild_refuses_a_persistently_dirty_model() -> None:
    with pytest.raises(RuntimeError, match="refusing save"):
        final_rebuild_before_save(_Adapter(status=1), "harmonic-analyzer")


def test_final_rebuild_accepts_fully_rebuilt_state() -> None:
    final_rebuild_before_save(_Adapter(status=0), "harmonic-analyzer")


def test_save_chokepoint_skips_rebuild_when_solve_state_is_clean() -> None:
    calls = []
    adapter = _Adapter(status=0)
    adapter.currentModel.ForceRebuild3 = lambda _top_only: calls.append(True) or True
    rebuild_if_needed_before_save(adapter, "harmonic-analyzer")
    assert calls == []


def test_in_place_save_restamps_stale_revision(monkeypatch) -> None:
    import _assembly

    expected = _assembly._config.release_revision()
    stale = f"v{int(expected[1:]) - 1}"
    model = SimpleNamespace(
        GetCustomInfoValue=lambda _configuration, name: (
            stale if name == "Revision" else ""
        )
    )
    adapter = _Adapter()
    writes = []
    monkeypatch.setattr(
        _assembly,
        "apply_custom_properties",
        lambda _adapter, props, *, model=None: writes.append((props, model)),
    )
    assert _assembly._ensure_assembly_revision(adapter, model) is True
    assert writes == [({"Revision": expected}, model)]


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
        component("rocker-arm-1"),
        component("structural-bracket-1"),
    ]
    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    (tmp_path / ".channel.dof.json").write_text(
        json.dumps({"stem": "channel", "specs": [{"verify": ["rocker-arm-1", []]}]}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="structural-bracket-1"):
        assert_manifest_dof_state(adapter, "channel")


def test_unchanged_channel_refresh_still_checks_native_contact_and_revokes_proof(
    tmp_path, monkeypatch
) -> None:
    import _assembly

    assembly_path = tmp_path / "channel.SLDASM"
    assembly_path.write_bytes(b"byte-stable assembly")
    proof = tmp_path / ".channel.massprops.sha"
    proof.write_text("same-digest\n", encoding="utf-8")
    saves = []

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
        return {}

    monkeypatch.setattr(_assembly, "assembly_geometry_digest", digest)
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
        raise RuntimeError("nanometre contact failed")

    with pytest.raises(RuntimeError, match="nanometre contact failed"):
        asyncio.run(
            _assembly.refresh_assembly(
                adapter,
                "channel",
                views=[],
                native_contact_check=fail_native_contact,
            )
        )

    assert saves == [False]
    assert assembly_path.read_bytes() == b"byte-stable assembly"
    assert not proof.exists()


@pytest.mark.parametrize(
    ("operation", "assembly_name"),
    [
        ("save_assembly_and_images", "channel"),
        ("refresh_assembly", "summing"),
    ],
)
def test_spring_assembly_rejects_missing_native_checker(operation, assembly_name):
    import _assembly

    with pytest.raises(ValueError):
        asyncio.run(getattr(_assembly, operation)(None, assembly_name))


@pytest.mark.parametrize("persisted_failure", ["channel", "summing"])
def test_auto_repair_saves_every_document_before_persisted_contact_gate(
    persisted_failure, monkeypatch, tmp_path
) -> None:
    parent = SimpleNamespace(
        name="harmonic-analyzer",
        persisted=False,
        ForceRebuild3=lambda _top_only: True,
    )

    def repaired_model(name):
        return SimpleNamespace(
            name=name,
            persisted=False,
            ForceRebuild3=lambda _top_only: True,
        )

    channel = repaired_model("channel")
    summing = repaired_model("summing")
    events = []

    class Adapter(_Adapter):
        def __init__(self):
            super().__init__()
            self.currentModel = parent
            self.swApp = SimpleNamespace(
                CloseAllDocuments=lambda _save: events.append(("close", None))
            )

        async def open_model(self, path):
            events.append(("open", path))
            self.currentModel = parent
            return SimpleNamespace(is_success=True, data=None)

        async def list_configurations(self):
            return SimpleNamespace(is_success=True, data=["Default"])

    adapter = Adapter()
    monkeypatch.setattr(verify, "OUT_SLDASM", tmp_path)
    (tmp_path / "harmonic-analyzer.SLDASM").write_bytes(b"parent")
    proofs = {
        name: tmp_path / f".{name}.massprops.sha" for name in ("channel", "summing")
    }
    for proof in proofs.values():
        proof.write_text("stale-proof\n", encoding="utf-8")

    monkeypatch.setattr(verify, "_assert_fresh", lambda *_args: True)
    monkeypatch.setattr(verify, "assert_saved_rebuild_clean", lambda *_args: None)
    monkeypatch.setattr(verify, "active_configuration_name", lambda _adapter: "Default")
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
    monkeypatch.setattr(
        verify,
        "_repair_cache_dangles",
        lambda *_args: {
            "rebuilt": True,
            "documents": (("channel", channel), ("summing", summing)),
        },
    )
    monkeypatch.setattr(verify, "_massprops_sidecar", lambda name: proofs[name])

    def save(_adapter, name, geometry_changed, *, model):
        assert geometry_changed is True
        assert _adapter.currentModel is model
        events.append(("save", name))
        return True

    monkeypatch.setattr(verify, "save_assembly_in_place", save)

    async def reconcile(_adapter, name, path):
        assert path == tmp_path / f"{name}.SLDASM"
        assert [event for event in events if event[0] == "save"] == [
            ("save", "channel"),
            ("save", "summing"),
        ]
        assert all(not proof.exists() for proof in proofs.values())
        events.append(("reconcile", name))
        _adapter.currentModel = SimpleNamespace(name=name, persisted=True)

    monkeypatch.setattr(verify, "reconcile_saved_rebuild_state", reconcile)

    def contact(_adapter, name):
        phase = "persisted" if _adapter.currentModel.persisted else "pre-save"
        events.append((f"contact-{phase}", name))
        if phase == "persisted" and name == persisted_failure:
            raise RuntimeError(f"{name} persisted contact failed")

    monkeypatch.setattr(verify, "assert_assembly_spring_contacts", contact)
    monkeypatch.setattr(
        verify,
        "_export_assembly_images",
        lambda *_args, **_kwargs: pytest.fail(
            "renders must not run before all persisted contact gates pass"
        ),
    )
    monkeypatch.setattr(
        verify,
        "discard_open_documents",
        lambda _adapter: events.append(("discard", None)),
    )

    report = verify.Report()
    asyncio.run(
        verify._verify_static_one(
            adapter, "harmonic-analyzer", report, auto_repair=True
        )
    )

    assert ("contact-pre-save", "channel") in events
    assert ("contact-pre-save", "summing") in events
    assert [event for event in events if event[0] == "reconcile"] == [
        ("reconcile", "channel"),
        ("reconcile", "summing"),
    ]
    assert ("contact-persisted", "channel") in events
    assert ("contact-persisted", "summing") in events
    failed_label = f"{persisted_failure}:auto-repair-persisted-spring-native-contacts"
    assert (
        failed_label,
        f"{persisted_failure} persisted contact failed",
    ) in report.failed
    assert failed_label not in report.passed
    assert all(not proof.exists() for proof in proofs.values())
