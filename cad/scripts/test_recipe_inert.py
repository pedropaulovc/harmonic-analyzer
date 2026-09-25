"""``check:inert``: a recipe-inert module can never change a saved artefact.

``_buildgraph.RECIPE_INERT_MODULES`` are left out of every part/assembly/drawing
recipe, so editing one re-keys nothing (perf F2.6: 8 of 16 recent ``_common.py``
commits, each of which re-keyed all 227 leaves, touched only this kind of code).
That is sound only while the modules stay observation-only. These rules make
the claim checkable instead of argued, and fail loud when a change breaks it:

1. Skip set: each inert module is outside ``_local_modules`` and in no build
   script's closure (so in no recipe or cache key).
2. Call sites (no geometry-path use): every reference from a local module to an
   inert module is ``<module>.<name>`` inside a pinned ``(file, function)``, or a
   ``capture_com_failure(...)`` call statement, which always raises.
3. Inertness: the inert module makes no COM mutator call (a Save/Set/Add/Insert/
   Create/Edit/Select/... verb, which covers custom-property and dimension
   writes) except three pinned ones, reached only after the artefact is
   settled. It stores no attribute on a foreign object, and nothing reachable
   from its PRE-SAVE entry points reaches any pinned mutator.
4. Direction: an inert module imports no tracked local module except through
   pinned attribute reads.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _buildgraph as bg  # noqa: E402

SCRIPTS = bg.SCRIPTS_DIR
INERT = {Path(name).stem: SCRIPTS / name for name in bg.RECIPE_INERT_MODULES}

# Rule 2: where tracked code may name the inert module, and what it may use there.
CALL_SITES: dict[tuple[str, str], frozenset[str]] = {
    # Connect-time provenance (read-only) and the post-save teardown.
    ("_common.py", "run_build"): frozenset(
        {"note_seats_before_connect", "record_seat_provenance", "teardown_seat"}
    ),
    # PRE-save, by necessity: the camera moves right after this, and the snapshot
    # records the view the sketches were authored under. Rule 3 proves it reads only.
    ("_common.py", "save_part_and_images"): frozenset({"record_authoring_context"}),
    # Release packaging's own teardown, after Pack-and-Go.
    ("package_native.py", "_release_seat"): frozenset({"release_seat_working_directory"}),
}
# Allowed anywhere, but only as a statement whose value is the call: it always raises.
TERMINAL = frozenset({"capture_com_failure"})

# Rule 3: the COM mutators an inert module may call, and the function that calls each.
MUTATOR = re.compile(
    r"^(Save|Rebuild|ForceRebuild|EditRebuild|Insert|Create|Delete|Edit|Select|Set|Add|"
    r"Close|Show|Blank|Hide|Modify|Suppress|Unsuppress|Clear|Paste|Import|Open|New|"
    r"Activate|Rename|Replace|Move|Copy|Change|Put)[A-Z0-9_]"
)
PINNED_MUTATORS = {
    ("_save_failure_document", "SaveAs3"),  # a COPY of the failing document
    ("_save_seat_image", "SaveBMP"),  # the viewport, no camera move
    ("release_seat_working_directory", "SetCurrentWorkingDirectory"),  # teardown
    ("_process_handle", "OpenProcess"),  # kernel32, another process: read access
    ("_process_handle", "CloseHandle"),  # kernel32, the handle just opened
}
# Functions holding a pinned document/seat mutator, and the only in-module roots
# that may reach them. capture_com_failure always raises; teardown_seat runs after
# the build returned.
MUTATOR_ROOTS = {
    "_save_failure_document": {"capture_com_failure"},
    "_save_seat_image": {"capture_com_failure"},
    "release_seat_working_directory": {"teardown_seat"},
}
# Entry points that run BEFORE an artefact is saved: nothing they reach may mutate.
PRE_SAVE = {"record_authoring_context", "record_seat_provenance", "note_seats_before_connect"}
# ctypes structures and prototypes the module builds itself.
LOCAL_ATTRIBUTE_STORES = {"cb", "argtypes", "restype"}

# Rule 4: the tracked names an inert module may read, per tracked module.
READS: dict[str, frozenset[str]] = {
    "_common": frozenset(
        {
            "CAD_ROOT",
            "_read_member",
            "_early_bound",
            "_preference_id",
            "_attributes_of",
            "_scalar",
            "_FEATURE_ERROR",
            "active_configuration_name",
            # Teardown only (rule 3 pins teardown_seat's callers).
            "discard_open_documents",
            "_resident_output_documents",
        }
    ),
    "_sketch_closure": frozenset({"_sketch_state"}),
    "_telemetry": frozenset(),  # skipped from recipes itself; any use is fine
    "_watchdog": frozenset(),
}
OPEN_READS = {"_telemetry", "_watchdog"}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _tracked_sources() -> Iterator[Path]:
    yield from sorted(set(bg._local_modules().values()))


def _top_level_of(tree: ast.Module) -> dict[int, str]:
    """``id(node) -> name`` of the top-level def/class that contains it."""
    owners: dict[int, str] = {}
    for top in tree.body:
        name = getattr(top, "name", "<module>")
        for node in ast.walk(top):
            owners[id(node)] = name
    return owners


def _functions(tree: ast.Module) -> dict[str, ast.AST]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _referenced(function: ast.AST, names: set[str]) -> set[str]:
    return {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and node.id in names
    }


def _reachable(tree: ast.Module, roots: set[str]) -> set[str]:
    functions = _functions(tree)
    seen: set[str] = set()
    frontier = [root for root in roots if root in functions]
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        frontier.extend(_referenced(functions[name], set(functions)) - seen)
    return seen


def test_the_inert_set_is_not_empty_and_exists():
    assert INERT, "RECIPE_INERT_MODULES is empty: nothing to guard"
    for name, path in INERT.items():
        assert path.is_file(), f"{name}: listed as recipe-inert but missing"


def test_rule1_inert_modules_are_in_no_recipe():
    local = bg._local_modules()
    offenders = [name for name in INERT if name in local]
    assert not offenders, f"recipe-inert modules still in _local_modules: {offenders}"
    scripts = [
        *SCRIPTS.glob("build_*.py"),
        *SCRIPTS.glob("draw_*.py"),
        SCRIPTS / "package_native.py",
    ]
    leaks = sorted(
        f"{script.name} -> {Path(dep).name}"
        for script in scripts
        for dep in bg.module_deps_of(script)
        if Path(dep).resolve() in {path.resolve() for path in INERT.values()}
    )
    assert not leaks, f"a recipe folds a recipe-inert module: {leaks}"


def _call_site_violations(path: Path, rel: str) -> list[str]:
    tree = _tree(path)
    owners = _top_level_of(tree)
    statement_calls = {
        id(node.value.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    }
    attribute_values = {
        id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    violations: list[str] = []
    for node in ast.walk(tree):
        where = f"{rel}:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.ImportFrom) and node.module in INERT:
            violations.append(f"{where}: from-import of {node.module} (use the module)")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in INERT and alias.asname is not None:
                    violations.append(f"{where}: {alias.name} imported under an alias")
        elif isinstance(node, ast.Constant) and node.value in INERT:
            violations.append(f"{where}: string reference to {node.value}")
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in INERT
        ):
            owner = owners.get(id(node), "<module>")
            if node.attr in CALL_SITES.get((rel, owner), frozenset()):
                continue
            if node.attr in TERMINAL and id(node) in statement_calls:
                continue
            violations.append(
                f"{where}: {node.value.id}.{node.attr} in {owner}() is not a pinned "
                "call site (add it to CALL_SITES only if it runs after the save "
                "or reads nothing into the model)"
            )
        elif isinstance(node, ast.Name) and node.id in INERT and id(node) not in attribute_values:
            violations.append(f"{where}: {node.id} passed around as a value")
    return violations


def test_rule2_tracked_code_reaches_inert_modules_only_at_pinned_sites():
    violations = [
        violation
        for path in _tracked_sources()
        for violation in _call_site_violations(path, path.relative_to(SCRIPTS).as_posix())
    ]
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("name", sorted(INERT))
def test_rule3_inert_module_runs_no_com_mutator_before_a_save(name):
    tree = _tree(INERT[name])
    owners = _top_level_of(tree)
    violations: list[str] = []
    holders: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        where = f"{name}.py:{getattr(node, 'lineno', '?')}"
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and MUTATOR.match(node.func.attr)
        ):
            owner = owners.get(id(node), "<module>")
            if (owner, node.func.attr) not in PINNED_MUTATORS:
                violations.append(f"{where}: {owner}() calls COM mutator {node.func.attr}")
            holders.setdefault(owner, set()).add(node.func.attr)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            if node.attr not in LOCAL_ATTRIBUTE_STORES:
                violations.append(f"{where}: stores .{node.attr} on another object")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
            "setattr",
            "exec",
            "eval",
        }:
            violations.append(f"{where}: {node.func.id}() defeats the static check")

    functions = _functions(tree)
    for holder, roots in MUTATOR_ROOTS.items():
        if holder not in functions:
            continue
        callers = {
            other
            for other, function in functions.items()
            if other != holder and holder in _referenced(function, {holder})
        }
        stray = callers - roots
        if stray:
            violations.append(f"{holder} (a pinned mutator) is reached from {sorted(stray)}")
    capture = functions.get("capture_com_failure")
    if capture is not None:
        returns = ast.unparse(capture.returns) if capture.returns is not None else ""
        if returns != "NoReturn" or not isinstance(capture.body[-1], ast.Raise):
            violations.append("capture_com_failure must be NoReturn and end in raise")
    for entry in PRE_SAVE & set(functions):
        reached = _reachable(tree, {entry}) & set(MUTATOR_ROOTS)
        if reached:
            violations.append(f"pre-save {entry}() reaches mutators {sorted(reached)}")
        writers = sorted(
            f"{fn}:{verb}"
            for fn in _reachable(tree, {entry})
            for verb in holders.get(fn, set())
            if fn != "_process_handle"
        )
        if writers:
            violations.append(f"pre-save {entry}() reaches COM writes {writers}")
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("name", sorted(INERT))
def test_rule4_inert_module_reads_tracked_code_only_through_pinned_names(name):
    tree = _tree(INERT[name])
    local = set(bg._local_modules()) | set(INERT)
    violations: list[str] = []
    imported: set[str] = set()
    for node in ast.walk(tree):
        where = f"{name}.py:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.split(".")[0] in local or node.module in READS:
                violations.append(f"{where}: from-import of local module {node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in local or root in READS:
                    if alias.name not in READS or alias.asname is not None:
                        violations.append(f"{where}: imports local module {alias.name}")
                    imported.add(alias.name)
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in READS
            and node.value.id not in OPEN_READS
            and node.attr not in READS[node.value.id]
        ):
            violations.append(
                f"{where}: reads {node.value.id}.{node.attr}, not a pinned name"
            )
    assert not violations, "\n".join(violations)
    assert imported <= set(READS), imported


def test_the_rules_catch_what_they_claim(tmp_path, monkeypatch):
    """Negative controls: each rule fails on a module that breaks it."""
    fake = tmp_path / "_fake_inert.py"
    fake.write_text(
        "import _common\n"
        "def stamp(model):\n"
        "    model.Extension.CustomPropertyManager('').Add3('Generator', 30, 'x', 2)\n"
        "def resize(dimension):\n"
        "    dimension.SystemValue = 0.002\n"
        "def peek(adapter):\n"
        "    return _common.save_part_and_images\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(INERT, "_fake_inert", fake)
    with pytest.raises(AssertionError, match="Add3"):
        test_rule3_inert_module_runs_no_com_mutator_before_a_save("_fake_inert")
    with pytest.raises(AssertionError, match="SystemValue"):
        test_rule3_inert_module_runs_no_com_mutator_before_a_save("_fake_inert")
    with pytest.raises(AssertionError, match="save_part_and_images"):
        test_rule4_inert_module_reads_tracked_code_only_through_pinned_names("_fake_inert")


def test_rule2_rejects_a_geometry_path_call(tmp_path):
    tracked = tmp_path / "build_fake.py"
    tracked.write_text(
        "import _seat_forensics\n"
        "def extrude(adapter):\n"
        "    _seat_forensics.display_geometry(adapter)\n"
        "    return _seat_forensics.capture_com_failure(adapter, 'x', 'y')\n"
        "def fail(adapter):\n"
        "    _seat_forensics.capture_com_failure(adapter, 'x', 'y')\n",
        encoding="utf-8",
    )
    violations = _call_site_violations(tracked, "build_fake.py")
    assert [v.split(": ", 1)[1].split(" in ")[0] for v in violations] == [
        "_seat_forensics.display_geometry",
        "_seat_forensics.capture_com_failure",
    ], violations
