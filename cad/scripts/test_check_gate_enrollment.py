"""Audit maintained pytest discovery against actual required check producers.

Paths are repository-relative, never basenames.  Root-runner infrastructure and
the opt-in telemetry verifier have explicit dispositions; every other maintained
test must be reached by a required gate.  There is no pending-orphan allowance.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_ANCHORS = {
    "cad/scripts": "cad/scripts/test_check_gate_enrollment.py",
    "cad/comparisons/tools": "cad/comparisons/tools/test_seed_manifest.py",
    "tests": "tests/test_pytest_scope.py",
}

# These are runner responsibilities, not exemptions waiting for triage.  Keep
# entries as rows so duplicate dispositions cannot disappear in a dict literal.
DISPOSITIONS = (
    (
        "cad/scripts/test_verify_telemetry.py",
        "opt-in-or-release-only",
        "The verify_telemetry check is opt-in, not part of the required build gates.",
    ),
    (
        "tests/test_solidworks_launch_guard.py",
        "justified-root-runner",
        "Root conftest's SolidWorks launch-refusal contract belongs to the root runner.",
    ),
    (
        "tests/test_pytest_scope.py",
        "justified-root-runner",
        "Root collection scope excludes vendored suites for bare pytest and pytest dot.",
    ),
    (
        "tests/test_farm_mode.py",
        "justified-root-runner",
        "Farm submitter execution and outcome handling are root build-runner contracts.",
    ),
    (
        "tests/test_farm_launcher.py",
        "justified-root-runner",
        "The supervised Windows farm launcher is root-runner infrastructure.",
    ),
    (
        "tests/test_farm_checkout_drift.py",
        "justified-root-runner",
        "The submitter's checkout-drift guard exercises root-runner scratch Git checkouts.",
    ),
    (
        "tests/test_doit_load_span.py",
        "justified-root-runner",
        "Ordinary root-runner graph and CLI loading emit the doit.load telemetry span.",
    ),
    (
        "cad/comparisons/tools/test_pose_to_meshprobe.py",
        "justified-root-runner",
        "Renderer-convention comparison needs optional Blender and meshprobe render artifacts.",
    ),
)


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        pytest.fail(f"pytest target is outside the maintained repository: {path}")


def _matches(path: Path, patterns, root: Path) -> bool:
    return any(
        fnmatchcase(candidate, pattern)
        for pattern in patterns
        for candidate in (path.name, path.as_posix(), _relative(path, root))
    )


def _configured_inventory(config, root: Path, anchors=ROOT_ANCHORS) -> set[str]:
    """Discover independently from the settings pytest actually loaded."""
    configured = config.getini("testpaths")
    assert len(configured) == len(set(configured)), "duplicate configured pytest roots"
    assert set(configured) == set(anchors), (
        f"maintained pytest roots changed: {configured}; expected {sorted(anchors)}"
    )
    filenames = config.getini("python_files")
    excluded = config.getini("norecursedirs")
    assert filenames, "pytest python_files must not be empty"
    inventory: set[str] = set()
    for relative_root, anchor in anchors.items():
        directory = root / relative_root
        assert directory.is_dir(), f"missing maintained pytest root: {relative_root}"
        assert not _matches(directory, excluded, root), (
            f"maintained pytest root is excluded: {relative_root}"
        )
        members: set[str] = set()
        for current, directories, files in os.walk(directory, followlinks=False):
            base = Path(current)
            directories[:] = [
                name
                for name in directories
                if not (base / name).is_symlink()
                and not _matches(base / name, excluded, root)
            ]
            members.update(
                _relative(base / name, root)
                for name in files
                if (base / name).suffix == ".py"
                and _matches(base / name, filenames, root)
            )
        assert members, f"empty maintained pytest root: {relative_root}"
        assert anchor in members, (
            f"missing maintained pytest root anchor: {anchor} in {relative_root}"
        )
        inventory.update(members)
    return inventory


def _gate_reach(dodo, inventory: set[str], root: Path):
    required_names = set(dodo._CHECK_NAMES)
    optional_names = set(dodo._OPTIONAL_CHECK_NAMES)
    assert len(required_names) == len(dodo._CHECK_NAMES), "duplicate required check names"
    assert len(optional_names) == len(dodo._OPTIONAL_CHECK_NAMES), "duplicate optional check names"
    assert not required_names & optional_names, "optional check masquerades as required"
    required: dict[str, set[str]] = {}
    optional: dict[str, set[str]] = {}
    seen: set[str] = set()
    for task in dodo.task_check():
        name = task["name"]
        assert name not in seen, f"duplicate check producer: {name}"
        seen.add(name)
        assert name in required_names | optional_names, f"unknown check producer: {name}"
        actions = task["actions"]
        assert len(actions) == 1, f"unsupported check action shape: {name}"
        run, arguments = actions[0]
        assert run is dodo._run_stamped and len(arguments) == 4, (
            f"unsupported check action shape: {name}"
        )
        cmd, _label, _stamp, task_name = arguments
        assert task_name == f"check:{name}", f"wrong stamped task name: {task_name}"
        assert len(cmd) >= 2, f"empty check command: {name}"
        if list(cmd[1:3]) != ["-m", "pytest"]:
            driver = Path(str(cmd[1]))
            if not driver.is_absolute():
                driver = root / driver
            assert "pytest" not in cmd and not (
                driver.suffix == ".py" and _relative(driver, root) in inventory
            ), f"test gate does not invoke python -m pytest: {name}: {cmd}"
            continue
        targets = []
        for arg in cmd[3:]:
            text = str(arg)
            if text == "-q":
                continue
            assert not text.startswith("-") and "::" not in text, (
                f"unsupported pytest selector in check:{name}: {text}"
            )
            path = Path(text)
            if not path.is_absolute():
                path = root / path
            assert path.is_file() and path.suffix == ".py", (
                f"unsupported or missing pytest target in check:{name}: {text}"
            )
            target = _relative(path, root)
            assert target in inventory, (
                f"stale or out-of-scope pytest target in check:{name}: {target}"
            )
            assert target not in targets, f"duplicate pytest target in check:{name}: {target}"
            targets.append(target)
        assert targets, f"pytest gate has no explicit maintained targets: {name}"
        reach = required if name in required_names else optional
        for target in targets:
            reach.setdefault(target, set()).add(name)
    assert seen == required_names | optional_names, (
        f"missing check producers: {sorted((required_names | optional_names) - seen)}"
    )
    return required, optional


def _audit_dispositions(inventory, required, optional, dispositions=DISPOSITIONS):
    assert not (set(required) | set(optional)) - inventory, "unknown gate inventory paths"
    assert not set(required) & set(optional), "optional test masquerades as required"
    classified = {path: "required-gate" for path in required}
    seen: set[str] = set()
    for path, category, reason in dispositions:
        assert path not in seen, f"duplicate disposition: {path}"
        seen.add(path)
        assert path in inventory, f"stale disposition: {path}"
        assert category in {"opt-in-or-release-only", "justified-root-runner"}, (
            f"unknown or pending disposition: {path}: {category}"
        )
        assert isinstance(reason, str) and reason.strip(), f"missing disposition reason: {path}"
        assert path not in required, f"optional or runner-only disposition is required: {path}"
        if category == "opt-in-or-release-only":
            assert path in optional, f"optional disposition has no optional gate: {path}"
        else:
            assert path not in optional, f"root-runner disposition is gated: {path}"
        classified[path] = category
    assert not set(optional) - seen, (
        f"optional gates need explicit dispositions: {sorted(set(optional) - seen)}"
    )
    assert not inventory - classified.keys(), (
        "test files no required check gate collects: "
        f"{sorted(inventory - classified.keys())}"
    )
    return classified


def _assert_root_collection(inventory, collected):
    assert not collected - inventory, (
        f"root pytest collected out-of-scope test paths: {sorted(collected - inventory)}"
    )
    assert not inventory - collected, (
        f"root pytest did not collect maintained test paths: {sorted(inventory - collected)}"
    )


def test_every_maintained_test_has_a_current_disposition(pytestconfig):
    inventory = _configured_inventory(pytestconfig, REPO_ROOT)
    required, optional = _gate_reach(_load_dodo(), inventory, REPO_ROOT)
    classified = _audit_dispositions(inventory, required, optional)
    assert classified[_relative(Path(__file__), REPO_ROOT)] == "required-gate"
    assert optional["cad/scripts/test_verify_telemetry.py"] == {"verify_telemetry"}


def _audit_session_collection(pytestconfig, root, inventory, witness_path):
    """Return whether this already-collected session is a full-root witness."""
    session = pytestconfig.pluginmanager.get_plugin("session")
    assert session is not None, "pytest's collected session is unavailable"
    collected = {_relative(Path(item.path), root) for item in session.items}
    witness = _relative(witness_path, root)
    assert witness in collected, f"pytest did not collect its enrollment witness: {witness}"
    assert not collected - inventory, (
        f"pytest collected out-of-scope test paths: {sorted(collected - inventory)}"
    )
    # Root arguments survive pytest's filtering hooks. Their remaining items
    # cannot witness complete root collection, even if a filter happened to
    # match everything. Order-only --ff/--nf and --collect-only do not filter.
    filtered = any(
        pytestconfig.getoption(option, default=None)
        for option in ("keyword", "markexpr", "lf", "deselect", "ignore", "ignore_glob")
    )
    reporter = pytestconfig.pluginmanager.get_plugin("terminalreporter")
    deselected = reporter is not None and bool(reporter.stats.get("deselected"))
    if filtered or deselected or any("::" in arg for arg in pytestconfig.args):
        return False
    selectors = {
        _relative(Path(arg) if Path(arg).is_absolute() else root / arg, root)
        for arg in pytestconfig.args
    }
    if selectors not in (set(ROOT_ANCHORS), {"."}):
        return False
    _assert_root_collection(inventory, collected)
    return True


def test_actual_root_collection_matches_configured_inventory(pytestconfig):
    # Never recursively run pytest: the existing session is the collection
    # witness, not proof that the collected tests have executed or passed.
    inventory = _configured_inventory(pytestconfig, REPO_ROOT)
    if not _audit_session_collection(pytestconfig, REPO_ROOT, inventory, Path(__file__)):
        pytest.skip("full-root collection witness requires an unfiltered root selection")


@pytest.fixture
def inventory_tree(tmp_path):
    settings = {
        "testpaths": list(ROOT_ANCHORS),
        "python_files": ["test_*.py", "*_test.py"],
        "norecursedirs": [".*", "build", "references", "SolidworksMCP-python"],
    }
    for anchor in ROOT_ANCHORS.values():
        path = tmp_path / anchor
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_anchor(): pass\n", encoding="utf-8")
    return tmp_path, SimpleNamespace(getini=settings.__getitem__), settings


def _write_test(root, relative):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def test_scratch(): pass\n", encoding="utf-8")
    return path


def _fake_dodo(root, required_targets, optional_targets=()):
    def run(*args):
        raise AssertionError("the enrollment audit must never execute an action")

    def task(name, targets):
        return {
            "name": name,
            "actions": [(run, [
                ["python", "-m", "pytest", "-q", *(str(root / path) for path in targets)],
                f"check {name}", str(root / f"{name}.ok"), f"check:{name}",
            ])],
        }

    tasks = [task("recipe", required_targets)]
    if optional_targets:
        tasks.append(task("verify_telemetry", optional_targets))
    return SimpleNamespace(
        _CHECK_NAMES=("recipe",),
        _OPTIONAL_CHECK_NAMES=("verify_telemetry",) if optional_targets else (),
        _run_stamped=run,
        task_check=lambda: tasks,
    )


def test_nested_orphan_and_same_basename_are_independent(inventory_tree):
    root, config, _settings = inventory_tree
    top = "cad/scripts/test_collision.py"
    nested = "cad/scripts/diagnostics/test_collision.py"
    _write_test(root, top)
    _write_test(root, nested)
    inventory = _configured_inventory(config, root)
    dodo = _fake_dodo(root, sorted(inventory - {nested}))
    required, optional = _gate_reach(dodo, inventory, root)
    with pytest.raises(AssertionError, match=nested):
        _audit_dispositions(inventory, required, optional, ())
    assert top in required and nested not in required
    moved = "cad/scripts/diagnostics/deeper/test_collision.py"
    (root / moved).parent.mkdir(parents=True)
    (root / nested).rename(root / moved)
    with pytest.raises(AssertionError, match=nested):
        _audit_dispositions(
            _configured_inventory(config, root), required, optional,
            ((nested, "justified-root-runner", "A former scratch runner."),),
        )


def test_missing_required_gate_cannot_be_satisfied_by_optional_reach(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    missing = ROOT_ANCHORS["cad/scripts"]
    dodo = _fake_dodo(root, sorted(inventory - {missing}), [missing])
    required, optional = _gate_reach(dodo, inventory, root)
    with pytest.raises(AssertionError, match="explicit dispositions"):
        _audit_dispositions(inventory, required, optional, ())


@pytest.mark.parametrize("bad_category", ["pending", "unknown"])
def test_unknown_or_pending_disposition_is_rejected(inventory_tree, bad_category):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    path = ROOT_ANCHORS["tests"]
    with pytest.raises(AssertionError, match="unknown or pending"):
        _audit_dispositions(
            inventory, {p: {"recipe"} for p in inventory - {path}}, {},
            ((path, bad_category, "Not a valid disposition."),),
        )


@pytest.mark.parametrize("reason", [None, "", " \t"])
def test_runner_disposition_requires_a_reason(inventory_tree, reason):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    path = ROOT_ANCHORS["tests"]
    with pytest.raises(AssertionError, match="missing disposition reason"):
        _audit_dispositions(
            inventory, {p: {"recipe"} for p in inventory - {path}}, {},
            ((path, "justified-root-runner", reason),),
        )


def test_duplicate_and_stale_dispositions_are_rejected(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    path = ROOT_ANCHORS["tests"]
    required = {p: {"recipe"} for p in inventory - {path}}
    row = (path, "justified-root-runner", "Scratch root infrastructure.")
    with pytest.raises(AssertionError, match="duplicate disposition"):
        _audit_dispositions(inventory, required, {}, (row, row))
    with pytest.raises(AssertionError, match="stale disposition"):
        _audit_dispositions(inventory, required, {}, (
            ("tests/test_removed.py", "justified-root-runner", "Removed runner."),
        ))


def test_optional_disposition_cannot_masquerade_as_required(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    path = ROOT_ANCHORS["tests"]
    with pytest.raises(AssertionError, match="disposition is required"):
        _audit_dispositions(
            inventory, {p: {"recipe"} for p in inventory}, {},
            ((path, "opt-in-or-release-only", "Optional scratch verifier."),),
        )


def test_configured_filename_patterns_and_excluded_directories(inventory_tree):
    root, config, settings = inventory_tree
    included = "cad/scripts/diagnostics/nested_test.py"
    _write_test(root, included)
    excluded = [
        f"cad/scripts/{directory}/test_not_maintained.py"
        for directory in (".hidden", "build", "references", "SolidworksMCP-python")
    ]
    for path in excluded:
        _write_test(root, path)
    inventory = _configured_inventory(config, root)
    assert included in inventory
    assert not set(excluded) & inventory
    required, optional = _gate_reach(_fake_dodo(root, sorted(inventory)), inventory, root)
    assert _audit_dispositions(inventory, required, optional, ())[included] == "required-gate"
    settings["python_files"] = ["test_*.py"]
    assert included not in _configured_inventory(config, root)


@pytest.mark.parametrize("relative_root", ROOT_ANCHORS)
@pytest.mark.parametrize("mutation", ["empty", "moved", "excluded", "reconfigured"])
def test_each_configured_root_requires_its_own_anchor(inventory_tree, relative_root, mutation):
    root, config, settings = inventory_tree
    anchor = root / ROOT_ANCHORS[relative_root]
    if mutation == "empty":
        anchor.unlink()
    elif mutation == "moved":
        anchor.rename(anchor.with_name("test_moved_anchor.py"))
    elif mutation == "excluded":
        settings["norecursedirs"].append(relative_root)
    else:
        settings["testpaths"] = [
            "elsewhere" if path == relative_root else path
            for path in settings["testpaths"]
        ]
    with pytest.raises(AssertionError, match="root"):
        _configured_inventory(config, root)


@pytest.mark.parametrize("selector", ["-k", "--ignore=tests", "cad/scripts", "test.py::test_one"])
def test_unsupported_actual_pytest_selectors_fail_closed(inventory_tree, selector):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    dodo = _fake_dodo(root, sorted(inventory))
    dodo.task_check()[0]["actions"][0][1][0].append(selector)
    with pytest.raises(AssertionError, match="unsupported"):
        _gate_reach(dodo, inventory, root)


def test_non_pytest_action_and_duplicate_target_are_rejected(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    dodo = _fake_dodo(root, sorted(inventory))
    command = dodo.task_check()[0]["actions"][0][1][0]
    command[:] = ["python", str(root / ROOT_ANCHORS["cad/scripts"])]
    with pytest.raises(AssertionError, match="does not invoke"):
        _gate_reach(dodo, inventory, root)
    dodo = _fake_dodo(root, [*sorted(inventory), ROOT_ANCHORS["tests"]])
    with pytest.raises(AssertionError, match="duplicate pytest target"):
        _gate_reach(dodo, inventory, root)


def test_non_pytest_source_scanner_does_not_count_as_collection(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    dodo = _fake_dodo(root, sorted(inventory))
    dodo.task_check()[0]["actions"][0][1][0][:] = [
        "python", "-m", "ruff", "check", *(str(root / path) for path in inventory),
    ]
    required, optional = _gate_reach(dodo, inventory, root)
    assert not required and not optional
    with pytest.raises(AssertionError, match="no required check gate"):
        _audit_dispositions(inventory, required, optional, ())


def test_removed_required_target_is_reported_as_an_orphan(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    omitted = ROOT_ANCHORS["tests"]
    required, optional = _gate_reach(
        _fake_dodo(root, sorted(inventory - {omitted})), inventory, root
    )
    with pytest.raises(AssertionError, match=omitted):
        _audit_dispositions(inventory, required, optional, ())


def test_optional_registry_overlap_and_stale_gate_target_fail(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    dodo = _fake_dodo(root, sorted(inventory))
    dodo._OPTIONAL_CHECK_NAMES = ("recipe",)
    with pytest.raises(AssertionError, match="masquerades as required"):
        _gate_reach(dodo, inventory, root)
    dodo = _fake_dodo(root, [*sorted(inventory), "tests/test_missing.py"])
    with pytest.raises(AssertionError, match="missing pytest target"):
        _gate_reach(dodo, inventory, root)


@pytest.mark.parametrize("relative_root", ROOT_ANCHORS)
def test_collected_root_witness_cannot_omit_a_root(inventory_tree, relative_root):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    with pytest.raises(AssertionError, match=ROOT_ANCHORS[relative_root]):
        _assert_root_collection(inventory, inventory - {ROOT_ANCHORS[relative_root]})


def _collected_session_config(root, collected, *, options=None, args=None, deselected=()):
    session = SimpleNamespace(
        items=[SimpleNamespace(path=root / relative) for relative in sorted(collected)]
    )
    plugins = {
        "session": session,
        "terminalreporter": SimpleNamespace(stats={"deselected": list(deselected)}),
    }
    options = options or {}
    return SimpleNamespace(
        args=list(ROOT_ANCHORS) if args is None else args,
        getoption=lambda name, default=None: options.get(name, default),
        pluginmanager=SimpleNamespace(get_plugin=plugins.get),
    )


@pytest.mark.parametrize("args", [list(ROOT_ANCHORS), ["."]])
@pytest.mark.parametrize(("option", "value"), [
    ("keyword", "enrollment"),
    ("markexpr", "offline"),
    ("lf", True),
    ("deselect", ["tests/test_pytest_scope.py::test_pytest_reads_the_root_configuration"]),
    ("ignore", ["tests/test_pytest_scope.py"]),
    ("ignore_glob", ["tests/test_pytest_*.py"]),
])
def test_filtered_root_session_is_not_a_full_collection_witness(
    inventory_tree, args, option, value
):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    missing = ROOT_ANCHORS["tests"]
    collected = inventory - {missing}
    witness = root / ROOT_ANCHORS["cad/scripts"]
    selection = {option: value}
    config = _collected_session_config(root, collected, options=selection, args=args)
    assert _audit_session_collection(config, root, inventory, witness) is False
    # Same incomplete session, but no intentional selection: the consumer must
    # still refuse the named missing path, not silently lower root coverage.
    selection.clear()
    with pytest.raises(AssertionError, match=missing):
        _audit_session_collection(config, root, inventory, witness)


def test_recorded_deselection_without_selection_options_is_not_a_full_witness(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    missing = ROOT_ANCHORS["tests"]
    config = _collected_session_config(
        root, inventory - {missing}, deselected=[SimpleNamespace(path=root / missing)]
    )
    witness = root / ROOT_ANCHORS["cad/scripts"]
    assert _audit_session_collection(config, root, inventory, witness) is False
    config.pluginmanager.get_plugin("terminalreporter").stats["deselected"].clear()
    with pytest.raises(AssertionError, match=missing):
        _audit_session_collection(config, root, inventory, witness)


@pytest.mark.parametrize("option", ["failedfirst", "newfirst", "collectonly"])
def test_order_only_and_collection_only_modes_preserve_full_root_refusals(inventory_tree, option):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    missing = ROOT_ANCHORS["tests"]
    config = _collected_session_config(root, inventory - {missing}, options={option: True})
    witness = root / ROOT_ANCHORS["cad/scripts"]
    with pytest.raises(AssertionError, match=missing):
        _audit_session_collection(config, root, inventory, witness)
    config.pluginmanager.get_plugin("session").items.append(SimpleNamespace(path=root / missing))
    assert _audit_session_collection(config, root, inventory, witness) is True


@pytest.mark.parametrize("args", [
    ["cad/scripts/test_check_gate_enrollment.py"],
    [*ROOT_ANCHORS, "tests/test_pytest_scope.py::test_pytest_reads_the_root_configuration"],
])
def test_explicit_file_or_node_selection_is_not_a_full_root_witness(inventory_tree, args):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    config = _collected_session_config(root, inventory - {ROOT_ANCHORS["tests"]}, args=args)
    assert _audit_session_collection(
        config, root, inventory, root / ROOT_ANCHORS["cad/scripts"]
    ) is False


def test_filtered_collection_still_refuses_out_of_scope_items(inventory_tree):
    root, config, _settings = inventory_tree
    inventory = _configured_inventory(config, root)
    outside = "SolidworksMCP-python/tests/test_vendor.py"
    config = _collected_session_config(
        root, inventory | {outside}, options={"keyword": "enrollment"}
    )
    with pytest.raises(AssertionError, match=outside):
        _audit_session_collection(
            config, root, inventory, root / ROOT_ANCHORS["cad/scripts"]
        )
