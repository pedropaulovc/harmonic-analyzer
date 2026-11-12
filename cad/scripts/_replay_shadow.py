"""COM-conversation recording of part builds and reuse from it (dodo's side).

One switch, read here and nowhere else (:func:`mode`): ``HARMONIC_COM_REPLAY``
= ``off`` | ``record`` | ``shadow`` | ``reuse`` (unset: ``reuse``).

* ``off``: a part build runs exactly as it did before recording existed: the
  same command line, and the engine (``_com_conversation``) is never imported.
* ``record``: the build runs through the driver (``com_replay.py record``):
  same seat, same outputs, same exit codes, its COM conversation recorded under
  ``cad/out/replay/<stem>/``. Once the seat is released the recording is
  published BESIDE the part archive as two cache sidecars named from the part
  key (``com-replay/<engine>/<stem>/bundle/<key>.tar`` and
  ``.../manifest/<key>.json``): create-only, never fatal
  (``_artifact_cache.publish_sidecar``). The manifest is bound to the archive
  this process stored under the key (``archive``); a build that stored no
  archive (its store lost the race, failed, or stored nothing) publishes no
  recording. Only a cache role that can publish (``rw``) records at all: in
  ``ro`` or ``off`` the build runs unrecorded.
* ``shadow``: ``record``, then, still off the seat, the nearest earlier
  recording of the stem (fewest differing key inputs) is replayed against the
  CURRENT source in a sandboxed subprocess and compared with this build's
  recording. The verdict is telemetry only: span ``replay.shadow <label>`` on
  ``build-infra`` and a ``replay_shadow`` record in ``cad/out/reports/cache.jsonl``.
* ``reuse``: before the seat, the nearest real build's recording bound to its
  archive, and not revoked, is replayed against the current source
  (:func:`reuse_attempt`). A clean no-op whose every check holds makes the
  base's archive this key's outputs, stored under this key like a build's and
  marked (``.../reused/<key>.json``, no recording), with no COM at all; one in
  :data:`AUDIT_ONE_IN` such keys builds anyway and is judged as a shadow.
  Anything else builds as in ``shadow``, judged by the same replay (no second
  one after the build). A soundness alarm against a base, or a forced refresh
  of a base or of a key reused from one, revokes the base
  (``.../revoked/<key>.json``).

A driver exit of :data:`EXIT_RECORD_FAULT` (the recorder failed where the
build's results cannot be trusted, not the script or SolidWorks) re-runs the
build once unrecorded on the same seat (``dodo._exec_com``); a recorder fault
after the build had its results only stops the recording
(:meth:`Recording.exited`). Either way nothing of that recording is published.
The script's and SolidWorks' own failures stay the build's, never retried
here. Each recorded leaf ends with one INFO line (:func:`report_line`), each
reuse attempt with another (:func:`reuse_line`). DEVELOPING.md "COM
conversation recording (shadow)" has the operator view.
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime
import functools
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePath
from typing import Any, BinaryIO

import _artifact_cache as _cache
import _buildgraph
import _telemetry

MODE_ENV = "HARMONIC_COM_REPLAY"
# _com_conversation.EXIT_RECORD_FAULT, restated (dodo never imports the engine)
# and pinned equal by test_replay_shadow.
EXIT_RECORD_FAULT = 92
SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parents[1]
OUT_ROOT = REPO_ROOT / "cad" / "out"
RECORDINGS = OUT_ROOT / "replay"
# Shadow evaluations' work directories: ``<SCRATCH>/<8 random chars>/`` with
# the base bundle in ``b``, the replay's output root in ``o`` and its temporary
# files in ``t``. Short on purpose: a replay writes every output of the build
# under ``o``, so its paths are the build's own (under OUT_ROOT) plus 14
# characters, ``\rs\<8 random chars>\o`` (pinned by test).
SCRATCH = OUT_ROOT / "rs"
SCRATCH_NAME_CHARS = 8  # tempfile.mkdtemp(prefix="")
WORK_BASE, WORK_OUTPUT, WORK_TMP = "b", "o", "t"
DRIVER = SCRIPTS_DIR / "com_replay.py"
# The engine whose digest scopes every recording (never imported here).
ENGINE_FILE = SCRIPTS_DIR / "_com_conversation.py"
# The module whose run_build drives the seat before and after the recorded
# window (connect, discard, template pin, teardown); a replay replaces it.
SESSION_MODULE = SCRIPTS_DIR / "_session.py"
BLOB_ROOT = "com-replay"
# 3: manifests carry the cache salt and epoch; bundles of engine log schema 2
# (flat captures). Fields a reuse needs and older manifests lack are optional:
# ``archive`` (the identity of the archive the recorded build stored under its
# key) and ``sw_build`` (that machine's SolidWorks file version). Only a real
# build publishes one: a reused key publishes a ``reused/`` marker instead.
MANIFEST_SCHEMA = 3
LOG_NAME = "conversation.jsonl.gz"
CAPTURE_NAME = f"{LOG_NAME}.files"  # _com_conversation.capture_dir_of
# _com_conversation.capture_name(i) for any i < 10**6 (pinned by test).
CAPTURE_FILE = "000000.gz"
SUMMARY_NAME = "summary.json"
SHADOW_NAME = "shadow.json"
REPLAY_LOG_NAME = "shadow-replay.log"
DIFF_LOG_NAME = "shadow-diff.log"
# Windows without long-path support (farm workers, and SolidWorks itself):
# a file path is at most 259 characters, a directory 247 (CreateDirectory
# keeps room for an 8.3 name).
PATH_LIMIT = 259
DIRECTORY_LIMIT = 247
# The base lookup: one listing plus at most this many manifest reads (newest
# first), all inside a hard wall budget; past it the shadow step is skipped.
LOOKUP_SECONDS = 3.0
LOOKUP_MANIFESTS = 8
# The whole shadow evaluation (bundle download, replay, comparison): a hard
# wall budget on this task's worker slot, never on the seat.
SHADOW_SECONDS = 120.0
# A reuse attempt before the build (base bundle and archive downloads, the
# replay): the same hard wall budget, also never on the seat.
REUSE_SECONDS = SHADOW_SECONDS
# One in this many would-be reuses still builds on the seat and is judged as a
# shadow, so the soundness alarm stays live. Chosen by the new key's hash: the
# same key is audited on every seat and every rerun.
AUDIT_ONE_IN = 8
REUSE_NAME = "reuse.json"
# Bound on the pre-build replay's own log kept for the recording directory.
REUSE_LOG_CHARS = 200_000
# Bound on any evidence string carried by a span, log or cache.jsonl record.
EVIDENCE_CHARS = 4000
DIFFERING_LISTED = 40
_SHA256 = re.compile(r"[0-9a-f]{64}")


class Recovery(StrEnum):
    """_com_conversation.Recovery, restated (pinned equal by test): what a
    recorder fault cost the build."""

    DEGRADED = "degraded"  # recording stopped; the build finished as its own
    RERUN = "rerun"  # driver exit EXIT_RECORD_FAULT; re-run unrecorded


class ReplayMode(StrEnum):
    OFF = "off"
    RECORD = "record"
    SHADOW = "shadow"
    REUSE = "reuse"


# The fleet switch: farm workers get no submitter environment, so a fleet-wide
# change of mode is a change of this default.
DEFAULT_MODE = ReplayMode.REUSE
_UNKNOWN_MODES: set[str] = set()


def mode() -> ReplayMode:
    """The one reading of ``HARMONIC_COM_REPLAY``. Unset or empty is the
    default (``reuse``). Anything else unknown is a typo, not a request:
    recording is off, and WARN says so once per value."""
    raw = os.environ.get(MODE_ENV, "").strip().lower()
    if not raw:
        return DEFAULT_MODE
    try:
        return ReplayMode(raw)
    except ValueError:
        if raw not in _UNKNOWN_MODES:
            _UNKNOWN_MODES.add(raw)
            _telemetry.warn(
                f"[com-replay] {MODE_ENV}={raw!r} is not one of "
                f"{', '.join(m.value for m in ReplayMode)}: recording is off",
                value=raw,
            )
        return ReplayMode.OFF


class InputClass(StrEnum):
    """What kind of key input differs between a recording and its base."""

    SCRIPT = "script"
    HELPER = "helper"
    CONFIG = "config"
    RELEASE = "release"
    TEMPLATE = "template"
    ADAPTER = "adapter"
    SALT = "salt"
    OTHER = "other"


# The cache salt is a key input but no file (``_artifact_cache.key_inputs``
# folds it into the key, not into the per-file pairs): a base recorded under
# another salt differs by this one pseudo-input. Never a filter: a throwaway
# salt must still find the recordings made under the default one.
SALT_INPUT = "(cache salt)"


def input_class(tag: str) -> InputClass:
    """Classify one repo-relative key-input tag (``_artifact_cache.key_inputs``)."""
    if tag == SALT_INPUT:
        return InputClass.SALT
    name = tag.rsplit("/", 1)[-1]
    if tag.startswith("cad/scripts/"):
        if name.startswith("build_") and name.endswith(".py"):
            return InputClass.SCRIPT
        return InputClass.HELPER
    if tag == "cad/config/release.yaml":
        return InputClass.RELEASE
    if tag.startswith("cad/config/"):
        return InputClass.CONFIG
    if tag.startswith("cad/templates/"):
        return InputClass.TEMPLATE
    if name.startswith(".solidworks-mcp-submodule"):
        return InputClass.ADAPTER
    return InputClass.OTHER


# ---------------------------------------------------------------------------
# The recorded build
# ---------------------------------------------------------------------------


@dataclass
class Recording:
    """One part build run through the recording driver."""

    mode: ReplayMode
    stem: str
    script: Path
    key: str
    directory: Path
    # Set once a recorder fault is known (Recording.exited): the recording is
    # unusable and nothing of it is published.
    recovery: Recovery | None = None
    fault_where: str | None = None
    # Mode ``reuse``: the attempt this build follows (not reused); its replay,
    # when it ran, is the shadow's (:func:`after_build`).
    reuse: Reuse | None = None

    @property
    def faulted(self) -> bool:
        return self.recovery is not None

    @property
    def label(self) -> str:
        return f"part:{self.stem}"

    @property
    def log(self) -> Path:
        return self.directory / LOG_NAME

    @property
    def captures(self) -> Path:
        return self.directory / CAPTURE_NAME

    @property
    def summary_path(self) -> Path:
        return self.directory / SUMMARY_NAME

    @property
    def command(self) -> list[str]:
        """The driver command: the build script run under the recorder."""
        return [
            sys.executable,
            str(DRIVER),
            "record",
            str(self.script),
            "--log",
            str(self.log),
            "--summary",
            str(self.summary_path),
        ]

    @property
    def unrecorded(self) -> list[str]:
        """The build's own command, exactly as with recording off."""
        return [sys.executable, str(self.script)]

    def exited(self, exit_code: int) -> bool:
        """Read the driver's exit; True when the caller must re-run the build
        once unrecorded.

        :data:`EXIT_RECORD_FAULT` is a ``rerun`` fault: the recorder failed
        where the build's results cannot be trusted. Any other exit code is the
        build's own; the summary's ``faults`` then name a ``degraded`` fault
        (recording stopped, the build finished on its real results) or none.
        A fault of either class is said here (WARN, a ``replay.record_fault``
        event on the task span, a ``replay_record_fault`` cache.jsonl record,
        each with its ``recovery``) and nothing of this recording is used."""
        summary = _read_json(self.summary_path) or {}
        faults = [f for f in summary.get("faults") or [] if isinstance(f, dict)]
        if exit_code == EXIT_RECORD_FAULT:
            recovery = Recovery.RERUN
        elif faults:
            recovery = Recovery.DEGRADED
        else:
            return False
        first = faults[0] if faults else {}
        self.recovery = recovery
        self.fault_where = where = str(first.get("where", "unknown"))
        fault_type = str(first.get("type", "unknown"))
        message = str(first.get("message", ""))[:EVIDENCE_CHARS]
        consequence = (
            "re-running the build once unrecorded on the same seat"
            if recovery is Recovery.RERUN
            else f"recording stopped there; the build finished on its own results "
            f"(exit {exit_code}) and nothing of this recording is published"
        )
        _telemetry.warn(
            f"[com-replay] {self.label}: recorder fault in {where} "
            f"({fault_type}: {message}); {consequence}",
            label=self.label,
            exit_code=exit_code,
            where=where,
            fault_type=fault_type,
            recovery=recovery.value,
        )
        _telemetry.event(
            "replay.record_fault",
            label=self.label,
            exit_code=exit_code,
            where=where,
            fault_type=fault_type,
            message=message,
            fault_count=len(faults),
            recovery=recovery.value,
        )
        _cache.record_event(
            "replay_record_fault",
            self.label,
            self.key,
            mode=self.mode.value,
            exit_code=exit_code,
            where=where,
            fault_type=fault_type,
            message=message,
            recovery=recovery.value,
            traceback=str(first.get("traceback", ""))[-EVIDENCE_CHARS:],
        )
        return recovery is Recovery.RERUN


@dataclass(frozen=True)
class PathNeed:
    """One path a recording or its shadow evaluation creates."""

    purpose: str
    path: str
    directory: bool = False

    @property
    def headroom(self) -> int:
        """Characters to spare under the Windows limit (negative: too long)."""
        return (DIRECTORY_LIMIT if self.directory else PATH_LIMIT) - len(self.path)


def path_needs(
    stem: str,
    recordings: PurePath,
    scratch: PurePath,
    outputs: Iterable[str] = (),
) -> list[PathNeed]:
    """Every path recording ``stem`` creates, at its longest: the recording's
    own files under ``recordings`` (:data:`RECORDINGS`), the shadow work
    directory under ``scratch`` (:data:`SCRATCH`; random names at full width)
    and, for each output path the build writes (relative to the output root),
    its copy under the replay's scratch output root."""
    recording = recordings / stem
    captures = recording / CAPTURE_NAME
    work = scratch / ("x" * SCRATCH_NAME_CHARS)
    base = work / WORK_BASE
    needs = [
        PathNeed("recording", str(recording), directory=True),
        PathNeed("captures", str(captures), directory=True),
        PathNeed("capture", str(captures / CAPTURE_FILE)),
        *(
            PathNeed(name, str(recording / name))
            for name in (
                LOG_NAME,
                SUMMARY_NAME,
                SHADOW_NAME,
                REPLAY_LOG_NAME,
                DIFF_LOG_NAME,
                REUSE_NAME,
            )
        ),
        PathNeed("work", str(work), directory=True),
        PathNeed("work tmp", str(work / WORK_TMP), directory=True),
        PathNeed("work replay.json", str(work / "replay.json")),
        PathNeed("work replay.log", str(work / "replay.log")),
        PathNeed("work diff.json", str(work / "diff.json")),
        PathNeed("base captures", str(base / CAPTURE_NAME), directory=True),
        PathNeed("base capture", str(base / CAPTURE_NAME / CAPTURE_FILE)),
        PathNeed("base log", str(base / LOG_NAME)),
    ]
    replay_out = work / WORK_OUTPUT
    for output in outputs:
        target = replay_out / output
        needs.append(PathNeed(f"replay output {output}", str(target)))
        needs.append(
            PathNeed(f"replay directory {output}", str(target.parent), directory=True)
        )
    return needs


def plan(
    stem: str, script: Path, key: str, *, reuse: Reuse | None = None
) -> Recording | None:
    """The recording of this part build, or None: mode ``off`` (the build runs
    exactly as before), a cache role that cannot publish (``ro``/``off``: a
    recording nobody can publish is pure cost, so the build runs exactly as
    unrecorded), a checkout too deep for the recording's own paths, or a
    recording directory that cannot be prepared (the build runs unrecorded;
    recording never costs a build). ``reuse``: the attempt this build follows
    (mode ``reuse``); its replay's log is kept beside the recording."""
    current = mode()
    if current is ReplayMode.OFF or not _cache.writable():
        return None
    directory = _fresh_directory(stem, "building unrecorded")
    if directory is None:
        return None
    if reuse is not None and reuse.replay_log:
        with contextlib.suppress(OSError):
            (directory / REPLAY_LOG_NAME).write_text(reuse.replay_log, "utf-8")
    return Recording(current, stem, script, key, directory, reuse=reuse)


def _fresh_directory(stem: str, otherwise: str) -> Path | None:
    """``RECORDINGS/<stem>``, emptied, or None (WARN, ``otherwise`` says what
    happens instead): a checkout too deep for the recording's own paths, or a
    directory that cannot be prepared."""
    too_long = [
        need for need in path_needs(stem, RECORDINGS, SCRATCH) if need.headroom < 0
    ]
    if too_long:
        _telemetry.warn(
            f"[com-replay] part:{stem}: {too_long[0].purpose} path "
            f"{too_long[0].path} is {len(too_long[0].path)} characters, past the "
            f"Windows limit; {otherwise}",
            label=f"part:{stem}",
        )
        return None
    directory = RECORDINGS / stem
    try:
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
    except OSError as exc:
        _telemetry.warn(
            f"[com-replay] part:{stem}: recording directory unusable ({exc}); "
            f"{otherwise}",
            label=f"part:{stem}",
        )
        return None
    return directory


# ---------------------------------------------------------------------------
# Publication: two sidecars beside the part archive
# ---------------------------------------------------------------------------


def blob_prefix(engine: str, stem: str) -> str:
    """The manifests of every recording of ``stem`` by this engine: what the
    base lookup lists. A log only replays under the engine that wrote it, so
    the engine digest scopes the listing, and bundles live under a sibling
    prefix, so it lists manifests only. (The cache layer adds the epoch:
    ``_artifact_cache._sidecar_blob``.)"""
    return f"{BLOB_ROOT}/{engine[:16]}/{stem}/manifest/"


def blob_names(engine: str, stem: str, key: str) -> tuple[str, str]:
    """``(bundle, manifest)`` sidecar names of the recording of part ``key``."""
    root = f"{BLOB_ROOT}/{engine[:16]}/{stem}"
    return f"{root}/bundle/{key}.tar", f"{blob_prefix(engine, stem)}{key}.json"


def bundle(recording: Recording) -> bytes:
    """The log and its captures as one uncompressed tar (both are gzip
    already): sorted members, no timestamps or owners."""
    files = [recording.log]
    if recording.captures.is_dir():
        files += sorted(p for p in recording.captures.rglob("*") if p.is_file())
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in files:
            info = tarfile.TarInfo(path.relative_to(recording.directory).as_posix())
            info.size = path.stat().st_size
            info.mode = 0o644
            with path.open("rb") as fh:
                tar.addfile(info, fh)
    return buffer.getvalue()


def unbundle(data: bytes, target: Path) -> None:
    """Extract a recording bundle (regular files under ``target`` only)."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tar:
        tar.extractall(target, filter="data")


def manifest(
    recording: Recording,
    summary: dict[str, Any],
    inputs: dict[str, str],
    bundle_name: str,
    bundle_bytes: bytes,
    *,
    archive: tuple[str, int] | None = None,
    sw_build: str | None = None,
) -> dict[str, Any]:
    """The small record a later build's base lookup reads instead of a bundle.
    ``salt`` and ``epoch`` are the cache's (``_artifact_cache.config_summary``):
    the two key inputs that are not files. ``archive`` binds the recording to
    the archive its build stored under the key (``(sha256, size)``,
    :func:`_artifact_cache.publication`; None: unbound, never a reuse base);
    ``sw_build`` is the recording machine's SolidWorks (:func:`seat_build`)."""
    settings = _cache.config_summary()
    return {
        "schema": MANIFEST_SCHEMA,
        "recording_id": uuid.uuid4().hex,
        "label": recording.label,
        "stem": recording.stem,
        "key": recording.key,
        "inputs": inputs,
        "salt": settings["salt"],
        "epoch": settings["epoch"],
        "engine": summary["engine"],
        "recipe_requests": summary.get("recipe_requests"),
        "calls": summary.get("calls"),
        "inert_calls": summary.get("inert_calls"),
        "callers": summary.get("callers"),
        "sw_revision": summary.get("sw_revision"),
        "sw_build": sw_build,
        "environment": summary.get("environment"),
        "bundle": {
            "name": bundle_name,
            "sha256": hashlib.sha256(bundle_bytes).hexdigest(),
            "size": len(bundle_bytes),
        },
        "archive": None
        if archive is None
        else {"sha256": archive[0], "size": archive[1]},
        "recorded_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    }


def bound_archive(record: dict[str, Any]) -> str | None:
    """The SHA-256 of the archive a manifest is bound to, or None (unbound:
    published before binding existed, or by a build that stored nothing)."""
    archive = record.get("archive")
    digest = archive.get("sha256") if isinstance(archive, dict) else None
    return digest if isinstance(digest, str) and _SHA256.fullmatch(digest) else None


def reused_name(engine: str, stem: str, key: str) -> str:
    """The marker a reuse publishes for ``key`` instead of a recording: where
    its archive came from (:meth:`Reuse.mark`)."""
    return f"{BLOB_ROOT}/{engine[:16]}/{stem}/reused/{key}.json"


def revoked_name(engine: str, stem: str, key: str) -> str:
    """The marker that retires base ``key`` from reuse (:func:`revoke`)."""
    return f"{BLOB_ROOT}/{engine[:16]}/{stem}/revoked/{key}.json"


def revoke(engine: str, stem: str, key: str, reason: str) -> str:
    """Retire base ``key``: a create-only ``revoked/`` marker, after which no
    reuse installs its archive (``revoked_base``). The publication's outcome
    (``exists``: already revoked); RAISES when it is neither, so the caller
    says so."""
    record = {"key": key, "reason": reason, "revoked_utc": _now(), "commit": _commit()}
    outcome = _cache.publish_sidecar(
        revoked_name(engine, stem, key),
        json.dumps(record, sort_keys=True).encode("utf-8"),
    )
    if outcome not in ("stored", "exists"):
        raise RuntimeError(f"revocation of {key[:12]} not published ({outcome})")
    label = f"part:{stem}"
    _telemetry.warn(
        f"[com-replay] {label}: base {key[:12]} revoked ({outcome}): {reason}",
        label=label,
        base_key=key,
    )
    return outcome


def revoked(engine: str, stem: str, key: str) -> bool:
    """Is base ``key`` revoked? RAISES when the cache cannot say: a reuse
    attempt then declines (fail closed)."""
    return _cache.read_sidecar(revoked_name(engine, stem, key)) is not None


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()


@functools.cache
def _commit() -> str:
    """This checkout's HEAD for a marker, or ``unknown``."""
    try:
        found = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return found.stdout.strip() or "unknown"


def publish(recording: Recording, record: dict[str, Any], data: bytes) -> str:
    """Bundle first, then the manifest, so a manifest never names a missing
    bundle. Only the writer whose bundle was stored writes the manifest: a
    bundle that already ``exists`` is another writer's bytes (a recording is
    never byte-identical twice), which this manifest's digest and counts do
    not describe, so the publication ends there. The manifest's outcome is
    the publication's."""
    bundle_outcome = _cache.publish_sidecar(record["bundle"]["name"], data)
    if bundle_outcome != "stored":
        return bundle_outcome
    _, manifest_name = blob_names(record["engine"], recording.stem, recording.key)
    return _cache.publish_sidecar(
        manifest_name, json.dumps(record, sort_keys=True).encode("utf-8")
    )


# ---------------------------------------------------------------------------
# Base selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Base:
    """An earlier recording of the stem and how far its inputs are from now."""

    manifest: dict[str, Any]
    differing: tuple[str, ...]
    modified: float

    @property
    def classes(self) -> dict[str, int]:
        return dict(
            sorted(Counter(input_class(tag).value for tag in self.differing).items())
        )


def differing_inputs(base: dict[str, str], current: dict[str, str]) -> tuple[str, ...]:
    """Key-input tags whose digest differs, or which only one side has."""
    return tuple(
        sorted(
            tag
            for tag in base.keys() | current.keys()
            if base.get(tag) != current.get(tag)
        )
    )


def nearest(
    candidates: Iterable[tuple[dict[str, Any], float]],
    inputs: dict[str, str],
    exclude_id: str | None,
    salt: str,
) -> Base | None:
    """The candidate with the fewest differing inputs; a tie goes to the most
    recently published. Never the recording being evaluated. A base recorded
    under another cache ``salt`` differs by one more input
    (:data:`SALT_INPUT`); it is never excluded for it."""
    best: Base | None = None
    for record, modified in candidates:
        if record.get("schema") != MANIFEST_SCHEMA:
            continue
        if exclude_id is not None and record.get("recording_id") == exclude_id:
            continue
        differing = differing_inputs(record.get("inputs") or {}, inputs)
        if record.get("salt") != salt:
            differing = (SALT_INPUT, *differing)
        candidate = Base(record, differing, modified)
        if best is None or (len(candidate.differing), -candidate.modified) < (
            len(best.differing),
            -best.modified,
        ):
            best = candidate
    return best


class Lookup(StrEnum):
    FOUND = "found"
    NONE = "none"
    BUDGET = "budget"
    OFF = "off"


@dataclass
class LookupResult:
    outcome: Lookup
    base: Base | None = None
    listed: int = 0
    read: int = 0
    # Manifests read that the caller could not use (find_base ``usable``).
    unusable: int = 0


def find_base(
    prefix: str,
    inputs: dict[str, str],
    exclude_id: str | None,
    salt: str,
    *,
    budget: float = LOOKUP_SECONDS,
    limit: int = LOOKUP_MANIFESTS,
    usable: Callable[[dict[str, Any]], bool] | None = None,
) -> LookupResult:
    """One listing of ``prefix`` and at most ``limit`` manifest reads, newest
    first, inside ``budget`` seconds of wall time; past it, no base. ``salt``
    is the current cache salt (:func:`nearest`). ``usable``: only manifests
    it accepts are candidates (the others are counted, ``unusable``)."""
    if not _cache.enabled():
        return LookupResult(Lookup.OFF)
    result = LookupResult(Lookup.NONE)
    candidates: list[tuple[dict[str, Any], float]] = []
    deadline = time.monotonic() + budget

    def work() -> None:
        listed = [
            (n, t) for n, t in _cache.list_sidecars(prefix) if n.endswith(".json")
        ]
        result.listed = len(listed)
        for name, modified in listed[:limit]:
            if time.monotonic() >= deadline:
                return
            data = _cache.fetch_sidecar(name)
            result.read += 1
            try:
                record = json.loads(data) if data is not None else None
            except ValueError:
                record = None
            if isinstance(record, dict):
                candidates.append((record, modified))

    if not within(budget, work):
        return LookupResult(Lookup.BUDGET, None, result.listed, result.read)
    if usable is not None:
        kept = [candidate for candidate in candidates if usable(candidate[0])]
        result.unusable = len(candidates) - len(kept)
        candidates = kept
    base = nearest(candidates, inputs, exclude_id, salt)
    result.base = base
    result.outcome = Lookup.FOUND if base is not None else Lookup.NONE
    return result


def within(seconds: float, work: Callable[[], None]) -> bool:
    """Run ``work`` on a daemon thread (in this context, so its spans nest);
    False when it did not finish in ``seconds``: it is abandoned, never awaited.
    An exception it raised is re-raised here."""
    errors: list[BaseException] = []

    def run() -> None:
        try:
            work()
        except BaseException as exc:  # noqa: BLE001 - re-raised by the caller
            errors.append(exc)

    context = contextvars.copy_context()
    thread = threading.Thread(
        target=context.run, args=(run,), name="com-replay-bounded", daemon=True
    )
    thread.start()
    thread.join(max(seconds, 0.0))
    if thread.is_alive():
        return False
    if errors:
        raise errors[0]
    return True


# ---------------------------------------------------------------------------
# Shadow evaluation (off the seat, sandboxed subprocesses)
# ---------------------------------------------------------------------------


class VerdictClass(StrEnum):
    """What a shadow verdict says about the replay's judgement."""

    NOOP = "noop"
    # The replay judged the current source's requests against the base and
    # found them different: diverged, exhausted or unconsumed.
    DIVERGENCE = "divergence"
    # The replay declined to judge, by design: inputs other than source
    # differ from the base (input_mismatch), or the script did what a replay
    # never serves (sandbox).
    REFUSAL = "refusal"
    # No judgement for a reason of the machinery's own: error, timeout,
    # unavailable base, or anything unknown.
    INFRASTRUCTURE = "infrastructure"


# The engine's Verdict values (_com_conversation.Verdict; dodo never imports
# the engine) plus this module's own; pinned complete by test.
VERDICT_CLASSES: dict[str, VerdictClass] = {
    "noop": VerdictClass.NOOP,
    "diverged": VerdictClass.DIVERGENCE,
    "exhausted": VerdictClass.DIVERGENCE,
    "unconsumed": VerdictClass.DIVERGENCE,
    "input_mismatch": VerdictClass.REFUSAL,
    "sandbox": VerdictClass.REFUSAL,
    "error": VerdictClass.INFRASTRUCTURE,
    "timeout": VerdictClass.INFRASTRUCTURE,
    "unavailable": VerdictClass.INFRASTRUCTURE,
}


class NoopJudgement(StrEnum):
    """What this build's own recording says about a replay NOOP: exactly one
    per no-op (:attr:`Shadow.noop_judgement`)."""

    # The base's exact requests and the base's part: the no-op holds.
    CONFIRMED = "confirmed"
    # Another part than the base's: reuse would have served a wrong artefact.
    SOUNDNESS_ALARM = "soundness_alarm"
    # The base's part; the requests diverged after SolidWorks answered
    # differently (2026-11-11: one body's faces listed in another order;
    # 2026-11-12: a document title counter the script echoed into an equation,
    # ``truth_cause`` ``response:title_counter``).
    SEAT_NONDETERMINISM = "seat_nondeterminism"
    # The base's part; the requests diverged with every earlier answer the
    # same. A no-op rules the source out and SolidWorks answered alike, so an
    # input the replay does not pin is left (Python's own nondeterminism).
    UNEXPLAINED_DIVERGENCE = "noop_unexplained_divergence"
    # Nothing to judge by: a log without a mass-property snapshot or an STL
    # export, no comparison at all, or a divergence whose cause could not be
    # judged (``truth_cause`` ``error:<type>``, _com_outcome.judge).
    OUTCOME_UNKNOWN = "noop_outcome_unknown"


@dataclass
class Shadow:
    """What a shadow replay of the current source against a base found.

    ``ground_truth``: whether this build's own recording issued the base's
    requests (request equality, ``same``/``diverged``). ``truth_cause``: what
    preceded its first divergence, ``response:<member>`` (SolidWorks answered
    differently first; ``response:title_counter``: the script echoed a title
    counter SolidWorks answered) or ``request`` (the source asked something else).
    ``outcome``: whether this build made the base's part (``same``,
    ``different``, ``unknown``: ``_com_outcome.Outcome``). A no-op proves the
    current source maps the base's answers onto the base's requests, so with
    pinned inputs a live request divergence after a no-op comes from
    SolidWorks: request equality is telemetry about the seat, the outcome is
    the oracle."""

    verdict: str
    recorded: int | None = None
    served: int | None = None
    divergence: dict[str, Any] | None = None
    inert: dict[str, Any] = field(default_factory=dict)
    substitutions: int | None = None
    reason: str | None = None
    ground_truth: str = "unknown"
    request_divergence: dict[str, Any] | None = None
    truth_cause: str | None = None
    outcome: str = "unknown"
    outcome_signals: dict[str, str] = field(default_factory=dict)
    outcome_details: dict[str, Any] | None = None
    # What the comparison's judge raised (_com_outcome.judge ``judge_faults``:
    # ``step``, ``error``).
    judge_faults: list[dict[str, Any]] = field(default_factory=list)

    @property
    def verdict_class(self) -> VerdictClass:
        return VERDICT_CLASSES.get(self.verdict, VerdictClass.INFRASTRUCTURE)

    @property
    def noop_judgement(self) -> NoopJudgement | None:
        """The one judgement of a NOOP (``None`` for any other verdict)."""
        if self.verdict != "noop":
            return None
        if self.outcome == "different":
            return NoopJudgement.SOUNDNESS_ALARM
        if self.outcome != "same" or self.ground_truth not in ("same", "diverged"):
            return NoopJudgement.OUTCOME_UNKNOWN
        if self.ground_truth == "same":
            return NoopJudgement.CONFIRMED
        cause = self.truth_cause or ""
        if cause.startswith("response:"):
            return NoopJudgement.SEAT_NONDETERMINISM
        if cause.startswith("error:"):
            return NoopJudgement.OUTCOME_UNKNOWN
        return NoopJudgement.UNEXPLAINED_DIVERGENCE

    @property
    def soundness_alarm(self) -> bool:
        """A replay NOOP although this build made another part than the base:
        reuse would have served a wrong artefact."""
        return self.noop_judgement is NoopJudgement.SOUNDNESS_ALARM

    @property
    def seat_nondeterminism(self) -> bool:
        """A replay NOOP, this build's requests diverged from the base after
        SolidWorks answered differently, and it made the same part: the seat
        varied, not the source. Counted, never an alarm."""
        return self.noop_judgement is NoopJudgement.SEAT_NONDETERMINISM

    @property
    def noop_unexplained_divergence(self) -> bool:
        """A replay NOOP, this build made the same part, but its requests
        diverged from the base with every earlier answer the same: neither the
        source nor SolidWorks explains it. Counted and logged at WARN."""
        return self.noop_judgement is NoopJudgement.UNEXPLAINED_DIVERGENCE

    @property
    def noop_outcome_unknown(self) -> bool:
        """A replay NOOP whose outcome could not be compared (a log without a
        mass-property snapshot or an STL export, or no comparison), or whose
        divergence's cause could not be judged: neither an alarm nor evidence
        of soundness. Counted apart."""
        return self.noop_judgement is NoopJudgement.OUTCOME_UNKNOWN

    @property
    def judge_fault(self) -> bool:
        """Judging this build's recording against the base raised (a
        ``truth_cause`` of ``error:<type>``, or a signal absent because its
        judgement raised, not because neither log holds it): what it judged
        is unknown, the request divergence is kept. Any verdict; counted and
        logged at WARN, so a judge that faults every time stands out from
        no-ops legitimately unknown."""
        return bool(self.judge_faults) or (self.truth_cause or "").startswith("error:")

    @property
    def false_divergence(self) -> bool:
        """The replay judged a divergence although the fresh recording issued
        the base's exact requests (a missed reuse, never an unsound one).
        Refusals and infrastructure verdicts are no judgement, so never one:
        they are counted by :attr:`verdict_class`."""
        return (
            self.verdict_class is VerdictClass.DIVERGENCE
            and self.ground_truth == "same"
        )


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _child_env(summary: dict[str, Any], tmp: Path) -> dict[str, str]:
    """The replay's environment: the build's pinned process inputs (the
    summary's ``environment``: a recorded build's, or for a reuse attempt
    those the build about to run gets), this span as parent, temporary files
    in the task's own scratch, no bytecode written into the checkout."""
    env = _telemetry.inject_env()
    env["OTEL_SERVICE_NAME"] = "replay-shadow"
    for name, value in (summary.get("environment") or {}).items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    for name in ("TMP", "TEMP", "TMPDIR"):
        env[name] = str(tmp)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("HARMONIC_COM_SEAT", None)
    return env


def _run(
    command: list[str], env: dict[str, str], deadline: float, log: Path
) -> int | None:
    """One driver subprocess within the deadline; None when it ran out."""
    with log.open("w", encoding="utf-8") as fh:
        try:
            return subprocess.run(
                command,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=fh,
                stderr=subprocess.STDOUT,
                timeout=max(deadline - time.monotonic(), 1.0),
            ).returncode
        except subprocess.TimeoutExpired:
            return None


@contextlib.contextmanager
def _work_directory() -> Iterator[Path]:
    """A fresh work directory under :data:`SCRATCH` (``b`` for the base
    bundle, ``t`` for temporary files; the replay creates ``o``), removed
    afterwards."""
    SCRATCH.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="", dir=SCRATCH))
    try:
        (work / WORK_BASE).mkdir()
        (work / WORK_TMP).mkdir()
        yield work
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _bundle_of(base: Base, deadline: float) -> tuple[bytes | None, str | None]:
    """The base's bundle, verified against its manifest, or None and the
    verdict that says why not (``timeout``, ``unavailable``)."""
    described = base.manifest.get("bundle") or {}
    fetched: dict[str, bytes | None] = {}

    def download() -> None:
        fetched["data"] = _cache.fetch_sidecar(str(described.get("name")))

    if not within(deadline - time.monotonic(), download):
        return None, "timeout"
    data = fetched.get("data")
    if data is None or hashlib.sha256(data).hexdigest() != described.get("sha256"):
        return None, "unavailable"
    return data, None


_BUNDLE_REASONS = {
    "timeout": "bundle download exceeded the budget",
    "unavailable": "base bundle absent or not the manifest's",
}


def _replay_command(
    script: Path, work: Path, seat_log: Path, base_outputs: Path | None
) -> list[str]:
    """The driver replaying ``script`` against the base bundle in ``work``."""
    base_dir = work / WORK_BASE
    command = [
        sys.executable,
        str(DRIVER),
        "replay",
        str(script),
        "--log",
        str(base_dir / LOG_NAME),
        "--seat-log",
        str(seat_log),
        "--capture-dir",
        str(base_dir / CAPTURE_NAME),
        "--scratch",
        str(work / WORK_OUTPUT),
        "--result",
        str(work / "replay.json"),
    ]
    if base_outputs is not None:
        command += ["--base-outputs", str(base_outputs)]
    return command


def _diff(
    work: Path, recording: Recording, env: dict[str, str], deadline: float
) -> tuple[int | None, dict[str, Any] | None]:
    """This build's recording compared with the base's in ``work``."""
    diff_result = work / "diff.json"
    diff_rc = _run(
        [
            sys.executable,
            str(DRIVER),
            "diff",
            str(work / WORK_BASE / LOG_NAME),
            str(recording.log),
            "--result",
            str(diff_result),
        ],
        env,
        deadline,
        recording.directory / DIFF_LOG_NAME,
    )
    return diff_rc, _read_json(diff_result)


def evaluate(
    recording: Recording,
    base: Base,
    summary: dict[str, Any],
    *,
    seconds: float = SHADOW_SECONDS,
) -> Shadow:
    """Replay the current source against ``base`` and compare this build's
    recording with it. Everything lives in a fresh work directory under
    :data:`SCRATCH` (the replay's outputs in its ``o``), removed afterwards;
    nothing from the base reaches the build's outputs."""
    deadline = time.monotonic() + seconds
    with _work_directory() as work:
        data, failure = _bundle_of(base, deadline)
        if data is None:
            return Shadow(str(failure), reason=_BUNDLE_REASONS.get(str(failure)))
        unbundle(data, work / WORK_BASE)
        env = _child_env(summary, work / WORK_TMP)
        replay_rc = _run(
            _replay_command(recording.script, work, recording.log, OUT_ROOT),
            env,
            deadline,
            recording.directory / REPLAY_LOG_NAME,
        )
        replay = _read_json(work / "replay.json")
        diff_rc, diff = _diff(work, recording, env, deadline)
        return shadow_of(replay_rc, replay, diff_rc, diff)


def judge_replayed(
    recording: Recording,
    reuse: Reuse,
    summary: dict[str, Any],
    *,
    seconds: float = SHADOW_SECONDS,
) -> Shadow:
    """Mode ``reuse``, a build that was not reused: :func:`evaluate` with the
    pre-build replay of the same source against the same base as its replay
    (no second one), compared with this build's recording. That replay stood
    for the base's seat; on a seat of another SolidWorks revision the shadow's
    own replay would have been refused, and so is this one
    (``input_mismatch``)."""
    replay_rc, replay = reuse.replay_rc, reuse.replay
    revision = reuse.base.manifest.get("sw_revision") if reuse.base else None
    if replay is not None and (
        revision is None or summary.get("sw_revision") != revision
    ):
        replay = {
            "verdict": "input_mismatch",
            "recorded": replay.get("recorded"),
            "served": 0,
            "reason": "inputs differ from the recording: sw_revision "
            f"({revision}; this seat {summary.get('sw_revision')})",
        }
    deadline = time.monotonic() + seconds
    with _work_directory() as work:
        unbundle(reuse.bundle or b"", work / WORK_BASE)
        env = _child_env(summary, work / WORK_TMP)
        diff_rc, diff = _diff(work, recording, env, deadline)
    return shadow_of(replay_rc, replay, diff_rc, diff)


def shadow_of(
    replay_rc: int | None,
    replay: dict[str, Any] | None,
    diff_rc: int | None,
    diff: dict[str, Any] | None,
) -> Shadow:
    """Fold the replay result and the comparison of this build's recording
    with the base (request equality, its cause, the outcome) into one
    Shadow."""
    if replay_rc is None:
        shadow = Shadow("timeout", reason="replay exceeded the shadow budget")
    elif replay is None:
        shadow = Shadow("error", reason=f"replay exited {replay_rc} with no result")
    else:
        details_inert = replay.get("inert") or {}
        shadow = Shadow(
            str(replay.get("verdict")),
            recorded=replay.get("recorded"),
            served=replay.get("served"),
            divergence=replay.get("divergence"),
            inert={k: details_inert.get(k) for k in ("recorded", "served", "unserved")},
            substitutions=(replay.get("substitutions") or {}).get("count"),
            reason=str(replay.get("reason") or "")[:EVIDENCE_CHARS] or None,
        )
    if diff_rc is not None and diff is not None and "request_divergence" in diff:
        shadow.request_divergence = diff["request_divergence"]
        shadow.ground_truth = (
            "same" if diff["request_divergence"] is None else "diverged"
        )
        shadow.truth_cause = diff.get("truth_cause")
        shadow.outcome = str(diff.get("outcome") or "unknown")
        shadow.outcome_signals = dict(diff.get("outcome_signals") or {})
        shadow.outcome_details = diff.get("outcome_details")
        shadow.judge_faults = list(diff.get("judge_faults") or [])
    return shadow


# ---------------------------------------------------------------------------
# Reuse: before the seat, the base's archive as this key's outputs
# ---------------------------------------------------------------------------


@functools.cache
def seat_build() -> str | None:
    """The file version of the SolidWorks this machine's COM registration
    starts (``SldWorks.Application``'s ``LocalServer32``), read from the
    registry and the executable's version resource, never by starting or
    connecting to it; None when there is none (or not on Windows). Every
    manifest records it (``sw_build``); a reuse requires the base's to be
    this machine's."""
    if sys.platform != "win32":
        return None
    import ctypes
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, r"SldWorks.Application\CLSID"
        ) as handle:
            clsid = winreg.QueryValue(handle, None)
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32"
        ) as handle:
            server = str(winreg.QueryValue(handle, None)).strip()
    except OSError:
        return None
    if server.startswith('"'):
        executable = server[1:].split('"', 1)[0]
    else:
        end = server.lower().find(".exe")
        executable = server if end < 0 else server[: end + 4]
    version = ctypes.WinDLL("version")
    size = version.GetFileVersionInfoSizeW(executable, None)
    if not size:
        return None
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(executable, 0, size, data):
        return None
    fixed = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not version.VerQueryValueW(
        data, "\\", ctypes.byref(fixed), ctypes.byref(length)
    ):
        return None
    # VS_FIXEDFILEINFO: signature, structure version, file version MS and LS.
    words = (ctypes.c_uint32 * 4).from_address(fixed.value)
    high, low = words[2], words[3]
    return f"{high >> 16}.{high & 0xFFFF}.{low >> 16}.{low & 0xFFFF}"


@functools.cache
def engine_digest() -> str:
    """The engine's digest (``_com_conversation.sha256_file(ENGINE_FILE)``,
    what a recording's summary names): it scopes every recording's blobs."""
    return hashlib.sha256(ENGINE_FILE.read_bytes()).hexdigest()


def audited(key: str) -> bool:
    """Is ``key`` one of the one in :data:`AUDIT_ONE_IN` would-be reuses that
    build anyway? By the key's own hash: every seat and rerun agrees."""
    digest = hashlib.sha256(key.encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big") % AUDIT_ONE_IN == 0


class ReuseDecision(StrEnum):
    """What a reuse attempt decided (``reuse_decision``; a decline reads
    ``declined:<reason>``)."""

    REUSED = "reused"
    # Every check held, but the key is audited (audited()): it builds on the
    # seat and is judged as a shadow, so the soundness alarm stays live.
    AUDITED = "audited"
    DECLINED = "declined"


class Decline(StrEnum):
    """Why a part build was not reused (the first check that failed)."""

    FORCED_REFRESH = "forced_refresh"
    INPUTS_MOVED = "inputs_moved"
    NO_BASE = "no_base"
    # Recordings of the stem exist, but none is a real build's bound to the
    # archive it stored under this salt: published before binding existed, or
    # under another salt (a stored build publishes only bound manifests).
    NO_BOUND_BASE = "no_bound_base"
    # The base was revoked (a ``revoked/`` marker: a soundness alarm against
    # it, or a forced refresh of it or of a key reused from it).
    REVOKED_BASE = "revoked_base"
    # The base's key no longer holds the archive its recording is bound to (a
    # forced refresh replaced it).
    UNBOUND_BASE = "unbound_base"
    # The base was recorded on another SolidWorks than this machine's.
    SEAT_DIFFERS = "seat_differs"
    BASE_BUNDLE_MISSING = "base_bundle_missing"
    INPUT_MISMATCH = "input_mismatch"
    DIVERGED = "diverged"
    SANDBOX = "sandbox"
    REPLAY_ERROR = "replay_error"
    TIME_CAP = "time_cap"
    # A differing key input whose effect the replay does not judge.
    UNJUDGED_INPUT = "unjudged_input"
    # A replayed request carries a SolidWorks new-document title counter
    # (``Part24``): the script echoes the seat's session state, which the
    # replay serves from the base, so a build here would ask something else
    # (2026-11-12, ms_stick). Also when the replay did not report it.
    SEAT_STATE_ECHO = "seat_state_echo"
    BASE_ARCHIVE_MISSING = "base_archive_missing"
    OUTPUT_SET_DIFFERS = "output_set_differs"
    PYTHON_OUTPUT_DIFFERS = "python_output_differs"
    TOKEN_MISMATCH = "token_mismatch"
    FAULT = "fault"


class Declined(Exception):
    """A reuse attempt stops at a check that failed."""

    def __init__(self, reason: Decline, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _fold(path: str) -> str:
    """A ``/``-separated path compared as Windows compares it."""
    return path.replace("\\", "/").casefold()


def outside_window_inputs() -> frozenset[str]:
    """The key inputs that act on the seat outside the recorded window, as
    folded repository paths: :data:`SESSION_MODULE` and every keyed module it
    imports (``_buildgraph.module_deps_of``: today ``_com.py`` and
    ``_paths.py``, whose ``PART_TEMPLATE`` it pins). ``run_build`` connects,
    discards, pins the template and tears down outside the window, and a
    replay replaces it whole, so whatever these modules do there is never
    judged, even when the recipe also executes them inside the window."""
    root = _cache.REPO_ROOT.resolve()
    found = set()
    for raw in (str(SESSION_MODULE), *_buildgraph.module_deps_of(SESSION_MODULE)):
        try:
            found.add(_fold(Path(raw).resolve().relative_to(root).as_posix()))
        except ValueError:  # outside this checkout: no key input of it
            continue
    return frozenset(found)


# Documents of a kind SolidWorks opens itself, by path: templates, models,
# drawings, imports, fonts and libraries. None is ever judged by a replay,
# whatever Python also does with it (a defence beside the COM-argument rule:
# the template is pinned before the recorded window, where no argument shows).
SOLIDWORKS_DOCUMENTS = frozenset(
    {
        ".sldprt",
        ".sldasm",
        ".slddrw",
        ".prtdot",
        ".asmdot",
        ".drwdot",
        ".sldlfp",
        ".sldblk",
        ".sldmat",
        ".sldstd",
        ".sldclr",
        ".step",
        ".stp",
        ".igs",
        ".iges",
        ".x_t",
        ".x_b",
        ".sat",
        ".dxf",
        ".dwg",
        ".stl",
        ".ttf",
        ".otf",
    }
)


def seat_inputs(differing: Iterable[str]) -> list[str]:
    """Differing key inputs no replay judges, whatever it finds: documents
    SolidWorks opens itself (:data:`SOLIDWORKS_DOCUMENTS`) and the modules
    that act on the seat outside the recorded window
    (:func:`outside_window_inputs`)."""
    outside = outside_window_inputs()
    return [
        tag
        for tag in differing
        if _fold(tag) in outside
        or PurePath(tag).suffix.casefold() in SOLIDWORKS_DOCUMENTS
    ]


def solidworks_named(differing: Iterable[str], replay: dict[str, Any]) -> list[str]:
    """Differing key inputs a COM argument of the base names
    (``solidworks_inputs``, com_replay.py): SolidWorks opens them itself,
    whatever the script also does with them, so a replay serving its
    recorded responses never sees their content."""
    named = {_fold(path) for path in replay.get("solidworks_inputs") or []}
    return [tag for tag in differing if _fold(tag) in named]


def unexecuted_inputs(differing: Iterable[str], replay: dict[str, Any]) -> list[str]:
    """Differing key inputs the replayed recipe neither imported nor read
    (``python_files``, com_replay.py: the build script's own execution, never
    the engine's): what reaches the part some other way (the cache salt, the
    adapter, anything SolidWorks resolves itself). What the recipe executed
    or read inside the window reaches the part only through the requests the
    replay matched and the Python-written outputs, compared with the base
    archive's (:func:`_verify_outputs`); what it does outside the window is
    :func:`seat_inputs`'."""
    executed = {_fold(path) for path in replay.get("python_files") or []}
    return [tag for tag in differing if _fold(tag) not in executed]


@dataclass(frozen=True)
class PartBuild:
    """What dodo knows of one part build before it runs (:func:`reuse_attempt`)."""

    stem: str
    script: Path
    key: str
    file_deps: list[str]
    digest: Callable[[str], str]
    # The task's cache outputs and, among them, the native part whose bytes
    # the .execution token hashes.
    outputs: list[Path]
    native: Path
    # The pinned process inputs the build subprocess would get
    # (_com_conversation.ENVIRONMENT_KEYS); computed only by an attempt.
    environment: Callable[[], dict[str, str | None]]

    @property
    def label(self) -> str:
        return f"part:{self.stem}"


_REUSE_PHASES = ("lookup", "bundle", "replay", "archive", "verify", "publish")


@dataclass
class Reuse:
    """One reuse attempt (:func:`reuse_attempt`): what it found and decided.
    ``decision`` None: no attempt was made."""

    part: PartBuild | None = None
    decision: ReuseDecision | None = None
    reason: Decline | None = None
    detail: str | None = None
    inputs: dict[str, str] = field(default_factory=dict)
    lookup: LookupResult | None = None
    base: Base | None = None
    # The base's verified bundle, kept for the comparison after a build.
    bundle: bytes | None = None
    replayed: bool = False
    replay_rc: int | None = None
    replay: dict[str, Any] | None = None
    replay_log: str = ""
    # The base's verified archive and its members, while a reuse is pending.
    archive: BinaryIO | None = None
    archive_bytes: int | None = None
    members: dict[str, str] = field(default_factory=dict)
    token: str | None = None
    seconds: dict[str, float] = field(default_factory=dict)
    store: str | None = None
    # The ``reused/`` marker's publication (:meth:`mark`).
    marker: str | None = None
    published_from: float = 0.0
    # The last phase entered (``timed``): where a fault happened.
    phase: str = "prepare"

    @property
    def value(self) -> str | None:
        """``reused``, ``audited`` or ``declined:<reason>``; None: no attempt."""
        if self.decision is None:
            return None
        if self.reason is None:
            return self.decision.value
        return f"{self.decision.value}:{self.reason.value}"

    @property
    def shadow(self) -> Shadow | None:
        """The pre-build replay's verdict, before any comparison."""
        if not self.replayed:
            return None
        return shadow_of(self.replay_rc, self.replay, None, None)

    @contextlib.contextmanager
    def timed(self, phase: str) -> Iterator[None]:
        self.phase = phase
        started = time.monotonic()
        try:
            yield
        finally:
            self.seconds[phase] = time.monotonic() - started

    def decline(self, reason: Decline, detail: str) -> None:
        self.decision = ReuseDecision.DECLINED
        self.reason = reason
        self.detail = " ".join(detail.split())[:EVIDENCE_CHARS]
        self.close()

    def close(self) -> None:
        if self.archive is not None:
            self.archive.close()
            self.archive = None

    def fall_through(self, phase: str, exc: BaseException) -> None:
        """A step failed: decline (``fault`` unless the step said why), WARN;
        the build then runs exactly as with no attempt."""
        self.phase = phase
        if isinstance(exc, Declined):
            self.decline(exc.reason, exc.detail)
        else:
            self.decline(Decline.FAULT, f"{phase}: {exc!r}")
        label = self.part.label if self.part else "part:?"
        _telemetry.warn(
            f"[com-replay] {label}: reuse {self.value} in {phase}, building on "
            f"the seat: {self.detail}",
            label=label,
        )

    def install(self, outputs: list[Path]) -> None:
        """Install the base's verified archive as this build's ``outputs``,
        as a cache HIT restores one, and check each installed file is the
        archive's member byte for byte. A restore lock on an output (a
        document open in SolidWorks: ``RestoreLocked``) raises like any other
        fault, and the build falls through to the seat."""
        self.phase = "install"
        self.published_from = time.monotonic()
        if self.archive is None or self.base is None or self.part is None:
            raise RuntimeError("no verified base archive to install")
        _cache.install_archive(
            self.archive, outputs, self.part.label, str(self.base.manifest["key"])
        )
        for rel, digest in self.members.items():
            if _sha256_file(OUT_ROOT / rel) != digest:
                raise RuntimeError(f"installed {rel} is not the archive's member")

    def check_token(self, path: Path) -> None:
        """An integrity check: the ``.execution`` token re-stamped from the
        installed native part must be the base's (the same bytes). Dependents'
        keys still move with this key, since they fold the part's recipe
        digest (``dodo._stable_artefact_digest``); a reuse saves the part leaf
        only."""
        stamped = path.read_text(encoding="utf-8").strip()
        if stamped != self.token:
            raise Declined(
                Decline.TOKEN_MISMATCH,
                f".execution {stamped[:12]} is not the base native part's "
                f"{str(self.token)[:12]}",
            )

    def mark(self) -> None:
        """Before dodo stores the installed outputs under this key: the
        create-only ``reused/<key>`` marker naming the origin (a real build)
        and the archive installed, so a forced refresh of this key can revoke
        that origin. RAISES when the marker is not published, or an existing
        one names another origin: the build then runs on the seat."""
        self.phase = "mark"
        if self.part is None or self.base is None:
            raise RuntimeError("no reuse to mark")
        origin = str(self.base.manifest.get("key"))
        name = reused_name(engine_digest(), self.part.stem, self.part.key)
        record = {
            "key": self.part.key,
            "origin_key": origin,
            "archive": {
                "sha256": bound_archive(self.base.manifest),
                "size": self.archive_bytes,
            },
            "marked_utc": _now(),
            "commit": _commit(),
        }
        self.marker = _cache.publish_sidecar(
            name, json.dumps(record, sort_keys=True).encode("utf-8")
        )
        if self.marker == "stored":
            return
        if self.marker == "exists":
            existing = _cache.read_sidecar(name)
            named = json.loads(existing).get("origin_key") if existing else None
            if named == origin:
                return
            raise RuntimeError(f"reused marker of {self.part.key[:12]} names {named}")
        raise RuntimeError(f"reused marker not published ({self.marker})")

    def finish(self, outcome: str) -> None:
        """dodo stored the installed outputs under this key (``outcome``).
        A reused key publishes no recording (only real builds are bases);
        its marker went out before the store (:meth:`mark`). Never raises."""
        self.store = outcome
        self.seconds["publish"] = time.monotonic() - self.published_from
        self._keep()

    @property
    def label(self) -> str:
        return self.part.label if self.part else "part:?"

    def _keep(self) -> None:
        """This reuse's record and replay log in the stem's recording
        directory, for a local look (best-effort: never raises, so nothing
        here can fail a task whose outputs are already stored)."""
        try:
            if self.part is None:
                return
            directory = _fresh_directory(self.part.stem, "keeping no local record")
            if directory is None:
                return
            (directory / REUSE_NAME).write_text(
                json.dumps(reuse_record(self), indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )
            if self.replay_log:
                (directory / REPLAY_LOG_NAME).write_text(self.replay_log, "utf-8")
        except Exception as exc:  # noqa: BLE001 - a local record never costs a build
            _telemetry.warn(
                f"[com-replay] {self.label}: local reuse record not kept: {exc!r}",
                label=self.label,
            )


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1 << 20):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def revoke_refreshed(part: PartBuild) -> bool:
    """Is this build a forced cache refresh (``_cache.forced_refresh``)? Then
    what ``part.key`` held is suspect: revoke the origin its ``reused/``
    marker names, and the key itself when it is a base (a recording of it is
    published). A revocation that fails is a WARN, never the build's: the
    refresh builds on the seat either way. Raises only what reading the
    refresh carrier raises."""
    if _cache.forced_refresh(part.label) is None:
        return False
    engine = engine_digest()
    try:
        marker = _cache.read_sidecar(reused_name(engine, part.stem, part.key))
        origin = json.loads(marker).get("origin_key") if marker is not None else None
        if isinstance(origin, str) and origin:
            revoke(
                engine,
                part.stem,
                origin,
                f"forced refresh of {part.key[:12]}, which was reused from it",
            )
        _, manifest_name = blob_names(engine, part.stem, part.key)
        if _cache.read_sidecar(manifest_name) is not None:
            revoke(engine, part.stem, part.key, "forced refresh of a base")
    except Exception as exc:  # noqa: BLE001 - a revocation never costs a build
        _telemetry.warn(
            f"[com-replay] {part.label}: forced refresh, but its revocation "
            f"failed: {exc!r}",
            label=part.label,
        )
    return True


@contextlib.contextmanager
def reuse_attempt(part: PartBuild) -> Iterator[Reuse]:
    """Mode ``reuse`` in a cache role that can publish: before the seat, try
    to make the nearest bound real build's archive this build's outputs
    (:func:`_prepare`), inside span ``replay.reuse <label>``. The body sees
    the decision: ``reused`` lets dodo install, mark and store it
    (:meth:`Reuse.install`, :meth:`Reuse.check_token`, :meth:`Reuse.mark`,
    :meth:`Reuse.finish`); anything else builds on the seat. On leaving: one
    ``replay_reuse`` cache.jsonl record and one INFO line (:func:`reuse_line`).
    The attempt never raises; another mode or role yields a Reuse without a
    decision and records nothing (``record`` and ``shadow`` still revoke
    what a forced refresh replaces: :func:`revoke_refreshed`)."""
    reuse = Reuse(part)
    current = mode()
    if current is ReplayMode.OFF or not _cache.writable():
        yield reuse
        return
    if current is not ReplayMode.REUSE:
        try:
            revoke_refreshed(part)
        except Exception as exc:  # noqa: BLE001 - the probe already read it
            _telemetry.warn(
                f"[com-replay] {part.label}: refresh carrier unreadable: {exc!r}",
                label=part.label,
            )
        yield reuse
        return
    label = part.label
    with _telemetry.span(
        f"replay.reuse {label}", service=_telemetry.BUILD_INFRA_SERVICE, label=label
    ) as sp:
        try:
            _prepare(part, reuse)
        except Declined as declined:
            reuse.decline(declined.reason, declined.detail)
        except Exception as exc:  # noqa: BLE001 - a reuse attempt never costs a build
            reuse.fall_through(reuse.phase, exc)
        try:
            yield reuse
        finally:
            reuse.close()
            _report_reuse(reuse, sp)


def _prepare(part: PartBuild, reuse: Reuse) -> None:
    """Fill ``reuse`` through its decision; :class:`Declined` at the first
    check that fails, in this order: no forced refresh (which revokes what it
    replaces); the key's inputs; a real build's recording of the stem bound
    to its archive under this salt, not revoked, made on this machine's
    SolidWorks; its bundle; a clean no-op replay of the current source against
    it, standing for the base's seat; every differing input judged by that
    replay (none SolidWorks opens itself, none acting outside the recorded
    window, each one the replayed recipe imported or read); no replayed
    request echoing a document title counter; the base key's archive,
    verified and the one the recording is bound to; the replay's outputs
    exactly the archive's members, within the task's declared outputs, the
    Python-written ones byte for byte, the native part among them; the inputs
    unmoved."""
    deadline = time.monotonic() + REUSE_SECONDS
    if revoke_refreshed(part):
        raise Declined(
            Decline.FORCED_REFRESH, "a forced cache refresh builds on the seat"
        )
    reuse.inputs = _current_inputs(part)
    salt = str(_cache.config_summary()["salt"])

    def usable(record: dict[str, Any]) -> bool:
        return (
            bound_archive(record) is not None
            and record.get("salt") == salt
            and record.get("key") != part.key
        )

    engine = engine_digest()
    with reuse.timed("lookup"):
        reuse.lookup = found = find_base(
            blob_prefix(engine, part.stem),
            reuse.inputs,
            None,
            salt,
            budget=LOOKUP_SECONDS,
            usable=usable,
        )
    if found.outcome is Lookup.BUDGET:
        raise Declined(Decline.TIME_CAP, f"base lookup past {LOOKUP_SECONDS} s")
    if found.base is None:
        if found.unusable:
            raise Declined(
                Decline.NO_BOUND_BASE,
                f"{found.unusable} recording(s) of the stem, none a real build's "
                f"bound to its archive under salt {salt}",
            )
        raise Declined(Decline.NO_BASE, f"no recording of the stem ({found.outcome})")
    base = reuse.base = found.base
    base_key = str(base.manifest.get("key"))
    if revoked(engine, part.stem, base_key):
        raise Declined(Decline.REVOKED_BASE, f"base {base_key[:12]} is revoked")
    here = seat_build()
    if here is None or base.manifest.get("sw_build") != here:
        raise Declined(
            Decline.SEAT_DIFFERS,
            f"the base was recorded on SolidWorks {base.manifest.get('sw_build')}, "
            f"this machine has {here}",
        )
    unjudged = seat_inputs(base.differing)
    if unjudged:
        raise Declined(
            Decline.UNJUDGED_INPUT,
            "differing input(s) SolidWorks opens itself or that act on the seat "
            "outside the recorded window: " + ", ".join(unjudged[:5]),
        )
    with reuse.timed("bundle"):
        reuse.bundle, failure = _bundle_of(base, deadline)
    if reuse.bundle is None:
        reason = (
            Decline.TIME_CAP if failure == "timeout" else Decline.BASE_BUNDLE_MISSING
        )
        raise Declined(reason, _BUNDLE_REASONS[str(failure)])
    with reuse.timed("replay"):
        _replay_before(part, reuse, deadline)
    replay = reuse.replay or {}
    # Before the verdict: a differing file SolidWorks opens by path may also
    # make the replay refuse (its digest is pinned), but this is why.
    unjudged = solidworks_named(base.differing, replay)
    if unjudged:
        raise Declined(
            Decline.UNJUDGED_INPUT,
            "differing input(s) SolidWorks opens by path: " + ", ".join(unjudged[:5]),
        )
    shadow = shadow_of(reuse.replay_rc, reuse.replay, None, None)
    if shadow.verdict != "noop":
        raise Declined(
            _verdict_decline(shadow), f"replay {shadow.verdict}: {shadow.reason}"
        )
    unjudged = unexecuted_inputs(base.differing, replay)
    if unjudged:
        raise Declined(
            Decline.UNJUDGED_INPUT,
            "differing input(s) the replayed Python neither executed nor read: "
            + ", ".join(unjudged[:5]),
        )
    read_outputs = replay.get("solidworks_out_inputs") or []
    if read_outputs:
        raise Declined(
            Decline.UNJUDGED_INPUT,
            "SolidWorks opens output-root files the base did not capture: "
            + ", ".join(read_outputs[:5]),
        )
    echoes = replay.get("title_echoes")
    if not isinstance(echoes, dict) or echoes.get("count") != 0:
        raise Declined(Decline.SEAT_STATE_ECHO, _echo_detail(echoes))
    with reuse.timed("archive"):
        _fetch_base_archive(base, reuse, deadline)
    with reuse.timed("verify"):
        _verify_outputs(part, reuse)
    if _current_inputs(part) != reuse.inputs:
        raise Declined(Decline.INPUTS_MOVED, "an input changed during the attempt")
    if audited(part.key):
        reuse.decision = ReuseDecision.AUDITED
        reuse.close()
        return
    reuse.decision = ReuseDecision.REUSED


def _echo_detail(echoes: Any) -> str:
    if not isinstance(echoes, dict):
        return "the replay did not report its requests' title counters"
    first = ", ".join(str(item) for item in (echoes.get("first") or [])[:5])
    return (
        f"{echoes.get('count')} replayed request(s) carry a SolidWorks document "
        f"title counter, the seat's session state: {first}"
    )


def _current_inputs(part: PartBuild) -> dict[str, str]:
    key, pairs = _cache.key_inputs(part.file_deps, part.digest)
    if key != part.key:
        raise Declined(
            Decline.INPUTS_MOVED,
            f"the inputs now key {key[:12]}, not {part.key[:12]}",
        )
    return dict(pairs)


def _verdict_decline(shadow: Shadow) -> Decline:
    if shadow.verdict_class is VerdictClass.DIVERGENCE:
        return Decline.DIVERGED
    return {
        "sandbox": Decline.SANDBOX,
        "input_mismatch": Decline.INPUT_MISMATCH,
        "timeout": Decline.TIME_CAP,
    }.get(shadow.verdict, Decline.REPLAY_ERROR)


def _replay_before(part: PartBuild, reuse: Reuse, deadline: float) -> None:
    """Replay the current source against the base bundle with SolidWorks
    absent, standing for the base's seat (its own log is the seat log), under
    the process inputs the build would get. No comparison of Python outputs
    here: :func:`_verify_outputs` compares the replay's own digests with the
    base archive's members once a no-op makes downloading it worthwhile."""
    environment = part.environment()
    with _work_directory() as work:
        unbundle(reuse.bundle or b"", work / WORK_BASE)
        log = work / "replay.log"
        reuse.replay_rc = _run(
            _replay_command(part.script, work, work / WORK_BASE / LOG_NAME, None),
            _child_env({"environment": environment}, work / WORK_TMP),
            deadline,
            log,
        )
        reuse.replay = _read_json(work / "replay.json")
        reuse.replayed = True
        with contextlib.suppress(OSError):
            reuse.replay_log = log.read_text("utf-8", errors="replace")[
                -REUSE_LOG_CHARS:
            ]


def _fetch_base_archive(base: Base, reuse: Reuse, deadline: float) -> None:
    """The base key's canonical archive, verified, and the one the recording
    is bound to: its committed SHA-256 is the manifest's ``archive``."""
    key = str(base.manifest.get("key"))
    fetched: dict[str, BinaryIO | None] = {}

    def download() -> None:
        fetched["archive"] = _cache.fetch_archive(key)

    if not within(deadline - time.monotonic(), download):
        raise Declined(Decline.TIME_CAP, "base archive download exceeded the budget")
    archive = fetched.get("archive")
    if archive is None:
        raise Declined(
            Decline.BASE_ARCHIVE_MISSING, f"no verified archive under {key[:12]}"
        )
    reuse.archive = archive
    digest, size = _cache.archive_identity(archive)
    reuse.archive_bytes = size
    if digest != bound_archive(base.manifest):
        raise Declined(
            Decline.UNBOUND_BASE,
            f"the archive under {key[:12]} is {digest[:12]}, the recording's "
            f"build stored {str(bound_archive(base.manifest))[:12]}",
        )
    reuse.members = _cache.archive_members(archive)


def _out_relative(path: Path) -> str | None:
    try:
        relative = os.path.relpath(path, OUT_ROOT)
    except ValueError:  # another drive
        return None
    return None if relative.startswith("..") else _fold(relative)


def _verify_outputs(part: PartBuild, reuse: Reuse) -> None:
    """The replay wrote exactly the base archive's files, all within the
    task's declared outputs; each one Python wrote is the archive's byte for
    byte (those SolidWorks wrote come from the base's captures, and the
    archive is what the base's own build stored); the native part is among
    them, its digest the token a reuse must re-stamp."""
    replay = reuse.replay or {}
    python = {
        _fold(rel): digest for rel, digest in (replay.get("py_outputs") or {}).items()
    }
    produced = set(python) | {_fold(rel) for rel in replay.get("com_outputs") or {}}
    members = {_fold(rel): digest for rel, digest in reuse.members.items()}
    if produced != set(members):
        raise Declined(
            Decline.OUTPUT_SET_DIFFERS,
            f"the replay wrote {sorted(produced - set(members))[:5]} the archive "
            f"lacks; the archive holds {sorted(set(members) - produced)[:5]} the "
            "replay did not write",
        )
    declared = [rel for rel in map(_out_relative, part.outputs) if rel is not None]
    outside = sorted(
        rel
        for rel in members
        if not any(rel == own or rel.startswith(own + "/") for own in declared)
    )
    if outside:
        raise Declined(
            Decline.OUTPUT_SET_DIFFERS,
            f"archive files outside the task's declared outputs: {outside[:5]}",
        )
    differing = sorted(rel for rel, digest in python.items() if members[rel] != digest)
    if differing:
        raise Declined(
            Decline.PYTHON_OUTPUT_DIFFERS,
            f"Python-written {differing[:5]} not the base archive's",
        )
    native = _out_relative(part.native)
    token = members.get(native) if native is not None else None
    if token is None:
        raise Declined(
            Decline.OUTPUT_SET_DIFFERS, f"the archive holds no native part {native}"
        )
    reuse.token = token


def reuse_record(reuse: Reuse) -> dict[str, Any]:
    """A reuse attempt as its ``replay_reuse`` cache.jsonl record."""
    shadow = reuse.shadow
    base = reuse.base.manifest if reuse.base else {}
    lookup = reuse.lookup
    return {
        "mode": ReplayMode.REUSE.value,
        "reuse_decision": reuse.value,
        "decline": reuse.reason.value if reuse.reason else None,
        "detail": reuse.detail,
        "phase": reuse.phase if reuse.reason is Decline.FAULT else None,
        "lookup": lookup.outcome.value if lookup else None,
        "listed": lookup.listed if lookup else None,
        "read": lookup.read if lookup else None,
        "unusable": lookup.unusable if lookup else None,
        "base_key": base.get("key"),
        "differing_count": len(reuse.base.differing) if reuse.base else None,
        "differing_classes": reuse.base.classes if reuse.base else None,
        "differing": list(reuse.base.differing[:DIFFERING_LISTED])
        if reuse.base
        else None,
        "verdict": shadow.verdict if shadow else None,
        "served": shadow.served if shadow else None,
        "recorded": shadow.recorded if shadow else None,
        "seconds": {
            phase: round(reuse.seconds[phase], 3)
            for phase in _REUSE_PHASES
            if phase in reuse.seconds
        },
        "bundle_bytes": len(reuse.bundle) if reuse.bundle is not None else None,
        "archive_bytes": reuse.archive_bytes,
        "token": reuse.token,
        "store": reuse.store,
        "marker": reuse.marker,
    }


def reuse_line(label: str, record: dict[str, Any]) -> str:
    """One line (never a newline) of a reuse attempt: the decision; the base
    and how many inputs differ from it; the replay's verdict and requests
    served of recorded; seconds per phase; for a reuse, the store's outcome
    and the ``reused/`` marker's publication; for a decline, why."""

    def shown(name: str) -> str:
        value = record.get(name)
        return "-" if value is None else str(value)

    seconds = record.get("seconds") or {}
    segments = [
        f"[com-replay] {label}: reuse={shown('reuse_decision')}",
        f"base={str(record.get('base_key') or '-')[:12]} "
        f"differing={shown('differing_count')}",
        f"shadow={shown('verdict')} served={shown('served')}/{shown('recorded')}",
        " ".join(f"{phase}={value}s" for phase, value in seconds.items()) or "-",
    ]
    if record.get("store") is not None:
        segments.append(f"store={shown('store')} marker={shown('marker')}")
    if record.get("detail"):
        segments.append(" ".join(str(record["detail"]).split())[:200])
    return " | ".join(segments)


def _report_reuse(reuse: Reuse, sp: Any) -> None:
    """The attempt's span attributes, cache.jsonl record and INFO line; never
    raises."""
    label = reuse.label
    try:
        record = reuse_record(reuse)
        flat = {
            **{k: v for k, v in record.items() if k not in ("seconds", "differing")},
            "base_key": str(record["base_key"] or "")[:12] or None,
            "differing_classes": ",".join(
                f"{k}:{v}" for k, v in (record["differing_classes"] or {}).items()
            )
            or None,
            **{f"{phase}_s": value for phase, value in record["seconds"].items()},
        }
        for name, value in _attributes("replay", flat).items():
            sp.set_attribute(name, value)
        key = reuse.part.key if reuse.part else ""
        _cache.record_event("replay_reuse", label, key, **record)
        _telemetry.info(
            reuse_line(label, record), label=label, reuse=record["reuse_decision"]
        )
    except Exception as exc:  # noqa: BLE001 - observation never costs a build
        _telemetry.warn(
            f"[com-replay] {label}: reuse report failed: {exc!r}", label=label
        )


# ---------------------------------------------------------------------------
# After the build: publish, look up, evaluate -- telemetry only
# ---------------------------------------------------------------------------


def after_build(
    recording: Recording | None,
    file_deps: list[str],
    digest: Callable[[str], str],
) -> None:
    """Publish this build's recording and (``shadow``, ``reuse``) evaluate a
    replay of it. Runs after the seat is released; never raises, never touches
    an output. ``recording`` None (no recording: :func:`plan`) is a no-op; a
    faulted recording (:meth:`Recording.exited`) publishes nothing. Every
    recorded build ends with one ``replay_shadow`` cache.jsonl record and one
    INFO line (:func:`report_line`), all inside one ``replay.after_build``
    span: the wall time this step adds to the task, every part of it."""
    if recording is None:
        return
    label = recording.label
    record: dict[str, Any] = {"mode": recording.mode.value}
    if recording.reuse is not None and recording.reuse.value is not None:
        record["reuse_decision"] = recording.reuse.value
    with _telemetry.span(
        f"replay.after_build {label}",
        service=_telemetry.BUILD_INFRA_SERVICE,
        label=label,
    ) as sp:
        if recording.recovery is not None:
            record.update(
                outcome="record_fault",
                recovery=recording.recovery.value,
                where=recording.fault_where,
            )
        else:
            try:
                _after_build(recording, file_deps, digest, record)
            except Exception as exc:  # noqa: BLE001 - observation never costs a build
                _telemetry.warn(
                    f"[com-replay] {label}: shadow step failed: {exc!r}",
                    label=label,
                )
                record.update(outcome="error", error=repr(exc)[:EVIDENCE_CHARS])
        sp.set_attribute("replay.outcome", record["outcome"])
        if "reuse_decision" in record:
            sp.set_attribute("replay.reuse_decision", record["reuse_decision"])
        _cache.record_event("replay_shadow", label, recording.key, **record)
        _telemetry.info(
            report_line(label, record), label=label, outcome=record["outcome"]
        )


def report_line(label: str, record: dict[str, Any]) -> str:
    """One line (never a newline) of what a recorded build's shadow step did:
    publication outcome and bundle bytes; the base lookup (base key or none,
    manifests listed and read, seconds); the shadow replay's verdict, requests
    served of recorded, seconds; the ground truth from this build's own
    requests; the outcome against the base's and the truth's cause; then the
    markers (``SOUNDNESS ALARM``, ``seat_nondeterminism``,
    ``noop_unexplained_divergence``, ``noop_outcome_unknown``,
    ``judge_fault``). ``-`` marks a step the build never reached."""

    def shown(name: str, unit: str = "") -> str:
        value = record.get(name)
        return "-" if value is None else f"{value}{unit}"

    outcome = str(record.get("outcome"))
    head = f"[com-replay] {label}: {outcome}"
    if outcome == "record_fault":
        head += f" ({shown('recovery')} in {shown('where')}): nothing published"
    elif outcome == "error":
        head += f" ({' '.join(str(record.get('error')).split())[:200]})"
    base = str(record.get("base_key") or "")[:12]
    if not base:
        base = "none" if "lookup" in record else "-"
    segments = [
        head,
        *(
            [f"reuse={record['reuse_decision']}"]
            if record.get("reuse_decision")
            else []
        ),
        f"publish={shown('publish')} bytes={shown('bundle_bytes')}",
        f"lookup={shown('lookup')} base={base} differing={shown('differing_count')} "
        f"listed={shown('listed')} read={shown('read')} {shown('lookup_s', 's')}",
        f"shadow={shown('verdict')} served={shown('served')}/{shown('recorded')} "
        f"{shown('wall_s', 's')}",
        f"truth={shown('ground_truth')}",
        f"outcome={shown('artefact_outcome')} cause={shown('truth_cause')}",
    ]
    if record.get("soundness_alarm"):
        segments.append("SOUNDNESS ALARM")
    if record.get("seat_nondeterminism"):
        segments.append("seat_nondeterminism")
    if record.get("noop_unexplained_divergence"):
        segments.append("noop_unexplained_divergence")
    if record.get("noop_outcome_unknown"):
        segments.append("noop_outcome_unknown")
    if record.get("judge_fault"):
        segments.append("judge_fault")
    return " | ".join(segments)


# The fields of a request divergence that place it (the rest is context).
_DIVERGENCE_SUMMARY = (
    "index",
    "field",
    "member_expected",
    "member_actual",
    "feature",
    "caller_expected",
    "caller_actual",
)


def _evidence(base: Base, shadow: Shadow) -> str:
    """Bounded evidence of a shadow's judgement: the short fields first, the
    outcome details last and clipped to the room left, so the cut at
    :data:`EVIDENCE_CHARS` only ever shortens the details."""
    divergence = shadow.request_divergence
    found: dict[str, Any] = {
        "base_key": base.manifest.get("key"),
        "replay_verdict": shadow.verdict,
        "served": shadow.served,
        "recorded": shadow.recorded,
        "ground_truth": shadow.ground_truth,
        "truth_cause": shadow.truth_cause,
        "outcome": shadow.outcome,
        "outcome_signals": shadow.outcome_signals,
        "judge_faults": shadow.judge_faults,
        "request_divergence": {
            name: divergence.get(name) for name in _DIVERGENCE_SUMMARY
        }
        if divergence
        else None,
        "differing": list(base.differing[:DIFFERING_LISTED]),
    }
    room = EVIDENCE_CHARS - len(json.dumps(found, default=str))
    details = json.dumps(shadow.outcome_details, sort_keys=True, default=str)
    found["outcome_details"] = details[: max(room, 0)]
    return json.dumps(found, default=str)[:EVIDENCE_CHARS]


def _overhead(summary: dict[str, Any]) -> dict[str, Any]:
    clock = summary.get("clock_seconds") or {}
    engine = float(clock.get("engine") or 0.0)
    audit = float(summary.get("escape_audit_seconds") or 0.0)
    window = float(summary.get("window_seconds") or 0.0)
    unrecorded = window - engine - audit
    return {
        "engine_s": round(engine, 4),
        "escape_audit_s": round(audit, 4),
        "com_s": round(float(clock.get("com") or 0.0), 4),
        "window_s": round(window, 4),
        "overhead_pct": round(100.0 * (engine + audit) / unrecorded, 3)
        if unrecorded > 0
        else None,
        "recipe_requests": summary.get("recipe_requests"),
        "inert_calls": summary.get("inert_calls"),
        "capture_stored_bytes": summary.get("capture_stored_bytes"),
    }


def _attributes(prefix: str, values: dict[str, Any]) -> dict[str, Any]:
    """Span attributes: ``prefix.name`` for every non-None primitive."""
    return {
        f"{prefix}.{name}": value
        for name, value in values.items()
        if isinstance(value, (str, bool, int, float))
    }


def _after_build(
    recording: Recording,
    file_deps: list[str],
    digest: Callable[[str], str],
    record: dict[str, Any],
) -> None:
    """Fill ``record`` (``outcome`` last) as far as this build gets."""
    label = recording.label
    infra = _telemetry.BUILD_INFRA_SERVICE
    summary = _read_json(recording.summary_path)
    if summary is None or not summary.get("complete") or summary.get("exit_code") != 0:
        record["outcome"] = "no_recording"
        return
    overhead = _overhead(summary)
    record["overhead"] = overhead
    with _telemetry.span(
        f"replay.record_overhead {label}",
        service=infra,
        label=label,
        **_attributes("replay", overhead),
    ):
        pass
    key, pairs = _cache.key_inputs(file_deps, digest)
    if key != recording.key:
        # An input changed while the part built: the manifest would misstate
        # what the key was built from, so nothing is published or evaluated.
        record["outcome"] = "inputs_moved"
        return
    inputs = dict(pairs)
    data = bundle(recording)
    bundle_name, _ = blob_names(summary["engine"], recording.stem, recording.key)
    stored = _cache.publication(recording.key)
    outcome = None if stored is None else stored[0]
    published = manifest(
        recording,
        summary,
        inputs,
        bundle_name,
        data,
        archive=stored[1] if stored is not None and outcome == "stored" else None,
        sw_build=seat_build(),
    )
    record["bundle_bytes"] = len(data)
    record["bound"] = bound_archive(published) is not None
    with _telemetry.span(f"replay.publish {label}", service=infra, label=label) as sp:
        # Only a build that stored the key's archive publishes its recording:
        # one whose store lost the race made none of it (its recording
        # describes another build's part), and one that stored nothing, or
        # failed to, would leave an unbound manifest holding the key's
        # create-only names. ``publish`` is then the store's outcome.
        record["publish"] = (
            publish(recording, published, data)
            if outcome == "stored"
            else outcome or "unstored"
        )
        sp.set_attribute("replay.publish", record["publish"])
        sp.set_attribute("replay.bundle_bytes", len(data))
        sp.set_attribute("replay.bound", bound_archive(published) is not None)
    if recording.mode not in (ReplayMode.SHADOW, ReplayMode.REUSE):
        record["outcome"] = "recorded"
        return
    reuse = recording.reuse
    replayed = reuse is not None and reuse.replayed and reuse.lookup is not None
    if replayed:
        # The pre-build attempt looked the base up and replayed against it.
        found = reuse.lookup
        lookup_s = reuse.seconds.get("lookup")
    else:
        started = time.monotonic()
        with _telemetry.span(
            f"replay.base_lookup {label}", service=infra, label=label
        ) as sp:
            found = find_base(
                blob_prefix(summary["engine"], recording.stem),
                inputs,
                published["recording_id"],
                published["salt"],
            )
            sp.set_attribute("replay.lookup", found.outcome.value)
            sp.set_attribute("replay.listed", found.listed)
            sp.set_attribute("replay.read", found.read)
        lookup_s = time.monotonic() - started
    record.update(
        lookup=found.outcome.value,
        lookup_s=None if lookup_s is None else round(lookup_s, 3),
        listed=found.listed,
        read=found.read,
    )
    if found.base is None:
        record["outcome"] = "no_base"
        return
    base = found.base
    record.update(
        base_key=base.manifest.get("key"),
        base_recorded_utc=base.manifest.get("recorded_utc"),
        differing_count=len(base.differing),
        differing_classes=base.classes,
        differing=list(base.differing[:DIFFERING_LISTED]),
    )
    started = time.monotonic()
    with _telemetry.span(f"replay.shadow {label}", service=infra, label=label) as sp:
        try:
            if replayed:
                shadow = judge_replayed(recording, reuse, summary)
            else:
                shadow = evaluate(recording, base, summary)
        except Exception as exc:  # noqa: BLE001 - a failed evaluation is a verdict
            shadow = Shadow("error", reason=repr(exc)[:EVIDENCE_CHARS])
        wall = round(time.monotonic() - started, 3)
        divergence = shadow.divergence or {}
        fields = {
            "verdict": shadow.verdict,
            "verdict_class": shadow.verdict_class.value,
            "recorded": shadow.recorded,
            "served": shadow.served,
            "divergence_member": divergence.get("member_actual")
            or divergence.get("member_expected"),
            "divergence_field": divergence.get("field"),
            "divergence_caller": divergence.get("caller_actual"),
            "divergence_index": divergence.get("index"),
            "inert_recorded": shadow.inert.get("recorded"),
            "inert_served": shadow.inert.get("served"),
            "inert_unserved": shadow.inert.get("unserved"),
            "substitutions": shadow.substitutions,
            "base_key": str(base.manifest.get("key", ""))[:12],
            "differing_count": len(base.differing),
            "differing_classes": ",".join(f"{k}:{v}" for k, v in base.classes.items()),
            "ground_truth": shadow.ground_truth,
            "truth_cause": shadow.truth_cause,
            "artefact_outcome": shadow.outcome,
            "outcome_signals": ",".join(
                f"{name}:{signal}" for name, signal in shadow.outcome_signals.items()
            )
            or None,
            "soundness_alarm": shadow.soundness_alarm,
            "seat_nondeterminism": shadow.seat_nondeterminism,
            "noop_unexplained_divergence": shadow.noop_unexplained_divergence,
            "noop_outcome_unknown": shadow.noop_outcome_unknown,
            "noop_judgement": shadow.noop_judgement,
            "false_divergence": shadow.false_divergence,
            "judge_fault": shadow.judge_fault,
            "judge_faults": ",".join(
                str(fault.get("step")) for fault in shadow.judge_faults
            )
            or None,
            "wall_s": wall,
        }
        for name, value in _attributes("replay", fields).items():
            sp.set_attribute(name, value)
    record.update(
        **{
            k: v
            for k, v in fields.items()
            if k not in ("base_key", "differing_count", "differing_classes")
        },
        reason=shadow.reason,
    )
    key = str(base.manifest.get("key", ""))
    if shadow.soundness_alarm:
        evidence = _evidence(base, shadow)
        record["alarm_evidence"] = evidence
        _telemetry.error(
            f"[com-replay] SOUNDNESS ALARM {label}: the replay against base "
            f"{key[:12]} was a no-op, but this build made another part than "
            f"that base: {evidence}",
            label=label,
            base_key=key,
        )
        record["revoked"] = _revoke_alarmed(
            summary["engine"], recording.stem, base.manifest
        )
    if shadow.noop_unexplained_divergence:
        _telemetry.warn(
            f"[com-replay] noop_unexplained_divergence {label}: the replay "
            f"against base {key[:12]} was a no-op and this build made that "
            "base's part, but its requests diverged from it with every earlier "
            "SolidWorks answer the same: neither the source nor SolidWorks "
            "explains it (an input the replay does not pin?): "
            f"{_evidence(base, shadow)}",
            label=label,
            base_key=key,
        )
    if shadow.judge_fault:
        _telemetry.warn(
            f"[com-replay] judge_fault {label}: judging this build's recording "
            f"against base {key[:12]} raised, so what it judged is unknown (the "
            f"request divergence is kept): {_evidence(base, shadow)}",
            label=label,
            base_key=key,
        )
    record["outcome"] = "evaluated"
    _write_shadow(recording, record)


def _revoke_alarmed(engine: str, stem: str, base: dict[str, Any]) -> str:
    """A soundness alarm against ``base``: revoke it. The revocation's
    outcome, or ``error`` after a WARN (the alarm itself is already raised)."""
    try:
        return revoke(engine, stem, str(base["key"]), "a SOUNDNESS ALARM against it")
    except Exception as exc:  # noqa: BLE001 - the alarm is raised either way
        _telemetry.warn(
            f"[com-replay] part:{stem}: SOUNDNESS ALARM base not revoked: {exc!r}",
            label=f"part:{stem}",
        )
        return "error"


def _write_shadow(recording: Recording, record: dict[str, Any]) -> None:
    """The last shadow outcome of the stem, for a local look (best-effort)."""
    try:
        (recording.directory / SHADOW_NAME).write_text(
            json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
    except OSError:
        pass
