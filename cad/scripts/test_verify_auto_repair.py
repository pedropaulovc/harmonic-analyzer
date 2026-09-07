"""SolidWorks-free contracts for verify's opt-in cache-dangle repair."""

from __future__ import annotations

import inspect
import json
import asyncio
import hashlib
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


def test_fresh_build_checks_solve_state_after_gates_and_view_setup() -> None:
    source = inspect.getsource(save_assembly_and_images)
    assert source.count("final_rebuild_before_save(adapter, asm_name)") == 1
    assert source.count("rebuild_if_needed_before_save(adapter, asm_name)") == 1
    assert source.index(
        "rebuild_if_needed_before_save(adapter, asm_name)"
    ) < source.index("_save_new_assembly_as_copy(adapter, asm_path)")


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


@pytest.fixture
def resolved_mass_reader(monkeypatch):
    import _assembly_mass_properties as reader

    calls = []
    after_read = []
    inertia = [0.11, 0.12, 0.13, 0.21, 0.22, 0.23, 0.31, 0.32, 0.33]

    def read_inertia(reference):
        calls.append(("inertia", reference))
        for operation in after_read:
            operation()
        return inertia

    mass = SimpleNamespace(
        Volume=0.0025,
        SurfaceArea=0.75,
        Mass=19.5,
        CenterOfMass=[0.012, -0.034, 0.056],
        GetMomentOfInertia=read_inertia,
    )

    def create():
        calls.append(("create",))
        return mass

    def forbidden(*_args, **_kwargs):
        pytest.fail("resolved mass read must not rebuild, activate, save, or fall back")

    extension = SimpleNamespace(NeedsRebuild2=0, CreateMassProperty=create)
    configuration = SimpleNamespace(Name="Default")
    manager = SimpleNamespace(ActiveConfiguration=configuration)

    def wrapper():
        return SimpleNamespace(
            native_id=17,
            Extension=extension,
            ConfigurationManager=manager,
            GetType=lambda: 2,
            ForceRebuild3=forbidden,
            Save3=forbidden,
        )

    expected, current, active = wrapper(), wrapper(), wrapper()

    def same(left, right):
        calls.append(("same",))
        return int(left.native_id == right.native_id)

    adapter = SimpleNamespace(
        currentModel=current,
        swApp=SimpleNamespace(ActiveDoc=active, IsSame=same),
        get_mass_properties=forbidden,
        set_active_configuration=forbidden,
    )
    monkeypatch.setattr(reader, "_early_bound", lambda value, _interface: value)

    def read():
        return reader.read_resolved_mass_properties(
            adapter,
            expected_model=expected,
            expected_configuration="Default",
        )

    return SimpleNamespace(
        read=read, adapter=adapter, expected=expected, mass=mass,
        extension=extension, configuration=configuration, inertia=inertia,
        calls=calls, after_read=after_read,
    )


def test_resolved_mass_reader_preserves_legacy_units_and_tensor_mapping(resolved_mass_reader):
    from solidworks_mcp.adapters.base import MassProperties

    trial = resolved_mass_reader
    result = trial.read()
    assert isinstance(result, MassProperties)
    assert result.volume == 2_500_000.0
    assert result.surface_area == 750_000.0
    assert result.mass == 19.5
    assert result.center_of_mass == pytest.approx([12.0, -34.0, 56.0])
    assert result.moments_of_inertia == {
        "Ixx": 0.11, "Iyy": 0.22, "Izz": 0.33,
        "Ixy": 0.12, "Ixz": 0.13, "Iyz": 0.23,
    }
    assert trial.calls.count(("create",)) == 1
    assert trial.calls.count(("inertia", 0)) == 1
    assert trial.calls.count(("same",)) >= 4
    # A second call must acquire a fresh native mass-property object.
    trial.read()
    assert trial.calls.count(("create",)) == 2


def test_resolved_mass_reader_accepts_tuple_vectors(resolved_mass_reader):
    trial = resolved_mass_reader
    expected = trial.read()
    trial.mass.CenterOfMass = tuple(trial.mass.CenterOfMass)

    def tuple_inertia(reference):
        assert reference == 0
        return tuple(trial.inertia)

    trial.mass.GetMomentOfInertia = tuple_inertia
    assert trial.read().model_dump() == expected.model_dump()


@pytest.mark.parametrize(
    "missing", [{"expected_model": None}, {"expected_configuration": ""}]
)
def test_resolved_mass_reader_requires_expected_model_and_configuration(
    resolved_mass_reader, missing
):
    from _assembly_mass_properties import read_resolved_mass_properties

    trial = resolved_mass_reader
    expected = {
        "expected_model": trial.expected,
        "expected_configuration": "Default",
        **missing,
    }
    with pytest.raises(RuntimeError, match="requires a model and configuration"):
        read_resolved_mass_properties(trial.adapter, **expected)
    assert ("create",) not in trial.calls


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("missing", ["extension", "rebuild status"])
def test_resolved_mass_reader_requires_readable_solve_state(
    resolved_mass_reader, phase, missing
):
    trial = resolved_mass_reader

    def corrupt():
        if missing == "extension":
            trial.expected.Extension = None
        if missing == "rebuild status":
            trial.extension.NeedsRebuild2 = None

    if phase == "before":
        corrupt()
    if phase == "after":
        trial.after_read.append(corrupt)
    with pytest.raises(RuntimeError):
        trial.read()
    assert trial.calls.count(("create",)) == (0 if phase == "before" else 1)


@pytest.mark.parametrize("phase", ["before", "after"])
@pytest.mark.parametrize("fault", ["current", "active", "indeterminate", "configuration", "dirty"])
def test_resolved_mass_reader_rejects_changed_or_unresolved_state(
    resolved_mass_reader, phase, fault
):
    trial = resolved_mass_reader

    def corrupt():
        if fault == "current":
            trial.adapter.currentModel.native_id = 99
        if fault == "active":
            trial.adapter.swApp.ActiveDoc.native_id = 99
        if fault == "indeterminate":
            trial.adapter.swApp.IsSame = lambda *_args: -1
        if fault == "configuration":
            trial.configuration.Name = "Other"
        if fault == "dirty":
            trial.extension.NeedsRebuild2 = 1

    if phase == "before":
        corrupt()
    if phase == "after":
        trial.after_read.append(corrupt)
    with pytest.raises(RuntimeError):
        trial.read()
    assert trial.calls.count(("create",)) == (0 if phase == "before" else 1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("CenterOfMass", None), ("CenterOfMass", [1.0, 2.0]),
        ("CenterOfMass", [1.0, 2.0, 3.0, 4.0]), ("CenterOfMass", "123"),
        ("inertia", None), ("inertia", [0.0] * 8),
        ("inertia", [0.0] * 10), ("inertia", "123456789"),
        ("Mass", float("nan")), ("Volume", float("inf")), ("Volume", 1e308),
        ("SurfaceArea", float("-inf")),
        ("Mass", "not numeric"),
        ("CenterOfMass", [0.0, "not numeric", 0.0]),
        ("inertia", [0.0, 0.0, 0.0, "not numeric", 0.0, 0.0, 0.0, 0.0, 0.0]),
        ("CenterOfMass", [0.0, float("nan"), 0.0]),
        ("inertia", [0.0, 0.0, 0.0, float("inf"), 0.0, 0.0, 0.0, 0.0, 0.0]),
    ],
)
def test_resolved_mass_reader_rejects_malformed_or_nonfinite_properties(
    resolved_mass_reader, field, value
):
    trial = resolved_mass_reader
    if field == "inertia":
        trial.mass.GetMomentOfInertia = lambda _reference: value
    if field != "inertia":
        setattr(trial.mass, field, value)
    with pytest.raises(RuntimeError):
        trial.read()


def test_resolved_mass_reader_rejects_null_mass_object(resolved_mass_reader):
    trial = resolved_mass_reader
    trial.extension.CreateMassProperty = lambda: None
    with pytest.raises(RuntimeError):
        trial.read()


@pytest.mark.parametrize("missing", ["current", "active"])
def test_resolved_mass_reader_rejects_missing_documents(resolved_mass_reader, missing):
    trial = resolved_mass_reader
    if missing == "current":
        trial.adapter.currentModel = None
    if missing == "active":
        trial.adapter.swApp.ActiveDoc = None
    with pytest.raises(RuntimeError):
        trial.read()
    assert ("create",) not in trial.calls


@pytest.fixture
def digest_trial(monkeypatch):
    import _assembly
    from solidworks_mcp.adapters.base import MassProperties

    calls = []
    configuration = SimpleNamespace(Name="Default")
    transform = [1.00000012, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
                 0.012341, -0.056781, 0.090121, 1.0, 0.0, 0.0, 0.0]
    components = [
        SimpleNamespace(Name2=name, Transform2=SimpleNamespace(ArrayData=list(transform)))
        for name in ("z-part-1", "a-part-1")
    ]
    mass = MassProperties(
        mass=1.23456789, volume=1234.56789, surface_area=2345.67891,
        center_of_mass=[1.234567, -2.345678, 3.456789],
        moments_of_inertia={
            "Ixx": 0.111119, "Iyy": 0.222229, "Izz": 0.333339,
            "Ixy": 0.444449, "Ixz": 0.555559, "Iyz": 0.666669,
        },
    )
    state = SimpleNamespace(configs=["Default"], rebuilt=True, status_after_rebuild=0)
    adapter = _Adapter()
    adapter.currentModel.ConfigurationManager = SimpleNamespace(ActiveConfiguration=configuration)

    async def configs():
        return SimpleNamespace(is_success=True, data=state.configs)

    async def activate(name):
        calls.append(("activate", name))
        configuration.Name = name
        adapter.currentModel.Extension.NeedsRebuild2 = 1
        return SimpleNamespace(is_success=True, data=None)

    def rebuild(top_only):
        calls.append(("rebuild", configuration.Name, top_only))
        adapter.currentModel.Extension.NeedsRebuild2 = state.status_after_rebuild
        return state.rebuilt

    original_model = adapter.currentModel

    def properties(caller, *, expected_model: object, expected_configuration: str):
        assert caller is adapter
        assert expected_model is original_model
        assert expected_configuration == configuration.Name
        calls.append(("mass", configuration.Name))
        return mass

    def forbidden_mass_read():
        pytest.fail("geometry digest must not call the rebuilding adapter mass reader")

    def component_list(top_only):
        calls.append(("poses", configuration.Name, top_only))
        return components

    adapter.list_configurations = configs
    adapter.set_active_configuration = activate
    adapter.get_mass_properties = forbidden_mass_read
    adapter.currentModel.ForceRebuild3 = rebuild
    adapter.currentModel.GetComponents = component_list
    monkeypatch.setattr(_assembly, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_assembly, "read_resolved_mass_properties", properties)
    return SimpleNamespace(
        digest=lambda: asyncio.run(_assembly.assembly_geometry_digest(adapter, "test-assembly")),
        adapter=adapter, calls=calls, state=state, configuration=configuration,
        components=components, mass=mass,
    )


def test_geometry_digest_has_unchanged_golden_rows_and_single_config_no_solve(digest_trial):
    trial = digest_trial
    expected_rows = [
        ("Default", 1.234568, 1234.568, 2345.679, (1.2346, -2.3457, 3.4568),
         (0.1111, 0.2222, 0.3333, 0.4444, 0.5556, 0.6667)),
        ("Default", "a-part-1", (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
         (0.0123, -0.0568, 0.0901)),
        ("Default", "z-part-1", (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
         (0.0123, -0.0568, 0.0901)),
    ]
    assert trial.digest() == hashlib.sha256(repr(expected_rows).encode("utf-8")).hexdigest()
    assert trial.calls == [("mass", "Default"), ("poses", "Default", True)]


def test_geometry_digest_ignores_order_noise_and_tail_but_detects_pose_only_change(digest_trial):
    trial = digest_trial
    before = trial.digest()
    trial.components.reverse()
    pose = trial.components[0].Transform2.ArrayData
    pose[0] += 1e-9
    pose[9] += 1e-9
    pose[12:] = [7.0, 8.0, 9.0, 10.0]
    assert trial.digest() == before
    pose[9] += 0.001
    assert trial.digest() != before


@pytest.mark.parametrize(
    "configs", [["Default", "Travel"], ["Park", "Travel"], ["Travel", "Default"]]
)
def test_geometry_digest_explicitly_solves_switches_and_returns_to_rest(digest_trial, configs):
    trial = digest_trial
    trial.state.configs = configs
    trial.configuration.Name = configs[0]
    trial.digest()
    expected = [
        ("mass", configs[0]), ("poses", configs[0], True),
        ("activate", configs[1]), ("rebuild", configs[1], False),
        ("mass", configs[1]), ("poses", configs[1], True),
    ]
    rest = "Default" if "Default" in configs else configs[0]
    if configs[1] != rest:
        expected.extend([("activate", rest), ("rebuild", rest, False)])
    assert trial.calls == expected
    assert trial.configuration.Name == rest


@pytest.mark.parametrize(("rebuilt", "status"), [(False, 0), (None, 0), (True, 1)])
def test_geometry_digest_rejects_unsolved_switch_before_mass_read(digest_trial, rebuilt, status):
    trial = digest_trial
    trial.state.configs = ["Default", "Travel"]
    trial.state.rebuilt = rebuilt
    trial.state.status_after_rebuild = status
    with pytest.raises(RuntimeError):
        trial.digest()
    assert ("mass", "Travel") not in trial.calls


def test_geometry_digest_rejects_failed_configuration_activation(digest_trial):
    trial = digest_trial
    trial.state.configs = ["Default", "Travel"]

    async def fail_activation(_name):
        return SimpleNamespace(is_success=False, error="activation rejected")

    trial.adapter.set_active_configuration = fail_activation
    with pytest.raises(RuntimeError, match="activation rejected"):
        trial.digest()
    assert trial.calls == [("mass", "Default"), ("poses", "Default", True)]


@pytest.fixture
def assembly_profile_records():
    def span(name, identity, parent, start, end, **attributes):
        return {
            "name": name, "context": {"trace_id": "trace-exact", "span_id": identity},
            "parent_id": parent,
            "start_time": f"2026-09-07T00:00:00.{start:09d}Z",
            "end_time": f"2026-09-07T00:00:00.{end:09d}Z",
            "attributes": attributes, "status": {"status_code": "OK"},
        }

    return [
        span("geometry_digest.mass_properties", "mass", "geometry", 3, 6),
        span("assembly.geometry_digest", "geometry", "root", 2, 7),
        span("mate one", "mate", "root", 7, 9, kind="lock"),
        span("task assembly:drive_train", "root", None, 0, 10, seat_wait_s=1000),
    ]


def test_assembly_profile_exact_trace_exclusive_nanoseconds_and_retained_errors(
    tmp_path, assembly_profile_records
):
    from diagnostics.report_assembly_profile import report

    records = assembly_profile_records
    records[0]["status"]["status_code"] = "ERROR"
    selected = [json.dumps(row).encode() + b"\n" for row in records]
    other = {
        "context": {"trace_id": "different-trace"}, "message": "trace-exact",
    }
    path = tmp_path / "trace.jsonl"
    path.write_bytes(selected[0] + json.dumps(other).encode() + b"\n" + b"".join(selected[1:]))
    result = report(path, "trace-exact")
    assert result["span_count"] == 4
    assert result["error_span_count"] == 1
    assert result["selected_records_sha256"] == hashlib.sha256(b"".join(selected)).hexdigest()
    assert result["task"]["duration_ns"] == result["exclusive_total_ns"] == 10
    assert result["task"]["seat_wait_s"] == 1000
    assert {row["category"]: row["exclusive_ns"] for row in result["categories"]} == {
        "task": 3, "assembly.geometry_digest": 5, "scalar mates": 2,
    }
    assert {row["record"]["context"]["span_id"]: row["exclusive_ns"] for row in result["spans"]} == {
        "root": 3, "geometry": 2, "mass": 3, "mate": 2,
    }
    assert sorted(row["source_line"] for row in result["spans"]) == [1, 3, 4, 5]


@pytest.mark.parametrize(
    "fault", ["duplicate", "missing_parent", "multiple_roots", "negative", "outside", "overlap", "cycle", "absent"]
)
def test_assembly_profile_rejects_incomplete_or_double_counted_traces(
    tmp_path, assembly_profile_records, fault
):
    from diagnostics.report_assembly_profile import report

    records = assembly_profile_records
    mass, geometry, mate, root = records
    if fault == "duplicate":
        records.append(root)
    if fault == "missing_parent":
        geometry["parent_id"] = "not-recorded"
    if fault == "multiple_roots":
        geometry["parent_id"] = None
    if fault == "negative":
        mass["end_time"] = geometry["start_time"]
    if fault == "outside":
        mass["start_time"] = root["start_time"]
    if fault == "overlap":
        mate["start_time"] = mass["end_time"]
    if fault == "cycle":
        geometry["parent_id"] = "mass"
        mass.update(start_time=geometry["start_time"], end_time=geometry["end_time"])
    if fault == "absent":
        records = []
    path = tmp_path / "trace.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    with pytest.raises(ValueError):
        report(path, "trace-exact")


def test_assembly_profile_timestamp_offsets_and_interval_union_are_exact():
    from diagnostics.report_assembly_profile import timestamp_ns, union_ns

    assert timestamp_ns("2026-09-07T00:00:00.123456789Z") == timestamp_ns("2026-09-06T17:00:00.123456789-07:00")
    assert timestamp_ns("2026-09-07T00:00:00.000000001Z") - timestamp_ns("2026-09-07T00:00:00Z") == 1
    assert union_ns([(5, 9), (1, 7), (10, 12), (3, 3)]) == 10


@pytest.fixture
def native_fixture_owner(tmp_path, monkeypatch):
    from diagnostics import probe_assembly_part_change as probe
    from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

    monkeypatch.setattr(probe, "_early_bound", lambda value, _interface: value)
    path = tmp_path / "copy.SLDPRT"
    path.write_bytes(b"copied native input")
    documents, closed = [], []
    app = SimpleNamespace(ActiveDoc=None)
    app.GetDocuments = lambda: tuple(documents)
    app.GetDocumentDependencies2 = lambda *_args: ()
    app.IsSame = lambda left, right: int(left.native_id == right.native_id)
    model = SimpleNamespace(native_id=1, path=path, title="copy.SLDPRT")
    model.GetPathName = lambda: str(model.path)
    model.GetTitle = lambda: model.title
    model.GetType = lambda: 1

    def close(title):
        closed.append(title)
        documents[:] = [doc for doc in documents if doc.GetTitle() != title]
        if app.ActiveDoc is not None and app.ActiveDoc.GetTitle() == title:
            app.ActiveDoc = None

    def forbidden(*_args):
        pytest.fail("raw broad close/save must never run in fixture cleanup")

    model.Save3 = forbidden
    app.CloseDoc = close
    app.CloseAllDocuments = forbidden
    adapter = SimpleNamespace(swApp=app, currentModel=None, _attempt=_Adapter._attempt)
    state = SimpleNamespace(open_status=AdapterResultStatus.SUCCESS, open_calls=[])

    async def open_model(requested):
        state.open_calls.append(requested)
        documents.append(model)
        app.ActiveDoc = adapter.currentModel = model
        return AdapterResult(status=state.open_status, error="synthetic open rejection")

    adapter.open_model = open_model
    owner = probe.FixtureOwner(adapter, tmp_path)
    owner.register({path}, {path: set()})
    wrapped = probe.FixtureAdapter(owner, probe.Variant.BASELINE, [])
    return SimpleNamespace(
        probe=probe, path=path, owner=owner, wrapped=wrapped, model=model,
        adapter=adapter, app=app, documents=documents, closed=closed, state=state,
    )


def test_part_change_owner_closes_only_claimed_titles_without_save(native_fixture_owner):
    trial = native_fixture_owner
    asyncio.run(trial.wrapped.open_model(str(trial.path)))
    assert trial.wrapped.currentModel is trial.model
    assert trial.wrapped.swApp.CloseAllDocuments(True) is True
    assert trial.closed == ["copy.SLDPRT"]
    assert trial.documents == []
    assert trial.adapter.currentModel is None
    # A new native lifetime may reuse the path, but gets claimed afresh.
    trial.model.native_id = 2
    asyncio.run(trial.wrapped.open_model(str(trial.path)))
    assert trial.wrapped.currentModel.native_id == 2
    trial.owner.close()


def test_part_change_owner_rejects_foreign_document_before_any_close(native_fixture_owner, tmp_path):
    trial = native_fixture_owner
    asyncio.run(trial.wrapped.open_model(str(trial.path)))
    foreign = SimpleNamespace(
        GetPathName=lambda: str(tmp_path / "unregistered.SLDPRT"),
        GetTitle=lambda: "unregistered.SLDPRT", native_id=99,
    )
    trial.documents.append(foreign)
    with pytest.raises(trial.probe.OwnershipError):
        trial.wrapped._attempt(lambda: trial.wrapped.swApp.CloseAllDocuments(True))
    assert trial.closed == []
    assert len(trial.documents) == 2
    with pytest.raises(trial.probe.OwnershipError):
        _ = trial.wrapped.currentModel


def test_part_change_owner_latches_raw_cleanup_errors_through_attempt(native_fixture_owner):
    trial = native_fixture_owner
    asyncio.run(trial.wrapped.open_model(str(trial.path)))

    def failed_close(_title):
        raise RuntimeError("synthetic native close failure")

    trial.app.CloseDoc = failed_close
    with pytest.raises(trial.probe.OwnershipError, match="synthetic native close failure"):
        trial.wrapped._attempt(lambda: trial.wrapped.swApp.CloseAllDocuments(True))
    with pytest.raises(trial.probe.OwnershipError):
        asyncio.run(trial.wrapped.open_model(str(trial.path)))
    assert len(trial.state.open_calls) == 1


def test_part_change_owner_rejects_failed_open_but_can_close_claimed_copy(native_fixture_owner):
    from solidworks_mcp.adapters.base import AdapterResultStatus

    trial = native_fixture_owner
    trial.state.open_status = AdapterResultStatus.ERROR
    with pytest.raises(trial.probe.OwnershipError, match="fixture open failed"):
        asyncio.run(trial.wrapped.open_model(str(trial.path)))
    with pytest.raises(trial.probe.OwnershipError):
        _ = trial.wrapped.currentModel
    trial.owner.close()
    assert trial.closed == ["copy.SLDPRT"]


def test_part_change_owner_rejects_same_handle_path_change(native_fixture_owner, tmp_path):
    trial = native_fixture_owner
    asyncio.run(trial.wrapped.open_model(str(trial.path)))
    trial.model.path = tmp_path / "foreign-after-save-as.SLDPRT"
    with pytest.raises(trial.probe.OwnershipError):
        _ = trial.wrapped.currentModel
    assert trial.closed == []


def test_part_change_owner_rejects_unregistered_open_without_delegation(native_fixture_owner, tmp_path):
    trial = native_fixture_owner
    foreign = tmp_path / "foreign.SLDPRT"
    foreign.write_bytes(b"not registered")
    with pytest.raises(trial.probe.OwnershipError):
        asyncio.run(trial.wrapped.open_model(str(foreign)))
    assert trial.state.open_calls == []


def test_part_change_nominal_readback_accepts_observed_subnanometre_roundoff():
    from diagnostics.probe_assembly_part_change import require_nominal_mm

    require_nominal_mm(58.000000078, 58.0, "observed handle length")
    require_nominal_mm(6.125000078, 6.125, "nominal bore readback")


@pytest.mark.parametrize("actual", [58.000002, 57.999998, float("nan"), float("inf"), 0.0, -58.0])
def test_part_change_nominal_readback_remains_finite_positive_and_narrow(actual):
    from diagnostics.probe_assembly_part_change import require_nominal_mm

    with pytest.raises(RuntimeError):
        require_nominal_mm(actual, 58.0, "nominal readback")


@pytest.fixture
def saved_part_change_control(tmp_path, monkeypatch):
    from pathlib import Path
    from diagnostics import probe_assembly_part_change as probe

    root = tmp_path / "repo"
    prior_dir = root / "cad/out/reports/prior"
    control = prior_dir / "control/sldasm/drive-train.SLDASM"
    paths = {control, *(prior_dir / f"control/sldprt/part-{index}.SLDPRT" for index in range(38))}
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(path.name.encode())
    fingerprint = "f" * 64
    dof = {"specs": [{"name": str(index)} for index in range(4)]}
    mass_sidecar = control.parent / ".drive-train.massprops.sha"
    mass_sidecar.write_text(fingerprint, encoding="utf-8")
    (control.parent / ".drive-train.dof.json").write_text(json.dumps(dof), encoding="utf-8")
    originals = {str(root / "cad/out/sldasm/drive-train.SLDASM"): "original-hash"}
    source_hashes = {
        str(Path("cad/scripts/_assembly.py")): "core-hash",
        str(Path("cad/scripts/_assembly_mass_properties.py")): "reader-hash",
    }
    current = {
        "original_hashes_before": dict(originals), "adapter_commit": "adapter-commit",
        "source_sha256": dict(source_hashes), "source_fingerprint": fingerprint, "dof_manifest": dof,
    }
    gate_names = ["assert_manifest_dof_state", "check_no_interference", "assert_model_healthy"]
    solved = {
        "name": "control.resolve_gate_save", "status": "passed", "fingerprint": fingerprint,
        "gate_calls": gate_names, "save_result": [True, 0, 0],
        "mass_reads": [{"status": "passed", "variant": probe.Variant.BASELINE}],
    }
    cold = {
        **solved, "name": "control.cold_verify", "saved_rebuild_clean_before_resolve": True,
        "closed_native_sha256": probe.native_hashes(paths),
    }
    prior = {
        "root": str(root), "directory": str(prior_dir), "status": "failed",
        "error": "later nominal assertion failed", "root_commit": "prior-commit",
        "source_sha256": dict(source_hashes), "adapter_commit": "adapter-commit",
        "source_fingerprint": fingerprint, "dof_manifest": dof,
        "original_hashes_before": originals, "original_path_set_unchanged": True,
        "original_evidence": {name: {"unchanged": True, "before": value, "after": value} for name, value in originals.items()},
        "phases": [
            {"name": "control.copy", "status": "passed", "native_count": 39, "closed_closure_verified": True,
             "copies": [{"target": str(path)} for path in sorted(paths)]},
            solved, cold,
        ],
    }
    edges = {path: paths - {control} if path == control else set() for path in paths}
    native_calls = []

    def dependencies(path, traverse, search, readonly):
        native_calls.append((path, traverse, search, readonly))
        return tuple(item for child in sorted(edges[Path(path)]) for item in (child.name, str(child)))

    owner = SimpleNamespace(
        require_healthy=lambda: None, require_empty=lambda: None,
        app=SimpleNamespace(GetDocumentDependencies2=dependencies),
    )
    monkeypatch.setattr(probe, "ROOT", root)
    monkeypatch.setattr(probe.subprocess, "check_output", lambda *_args, **_kwargs: "")
    path = prior_dir / "measurements.json"

    def validate():
        path.write_text(json.dumps(prior), encoding="utf-8")
        return probe.validate_control_report(owner, path, current)

    return SimpleNamespace(
        validate=validate, probe=probe, root=root, control=control, paths=paths,
        prior=prior, current=current, report_path=path, mass_sidecar=mass_sidecar,
        edges=edges, native_calls=native_calls,
    )


def test_part_change_resume_reuses_only_passed_closed_control(saved_part_change_control):
    trial = saved_part_change_control
    root, paths, edges, cold = trial.validate()
    assert root == trial.control and paths == trial.paths and edges == trial.edges
    assert cold["status"] == "passed"
    provenance = trial.current["resumed_control"]
    assert provenance["parent_trial_status"] == "failed"
    assert provenance["parent_trial_error"] == "later nominal assertion failed"
    assert provenance["status"] == "validated"
    assert provenance["report_sha256"] == trial.probe.digest(trial.report_path)
    assert len(provenance["passed_control_phases"]) == 3
    assert len(trial.native_calls) == 40  # Closed reference reads only; no open/close/write API.


@pytest.mark.parametrize(
    "fault", ["native_bytes", "sidecar", "source", "adapter", "original", "cleanup", "cold_failed", "cold_dirty", "no_mass", "external_reference"]
)
def test_part_change_resume_rejects_changed_or_incomplete_proof(saved_part_change_control, fault):
    trial = saved_part_change_control
    if fault == "native_bytes":
        trial.control.write_bytes(b"changed native bytes")
    if fault == "sidecar":
        trial.mass_sidecar.write_text("changed", encoding="utf-8")
    if fault == "source":
        trial.current["source_sha256"][next(iter(trial.current["source_sha256"]))] = "changed"
    if fault == "adapter":
        trial.current["adapter_commit"] = "changed"
    if fault == "original":
        trial.current["original_hashes_before"][next(iter(trial.current["original_hashes_before"]))] = "changed"
    if fault == "cleanup":
        trial.prior["cleanup_error"] = "close failed"
    if fault == "cold_failed":
        trial.prior["phases"][2]["status"] = "failed"
    if fault == "cold_dirty":
        trial.prior["phases"][2]["saved_rebuild_clean_before_resolve"] = False
    if fault == "no_mass":
        trial.prior["phases"][2]["mass_reads"] = []
    if fault == "external_reference":
        external = trial.root / "outside-control.SLDPRT"
        external.write_bytes(b"external")
        trial.edges[trial.control].add(external)
    with pytest.raises(RuntimeError):
        trial.validate()
