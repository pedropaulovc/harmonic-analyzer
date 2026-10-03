"""Check and stage isolated feature bundles against the full neutral export.

The release-only gate reads certificates and exact bytes; it never opens CAD,
imports the full exporter, or repairs divergent producers. Each released bundle
keeps its adjacent STEP, features.toml and original neutral.json receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any, NoReturn

from prechips.model import Features

import _telemetry
import export_features

OUT = export_features.OUT
FEATURE_NEUTRAL_SCHEMA = "harmonic-analyzer/features-neutral@1"
RELEASE_NEUTRAL_SCHEMA = "harmonic-analyzer/release-neutral@3"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RECEIPT_FIELDS = {
    "schema", "stem", "exporter", "feature_sources_sha256", "drawing_revision",
    "native_sha256", "step", "features",
}
_REBUILD = "regenerate package:features and export before releasing"


class FeaturesBoundError(RuntimeError):
    """A feature bundle is missing, stale, malformed or producer-divergent."""


def _fail(label: str, detail: str) -> NoReturn:
    raise FeaturesBoundError(f"{label}: {detail}; {_REBUILD}")


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        _fail(str(path), f"cannot read required file ({exc.strerror})")


def _json(path: Path, content: bytes) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (ValueError, UnicodeError) as exc:
        _fail(str(path), f"invalid JSON ({exc})")
    if not isinstance(value, dict):
        _fail(str(path), "certificate must be a JSON object")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(label, "requires a known lowercase SHA-256")
    return value


def _producer(value: Any, label: str) -> str:
    # Full export's producer identity is an MD5 closure digest, not a SHA-256.
    if not isinstance(value, str) or not value.strip() or value.strip() == "unknown":
        _fail(label, "requires a known exporter identity")
    return value


def _certified_bytes(path: Path, record: Any, label: str) -> tuple[bytes, str]:
    if not isinstance(record, dict):
        _fail(label, "missing byte-integrity record")
    expected_size = record.get("bytes")
    if type(expected_size) is not int or expected_size <= 0:
        _fail(label, "bytes must be a known positive integer")
    expected_digest = _sha256(record.get("sha256"), f"{label}.sha256")
    content = _read(path)
    if len(content) != expected_size:
        _fail(label, f"byte size differs: recorded {expected_size}, actual {len(content)}")
    digest = hashlib.sha256(content).hexdigest()
    if digest != expected_digest:
        _fail(label, f"SHA-256 differs: recorded {expected_digest}, actual {digest}")
    return content, digest


def _validated_files(out: Path) -> tuple[tuple[Path, bytes], ...]:
    certificate_path = out / "reports" / "release-neutral.json"
    certificate = _json(certificate_path, _read(certificate_path))
    if certificate.get("schema") != RELEASE_NEUTRAL_SCHEMA:
        _fail(str(certificate_path), f"unsupported schema {certificate.get('schema')!r}")
    producer = _producer(certificate.get("exporter"), f"{certificate_path}: exporter")
    full_records = certificate.get("files")
    if not isinstance(full_records, dict):
        _fail(str(certificate_path), "missing full neutral file records")
    sources_digest = _sha256(
        export_features.feature_sources_sha256(), "current feature_sources_sha256",
    )
    pending: list[tuple[Path, bytes]] = []
    for stem in export_features.SUPPORTED_PARTS:
        dashed = stem.replace("_", "-")
        directory = out / "features" / stem
        receipt_path = directory / "neutral.json"
        receipt_bytes = _read(receipt_path)
        receipt = _json(receipt_path, receipt_bytes)
        label = str(receipt_path)
        if set(receipt) != _RECEIPT_FIELDS:
            missing = sorted(_RECEIPT_FIELDS - receipt.keys())
            extra = sorted(receipt.keys() - _RECEIPT_FIELDS)
            _fail(label, f"receipt fields differ: missing {missing}, unexpected {extra}")
        if receipt["schema"] != FEATURE_NEUTRAL_SCHEMA:
            _fail(label, f"unsupported schema {receipt['schema']!r}")
        if receipt["stem"] != stem:
            _fail(label, f"stem differs: expected {stem!r}, recorded {receipt['stem']!r}")
        receipt_producer = _producer(receipt["exporter"], f"{label}: exporter")
        if receipt_producer != producer:
            _fail(label, f"exporter differs from full certificate: scoped {receipt_producer!r}, full {producer!r}")
        recorded_sources = _sha256(receipt["feature_sources_sha256"], f"{label}: feature_sources_sha256")
        if recorded_sources != sources_digest:
            _fail(label, "feature sources changed since the scoped export")
        _sha256(receipt["native_sha256"], f"{label}: native_sha256")
        revision = receipt["drawing_revision"]
        if not isinstance(revision, str) or not revision:
            _fail(label, "drawing_revision must preserve the exported revision or 'unknown'")
        step_path = directory / f"{dashed}.STEP"
        manifest_path = directory / "features.toml"
        contents: dict[str, bytes] = {}
        for key, path in (("step", step_path), ("features", manifest_path)):
            record = receipt[key]
            if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
                _fail(label, f"{key} requires exactly path, bytes and sha256")
            if record["path"] != path.name:
                _fail(label, f"{key}.path must be adjacent basename {path.name!r}, recorded {record['path']!r}")
            contents[key], _digest = _certified_bytes(path, record, f"{label}: {key}")
        step_digest = receipt["step"]["sha256"]
        try:
            manifest = Features.model_validate(tomllib.loads(contents["features"].decode("utf-8")))
        except (UnicodeError, ValueError) as exc:
            _fail(str(manifest_path), f"invalid prechips Features schema ({exc})")
        if manifest.part != dashed:
            _fail(str(manifest_path), f"part differs: expected {dashed!r}, recorded {manifest.part!r}")
        if manifest.step != step_path.name:
            _fail(str(manifest_path), f"step must be adjacent basename {step_path.name!r}, recorded {manifest.step!r}")
        if manifest.step_sha256 != step_digest:
            _fail(str(manifest_path), "step_sha256 does not bind the certified scoped STEP bytes")
        if not manifest.features:
            _fail(str(manifest_path), "feature manifest has no features")
        if stem != "pivot_bracket" and (
            manifest.drawing == "unknown" or manifest.drawing.revision != revision
        ):
            _fail(str(manifest_path), "drawing revision differs from the scoped export receipt")
        full_path = out / "step" / step_path.name
        destination = f"step/{step_path.name}"
        full_record = full_records.get(destination)
        if not isinstance(full_record, dict):
            _fail(str(certificate_path), f"missing full neutral record {destination!r}")
        expected_source = (
            full_path.resolve().relative_to(export_features.REPO.resolve()).as_posix()
            if full_path.resolve().is_relative_to(export_features.REPO.resolve())
            else f"cad/out/{destination}"
        )
        if full_record.get("source") != expected_source:
            _fail(str(certificate_path), f"{destination} source must be {expected_source!r}, recorded {full_record.get('source')!r}")
        full_bytes, full_digest = _certified_bytes(full_path, full_record, f"{certificate_path}: {destination}")
        if len(full_bytes) != len(contents["step"]) or full_digest != step_digest:
            _fail(stem, f"scoped STEP and full STEP producers diverged: scoped {step_digest}, full {full_digest}")
        pending.extend(((step_path, contents["step"]), (manifest_path, contents["features"]), (receipt_path, receipt_bytes)))
    return tuple(pending)


def check_bound_features(out: Path | None = None) -> tuple[Path, ...]:
    """Validate every supported bundle without writing or repairing artifacts."""
    output = OUT if out is None else Path(out)
    with _telemetry.span("features_bound.validate", parts=len(export_features.SUPPORTED_PARTS)):
        return tuple(path for path, _content in _validated_files(output))


def stage_bound_features(out: Path, released: Path) -> list[Path]:
    """Validate all bundles, then stage their exact bytes after baseline neutrals.

    Validation includes the already-staged full STEP bytes. Snapshots of all
    validated scoped files are copied, not unverified later reads of the cache.
    """
    output, stage = Path(out), Path(released)
    with _telemetry.span("release.features_stage", parts=len(export_features.SUPPORTED_PARTS)):
        pending = _validated_files(output)
        for source, content in pending:
            if source.suffix == ".STEP":
                staged_step = stage / "step" / source.name
                if _read(staged_step) != content:
                    _fail(str(staged_step), "baseline staged STEP differs from the bound feature bundle")
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
