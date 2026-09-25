r"""Per-assembly contracts stay per-assembly (no SolidWorks required).

Flip seeds and free-DOF sets used to be module-level tables in ``_assembly.py``;
every assembly's recipe carries that module, so one drive-train seed re-keyed all
eight assemblies. They now live in ``cad/config/assemblies/<stem>.yaml`` and
dodo narrows each assembly task to its OWN file. These tests keep it that way:

* no module-level dict/set keyed by assembly stems creeps back into the shared
  modules;
* each assembly recipe (and soundness gate) carries its own contract and no
  sibling's;
* each build activates exactly its own contract, so the file its seeds come
  from is the file its recipe depends on;
* the contract files cover ``ASSEMBLY_ORDER`` exactly and parse;
* the seed audit records, warns and refuses as documented.

    uv run pytest cad/scripts/test_assembly_contract.py
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _assembly  # noqa: E402
import _assembly_contract  # noqa: E402
from _buildgraph import ASSEMBLY_ORDER, SCRIPTS_DIR, config_files_of, script_for  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHED = tuple(stem.replace("_", "-") for stem in ASSEMBLY_ORDER)
STEM_NAMES = frozenset(ASSEMBLY_ORDER) | frozenset(DASHED)
# Shared modules on every assembly's (or every soundness gate's) recipe: a
# per-assembly table here re-keys the whole fleet of assemblies on each edit.
SHARED_MODULES = ("_assembly.py",)


@pytest.fixture(scope="module")
def dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stem_keyed_tables(path: Path) -> list[str]:
    """Module-level dict/set literals whose keys or elements name assemblies."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        for inner in ast.walk(value):
            if isinstance(inner, ast.Dict):
                members = inner.keys
            elif isinstance(inner, ast.Set):
                members = inner.elts
            else:
                continue
            if any(
                isinstance(m, ast.Constant) and m.value in STEM_NAMES for m in members
            ):
                found.append(ast.unparse(targets[0]))
                break
    return found


@pytest.mark.parametrize("module", SHARED_MODULES)
def test_shared_module_holds_no_per_assembly_table(module):
    tables = _stem_keyed_tables(SCRIPTS_DIR / module)
    assert not tables, (
        f"{module} holds per-assembly table(s) {tables}: move the data to "
        "cad/config/assemblies/<stem>.yaml (see _assembly_contract) so an edit "
        "re-keys only that assembly"
    )


def test_stem_keyed_table_detector_sees_a_table(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(
        'X: dict[str, int] = {"drive-train": 1}\nY = frozenset({"channel"})\n',
        encoding="utf-8",
    )
    assert _stem_keyed_tables(probe) == ["X", "Y"]


def test_contract_files_cover_assembly_order_exactly():
    files = {p.stem for p in _assembly_contract.contract_files()}
    assert files == set(DASHED)
    for stem in DASHED:
        contract = _assembly_contract.assembly_contract(stem)
        assert contract.stem == stem


def test_missing_contract_raises():
    with pytest.raises(FileNotFoundError, match="assembly contract missing"):
        _assembly_contract.assembly_contract("no-such-assembly")


def test_contract_schema_rejects_unknown_and_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(_assembly_contract, "CONTRACT_DIR", tmp_path)
    _assembly_contract.assembly_contract.cache_clear()
    try:
        (tmp_path / "bad-key.yaml").write_text(
            "flip_invert: []\nallowed_free_stems: []\nflip_seeds: []\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unknown keys"):
            _assembly_contract.assembly_contract("bad-key")
        (tmp_path / "dupe.yaml").write_text(
            "flip_invert: [a, a]\nallowed_free_stems: []\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="more than once"):
            _assembly_contract.assembly_contract("dupe")
    finally:
        _assembly_contract.assembly_contract.cache_clear()


@pytest.mark.parametrize("stem", ASSEMBLY_ORDER)
def test_assembly_closure_reads_the_contract_family(stem):
    assert "assemblies/*" in config_files_of(script_for(stem))


@pytest.mark.parametrize("stem", ASSEMBLY_ORDER)
def test_assembly_recipe_carries_only_its_own_contract(dodo, stem):
    own = _assembly_contract.contract_path(stem.replace("_", "-")).resolve()
    contract_dir = _assembly_contract.CONTRACT_DIR.resolve()
    for label, deps in (
        (f"assembly:{stem}", dodo._assembly_file_deps(stem)),
        (f"verify_soundness:{stem}", dodo._soundness_file_deps(stem)),
    ):
        contracts = {Path(d).resolve() for d in deps if Path(d).parent == contract_dir}
        assert contracts == {own}, f"{label}: contract deps {sorted(contracts)}"


def test_parts_never_carry_a_contract(dodo):
    contract_dir = _assembly_contract.CONTRACT_DIR.resolve()
    for script in dodo.part_scripts():
        stem = script.stem.removeprefix("build_")
        deps = dodo._part_file_deps(script, stem)
        assert not [d for d in deps if Path(d).parent == contract_dir], stem


def _build_activation(script: Path) -> tuple[str | None, str | None]:
    """(module-level ASM_NAME literal, name passed to the first statement of
    ``build()`` if it is ``activate_assembly_contract(<name>)``)."""
    tree = ast.parse(script.read_text(encoding="utf-8"))
    asm_name = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and [ast.unparse(t) for t in node.targets] == ["ASM_NAME"]
            and isinstance(node.value, ast.Constant)
        ):
            asm_name = node.value.value
    build = next(
        n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "build"
    )
    first = build.body[0]
    call = first.value if isinstance(first, ast.Expr) else None
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "activate_assembly_contract"
        and len(call.args) == 1
    ):
        return asm_name, None
    arg = call.args[0]
    if isinstance(arg, ast.Constant):
        return asm_name, arg.value
    if isinstance(arg, ast.Name) and arg.id == "ASM_NAME":
        return asm_name, asm_name
    return asm_name, None


@pytest.mark.parametrize("stem", ASSEMBLY_ORDER)
def test_build_activates_its_own_contract_first(stem):
    asm_name, activated = _build_activation(script_for(stem))
    dashed = stem.replace("_", "-")
    assert asm_name == dashed
    assert activated == dashed, (
        f"build_{stem}_assembly.build() must open with "
        f"activate_assembly_contract(ASM_NAME) -- dodo depends the task on "
        f"{dashed}.yaml only"
    )


@pytest.fixture
def fresh_seed_state(monkeypatch):
    monkeypatch.setattr(_assembly, "_ACTIVE_CONTRACT", None)
    monkeypatch.setattr(_assembly, "_SEED_QUERIES", {})


def test_seed_flip_refuses_without_an_active_contract(fresh_seed_state):
    with pytest.raises(RuntimeError, match="no active assembly contract"):
        _assembly._seed_flip("lift rod axial d=1.00", 1.0)


def test_seed_flip_reads_only_the_active_assembly(fresh_seed_state):
    _assembly.activate_assembly_contract("drive-train")
    assert _assembly._seed_flip("lift rod axial d=12.00", 12.0)
    assert not _assembly._seed_flip("lift rod axial d=12.00", -12.0)
    _assembly.activate_assembly_contract("channel")
    assert not _assembly._seed_flip("lift rod axial d=12.00", 12.0)


def test_seed_audit_logs_queries_and_warns_on_dead_entries(
    fresh_seed_state, monkeypatch
):
    events: list[tuple[str, dict]] = []
    warnings: list[str] = []
    monkeypatch.setattr(
        _assembly._telemetry, "event", lambda name, **kw: events.append((name, kw))
    )
    monkeypatch.setattr(_assembly._telemetry, "warn", warnings.append)
    contract = _assembly.activate_assembly_contract("summing")
    _assembly._seed_flip("summing-lever axial d=3.00", 3.0)
    _assembly._seed_flip("summing-lever radial d=3.00", 3.0)
    _assembly.audit_flip_seeds("summing")
    audit = dict(events)["flip_seeds.audit"]
    assert audit["queried"] == ["summing lever axial", "summing lever radial"]
    assert audit["inverted"] == ["summing lever axial"]
    assert audit["dead"] == []
    assert not warnings

    monkeypatch.setattr(
        _assembly,
        "_ACTIVE_CONTRACT",
        type(contract)(
            stem=contract.stem,
            path=contract.path,
            flip_invert=contract.flip_invert | {"never queried seat"},
            allowed_free_stems=contract.allowed_free_stems,
        ),
    )
    _assembly.audit_flip_seeds("summing")
    assert dict(events)["flip_seeds.dead"]["dead"] == ["never queried seat"]
    assert warnings and "summing.yaml" in warnings[-1]


def test_seed_audit_refuses_a_foreign_contract(fresh_seed_state):
    _assembly.activate_assembly_contract("pen")
    with pytest.raises(RuntimeError, match="activate_assembly_contract"):
        _assembly.audit_flip_seeds("magnifier")


def test_activation_resets_the_audit(fresh_seed_state):
    _assembly.activate_assembly_contract("pen")
    _assembly._seed_flip("hanger screw head plane d=1.00", 1.0)
    _assembly.activate_assembly_contract("pen")
    assert _assembly._SEED_QUERIES == {}


def test_allowed_free_stems_come_from_the_contract():
    for stem in DASHED:
        assert _assembly.allowed_free_stems(stem) == (
            _assembly_contract.assembly_contract(stem).allowed_free_stems
        )
    assert _assembly.allowed_free_stems("frame") == ()
    assert "pinion-lever" in _assembly.allowed_free_stems("drive-train")
