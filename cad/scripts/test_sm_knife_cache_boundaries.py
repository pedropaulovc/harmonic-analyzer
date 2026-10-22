"""Real recipe/cache boundaries for the knife contact and top-seat interface.

Only copied recipe bytes and native tokens are mutated. The shared fixture
redirects CAD outputs and adapter sidecars before discovering production tasks;
no SolidWorks process, farm activity, or live native output is touched.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import _buildgraph as bg
from test_dodo_recipe import (
    _load_dodo,
    isolated_assembly_helper_keys as isolated_assembly_helper_keys,
    local_executor as local_executor,
)

pytestmark = pytest.mark.usefixtures("local_executor")

SCRIPTS = Path(__file__).resolve().parent
PARTS = {"fr_top_frame", "sm_knife_mount", "sm_summing_lever"}


def _closure(script: str) -> set[str]:
    bg.clear_import_caches()
    paths = bg.module_deps_of(SCRIPTS / script)
    assert paths, f"{script}: closure discovery matched no imports"
    return {Path(path).stem for path in paths}


@pytest.mark.parametrize("script", ["build_fr_top_frame.py", "draw_fr_top_frame.py"])
def test_frame_reads_the_mount_interface_not_the_lever_or_rocking_proof(script):
    names = _closure(script)
    assert {"sm_knife_mount_interface", "sm_vn_knife_mount_dowel_spec", "_config"} <= names
    assert not names & {
        "sm_knife_mount_spec", "sm_knife_contact", "sm_summing_lever_spec",
        "build_sm_summing_lever", "stock_anchor_geom",
    }


@pytest.mark.parametrize("script", ["build_sm_knife_mount.py", "draw_sm_knife_mount.py"])
def test_mount_keeps_contact_but_drops_the_lever_body_and_anchor_closure(script):
    names = _closure(script)
    assert {"sm_knife_contact", "sm_knife_mount_interface", "sm_knife_mount_spec"} <= names
    assert not names & {"sm_summing_lever_spec", "build_sm_summing_lever", "stock_anchor_geom"}


def test_contact_has_no_body_or_configuration_dependencies():
    bg.clear_import_caches()
    assert bg.module_deps_of(SCRIPTS / "sm_knife_contact.py") == []
    interface = _closure("sm_knife_mount_interface.py")
    assert {"_config", "sm_vn_knife_mount_dowel_spec"} <= interface
    assert not interface & {"sm_knife_contact", "sm_knife_mount_spec", "sm_summing_lever_spec"}


def _mutate(path: Path, before: bytes, after: bytes) -> bytes:
    original = path.read_bytes()
    assert original.count(before) == 1, f"{path.name}: mutation must match exactly once"
    path.write_bytes(original.replace(before, after))
    return original


def _changed(before, after, group):
    return {stem for stem in before[group] if before[group][stem] != after[group][stem]}


@pytest.mark.parametrize(
    ("script", "old", "new", "changed_parts", "own_assembly_recipe_changes"),
    [
        ("sm_summing_lever_spec.py", b"COEFFICIENT_T = 7.0", b"COEFFICIENT_T = 7.1",
         {"sm_summing_lever"}, True),
        ("build_sm_summing_lever.py", b"RIB_PAD = 0.1 * IN", b"RIB_PAD = 0.11 * IN",
         {"sm_summing_lever"}, False),
        ("sm_knife_mount_interface.py", b"BLK_HALF_X = 12.7", b"BLK_HALF_X = 12.8",
         {"fr_top_frame", "sm_knife_mount"}, True),
        ("sm_knife_mount_interface.py", b'"knife-hanger tap position": "0.15"',
         b'"knife-hanger tap position": "0.16"',
         {"fr_top_frame", "sm_knife_mount"}, True),
        ("sm_knife_contact.py", b"HEX_W = 8.080", b"HEX_W = 8.060",
         {"sm_summing_lever", "sm_knife_mount"}, True),
        ("sm_knife_contact.py", b"HEX_H = 10.268", b"HEX_H = 10.266",
         {"sm_summing_lever", "sm_knife_mount"}, True),
        ("sm_knife_contact.py", b"RIDGE_FROM_SIDE_TOL = 0.05", b"RIDGE_FROM_SIDE_TOL = 0.06",
         {"sm_summing_lever", "sm_knife_mount"}, True),
    ],
)
def test_real_recipe_and_cache_keys_respect_knife_boundaries(
    isolated_assembly_helper_keys, script, old, new, changed_parts,
    own_assembly_recipe_changes,
):
    _dodo, root, snapshot = isolated_assembly_helper_keys
    path = root / "cad" / "scripts" / script
    before = snapshot()
    assert PARTS <= before["parts"].keys()
    original = _mutate(path, old, new)
    try:
        after = snapshot()
    finally:
        path.write_bytes(original)
    assert _changed(before, after, "part_recipes") & PARTS == changed_parts
    assert _changed(before, after, "parts") & PARTS == changed_parts
    assert ("sm_summing" in _changed(before, after, "recipes")) is own_assembly_recipe_changes
    # Native part recipe identities propagate even for a rib-only edit that
    # does not change the summing assembly's own FULL-rebuild recipe.
    assert "sm_summing" in _changed(before, after, "assemblies")


def test_printed_configuration_still_changes_real_frame_and_mount_keys(isolated_assembly_helper_keys):
    dodo, root, snapshot = isolated_assembly_helper_keys
    title_block = root / "cad" / "config" / "title_block.yaml"
    for stem in PARTS:
        dependencies = dodo._part_file_deps(root / "cad" / "scripts" / f"build_{stem}.py", stem)
        assert dependencies.count(str(title_block)) == 1, stem
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
    assert _changed(before, after, "parts") & PARTS == PARTS
    assert _changed(before, after, "part_recipes") & PARTS == PARTS


def test_interface_alone_keeps_printed_geometry_configuration_without_stamping(monkeypatch):
    dodo = _load_dodo()
    interface = SCRIPTS / "sm_knife_mount_interface.py"
    bg.clear_import_caches()
    tokens = bg.config_files_of(interface)
    assert "title_block" in tokens
    assert "**" not in tokens, "whole-config fallback would mask the geometry-reader boundary"
    assert interface.stem in bg.TITLE_BLOCK_GEOMETRY_MODULES
    monkeypatch.setattr(dodo, "stamps_title_block_properties", lambda _script: False)
    # The real interface imports a dowel spec that is another registered reader.
    # Remove those alternative readers so they cannot hide a missing interface
    # classification from the production dependency expansion.
    monkeypatch.setattr(bg, "TITLE_BLOCK_GEOMETRY_MODULES", frozenset({interface.stem}))
    title_block = str((dodo.CONFIG_DIR / "title_block.yaml").resolve())
    assert bg.reads_title_block_geometry(interface)
    assert title_block in dodo._config_deps(interface, kind="assembly")
    monkeypatch.setattr(bg, "TITLE_BLOCK_GEOMETRY_MODULES", frozenset())
    assert not bg.reads_title_block_geometry(interface)
    assert title_block not in dodo._config_deps(interface, kind="assembly")


def test_real_summing_key_retains_exact_native_lever_execution_identity(isolated_assembly_helper_keys):
    dodo, root, snapshot = isolated_assembly_helper_keys
    token = Path(dodo._part_execution_token("sm_summing_lever"))
    assert token.resolve().is_relative_to(root.resolve())
    assert dodo._assembly_file_deps("sm_summing").count(str(token)) == 1
    before = snapshot()
    original = token.read_bytes()
    token.write_bytes(b"b" * 64 + b"\n")
    try:
        after = snapshot()
    finally:
        token.write_bytes(original)
    assert before["part_recipes"] == after["part_recipes"]
    assert before["parts"] == after["parts"]
    assert before["recipes"] == after["recipes"]
    assert "sm_summing" in _changed(before, after, "assemblies")


def _copied_python(root: Path, source: str):
    # Key discovery copies only selected config shards. Runtime accessors
    # aggregate whole split documents, so give imports a complete copied config
    # tree while preserving every existing fixture byte (including mutations).
    config = SCRIPTS.parent / "config"
    for original in config.rglob("*"):
        if not original.is_file():
            continue
        copied = root / "cad" / "config" / original.relative_to(config)
        if not copied.exists():
            copied.parent.mkdir(parents=True, exist_ok=True)
            copied.write_bytes(original.read_bytes())
    # Runtime imports still need helpers deliberately excluded from recipe keys.
    # Supply their copied bytes without adding them to the captured key inputs.
    for name in bg.RECIPE_SKIP_MODULES:
        original = SCRIPTS / name
        copied = root / "cad" / "scripts" / name
        if original.is_file() and not copied.exists():
            copied.write_bytes(original.read_bytes())
    # A fresh interpreter imports every consumer from this isolated tree. Keep
    # the suite's child guard and refusal log, but never the live scripts path.
    environment = os.environ.copy()
    assert environment.get("HARMONIC_TEST_FORBID_SOLIDWORKS"), (
        "child import needs the suite's refusal log"
    )
    guard = SCRIPTS.parents[1] / "tests" / "_child_guard"
    environment["PYTHONPATH"] = os.pathsep.join((str(guard), str(root / "cad" / "scripts")))
    source = "import sys\nassert 'harmonic_solidworks_guard' in sys.modules\n" + source
    result = subprocess.run(
        [sys.executable, "-B", "-c", source],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Copied-tree import failed with exit {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return json.loads(result.stdout)


def test_mounting_zone_print_and_stack_share_the_unrounded_string(isolated_assembly_helper_keys):
    _dodo, root, _snapshot = isolated_assembly_helper_keys
    path = root / "cad" / "scripts" / "sm_knife_mount_interface.py"
    original = _mutate(
        path,
        b'"knife-hanger tap position": "0.15"',
        b'"knife-hanger tap position": "0.155"',
    )
    try:
        numeric, printed = _copied_python(root, """
import json
import sm_knife_mount_interface as interface
import sm_knife_mount_spec as mount
print(json.dumps((
    interface.STUD_TAP_POSITION_TOL,
    mount.GEOMETRIC_TOLERANCES_MM["knife-hanger tap position"],
)))
""")
    finally:
        path.write_bytes(original)
    assert printed == "0.155"
    assert numeric == float(printed) == 0.155


@pytest.mark.parametrize(
    ("old", "new", "dimension"),
    [(b"HEX_W = 8.080", b"HEX_W = 8.060", "HEX_W"),
     (b"HEX_H = 10.268", b"HEX_H = 10.266", "HEX_H")],
)
def test_contact_edits_change_real_geometry_and_rocking_values(
    isolated_assembly_helper_keys, old, new, dimension,
):
    _dodo, root, _snapshot = isolated_assembly_helper_keys

    def values():
        return _copied_python(root, f"""
import json
import sm_knife_mount_spec as mount
import build_sm_summing_lever as lever
import build_sm_knife_mount as mount_build
import build_sm_summing_assembly as assembly
print(json.dumps((
    getattr(lever, {dimension!r}),
    mount.free_rock_deg(0.0),
    assembly.KNIFE_FREE_ROCK_WORST_DEG,
    mount_build.RIDGE_Y,
)))
""")

    before = values()
    path = root / "cad" / "scripts" / "sm_knife_contact.py"
    original = _mutate(path, old, new)
    try:
        after = values()
    finally:
        path.write_bytes(original)
    assert before[0] != after[0], "the actual lever builder still used a duplicate nominal"
    assert before[1] != after[1], "the actual mount's nominal rocking profile stayed stale"
    if dimension == "HEX_W":
        assert before[2] != after[2], "the actual assembly's printed-limit rocking proof stayed stale"
    else:
        # A 0.002 height edit does not cross the flank angle's printed 0.1 deg
        # rounding boundary; it must still move the real mount's ridge seat.
        assert before[3] != after[3], "the actual mount geometry ignored the ridge height"
