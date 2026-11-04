"""Each assembly's allowed-interference table re-keys only that assembly.

Every assembly owns ``_<stem>_interference.py`` (``_buildgraph.interference_module``),
its builder imports it statically, and verify.py/refresh_assembly.py resolve
their own stem's table by name.  These tests pin the graph consequences: an
edit to one table re-keys only its assembly, the assemblies that contain it,
their assembly drawings and their soundness gates -- never a sibling, a part,
a part drawing or the shared ``_assembly.py`` helper.
"""

from __future__ import annotations

import ast
import functools
import importlib
import importlib.util
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

from _buildgraph import (
    ASSEMBLY_ORDER,
    SCRIPTS_DIR,
    interference_contract_file,
    interference_module,
    module_deps_of,
    part_scripts,
    references_of,
    script_for,
)
from _drawing_registry import DRAWINGS

REPO_ROOT = SCRIPTS_DIR.parents[1]
TABLES = {stem: interference_contract_file(stem) for stem in ASSEMBLY_ORDER}
OWNER = {path: stem for stem, path in TABLES.items()}


@functools.cache
def _closure(script: Path) -> frozenset[str]:
    return frozenset(module_deps_of(script))


def _tables_reached(script: Path) -> set[str]:
    """The assembly stems whose table ``script``'s recipe closure folds in."""
    return {OWNER[path] for path in _closure(script) & OWNER.keys()}


@functools.cache
def _containers(stem: str) -> frozenset[str]:
    """``stem`` plus every assembly that references it, however indirectly."""
    found = {stem}
    changed = True
    while changed:
        changed = False
        for parent in ASSEMBLY_ORDER:
            if parent not in found and found & set(references_of(parent)):
                found.add(parent)
                changed = True
    return frozenset(found)


@functools.cache
def _dodo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("stem", ASSEMBLY_ORDER)
def test_each_assembly_has_its_own_table(stem: str) -> None:
    path = Path(interference_contract_file(stem))
    assert path.is_file(), path
    assert interference_module(stem) == interference_module(stem.replace("_", "-"))
    assert interference_contract_file(stem.replace("_", "-")) == str(path)
    table = importlib.import_module(interference_module(stem)).ALLOWED_PAIRS
    assert isinstance(table, Mapping)
    for pair, limit in table.items():
        assert isinstance(pair, frozenset) and len(pair) == 2, pair
        assert isinstance(limit, float) and limit >= 0.0, (pair, limit)


@pytest.mark.parametrize("stem", ASSEMBLY_ORDER)
def test_a_table_rekeys_only_its_assembly_and_containers(stem: str) -> None:
    holders = {
        other for other in ASSEMBLY_ORDER if stem in _tables_reached(script_for(other))
    }
    assert holders <= _containers(stem), (stem, holders - _containers(stem))
    # The builder gates with its own table exactly when it has pairs to allow.
    table = importlib.import_module(interference_module(stem)).ALLOWED_PAIRS
    assert (stem in holders) == bool(table), stem


def test_no_part_or_shared_helper_reaches_a_table() -> None:
    assert not _tables_reached(SCRIPTS_DIR / "_assembly.py")
    for script in part_scripts():
        assert not _tables_reached(script), script.name
    builders = {str(script_for(stem).resolve()) for stem in ASSEMBLY_ORDER}
    helpers = set().union(*(_closure(script_for(stem)) for stem in ASSEMBLY_ORDER))
    for helper in sorted(helpers - builders - OWNER.keys()):
        assert not _tables_reached(Path(helper)), helper


def test_only_containing_assembly_drawings_reach_a_table() -> None:
    for drawing in DRAWINGS:
        reached = _tables_reached(SCRIPTS_DIR / drawing.script_name)
        if not reached:
            continue
        assert drawing.source_kind == "assembly", drawing.name
        for stem in reached:
            assert drawing.part in _containers(stem), (drawing.name, stem)


def test_unrelated_tables_share_no_interference_only_module() -> None:
    # Unrelated tables may share only the pure helpers module and general
    # specs/helpers some part also builds from; a module only tables import
    # is a re-centralised table that re-keys every assembly importing it.
    common = str((SCRIPTS_DIR / "_interference_common.py").resolve())
    part_modules = {str(script.resolve()) for script in part_scripts()}
    part_modules |= set().union(*(_closure(script) for script in part_scripts()))
    for first in ASSEMBLY_ORDER:
        for second in ASSEMBLY_ORDER:
            if first >= second or {first, second} & (
                _containers(first) & _containers(second)
            ):
                continue
            shared = _closure(Path(TABLES[first])) & _closure(Path(TABLES[second]))
            assert shared - {common} <= part_modules, (first, second)


@pytest.mark.parametrize("stem", ASSEMBLY_ORDER)
def test_soundness_folds_only_own_and_contained_tables(stem: str) -> None:
    deps = set(_dodo()._soundness_file_deps(stem))
    assert TABLES[stem] in deps
    for table_stem, path in TABLES.items():
        if path in deps:
            assert stem in _containers(table_stem), (stem, table_stem)
    # The table's own imports ride the gate too (verify.py resolves it by name).
    assert _closure(Path(TABLES[stem])) <= deps


@pytest.mark.parametrize("stem", ASSEMBLY_ORDER)
def test_runtime_resolution_is_the_builder_table(stem: str) -> None:
    # Importing the builders costs seconds each (COM stacks), so read which
    # module each binds ALLOWED_PAIRS from; Python's module cache then makes
    # verify/refresh's importlib lookup the very object the builder gates with.
    tree = ast.parse(script_for(stem).read_text(encoding="utf-8"))
    sources = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "ALLOWED_PAIRS" for alias in node.names)
    }
    resolved = importlib.import_module(interference_module(stem))
    if sources:
        assert sources == {interference_module(stem)}, (stem, sources)
        assert importlib.import_module(sources.pop()) is resolved
    else:
        # A builder without a table gates nothing at build: nothing to allow.
        assert resolved.ALLOWED_PAIRS == {}
