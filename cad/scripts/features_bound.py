"""Check and stage isolated feature bundles against the full neutral export.

The isolated producer owns the raw labelled STEP and its adjacent manifest.
Full export copies that STEP without rewriting it; the release-only gate
requires byte-identical scoped and neutral copies. ``features.toml`` must
satisfy the pinned prechips schema, bind its adjacent STEP's exact raw bytes,
and record that STEP's exact face sets per feature. Consumers derive feature
names from the produced manifest, never reload drawing declarations. Every
failure is loud; neither export nor the gate regenerates a missing bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import tomllib
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
_STEP_FACE_COUNTS = {"ch_rocker_arm": {"pivot_bore": 2}}


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


def _validated_bundles(out: Path) -> tuple[tuple[Path, bytes], ...]:
    """Read and validate the complete producer inventory before any copy."""
    pending: list[tuple[Path, bytes]] = []
    for stem in export_features.SUPPORTED_PARTS:
        manifest_path, step_path = export_features.bundle_paths(stem, out)
        step_bytes = _read(step_path)
        manifest_bytes = _read(manifest_path)
        scoped_digest = hashlib.sha256(step_bytes).hexdigest()
        digests = f"scoped sha256 {scoped_digest}"
        try:
            manifest = tomllib.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeError, tomllib.TOMLDecodeError) as exc:
            _fail(str(manifest_path), f"invalid TOML ({exc})")
        try:
            validated = Features.model_validate(manifest)
        except ValidationError as exc:
            _fail(str(manifest_path), f"invalid feature manifest ({exc})")
        if validated.part != stem.replace("_", "-"):
            _fail(str(manifest_path), f"part must identify {stem.replace('_', '-')!r}, recorded {validated.part!r}")
        if manifest.get("step") != step_path.name:
            _fail(str(manifest_path), f"step must be adjacent basename {step_path.name!r}, recorded {manifest.get('step')!r}")
        if manifest.get("step_sha256") != scoped_digest:
            _fail(str(manifest_path), f"step_sha256 {manifest.get('step_sha256')!r} does not bind the adjacent STEP ({digests})")
        features = list(validated.features)
        if not features:
            _fail(str(manifest_path), "feature manifest has no features")
        scoped_faces = _face_sets(step_path, step_bytes, features, digests)
        for feature, refs in scoped_faces.items():
            recorded = validated.features[feature].faces
            if not isinstance(recorded, list) or len(recorded) != len(refs) or set(recorded) != set(refs):
                _fail(str(manifest_path), f"{feature} faces {recorded!r} differ from adjacent STEP {refs!r} ({digests})")
        for feature, expected in _STEP_FACE_COUNTS.get(stem, {}).items():
            actual = len(scoped_faces.get(feature, ()))
            if actual != expected:
                _fail(stem, f"{feature} must be exactly {expected} STEP faces, found {actual} ({digests})")
        pending.extend(((step_path, step_bytes), (manifest_path, manifest_bytes)))
        # A multi-configuration part's per-configuration STEPs label the same features.
        for cfg_path in export_features.configuration_step_paths(stem, out).values():
            cfg_bytes = _read(cfg_path)
            cfg_digests = f"scoped sha256 {hashlib.sha256(cfg_bytes).hexdigest()}"
            cfg_faces = _face_sets(cfg_path, cfg_bytes, features, cfg_digests)
            unlabelled = sorted(feature for feature, refs in cfg_faces.items() if not refs)
            if unlabelled:
                _fail(str(cfg_path), f"labels no face for {unlabelled} ({cfg_digests})")
            pending.append((cfg_path, cfg_bytes))
    return tuple(pending)


def stage_feature_steps(out: Path, step_directory: Path) -> tuple[Path, ...]:
    """Copy every validated producer STEP to the neutral cache, byte-for-byte.

    All bundles must be complete and valid before the first destination is
    created. Copy the snapshots just validated, not a later read of the cache.
    """
    with _telemetry.span("export.feature_steps", parts=len(export_features.SUPPORTED_PARTS)):
        pending = _validated_bundles(Path(out))
        staged = []
        for source, content in pending:
            if source.suffix != ".STEP":
                continue
            target = Path(step_directory) / source.name
            if not target.is_file() or target.read_bytes() != content:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            staged.append(target)
        return tuple(staged)


def _validated_files(out: Path) -> tuple[tuple[Path, bytes], ...]:
    pending = _validated_bundles(out)
    for step_path, step_bytes in pending:
        if step_path.suffix != ".STEP":
            continue
        full_path = out / "step" / step_path.name
        full_bytes = _read(full_path)
        scoped_digest = hashlib.sha256(step_bytes).hexdigest()
        full_digest = hashlib.sha256(full_bytes).hexdigest()
        digests = f"scoped sha256 {scoped_digest}, full sha256 {full_digest}"
        if step_bytes != full_bytes:
            _fail(str(full_path), f"full STEP is not the exact scoped copy ({digests})")
        _telemetry.info(
            f"features-bound: {step_path.parent.name} exact STEP copy agrees ({digests})",
            stem=step_path.parent.name, scoped_sha256=scoped_digest, full_sha256=full_digest,
        )
    return pending


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
