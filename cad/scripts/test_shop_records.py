"""Shop TOML records are cache-key inputs of exactly their consumers (#2852).

``_shop_records.shop_record`` is the only way a build closure reads
``cad/config/shop-equipment.toml`` or ``cad/process/shop.toml``; dodo folds a
digest of the records each COM leaf's closure names, and the subprocess guard
refuses any other record.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

import _shop_records
from _shop_records import shop_record

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[1]
GAUGE_HEADER = "[gauges.gauge-blocks-mitutoyo]\n"
# COM leaves around the jig; part:dt_cone_gear reads no shop record.
_LEAVES = {
    "part:ch_rocker_arm_tl_oblique_base_bar": lambda d: d._part_file_deps(
        d.SCRIPTS_DIR / "build_ch_rocker_arm_tl_oblique_base_bar.py",
        "ch_rocker_arm_tl_oblique_base_bar",
    ),
    "part:ch_rocker_arm_tl_oblique_end_bracket": lambda d: d._part_file_deps(
        d.SCRIPTS_DIR / "build_ch_rocker_arm_tl_oblique_end_bracket.py",
        "ch_rocker_arm_tl_oblique_end_bracket",
    ),
    "drawing:ch_rocker_arm_tl_oblique_base_bar": lambda d: d._drawing_file_deps(
        "ch_rocker_arm_tl_oblique_base_bar"
    ),
    "assembly:ch_rocker_arm_tl_oblique_jig": lambda d: d._recipe_files(
        "ch_rocker_arm_tl_oblique_jig"
    ),
    "drawing:ch_rocker_arm_tl_oblique_jig_assembly": lambda d: d._drawing_file_deps(
        "ch_rocker_arm_tl_oblique_jig_assembly"
    ),
    "verify_soundness:ch_rocker_arm_tl_oblique_jig": lambda d: d._soundness_file_deps(
        "ch_rocker_arm_tl_oblique_jig"
    ),
    "package:features:ch_rocker_arm_tl_oblique_base_bar": lambda d: (
        d._feature_export_file_deps("ch_rocker_arm_tl_oblique_base_bar")
    ),
    "part:dt_cone_gear": lambda d: d._part_file_deps(
        d.SCRIPTS_DIR / "build_dt_cone_gear.py", "dt_cone_gear"
    ),
}
_BASE_BAR_CONSUMERS = set(_LEAVES) - {"part:dt_cone_gear"}
_JIG_CONSUMERS = {
    "assembly:ch_rocker_arm_tl_oblique_jig",
    "drawing:ch_rocker_arm_tl_oblique_jig_assembly",
    "verify_soundness:ch_rocker_arm_tl_oblique_jig",
}


@pytest.fixture(scope="module")
def dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def shop_copy(tmp_path, monkeypatch):
    """Temporary copies of both shop files that every reader (and dodo) uses."""
    copies = {}
    for name, path in _shop_records.SHOP_FILES.items():
        copy = tmp_path / name
        copy.write_bytes(path.read_bytes())
        monkeypatch.setitem(_shop_records.SHOP_FILES, name, copy)
        copies[name] = copy
    _shop_records._document.cache_clear()
    yield copies
    _shop_records._document.cache_clear()


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), encoding="utf-8")
    _shop_records._document.cache_clear()


def _keys(dodo) -> dict[str, str]:
    return {
        label: dodo._cache.key_inputs(deps(dodo), dodo.ContentChecker._digest, salt="")[0]
        for label, deps in _LEAVES.items()
    }


def _moved(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {label for label in before if before[label] != after[label]}


def test_a_record_edit_rekeys_exactly_its_consumers(dodo, shop_copy, tmp_path, monkeypatch):
    monkeypatch.setattr(dodo, "CAD_OUT", tmp_path / "out")
    equipment = shop_copy["shop-equipment.toml"]
    base = _keys(dodo)
    _edit(equipment, "repeatability_mm = 0.02\n", "repeatability_mm = 0.03\n")
    cnc = _keys(dodo)
    assert _moved(base, cnc) == _BASE_BAR_CONSUMERS
    _edit(equipment, GAUGE_HEADER, GAUGE_HEADER + 'probe = "edited"\n')
    gauges = _keys(dodo)
    assert _moved(cnc, gauges) == _JIG_CONSUMERS
    _edit(shop_copy["shop.toml"], "[machines.pm-30mv]\n", "[machines.pm-30mv]\nprobe = 1\n")
    assert _moved(gauges, _keys(dodo)) == _JIG_CONSUMERS


def test_unrelated_records_and_new_tables_rekey_nothing(dodo, shop_copy, tmp_path, monkeypatch):
    monkeypatch.setattr(dodo, "CAD_OUT", tmp_path / "out")
    equipment = shop_copy["shop-equipment.toml"]
    base = _keys(dodo)
    _edit(equipment, "[gauges.surface-plate]\n", '[gauges.surface-plate]\nprobe = "x"\n')
    with equipment.open("a", encoding="utf-8") as handle:
        handle.write('\n# a comment\n[tools.probe-new-table]\nkind = "probe"\n')
    with shop_copy["shop.toml"].open("a", encoding="utf-8") as handle:
        handle.write('\n[probe-new-family.probe]\nkind = "probe"\n')
    _shop_records._document.cache_clear()
    assert _moved(base, _keys(dodo)) == set()


def test_the_guard_carries_the_folded_records(dodo):
    guard = json.loads(dodo._shop_records_env("part:ch_rocker_arm_tl_oblique_base_bar"))
    assert guard == {
        "files": [],
        "records": [
            ["shop-equipment.toml", "cnc", "pm-30mv"],
            ["shop-equipment.toml", "tools", "spring-tap-guide"],
        ],
    }
    assert json.loads(dodo._shop_records_env("part:dt_cone_gear")) == {
        "files": [], "records": [],
    }
    assert dodo._shop_records_env("check:math") is None
    assert dodo._shop_records_env("verify:kinematics") is None
    assert dodo._shop_records_env("package:features") is None
    for label in ("part:no_such_part", "verify_soundness:no_such_assembly", "FULL build x", ""):
        with pytest.raises(ValueError):
            dodo._shop_records_env(label)


def test_a_read_outside_the_key_fails_the_build(dodo, monkeypatch):
    seen = {}

    def fake_run(cmd, cwd, env):
        seen.update(env)
        with monkeypatch.context() as child:
            child.setenv(_shop_records.ENV, env[_shop_records.ENV])
            shop_record("shop-equipment.toml", "cnc", "pm-30mv")
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setenv(_shop_records.ENV, "inherited-must-not-leak")
    monkeypatch.setattr(dodo.subprocess, "run", fake_run)
    assert dodo._run_subprocess(["x"], "part:ch_rocker_arm_tl_oblique_end_bracket") == 0
    with pytest.raises(KeyError, match="is outside this build"):
        dodo._run_subprocess(["x"], "part:dt_cone_gear")
    seen.clear()

    def record_env(cmd, cwd, env):
        seen.update(env)
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setattr(dodo.subprocess, "run", record_env)
    assert dodo._run_subprocess(["x"], "check:math") == 0
    assert _shop_records.ENV not in seen


def test_the_accessor_enforces_the_guard(monkeypatch):
    monkeypatch.delenv(_shop_records.ENV, raising=False)
    record = shop_record("shop.toml", "gauges", "dti")
    record["resolution_mm"] = -1
    assert shop_record("shop.toml", "gauges", "dti")["resolution_mm"] != -1
    monkeypatch.setenv(
        _shop_records.ENV,
        _shop_records.guard_value(
            frozenset({("shop-equipment.toml", "cnc", "pm-30mv")}), frozenset({"shop.toml"})
        ),
    )
    assert shop_record("shop-equipment.toml", "cnc", "pm-30mv")["repeatability_mm"] > 0
    assert shop_record("shop.toml", "gauges", "dti")
    with pytest.raises(KeyError, match="is outside this build"):
        shop_record("shop-equipment.toml", "tools", "spring-tap-guide")
    monkeypatch.delenv(_shop_records.ENV)
    with pytest.raises(KeyError, match="is not in"):
        shop_record("shop.toml", "gauges", "no-such-gauge")
    with pytest.raises(KeyError, match="unknown shop file"):
        shop_record("inventory.toml", "gauges", "dti")


def test_an_absent_selected_record_is_keyed_as_absent(shop_copy):
    record = frozenset({("shop-equipment.toml", "tools", "probe-later")})
    before = _shop_records.records_recipe(record)
    with shop_copy["shop-equipment.toml"].open("a", encoding="utf-8") as handle:
        handle.write('\n[tools.probe-later]\nkind = "probe"\n')
    _shop_records._document.cache_clear()
    assert _shop_records.records_recipe(record) != before


# The modules allowed to name the shop files directly: the accessor itself and
# two readers outside every COM leaf (release staging and the uncached
# prechips/CAM plans).
_DIRECT_READERS = {"_shop_records.py", "ha_assembly_package.py", "_process_plans.py"}
_SHOP_FILE_NAMES = ("shop.toml", "shop-equipment.toml")


def _names_a_shop_file(text: str) -> bool:
    """Whether any string in ``text`` names a shop file, other than a docstring
    or the file argument of a ``shop_record(...)`` call (comments are not in
    the AST)."""
    tree = ast.parse(text)
    exempt = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    } | {
        id(node.args[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "shop_record"
        and node.args
    }
    return any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in exempt
        and any(name in node.value for name in _SHOP_FILE_NAMES)
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize(
    ("source", "direct"),
    [
        ('X = tomllib.loads((CAD_ROOT / "process" / "shop.toml").read_text())\n', True),
        ('P = ROOT / f"config/shop-equipment.toml"\n', True),
        ('X = shop_record("shop.toml", "gauges", "dti")\n', False),
        ('"""Reads shop.toml."""\n# shop-equipment.toml\nX = 1\n', False),
    ],
    ids=["read-text", "f-string", "accessor", "docstring-and-comment"],
)
def test_the_direct_read_scan_is_ast_based(source, direct):
    assert _names_a_shop_file(source) is direct


def test_no_module_reads_the_shop_files_directly():
    """A new direct read would be an input no cache key sees: read through
    ``shop_record`` instead."""
    offenders = sorted(
        str(path.relative_to(SCRIPTS))
        for path in (*SCRIPTS.glob("*.py"), *SCRIPTS.glob("diagnostics/*.py"))
        if not path.name.startswith("test_")
        and path.name not in _DIRECT_READERS
        and _names_a_shop_file(path.read_text(encoding="utf-8"))
    )
    assert offenders == []
    assert _names_a_shop_file((SCRIPTS / "_process_plans.py").read_text(encoding="utf-8"))


def test_direct_readers_stay_outside_every_com_leaf(dodo):
    """The exempt readers may never join a part, assembly, drawing, soundness
    gate or feature export closure."""
    exempt = {
        str((SCRIPTS / name).resolve()) for name in _DIRECT_READERS - {"_shop_records.py"}
    }
    roots = [
        *dodo.part_scripts(),
        *(dodo.script_for(stem) for stem in dodo.ASSEMBLY_ORDER),
        *(dodo._resolved(spec.script) for spec in dodo.DRAWINGS_BY_NAME.values()),
        dodo.VERIFY_PY,
        SCRIPTS / "export_features.py",
    ]
    reached = {
        str(root): sorted(exempt & {str(Path(dep).resolve()) for dep in dodo.module_deps_of(Path(root))})
        for root in roots
    }
    assert {root: hits for root, hits in reached.items() if hits} == {}
