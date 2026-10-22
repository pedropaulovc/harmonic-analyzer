"""Real recipe/cache and guard coverage for the rocker outline boundary.

Mutations touch copied inputs only. The shared fixture redirects all native
outputs and adapter sidecars before enumerating production part/assembly tasks;
no SolidWorks session, farm activity or checkout configuration is modified.
"""

from __future__ import annotations

from pathlib import Path
import sys
from types import ModuleType

import pytest

import _buildgraph as bg
from test_dodo_recipe import (  # noqa: F401 -- pytest discovers imported fixtures
    isolated_assembly_helper_keys,
    local_executor,
)

pytestmark = pytest.mark.usefixtures("local_executor")

SCRIPTS = Path(__file__).resolve().parent
# Only active native leaves belong here. The retired strap shim stack and
# outline template have no production part/cache keys.
OUTLINE_ONLY_PARTS = {"ch_rocker_arm_tl_oblique_carrier"}
MIXED_PARTS = {
    "ch_rocker_arm",
    "ch_rocker_strap",
    "ch_rocker_arm_tl_oblique_hub_pin",
}


def _closure(script: str) -> set[str]:
    bg.clear_import_caches()
    dependencies = bg.module_deps_of(SCRIPTS / script)
    assert dependencies, f"{script}: closure discovery must match real imports"
    return {Path(path).stem for path in dependencies}


@pytest.mark.parametrize(
    "script",
    [
        "ch_rocker_arm_tl_oblique_trammel_spec.py",
        *(f"build_{stem}.py" for stem in sorted(OUTLINE_ONLY_PARTS)),
    ],
)
def test_outline_tooling_does_not_import_guarded_hub_implementation(script):
    closure = _closure(script)
    assert "ch_rocker_arm_outline_spec" in closure
    assert "ch_rocker_arm_spec" not in closure


@pytest.mark.parametrize("stem", sorted(MIXED_PARTS))
def test_parts_that_use_fits_keep_the_guarded_owner(stem):
    assert {"ch_rocker_arm_spec", "ch_rocker_arm_outline_spec"} <= _closure(
        f"build_{stem}.py"
    )


def test_outline_owner_has_no_reverse_hub_dependency():
    closure = _closure("ch_rocker_arm_outline_spec.py")
    assert "_rocker_interface" in closure
    assert "ch_rocker_arm_spec" not in closure


def _part_dependencies(dodo):
    tasks = {task["name"]: task for task in dodo.task_part()}
    assert OUTLINE_ONLY_PARTS | MIXED_PARTS <= tasks.keys()
    return {stem: task["file_dep"] for stem, task in tasks.items()}


def _mutate(path: Path, old: bytes, new: bytes) -> bytes:
    original = path.read_bytes()
    assert original.count(old) == 1, f"{path.name}: mutation must match exactly once"
    path.write_bytes(original.replace(old, new))
    return original


def _changed(before, after, group):
    return {stem for stem in before[group] if before[group][stem] != after[group][stem]}


@pytest.mark.parametrize(
    ("member", "old", "new"),
    [
        (
            "ch_rocker_arm_spec",
            b"HUB_DIA = 10.2",
            b"HUB_DIA = 10.21",
        ),
        (
            "ch_rocker_arm_outline_spec",
            b"TOP_ARC_LEN = 292.1",
            b"TOP_ARC_LEN = 292.2",
        ),
    ],
)
def test_actual_part_recipe_and_cache_keys_respect_outline_boundary(
    isolated_assembly_helper_keys, member, old, new
):
    dodo, root, snapshot = isolated_assembly_helper_keys
    dependencies = _part_dependencies(dodo)
    scripts = root / "cad" / "scripts"
    hub = str((scripts / "ch_rocker_arm_spec.py").resolve())
    outline = str((scripts / "ch_rocker_arm_outline_spec.py").resolve())
    hub_readers = {stem for stem, paths in dependencies.items() if hub in paths}
    outline_readers = {stem for stem, paths in dependencies.items() if outline in paths}
    assert MIXED_PARTS <= hub_readers & outline_readers
    assert OUTLINE_ONLY_PARTS <= outline_readers - hub_readers
    assert all(
        Path(path).resolve().is_relative_to(root.resolve())
        for paths in dependencies.values()
        for path in paths
    )
    expected = hub_readers if member == "ch_rocker_arm_spec" else outline_readers
    before = snapshot()
    path = scripts / f"{member}.py"
    original = _mutate(path, old, new)
    try:
        after = snapshot()
    finally:
        path.write_bytes(original)
    assert _changed(before, after, "part_recipes") == expected
    assert _changed(before, after, "parts") == expected


def test_outline_split_preserves_printed_configuration_in_actual_keys(
    isolated_assembly_helper_keys,
):
    dodo, root, snapshot = isolated_assembly_helper_keys
    dependencies = _part_dependencies(dodo)
    title_block = root / "cad" / "config" / "title_block.yaml"
    expected = {
        stem for stem, paths in dependencies.items() if str(title_block) in paths
    }
    assert OUTLINE_ONLY_PARTS | MIXED_PARTS <= expected
    for stem in OUTLINE_ONLY_PARTS | MIXED_PARTS:
        assert dependencies[stem].count(str(title_block)) == 1, stem
    before = snapshot()
    original = _mutate(
        title_block,
        'linear_1pl: { value_in: 0.03,  display: "±0.8" }'.encode(),
        'linear_1pl: { value_in: 0.03,  display: "±0.9" }'.encode(),
    )
    try:
        after = snapshot()
    finally:
        title_block.write_bytes(original)
    assert _changed(before, after, "part_recipes") == expected
    assert _changed(before, after, "parts") == expected


def _load_copy(root: Path, name: str, monkeypatch):
    path = root / "cad" / "scripts" / f"{name}.py"
    module = ModuleType(name)
    module.__file__ = str(path)
    monkeypatch.setitem(sys.modules, name, module)
    # Compile current copied bytes; same-second mutations must not hit stale pyc.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            b"HUB_DIA = 10.2",
            b"HUB_DIA = 9.0",
            "under its .* wall floor",
        ),
        (
            b'"strap position to hub": "0.10"',
            b'"strap position to hub": "0.11"',
            "strap position zone must print STRAP_HUB_SYMMETRY",
        ),
        (
            b'"hub OD position to bore": "0.10"',
            b'"hub OD position to bore": "0.11"',
            "hub OD position zone must print HUB_COAXIALITY_DIA",
        ),
    ],
)
def test_retained_hub_and_gdt_guards_still_reject_invalid_data(
    isolated_assembly_helper_keys, monkeypatch, old, new, message
):
    _dodo, root, _snapshot = isolated_assembly_helper_keys
    path = root / "cad" / "scripts" / "ch_rocker_arm_spec.py"
    original = _mutate(path, old, new)
    try:
        with pytest.raises(AssertionError, match=message):
            _load_copy(root, "ch_rocker_arm_spec", monkeypatch)
        # The outline does not consume any of the invalid guarded contracts.
        outline = _load_copy(root, "ch_rocker_arm_outline_spec", monkeypatch)
        assert outline.ROD_TIP_X > outline.TOP_END_X > outline.BOT_END_X > 0.0
    finally:
        path.write_bytes(original)
