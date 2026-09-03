"""SolidWorks-free contracts for verify's opt-in cache-dangle repair."""

from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

import verify
from _assembly import (
    assert_manifest_dof_state,
    assert_saved_rebuild_clean,
    final_rebuild_before_save,
    rebuild_if_needed_before_save,
    save_assembly_and_images,
    save_assembly_in_place,
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


def test_repair_save_path_targets_each_repaired_document() -> None:
    source = verify.Path(verify.__file__).read_text(encoding="utf-8")
    assert "for repaired_name, model in repaired_documents:" in source
    assert "geometry_changed=True, model=m" in source
    assert "if name not in rendered:" in source
    assert "_run_soundness_battery(" in source
    assert "discard_open_documents(adapter)" in source


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


def test_in_place_save_checks_solve_state_at_the_save_chokepoint() -> None:
    source = inspect.getsource(save_assembly_in_place)
    rebuild = source.index("rebuild_if_needed_before_save(adapter, asm_name, asm)")
    save = source.index("asm.Save3(options, 0, 0)")
    assert rebuild < source.index("asm.GetSaveFlag()") < save
    assert "_ensure_assembly_revision(adapter, asm)" in source
    assert "must_save = geometry_changed or revision_changed" in source
    assert "final_rebuild_before_save(adapter, asm_name, asm)" not in source


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


def test_fresh_build_creates_and_collapses_native_exploded_view(monkeypatch) -> None:
    import _assembly

    calls: list[tuple[object, ...]] = []
    assembly = SimpleNamespace(
        GetExplodedViewCount2=lambda configuration: (
            calls.append(("count", configuration)) or 0
        ),
        AutoExplode=lambda: calls.append(("auto",)) or True,
        GetExplodedViewNames2=lambda configuration: (
            calls.append(("names", configuration)) or ("ExplView1",)
        ),
        ShowExploded2=lambda shown, name: calls.append(("show", shown, name)) or True,
    )
    model = SimpleNamespace(EditRebuild3=lambda: calls.append(("rebuild",)) or True)
    adapter = SimpleNamespace(currentModel=model)
    monkeypatch.setattr(
        _assembly,
        "_early_bound",
        lambda value, interface: assembly if interface == "IAssemblyDoc" else value,
    )
    monkeypatch.setattr(
        _assembly,
        "active_configuration_name",
        lambda _adapter, _model: "Default",
    )

    assert _assembly._ensure_exploded_view(adapter, "channel") == "ExplView1"
    assert calls == [
        ("count", "Default"),
        ("auto",),
        ("rebuild",),
        ("names", "Default"),
        ("show", False, "ExplView1"),
    ]


def test_existing_exploded_view_is_reused_without_auto_explode(monkeypatch) -> None:
    import _assembly

    calls: list[tuple[object, ...]] = []
    assembly = SimpleNamespace(
        GetExplodedViewCount2=lambda configuration: 1,
        AutoExplode=lambda: (_ for _ in ()).throw(AssertionError("duplicate explode")),
        GetExplodedViewNames2=lambda configuration: ("ExplView1",),
        ShowExploded2=lambda shown, name: calls.append(("show", shown, name)) or True,
    )
    adapter = SimpleNamespace(currentModel=SimpleNamespace())
    monkeypatch.setattr(
        _assembly,
        "_early_bound",
        lambda value, interface: assembly if interface == "IAssemblyDoc" else value,
    )
    monkeypatch.setattr(
        _assembly,
        "active_configuration_name",
        lambda _adapter, _model: "Default",
    )

    assert _assembly._ensure_exploded_view(adapter, "channel") == "ExplView1"
    assert calls == [("show", False, "ExplView1")]


def test_fresh_build_checks_solve_state_after_gates_and_view_setup() -> None:
    source = inspect.getsource(save_assembly_and_images)
    assert source.count("final_rebuild_before_save(adapter, asm_name)") == 1
    assert source.count("rebuild_if_needed_before_save(adapter, asm_name)") == 1
    assert source.index(
        "rebuild_if_needed_before_save(adapter, asm_name)"
    ) < source.index("_save_new_assembly_as_copy(adapter, asm_path)")
    assert source.index("_ensure_exploded_view(adapter, asm_name)") < source.index(
        "final_rebuild_before_save(adapter, asm_name)"
    )


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


def test_refresh_reuses_one_resolved_state_across_gates_and_save() -> None:
    import _assembly

    source = inspect.getsource(_assembly.refresh_assembly)
    assert source.count("final_rebuild_before_save(adapter, asm_name)") == 1
    assert "assert_manifest_dof_state(adapter, asm_name, resolve=False)" in source
    assert (
        "assert_model_healthy(adapter, label=asm_name, deep=True, rebuilt=True)"
        in source
    )


def test_multi_config_digest_resolves_each_lazy_activation() -> None:
    import _assembly

    source = inspect.getsource(_assembly.assembly_geometry_digest)
    assert "async def activate_resolved(cfg: str)" in source
    assert "await activate_resolved(cfg)" in source
    assert "await activate_resolved(rest)" in source
    assert "geometry_digest.resolve_configuration" in source
    assert "status = saved_rebuild_status(adapter)" in source
    assert "if status != 0" in source


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
