"""Canonical selected-task construction, with no native actions or subprocess builds."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
import builtins
from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass
from enum import Enum
import importlib.util
import inspect
from pathlib import Path
from types import MappingProxyType, ModuleType, SimpleNamespace
from threading import Barrier

import pytest
import doit.loader as doit_loader
from doit.action import PythonAction
from doit.control import TaskControl
from doit.loader import generate_tasks, load_tasks
from doit.task import Task
from cad.scripts._selected_execution import SelectedExecutionError, _workspace_path


REPO_ROOT = Path(__file__).resolve().parents[2]


class _DefinitionTemplates(Mapping):
    """Normal-generator definitions, handed to cases only as deep copies.

    The captured templates are the oracle; no case can mutate them in place.
    """

    def __init__(self, definitions):
        self._definitions = MappingProxyType(definitions)

    def __getitem__(self, name):
        return deepcopy(self._definitions[name])

    def __iter__(self):
        return iter(self._definitions)

    def __len__(self):
        return len(self._definitions)


@dataclass(frozen=True)
class _TaskView:
    """Read-only graph fields of one independent normal-loader Task."""

    name: str
    targets: tuple[str, ...]
    file_dep: frozenset[str]
    task_dep: tuple[str, ...]
    subtask_of: str | None
    has_subtask: bool
    doc: str | None


@dataclass(frozen=True)
class _ControlView:
    tasks: Mapping[str, _TaskView]


def _control_view(control):
    """Project a processed TaskControl once; cases never share its mutable Tasks."""
    return _ControlView(MappingProxyType({
        name: _TaskView(
            name=task.name, targets=tuple(task.targets),
            file_dep=frozenset(task.file_dep), task_dep=tuple(task.task_dep),
            subtask_of=task.subtask_of, has_subtask=task.has_subtask, doc=task.doc,
        )
        for name, task in control.tasks.items()
    }))


@pytest.fixture(scope="module")
def dodo(tmp_path_factory):
    """Real source discovery; synthetic adapter sidecars stay outside the checkout."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HARMONIC_EXECUTOR", "local")
        patch.delenv("HARMONIC_CACHE_REFRESH", raising=False)
        spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        scratch = tmp_path_factory.mktemp("selected-factory-inputs")
        for helper, name in (
            ("_submodule_dep", "drawing"),
            ("_submodule_assembly_dep", "assembly"),
            ("_submodule_part_dep", "part"),
        ):
            sidecar = scratch / f"{name}.digest"
            sidecar.write_text(f"fixture {name}\n", encoding="utf-8")
            patch.setattr(module, helper, lambda path=sidecar: str(path))
        yield module


@pytest.fixture(scope="module")
def ordinary_graph(dodo):
    """Capture independent normal-generator definitions before doit mutates them."""
    definitions = {}
    convert = doit_loader.dict_to_task

    def capture(definition):
        name = definition["name"]
        assert name not in definitions
        definitions[name] = deepcopy(definition)
        return convert(definition)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(doit_loader, "dict_to_task", capture)
        control = TaskControl(load_tasks(dict(vars(dodo)), allow_delayed=True))
    return control, _DefinitionTemplates(definitions)


@pytest.fixture(scope="module")
def ordinary(ordinary_graph):
    return ordinary_graph[0]


@pytest.fixture(scope="module")
def ordinary_view(ordinary):
    return _control_view(ordinary)


@pytest.fixture(scope="module")
def ordinary_definitions(ordinary_graph):
    # Copy-on-read templates; the oracle never comes from selected code.
    return ordinary_graph[1]


@pytest.fixture(scope="module")
def selected_all(dodo, ordinary):
    return TaskControl(dodo.canonical_tasks(ordinary.tasks))


@pytest.fixture(scope="module")
def ordinary_records(ordinary):
    return MappingProxyType({
        name: _freeze(_record(task)) for name, task in ordinary.tasks.items()
    })


@pytest.fixture(scope="module")
def ordinary_callables(ordinary):
    return MappingProxyType({
        name: tuple(action.py_callable for action in task.actions)
        for name, task in ordinary.tasks.items()
    })


@pytest.fixture(scope="module")
def selected_records(selected_all):
    # These are actual results only; expected records exclusively use ordinary.
    return MappingProxyType({
        name: _freeze(_record(task)) for name, task in selected_all.tasks.items()
    })


@pytest.fixture(scope="module")
def selected_callables(selected_all):
    # Actual callable identities only, so cases never share selected Tasks.
    return MappingProxyType({
        name: tuple(action.py_callable for action in task.actions)
        for name, task in selected_all.tasks.items()
    })


@pytest.fixture(scope="module")
def target_owners(dodo):
    return MappingProxyType(dodo.canonical_target_owners())


def _freeze(value):
    """Compare live factory inputs, not JSON action descriptions or object ids."""
    if isinstance(value, Enum):
        return type(value).__module__, type(value).__qualname__, value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted(_freeze(item) for item in value))
    if inspect.isfunction(value) or inspect.ismethod(value):
        return (
            value.__module__, value.__qualname__,
            getattr(value, "_farm_leaf_action", False),
            getattr(value, "_remote_cache_action", False),
        )
    if callable(value):
        return type(value).__module__, type(value).__qualname__, _freeze(vars(value))
    return value


def _actions(actions):
    result = []
    for action in actions:
        assert isinstance(action, PythonAction)
        result.append((_freeze(action.py_callable), _freeze(action.args), _freeze(action.kwargs)))
    return result


def _record(task):
    return {
        "name": task.name,
        "dependencies": sorted(set(task.task_dep)),
        "file_dependencies": sorted(task.file_dep),
        "targets": list(task.targets),
        "actions": _actions(task.actions),
        "clean_actions": _actions(task.clean_actions),
        "teardown": _actions(task.teardown),
        "remove_targets": task._remove_targets,
        "uptodate": _freeze(task.uptodate),
        "value_savers": _freeze(task.value_savers),
        "subtask_of": task.subtask_of,
        "has_subtask": task.has_subtask,
        "is_subtask": getattr(task, "is_subtask", None),
        "doc": task.doc,
        "params": task.params,
        "creator_params": task.creator_params,
        "pos_arg": task.pos_arg,
        "loader": task.loader,
        "setup": task.setup_tasks,
        "getargs": task.getargs,
        "verbosity": task.verbosity,
        "result": task.result,
        "values": task.values,
    }


def _case_every_family_matches_normal_loader_after_taskcontrol(
    ordinary, selected_callables, ordinary_records, ordinary_callables, selected_records, family,
):
    names = [name for name in ordinary.tasks if name == family or name.startswith(f"{family}:")]
    assert names, f"{family} parity must not pass with no matching tasks"
    for name in names:
        assert selected_records[name] == ordinary_records[name], name
        actual = selected_callables[name]
        expected = ordinary_callables[name]
        assert len(actual) == len(expected)
        assert all(selected is normal for selected, normal in zip(actual, expected))


def _case_groups_preserve_all_child_edges_without_building_children(dodo, ordinary, monkeypatch, family):
    def forbidden(*_args, **_kwargs):
        pytest.fail("constructing a basename group must not construct any child")

    monkeypatch.setattr(dodo, "_canonical_subtask_definition", forbidden)
    selected, = dodo.canonical_tasks([family])
    normal = ordinary.tasks[family]
    assert selected.name == normal.name
    assert selected.has_subtask is normal.has_subtask is True
    assert selected.subtask_of is normal.subtask_of is None
    assert selected.doc == normal.doc
    assert tuple(selected.task_dep) == normal.task_dep
    assert not selected.actions


def _closure(control, name):
    names = set()
    pending = [name]
    while pending:
        current = pending.pop()
        if current not in names:
            names.add(current)
            pending.extend(control.tasks[current].task_dep)
    return sorted(names)


def _replay_ordinary_definitions(dodo, ordinary, definitions, monkeypatch):
    """Cache input discovery only; canonical conversion/counting remains genuine."""
    def subtask(family, subname):
        return definitions[f"{family}:{subname}"]
    monkeypatch.setattr(dodo, "_canonical_subtask_definition", subtask)
    for name, task in ordinary.tasks.items():
        if task.subtask_of is not None or task.has_subtask:
            continue
        creator = getattr(dodo, f"task_{name}")

        def singleton(name=name):
            definition = definitions[name]
            # The independent normal loader already added this singleton's name.
            definition.pop("name")
            return definition

        singleton.__doc__ = creator.__doc__
        monkeypatch.setattr(dodo, f"task_{name}", singleton)


def _case_only_requested_closure_constructs_tasks(
    dodo, ordinary, ordinary_definitions, ordinary_records, monkeypatch, family,
):
    preferred = {"verify": "verify:soundness", "check": "check:math", "package": "package:features"}
    if family in preferred:
        root = preferred[family]
    elif family in ("export", "preflight"):
        root = family
    else:
        root = next(name for name in ordinary.tasks if name.startswith(f"{family}:"))
    names = _closure(ordinary, root)
    _replay_ordinary_definitions(dodo, ordinary, ordinary_definitions, monkeypatch)
    constructed = []
    original_init = Task.__init__

    def counted(task, name, *args, **kwargs):
        constructed.append(name)
        original_init(task, name, *args, **kwargs)

    monkeypatch.setattr(Task, "__init__", counted)
    selected = dodo.canonical_tasks(names)
    assert [task.name for task in selected] == names
    assert Counter(constructed) == Counter(names), "no unrequested implicit group or sibling Task"
    control = TaskControl(selected)
    for name in names:
        assert _freeze(_record(control.tasks[name])) == ordinary_records[name], name


def _case_real_small_closure_constructs_only_requested_tasks(dodo, ordinary, ordinary_records, monkeypatch):
    """Keep a count proof with every production factory/discovery seam unpatched."""
    root = next(name for name in ordinary.tasks if name.startswith("part:"))
    names = _closure(ordinary, root)
    constructed = []
    original_init = Task.__init__

    def counted(task, name, *args, **kwargs):
        constructed.append(name)
        original_init(task, name, *args, **kwargs)

    monkeypatch.setattr(Task, "__init__", counted)
    selected = dodo.canonical_tasks(names)
    assert [task.name for task in selected] == names
    assert Counter(constructed) == Counter(names)
    control = TaskControl(selected)
    for name in names:
        assert _freeze(_record(control.tasks[name])) == ordinary_records[name], name


def _case_replayed_definitions_are_deep_independent(dodo, ordinary, ordinary_definitions):
    name = next(name for name in ordinary.tasks if name.startswith("assembly:"))
    first = ordinary_definitions[name]
    second = ordinary_definitions[name]
    first["file_dep"].append("fixture-only-input")
    assert "fixture-only-input" not in second["file_dep"]
    assert "fixture-only-input" not in ordinary_definitions[name]["file_dep"]
    tracker, = [check for check in first["uptodate"] if isinstance(check, dodo._RecipeTracker)]
    tracker.digest = "fixture-only-digest"
    for definition in (second, ordinary_definitions[name]):
        untouched, = [check for check in definition["uptodate"] if isinstance(check, dodo._RecipeTracker)]
        assert untouched.digest is None


def _case_invalid_or_duplicate_names_fail_before_task_construction(dodo, monkeypatch, names):
    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid selection must be rejected before constructing any Task")

    monkeypatch.setattr(Task, "__init__", forbidden)
    with pytest.raises(ValueError, match="canonical task"):
        dodo.canonical_tasks(names)


def _case_empty_selection_constructs_nothing(dodo, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("empty selection must not discover families or build tasks")

    monkeypatch.setattr(dodo, "_canonical_subtask_names", forbidden)
    assert dodo.canonical_tasks([]) == []


def _case_selected_check_does_not_construct_other_check_specs(dodo, monkeypatch):
    commands = []

    def forbidden(*_args, **_kwargs):
        pytest.fail("check:math must not discover recipe, feature or review siblings")

    def executed(command):
        commands.append(command)
        return {str(dodo.VERIFY_PY)}

    monkeypatch.setitem(dodo._CHECK_SPEC_BUILDERS, "recipe", forbidden)
    monkeypatch.setattr(dodo, "_feature_bundle_outputs", forbidden)
    monkeypatch.setattr(dodo, "_machinist_review_file_deps", forbidden)
    monkeypatch.setattr(dodo, "_executed_closure", executed)
    selected, = dodo.canonical_tasks(["check:math"])
    assert selected.name == "check:math"
    assert commands == [[dodo.sys.executable, str(dodo.VERIFY_PY), "--suite", "math"]]
    assert selected.file_dep == {
        str(dodo.VERIFY_PY),
        str((dodo.SCRIPTS_DIR / "_config.py").resolve()),
        *dodo._CONFIG_YAMLS,
        str(Path(dodo._local_check.__file__).resolve()),
    }
    assert selected.targets == [str(dodo.REPORTS / "check-math.ok")]
    assert selected.uptodate == []
    action, = selected.actions
    assert action.py_callable is dodo._run_stamped
    assert action.args == [
        commands[0], "check math", selected.targets[0], "check:math",
    ]


def _case_registered_checks_require_enrollment_without_building_siblings(dodo, monkeypatch):
    constructed = []

    def unrelated(_pytest_cmd):
        constructed.append("unrelated")
        pytest.fail("selecting check:math must not construct an unrelated check")

    name = "selected_factory_enrollment_probe"
    monkeypatch.setitem(dodo._CHECK_SPEC_BUILDERS, name, unrelated)
    with pytest.raises(AssertionError, match="check specs vs check-names drift"):
        dodo.canonical_tasks(["check:math"])
    assert not constructed

    monkeypatch.setattr(dodo, "_OPTIONAL_CHECK_NAMES", (*dodo._OPTIONAL_CHECK_NAMES, name))
    monkeypatch.setattr(dodo, "_executed_closure", lambda _cmd: {str(dodo.VERIFY_PY)})
    selected, = dodo.canonical_tasks(["check:math"])
    assert selected.name == "check:math"
    action, = selected.actions
    assert action.py_callable is dodo._run_stamped
    assert action.args[0] == [dodo.sys.executable, str(dodo.VERIFY_PY), "--suite", "math"]
    assert not constructed


def _case_concurrent_selections_have_independent_mutable_task_state(dodo, monkeypatch):
    monkeypatch.setattr(dodo, "_executed_closure", lambda _cmd: {str(dodo.VERIFY_PY)})
    start = Barrier(4)

    def construct(_index):
        start.wait(timeout=30)
        selected, = dodo.canonical_tasks(["check:math"])
        return selected

    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = list(executor.map(construct, range(4)))
    assert len({id(task) for task in tasks}) == 4
    expected = _freeze(_record(tasks[0]))
    assert all(_freeze(_record(task)) == expected for task in tasks)
    first, *others = tasks
    first.file_dep.add("case-only-source")
    first.task_dep.append("case-only-dependency")
    first.targets.append("case-only-target")
    first.uptodate.append((False, [], {}))
    first.actions[0].args[0].append("--case-only-argument")
    first.value_savers.append(lambda: {"case-only": True})
    assert all(_freeze(_record(task)) == expected for task in others)
    later, = dodo.canonical_tasks(["check:math"])
    assert _freeze(_record(later)) == expected


def _case_assembly_keeps_trackers_wrappers_and_doit_reserved_arguments(dodo, ordinary, monkeypatch):
    name = next(name for name in ordinary.tasks if name.startswith("assembly:"))
    selected, = dodo.canonical_tasks([name])
    action, = selected.actions
    assert action.py_callable is dodo.build_or_refresh
    assert action.py_callable._farm_leaf_action is True
    assert action.py_callable._remote_cache_action is True
    assert inspect.signature(action.py_callable).parameters.keys() == {"stem", "dependencies", "changed", "targets"}
    assert any(isinstance(check, dodo._ExecutionIdentityTracker) for check, _args, _kwargs in selected.uptodate)
    tracker, = [check for check, _args, _kwargs in selected.uptodate if isinstance(check, dodo._RecipeTracker)]
    digest = "a" * 32
    monkeypatch.setattr(dodo, "_digest_files", lambda _files: digest)
    assert tracker(selected, {}) is False
    assert selected.values == {}, "checking staleness must not record a successful recipe"
    assert len(selected.value_savers) == 1
    assert selected.value_savers[0]() == {"_recipe_digest": digest}
    assert tracker(selected, {"_recipe_digest": digest}) is True
    selected.options = {}
    selected.dep_changed = [next(iter(selected.file_dep))]
    injected = action._prepare_kwargs()
    assert set(injected["dependencies"]) == selected.file_dep
    assert injected["changed"] == selected.dep_changed
    assert injected["targets"] == selected.targets
    assert action.args == [name.removeprefix("assembly:")]


def _case_target_ownership_matches_every_normal_declared_target(target_owners, ordinary):
    expected = {
        _workspace_path(REPO_ROOT, target): name
        for name, task in ordinary.tasks.items()
        for target in task.targets
    }
    assert expected, "target ownership coverage must not be vacuous"
    assert target_owners == expected


def _case_target_ownership_never_builds_tasks_or_dependency_closures(dodo, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("ownership discovery must not compute task dictionaries or input graphs")

    for helper in (
        "_canonical_subtask_definition", "_part_file_deps", "_assembly_file_deps",
        "_drawing_file_deps", "_soundness_file_deps", "_kinematics_file_deps",
        "_bank_retention_file_deps", "_feature_export_file_deps", "_export_file_deps",
        "_preflight_file_deps", "_package_file_deps", "_check_spec", "_recipe_files",
        "_executed_closure",
    ):
        monkeypatch.setattr(dodo, helper, forbidden)
    monkeypatch.setattr(Task, "__init__", forbidden)
    assert dodo.canonical_target_owners()


def _case_target_ownership_exposes_producer_omitted_before_taskcontrol(dodo, ordinary, target_owners):
    owner_index = target_owners
    name = next(name for name in ordinary.tasks if name.startswith("assembly:"))
    selected, = dodo.canonical_tasks([name])
    omitted = {
        owner_index[relative]
        for dep in selected.file_dep
        if Path(dep).is_relative_to(REPO_ROOT)
        and (relative := _workspace_path(REPO_ROOT, dep)) in owner_index
    } - {name}
    assert omitted, "the regression requires real implicit producer edges"
    assert omitted <= set(ordinary.tasks[name].task_dep)
    assert not omitted.intersection(selected.task_dep)
    # TaskControl alone cannot detect an owner that was not given to it.
    incomplete = TaskControl([selected])
    assert not omitted.intersection(incomplete.tasks[name].task_dep)


def _case_cache_access_mode_does_not_change_factory_records(
    dodo, ordinary, ordinary_definitions, ordinary_records, monkeypatch, mode,
):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", mode)
    names = [
        next(name for name in ordinary.tasks if name.startswith(prefix))
        for prefix in ("part:", "assembly:", "drawing:", "verify_soundness:", "package:features:")
    ] + ["verify:kinematics", "check:math", "export", "preflight"]
    for selected in dodo.canonical_tasks(names):
        expected = dict(ordinary_records[selected.name])
        assert selected.task_dep == ordinary_definitions[selected.name].get("task_dep", [])
        # Normalize only TaskControl's independently captured inferred edges.
        actual = _record(selected)
        actual["dependencies"] = expected["dependencies"]
        assert _freeze(actual) == ordinary_records[selected.name]


def _case_enrolled_traveler_keeps_normal_loader_conversion_and_lazy_kernel(dodo, monkeypatch, tmp_path):
    import _process_plans

    stem = "ch_rocker_arm"
    source = tmp_path / "plan.toml"
    source.write_text('features = "fixture"\n', encoding="utf-8")
    monkeypatch.setattr(_process_plans, "TRAVELER_STEMS", (stem,))
    monkeypatch.setattr(_process_plans, "plan_path", lambda _stem: source)
    monkeypatch.setattr(_process_plans, "shop_paths", lambda: ())
    monkeypatch.setattr(_process_plans, "shop_spec_modules", lambda: ())

    def forbidden(*_args, **_kwargs):
        pytest.fail("constructing a traveler must not discover or launch FreeCAD")

    monkeypatch.setattr(dodo._PrechipsKernelTracker, "_calc", forbidden)
    normal = {task.name: task for task in generate_tasks("prechips", dodo.task_prechips(), dodo.task_prechips.__doc__)}
    selected = {task.name: task for task in dodo.canonical_tasks(["prechips", f"prechips:{stem}"])}
    assert set(selected) == set(normal)
    for name in selected:
        assert _record(selected[name]) == _record(normal[name])
    tracker, = [check for check, _args, _kwargs in selected[f"prechips:{stem}"].uptodate if isinstance(check, dodo._PrechipsKernelTracker)]
    assert tracker.identity is None
    assert selected[f"prechips:{stem}"].task_dep == [f"package:features:{stem}"]
    owners = dodo.canonical_target_owners()
    for target in selected[f"prechips:{stem}"].targets:
        assert owners[_workspace_path(REPO_ROOT, target)] == f"prechips:{stem}"


def _case_requested_order_and_iterable_are_preserved_without_dependency_expansion(dodo, ordinary):
    part = next(name for name in ordinary.tasks if name.startswith("part:"))
    names = ["verify:kinematics", part, "package:features"]
    selected = dodo.canonical_tasks(iter(names))
    assert [task.name for task in selected] == names
    assert len(selected) == len(names)
    assert selected[-1].subtask_of == "package"
    assert selected[-1].has_subtask is False


def _case_forced_refresh_preserves_other_freshness_trackers(
    dodo, ordinary, ordinary_definitions, ordinary_records, monkeypatch, family,
):
    preferred = {"verify": "verify:kinematics", "check": "check:math"}
    name = preferred.get(family) or next(
        name for name in ordinary.tasks if name.startswith(f"{family}:")
    )
    monkeypatch.setattr(dodo._cache, "forced_refresh", lambda label: "fixture-refresh" if label == name else None)
    selected, = dodo.canonical_tasks([name])
    expected = dict(ordinary_records[name])
    original_freshness = expected["uptodate"]
    expected_changes = 0 if family == "check" else 1
    assert sum(check is True for check, _args, _kwargs in original_freshness) == expected_changes
    expected["uptodate"] = tuple(
        (False, args, kwargs) if check is True else (check, args, kwargs)
        for check, args, kwargs in original_freshness
    )
    assert selected.task_dep == ordinary_definitions[name].get("task_dep", [])
    actual = _record(selected)
    actual["dependencies"] = expected["dependencies"]
    assert _freeze(actual) == _freeze(expected)
    if family == "assembly":
        assert any(isinstance(check, dodo._RecipeTracker) for check, _args, _kwargs in selected.uptodate)
    if family in ("part", "assembly"):
        assert any(isinstance(check, dodo._ExecutionIdentityTracker) for check, _args, _kwargs in selected.uptodate)


def _case_normal_generator_refreshes_one_real_part_without_sibling_construction(
    dodo, ordinary, ordinary_records, monkeypatch,
):
    """The refresh oracle includes a real normal generator, not selected factories."""
    name = next(name for name in ordinary.tasks if name.startswith("part:"))
    stem = name.removeprefix("part:")
    monkeypatch.setattr(dodo, "_seat_part_order", lambda: [stem])
    monkeypatch.setattr(dodo._cache, "forced_refresh", lambda label: "fixture-refresh" if label == name else None)
    generated = generate_tasks("part", dodo.task_part(), dodo.task_part.__doc__)
    assert [task.name for task in generated] == ["part", name]
    normal = generated[1]
    expected = dict(ordinary_records[name])
    assert sum(check is True for check, _args, _kwargs in expected["uptodate"]) == 1
    expected["uptodate"] = tuple(
        (False, args, kwargs) if check is True else (check, args, kwargs)
        for check, args, kwargs in expected["uptodate"]
    )
    assert _freeze(_record(normal)) == _freeze(expected)


def _case_selected_drawing_keeps_authoritative_model_and_exact_identity(dodo, target_owners, source_kind):
    stem = next(
        stem for stem, spec in dodo.DRAWINGS_BY_NAME.items()
        if spec.source_kind == source_kind
    )
    spec = dodo.DRAWINGS_BY_NAME[stem]
    selected, = dodo.canonical_tasks([f"drawing:{stem}"])
    if source_kind == "assembly":
        expected = {dodo._sldasm(spec.part), dodo._assembly_execution_token(spec.part)}
    else:
        expected = {dodo._sldprt(spec.part), dodo._part_execution_token(spec.part)}
    assert expected <= selected.file_dep
    owners = target_owners
    assert {
        owners[_workspace_path(REPO_ROOT, path)] for path in expected
    } == {f"{source_kind}:{spec.part}"}
    assert selected.actions[0].py_callable is dodo._cached_drawing_action
    assert selected.actions[0].py_callable._farm_leaf_action is True
    assert selected.actions[0].py_callable._remote_cache_action is True


def _case_queried_ownership_matches_complete_normal_oracle(dodo, ordinary, target_owners):
    queries = set(target_owners)
    implicit_inputs = {
        dependency
        for task in ordinary.tasks.values()
        for dependency in task.file_dep
        if Path(dependency).is_relative_to(REPO_ROOT)
        and _workspace_path(REPO_ROOT, dependency) in target_owners
    }
    queries.update(implicit_inputs)
    assert implicit_inputs, "queried ownership must cover real inferred producer inputs"
    assert dodo.canonical_target_owners(queries) == target_owners
    for family in (
        "part", "assembly", "drawing", "verify_soundness", "verify", "check",
        "package", "prechips", "export", "preflight", "gallery", "build", "release",
    ):
        selected_paths = {
            path
            for name, task in ordinary.tasks.items()
            if name == family or name.startswith(f"{family}:")
            for path in (*task.targets, *task.file_dep)
            if Path(path).is_relative_to(REPO_ROOT)
        }
        normalized = {_workspace_path(REPO_ROOT, path) for path in selected_paths}
        expected = {path: owner for path, owner in target_owners.items() if path in normalized}
        assert dodo.canonical_target_owners(selected_paths) == expected, family


def _case_part_ownership_avoids_heavy_enrollment(dodo, ordinary, target_owners, monkeypatch):
    task = next(task for name, task in ordinary.tasks.items() if name.startswith("part:"))
    query = task.targets[0]
    original_import = builtins.__import__

    def import_without_enrollment(name, *args, **kwargs):
        if name in ("export_features", "_process_plans"):
            pytest.fail(f"native-only ownership imported unrelated enrollment: {name}")
        return original_import(name, *args, **kwargs)

    def forbidden(*_args, **_kwargs):
        pytest.fail("native-only ownership parsed unrelated review/task definitions")

    monkeypatch.setattr(builtins, "__import__", import_without_enrollment)
    monkeypatch.setattr(dodo, "_reviewed_drawings", forbidden)
    monkeypatch.setattr(dodo, "mode_for_drawing", forbidden)
    monkeypatch.setattr(dodo, "_canonical_subtask_names", forbidden)
    # Simulate a clean filesystem namespace without relocating any canonical
    # target outside the source workspace. REPORTS also owns soundness targets.
    original_glob = Path.glob

    def clean_report_glob(path, pattern, *args, **kwargs):
        if path == dodo.REPORTS and pattern == "prechips-*.ok":
            return iter(())
        return original_glob(path, pattern, *args, **kwargs)

    monkeypatch.setattr(Path, "glob", clean_report_glob)
    monkeypatch.setattr(dodo, "_ownership_namespace_has_aliases", lambda *_args, **_kwargs: False)
    actual = dodo.canonical_target_owners([query])
    key = _workspace_path(REPO_ROOT, query)
    assert actual == {key: target_owners[key]}


class _ScandirIterator:
    """Match scandir's iterator, context-manager, and closed-state behavior."""

    def __init__(self, entries):
        self._entries = iter(entries)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        try:
            return next(self._entries)
        except StopIteration:
            self.close()
            raise

    def close(self):
        self.closed = True
        self._entries = iter(())

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def _case_nested_feature_junction_cannot_hide_an_omitted_producer(dodo, monkeypatch):
    """Simulate filesystem metadata only; do not create links or native outputs."""
    feature_root = dodo.CAD_OUT / "features"
    stem_directory = feature_root / "ownership_probe"
    target = stem_directory / "ownership-probe.STEP"
    relocated = dodo.CAD_OUT / "sldprt" / "ownership-probe.STEP"
    original_resolve = Path.resolve
    original_junction = Path.is_junction
    original_scandir = dodo.os.scandir
    original_targets = dodo._canonical_targets
    scans = []

    def resolved(path, strict=False):
        if path == target:
            return original_resolve(relocated, strict=strict)
        if path == stem_directory:
            return original_resolve(relocated.parent, strict=strict)
        return original_resolve(path, strict=strict)

    def junction(path):
        return path == stem_directory or original_junction(path)

    entry = SimpleNamespace(
        path=str(stem_directory), is_symlink=lambda: False,
        is_dir=lambda **_kwargs: True,
    )

    def scandir(path):
        if Path(path) == feature_root:
            scans.append(Path(path))
            return _ScandirIterator([entry])
        return original_scandir(path)

    exporter = ModuleType("export_features")
    exporter.SUPPORTED_PARTS = ("ownership_probe",)
    monkeypatch.setitem(dodo.sys.modules, "export_features", exporter)
    monkeypatch.setattr(Path, "resolve", resolved)
    monkeypatch.setattr(Path, "is_junction", junction)
    monkeypatch.setattr(dodo.os, "scandir", scandir)
    monkeypatch.setattr(
        dodo, "_canonical_targets",
        lambda name: [str(target)] if name == "package:features:ownership_probe" else original_targets(name),
    )
    key = _workspace_path(REPO_ROOT, str(relocated))
    assert dodo.canonical_target_owners([str(relocated)]) == {
        key: "package:features:ownership_probe",
    }
    assert scans == [feature_root]


def _case_alias_scan_covers_exact_declared_target_depth(dodo, ordinary, monkeypatch):
    for name, task in ordinary.tasks.items():
        if name.startswith("package:features:"):
            for target in task.targets:
                relative = Path(target).relative_to(dodo.CAD_OUT / "features")
                assert len(relative.parts) == 2
                assert relative.name == "features.toml" or relative.suffix.lower() == ".step"

    root = dodo.CAD_OUT / "features"
    stem = root / "ownership_probe"
    scanned = []
    children = []

    def entry(path, *, directory=False, alias=False):
        return SimpleNamespace(
            path=str(path), is_symlink=lambda: alias,
            is_dir=lambda **_kwargs: directory,
        )

    children.append(entry(stem / "unrelated", directory=True))

    def scandir(path):
        path = Path(path)
        scanned.append(path)
        if path == root:
            return _ScandirIterator([entry(stem, directory=True)])
        if path == stem:
            # Unrelated descendants are not canonical targets and are never walked.
            return _ScandirIterator(children)
        pytest.fail(f"ownership alias scan escaped declared target depth: {path}")

    monkeypatch.setattr(dodo.os, "scandir", scandir)
    monkeypatch.setattr(Path, "is_symlink", lambda _path: False)
    monkeypatch.setattr(Path, "is_junction", lambda _path: False)
    assert not dodo._ownership_namespace_has_aliases(
        root, filenames=frozenset({"features.toml"}), suffixes=frozenset({".step"}),
    )
    assert scanned == [root, stem]
    for filename, names, suffixes in (
        ("features.toml", frozenset({"features.toml"}), frozenset({".step"})),
        ("ownership-probe.STEP", frozenset({"features.toml"}), frozenset({".step"})),
        ("ownership-probe-Installed.STEP", frozenset({"features.toml"}), frozenset({".step"})),
        ("plan.toml", frozenset({"plan.toml", "report.json", "traveler.html"}), frozenset()),
        ("report.json", frozenset({"plan.toml", "report.json", "traveler.html"}), frozenset()),
        ("traveler.html", frozenset({"plan.toml", "report.json", "traveler.html"}), frozenset()),
    ):
        scanned.clear()
        children[:] = [entry(stem / filename, alias=True)]
        assert dodo._ownership_namespace_has_aliases(root, filenames=names, suffixes=suffixes)
        assert scanned == [root, stem]


def _case_declared_target_outside_workspace_is_refused(
    dodo, ordinary, monkeypatch
):
    query = next(
        task.targets[0] for name, task in ordinary.tasks.items()
        if name.startswith("part:")
    )
    reports = REPO_ROOT.parent / "outside-selected-reports"
    monkeypatch.setattr(dodo, "REPORTS", reports)
    # Even a native-only query must reject an escaping declared soundness
    # target; filtering it out before normalization would hide bad authority.
    with pytest.raises(SelectedExecutionError, match="escapes selected workspace") as error:
        dodo.canonical_target_owners([query])
    # The diagnostic deliberately uses !r, escaping Windows path separators.
    assert repr(str(reports))[1:-1] in str(error.value)


def _case_ownership_queries_refuse_escaping_paths(dodo):
    with pytest.raises(SelectedExecutionError, match="escapes selected workspace"):
        dodo.canonical_target_owners([str(REPO_ROOT.parent / "outside-selected-target")])


_PORTFOLIO_FAILURES = (Exception, pytest.fail.Exception)


def _run_portfolio(cases, shared, tmp_path):
    """Run every independent case, then report all ordinary failures together.

    Each case gets a fresh MonkeyPatch rolled back before the next case starts,
    and every failure carries its case identity. Interrupts and pytest.exit
    propagate at once; pytest.fail's BaseException outcome is still collected.
    """
    failures = []
    for index, (case, parameters) in enumerate(cases):
        label = f"selected factories portfolio case {index}: {case.__name__} {parameters!r}"
        try:
            with pytest.MonkeyPatch.context() as patch:
                available = {**shared, **parameters, "monkeypatch": patch}
                signature = inspect.signature(case)
                if "tmp_path" in signature.parameters:
                    directory = tmp_path / f"case-{index}"
                    directory.mkdir()
                    available["tmp_path"] = directory
                arguments = {name: available[name] for name in signature.parameters}
                case(**arguments)
        except pytest.exit.Exception:
            raise
        except _PORTFOLIO_FAILURES as error:
            error.add_note(label)
            failures.append(error)
    if failures:
        raise BaseExceptionGroup(
            f"{len(failures)} of {len(cases)} selected factories portfolio cases failed",
            failures,
        )


def test_selected_factories_portfolio(
    dodo, ordinary_view, ordinary_definitions, ordinary_records, ordinary_callables,
    selected_callables, selected_records, target_owners, tmp_path,
):
    """One scheduler item owns the heavy portfolio even under -n 8 --dist worksteal.

    Expected records/callable identities come exclusively from normal generators.
    selected_all remains a real, unpatched canonical construction. Cases share
    only read-only oracle views, never the mutable TaskControls or templates.
    """
    shared = {
        "dodo": dodo, "ordinary": ordinary_view,
        "ordinary_definitions": ordinary_definitions, "ordinary_records": ordinary_records,
        "ordinary_callables": ordinary_callables, "selected_callables": selected_callables,
        "selected_records": selected_records, "target_owners": target_owners,
    }
    cases = [
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'part'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'assembly'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'drawing'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'verify_soundness'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'verify'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'check'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'package'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'prechips'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'export'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'preflight'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'gallery'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'release'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'build'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'build_bare'}),
        (_case_every_family_matches_normal_loader_after_taskcontrol, {'family': 'cache_status'}),
        (_case_groups_preserve_all_child_edges_without_building_children, {'family': 'part'}),
        (_case_groups_preserve_all_child_edges_without_building_children, {'family': 'assembly'}),
        (_case_groups_preserve_all_child_edges_without_building_children, {'family': 'drawing'}),
        (_case_groups_preserve_all_child_edges_without_building_children, {'family': 'verify_soundness'}),
        (_case_groups_preserve_all_child_edges_without_building_children, {'family': 'verify'}),
        (_case_groups_preserve_all_child_edges_without_building_children, {'family': 'check'}),
        (_case_groups_preserve_all_child_edges_without_building_children, {'family': 'package'}),
        (_case_groups_preserve_all_child_edges_without_building_children, {'family': 'prechips'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'part'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'assembly'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'drawing'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'verify_soundness'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'verify'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'check'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'package'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'export'}),
        (_case_only_requested_closure_constructs_tasks, {'family': 'preflight'}),
        (_case_real_small_closure_constructs_only_requested_tasks, {}),
        (_case_replayed_definitions_are_deep_independent, {}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['not-a-task']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['part:']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['part:not-a-part']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['assembly:not-an-assembly']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['drawing:not-a-drawing']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['verify:not-a-suite']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['verify_soundness:not-an-assembly']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['check:not-a-check']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['check:machinist_review:not-a-drawing']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['package:features:not-a-part']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['package:not-a-package']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['prechips:not-enrolled']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['check:math', 'check:math']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['check:math', 'not-a-task']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': ['']}),
        (_case_invalid_or_duplicate_names_fail_before_task_construction, {'names': [None]}),
        (_case_empty_selection_constructs_nothing, {}),
        (_case_selected_check_does_not_construct_other_check_specs, {}),
        (_case_registered_checks_require_enrollment_without_building_siblings, {}),
        (_case_concurrent_selections_have_independent_mutable_task_state, {}),
        (_case_assembly_keeps_trackers_wrappers_and_doit_reserved_arguments, {}),
        (_case_target_ownership_matches_every_normal_declared_target, {}),
        (_case_target_ownership_never_builds_tasks_or_dependency_closures, {}),
        (_case_target_ownership_exposes_producer_omitted_before_taskcontrol, {}),
        (_case_cache_access_mode_does_not_change_factory_records, {'mode': 'ro'}),
        (_case_cache_access_mode_does_not_change_factory_records, {'mode': 'rw'}),
        (_case_enrolled_traveler_keeps_normal_loader_conversion_and_lazy_kernel, {}),
        (_case_requested_order_and_iterable_are_preserved_without_dependency_expansion, {}),
        (_case_forced_refresh_preserves_other_freshness_trackers, {'family': 'part'}),
        (_case_forced_refresh_preserves_other_freshness_trackers, {'family': 'assembly'}),
        (_case_forced_refresh_preserves_other_freshness_trackers, {'family': 'drawing'}),
        (_case_forced_refresh_preserves_other_freshness_trackers, {'family': 'verify_soundness'}),
        (_case_forced_refresh_preserves_other_freshness_trackers, {'family': 'verify'}),
        (_case_forced_refresh_preserves_other_freshness_trackers, {'family': 'check'}),
        (_case_normal_generator_refreshes_one_real_part_without_sibling_construction, {}),
        (_case_selected_drawing_keeps_authoritative_model_and_exact_identity, {'source_kind': 'part'}),
        (_case_selected_drawing_keeps_authoritative_model_and_exact_identity, {'source_kind': 'assembly'}),
        (_case_queried_ownership_matches_complete_normal_oracle, {}),
        (_case_part_ownership_avoids_heavy_enrollment, {}),
        (_case_nested_feature_junction_cannot_hide_an_omitted_producer, {}),
        (_case_alias_scan_covers_exact_declared_target_depth, {}),
        (_case_declared_target_outside_workspace_is_refused, {}),
        (_case_ownership_queries_refuse_escaping_paths, {}),
    ]
    _run_portfolio(cases, shared, tmp_path)


# Runner and oracle-view regressions use synthetic cases only: no dodo import.


def test_portfolio_runs_every_case_and_reports_each_failure_with_identity(tmp_path):
    ran = []

    def asserted(label):
        ran.append(label)
        assert label == "unexpected", "ordinary assertion"

    def failed(label):
        ran.append(label)
        pytest.fail("pytest.fail outcome")

    def raised(label):
        ran.append(label)
        raise ValueError("ordinary error")

    def passed(label):
        ran.append(label)

    cases = [
        (asserted, {"label": "first"}), (failed, {"label": "second"}),
        (passed, {"label": "third"}), (raised, {"label": "fourth"}),
    ]
    with pytest.raises(BaseExceptionGroup) as group:
        _run_portfolio(cases, {}, tmp_path)
    assert ran == ["first", "second", "third", "fourth"]
    errors = group.value.exceptions
    assert [type(error) for error in errors] == [AssertionError, pytest.fail.Exception, ValueError]
    assert "3 of 4" in str(group.value)
    for error, (index, name, label) in zip(errors, [
        (0, "asserted", "first"), (1, "failed", "second"), (3, "raised", "fourth"),
    ]):
        assert error.__notes__ == [
            f"selected factories portfolio case {index}: {name} {{'label': {label!r}}}"
        ]


def test_portfolio_rolls_back_each_case_patch_before_the_next(tmp_path):
    target = SimpleNamespace(value="original")
    observed = []

    def patch_then_fail(monkeypatch, tmp_path):
        monkeypatch.setattr(target, "value", "patched")
        (tmp_path / "scratch").write_text("case-local", encoding="utf-8")
        observed.append((target.value, tmp_path.name))
        assert False, "patched case fails"

    def observe(monkeypatch, tmp_path):
        observed.append((target.value, tmp_path.name))
        assert not (tmp_path / "scratch").exists()

    with pytest.raises(BaseExceptionGroup) as group:
        _run_portfolio([(patch_then_fail, {}), (observe, {})], {}, tmp_path)
    assert len(group.value.exceptions) == 1
    assert observed == [("patched", "case-0"), ("original", "case-1")]
    assert target.value == "original"


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit, pytest.exit.Exception])
def test_portfolio_propagates_interrupts_without_running_later_cases(tmp_path, interrupt):
    target = SimpleNamespace(value="original")
    ran = []

    def earlier_failure():
        ran.append("earlier")
        assert False

    def interrupted(monkeypatch):
        monkeypatch.setattr(target, "value", "patched")
        ran.append("interrupted")
        raise interrupt("stop the session")

    def later():
        ran.append("later")

    with pytest.raises(interrupt):
        _run_portfolio(
            [(earlier_failure, {}), (interrupted, {}), (later, {})], {}, tmp_path,
        )
    assert ran == ["earlier", "interrupted"]
    assert target.value == "original"


def test_shared_oracle_views_cannot_be_mutated_by_cases():
    child = Task("part:child", [], file_dep=["source.py"], targets=["child.out"], subtask_of="part")
    group = Task("part", None, task_dep=["part:child"], has_subtask=True, doc="parts")
    view = _control_view(TaskControl([group, child]))
    task = view.tasks["part"]
    assert task.task_dep == ("part:child",)
    assert view.tasks["part:child"].file_dep == frozenset({"source.py"})
    with pytest.raises(TypeError):
        view.tasks["other"] = task
    with pytest.raises(FrozenInstanceError):
        task.task_dep = ()
    with pytest.raises(AttributeError):
        task.task_dep.append("part:other")

    templates = _DefinitionTemplates({"part:child": {"file_dep": ["source.py"], "name": "part:child"}})
    copy = templates["part:child"]
    copy["file_dep"].append("case-only-input")
    copy.pop("name")
    assert templates["part:child"] == {"file_dep": ["source.py"], "name": "part:child"}
    assert list(templates) == ["part:child"] and len(templates) == 1
