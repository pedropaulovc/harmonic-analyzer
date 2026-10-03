"""Check and stage isolated feature bundles against the full neutral export.

SolidWorks never writes the same STEP bytes twice: the header stamps the write
time and every export renumbers its entities. The release-only gate therefore
compares what the feature contract needs. For each supported part, the scoped
STEP (``features/<stem>/<part>.STEP``) and the full export
(``step/<part>.STEP``) must carry the same feature -> face-label -> patch-count
map, read with ``step_face_sets``. ``features.toml`` must satisfy the pinned
prechips schema, bind the exact raw bytes of its adjacent scoped STEP, and
record that STEP's exact face sets per feature. Both raw digests are logged,
and every failure reports them. The gate never opens CAD or repairs either producer.
"""

from __future__ import annotations

import argparse
import hashlib
import tomllib
from collections import Counter
from pathlib import Path
from typing import NoReturn

from prechips.model import Features
from pydantic import ValidationError

import _telemetry
import export_features
from _export_feature_faces import FeatureFaceError, step_face_sets

OUT = export_features.OUT
_REBUILD = "regenerate package:features and export before releasing"
# A split periodic face labels each STEP half with its native name. The issue
# #1204 spike found the v38 rocker-arm pivot bore as two Ø6.5 halves, so a
# half-labelled split (one patch) must fail here, not ship a partial datum A.
_STEP_FACE_COUNTS = {"rocker_arm": {"pivot_bore": 2}}

FaceLabels = dict[str, Counter[str]]


class FeaturesBoundError(RuntimeError):
    """A feature bundle is missing, unbound, or disagrees with the full export."""


def _fail(label: str, detail: str) -> NoReturn:
    raise FeaturesBoundError(f"{label}: {detail}; {_REBUILD}")


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        _fail(str(path), f"cannot read required file ({exc.strerror})")


def _face_sets(path: Path, content: bytes, features: list[str], digests: str) -> dict[str, list[str]]:
    try:
        return step_face_sets(content.decode("latin-1"), features)
    except FeatureFaceError as exc:
        _fail(str(path), f"{exc} ({digests})")


def _face_labels(faces: dict[str, list[str]]) -> FaceLabels:
    # A face reference is ``#<entity>/ADVANCED_FACE[<ordinal>]/<label>``; only
    # the label survives a re-export, so entity ids and file order are dropped.
    return {
        feature: Counter(ref.rsplit("/", 1)[1] for ref in refs)
        for feature, refs in faces.items()
    }


def _validated_files(out: Path) -> tuple[tuple[Path, bytes], ...]:
    pending: list[tuple[Path, bytes]] = []
    for stem in export_features.SUPPORTED_PARTS:
        dashed = stem.replace("_", "-")
        directory = out / "features" / stem
        step_path = directory / f"{dashed}.STEP"
        manifest_path = directory / "features.toml"
        full_path = out / "step" / step_path.name
        step_bytes = _read(step_path)
        manifest_bytes = _read(manifest_path)
        full_bytes = _read(full_path)
        scoped_digest = hashlib.sha256(step_bytes).hexdigest()
        full_digest = hashlib.sha256(full_bytes).hexdigest()
        digests = f"scoped sha256 {scoped_digest}, full sha256 {full_digest}"
        try:
            manifest = tomllib.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeError, tomllib.TOMLDecodeError) as exc:
            _fail(str(manifest_path), f"invalid TOML ({exc})")
        try:
            validated = Features.model_validate(manifest)
        except ValidationError as exc:
            _fail(str(manifest_path), f"invalid feature manifest ({exc})")
        if manifest.get("step") != step_path.name:
            _fail(str(manifest_path), f"step must be adjacent basename {step_path.name!r}, recorded {manifest.get('step')!r}")
        if manifest.get("step_sha256") != scoped_digest:
            _fail(str(manifest_path), f"step_sha256 {manifest.get('step_sha256')!r} does not bind the adjacent STEP ({digests})")
        features = list(export_features.feature_selectors(stem))
        scoped_faces = _face_sets(step_path, step_bytes, features, digests)
        if set(validated.features) != set(features):
            _fail(str(manifest_path), f"feature names differ from scoped STEP contract ({digests})")
        for feature, refs in scoped_faces.items():
            recorded = validated.features[feature].faces
            if not isinstance(recorded, list) or set(recorded) != set(refs):
                _fail(str(manifest_path), f"{feature} faces {recorded!r} differ from adjacent STEP {refs!r} ({digests})")
        scoped = _face_labels(scoped_faces)
        full = _face_labels(_face_sets(full_path, full_bytes, features, digests))
        if scoped != full:
            differing = {
                feature: {"scoped": dict(scoped[feature]), "full": dict(full[feature])}
                for feature in features
                if scoped[feature] != full[feature]
            }
            _fail(stem, f"scoped and full STEP face labels differ {differing} ({digests})")
        for feature, expected in _STEP_FACE_COUNTS.get(stem, {}).items():
            actual = sum(scoped[feature].values())
            if actual != expected:
                _fail(stem, f"{feature} must be exactly {expected} STEP faces, found {actual} ({digests})")
        _telemetry.info(
            f"features-bound: {stem} face labels agree ({digests})",
            stem=stem, scoped_sha256=scoped_digest, full_sha256=full_digest,
        )
        pending.extend(((step_path, step_bytes), (manifest_path, manifest_bytes)))
    return tuple(pending)


def check_bound_features(out: Path | None = None) -> tuple[Path, ...]:
    """Validate every supported bundle without writing or repairing artifacts."""
    output = OUT if out is None else Path(out)
    with _telemetry.span("features_bound.validate", parts=len(export_features.SUPPORTED_PARTS)):
        return tuple(path for path, _content in _validated_files(output))


def stage_bound_features(out: Path, released: Path) -> list[Path]:
    """Validate all bundles, then stage the exact validated scoped bytes.

    Each bundle stages its scoped STEP and ``features.toml``; the snapshots
    read during validation are written, never a later read of the cache.
    """
    output, stage = Path(out), Path(released)
    with _telemetry.span("release.features_stage", parts=len(export_features.SUPPORTED_PARTS)):
        pending = _validated_files(output)
        staged = []
        for source, content in pending:
            target = stage / source.relative_to(output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            staged.append(target)
        return staged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT, help="export output root (default: cad/out)")
    args = parser.parse_args(argv)
    _telemetry.set_service("features-bound")
    _telemetry.configure()
    with _telemetry.run_pipeline_span("features_bound") as root:
        try:
            files = check_bound_features(args.out)
        except (FeaturesBoundError, OSError, ValueError) as exc:
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
            _telemetry.error(f"features-bound: {exc}")
            return 1
        _telemetry.info(f"features-bound: verified {len(export_features.SUPPORTED_PARTS)} bundles, {len(files)} files against the full export")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
