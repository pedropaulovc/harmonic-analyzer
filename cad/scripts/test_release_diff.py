"""Offline release comparisons pair actual files across the identity cutover."""

import importlib.util
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


def test_pairs_preserve_released_configurations_and_missing_variants():
    mapping = load_identity_map()
    old = [
        "transgear-removable--t12",
        "transgear-removable--t18",
        "transgear-removable--t24",
        "crank-handle-ferrule--installed",
        "crank-handle-pivot-screw--installed",
        "pinion-lever-pin--installed",
        "cone-gear--t006",
        "cone-gear--t024",
        "channel-spring-installed-stretch07",
        "deleted",
    ]
    new = [
        "pd-transgear-removable--t12",
        "pd-transgear-removable--t18",
        "pd-transgear-removable--t24",
        "dt-crank-handle-ferrule--installed",
        "dt-crank-handle-pivot-screw--installed",
        "dt-pinion-lever-pin--installed",
        "dt-cone-gear--t006",
        "dt-cone-gear--t048",
        "vn-channel-spring-installed-stretch07",
        "added",
    ]
    pairs = paired_keys(old, new, mapping)
    assert pairs == {
        "pd-transgear-removable--t12": "transgear-removable--t12",
        "pd-transgear-removable--t18": "transgear-removable--t18",
        "pd-transgear-removable--t24": "transgear-removable--t24",
        "dt-crank-handle-ferrule--installed": "crank-handle-ferrule--installed",
        "dt-crank-handle-pivot-screw--installed": "crank-handle-pivot-screw--installed",
        "dt-pinion-lever-pin--installed": "pinion-lever-pin--installed",
        "dt-cone-gear--t006": "cone-gear--t006",
        "vn-channel-spring-installed-stretch07": "channel-spring-installed-stretch07",
    }
    assert set(new) - set(pairs) == {"added", "dt-cone-gear--t048"}
    assert set(old) - set(pairs.values()) == {"deleted", "cone-gear--t024"}


def test_configuration_separator_takes_precedence_over_stretch_suffix(render_diff):
    old = [
        "channel-spring-installed-stretch07",
        "channel-spring-installed--installed--stretch07",
    ]
    new = [
        "vn-channel-spring-installed-stretch07",
        "vn-channel-spring-installed--installed--stretch07",
    ]
    pairs = paired_keys(old, new, load_identity_map())
    assert pairs == {
        "vn-channel-spring-installed-stretch07": "channel-spring-installed-stretch07",
        "vn-channel-spring-installed--installed--stretch07":
            "channel-spring-installed--installed--stretch07",
    }
    assert {render_diff.base_part(key) for key in pairs} == {"vn-channel-spring-installed"}


@pytest.mark.parametrize("old,new", [
    (["cone-gear", "dt-cone-gear"], ["dt-cone-gear"]),
    (["cone-gear"], ["cone-gear", "dt-cone-gear"]),
    (["cone-gear", "CONE-GEAR"], ["dt-cone-gear"]),
])
def test_duplicate_logical_identity_is_rejected(old, new):
    with pytest.raises(ValueError, match="duplicate logical identity"):
        paired_keys(old, new, {"cone-gear": "dt-cone-gear"})


def test_renamed_variants_keep_independent_geometry_verdicts_and_grouping(tmp_path, render_diff):
    old_root, new_root = tmp_path / "old", tmp_path / "new"
    for root in (old_root, new_root):
        (root / "stl").mkdir(parents=True)
    mesh = trimesh.creation.box(extents=(10, 10, 10))
    unchanged = [
        ("transgear-removable--t12", "pd-transgear-removable--t12"),
        ("crank-handle-pivot-screw--installed", "dt-crank-handle-pivot-screw--installed"),
        ("pinion-lever-pin--installed", "dt-pinion-lever-pin--installed"),
        ("channel-spring-installed-stretch07", "vn-channel-spring-installed-stretch07"),
    ]
    for before, after in unchanged:
        mesh.export(old_root / "stl" / f"{before}.STL")
        mesh.export(new_root / "stl" / f"{after}.STL")
    # The default and INSTALLED meshes of one family must never replace each other.
    default = trimesh.creation.box(extents=(4, 4, 4))
    default.export(old_root / "stl" / "crank-handle-ferrule.STL")
    default.export(new_root / "stl" / "dt-crank-handle-ferrule.STL")
    changed_variants = [
        ("transgear-removable--t18", "pd-transgear-removable--t18", 2),
        ("transgear-removable--t24", "pd-transgear-removable--t24", 3),
        ("crank-handle-ferrule--installed", "dt-crank-handle-ferrule--installed", 1),
    ]
    for before, after, distance in changed_variants:
        mesh.export(old_root / "stl" / f"{before}.STL")
        moved = mesh.copy()
        moved.apply_translation((distance, 0, 0))
        moved.export(new_root / "stl" / f"{after}.STL")
    # Alternate STL encoding must reach Hausdorff, without flagging a renamed T006.
    mesh.export(old_root / "stl" / "cone-gear--t006.STL")
    (new_root / "stl" / "dt-cone-gear--t006.STL").write_text(
        trimesh.exchange.stl.export_stl_ascii(mesh), encoding="ascii",
    )
    mesh.export(old_root / "stl" / "cone-gear--t048.STL")
    mesh.export(new_root / "stl" / "dt-cone-gear--t024.STL")
    old, new = render_diff.LocalSource(old_root), render_diff.LocalSource(new_root)
    pairs = paired_keys(old.mesh_keys(), new.mesh_keys(), load_identity_map())
    assert set(new.mesh_keys()) - set(pairs) == {"dt-cone-gear--t024"}
    assert set(old.mesh_keys()) - set(pairs.values()) == {"cone-gear--t048"}
    changed, deviations = render_diff.classify(old, new, set(new.mesh_keys()), pairs, jobs=1)
    assert changed == {
        "pd-transgear-removable--t18",
        "pd-transgear-removable--t24",
        "dt-crank-handle-ferrule--installed",
        "dt-cone-gear--t024",
    }
    assert {render_diff.base_part(key) for key in changed} == {
        "pd-transgear-removable", "dt-crank-handle-ferrule", "dt-cone-gear",
    }
    for _, key, distance in changed_variants:
        assert deviations[key] == pytest.approx(distance)
    assert deviations["dt-cone-gear--t006"] < 0.01
    assert deviations["dt-cone-gear--t024"] == float("inf")


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
