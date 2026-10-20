"""Offline release comparisons pair actual files across the identity cutover."""

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
import trimesh

TOOLS = Path(__file__).resolve().parents[1] / "comparisons" / "tools"
sys.path.insert(0, str(TOOLS))

from release_diff import (
    HISTORICAL_IDENTITY_MAP, IDENTITY_MAP, canonical_keys, identity_inventory,
    load_identity_map, mesh_deviation, paired_keys,
)


@pytest.fixture
def render_diff(monkeypatch):
    monkeypatch.setitem(sys.modules, "osmesa_win", SimpleNamespace(enable_offscreen_gl=lambda: None))
    spec = importlib.util.spec_from_file_location("render_diff_pairing_test", TOOLS / "render_diff.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SPLIT_FAMILIES = [
    ("vn-fillister-screw", ("dt-vn-fillister-screw", "fr-vn-fillister-screw", "pd-vn-fillister-screw")),
    ("vn-clamp-screw", ("mg-vn-clamp-screw", "pd-vn-clamp-screw")),
    ("vn-arbor-set-screw", ("ch-vn-arbor-set-screw", "dt-vn-arbor-set-screw")),
    ("vn-thumb-screw", ("mg-vn-thumb-screw", "ms-vn-thumb-screw")),
]


@pytest.mark.parametrize("extension", [".step", ".STL", ".pdf", ".SLDPRT", ".SLDDRW"])
def test_every_current_artifact_pairs_with_its_prior_source_without_mutating_maps(extension):
    current_bytes = IDENTITY_MAP.read_bytes()
    historical_bytes = HISTORICAL_IDENTITY_MAP.read_bytes()
    rows = json.loads(current_bytes)["parts_and_assemblies"]
    old = [Path(row["old_stem"] + extension).stem for row in rows]
    expected = {
        Path(identity["stem"] + extension).stem: row["old_stem"]
        for row in rows for identity in row["new_identities"]
    }
    mapping = load_identity_map()
    assert paired_keys(old, expected, mapping) == expected
    assert paired_keys(expected, expected, mapping) == {key: key for key in expected}
    assert IDENTITY_MAP.read_bytes() == current_bytes
    assert HISTORICAL_IDENTITY_MAP.read_bytes() == historical_bytes


def test_all_archived_identities_compose_through_the_current_authority():
    current = json.loads(IDENTITY_MAP.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL_IDENTITY_MAP.read_text(encoding="utf-8"))
    current_targets = {
        row["old_stem"]: tuple(identity["stem"] for identity in row["new_identities"])
        for row in current["parts_and_assemblies"]
    }
    current_targets.update({
        row["old_stem"]: (row["current_stem"],)
        for row in current["historical_current_aliases"]
    })
    archived = [
        row for row in historical["identities"]
        if row["old_stem"] is not None and row["new_stem"] in current_targets
    ]
    assert archived
    expected = {
        target: row["old_stem"]
        for row in archived for target in current_targets[row["new_stem"]]
    }
    assert paired_keys((row["old_stem"] for row in archived), expected, load_identity_map()) == expected


@pytest.mark.parametrize("prior,targets", SPLIT_FAMILIES)
@pytest.mark.parametrize("archived", [False, True])
@pytest.mark.parametrize("qualifier", ["", "--installed", "--t006", "-stretch07"])
def test_every_split_target_reuses_the_physical_prior_vendor_source(prior, targets, archived, qualifier):
    source = (prior.removeprefix("vn-") if archived else prior) + qualifier
    current = [target + qualifier for target in targets]
    mapping = load_identity_map()
    assert paired_keys([source], current, mapping) == {target: source for target in current}
    assert canonical_keys(source, mapping) == tuple(current)
    assert identity_inventory(current, mapping) == {target: target for target in current}


def test_current_split_clones_pair_only_with_their_own_identity():
    _, targets = SPLIT_FAMILIES[0]
    mapping = load_identity_map()
    assert paired_keys(targets, targets, mapping) == {target: target for target in targets}
    assert paired_keys([targets[0]], targets, mapping) == {targets[0]: targets[0]}
    with pytest.raises(ValueError, match="ambiguous prior identity"):
        paired_keys(targets, ["vn-fillister-screw"], mapping)


@pytest.mark.parametrize("old", [
    ["vn-fillister-screw", "dt-vn-fillister-screw"],
    ["fillister-screw", "vn-fillister-screw"],
])
def test_mixed_historical_and_current_split_aliases_are_rejected(old):
    mapping = load_identity_map()
    with pytest.raises(ValueError, match="duplicate logical identity"):
        paired_keys(old, ["dt-vn-fillister-screw"], mapping)
    with pytest.raises(ValueError, match="duplicate logical identity"):
        paired_keys(["vn-fillister-screw"], old, mapping)


@pytest.mark.parametrize("archived,category,prior,current", [
    ("lever-wire", "mg-lever-wire", "vn-lever-wire", "mg-vn-lever-wire"),
    ("pen-wire", "pn-pen-wire", "vn-pen-wire", "pn-vn-pen-wire"),
    ("pen-marker", "pn-pen-marker", "vn-pen-marker", "pn-vn-pen-marker"),
])
def test_sealed_and_post_v39_aliases_project_to_the_current_vendor(archived, category, prior, current):
    mapping = load_identity_map()
    for source in (archived, category, prior):
        assert paired_keys([source], [current], mapping) == {current: source}


def test_tooling_vendor_identity_pairs_without_changing_configuration():
    prior = "ch-rocker-arm-tl-oblique-nut-screw--installed"
    current = "ch-rocker-arm-tl-vn-oblique-nut-screw--installed"
    mapping = load_identity_map()
    assert paired_keys([prior], [current], mapping) == {current: prior}
    assert paired_keys([current], [current], mapping) == {current: current}


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
        "ch-vn-channel-spring-installed-stretch07",
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
        "ch-vn-channel-spring-installed-stretch07": "channel-spring-installed-stretch07",
    }
    assert set(new) - set(pairs) == {"added", "dt-cone-gear--t048"}
    assert set(old) - set(pairs.values()) == {"deleted", "cone-gear--t024"}


def test_configuration_separator_takes_precedence_over_stretch_suffix(render_diff):
    old = [
        "channel-spring-installed-stretch07",
        "channel-spring-installed--installed--stretch07",
    ]
    new = [
        "ch-vn-channel-spring-installed-stretch07",
        "ch-vn-channel-spring-installed--installed--stretch07",
    ]
    pairs = paired_keys(old, new, load_identity_map())
    assert pairs == {
        "ch-vn-channel-spring-installed-stretch07": "channel-spring-installed-stretch07",
        "ch-vn-channel-spring-installed--installed--stretch07":
            "channel-spring-installed--installed--stretch07",
    }


@pytest.mark.parametrize("old,new", [
    (["cone-gear", "dt-cone-gear"], ["dt-cone-gear"]),
    (["cone-gear"], ["cone-gear", "dt-cone-gear"]),
    (["cone-gear", "CONE-GEAR"], ["dt-cone-gear"]),
])
def test_duplicate_logical_identity_is_rejected(old, new):
    with pytest.raises(ValueError, match="duplicate logical identity"):
        paired_keys(old, new, {"cone-gear": ("dt-cone-gear",)})


def test_renamed_variants_keep_independent_geometry_verdicts_and_grouping(tmp_path, render_diff):
    old_root, new_root = tmp_path / "old", tmp_path / "new"
    for root in (old_root, new_root):
        (root / "stl").mkdir(parents=True)
    mesh = trimesh.creation.box(extents=(10, 10, 10))
    unchanged = [
        ("transgear-removable--t12", "pd-transgear-removable--t12"),
        ("crank-handle-pivot-screw--installed", "dt-crank-handle-pivot-screw--installed"),
        ("pinion-lever-pin--installed", "dt-pinion-lever-pin--installed"),
        ("channel-spring-installed-stretch07", "ch-vn-channel-spring-installed-stretch07"),
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
        "pd-transgear-removable", "dt-crank-handle-ferrule--installed", "dt-cone-gear",
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


@pytest.mark.parametrize("prior,targets", SPLIT_FAMILIES)
@pytest.mark.parametrize("archived", [False, True])
def test_vendor_clones_are_not_classified_as_new_geometry(tmp_path, render_diff, prior, targets, archived):
    old_root, new_root = tmp_path / "old", tmp_path / "new"
    for root in (old_root, new_root):
        (root / "stl").mkdir(parents=True)
    mesh = trimesh.creation.box(extents=(10, 10, 10))
    source = prior.removeprefix("vn-") if archived else prior
    mesh.export(old_root / "stl" / f"{source}.STL")
    for target in targets:
        mesh.export(new_root / "stl" / f"{target}.STL")
    old, new = render_diff.LocalSource(old_root), render_diff.LocalSource(new_root)
    pairs = paired_keys(old.mesh_keys(), new.mesh_keys(), load_identity_map())
    assert pairs == {target: source for target in targets}
    assert render_diff.classify(old, new, set(new.mesh_keys()), pairs, jobs=1) == (set(), {})


def test_split_clone_geometry_verdicts_remain_independent(tmp_path, render_diff):
    old_root, new_root = tmp_path / "old", tmp_path / "new"
    for root in (old_root, new_root):
        (root / "stl").mkdir(parents=True)
    mesh = trimesh.creation.box(extents=(10, 10, 10))
    mesh.export(old_root / "stl" / "vn-fillister-screw--installed.STL")
    (new_root / "stl" / "dt-vn-fillister-screw--installed.STL").write_text(
        trimesh.exchange.stl.export_stl_ascii(mesh), encoding="ascii",
    )
    mesh.export(new_root / "stl" / "pd-vn-fillister-screw--installed.STL")
    mesh.apply_translation((2, 0, 0))
    mesh.export(new_root / "stl" / "fr-vn-fillister-screw--installed.STL")
    old, new = render_diff.LocalSource(old_root), render_diff.LocalSource(new_root)
    pairs = paired_keys(old.mesh_keys(), new.mesh_keys(), load_identity_map())
    assert len(pairs) == 3
    changed, deviations = render_diff.classify(old, new, set(new.mesh_keys()), pairs, jobs=1)
    assert changed == {"fr-vn-fillister-screw--installed"}
    assert deviations["dt-vn-fillister-screw--installed"] < 0.01
    assert deviations["fr-vn-fillister-screw--installed"] == pytest.approx(2)
    assert "pd-vn-fillister-screw--installed" not in deviations


@pytest.mark.parametrize("requested,expected", [
    ("fillister-screw", ["dt-vn-fillister-screw", "fr-vn-fillister-screw"]),
    ("vn-fillister-screw", ["dt-vn-fillister-screw", "fr-vn-fillister-screw"]),
    ("dt-vn-fillister-screw", ["dt-vn-fillister-screw"]),
])
def test_parts_selector_accepts_historical_family_or_one_current_clone(monkeypatch, capsys, requested, expected):
    import release_diff

    old = {"step/vn-fillister-screw.STEP": {"crc": 1, "uncomp": 100}}
    new = {
        f"step/{stem}.STEP": {"crc": 1, "uncomp": 100}
        for stem in ("dt-vn-fillister-screw", "fr-vn-fillister-screw")
    }
    monkeypatch.setattr(release_diff, "central_dir",
                        lambda url: old if url == release_diff.asset_url("v50") else new)
    monkeypatch.setattr(release_diff, "member", lambda *args: None)
    monkeypatch.setattr(sys, "argv",
                        ["release_diff.py", "v50", "v51", "--no-boolean", "--parts", requested])
    release_diff.main()
    output = capsys.readouterr().out
    assert [line.removeprefix("### ") for line in output.splitlines() if line.startswith("### ")] == expected
    assert "new parts: (none)" in output
    assert "deleted parts: (none)" in output


@pytest.mark.parametrize("stem", ["harmonic-analyzer", "ha-harmonic-analyzer"])
def test_render_scene_uses_composed_identity_mapping(render_diff, stem):
    mapping = load_identity_map()
    name = f"boxes/{stem}.json"
    assert render_diff._scene_member(["boxes/unrelated.json", name], mapping) == name
    with pytest.raises(ValueError, match="duplicate logical identity"):
        render_diff._scene_member(
            ["boxes/harmonic-analyzer.json", "boxes/ha-harmonic-analyzer.json"], mapping,
        )


@pytest.mark.parametrize("directory,extension", [("gltf", ".glb"), ("boxes", ".json"), ("pdf", ".pdf")])
@pytest.mark.parametrize("source", ["fillister-screw", "vn-fillister-screw"])
def test_meshprobe_release_lookup_reuses_actual_prior_member(tmp_path, monkeypatch, directory, extension, source):
    import pose_to_meshprobe

    monkeypatch.setattr(pose_to_meshprobe, "CAD_OUT", tmp_path)
    cache = tmp_path / "release-cache" / "v50"
    cache.mkdir(parents=True)
    asset = "harmonic-analyzer-v50.zip"
    name = f"{directory}/{source}{extension}"
    with ZipFile(cache / asset, "w") as archive:
        archive.writestr(name, b"immutable historical member")
    calls = []
    monkeypatch.setattr(pose_to_meshprobe, "_gh", lambda args: calls.append(args) or asset)
    for target in SPLIT_FAMILIES[0][1]:
        actual = pose_to_meshprobe.release_member(f"{directory}/{target}{extension}", "v50")
        assert actual == cache / name
        assert actual.read_bytes() == b"immutable historical member"
    assert len(calls) == 1


def test_meshprobe_current_release_lookup_never_substitutes_a_sibling_clone(tmp_path, monkeypatch):
    import pose_to_meshprobe

    monkeypatch.setattr(pose_to_meshprobe, "CAD_OUT", tmp_path)
    cache = tmp_path / "release-cache" / "v51"
    cache.mkdir(parents=True)
    asset = "harmonic-analyzer-v51.zip"
    with ZipFile(cache / asset, "w") as archive:
        for target in SPLIT_FAMILIES[0][1]:
            archive.writestr(f"gltf/{target}.glb", target.encode("ascii"))
    monkeypatch.setattr(pose_to_meshprobe, "_gh", lambda args: asset)
    for target in SPLIT_FAMILIES[0][1]:
        actual = pose_to_meshprobe.release_member(f"gltf/{target}.glb", "v51")
        assert actual == cache / f"gltf/{target}.glb"
        assert actual.read_bytes() == target.encode("ascii")
