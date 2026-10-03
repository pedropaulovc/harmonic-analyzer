"""Offline byte-integrity and independent-producer binding regressions."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import export_features
import features_bound
from _export_feature_faces import face_name


def byte_record(path: Path, *, scoped: bool = False) -> dict:
    content = path.read_bytes()
    return {
        "path" if scoped else "source": (
            path.name if scoped else f"cad/out/{path.parent.name}/{path.name}"
        ),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def bound_output(tmp_path: Path) -> Path:
    """Produce real requirement manifests bound to named synthetic STEP bytes."""
    out = tmp_path / "cad" / "out"
    producer = hashlib.md5(b"offline exporter identity").hexdigest()
    source_digest = export_features.feature_sources_sha256()
    records = {}
    for stem in export_features.SUPPORTED_PARTS:
        dashed = stem.replace("_", "-")
        labels = [
            face_name(feature, 1)
            for feature in export_features.feature_selectors(stem)
        ]
        if stem == "rocker_arm":
            labels.insert(0, face_name("pivot_bore", 1))
        rows = ["ISO-10303-21;", "HEADER;", "ENDSEC;", "DATA;"]
        rows.extend(
            f"#{index} = ADVANCED_FACE('{label}',(#1),#2,.T.);"
            for index, label in enumerate(labels, start=10)
        )
        rows.extend(("ENDSEC;", "END-ISO-10303-21;"))
        bundle = out / "features" / stem
        bundle.mkdir(parents=True)
        step = bundle / f"{dashed}.STEP"
        step.write_bytes("\n".join(rows).encode("ascii"))
        full_step = out / "step" / step.name
        full_step.parent.mkdir(exist_ok=True)
        shutil.copyfile(step, full_step)
        records[f"step/{step.name}"] = byte_record(full_step)
        receipt = {
            "schema": features_bound.FEATURE_NEUTRAL_SCHEMA,
            "stem": stem,
            "exporter": producer,
            "feature_sources_sha256": source_digest,
            "drawing_revision": "v38",
            "native_sha256": hashlib.sha256(f"native fixture {stem}".encode()).hexdigest(),
            "step": byte_record(step, scoped=True),
        }
        (bundle / "neutral.json").write_text(json.dumps(receipt), encoding="utf-8")
    for manifest in export_features.write_manifests(out=out):
        receipt_path = manifest.parent / "neutral.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["features"] = byte_record(manifest, scoped=True)
        receipt_path.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
    certificate = out / "reports" / "release-neutral.json"
    certificate.parent.mkdir()
    certificate.write_text(json.dumps({
        "schema": features_bound.RELEASE_NEUTRAL_SCHEMA,
        "exporter": producer,
        "sources": {},
        "files": records,
    }), encoding="utf-8")
    return out


def _rewrite(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize(("corruption", "diagnostic"), [
    ("scoped-step-bytes", "SHA-256 differs"),
    ("feature-bytes", "SHA-256 differs"),
    ("full-step-bytes", "SHA-256 differs"),
    ("scoped-step-size", "byte size differs"),
    ("feature-size", "byte size differs"),
    ("full-step-size", "byte size differs"),
    ("full-step-producer", "producers diverged"),
    ("exporter-identity", "exporter differs"),
    ("requirement-sources", "feature sources changed"),
    ("manifest-step", "step must be adjacent"),
    ("manifest-digest", "step_sha256 does not bind"),
    ("manifest-schema", "invalid prechips Features schema"),
    ("missing-receipt", "cannot read required file"),
    ("missing-feature", "cannot read required file"),
    ("missing-full-record", "missing full neutral record"),
    ("full-source-path", "source must be"),
])
def test_binding_failure_never_stages_any_feature_bundle(
    tmp_path: Path, corruption: str, diagnostic: str,
) -> None:
    out = bound_output(tmp_path)
    stage = tmp_path / "stage"
    shutil.copytree(out / "step", stage / "step")
    # Corrupt the final stem so earlier valid bundles cannot leak into staging.
    stem = export_features.SUPPORTED_PARTS[-1]
    dashed = stem.replace("_", "-")
    bundle = out / "features" / stem
    step = bundle / f"{dashed}.STEP"
    manifest = bundle / "features.toml"
    receipt_path = bundle / "neutral.json"
    receipt = json.loads(receipt_path.read_bytes())
    certificate_path = out / "reports" / "release-neutral.json"
    certificate = json.loads(certificate_path.read_bytes())
    full_step = out / "step" / step.name
    if corruption == "scoped-step-bytes":
        step.write_bytes(step.read_bytes().replace(b"ADVANCED_FACE", b"ADVANCED_FACX", 1))
    elif corruption == "feature-bytes":
        manifest.write_bytes(manifest.read_bytes().replace(b"# Generated", b"# generated", 1))
    elif corruption in {"full-step-bytes", "full-step-producer"}:
        full_step.write_bytes(full_step.read_bytes().replace(b"ADVANCED_FACE", b"ADVANCED_FACX", 1))
        if corruption == "full-step-producer":
            certificate["files"][f"step/{step.name}"] = byte_record(full_step)
            _rewrite(certificate_path, certificate)
    elif corruption in {"scoped-step-size", "feature-size"}:
        key = "step" if corruption == "scoped-step-size" else "features"
        receipt[key]["bytes"] += 1
        _rewrite(receipt_path, receipt)
    elif corruption == "full-step-size":
        certificate["files"][f"step/{step.name}"]["bytes"] += 1
        _rewrite(certificate_path, certificate)
    elif corruption == "exporter-identity":
        receipt["exporter"] = hashlib.md5(b"different producer").hexdigest()
        _rewrite(receipt_path, receipt)
    elif corruption == "requirement-sources":
        receipt["feature_sources_sha256"] = "0" * 64
        _rewrite(receipt_path, receipt)
    elif corruption in {"manifest-step", "manifest-digest", "manifest-schema"}:
        values = tomllib.loads(manifest.read_text(encoding="utf-8"))
        if corruption == "manifest-step":
            values["step"] = f"../../step/{step.name}"
        elif corruption == "manifest-digest":
            values["step_sha256"] = "unknown"
        else:
            values["unrecognized_field"] = "unknown"
        manifest.write_text(export_features._toml(values), encoding="utf-8")
        receipt["features"] = byte_record(manifest, scoped=True)
        _rewrite(receipt_path, receipt)
    elif corruption == "missing-receipt":
        receipt_path.unlink()
    elif corruption == "missing-feature":
        manifest.unlink()
    elif corruption == "missing-full-record":
        del certificate["files"][f"step/{step.name}"]
        _rewrite(certificate_path, certificate)
    else:
        certificate["files"][f"step/{step.name}"]["source"] = "cad/out/step/other.STEP"
        _rewrite(certificate_path, certificate)
    baseline = {path.name: path.read_bytes() for path in (stage / "step").iterdir()}
    with pytest.raises(features_bound.FeaturesBoundError, match=diagnostic):
        features_bound.check_bound_features(out)
    with pytest.raises(features_bound.FeaturesBoundError, match=diagnostic):
        features_bound.stage_bound_features(out, stage)
    assert not (stage / "features").exists()
    assert {path.name: path.read_bytes() for path in (stage / "step").iterdir()} == baseline


def test_stage_rejects_a_different_already_staged_full_step(tmp_path: Path) -> None:
    out = bound_output(tmp_path)
    stage = tmp_path / "stage"
    shutil.copytree(out / "step", stage / "step")
    staged_step = stage / "step" / "rocker-arm.STEP"
    staged_step.write_bytes(staged_step.read_bytes().replace(b"ADVANCED_FACE", b"ADVANCED_FACX", 1))
    # Both source producers agree; the baseline bundle is what has diverged.
    with pytest.raises(features_bound.FeaturesBoundError, match="baseline staged STEP differs"):
        features_bound.stage_bound_features(out, stage)
    assert not (stage / "features").exists()


def test_cli_missing_certificate_is_nonzero_and_actionable(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(Path(features_bound.__file__)), "--out", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "release-neutral.json" in result.stderr
    assert "regenerate package:features and export" in result.stderr
