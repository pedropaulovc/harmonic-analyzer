"""Offline behavior of drawing requirements and their certified STEP binding."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

import pytest
from prechips.model import Features

import export_features as exporter
import rocker_arm_notes
from _export_feature_faces import FeatureFaceError, face_name


def _certified(tmp_path: Path, parts: tuple[str, ...] = ("rocker_arm",)) -> Path:
    output = tmp_path / "out"
    source_digest = exporter.feature_sources_sha256()
    for stem in parts:
        labels = [face_name(feature, 1) for feature in exporter.feature_selectors(stem)]
        if stem == "rocker_arm":
            labels.insert(0, face_name("pivot_bore", 1))
        rows = ["ISO-10303-21;", "HEADER;", "ENDSEC;", "DATA;"]
        rows += [f"#{index} = ADVANCED_FACE('{label}',(#1),#2,.T.);" for index, label in enumerate(labels, start=10)]
        rows += ["ENDSEC;", "END-ISO-10303-21;"]
        content = "\n".join(rows).encode("utf-8")
        dashed = stem.replace("_", "-")
        path = output / "features" / stem / f"{dashed}.STEP"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        (path.parent / "neutral.json").write_text(json.dumps({
            "schema": "harmonic-analyzer/features-neutral@1",
            "stem": stem,
            "exporter": "exporter-v1",
            "feature_sources_sha256": source_digest,
            "drawing_revision": "v38",
            "native_sha256": "a" * 64,
            "step": {"path": path.name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()},
        }), encoding="utf-8")
    return output


def _load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_rocker_bands_respect_native_nominals_and_displayed_general_rows() -> None:
    manifest = exporter.requirement_manifest("rocker-arm")
    features = manifest["features"]
    assert manifest["general_tolerances"]["linear_1pl"] == 0.8
    assert manifest["general_tolerances"]["linear_2pl"] == 0.51
    assert manifest["general_tolerances"]["linear_3pl"] == 0.13
    assert features["hub_od"]["dia"] == [9.69, 10.71]
    assert features["hub_faces"]["length"] == [7.0565, 7.1065]
    assert features["hub_faces"]["length_nominal"] == 7.0565
    assert features["profile_outer"]["tip_land"] == [5.08, 6.10]
    assert features["rod_hole"]["dia"] == [1.994, 2.094]
    assert features["rod_hole"]["nominal_dia"] == 1.994
    assert features["rod_hole"]["precision"]["dia"] == 2
    assert features["pivot_bore"]["dia"] == [6.50, 6.53]
    assert features["rod_hole"]["at"] == pytest.approx([133.06740213488345, 16.456064115939025, 0.0])


def test_unknown_requirement_and_reference_do_not_acquire_acceptance_bands() -> None:
    features = exporter.requirement_manifest("rocker_arm")["features"]
    assert features["profile_outer"]["land_angle_deg"] == "unknown"
    assert "land_angle_deg" in features["profile_outer"]["requirements"]
    assert "depth_ref" not in features["profile_outer"]["requirements"]
    assert "centre_from_pivot_ref" not in features["top_edge"]["requirements"]
    shaft = exporter.requirement_manifest("pivot_shaft")
    assert "length" not in shaft["features"]["pivot_bearing"]["requirements"]
    assert shaft["datums"] == {}
    assert shaft["features"]["north_relief"]["dia"] == [5.57, 5.83]
    assert shaft["features"]["pivot_journal"]["length"] == [5.2, 6.8]


def test_bracket_without_drawing_preserves_unknown_acceptance() -> None:
    manifest = exporter.requirement_manifest("pivot_bracket")
    assert manifest["drawing"]["revision"] == "unknown"
    assert manifest["datums"] == "unknown"
    assert manifest["features"]["shaft_bore"]["nominal_dia"] == 6.5
    assert manifest["features"]["shaft_bore"]["dia"] == "unknown"
    assert manifest["features"]["hold_down_1"]["station"] == "unknown"
    assert all(feature["requirements"] == "unknown" for feature in manifest["features"].values())


def test_cone_native_tolerances_and_angularity_are_not_position_or_general_bands() -> None:
    features = exporter.requirement_manifest("cone_pivot_post")["features"]
    crank = features["crank_bore"]
    assert crank["dia"] == [11.413, 11.443]
    assert features["journal_bore"]["dia"] == [12.2558, 12.2858]
    assert features["journal_bore"]["height"] == [33.118, 33.618]
    assert crank["separation"] == [39.332, 39.702]
    assert crank["angularity_dia"] == 0.10
    assert crank["angularity_datums"] == ["A", "B"]
    assert "angularity_dia" in crank["requirements"]
    assert "position_dia" not in crank
    assert "height" not in crank["requirements"]  # crank height is REF, not a second chain
    assert "unknown" in features["journal_bore"]["requirements"]
    assert features["mount_west"]["dia"] == [7.14248, 7.24248]
    assert features["mount_west"]["nominal_dia"] == 7.14248
    assert features["mount_west"]["precision"]["dia"] == 2


@pytest.mark.parametrize("stem", exporter.SUPPORTED_PARTS)
def test_certified_step_binds_split_patches_without_importing_part_documents(tmp_path: Path, stem: str) -> None:
    output = _certified(tmp_path, (stem,))
    paths = exporter.write_manifests([stem.replace("_", "-")], out=output)
    bundle = output / "features" / stem
    assert paths == [bundle / "features.toml"]
    manifest = _load(paths[0])
    loaded = Features.model_validate(manifest)
    if stem == "rocker_arm":
        assert loaded.features["pivot_bore"].faces == [
            "#10/ADVANCED_FACE[1]/HAF_PIVOT_BORE__P01",
            "#11/ADVANCED_FACE[2]/HAF_PIVOT_BORE__P01",
        ]
    step = bundle / f"{stem.replace('_', '-')}.STEP"
    assert manifest["step"] == step.name
    assert (paths[0].parent / manifest["step"]).read_bytes() == step.read_bytes()
    assert manifest["step_sha256"] == hashlib.sha256(step.read_bytes()).hexdigest()
    assert manifest["drawing"]["revision"] == ("unknown" if stem == "pivot_bracket" else "v38")
    assert manifest["cite"]["step_sha256"] == [
        f"harmonic-analyzer/cad/out/features/{stem}/neutral.json",
        f"harmonic-analyzer/cad/out/features/{stem}/{step.name}",
    ]
    receipt_path = bundle / "neutral.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    content = paths[0].read_bytes()
    receipt["features"] = {"path": "features.toml", "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_bytes = receipt_path.read_bytes()
    assert exporter.write_manifests([stem], out=output) == paths
    assert paths[0].read_bytes() == content
    assert receipt_path.read_bytes() == receipt_bytes
    with pytest.raises(ValueError, match="unsupported"):
        exporter.write_manifests([stem, "unrelated_part"], out=output)
    assert paths[0].read_bytes() == content


def test_certified_step_preserves_ansi_metadata_and_binds_ascii_face_labels(tmp_path: Path) -> None:
    output = _certified(tmp_path)
    step = output / "features" / "rocker_arm" / "rocker-arm.STEP"
    prefix, suffix = step.read_bytes().split(b"HEADER;\n", 1)
    content = prefix + b"HEADER;\nFILE_DESCRIPTION(('M\xe9tal \x80 metadata'),'2;1');\n" + suffix
    step.write_bytes(content)
    certificate_path = step.parent / "neutral.json"
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    record = certificate["step"]
    record["bytes"] = len(content)
    record["sha256"] = hashlib.sha256(content).hexdigest()
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    path = exporter.write_manifests(["rocker_arm"], out=output)[0]
    manifest = _load(path)
    assert manifest["features"]["pivot_bore"]["faces"] == [
        "#10/ADVANCED_FACE[1]/HAF_PIVOT_BORE__P01",
        "#11/ADVANCED_FACE[2]/HAF_PIVOT_BORE__P01",
    ]
    assert manifest["step_sha256"] == record["sha256"]
    assert step.read_bytes() == content


@pytest.mark.parametrize("corruption", [
    "content", "size", "hash", "path", "step_record", "schema", "stem", "exporter",
    "native_sha256", "missing_native_sha256", "drawing_revision",
    "feature_sources_sha256", "missing_feature_sources_sha256",
    "missing_receipt", "invalid_json", "non_object_receipt",
    "features_content", "features_size", "features_hash", "features_path",
    "features_record", "missing_features", "features_requirements",
])
def test_certificate_drift_never_overwrites_existing_manifest(tmp_path: Path, corruption: str) -> None:
    output = _certified(tmp_path)
    existing = exporter.write_manifests(["rocker_arm"], out=output)[0]
    previous = existing.read_bytes()
    certificate_path = existing.parent / "neutral.json"
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate["features"] = {
        "path": "features.toml", "bytes": len(previous), "sha256": hashlib.sha256(previous).hexdigest(),
    }
    record = certificate["step"]
    if corruption == "content":
        step = existing.parent / "rocker-arm.STEP"
        step.write_bytes(step.read_bytes().replace(b"PIVOT_BORE", b"WRONG_BORE"))
    elif corruption == "size":
        record["bytes"] += 1
    elif corruption == "hash":
        record["sha256"] = "0" * 64
    elif corruption == "path":
        record["path"] = "../step/rocker-arm.STEP"
    elif corruption == "step_record":
        del certificate["step"]
    elif corruption == "stem":
        certificate["stem"] = "pivot_shaft"
    elif corruption == "exporter":
        del certificate["exporter"]
    elif corruption in {"native_sha256", "feature_sources_sha256"}:
        certificate[corruption] = "invalid"
    elif corruption in {"missing_native_sha256", "missing_feature_sources_sha256"}:
        del certificate[corruption.removeprefix("missing_")]
    elif corruption == "drawing_revision":
        certificate["drawing_revision"] = None
    elif corruption == "features_content":
        existing.write_bytes(previous + b"# changed after certification\n")
        previous = existing.read_bytes()
    elif corruption == "features_size":
        certificate["features"]["bytes"] += 1
    elif corruption == "features_hash":
        certificate["features"]["sha256"] = "0" * 64
    elif corruption == "features_path":
        certificate["features"]["path"] = "other.toml"
    elif corruption == "features_record":
        certificate["features"] = None
    elif corruption == "features_requirements":
        certificate["drawing_revision"] = "v999"
    elif corruption == "schema":
        certificate["schema"] = "unknown"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    if corruption == "missing_receipt":
        certificate_path.unlink()
    elif corruption == "invalid_json":
        certificate_path.write_text("{broken", encoding="utf-8")
    elif corruption == "non_object_receipt":
        certificate_path.write_text("[]", encoding="utf-8")
    elif corruption == "missing_features":
        existing.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        exporter.write_manifests(["rocker_arm"], out=output)
    if corruption == "missing_features":
        assert not existing.exists()
    else:
        assert existing.read_bytes() == previous


def test_all_requested_manifests_validate_before_any_write(tmp_path: Path) -> None:
    output = _certified(tmp_path, ("rocker_arm", "pivot_shaft"))
    path = output / "features" / "pivot_shaft" / "pivot-shaft.STEP"
    text = path.read_text(encoding="utf-8").replace(face_name("north_dome", 1), "NONE")
    path.write_text(text, encoding="utf-8")
    certificate_path = path.parent / "neutral.json"
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate["step"].update({"bytes": len(path.read_bytes()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    existing = output / "features" / "rocker_arm" / "features.toml"
    existing.write_bytes(b"previous certified output")
    with pytest.raises(FeatureFaceError, match="north_dome"):
        exporter.write_manifests(["rocker_arm", "pivot_shaft"], out=output)
    assert existing.read_bytes() == b"previous certified output"
    assert not (path.parent / "features.toml").exists()


@pytest.mark.parametrize("revision", ["v38", "unknown"])
def test_certificate_revision_is_preserved_not_rebound_to_current_config(tmp_path: Path, monkeypatch, revision: str) -> None:
    output = _certified(tmp_path)
    monkeypatch.setattr(exporter._config, "release_revision", lambda: "v999")
    certificate_path = output / "features" / "rocker_arm" / "neutral.json"
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate["drawing_revision"] = revision
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    path = exporter.write_manifests(["rocker_arm"], out=output)[0]
    assert _load(path)["drawing"]["revision"] == revision
    del certificate["drawing_revision"]
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")
    path = exporter.write_manifests(["rocker_arm"], out=output)[0]
    assert _load(path)["drawing"]["revision"] == "unknown"


def test_construction_requires_explicit_permission_in_actual_notes(monkeypatch) -> None:
    assert exporter.requirement_manifest("rocker_arm")["construction"] == "one_piece"
    permission = "BUILT-UP CONSTRUCTION IS PERMITTED."
    monkeypatch.setattr(rocker_arm_notes, "BUILT_UP_PERMISSION_NOTE", permission)
    with pytest.raises(ValueError, match="explicit text in DRAWING_NOTES"):
        exporter.requirement_manifest("rocker_arm")
    monkeypatch.setattr(rocker_arm_notes, "DRAWING_NOTES", rocker_arm_notes.DRAWING_NOTES + "\n" + permission)
    assert exporter.requirement_manifest("rocker_arm")["construction"] == "built_up_permitted"


def test_cli_selects_only_requested_part_and_rejects_unknown_stem(tmp_path: Path, monkeypatch, capsys) -> None:
    output = _certified(tmp_path, ("rocker_arm", "pivot_shaft"))
    monkeypatch.setattr(exporter, "OUT", output)
    assert exporter.main(["--parts", "pivot-shaft"]) == 0
    assert _load(output / "features" / "pivot_shaft" / "features.toml")["part"] == "pivot-shaft"
    assert not (output / "features" / "rocker_arm" / "features.toml").exists()
    assert str(output / "features" / "pivot_shaft" / "features.toml") in capsys.readouterr().out
    with pytest.raises(ValueError, match="unsupported"):
        exporter.main(["--parts", "not_a_part"])


def test_source_fingerprint_tracks_citation_bytes_but_not_checkout_eols_or_revision(tmp_path: Path, monkeypatch) -> None:
    # Substitute only the source inventory; production normalization stays in
    # the pure manifest reader and never imports the build/COM runtime.
    config = tmp_path / "cad" / "config"
    config.mkdir(parents=True)
    source = config / "title_block.yaml"
    release = config / "release.yaml"
    source.write_bytes(b"linear: 0.51\n")
    release.write_bytes(b"next_revision: v38\n")
    monkeypatch.setattr(exporter, "REPO", tmp_path)
    monkeypatch.setattr(exporter._config, "CONFIG_DIR", config)
    monkeypatch.setattr(exporter, "source_paths", lambda: (source, release))
    original = exporter.feature_sources_sha256()
    source.write_bytes(b"linear: 0.51\r\n")
    assert exporter.feature_sources_sha256() == original
    release.write_bytes(b"next_revision: v40\n")
    assert exporter.feature_sources_sha256() == original
    source.write_bytes(b"# Moves the cited line\nlinear: 0.51\n")
    assert exporter.feature_sources_sha256() != original
