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


@pytest.mark.parametrize(
    "asm_name", ["ch-channel", "ch_channel", "ch_channel.SLDASM"]
)
def test_refresh_dof_gate_matches_canonical_artifact_identity(
    tmp_path, monkeypatch, asm_name
) -> None:
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    (tmp_path / ".ch-channel.dof.json").write_text(
        json.dumps(
            {
                "stem": "ch-channel",
                "specs": [
                    {"verify": ["ch-rocker-arm-1", []]},
                    {"verify": ["ch-rocker-arm-1", []]},
                ],
            }
        ),
        encoding="utf-8",
    )
    calls = []
    monkeypatch.setattr(
        _assembly,
        "assert_free_dof_necessity",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    allowed = ("ch-rocker-arm",)
    contract_names = []

    def allowed_stems(name):
        contract_names.append(name)
        return allowed

    monkeypatch.setattr(_assembly, "allowed_free_stems", allowed_stems)
    adapter = object()

    assert_manifest_dof_state(adapter, asm_name, resolve=False)

    assert contract_names == ["ch-channel"]
    assert calls == [
        (
            (adapter, 2),
            {
                "resolve": False,
                "required_instances": ("ch-rocker-arm-1",),
                "allowed_stems": allowed,
            },
        )
    ]


@pytest.mark.parametrize(
    "identity",
    [
        {"stem": "dt-drive-train"},
        {"stem": "channel"},
        {"stem": "ch_channel"},
        {"stem": ""},
        {"stem": None},
        {"stem": 42},
        {},
    ],
)
def test_refresh_dof_gate_refuses_wrong_or_missing_manifest_identity(
    tmp_path, monkeypatch, identity
) -> None:
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    path = tmp_path / ".ch-channel.dof.json"
    # A valid channel witness cannot authorize a manifest naming another assembly.
    contents = json.dumps(
        {**identity, "specs": [{"verify": ["ch-rocker-arm-1", []]}]}
    )
    path.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(
        _assembly,
        "assert_free_dof_necessity",
        lambda *_args, **_kwargs: pytest.fail("untrusted manifest reached DOF gate"),
    )
    monkeypatch.setattr(
        _assembly,
        "allowed_free_stems",
        lambda *_args: pytest.fail("untrusted manifest reached family contract"),
    )
    monkeypatch.setattr(
        _assembly,
        "assert_components_fully_defined",
        lambda *_args, **_kwargs: pytest.fail("invalid manifest used missing fallback"),
    )

    with pytest.raises(RuntimeError, match="expected 'ch-channel'"):
        assert_manifest_dof_state(object(), "ch_channel.SLDASM", resolve=False)

    assert path.read_text(encoding="utf-8") == contents


@pytest.mark.parametrize("resolve", [True, False])
def test_refresh_dof_gate_without_manifest_keeps_strict_gate(
    tmp_path, monkeypatch, resolve
) -> None:
    import _assembly

    monkeypatch.setattr(_assembly, "OUT_SLDASM", tmp_path)
    calls = []
    monkeypatch.setattr(
        _assembly,
        "assert_components_fully_defined",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        _assembly,
        "assert_free_dof_necessity",
        lambda *_args, **_kwargs: pytest.fail("missing manifest reached free-DOF gate"),
    )
    adapter = object()

    assert_manifest_dof_state(adapter, "ch-channel", resolve=resolve)

    assert calls == [((adapter,), {"resolve": resolve})]
    assert not (tmp_path / ".ch-channel.dof.json").exists()


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


def test_unchanged_channel_refresh_still_checks_native_contact_and_revokes_proof(
    tmp_path, monkeypatch
) -> None:
    import _assembly

    assembly_path = tmp_path / "ch-channel.SLDASM"
    assembly_path.write_bytes(b"byte-stable assembly")
    proof = tmp_path / ".ch-channel.massprops.sha"
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
    # The saved assembly already carries an up-to-date "Default Simplified".
    monkeypatch.setattr(
        _assembly, "sync_simplified_configuration", lambda _adapter, _name, *, verify: 0
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
        raise RuntimeError("nanometre contact failed")

    with pytest.raises(RuntimeError, match="nanometre contact failed"):
        asyncio.run(
            _assembly.refresh_assembly(
                adapter,
                "ch-channel",
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
        ("save_assembly_and_images", "ch-channel"),
        ("refresh_assembly", "sm-summing"),
    ],
)
def test_spring_assembly_rejects_missing_native_checker(operation, assembly_name):
    import _assembly

    with pytest.raises(ValueError):
        asyncio.run(getattr(_assembly, operation)(None, assembly_name))


@pytest.mark.parametrize("persisted_failure", ["ch-channel", "sm-summing", None])
def test_auto_repair_saves_every_document_before_persisted_contact_gate(
    persisted_failure, monkeypatch, tmp_path
) -> None:
    parent = SimpleNamespace(
        name="ha-harmonic-analyzer",
        persisted=False,
        ForceRebuild3=lambda _top_only: True,
    )

    def repaired_model(name):
        return SimpleNamespace(
            name=name,
            persisted=False,
            ForceRebuild3=lambda _top_only: True,
        )

    channel = repaired_model("ch-channel")
    summing = repaired_model("sm-summing")
    events = []
    rendered = {}
    proof_states_at_reconcile = []

    class Adapter(_Adapter):
        def __init__(self):
            super().__init__()
            self.currentModel = parent
            self.swApp = SimpleNamespace(
                CloseAllDocuments=lambda _save: events.append(("close", None))
            )

        async def open_model(self, path):
            events.append(("open", path))
            self.currentModel = SimpleNamespace(
                name=Path(path).stem,
                persisted=True,
                ForceRebuild3=lambda _top_only: True,
            )
            return SimpleNamespace(is_success=True, data=None)

        async def list_configurations(self):
            return SimpleNamespace(is_success=True, data=["Default"])

    adapter = Adapter()
    monkeypatch.setattr(verify, "OUT_SLDASM", tmp_path)
    (tmp_path / "ha-harmonic-analyzer.SLDASM").write_bytes(b"parent")
    proofs = {
        name: tmp_path / f".{name}.massprops.sha" for name in ("ch-channel", "sm-summing")
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
            "documents": (("ch-channel", channel), ("sm-summing", summing)),
        },
    )
    monkeypatch.setattr(verify, "_massprops_sidecar", lambda name: proofs[name])

    def save(_adapter, name, geometry_changed, *, model):
        events.append(("save", name))
        return True

    monkeypatch.setattr(verify, "save_assembly_in_place", save)

    async def reconcile(_adapter, name, path):
        proof_states_at_reconcile.append(
            tuple(proof.exists() for proof in proofs.values())
        )
        events.append(("reconcile", name))
        _adapter.currentModel = SimpleNamespace(name=name, persisted=True)

    monkeypatch.setattr(verify, "reconcile_saved_rebuild_state", reconcile)

    def contact(_adapter, name):
        phase = "persisted" if _adapter.currentModel.persisted else "pre-save"
        events.append((f"contact-{phase}", name))
        if phase == "persisted" and name == persisted_failure:
            raise RuntimeError(f"{name} persisted contact failed")

    monkeypatch.setattr(verify, "assert_assembly_spring_contacts", contact)

    async def render(_adapter, name, _views):
        events.append(("render", name))
        rendered[name] = _adapter.currentModel.name
        return {}

    monkeypatch.setattr(verify, "_export_assembly_images", render)
    monkeypatch.setattr(
        verify,
        "discard_open_documents",
        lambda _adapter: events.append(("discard", None)),
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
    save_indices = [events.index(("save", name)) for name in ("ch-channel", "sm-summing")]
    first_reconcile = next(
        index for index, event in enumerate(events) if event[0] == "reconcile"
    )
    assert max(pre_save_indices) < min(save_indices)
    assert max(save_indices) < first_reconcile
    assert all(not any(states) for states in proof_states_at_reconcile)
    assert [event for event in events if event[0] == "reconcile"] == [
        ("reconcile", "ch-channel"),
        ("reconcile", "sm-summing"),
    ]
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
