"""Offline release comparisons pair actual files across the identity cutover."""

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import trimesh

TOOLS = Path(__file__).resolve().parents[1] / "comparisons" / "tools"
sys.path.insert(0, str(TOOLS))

from release_diff import load_identity_map, mesh_deviation, paired_keys


@pytest.fixture
def render_diff(monkeypatch):
    monkeypatch.setitem(sys.modules, "osmesa_win", SimpleNamespace(enable_offscreen_gl=lambda: None))
    spec = importlib.util.spec_from_file_location("render_diff_pairing_test", TOOLS / "render_diff.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pairs_preserve_actual_configured_names_and_missing_parts(tmp_path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"schema_version": 2, "identities": [
        {"old_stem": "cone-gear", "new_stem": "dt-cone-gear"},
    ]}), encoding="utf-8")
    mapping = load_identity_map(path)
    old = ["cone-gear--t024", "cone-gear-t032", "cone-gear-stretch07", "deleted"]
    new = ["dt-cone-gear--t024", "dt-cone-gear-t032", "dt-cone-gear-stretch07", "dt-cone-gear--t048", "added"]
    pairs = paired_keys(old, new, mapping)
    assert pairs == {
        "dt-cone-gear--t024": "cone-gear--t024",
        "dt-cone-gear-t032": "cone-gear-t032",
        "dt-cone-gear-stretch07": "cone-gear-stretch07",
    }
    assert set(new) - set(pairs) == {"added", "dt-cone-gear--t048"}
    assert set(old) - set(pairs.values()) == {"deleted"}
    assert paired_keys(new, new, mapping) == {key: key for key in new}


@pytest.mark.parametrize("old,new", [
    (["cone-gear", "dt-cone-gear"], ["dt-cone-gear"]),
    (["cone-gear"], ["cone-gear", "dt-cone-gear"]),
    (["cone-gear", "CONE-GEAR"], ["dt-cone-gear"]),
])
def test_duplicate_logical_identity_is_rejected(old, new):
    with pytest.raises(ValueError, match="duplicate logical identity"):
        paired_keys(old, new, {"cone-gear": "dt-cone-gear"})


def test_renamed_meshes_are_geometry_compared_not_reported_as_new(tmp_path, render_diff):
    old_root, new_root = tmp_path / "old", tmp_path / "new"
    for root in (old_root, new_root):
        (root / "stl").mkdir(parents=True)
    mesh = trimesh.creation.box(extents=(10, 10, 10))
    mesh.export(old_root / "stl" / "crank-arm.STL")
    # An alternate STL encoding must reach the real Hausdorff path, not CRC equality.
    (new_root / "stl" / "dt-crank-arm.STL").write_text(
        trimesh.exchange.stl.export_stl_ascii(mesh), encoding="ascii",
    )
    moved = mesh.copy()
    moved.apply_translation((2, 0, 0))
    moved.export(new_root / "stl" / "dt-moving-arm.STL")
    mesh.export(old_root / "stl" / "moving-arm.STL")
    mesh.export(new_root / "stl" / "new-part.STL")
    old, new = render_diff.LocalSource(old_root), render_diff.LocalSource(new_root)
    pairs = paired_keys(old.mesh_keys(), new.mesh_keys(), {
        "crank-arm": "dt-crank-arm", "moving-arm": "dt-moving-arm",
    })
    changed, deviations = render_diff.classify(old, new, set(new.mesh_keys()), pairs, jobs=1)
    assert changed == {"dt-moving-arm", "new-part"}
    assert deviations["dt-crank-arm"] < 0.01
    assert deviations["dt-moving-arm"] == pytest.approx(2.0)
    assert deviations["new-part"] == float("inf")


def test_mesh_deviation_reads_each_actual_cache_basename(tmp_path, monkeypatch):
    import release_diff

    monkeypatch.setattr(release_diff, "CACHE", tmp_path)
    for tag in ("before", "after"):
        (tmp_path / tag).mkdir()
    mesh = trimesh.creation.box(extents=(10, 10, 10))
    mesh.export(tmp_path / "before" / "crank-arm.stl")
    mesh.apply_translation((2, 0, 0))
    mesh.export(tmp_path / "after" / "dt-crank-arm.stl")
    deviation = mesh_deviation("before", "after", "crank-arm", "dt-crank-arm")
    assert deviation["hausdorff_mm"] == pytest.approx(2.0)
