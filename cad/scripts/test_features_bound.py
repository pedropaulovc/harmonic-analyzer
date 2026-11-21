"""Offline regressions for binding scoped feature bundles to the full export."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import _config
import export_features
import features_bound
from _export_feature_faces import FeatureFaceError, face_label, inventory_path
from _test_feature_bundles import bind_manifest, write_bundle


def _add_full_face(out: Path, stem: str, label: str) -> Path:
    """Add one labelled face to the full export only; its manifest is unaffected."""
    full = out / "step" / f"{stem.replace('_', '-')}.STEP"
    content = full.read_bytes()
    row = f"#99999 = ADVANCED_FACE ( '{label}', ( #1 ), #2, .T. ) ;\n".encode("ascii")
    index = content.rindex(b"ENDSEC;")
    full.write_bytes(content[:index] + row + content[index:])
    return full


def bound_output(tmp_path: Path, *, pivot_bore_faces: int = 2) -> Path:
    """Authoritative scoped bundles and their byte-identical neutral copies.

    Manifests come from the real generator binding the real declarations'
    feature names through the inventory; only the face selectors are doubles.
    """
    out = tmp_path / "cad" / "out"
    (out / "step").mkdir(parents=True)
    for stem in export_features.SUPPORTED_PARTS:
        _manifest, step = export_features.bundle_paths(stem, out)
        selectors = write_bundle(stem, step, split={"pivot_bore": pivot_bore_faces})
        (out / "step" / step.name).write_bytes(step.read_bytes())
        for cfg_step in export_features.configuration_step_paths(stem, out).values():
            cfg_step.write_bytes(step.read_bytes())
            inventory_path(cfg_step).write_text(
                inventory_path(step).read_text(encoding="utf-8").replace(step.name, cfg_step.name), encoding="utf-8",
            )
            (out / "step" / cfg_step.name).write_bytes(step.read_bytes())
        for member in export_features.member_step_paths(stem, out).values():
            (out / "step" / member.name).write_bytes(member.read_bytes())
        bind_manifest(stem, step, selectors, revision=_config.release_revision())
    return out


def _digests(out: Path, stem: str) -> tuple[str, str]:
    name = f"{stem.replace('_', '-')}.STEP"
    return tuple(
        hashlib.sha256((out / relative / name).read_bytes()).hexdigest()
        for relative in (Path("features") / stem, Path("step"))
    )


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }

@pytest.fixture
def configured_feature_part(monkeypatch) -> str:
    """Exercise opt-in exports without adding a production export obligation."""
    from dt_crank_handle_pivot_screw_spec import INSTALLED_CONFIG

    # Reuse real feature declarations with test-only configuration names.
    stem = "ch_rocker_arm"
    original = export_features.step_configurations
    monkeypatch.setattr(
        export_features, "step_configurations",
        lambda selected: ("Default", INSTALLED_CONFIG) if selected == stem else original(selected),
    )
    return stem



def test_copied_exports_bind_and_stage_exact_scoped_bytes(
    tmp_path: Path, monkeypatch, configured_feature_part: str,
) -> None:
    out = bound_output(tmp_path)

    def refuse_declarations(*_args):
        pytest.fail("bundle consumers must not reload drawing declarations")

    monkeypatch.setattr(export_features, "feature_selectors", refuse_declarations)
    monkeypatch.setattr(export_features, "requirement_manifest", refuse_declarations)
    for stem in export_features.SUPPORTED_PARTS:
        scoped, full = _digests(out, stem)
        assert scoped == full
    stage = tmp_path / "stage"

    checked = features_bound.check_bound_features(out)
    staged = features_bound.stage_bound_features(out, stage)

    expected = {
        relative: content
        for relative, content in _tree(out).items()
        if relative.startswith("features/")
    }
    configured = {
        stem: {
            **export_features.configuration_step_paths(stem, out),
            **export_features.member_step_paths(stem, out),
        }
        for stem in export_features.SUPPORTED_PARTS
    }
    assert export_features.configuration_step_paths(configured_feature_part, out)
    # Each part: its STEP, inventory and manifest; each extra STEP: itself and its inventory.
    files = 3 * len(export_features.SUPPORTED_PARTS) + 2 * sum(map(len, configured.values()))
    assert len(checked) == len(staged) == len(expected) == files
    assert _tree(stage) == expected
    for stem in export_features.SUPPORTED_PARTS:
        steps = [f"{stem.replace('_', '-')}.STEP", *(path.name for path in configured[stem].values())]
        assert {path.name for path in (stage / "features" / stem).iterdir()} == {
            "features.toml", *steps, *(inventory_path(Path(name)).name for name in steps),
        }


def test_missing_configuration_step_never_stages(
    tmp_path: Path, configured_feature_part: str,
) -> None:
    out = bound_output(tmp_path)
    from dt_crank_handle_pivot_screw_spec import INSTALLED_CONFIG

    missing = export_features.configuration_step_paths(configured_feature_part, out)[INSTALLED_CONFIG]
    missing.unlink()
    with pytest.raises(features_bound.FeaturesBoundError, match="cannot read required file"):
        features_bound.stage_bound_features(out, tmp_path / "stage")
    assert not (tmp_path / "stage").exists()


@pytest.mark.parametrize("member", ["manifest", "step", "inventory"])
def test_unproduced_feature_leaf_never_stages_a_partial_package(tmp_path: Path, member: str) -> None:
    out = bound_output(tmp_path)
    stem = export_features.SUPPORTED_PARTS[-1]
    manifest, step = export_features.bundle_paths(stem, out)
    missing = {"manifest": manifest, "step": step, "inventory": inventory_path(step)}[member]
    missing.unlink()
    before = _tree(out)
    stage = tmp_path / "stage"
    with pytest.raises(features_bound.FeaturesBoundError, match=re.escape(str(missing))):
        features_bound.stage_bound_features(out, stage)
    assert not stage.exists()
    assert _tree(out) == before


@pytest.mark.parametrize(("mismatch", "diagnostic"), [
    ("label-set", "not the exact scoped copy"),
    ("patch-count", "not the exact scoped copy"),
    ("adjacent-digest", "its STEP is"),
])
def test_unbound_bundle_never_stages_or_repairs(
    tmp_path: Path, mismatch: str, diagnostic: str,
) -> None:
    out = bound_output(tmp_path)
    # A declared part diverges; validation of every bundle precedes any staging.
    stem = export_features.DECLARED_PARTS[-1]
    if mismatch == "label-set":
        _add_full_face(out, stem, "HAF_F9999")
    elif mismatch == "patch-count":
        _add_full_face(out, stem, face_label(2))
    else:
        step = out / "features" / stem / f"{stem.replace('_', '-')}.STEP"
        step.write_bytes(step.read_bytes().replace(b"2026-10-01T22:03:24", b"2026-10-01T22:03:25"))
    before = _tree(out)
    scoped, full = _digests(out, stem)
    stage = tmp_path / "stage"

    for gate in (
        lambda: features_bound.check_bound_features(out),
        lambda: features_bound.stage_bound_features(out, stage),
    ):
        with pytest.raises(features_bound.FeaturesBoundError, match=diagnostic) as caught:
            gate()
        assert f"scoped sha256 {scoped}" in str(caught.value)
        if mismatch != "adjacent-digest":
            assert f"full sha256 {full}" in str(caught.value)
    assert not stage.exists()
    assert _tree(out) == before


def test_swapped_manifest_face_never_passes_or_stages(tmp_path: Path) -> None:
    out = bound_output(tmp_path)
    stem = export_features.DECLARED_PARTS[-1]
    path = out / "features" / stem / "features.toml"
    manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    feature, other = list(manifest["features"])[:2]
    manifest["features"][feature]["faces"] = manifest["features"][other]["faces"]
    path.write_text(export_features._toml(manifest), encoding="utf-8")
    before = _tree(out)
    stage = tmp_path / "stage"

    for gate in (
        lambda: features_bound.check_bound_features(out),
        lambda: features_bound.stage_bound_features(out, stage),
    ):
        with pytest.raises(features_bound.FeaturesBoundError, match=r"claimed by features"):
            gate()
    assert not stage.exists()
    assert _tree(out) == before


@pytest.mark.parametrize(
    ("corrupt", "message"),
    [
        ("empty", "feature manifest has no features"),
        ("scalar", "every feature must be a table"),
        ("undeclared-listing", "declares no requirement, but the manifest lists features"),
        ("stale-revision", "stale bundle: drawing revision 'v1'"),
    ],
)
def test_invalid_manifest_schema_never_stages(
    tmp_path: Path, corrupt: str, message: str
) -> None:
    out = bound_output(tmp_path)
    stem = export_features.DECLARED_PARTS[-1]
    undeclared = next(stem for stem in export_features.SUPPORTED_PARTS if stem not in export_features.DECLARED_PARTS)
    if corrupt == "undeclared-listing":
        stem = undeclared
    path = out / "features" / stem / "features.toml"
    manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    if corrupt == "empty":
        manifest["features"] = {}
    elif corrupt == "scalar":
        manifest["features"][next(iter(manifest["features"]))] = "not a table"
    elif corrupt == "undeclared-listing":
        assert manifest["features"] == {}
        manifest["features"] = {"invented": {"kind": "hole"}}
    else:
        manifest["drawing"]["revision"] = "v1"
    path.write_text(export_features._toml(manifest), encoding="utf-8")
    stage = tmp_path / "stage"
    with pytest.raises(features_bound.FeaturesBoundError, match=message):
        features_bound.stage_bound_features(out, stage)
    assert not stage.exists()


def test_half_labelled_rocker_pivot_bore_never_binds(tmp_path: Path) -> None:
    with pytest.raises(FeatureFaceError, match="pivot_bore: expected exactly 2 STEP patches, found 1"):
        bound_output(tmp_path, pivot_bore_faces=1)


@pytest.mark.parametrize("mismatch", ["part", "step", "duplicate-face"])
def test_bundle_identity_and_face_inventory_must_be_exact(tmp_path: Path, mismatch: str) -> None:
    out = bound_output(tmp_path)
    stem = export_features.DECLARED_PARTS[-1]
    path, _step_path = export_features.bundle_paths(stem, out)
    manifest = tomllib.loads(path.read_text(encoding="utf-8"))
    if mismatch == "part":
        manifest["part"] = "another-part"
        diagnostic = "part must identify"
    elif mismatch == "step":
        manifest["step"] = "../another-part.STEP"
        diagnostic = "adjacent basename"
    else:
        feature = next(iter(manifest["features"].values()))
        feature["faces"].append(feature["faces"][0])
        diagnostic = "name no or repeated STEP faces"
    path.write_text(export_features._toml(manifest), encoding="utf-8")
    stage = tmp_path / "stage"
    with pytest.raises(features_bound.FeaturesBoundError, match=diagnostic):
        features_bound.stage_bound_features(out, stage)
    assert not stage.exists()


def test_cli_exit_status_is_actionable(tmp_path: Path) -> None:
    script = str(Path(features_bound.__file__))
    # The two runs read disjoint trees, so start both before waiting on either:
    # each child spends seconds importing the exporter before it checks anything.
    runs = {
        name: subprocess.Popen(
            [sys.executable, script, "--out", str(out)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        for name, out in (
            ("missing", tmp_path / "missing"),
            ("bound", bound_output(tmp_path)),
        )
    }
    results = {name: (run.communicate(), run.returncode) for name, run in runs.items()}

    (_out, missing_stderr), missing_code = results["missing"]
    assert missing_code == 1
    assert "cannot read required file" in missing_stderr
    assert "regenerate package:features and export" in missing_stderr

    (_out, bound_stderr), bound_code = results["bound"]
    assert bound_code == 0, bound_stderr
