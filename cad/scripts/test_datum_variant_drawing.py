"""An explicit diagnostic binding changes one option before recipe execution."""

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from _drawing_native_callouts import DatumInitialMeasurement, DatumLeaderPolicy
from diagnostics import benchmark_drawing_recipes as benchmark
from diagnostics import probe_datum_policy_recipes as probe
from test_benchmark_drawing_recipes import recipe


def layout_recipe(source):
    return (
        recipe(source)
        + "\nfrom _drawing_project_layout import DatumLeaderPolicy, repair_project_drawing_layout\n"
        + "CAPTURED_LAYOUT = repair_project_drawing_layout\n"
        + "def layout_default(layout=repair_project_drawing_layout):\n    return layout\n"
    )


def test_layout_binding_precedes_globals_and_defaults_without_shared_monkeypatch(
    tmp_path, monkeypatch
):
    import _drawing_project_layout as shared

    original = shared.repair_project_drawing_layout
    code = layout_recipe(tmp_path / "part.SLDPRT")
    monkeypatch.setattr(benchmark, "recipe_source", lambda *_: code)
    selected = Mock(__module__="diagnostic", __qualname__="observed_layout")
    module = benchmark.load_recipe("frozen", "rocker_arm", tmp_path, layout=selected)
    assert module.repair_project_drawing_layout is selected
    assert module.CAPTURED_LAYOUT is module.layout_default() is selected
    assert module.DatumLeaderPolicy is DatumLeaderPolicy
    assert shared.repair_project_drawing_layout is original
    assert module.execution_receipt["layout_binding"] == "repair_project_drawing_layout"
    assert len(module.execution_receipt["compiled_ast_sha256"]) == 64
    assert module.execution_receipt["original_sha256"] == probe.attachments.file_digest(
        tmp_path / "recipe-source.py"
    )


@pytest.mark.parametrize(
    "shape", ["missing", "aliased", "duplicate", "nested", "rebound"]
)
def test_unsupported_layout_import_shape_fails_before_recipe_exec(
    tmp_path, monkeypatch, shape
):
    code = recipe(tmp_path / "part.SLDPRT")
    binding = "from _drawing_project_layout import repair_project_drawing_layout"
    if shape == "aliased":
        code += "\n" + binding + " as layout"
    if shape == "duplicate":
        code += "\n" + binding + "\n" + binding
    if shape == "nested":
        code += "\ndef nested():\n    " + binding
    if shape == "rebound":
        code += "\n" + binding + "\nrepair_project_drawing_layout = None"
    # Any execution, including pre-build module side effects, is forbidden.
    code = "raise AssertionError('recipe executed')\n" + code
    monkeypatch.setattr(benchmark, "recipe_source", lambda *_: code)
    with pytest.raises(ValueError, match="layout"):
        benchmark.load_recipe("frozen", "rocker_arm", tmp_path, layout=lambda: None)


@pytest.mark.parametrize("variant", list(DatumInitialMeasurement))
def test_measurement_wrapper_forwards_exact_arguments_and_counts_one_call(
    monkeypatch, variant
):
    sentinel, adapter, views, notes = (
        object(),
        object(),
        {"front": object()},
        (object(),),
    )
    production = Mock(return_value=sentinel)
    monkeypatch.setattr(probe, "repair_project_drawing_layout", production)
    times = iter((10.0, 13.5))
    monkeypatch.setattr(probe.time, "perf_counter", lambda: next(times))
    trial = {"target": "rocker_arm"}
    selected = probe.measured_layout(variant, trial)
    kwargs = {
        "views": views,
        "notes": notes,
        "datum_leader_policy": DatumLeaderPolicy.BENT_DOCUMENT,
    }
    assert selected(adapter, **kwargs) is sentinel
    production.assert_called_once_with(
        adapter, **kwargs, datum_initial_measurement=variant
    )
    assert len(trial["layout_calls"]) == 1
    assert trial["layout_calls"][0]["seconds"] == 3.5
    assert trial["layout_calls"][0]["status"] == "passed"
    probe.require_layout_invocation(trial)
    with pytest.raises(RuntimeError, match="exactly once"):
        selected(adapter, **kwargs)
    assert production.call_count == 1
    with pytest.raises(RuntimeError, match="exactly once"):
        probe.require_layout_invocation(trial)


def test_layout_exception_keeps_elapsed_receipt_without_claiming_cold_success(
    monkeypatch,
):
    production = Mock(side_effect=RuntimeError("native final clearance failed"))
    monkeypatch.setattr(probe, "repair_project_drawing_layout", production)
    trial = {"target": "rocker_arm"}
    selected = probe.measured_layout(DatumInitialMeasurement.REUSE_POST_POLICY, trial)
    with pytest.raises(RuntimeError, match="native final clearance"):
        selected(object(), views={})
    row = trial["layout_calls"][0]
    assert row["status"] == "failed" and row["seconds"] >= 0
    assert row["trace_id"] and row["span_id"]
    assert "native final clearance" in row["error"]
    assert "cold" not in row and "passed" not in trial


def test_recipe_cannot_silently_bypass_or_override_selected_policy(monkeypatch):
    trial = {"target": "rocker_arm"}
    with pytest.raises(RuntimeError, match="exactly once"):
        probe.require_layout_invocation(trial)
    production = Mock()
    monkeypatch.setattr(probe, "repair_project_drawing_layout", production)
    selected = probe.measured_layout(DatumInitialMeasurement.REUSE_POST_POLICY, trial)
    with pytest.raises(ValueError, match="already supplies"):
        selected(object(), datum_initial_measurement=DatumInitialMeasurement.FRESH)
    production.assert_not_called()


@pytest.mark.parametrize("target", probe.ORDER)
def test_real_pilot_recipe_captures_selected_binding_and_keeps_input_defaults(
    tmp_path, monkeypatch, target
):
    source = tmp_path / "owned.SLDPRT"
    source.write_bytes(b"offline input")
    selected = Mock(__module__="diagnostic", __qualname__="observed_layout")
    monkeypatch.setattr(
        benchmark,
        "recipe_source",
        lambda _, name: (benchmark.ROOT / "cad/scripts" / f"draw_{name}.py").read_text(
            encoding="utf-8"
        ),
    )
    module = benchmark.load_recipe(
        "current-tracked-recipe", target, tmp_path, source=source, layout=selected
    )
    assert module.SOURCE == source
    assert module.repair_project_drawing_layout is selected
    assert module.OUTPUTS.slddrw.parent == tmp_path
    if target == "channel_lever":
        assert inspect.signature(module.build).parameters["layout"].default is selected
        assert inspect.signature(module.build).parameters["source"].default == source
        assert (
            inspect.signature(module.build).parameters["outputs"].default
            is module.OUTPUTS
        )


@pytest.mark.parametrize("variant", list(DatumInitialMeasurement))
@pytest.mark.parametrize("route", ["parent", "worker"])
def test_variant_cli_is_explicit_and_survives_parent_worker_boundary(
    monkeypatch, tmp_path, variant, route
):
    import sys

    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", lambda: None)
    monkeypatch.setattr(probe.benchmark, "revision", lambda _: "frozen")
    parent = Mock()
    monkeypatch.setitem(sys.modules, "dodo", SimpleNamespace(_run=parent))
    seen = []

    async def pilot(*args, targets=None, datum_initial_measurement=None):
        seen.append(datum_initial_measurement)
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
        "--datum-initial-measurement",
        variant.value,
    ]
    if route == "worker":
        arguments.append("--worker")
    assert probe.main(arguments) == 0
    if route == "worker":
        assert seen == [variant]
        parent.assert_not_called()
        return
    command = parent.call_args.args[0]
    assert command[command.index("--datum-initial-measurement") + 1] == variant.value
    assert parent.call_args.kwargs["com"] is True


def test_unknown_variant_fails_before_native_parent_guard(monkeypatch, tmp_path):
    guard = Mock()
    monkeypatch.setattr(probe, "require_owned_diagnostic_environment", guard)
    with pytest.raises(SystemExit):
        probe.main(
            [
                "--source-root",
                str(tmp_path),
                "--guard-root",
                str(tmp_path),
                "--datum-initial-measurement",
                "guessed_fallback",
            ]
        )
    guard.assert_not_called()
