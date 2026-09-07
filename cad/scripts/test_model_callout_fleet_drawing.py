"""Exact 35-part / 72-row migration from the retained pre-migration contract."""

import ast
import asyncio
from collections import Counter, defaultdict
from dataclasses import replace
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from _buildgraph import module_deps_of, part_scripts
from _drawing_registry import DRAWINGS
import _model_dimension_callouts as author
import _fastener_drawing as fasteners
from draw_cone_pivot_screw import RECIPE as PIVOT_SCREW
from diagnostics._model_callout_migration_inventory import INVENTORY


ACTIVE = sorted({row["drawing"] for row in INVENTORY["calls"] if row["rows"]})


def evaluated(node, module):
    return eval(compile(ast.Expression(node), module.__file__, "eval"), vars(module))


def expected_rows(drawing):
    return Counter(
        (item["owners"][0], item["dimension"], item["text"], row["location"])
        for row in INVENTORY["calls"]
        if row["drawing"] == drawing
        for item in row["rows"]
    )


def calls(tree, name):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    ]


def tree_for(module):
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def rows_for(module, nodes, *, feature_index=None):
    rows = Counter()
    for node in nodes:
        keywords = {kw.arg: kw.value for kw in node.keywords}
        feature = evaluated(
            node.args[feature_index] if feature_index else keywords["feature_name"],
            module,
        )
        location = (
            evaluated(keywords["location"], module)
            if "location" in keywords
            else "below"
        )
        for name, text in evaluated(node.args[2], module).items():
            rows[feature, name, text, location] += 1
    return rows


@pytest.mark.parametrize("drawing", ACTIVE)
def test_every_source_authors_exact_original_rows_after_marks_before_save(drawing):
    module = importlib.import_module(drawing.replace("draw_", "build_", 1))
    tree = tree_for(module)
    authored = calls(tree, "author_model_callouts")
    assert rows_for(module, authored, feature_index=1) == expected_rows(drawing)
    marks, saves = (
        calls(tree, "mark_dimensions_for_drawing"),
        calls(tree, "save_part_and_images"),
    )
    assert len(saves) == 1
    assert max(node.lineno for node in marks) < min(node.lineno for node in authored)
    assert max(node.lineno for node in authored) < saves[0].lineno
    for feature, name, _text, _location in expected_rows(drawing):
        assert [
            owner for owner, names in module.DRAWING_DIMENSIONS.items() if name in names
        ] == [feature]


@pytest.mark.parametrize(
    "drawing", [name for name in ACTIVE if name != "draw_cone_pivot_screw"]
)
def test_every_direct_drawing_verifies_exact_rows_with_explicit_source_and_view(
    drawing,
):
    module = importlib.import_module(drawing)
    tree = tree_for(module)
    verified = calls(tree, "verify_dimension_callouts")
    assert rows_for(module, verified) == expected_rows(drawing)
    assert all(
        not evaluated(node.args[2], module)
        for node in calls(tree, "set_dimension_callouts")
    )
    source_name = (
        "source_model" if drawing == "draw_alignment_pinion" else "callout_source_model"
    )
    captured = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == source_name
            for target in node.targets
        )
    ]
    assert len(captured) == 1
    assert ast.unparse(captured[0].value) == "adapter.currentModel"
    assert captured[0].lineno < calls(tree, "drawing_factory")[0].lineno
    collectors = calls(tree, "curate_view_dimensions") + calls(
        tree, "retain_view_dimensions"
    )
    for node in verified:
        keywords = {kw.arg: kw.value for kw in node.keywords}
        assert ast.unparse(keywords["source_model"]) == source_name
        view = ast.unparse(keywords["view"])
        matching = [
            collector
            for collector in collectors
            if ast.unparse(collector.args[1]) == view
        ]
        assert len(matching) == 1
        keep = next(kw.value for kw in matching[0].keywords if kw.arg == "keep")
        if isinstance(keep, ast.Call):
            assert ast.unparse(keep.func) == "_shifted"
            keep = keep.args[0]
        assert set(evaluated(node.args[2], module)) <= set(evaluated(keep, module))


@pytest.mark.parametrize(
    "definition", INVENTORY["map_definitions"], ids=lambda row: row["drawing"]
)
def test_moved_expressions_and_shared_map_identity_are_unchanged(definition):
    drawing = importlib.import_module(definition["drawing"])
    stem = definition["drawing"].removeprefix("draw_")
    source = importlib.import_module(stem + "_spec")
    builder = importlib.import_module("build_" + stem)
    tree = tree_for(source)
    assignments = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        assignments.update(
            {
                target.id: node.value
                for target in targets
                if isinstance(target, ast.Name)
            }
        )
    for original in definition["maps"]:
        expected = ast.parse(original["source"]).body[0].value
        assert ast.dump(assignments[original["name"]]) == ast.dump(expected)
        assert getattr(source, original["name"]) is getattr(drawing, original["name"])
        assert getattr(source, original["name"]) is getattr(builder, original["name"])


def test_exact_fleet_counts_and_only_approved_part_dependency_growth():
    assert len(ACTIVE) == 35
    assert sum(sum(expected_rows(name).values()) for name in ACTIVE) == 72
    expected = {name.replace("draw_", "build_", 1) for name in ACTIVE}
    helper = str(Path(author.__file__).resolve())
    actual = {path.stem for path in part_scripts() if helper in module_deps_of(path)}
    assert actual == expected
    assert not any(
        Path(path).name == "_drawing_common.py" for path in module_deps_of(Path(helper))
    )


def test_recipe_gate_enrolls_author_and_fleet_contracts_exactly_once():
    from test_dodo_recipe import _load_dodo

    dodo = _load_dodo()
    gate = next(task for task in dodo.task_check() if task["name"] == "recipe")
    command = [Path(argument).name for argument in gate["actions"][0][1][0]]
    dependencies = {Path(path).name for path in gate["file_dep"]}
    names = {"test_model_dimension_callouts_drawing.py", Path(__file__).name}
    assert {name: command.count(name) for name in names} == dict.fromkeys(names, 1)
    assert names <= dependencies
    assert "_model_callout_migration_inventory.py" in dependencies


def test_spec_byte_invalidation_includes_exact_existing_non_author_consumers():
    migrated = set(ACTIVE) - {"draw_alignment_pinion"}
    specs = {
        str(
            Path(
                importlib.import_module(name.removeprefix("draw_") + "_spec").__file__
            ).resolve()
        )
        for name in migrated
    }
    consumers = {
        path.stem for path in part_scripts() if specs.intersection(module_deps_of(path))
    }
    assert consumers == {name.replace("draw_", "build_", 1) for name in migrated} | {
        "build_cone_swing_platform",
        "build_harmonic_base",
        "build_platen_clip",
    }
    assert len(consumers) == 37


def test_empty_only_recipes_keep_their_original_noop_maps():
    groups = defaultdict(list)
    for record in INVENTORY["calls"]:
        groups[record["drawing"]].append(record)
    empty_only = {
        name: rows
        for name, rows in groups.items()
        if not any(row["rows"] for row in rows)
    }
    assert len(empty_only) == 22
    for name, records in empty_only.items():
        module = importlib.import_module(name)
        for record in records:
            assert eval(record["expr"], vars(module)) == {}


def test_only_cone_pivot_shared_fastener_has_active_source_callouts():
    recipes = []
    for spec in DRAWINGS:
        module = importlib.import_module(spec.script.stem)
        recipe = getattr(module, "RECIPE", None)
        if recipe is not None and getattr(recipe, "side_dimension_callouts", None):
            recipes.append((module, recipe))
    assert len(recipes) == 1
    module, recipe = recipes[0]
    assert module.__name__ == "draw_cone_pivot_screw"
    assert recipe.side_callout_feature == "ThreadTail"
    assert recipe.side_dimension_callouts == {"ThreadLg": "#10-24 UNC-2A"}


@pytest.fixture
def fastener_scene(monkeypatch, tmp_path):
    source = tmp_path / "owned.SLDPRT"
    source.touch()
    source_model, drawing_model = object(), object()
    adapter = SimpleNamespace(currentModel=None)

    async def open_model(path):
        assert path == str(source)
        adapter.currentModel = source_model
        return "opened"

    def factory(adapter, **kwargs):
        assert adapter.currentModel is source_model
        adapter.currentModel = drawing_model
        return drawing_model, object()

    adapter.open_model = AsyncMock(side_effect=open_model)
    side, end, iso = (object() for _ in range(3))
    annotations = {side: [object()], end: [object()]}
    monkeypatch.setattr(fasteners, "place_view", Mock(side_effect=[side, end, iso]))
    monkeypatch.setattr(
        fasteners,
        "curate_view_dimensions",
        lambda adapter, view, **kwargs: annotations[view],
    )
    for name in (
        "check",
        "read_required_properties",
        "stamp_drawing_summary",
        "set_hidden_lines_removed",
        "add_property_linked_note",
    ):
        monkeypatch.setattr(fasteners, name, Mock())
    monkeypatch.setattr(fasteners, "finalize_drawing", AsyncMock(return_value={}))
    verifier, retired = Mock(), Mock()
    monkeypatch.setattr(fasteners, "verify_dimension_callouts", verifier)
    monkeypatch.setattr(fasteners, "set_dimension_callouts", retired)
    recipe = replace(PIVOT_SCREW, side_centerline_face=None, decorate=None, layout=None)
    return SimpleNamespace(
        adapter=adapter,
        source=source,
        source_model=source_model,
        drawing_model=drawing_model,
        factory=factory,
        side=side,
        end=end,
        annotations=annotations,
        recipe=recipe,
        verifier=verifier,
        retired=retired,
    )


def run_fastener(scene, recipe):
    return asyncio.run(
        fasteners.build_fastener_sheet(
            scene.adapter,
            drawing_factory=scene.factory,
            source=scene.source,
            property_view="owned",
            outputs=object(),
            recipe=recipe,
        )
    )


def test_shared_fastener_verifies_exact_side_owner_and_pre_factory_source(
    fastener_scene,
):
    scene = fastener_scene
    assert run_fastener(scene, scene.recipe) == {}
    scene.verifier.assert_called_once_with(
        scene.adapter,
        scene.annotations[scene.side],
        {"ThreadLg": "#10-24 UNC-2A"},
        feature_name="ThreadTail",
        view=scene.side,
        source_model=scene.source_model,
    )
    assert scene.adapter.currentModel is scene.drawing_model
    assert scene.retired.call_args_list == [
        call(scene.adapter, scene.annotations[scene.end], {}),
    ]


def test_shared_fastener_rejects_missing_source_feature_before_open(fastener_scene):
    scene = fastener_scene
    with pytest.raises(ValueError, match="exact source feature"):
        run_fastener(scene, replace(scene.recipe, side_callout_feature=None))
    scene.adapter.open_model.assert_not_called()
    scene.verifier.assert_not_called()
    scene.retired.assert_not_called()


def test_shared_fastener_empty_map_never_requires_a_source_author(fastener_scene):
    scene = fastener_scene
    recipe = replace(
        scene.recipe, side_dimension_callouts={}, side_callout_feature=None
    )
    run_fastener(scene, recipe)
    scene.verifier.assert_not_called()
    assert scene.retired.call_args_list == [
        call(scene.adapter, scene.annotations[scene.end], {}),
        call(scene.adapter, scene.annotations[scene.side], {}),
    ]
