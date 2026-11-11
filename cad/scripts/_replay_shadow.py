"""Shadow COM-conversation recording of part builds (dodo's side).

One switch, read here and nowhere else (:func:`mode`): ``HARMONIC_COM_REPLAY``
= ``off`` | ``record`` | ``shadow`` (unset: ``shadow``).

* ``off``: a part build runs exactly as it did before recording existed: the
  same command line, and the engine (``_com_conversation``) is never imported.
* ``record``: the build runs through the driver (``com_replay.py record``):
  same seat, same outputs, same exit codes, its COM conversation recorded under
  ``cad/out/replay/<stem>/``. Once the seat is released the recording is
  published BESIDE the part archive as two cache sidecars named from the part
  key (``com-replay/<engine>/<stem>/<key>.tar`` and ``.json``): create-only,
  ``rw`` only, never fatal (``_artifact_cache.publish_sidecar``).
* ``shadow``: ``record``, then, still off the seat, the nearest earlier
  recording of the stem (fewest differing key inputs) is replayed against the
  CURRENT source in a sandboxed subprocess and compared with this build's
  recording. The verdict is telemetry only: span ``replay.shadow <label>`` on
  ``build-infra`` and a ``replay_shadow`` record in ``cad/out/reports/cache.jsonl``.

Nothing is restored, reused or published FROM a base recording: every output and
every cache key is exactly what an unrecorded build produces. A driver exit of
:data:`EXIT_RECORD_FAULT` (the recorder failed where the build's results cannot
be trusted, not the script or SolidWorks) re-runs the build once unrecorded on
the same seat (``dodo._exec_com``); a recorder fault after the build had its
results only stops the recording (:meth:`Recording.exited`). Either way nothing
of that recording is published. The script's and SolidWorks' own failures stay
the build's, never retried here. Each recorded leaf ends with one INFO line
(:func:`report_line`). DEVELOPING.md "COM conversation recording (shadow)" has
the operator view.
"""

from __future__ import annotations

import contextvars
import datetime
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePath
from typing import Any

import _artifact_cache as _cache
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
# under ``o``, so its paths are the build's own plus SCRATCH_OVERHEAD.
SCRATCH = OUT_ROOT / "rs"
SCRATCH_NAME_CHARS = 8  # tempfile.mkdtemp(prefix="")
WORK_BASE, WORK_OUTPUT, WORK_TMP = "b", "o", "t"
DRIVER = SCRIPTS_DIR / "com_replay.py"
BLOB_ROOT = "com-replay"
# 2: bundles of engine log schema 2 (flat captures).
MANIFEST_SCHEMA = 2
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
# Bound on any evidence string carried by a span, log or cache.jsonl record.
EVIDENCE_CHARS = 4000
DIFFERING_LISTED = 40


class Recovery(StrEnum):
    """_com_conversation.Recovery, restated (pinned equal by test): what a
    recorder fault cost the build."""

    DEGRADED = "degraded"  # recording stopped; the build finished as its own
    RERUN = "rerun"  # driver exit EXIT_RECORD_FAULT; re-run unrecorded


class ReplayMode(StrEnum):
    OFF = "off"
    RECORD = "record"
    SHADOW = "shadow"


DEFAULT_MODE = ReplayMode.SHADOW
_UNKNOWN_MODES: set[str] = set()


def mode() -> ReplayMode:
    """The one reading of ``HARMONIC_COM_REPLAY``. Unset or empty is the
    default (``shadow``). Anything else unknown is a typo, not a request:
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
    OTHER = "other"


def input_class(tag: str) -> InputClass:
    """Classify one repo-relative key-input tag (``_artifact_cache.key_inputs``)."""
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
            )
        ),
        PathNeed("work", str(work), directory=True),
        PathNeed("work tmp", str(work / WORK_TMP), directory=True),
        PathNeed("work replay.json", str(work / "replay.json")),
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


def plan(stem: str, script: Path, key: str) -> Recording | None:
    """The recording of this part build, or None: mode ``off`` (the build runs
    exactly as before), a checkout too deep for the recording's own paths, or
    a recording directory that cannot be prepared (the build runs unrecorded;
    recording never costs a build)."""
    current = mode()
    if current is ReplayMode.OFF:
        return None
    too_long = [
        need for need in path_needs(stem, RECORDINGS, SCRATCH) if need.headroom < 0
    ]
    if too_long:
        _telemetry.warn(
            f"[com-replay] part:{stem}: {too_long[0].purpose} path "
            f"{too_long[0].path} is {len(too_long[0].path)} characters, past the "
            "Windows limit; building unrecorded",
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
            "building unrecorded",
            label=f"part:{stem}",
        )
        return None
    return Recording(current, stem, script, key, directory)


# ---------------------------------------------------------------------------
# Publication: two sidecars beside the part archive
# ---------------------------------------------------------------------------


def blob_prefix(engine: str, stem: str) -> str:
    """Every recording of ``stem`` by this engine: what the base lookup lists.
    A log only replays under the engine that wrote it, so the engine digest
    scopes the listing."""
    return f"{BLOB_ROOT}/{engine[:16]}/{stem}/"


def blob_names(engine: str, stem: str, key: str) -> tuple[str, str]:
    """``(bundle, manifest)`` sidecar names of the recording of part ``key``."""
    prefix = blob_prefix(engine, stem)
    return f"{prefix}{key}.tar", f"{prefix}{key}.json"


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
) -> dict[str, Any]:
    """The small record a later build's base lookup reads instead of a bundle."""
    return {
        "schema": MANIFEST_SCHEMA,
        "recording_id": uuid.uuid4().hex,
        "label": recording.label,
        "stem": recording.stem,
        "key": recording.key,
        "inputs": inputs,
        "engine": summary["engine"],
        "recipe_requests": summary.get("recipe_requests"),
        "calls": summary.get("calls"),
        "inert_calls": summary.get("inert_calls"),
        "callers": summary.get("callers"),
        "sw_revision": summary.get("sw_revision"),
        "environment": summary.get("environment"),
        "bundle": {
            "name": bundle_name,
            "sha256": hashlib.sha256(bundle_bytes).hexdigest(),
            "size": len(bundle_bytes),
        },
        "recorded_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    }


def publish(recording: Recording, record: dict[str, Any], data: bytes) -> str:
    """Bundle first, then the manifest (a manifest never names a missing
    bundle). The manifest's outcome is the publication's."""
    bundle_outcome = _cache.publish_sidecar(record["bundle"]["name"], data)
    if bundle_outcome not in ("stored", "exists"):
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
) -> Base | None:
    """The candidate with the fewest differing inputs; a tie goes to the most
    recently published. Never the recording being evaluated."""
    best: Base | None = None
    for record, modified in candidates:
        if record.get("schema") != MANIFEST_SCHEMA:
            continue
        if exclude_id is not None and record.get("recording_id") == exclude_id:
            continue
        candidate = Base(
            record, differing_inputs(record.get("inputs") or {}, inputs), modified
        )
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


def find_base(
    prefix: str,
    inputs: dict[str, str],
    exclude_id: str | None,
    *,
    budget: float = LOOKUP_SECONDS,
    limit: int = LOOKUP_MANIFESTS,
) -> LookupResult:
    """One listing of ``prefix`` and at most ``limit`` manifest reads, newest
    first, inside ``budget`` seconds of wall time; past it, no base."""
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
    base = nearest(candidates, inputs, exclude_id)
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


@dataclass
class Shadow:
    """What a shadow replay of the current source against a base found."""

    verdict: str
    recorded: int | None = None
    served: int | None = None
    divergence: dict[str, Any] | None = None
    inert: dict[str, Any] = field(default_factory=dict)
    substitutions: int | None = None
    reason: str | None = None
    ground_truth: str = "unknown"
    request_divergence: dict[str, Any] | None = None

    @property
    def soundness_alarm(self) -> bool:
        """A replay NOOP although the fresh recording's requests diverged
        from the base: the replay would have reused a wrong artefact."""
        return self.verdict == "noop" and self.ground_truth == "diverged"

    @property
    def false_divergence(self) -> bool:
        """The replay stopped although the fresh recording issued the base's
        exact requests (a missed reuse, never an unsound one)."""
        return self.verdict != "noop" and self.ground_truth == "same"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _child_env(summary: dict[str, Any], tmp: Path) -> dict[str, str]:
    """The replay's environment: the recorded build's pinned process inputs
    (the summary's ``environment``), this span as parent, temporary files in
    the task's own scratch, no bytecode written into the checkout."""
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
    SCRATCH.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="", dir=SCRATCH))
    base_dir = work / WORK_BASE
    tmp = work / WORK_TMP
    base_dir.mkdir()
    tmp.mkdir()
    try:
        described = base.manifest.get("bundle") or {}
        fetched: dict[str, bytes | None] = {}

        def download() -> None:
            fetched["data"] = _cache.fetch_sidecar(str(described.get("name")))

        if not within(deadline - time.monotonic(), download):
            return Shadow("timeout", reason="bundle download exceeded the budget")
        data = fetched.get("data")
        if data is None or hashlib.sha256(data).hexdigest() != described.get("sha256"):
            return Shadow(
                "unavailable", reason="base bundle absent or not the manifest's"
            )
        unbundle(data, base_dir)
        env = _child_env(summary, tmp)
        replay_result = work / "replay.json"
        replay_rc = _run(
            [
                sys.executable,
                str(DRIVER),
                "replay",
                str(recording.script),
                "--log",
                str(base_dir / LOG_NAME),
                "--capture-dir",
                str(base_dir / CAPTURE_NAME),
                "--scratch",
                str(work / WORK_OUTPUT),
                "--result",
                str(replay_result),
                "--base-outputs",
                str(OUT_ROOT),
            ],
            env,
            deadline,
            recording.directory / REPLAY_LOG_NAME,
        )
        diff_result = work / "diff.json"
        diff_rc = _run(
            [
                sys.executable,
                str(DRIVER),
                "diff",
                str(base_dir / LOG_NAME),
                str(recording.log),
                "--result",
                str(diff_result),
            ],
            env,
            deadline,
            recording.directory / DIFF_LOG_NAME,
        )
        return shadow_of(
            replay_rc, _read_json(replay_result), diff_rc, _read_json(diff_result)
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


def shadow_of(
    replay_rc: int | None,
    replay: dict[str, Any] | None,
    diff_rc: int | None,
    diff: dict[str, Any] | None,
) -> Shadow:
    """Fold the replay result and the request comparison into one Shadow."""
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
    return shadow


# ---------------------------------------------------------------------------
# After the build: publish, look up, evaluate -- telemetry only
# ---------------------------------------------------------------------------


def after_build(
    recording: Recording | None,
    file_deps: list[str],
    digest: Callable[[str], str],
) -> None:
    """Publish this build's recording and (``shadow``) evaluate a replay of
    it. Runs after the seat is released; never raises, never touches an
    output. ``recording`` None (mode ``off``) is a no-op; a faulted recording
    (:meth:`Recording.exited`) publishes nothing. Every recorded build ends
    with one ``replay_shadow`` cache.jsonl record and one INFO line
    (:func:`report_line`)."""
    if recording is None:
        return
    record: dict[str, Any] = {"mode": recording.mode.value}
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
                f"[com-replay] {recording.label}: shadow step failed: {exc!r}",
                label=recording.label,
            )
            record.update(outcome="error", error=repr(exc)[:EVIDENCE_CHARS])
    _cache.record_event("replay_shadow", recording.label, recording.key, **record)
    _telemetry.info(
        report_line(recording.label, record),
        label=recording.label,
        outcome=record["outcome"],
    )


def report_line(label: str, record: dict[str, Any]) -> str:
    """One line (never a newline) of what a recorded build's shadow step did:
    publication outcome and bundle bytes; the base lookup (base key or none,
    manifests listed and read, seconds); the shadow replay's verdict, requests
    served of recorded, seconds; and the ground truth from this build's own
    requests. ``-`` marks a step the build never reached."""

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
        f"publish={shown('publish')} bytes={shown('bundle_bytes')}",
        f"lookup={shown('lookup')} base={base} differing={shown('differing_count')} "
        f"listed={shown('listed')} read={shown('read')} {shown('lookup_s', 's')}",
        f"shadow={shown('verdict')} served={shown('served')}/{shown('recorded')} "
        f"{shown('wall_s', 's')}",
        f"truth={shown('ground_truth')}",
    ]
    if record.get("soundness_alarm"):
        segments.append("SOUNDNESS ALARM")
    return " | ".join(segments)


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
    published = manifest(recording, summary, inputs, bundle_name, data)
    record["bundle_bytes"] = len(data)
    with _telemetry.span(f"replay.publish {label}", service=infra, label=label) as sp:
        record["publish"] = publish(recording, published, data)
        sp.set_attribute("replay.publish", record["publish"])
        sp.set_attribute("replay.bundle_bytes", len(data))
    if recording.mode is not ReplayMode.SHADOW:
        record["outcome"] = "recorded"
        return
    started = time.monotonic()
    with _telemetry.span(
        f"replay.base_lookup {label}", service=infra, label=label
    ) as sp:
        found = find_base(
            blob_prefix(summary["engine"], recording.stem),
            inputs,
            published["recording_id"],
        )
        sp.set_attribute("replay.lookup", found.outcome.value)
        sp.set_attribute("replay.listed", found.listed)
        sp.set_attribute("replay.read", found.read)
    record.update(
        lookup=found.outcome.value,
        lookup_s=round(time.monotonic() - started, 3),
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
            shadow = evaluate(recording, base, summary)
        except Exception as exc:  # noqa: BLE001 - a failed evaluation is a verdict
            shadow = Shadow("error", reason=repr(exc)[:EVIDENCE_CHARS])
        wall = round(time.monotonic() - started, 3)
        divergence = shadow.divergence or {}
        fields = {
            "verdict": shadow.verdict,
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
            "soundness_alarm": shadow.soundness_alarm,
            "false_divergence": shadow.false_divergence,
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
    if shadow.soundness_alarm:
        evidence = json.dumps(
            {
                "base_key": base.manifest.get("key"),
                "differing": list(base.differing[:DIFFERING_LISTED]),
                "replay_verdict": shadow.verdict,
                "served": shadow.served,
                "recorded": shadow.recorded,
                "request_divergence": shadow.request_divergence,
            },
            sort_keys=True,
            default=str,
        )[:EVIDENCE_CHARS]
        record["alarm_evidence"] = evidence
        _telemetry.error(
            f"[com-replay] SOUNDNESS ALARM {label}: the replay against base "
            f"{str(base.manifest.get('key', ''))[:12]} was a no-op, but this "
            f"build's own requests diverged from that base: {evidence}",
            label=label,
            base_key=str(base.manifest.get("key", "")),
        )
    record["outcome"] = "evaluated"
    _write_shadow(recording, record)


def _write_shadow(recording: Recording, record: dict[str, Any]) -> None:
    """The last shadow outcome of the stem, for a local look (best-effort)."""
    try:
        (recording.directory / SHADOW_NAME).write_text(
            json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
    except OSError:
        pass
