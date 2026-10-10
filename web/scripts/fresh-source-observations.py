"""Current-only source observations; historical receipts have a separate loader.

The Node validator owns the shared authority/source boundary used by verify-sync.
The inventory is an exact-byte sealed exporter result, never a second approval.
Fresh observations are gzip-only and use the existing deterministic encoder.
Stored gzip and decoded authored JSON have separate exact-byte hashes; decoding
never reparses/reserializes JSON or falls back to a plain or archived record.
Assembly metadata is compiled by the live TypeScript domain through Node, with
the same source-witness and finite/gauge checks as runtime consumption. Neither
this loader nor the physical change census certifies posed constraints from REST.
The two genuine renderer-created template instances are checked through the
executed, sealed source-assembly creation ledger; raw inventory rows stay intact.
The executed-input declaration includes the actual SSR Scene import closure,
including target shader feedback, but not unrelated CLI/report-only modules.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

_LINK_NOFOLLOW_SUPPORTED = os.link in os.supports_follow_symlinks

WEB = Path(__file__).resolve().parents[1]
FRESH_ROOT = WEB / "content/v39-source"
LOADER = Path(__file__).with_suffix(".mjs")
EXECUTED_INPUTS = (
    "web/scripts/fresh-source-observations.py", "web/scripts/fresh-source-observations.mjs",
    "web/scripts/fresh-source-observations.schema.json", "web/scripts/source-observations.schema.json",
    "web/source-visibility.mjs",
    "web/native-line-checks.mjs",
    "web/scripts/executed-point-motion.mjs",
    "web/scripts/verify-reference.mjs", "web/scripts/fetch-model.mjs",
    "web/scripts/native-identity-map.mjs", "web/scripts/released-models.json",
    "web/scripts/canonical-native-evidence.py",
    "web/src/source-witness.ts", "web/src/image-plane-homography.ts", "web/src/video-catalog.ts",
    "web/src/native-primitive-snapshot.ts", "web/src/source-assembly.ts",
    "web/src/native-target-shader-feedback.ts",
    "web/src/spring-culling-bounds.ts",
)

_ENCODER_SPEC = importlib.util.spec_from_file_location(
    "current_observation_gzip_codec", Path(__file__).with_name("canonical-native-evidence.py"))
_ENCODER = importlib.util.module_from_spec(_ENCODER_SPEC)
_ENCODER_SPEC.loader.exec_module(_ENCODER)


def check_namespace(path, *, historical_diagnostic=False, output=False, video_id=None):
    """Diagnostics are temporary files, never a route into a published namespace."""
    declared = Path(path).absolute()
    path = declared.resolve()
    web = WEB
    historical = (web / "content").resolve()
    current = (web / "content/v39-source").resolve()
    if declared != path and (
        declared.is_relative_to(historical) or path.is_relative_to(historical)
    ):
        raise ValueError("Published observation namespaces cannot use filesystem aliases")
    if path.is_relative_to(current):
        if historical_diagnostic:
            raise ValueError("Historical diagnostics cannot read or write current observations")
        if path.parent != current or not path.name.endswith(".observations.json.gz"):
            raise ValueError("Current observations use only direct .observations.json.gz namespace entries")
        if video_id is not None and path != current / f"{video_id}.observations.json.gz":
            raise ValueError("Current observations must use their registered video filename")
    if (
        path.is_relative_to(historical) and not path.is_relative_to(current)
        and (output or not historical_diagnostic)
    ):
        raise ValueError("Historical content is immutable and requires explicit diagnostic input")
    if not historical_diagnostic and declared.suffix != ".gz":
        raise ValueError("Current observation input/output requires an explicit .gz path")
    if historical_diagnostic and output:
        private = web / ".vite/verification-output"
        external_temp = not path.is_relative_to(web.parent) and any(
            path.is_relative_to(Path(temp).resolve())
            for temp in (tempfile.gettempdir(), "/tmp", "/var/tmp"))
        private_escape = not path.is_relative_to(private) and any(
            parent.name == "verification-output" and parent.parent.name == ".vite"
            and parent.parent.parent.resolve() == web
            for parent in declared.parents)
        if private_escape or not (path.is_relative_to(private) or external_temp):
            raise ValueError("Historical diagnostics require private .vite/verification-output or resolved output under the platform temporary directory, /tmp or /var/tmp outside the checkout")
    return path


def decode_observation_bytes(raw: bytes) -> bytes:
    """Decode only gzip storage, retaining every authored JSON byte."""
    return gzip.decompress(raw)


def encode_observation_bytes(decoded: bytes) -> bytes:
    """Use the existing deterministic gzip codec without JSON reserialization."""
    return _ENCODER.encode_observations(decoded)


def write_output(path, contents, *, declared_path, historical_diagnostic):
    """Publish supplied payloads through staged handles without serialization."""
    path = Path(path)
    declared_path = Path(declared_path)
    if (
        check_namespace(
            declared_path, historical_diagnostic=historical_diagnostic,
            output=True) != path
        or check_namespace(
            path, historical_diagnostic=historical_diagnostic,
            output=True) != path
    ):
        raise ValueError("Output path changed after validation")
    text = isinstance(contents, str)
    if not historical_diagnostic and text:
        raise TypeError("Current observation output requires a binary payload")
    if historical_diagnostic:
        for destination in (declared_path, path):
            try:
                destination.lstat()
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError(f"Historical diagnostics require a new output file: {destination}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".diagnostic-" if historical_diagnostic else ".observations-",
        suffix=path.suffix if historical_diagnostic else ".gz", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(
            descriptor, "w" if text else "wb", encoding="utf-8" if text else None,
        ) as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if historical_diagnostic:
            # Hard-link creation refuses every existing leaf, including dangling
            # links that Windows O_CREAT|O_EXCL can follow.
            if _LINK_NOFOLLOW_SUPPORTED:
                os.link(temporary, path, follow_symlinks=False)
            else:
                os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_observation_bytes(path) -> bytes:
    """Read an explicit gzip observation path; plain files are not a fallback."""
    path = Path(path)
    if path.suffix != ".gz":
        raise ValueError("Current observation storage requires an explicit .gz path")
    return decode_observation_bytes(path.read_bytes())


def _validate(data=None, inventory=None, video_id=None, operation="validate", web_root=None):
    script = """
import { readFileSync } from 'node:fs';
const fresh = await import(process.argv[1]);
const payload = JSON.parse(readFileSync(0, 'utf8'));
let result;
const root = payload.webRoot;
if (payload.operation === 'inventory') result = (await fresh.loadCurrentAuthority(root)).inventory;
else if (payload.operation === 'load') result = await fresh.loadCurrentObservations(root, payload.videoId);
else if (payload.operation === 'assembly-change-times') result = await fresh.currentSourceAssemblyChangeTimes(payload.data, { webRoot: root });
else result = await fresh.validateCurrentObservations(payload.data, { webRoot: root, inventory: payload.inventory, videoId: payload.videoId ?? payload.data?.source?.videoId });
console.log(JSON.stringify(result));
"""
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script, LOADER.resolve().as_uri()],
            input=json.dumps({"operation": operation, "data": data, "inventory": inventory,
                              "videoId": video_id, "webRoot": str(web_root or WEB)}, allow_nan=False),
            capture_output=True, text=True, encoding="utf-8", check=False, cwd=WEB.parent,
        )
    except OSError as error:
        raise ValueError("Current source authority requires Node and the tracked fresh loader") from error
    if result.returncode:
        raise ValueError("Current source authority refused observations: " + result.stderr.strip())
    return json.loads(result.stdout)


def load_observations(video_id, *, web_root=None):
    """Load only the fresh .observations.json.gz namespace; never plain/archive."""
    return _validate(video_id=video_id, operation="load", web_root=web_root)


def load_inventory(*, web_root=None):
    return _validate(operation="inventory", web_root=web_root)


def validate_observations(data, inventory=None, *, video_id=None, web_root=None):
    return _validate(data, inventory, video_id, web_root=web_root)


def assembly_change_times(data, web_root=None):
    """Exact same-shot requested times where compiled physical state changes."""
    return _validate(data=data, operation="assembly-change-times", web_root=web_root)
