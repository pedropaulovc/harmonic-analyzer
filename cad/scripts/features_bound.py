"""Check and stage isolated feature bundles against the full neutral export.

The isolated producer owns each raw labelled STEP and its face inventory
(``.faces.json``, bound to that STEP's sha256); the seat-free manifest step
owns ``features.toml``. Full export copies the STEPs without rewriting them
and reads no manifest; the release-only gate requires byte-identical scoped
and neutral copies. ``features.toml`` must identify its part, bind its
adjacent STEP's exact raw bytes, and record per feature STEP faces that exist
with that entity id, ordinal and label, covering every face their labels carry.
A member's own requirements bind that member's STEP (``member_steps``) the same
way. Consumers derive feature names from the produced manifest, never reload
drawing declarations. Every failure is loud; neither export nor the gate
regenerates a missing bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import tomllib
from pathlib import Path
from typing import NoReturn

import _config
import _telemetry
import export_features
from _export_feature_faces import FeatureFaceError, inventory_path, read_inventory, step_feature_refs_valid, step_label_refs

OUT = export_features.OUT
_REBUILD = "regenerate package:features and export before releasing"


class FeaturesBoundError(RuntimeError):
    """A feature bundle is missing, unbound, or disagrees with the full export."""


def _fail(label: str, detail: str) -> NoReturn:
    raise FeaturesBoundError(f"{label}: {detail}; {_REBUILD}")


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        _fail(str(path), f"cannot read required file ({exc.strerror})")


def _validated_step(path: Path) -> list[tuple[Path, bytes]]:
    """One labelled STEP and its inventory: the inventory binds the STEP's bytes,
    and its labels are exactly the STEP's face labels."""
    content = _read(path)
    inventory = _read(inventory_path(path))
    digests = f"scoped sha256 {hashlib.sha256(content).hexdigest()}"
    try:
        labels, _geometries = read_inventory(path)
        step_label_refs(content.decode("latin-1"), labels)
    except FeatureFaceError as exc:
        _fail(str(path), f"{exc} ({digests})")
    return [(path, content), (inventory_path(path), inventory)]


def _validated_steps(out: Path, stems: tuple[str, ...] | None = None) -> tuple[tuple[Path, bytes], ...]:
    """Every exported STEP and inventory, validated before any copy."""
    return tuple(
        item
        for stem in (export_features.SUPPORTED_PARTS if stems is None else stems)
        for path in export_features.exported_steps(stem, out)
        for item in _validated_step(path)
    )


def _validated_bundles(out: Path, stems: tuple[str, ...] | None = None) -> tuple[tuple[Path, bytes], ...]:
    """Read and validate the complete producer inventory and manifests before any copy."""
    pending: list[tuple[Path, bytes]] = []
    for stem in export_features.SUPPORTED_PARTS if stems is None else stems:
        steps = dict(_validated_steps(out, (stem,)))
        manifest_path, step_path = export_features.bundle_paths(stem, out)
        manifest_bytes = _read(manifest_path)
        scoped_digest = hashlib.sha256(steps[step_path]).hexdigest()
        digests = f"scoped sha256 {scoped_digest}"
        try:
            manifest = tomllib.loads(manifest_bytes.decode("utf-8"))
        except (UnicodeError, tomllib.TOMLDecodeError) as exc:
            _fail(str(manifest_path), f"invalid TOML ({exc})")
        part = manifest.get("part")
        if part != stem.replace("_", "-"):
            _fail(str(manifest_path), f"part must identify {stem.replace('_', '-')!r}, recorded {part!r}")
        if manifest.get("step") != step_path.name:
            _fail(str(manifest_path), f"step must be adjacent basename {step_path.name!r}, recorded {manifest.get('step')!r}")
        if manifest.get("step_sha256") != scoped_digest:
            _fail(str(manifest_path), f"step_sha256 {manifest.get('step_sha256')!r} does not bind the adjacent STEP ({digests})")
        table = manifest.get("features")
        declared = stem in export_features.DECLARED_PARTS
        if not isinstance(table, dict):
            _fail(str(manifest_path), "feature manifest has no features table")
        if declared and not table:
            _fail(str(manifest_path), "feature manifest has no features")
        if not declared and table:
            _fail(str(manifest_path), f"draw_{stem} declares no requirement, but the manifest lists features {sorted(table)}")
        if not all(isinstance(entry, dict) for entry in table.values()):
            _fail(str(manifest_path), "every feature must be a table")
        members = export_features.member_step_paths(stem, out)
        recorded_members = manifest.get("member_steps", {})
        if not isinstance(recorded_members, dict) or set(recorded_members) != set(members):
            _fail(str(manifest_path), f"member_steps {sorted(recorded_members) if isinstance(recorded_members, dict) else recorded_members!r} must be {sorted(members)}")
        for cfg, member_path in members.items():
            entry = recorded_members[cfg]
            member_digest = hashlib.sha256(steps[member_path]).hexdigest()
            if not isinstance(entry, dict) or entry.get("step") != member_path.name or entry.get("step_sha256") != member_digest:
                _fail(str(manifest_path), f"member_steps.{cfg} {entry!r} does not bind {member_path.name} (scoped sha256 {member_digest})")
        scopes = {None: step_path, **members}
        stray = sorted(name for name, entry in table.items() if entry.get("configuration", None) not in scopes)
        if stray:
            _fail(str(manifest_path), f"features {stray} name no exported member configuration")
        for cfg, scoped in scopes.items():
            recorded = {name: entry.get("faces") for name, entry in table.items() if entry.get("configuration", None) == cfg}
            malformed = sorted(name for name, faces in recorded.items() if not isinstance(faces, list) or not faces)
            if malformed:
                _fail(str(manifest_path), f"{malformed} faces must be nonempty lists of STEP face refs")
            problems = step_feature_refs_valid(steps[scoped].decode("latin-1"), recorded)
            if problems:
                _fail(str(manifest_path), f"{'; '.join(problems)} (scoped sha256 {hashlib.sha256(steps[scoped]).hexdigest()})")
        for feature, expected in export_features.STEP_FACE_COUNTS.get(stem, {}).items():
            actual = len(table[feature]["faces"]) if feature in table else expected
            if actual != expected:
                _fail(stem, f"{feature} must be exactly {expected} STEP faces, found {actual} ({digests})")
        pending.extend(steps.items())
        pending.append((manifest_path, manifest_bytes))
    return tuple(pending)


def stage_feature_steps(out: Path, step_directory: Path) -> dict[Path, str]:
    """Copy every validated producer STEP to the neutral cache, byte-for-byte.

    Every STEP and face inventory must be complete and agree before the first
    destination is created; manifests are not read, so a declaration edit never
    touches the export. Copy the snapshots just validated, not a later read of
    the cache, and return each destination with its validated snapshot's SHA-256.
    """
    with _telemetry.span("export.feature_steps", parts=len(export_features.SUPPORTED_PARTS)):
        pending = _validated_steps(Path(out))
        staged: dict[Path, str] = {}
        for source, content in pending:
            if source.suffix != ".STEP":
                continue
            target = Path(step_directory) / source.name
            if not target.is_file() or target.read_bytes() != content:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            staged[target] = hashlib.sha256(content).hexdigest()
        return staged


def validate_bundle(stem: str, out: Path) -> tuple[tuple[Path, bytes], ...]:
    """Validate one part's bundle on its own (identity, STEP binding, face sets)."""
    stem = stem.replace("-", "_")
    if stem not in export_features.SUPPORTED_PARTS:
        _fail(stem, "not a part with a feature bundle")
    return _validated_bundles(Path(out), (stem,))


def _validated_files(out: Path) -> tuple[tuple[Path, bytes], ...]:
    pending = _validated_bundles(out)
    revision = _config.release_revision()
    for path, content in pending:
        if path.name != "features.toml":
            continue
        recorded = tomllib.loads(content.decode("utf-8")).get("drawing", {}).get("revision")
        if recorded != revision:
            _fail(str(path), f"stale bundle: drawing revision {recorded!r}, releasing {revision!r}")
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

    Each bundle stages its scoped STEPs, their face inventories and
    ``features.toml``; the snapshots read during validation are written, never
    a later read of the cache.
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
