"""Explicit fastener inputs use the existing owned-copy and cold pilot gates."""

import asyncio
from importlib import import_module
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _recipe_acceptance_targets as manifests
from diagnostics import _recipe_template_factory as factory
from diagnostics import _source_callout_authoring as authoring
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics import probe_source_basic_dimensions as parameters


FASTENERS = {
    "cone_tip_adjuster": (
        "f3578ac2b2ab95e478bc7bd72c316ebab057c125d5244af6fa2c3e12f4d48468",
        {
            "BodyProfile": {"BodyDiaDim"},
            "Body": {"BodyLenDim"},
            "CupProfile": {"CupDiaDim"},
            "Cup": {"CupDepth"},
            "SlotProfile": {"SlotWDim"},
        },
    ),
    "cone_pivot_screw": (
        "515019088b41d329b45f0487b9241123751ecac7d6c116481930ae9c45e89c36",
        {
            "HeadProfile": {"HeadDiaDim"},
            "ShoulderProfile": {"ShoulderDiaDim"},
            "Head": {"HeadHt"},
            "Shoulder": {"ShoulderLg"},
            "ThreadTail": {"ThreadLg"},
            "SlotProfile": {"SlotWDim"},
            "DriverSlot": {"SlotDepth"},
        },
    ),
}
OBSERVED_UNAPPROVED_TIP = (
    "55cc336009f1a837e5c9fb5afbea4cc06d6658c17dcb0aaef86294762f555194"
)
HISTORICAL_TIP = (
    "8e2ce51d8e7ca47f9ca5a8e5c743d1d6a0f0cd749e10195a54e2140117bf12f4"
)


@pytest.mark.parametrize("target", FASTENERS)
def test_fasteners_are_explicit_pinned_targets_with_exact_spec_manifests(target):
    assert pilot.target_order((target,)) == (target,)
    assert pilot.target_order() == ("rocker_arm", "channel_lever")
    spec = import_module(f"{target}_spec")
    manifest = manifests.TARGETS[target]
    digest, dimensions = FASTENERS[target]
    assert manifest.source_sha256 == pilot.EXPECTED_PART_HASHES[target] == digest
    assert manifest.spec_module == f"{target}_spec"
    assert manifest.dimensions is spec.DRAWING_DIMENSIONS
    assert manifest.dimensions == dimensions
    assert manifest.basic == {}  # Neither builder declares source BASIC fields.
    assert manifest.entity_labels == manifest.view_roles == {}


@pytest.mark.parametrize("target", FASTENERS)
@pytest.mark.parametrize(
    "digest", [None, "0" * 64, OBSERVED_UNAPPROVED_TIP, HISTORICAL_TIP]
)
def test_fastener_input_never_accepts_a_different_source_or_repins(
    monkeypatch, tmp_path, target, digest
):
    expected = FASTENERS[target][0]
    path = tmp_path / f"{target}.SLDPRT"
    observed = expected if digest is None else digest
    monkeypatch.setattr(pilot.attachments, "file_digest", lambda _: observed)
    sources = {target: path}
    if observed == expected:
        assert pilot.require_sources(sources, sources) == {str(path): expected}
    else:
        with pytest.raises(RuntimeError, match="exact immutable source hash mismatch"):
            pilot.require_sources(sources, sources)
    assert pilot.EXPECTED_PART_HASHES[target] == expected


@pytest.mark.parametrize("target", FASTENERS)
def test_fastener_parameter_witness_uses_exact_owner_and_all_named_dimensions(
    monkeypatch, tmp_path, target
):
    path = tmp_path / f"{target}-owned.SLDPRT"
    model = NS(
        GetType=lambda: 1,
        GetPathName=lambda: str(path),
        ConfigurationManager=NS(ActiveConfiguration=NS(Name="Default")),
    )
    monkeypatch.setattr(pilot, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(parameters, "_early_bound", lambda value, _: value)
    dimensions, calls = {}, []
    for feature, names in FASTENERS[target][1].items():
        for name in names:
            dimensions[feature, name] = NS(
                FullName=f"{name}@{feature}@{path.stem}.Part",
                GetSystemValue3=lambda mode, configuration: [0.0123456789],
                Tolerance=NS(Type=2),
                GetToleranceType=lambda: 2,
            )

    def named(adapter, feature, name):
        assert adapter.currentModel is model
        calls.append((feature, name))
        return object(), dimensions[feature, name]

    monkeypatch.setattr(parameters, "_named_dimension", named)
    result, handles = pilot.source_dimensions(model, target, path)
    assert set(calls) == set(dimensions)
    assert len(calls) == len(dimensions)
    assert handles == {
        f"{name}@{feature}": row for (feature, name), row in dimensions.items()
    }
    assert set(result["dimensions"]) == set(handles)
    assert all(row["tolerance_type"] == 2 for row in result["dimensions"].values())
    assert all(
        row["value_system"] == 0.0123456789 for row in result["dimensions"].values()
    )
    model.GetPathName = lambda: str(tmp_path / "wrong-source.SLDPRT")
    with pytest.raises(RuntimeError, match="wrong exact native owner"):
        pilot.source_dimensions(model, target, path)
    assert len(calls) == len(dimensions)


def load_current_recipe(monkeypatch, tmp_path, target):
    # No historical Git-object dependency in the test: evaluate current tracked
    # recipe declarations through the real reviewed output/source redirector.
    code = Path(__file__).with_name(f"draw_{target}.py").read_text(encoding="utf-8")
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: code)
    source = tmp_path / f"{target}-owned.SLDPRT"
    source.write_bytes(b"owned fixture, never native")
    directory = tmp_path / "trial"
    directory.mkdir()
    return pilot.benchmark.load_recipe("working-tree", target, directory, source=source)


@pytest.mark.parametrize("target", FASTENERS)
def test_actual_fastener_recipes_redirect_sources_aliases_and_prepared_spec(
    monkeypatch, tmp_path, target
):
    module = load_current_recipe(monkeypatch, tmp_path, target)
    assert module.SOURCE == tmp_path / f"{target}-owned.SLDPRT"
    assert module.OUTPUTS.slddrw == module.SLDDRW
    assert module.OUTPUTS.pdf == module.PDF
    assert module.OUTPUTS.png == module.PNG
    assert (
        module.SLDDRW.parent
        == module.PDF.parent
        == module.PNG.parent
        == tmp_path / "trial"
    )
    assert module.TEMPLATE_SPEC.scale == (4.0, 1.0)
    assert module.TEMPLATE_SPEC.decimals == 2


@pytest.mark.asyncio
async def test_actual_screw_entry_forwards_owned_inputs_to_shared_fastener(
    monkeypatch, tmp_path
):
    module = load_current_recipe(monkeypatch, tmp_path, "cone_pivot_screw")
    adapter, prepared_factory = object(), object()
    calls = []

    async def shared(actual_adapter, **kwargs):
        assert actual_adapter is adapter
        calls.append(kwargs)
        return {"sentinel": "shared fastener result"}

    monkeypatch.setattr(module, "build_fastener_sheet", shared)
    assert await module.build(adapter, drawing_factory=prepared_factory) == {
        "sentinel": "shared fastener result"
    }
    assert calls == [
        {
            "drawing_factory": prepared_factory,
            "source": module.SOURCE,
            "property_view": module.PART_STEM,
            "outputs": module.OUTPUTS,
            "recipe": module.RECIPE,
        }
    ]
    assert (
        module.RECIPE.side_dimension_callouts
        is import_module("cone_pivot_screw_spec").SIDE_DIMENSION_CALLOUTS
    )
    assert module.RECIPE.side_callout_feature == "ThreadTail"


@pytest.mark.parametrize("target", FASTENERS)
@pytest.mark.parametrize("route", ["parent", "worker"])
def test_fastener_cli_uses_prepared_factory_without_source_authoring_controls(
    monkeypatch, tmp_path, target, route
):
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "12345")
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    forbidden = Mock(side_effect=AssertionError("source authoring was not selected"))
    monkeypatch.setattr(authoring, "SourceCalloutControl", forbidden)
    parent, observed = Mock(), []
    monkeypatch.setitem(sys.modules, "dodo", NS(_run=parent))

    async def run(*args, **kwargs):
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(pilot, "pilot", run)
    monkeypatch.setattr(
        pilot, "run_copy_diagnostic", lambda callback: asyncio.run(callback(object()))
    )
    argv = [
        "--source-root",
        str(tmp_path),
        "--guard-root",
        str(tmp_path),
        "--target",
        target,
        "--factory",
        "prepared",
    ]
    assert pilot.main([*argv, *(["--worker"] if route == "worker" else [])]) == 0
    forbidden.assert_not_called()
    if route == "worker":
        assert len(observed) == 1
        controller = observed[0].pop("setup_controller")
        assert controller.variant is factory.DrawingFactory.PREPARED
        assert observed == [{"targets": (target,)}]
        parent.assert_not_called()
        return
    command = parent.call_args.args[0]
    assert command[command.index("--target") + 1] == target
    assert command[command.index("--factory") + 1] == "prepared"
    assert not {
        "--source-callout-authoring",
        "--callout-storage",
        "--drawing-save",
        "--source-observation",
    }.intersection(command)
    assert parent.call_args.kwargs["com"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("target", FASTENERS)
@pytest.mark.parametrize("mode", ["normal", "source_drift", "reopen_drift"])
async def test_selected_fastener_runs_existing_copy_and_cold_gates(
    monkeypatch, tmp_path, target, mode
):
    from test_benchmark_drawing_recipes import recipe
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources

    sources, _ = fixture_sources(tmp_path, monkeypatch)
    source = sources / f"{target.replace('_', '-')}.SLDPRT"
    source.write_bytes(target.encode())
    monkeypatch.setitem(
        pilot.EXPECTED_PART_HASHES, target, pilot.attachments.file_digest(source)
    )
    monkeypatch.setattr(
        pilot.benchmark, "recipe_source", lambda *_: recipe(Path("unopened.SLDPRT"))
    )
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"adapter": "same"})
    handle = object()
    monkeypatch.setattr(
        pilot,
        "source_dimensions",
        lambda *_: ({"configuration": "Default"}, {"dimension": handle}),
    )
    seen = []

    def witness(adapter, *, source, configuration):
        assert source.name.startswith(target.replace("_", "-") + "-source-")
        assert source.is_relative_to(tmp_path / "reports")
        assert configuration == "Default"
        seen.append(adapter.currentModel)
        return {
            "same": "source/attachments/text",
            "index": len(seen) if mode == "reopen_drift" else 0,
        }

    def compare(before, after):
        if before != after:
            raise RuntimeError("cold drawing text/geometry changed")
        return {"status": "passed", "rejected": []}

    monkeypatch.setattr(pilot, "drawing_witness", witness)
    monkeypatch.setattr(pilot, "compare_drawing_reopen", compare)
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())
    forbidden = Mock(side_effect=AssertionError("source authoring was not selected"))
    monkeypatch.setattr(authoring, "SourceCalloutControl", forbidden)
    adapter = Adapter(mode)
    root = tmp_path / "reports"
    if mode == "normal":
        await pilot.pilot(adapter, "frozen", sources, sources, root, targets=(target,))
    else:
        with pytest.raises(RuntimeError, match="source copy changed|cold drawing text"):
            await pilot.pilot(
                adapter, "frozen", sources, sources, root, targets=(target,)
            )
    (path,) = root.glob("*/pilot.json")
    report = json.loads(path.read_text())
    assert report["order"] == [target]
    assert report["protected_targets"] == [*pilot.ORDER, target]
    assert report["sources_before"] == report["sources_after"]
    assert len(report["sources_before"]) == 3
    assert source not in map(Path, adapter.opened)
    assert len(adapter.drawn) == 1
    forbidden.assert_not_called()
    trial = report["trials"][0]
    if mode == "normal":
        assert report["status"] == "passed"
        assert len(seen) == 2
        assert trial["copy_final"] == pilot.EXPECTED_PART_HASHES[target]
        assert set(trial["copy_hashes"]) == {
            "copied",
            "after_recipe",
            "after_close",
            "after_reopened_close",
        }
    if mode == "source_drift":
        assert report["status"] == "failed"
        assert report["runtime_final_guard_errors"]
        assert not seen
    if mode == "reopen_drift":
        assert report["status"] == "failed"
        assert len(seen) == 2
        assert "cold drawing text/geometry changed" in report["error"]
