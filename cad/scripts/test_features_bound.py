"""Offline regressions for binding scoped feature bundles to the full export."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import export_features
import features_bound
from _export_feature_faces import face_name


def _labels(stem: str, *, pivot_bore_faces: int = 2) -> list[str]:
    """One face per feature; the split rocker pivot bore labels both halves."""
    labels = [face_name(feature, 1) for feature in export_features.feature_selectors(stem)]
    if stem == "rocker_arm":
        labels.extend([face_name("pivot_bore", 1)] * (pivot_bore_faces - 1))
    return labels


def _step(name: str, labels: list[str], *, stamp: str, first: int, stride: int) -> bytes:
    """A STEP the way two separate SolidWorks writes differ: own header time,
    own entity numbering, own face order. Unnamed faces carry ``'NONE'``."""
    rows = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION (( 'STEP AP214' ), '1' );",
        f"FILE_NAME ('{name}', '{stamp}', ( '' ), ( '' ), 'SwSTEP 2.0', 'SolidWorks 2026', '' );",
        "FILE_SCHEMA (( 'AUTOMOTIVE_DESIGN' ));",
        "ENDSEC;",
        "DATA;",
    ]
    for index, label in enumerate(["NONE", *labels, "NONE"]):
        entity = first + stride * index
        rows.append(f"#{entity} = ADVANCED_FACE ( '{label}', ( #{entity + 1} ), #{entity + 2}, .T. ) ;")
    rows.extend(("ENDSEC;", "END-ISO-10303-21;"))
    return "\n".join(rows).encode("ascii")


def _add_full_face(out: Path, stem: str, label: str) -> Path:
    """Add one labelled face to the full export only; its manifest is unaffected."""
    full = out / "step" / f"{stem.replace('_', '-')}.STEP"
    content = full.read_bytes()
    row = f"#99999 = ADVANCED_FACE ( '{label}', ( #1 ), #2, .T. ) ;\n".encode("ascii")
    index = content.rindex(b"ENDSEC;")
    full.write_bytes(content[:index] + row + content[index:])
    return full


def bound_output(tmp_path: Path, *, pivot_bore_faces: int = 2) -> Path:
    """Scoped and full exports with distinct raw bytes and the same face labels.

    Manifests come from the real generator reading the scoped STEP it binds.
    """
    out = tmp_path / "cad" / "out"
    for stem in export_features.SUPPORTED_PARTS:
        labels = _labels(stem, pivot_bore_faces=pivot_bore_faces)
        name = f"{stem.replace('_', '-')}.STEP"
        step = out / "features" / stem / name
        step.parent.mkdir(parents=True)
        step.write_bytes(_step(name, labels, stamp="2026-10-01T22:03:24", first=10, stride=1))
        full = out / "step" / name
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(_step(name, labels[::-1], stamp="2026-10-03T05:26:08", first=400, stride=7))
        export_features.write_manifest(stem, step, revision="v38")
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


def test_independent_exports_bind_and_stage_exact_scoped_bytes(tmp_path: Path) -> None:
    out = bound_output(tmp_path)
    for stem in export_features.SUPPORTED_PARTS:
        scoped, full = _digests(out, stem)
        assert scoped != full
    stage = tmp_path / "stage"

    checked = features_bound.check_bound_features(out)
    staged = features_bound.stage_bound_features(out, stage)

    expected = {
        relative: content
        for relative, content in _tree(out).items()
        if relative.startswith("features/")
    }
    assert len(checked) == len(staged) == len(expected) == 2 * len(export_features.SUPPORTED_PARTS)
    assert _tree(stage) == expected
    for stem in export_features.SUPPORTED_PARTS:
        assert {path.name for path in (stage / "features" / stem).iterdir()} == {
            f"{stem.replace('_', '-')}.STEP", "features.toml",
        }


@pytest.mark.parametrize(("mismatch", "diagnostic"), [
    ("label-set", "face labels differ"),
    ("patch-count", "face labels differ"),
    ("adjacent-digest", "does not bind the adjacent STEP"),
])
def test_unbound_bundle_never_stages_or_repairs(
    tmp_path: Path, mismatch: str, diagnostic: str,
) -> None:
    out = bound_output(tmp_path)
    # The final stem diverges so earlier valid bundles cannot leak into staging.
    stem = export_features.SUPPORTED_PARTS[-1]
    feature = next(iter(export_features.feature_selectors(stem)))
    if mismatch == "label-set":
        _add_full_face(out, stem, face_name(feature, 2))
    elif mismatch == "patch-count":
        _add_full_face(out, stem, face_name(feature, 1))
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
        assert f"scoped sha256 {scoped}, full sha256 {full}" in str(caught.value)
    assert not stage.exists()
    assert _tree(out) == before


def test_half_labelled_rocker_pivot_bore_fails_even_when_both_exports_agree(
    tmp_path: Path,
) -> None:
    out = bound_output(tmp_path, pivot_bore_faces=1)
    with pytest.raises(features_bound.FeaturesBoundError, match="pivot_bore must be exactly 2 STEP faces, found 1"):
        features_bound.check_bound_features(out)


def test_cli_exit_status_is_actionable(tmp_path: Path) -> None:
    script = str(Path(features_bound.__file__))
    missing = subprocess.run(
        [sys.executable, script, "--out", str(tmp_path / "missing")],
        capture_output=True, text=True, check=False,
    )
    assert missing.returncode == 1
    assert "cannot read required file" in missing.stderr
    assert "regenerate package:features and export" in missing.stderr

    bound = subprocess.run(
        [sys.executable, script, "--out", str(bound_output(tmp_path))],
        capture_output=True, text=True, check=False,
    )
    assert bound.returncode == 0, bound.stderr
