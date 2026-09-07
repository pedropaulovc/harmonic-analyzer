"""Only isolated recipe setup changes; native recipe acceptance remains strict."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import _recipe_template_factory as factory


def model_fixture(tmp_path, monkeypatch):
    original = tmp_path / "original.DRWDOT"
    original.write_bytes(b"protected template")
    monkeypatch.setattr(factory.common, "PROJECT_DRWDOT", original)
    normal = Mock(return_value=("draw", "sheet"))
    monkeypatch.setattr(factory.common, "new_project_drawing", normal)
    monkeypatch.setattr(
        factory.pilot, "helper_fingerprints", lambda: {"helper": "same"}
    )
    monkeypatch.setattr(
        factory.pilot, "adapter_fingerprints", lambda: {"adapter": "same"}
    )
    module = SimpleNamespace(TEMPLATE_SPEC=factory.prepared.TemplateSpec((1, 2), 2))
    events = []

    @contextmanager
    def operation(kind, path):
        events.append((kind, Path(path)))
        yield

    adapter = SimpleNamespace(
        ownership=SimpleNamespace(
            register_source=Mock(),
            register_directory=Mock(),
            creating_document=lambda kind, path: operation("create", path),
            saving_as=lambda path: operation("save_as", path),
            relocate_prepared_template_directory=Mock(),
        )
    )
    return adapter, module, normal, events


@pytest.mark.asyncio
async def test_normal_factory_records_only_original_setup(tmp_path, monkeypatch):
    adapter, module, normal, events = model_fixture(tmp_path, monkeypatch)
    materialize = Mock(side_effect=AssertionError("normal must not prepare"))
    monkeypatch.setattr(
        factory.prepared, "prepare_project_drawing_template", materialize
    )
    controller = factory.RecipeTemplateFactory(factory.DrawingFactory.NORMAL)
    trial = {}
    selected = await controller.configure(adapter, module, trial, tmp_path)
    assert events == []
    assert not hasattr(module, "new_project_drawing")
    assert factory.common.new_project_drawing is normal
    assert selected(adapter, property_view="Front", scale=(1, 2)) == (
        "draw",
        "sheet",
    )
    normal.assert_called_once_with(
        adapter, property_view="Front", scale=(1, 2), decimals=2
    )
    controller.require_used()
    assert trial["template_factory"]["setup_calls"] == 1
    assert trial["template_factory"]["setup_seconds"] >= 0
    assert controller.final_guards() == []


@pytest.mark.asyncio
async def test_prepared_materialization_precedes_recipe_and_uses_exact_scopes(
    tmp_path, monkeypatch
):
    adapter, module, normal, events = model_fixture(tmp_path, monkeypatch)
    entry_dir = tmp_path / "cache" / "key"
    entry = factory.prepared.PreparedTemplate(
        entry_dir, "key", factory.prepared.TemplateSpec((1, 2), 2)
    )
    calls = []

    async def materialize(
        actual_adapter, *, scale, decimals, cache_root, operation_context
    ):
        assert actual_adapter is adapter and scale == (1, 2) and decimals == 2
        assert normal.call_count == 0  # No actual recipe factory yet.
        calls.append(1)
        if len(calls) == 1:
            stage = cache_root / "pending-key"
            stage.mkdir(parents=True)
            for kind, name in (
                (factory.prepared.TemplateOperation.CREATE, "prepared.DRWDOT"),
                (factory.prepared.TemplateOperation.SAVE_AS, "prepared.DRWDOT"),
                (factory.prepared.TemplateOperation.CREATE, "verification.SLDDRW"),
            ):
                with operation_context(kind, stage / name):
                    pass
            stage.rename(entry_dir)
            for name in (
                "prepared.DRWDOT",
                "manifest.json",
                "receipt.json",
                "ownership.json",
            ):
                (entry_dir / name).write_bytes(b"frozen")
        return entry

    monkeypatch.setattr(
        factory.prepared, "prepare_project_drawing_template", materialize
    )
    inherited = Mock(return_value=("inherited", "sheet"))
    monkeypatch.setattr(factory.prepared, "inherited_drawing", inherited)
    controller = factory.RecipeTemplateFactory(factory.DrawingFactory.PREPARED)
    trial = {}
    selected = await controller.configure(adapter, module, trial, tmp_path)
    assert [kind for kind, _ in events] == ["create", "save_as", "create"]
    assert len(calls) == 2
    adapter.ownership.relocate_prepared_template_directory.assert_called_once()
    assert selected(adapter, property_view="Front", scale=(1, 2)) == (
        "inherited",
        "sheet",
    )
    inherited.assert_called_once_with(adapter, entry)
    normal.assert_not_called()
    controller.require_used()
    assert [row["kind"] for row in trial["template_factory"]["accessors"]] == [
        "miss",
        "hit",
    ]
    assert controller.final_guards() == []
    entry.path.write_bytes(b"changed")
    assert "changed" in str(controller.final_guards())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"scale": (1, 1)},
        {"scale": (1, 2), "decimals": 3},
        {"scale": (1, 2), "unknown": 1},
    ],
)
async def test_setup_signature_drift_fails_without_native_factory(
    tmp_path, monkeypatch, kwargs
):
    adapter, module, normal, _ = model_fixture(tmp_path, monkeypatch)
    controller = factory.RecipeTemplateFactory(factory.DrawingFactory.NORMAL)
    selected = await controller.configure(adapter, module, {}, tmp_path)
    with pytest.raises(ValueError, match="setup"):
        selected(adapter, **kwargs)
    normal.assert_not_called()


@pytest.mark.asyncio
async def test_wrong_adapter_missing_or_repeated_setup_rejected(tmp_path, monkeypatch):
    adapter, module, normal, _ = model_fixture(tmp_path, monkeypatch)
    controller = factory.RecipeTemplateFactory(factory.DrawingFactory.NORMAL)
    selected = await controller.configure(adapter, module, {}, tmp_path)
    with pytest.raises(RuntimeError, match="exactly one"):
        controller.require_used()
    with pytest.raises(RuntimeError, match="adapter"):
        selected(object(), scale=(1, 2))
    selected(adapter, scale=(1, 2))
    with pytest.raises(RuntimeError, match="once"):
        selected(adapter, scale=(1, 2))
    assert normal.call_count == 1


@pytest.mark.asyncio
async def test_primary_setup_error_and_final_input_drift_are_both_visible(
    tmp_path, monkeypatch
):
    adapter, module, normal, _ = model_fixture(tmp_path, monkeypatch)
    controller = factory.RecipeTemplateFactory(factory.DrawingFactory.NORMAL)
    trial = {}
    selected = await controller.configure(adapter, module, trial, tmp_path)
    normal.side_effect = RuntimeError("native setup rejected")
    with pytest.raises(RuntimeError, match="native setup rejected"):
        selected(adapter, scale=(1, 2))
    assert trial["template_factory"]["setup_seconds"] >= 0
    monkeypatch.setattr(
        factory.pilot, "adapter_fingerprints", lambda: {"adapter": "changed"}
    )
    factory.common.PROJECT_DRWDOT.write_bytes(b"changed")
    errors = controller.final_guards()
    assert len(errors) == 2


@pytest.mark.parametrize("variant", tuple(factory.DrawingFactory))
@pytest.mark.parametrize("route", ("parent", "worker"))
def test_explicit_cli_factory_is_forwarded_without_dropping_target_or_guards(
    tmp_path, monkeypatch, variant, route
):
    import asyncio
    import sys

    probe = factory.pilot
    monkeypatch.setattr(factory, "require_factory_environment", lambda: None)
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "frozen")
    native_parent = Mock()
    monkeypatch.setitem(sys.modules, "dodo", SimpleNamespace(_run=native_parent))
    received = []

    async def pilot(*args, targets, setup_controller):
        received.append((targets, setup_controller.variant))
        return 0

    monkeypatch.setattr(probe, "pilot", pilot)
    monkeypatch.setattr(
        probe, "run_copy_diagnostic", lambda callback: asyncio.run(callback(object()))
    )
    arguments = [
        "--source-root",
        str(tmp_path),
        "--guard-root",
        str(tmp_path),
        "--factory",
        variant.value,
        "--target",
        "rocker_arm",
    ]
    if route == "worker":
        arguments.append("--worker")
    assert probe.main(arguments) == 0
    if route == "worker":
        assert received == [(("rocker_arm",), variant)]
        native_parent.assert_not_called()
        return
    (call,) = native_parent.call_args_list
    command = call.args[0]
    assert command[command.index("--factory") + 1] == variant.value
    assert command[command.index("--target") + 1] == "rocker_arm"
    assert command[command.index("--candidate") + 1] == "frozen"
    assert call.kwargs["com"] is True


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"HARMONIC_DIAGNOSTIC_SW_PID": "0"},
        {"HARMONIC_DIAGNOSTIC_SW_PID": "31860", "HARMONIC_REMOTE_CACHE_MODE": "rw"},
    ],
)
def test_factory_parent_refuses_missing_pid_or_remote_writes_before_native_wrapper(
    tmp_path, monkeypatch, environment
):
    import sys

    for name in ("HARMONIC_DIAGNOSTIC_SW_PID", "HARMONIC_REMOTE_CACHE_MODE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    native = Mock(
        side_effect=AssertionError("environment must fail before native parent")
    )
    monkeypatch.setitem(sys.modules, "dodo", SimpleNamespace(_run=native))
    with pytest.raises(RuntimeError):
        factory.pilot.main(
            [
                "--source-root",
                str(tmp_path),
                "--guard-root",
                str(tmp_path),
                "--factory",
                "normal",
            ]
        )
    native.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", tuple(factory.DrawingFactory))
@pytest.mark.parametrize(
    "mode", ("passed", "cold_title", "copy_saved", "guard_and_recipe_error")
)
async def test_full_pilot_keeps_source_and_cold_checks_for_each_selected_factory(
    tmp_path, monkeypatch, variant, mode
):
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources
    from test_benchmark_drawing_recipes import recipe

    probe = factory.pilot
    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(probe, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(probe, "adapter_fingerprints", lambda: {"adapter": "same"})
    monkeypatch.setattr(
        probe.benchmark, "recipe_source", lambda *_: recipe(Path("unused.SLDPRT"))
    )
    source_handle = object()
    monkeypatch.setattr(
        probe,
        "source_dimensions",
        lambda *_: (
            {"configuration": "Default", "value_tolerance_basic": "exact"},
            {"D": source_handle},
        ),
    )
    witness = Mock(return_value={"geometry": "exact", "values": "exact"})
    monkeypatch.setattr(probe, "drawing_witness", witness)
    comparison = Mock(
        return_value={
            "status": "failed" if mode == "cold_title" else "passed",
            "rejected": ["title moved 7 mm"],
        }
    )
    monkeypatch.setattr(probe, "compare_drawing_reopen", comparison)
    adapter = Adapter(
        "source_drift"
        if mode == "copy_saved"
        else "build_failure"
        if mode == "guard_and_recipe_error"
        else "normal"
    )
    events = []

    class Setup:
        def __init__(self):
            self.variant = variant
            self.guards = {"read": "recorded"}

        async def configure(self, actual, module, row, directory):
            assert actual is adapter and not adapter.opened
            assert not adapter.drawn
            events.append("configure_before_open")
            row["template_factory"] = {"variant": variant.value, "setup_seconds": 0.01}
            return Mock(name="explicit_factory")

        def require_used(self):
            events.append("recipe_complete")

        def final_guards(self):
            events.append("final_guards")
            return (
                [RuntimeError("helper changed")]
                if mode == "guard_and_recipe_error"
                else []
            )

    arguments = (adapter, "frozen", source_root, guard_root, tmp_path / "reports")
    if mode == "passed":
        await probe.pilot(*arguments, targets=("rocker_arm",), setup_controller=Setup())
    else:
        with pytest.raises((RuntimeError, ExceptionGroup)) as error:
            await probe.pilot(
                *arguments, targets=("rocker_arm",), setup_controller=Setup()
            )
        if mode == "guard_and_recipe_error":
            assert [str(item) for item in error.value.exceptions] == [
                "real recipe gate failed",
                "helper changed",
            ]
    (report_path,) = (tmp_path / "reports").glob("*/pilot.json")
    import json

    report = json.loads(report_path.read_text())
    assert report["factory"] == variant.value
    assert report["order"] == ["rocker_arm"]
    assert report["status"] == ("passed" if mode == "passed" else "failed")
    assert report["sources_before"] == report["sources_after"]
    assert report["elapsed_seconds"] >= report["trials"][0]["recipe_seconds"]
    assert events[0] == "configure_before_open" and events[-1] == "final_guards"
    assert len(adapter.drawn) == 1
    if mode in ("passed", "cold_title"):
        assert witness.call_count == 2
        comparison.assert_called_once()
    if mode == "cold_title":
        assert "title moved 7 mm" in report["error"]
        assert report["trials"][0]["reopen_annotation_comparison"]["status"] == "failed"
