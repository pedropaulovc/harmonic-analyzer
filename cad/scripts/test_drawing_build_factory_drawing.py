"""Prepared setup is explicit, drawing-only and precedes source opening."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from _drawing_registry import DRAWINGS


@pytest.mark.parametrize("drawing", DRAWINGS, ids=lambda item: item.name)
def test_every_recipe_declares_and_consumes_its_exact_explicit_spec(drawing):
    import ast
    import importlib
    import inspect

    from _drawing_build import TemplateSpec

    module = importlib.import_module(drawing.script.stem)
    parameter = inspect.signature(module.build).parameters["drawing_factory"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
    assert isinstance(module.TEMPLATE_SPEC, TemplateSpec)
    assert module.TEMPLATE_SPEC.scale == getattr(module, "SHEET_SCALE", (1, 1))
    assert module.TEMPLATE_SPEC.decimals == 2
    tree = ast.parse(drawing.script.read_text())
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert not any(
        call.func.id in {"new_project_drawing", "run_build"} for call in calls
    )
    (entry,) = [call for call in calls if call.func.id == "run_drawing_build"]
    assert ast.unparse(entry) == "run_drawing_build(build, spec=TEMPLATE_SPEC)"
    creators = [
        call
        for call in calls
        if call.func.id
        in {
            "drawing_factory",
            "build_fastener_sheet",
            "build_simple_three_view_drawing",
        }
    ]
    (creator,) = creators
    keywords = {item.arg: item.value for item in creator.keywords}
    if creator.func.id == "drawing_factory":
        scale = keywords.get(
            "scale", ast.Tuple(elts=[ast.Constant(1), ast.Constant(1)])
        )
        actual = (
            vars(module)[scale.id]
            if isinstance(scale, ast.Name)
            else ast.literal_eval(scale)
        )
        precision = ast.literal_eval(keywords.get("decimals", ast.Constant(2)))
        assert TemplateSpec(actual, precision) == module.TEMPLATE_SPEC
        return
    assert ast.unparse(keywords["drawing_factory"]) == "drawing_factory"
    if creator.func.id == "build_fastener_sheet":
        assert module.RECIPE.scale == module.TEMPLATE_SPEC.scale
        assert ast.unparse(keywords["recipe"]) == "RECIPE"
        return
    assert ast.unparse(keywords["sheet_scale"]) == "SHEET_SCALE"


def test_registry_and_factory_recipe_coverage_match():
    scripts = Path(__file__).resolve().parent
    assert {item.script.resolve() for item in DRAWINGS} == set(
        scripts.glob("draw_*.py")
    )


@pytest.mark.parametrize("drawing", DRAWINGS, ids=lambda item: item.name)
def test_recipe_usage_does_not_bypass_required_machine_seat(drawing):
    import ast
    import re

    docstring = ast.get_docstring(ast.parse(drawing.script.read_text())) or ""
    assert not re.search(r"uv run python[^\n]*draw_\w+\.py", docstring)


def test_prepared_runtime_is_a_real_drawing_cache_input_only():
    import dodo
    from _buildgraph import ASSEMBLY_ORDER, module_deps_of, part_scripts

    scripts = Path(__file__).resolve().parent
    runtime = {
        scripts / name
        for name in (
            "_drawing_build.py",
            "_drawing_prepared_template.py",
            "_drawing_template_defaults.py",
        )
    }
    for drawing in DRAWINGS:
        deps = {Path(path) for path in dodo._drawing_file_deps(drawing.name)}
        assert runtime <= deps
        assert drawing.source.resolve() in deps
        token = (
            dodo._assembly_execution_token(drawing.part)
            if drawing.source_kind == "assembly"
            else dodo._part_execution_token(drawing.part)
        )
        assert Path(token) in deps
        assert {path.resolve() for path in drawing.assets} <= deps
        assert not any("prepared-drawing-templates" in path.parts for path in deps)
    builds = [
        *part_scripts(),
        *(scripts / f"build_{name}_assembly.py" for name in ASSEMBLY_ORDER),
    ]
    for build in builds:
        assert not runtime & {Path(path) for path in module_deps_of(build)}, build.name


def test_runner_prepares_before_recipe_and_preserves_result(monkeypatch):
    import _drawing_build as runner

    monkeypatch.setenv("HARMONIC_COM_SEAT", "test-only-no-COM")
    adapter = object()
    spec = runner.TemplateSpec((2, 1), 2)
    entry = runner.prepared.PreparedTemplate(Path("cache"), "key", spec)
    events = []

    async def prepare(actual, *, scale, decimals):
        assert actual is adapter and (scale, decimals) == (spec.scale, 2)
        events.append("prepare")
        return entry

    def inherited(actual, actual_entry):
        assert actual is adapter and actual_entry is entry
        events.append("inherited")
        return "draw", "sheet"

    async def recipe(actual, *, drawing_factory):
        assert actual is adapter
        events.append("source_open")
        assert drawing_factory(actual, scale=(2, 1)) == ("draw", "sheet")
        return {"slddrw": "result"}

    monkeypatch.setattr(runner.prepared, "prepare_project_drawing_template", prepare)
    monkeypatch.setattr(runner.prepared, "inherited_drawing", inherited)
    monkeypatch.setattr(
        runner, "run_build", lambda callback: asyncio.run(callback(adapter))
    )
    assert runner.run_drawing_build(recipe, spec=spec) == {"slddrw": "result"}
    assert events == ["prepare", "source_open", "inherited"]


@pytest.mark.asyncio
async def test_preparation_failure_never_enters_recipe(monkeypatch):
    import _drawing_build as runner

    prepare = AsyncMock(side_effect=RuntimeError("invalid template receipt"))
    monkeypatch.setattr(runner.prepared, "prepare_project_drawing_template", prepare)
    with pytest.raises(RuntimeError, match="invalid template receipt"):
        await runner.prepare_drawing_factory(object(), runner.TemplateSpec())


@pytest.mark.parametrize("kind", ("normal", "prepared"))
def test_same_factory_adapter_spec_single_use_and_success_witness(monkeypatch, kind):
    import _drawing_build as runner

    adapter = object()
    spec = runner.TemplateSpec((1, 2), 3)
    native = Mock(return_value=("drawing", "sheet"))
    monkeypatch.setattr(runner.common, "new_project_drawing", native)
    monkeypatch.setattr(runner.prepared, "inherited_drawing", native)
    factory = (
        runner.normal_drawing_factory(adapter, spec)
        if kind == "normal"
        else runner.prepared_drawing_factory(
            adapter, runner.prepared.PreparedTemplate(Path("cache"), "key", spec)
        )
    )
    with pytest.raises(RuntimeError, match="exactly one"):
        factory.require_used()
    with pytest.raises(RuntimeError, match="adapter"):
        factory(object(), scale=(1, 2), decimals=3)
    with pytest.raises(ValueError, match="spec"):
        factory(adapter, scale=(1, 1), decimals=3)
    native.assert_not_called()
    assert factory(adapter, property_view="ignored", scale=(1, 2), decimals=3) == (
        "drawing",
        "sheet",
    )
    factory.require_used()
    with pytest.raises(RuntimeError, match="once"):
        factory(adapter, scale=(1, 2), decimals=3)
    assert native.call_count == 1


def test_failed_creation_is_not_retryable_or_successful(monkeypatch):
    import _drawing_build as runner

    native = Mock(side_effect=RuntimeError("native failed after creation"))
    monkeypatch.setattr(runner.common, "new_project_drawing", native)
    adapter = object()
    factory = runner.normal_drawing_factory(adapter, runner.TemplateSpec())
    with pytest.raises(RuntimeError, match="native failed after creation"):
        factory(adapter)
    with pytest.raises(RuntimeError, match="exactly one"):
        factory.require_used()
    with pytest.raises(RuntimeError, match="once"):
        factory(adapter)
    assert native.call_count == 1


@pytest.mark.asyncio
async def test_accessor_wrong_spec_rejected(monkeypatch):
    import _drawing_build as runner

    monkeypatch.setattr(
        runner.prepared,
        "prepare_project_drawing_template",
        AsyncMock(
            return_value=runner.prepared.PreparedTemplate(
                Path("cache"), "key", runner.TemplateSpec((3, 1))
            )
        ),
    )
    with pytest.raises(RuntimeError, match="spec"):
        await runner.prepare_drawing_factory(object(), runner.TemplateSpec((2, 1)))


@pytest.mark.parametrize("outcome", ("unused", "recipe_error"))
def test_runner_rejects_unconsumed_factory_without_replacing_recipe_error(
    monkeypatch, outcome
):
    import _drawing_build as runner

    monkeypatch.setenv("HARMONIC_COM_SEAT", "test-only-no-COM")
    adapter = object()
    entry = runner.prepared.PreparedTemplate(
        Path("cache"), "key", runner.TemplateSpec()
    )
    monkeypatch.setattr(
        runner.prepared,
        "prepare_project_drawing_template",
        AsyncMock(return_value=entry),
    )
    monkeypatch.setattr(
        runner, "run_build", lambda callback: asyncio.run(callback(adapter))
    )

    async def recipe(actual, *, drawing_factory):
        if outcome == "recipe_error":
            raise RuntimeError("source missing")
        return {}

    with pytest.raises(
        RuntimeError,
        match="source missing" if outcome == "recipe_error" else "exactly one",
    ):
        runner.run_drawing_build(recipe, spec=entry.spec)


def test_missing_machine_seat_fails_before_existing_connect_cleanup(monkeypatch):
    import _drawing_build as runner

    monkeypatch.delenv("HARMONIC_COM_SEAT", raising=False)
    connect = Mock(side_effect=AssertionError("must fail before connecting"))
    monkeypatch.setattr(runner, "run_build", connect)
    with pytest.raises(RuntimeError, match="seat"):
        runner.run_drawing_build(AsyncMock(), spec=runner.TemplateSpec())
    connect.assert_not_called()
