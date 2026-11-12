"""Tests for shadow COM-conversation recording of part builds (``_replay_shadow``).

No SolidWorks and no Azure: the cache is test_artifact_cache's in-memory
block-blob service (plus listing), the recorded build is test_com_conversation's
fake application, and every sink is under ``tmp_path``.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import datetime
import hashlib
import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path, PureWindowsPath
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parents[1]
sys.path.insert(0, str(SCRIPTS))

import _artifact_cache as cache  # noqa: E402
import _buildgraph  # noqa: E402
import _com_conversation as conv  # noqa: E402
import _com_outcome  # noqa: E402
import _replay_shadow as shadow  # noqa: E402
import _telemetry  # noqa: E402
from test_artifact_cache import _BlockBlobService  # noqa: E402
from test_com_conversation import (  # noqa: E402
    _RECORD_DRIVER,
    DEPENDENT_DRIVER,
    DRAWING_SCRIPT,
    drawing_outputs,
)

_STEM = "sh_widget"
_ENGINE = "e" * 64


class _ListingService(_BlockBlobService):
    """The block-blob fake plus ``list_blobs``; each upload is one second
    newer than the last, so publication order is listing order. A slow
    listing (``list_delay``) lists nothing: the lookup that gave up on it
    must not read the cache after the test has restored it."""

    def __init__(self) -> None:
        super().__init__()
        self.modified: dict[str, datetime.datetime] = {}
        self.list_delay = 0.0
        self.fail_uploads = False

    def get_blob_client(self, name: str) -> Any:
        client = super().get_blob_client(name)
        service = self
        upload = client.upload_blob

        def upload_blob(data: Any, **kwargs: Any) -> None:
            if service.fail_uploads:
                raise RuntimeError("injected: 503 server busy")
            upload(data, **kwargs)
            service.modified[name] = datetime.datetime.fromtimestamp(
                1_800_000_000 + len(service.modified), datetime.UTC
            )

        client.upload_blob = upload_blob
        return client

    def list_blobs(self, *, name_starts_with: str) -> Any:
        self.calls.append(("list", name_starts_with))
        if self.list_delay:
            time.sleep(self.list_delay)
            return
        for name in sorted(self.committed):
            if name.startswith(name_starts_with):
                yield types.SimpleNamespace(
                    name=name, last_modified=self.modified[name]
                )


@pytest.fixture
def blob(tmp_path, monkeypatch):
    """An ``rw`` cache on the listing fake; cache.jsonl, the key sidecars and
    the recordings under ``tmp_path``."""
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.setattr(cache, "_REPORTS", tmp_path / "reports")
    monkeypatch.setattr(cache, "_EVENTS_LOG", tmp_path / "reports" / "cache.jsonl")
    monkeypatch.setattr(cache, "_KEYDIR", tmp_path / "cache-keys")
    monkeypatch.setattr(cache, "_KEY_INPUTS", {})
    monkeypatch.setattr(cache, "_KEY_CONTEXT", {})
    monkeypatch.setattr(cache, "_KEY_MANIFESTS", {})
    monkeypatch.setattr(cache, "_PREWARMED", None)
    service = _ListingService()
    monkeypatch.setattr(cache, "_BACKEND", cache._BlobBackend(service))
    monkeypatch.setattr(cache, "_PUBLISHED", {})
    monkeypatch.setattr(shadow, "RECORDINGS", tmp_path / "replay")
    monkeypatch.setattr(shadow, "OUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(shadow, "SCRATCH", tmp_path / "out" / "rs")
    return service


def _events(tmp_path: Path, event: str) -> list[dict[str, Any]]:
    log = tmp_path / "reports" / "cache.jsonl"
    if not log.exists():
        return []
    records = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    return [record for record in records if record["event"] == event]


def _digest(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _stored(key: str) -> None:
    """This process stored an archive under ``key`` (``cache.publication``),
    as the build of every recording that publishes did."""
    archive = hashlib.sha256(b"archive of " + key.encode()).hexdigest()
    cache._PUBLISHED[key] = ("stored", (archive, 1024))


class _Spans:
    """``_telemetry.span`` and ``_telemetry.event`` recorded, not exported."""

    def __init__(self) -> None:
        self.opened: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    @contextlib.contextmanager
    def span(self, name: str, /, *, service: str | None = None, **attributes: Any):
        entry = {"name": name, "service": service, **attributes}
        self.opened.append(entry)
        yield types.SimpleNamespace(set_attribute=entry.__setitem__)

    def event(self, name: str, **attributes: Any) -> None:
        self.events.append({"name": name, **attributes})

    def named(self, prefix: str) -> list[dict[str, Any]]:
        return [entry for entry in self.opened if entry["name"].startswith(prefix)]


@pytest.fixture
def spans(monkeypatch):
    recorder = _Spans()
    monkeypatch.setattr(_telemetry, "span", recorder.span)
    monkeypatch.setattr(_telemetry, "event", recorder.event)
    return recorder


@pytest.fixture
def logged(monkeypatch):
    messages: dict[str, list[str]] = {"info": [], "warn": [], "error": []}
    for level in messages:
        monkeypatch.setattr(
            _telemetry,
            level,
            lambda message, *, _level=level, **_fields: messages[_level].append(
                message
            ),
        )
    return messages


def _summary(**changes: Any) -> dict[str, Any]:
    """A clean driver summary (``com_replay.py record --summary``)."""
    return {
        "schema": 1,
        "exit_code": 0,
        "rc": 0,
        "faults": [],
        "engine": _ENGINE,
        "complete": True,
        "calls": 120,
        "inert_calls": 20,
        "recipe_requests": 100,
        "callers": "divergence",
        "sw_revision": "34.3.0",
        "environment": {"PYTHONHASHSEED": None},
        "clock_seconds": {"engine": 1.5, "com": 80.0},
        "window_seconds": 100.0,
        "escape_audit_seconds": 0.03,
        "capture_stored_bytes": 400_000,
        **changes,
    }


def _built(
    tmp_path: Path, config: str, **summary: Any
) -> tuple[shadow.Recording, list[str]]:
    """A part build that ran under the driver and stored its archive (as every
    build whose recording publishes did): its recording directory holds a log,
    a capture and the summary (``plan`` under the current mode)."""
    source = tmp_path / "src"
    source.mkdir(exist_ok=True)
    script = source / f"build_{_STEM}.py"
    script.write_text("# the part\n", encoding="utf-8")
    (source / "widget.yaml").write_text(config, encoding="utf-8")
    deps = [str(script), str(source / "widget.yaml")]
    key, _ = cache.key_inputs(deps, _digest)
    recording = shadow.plan(_STEM, script, key)
    assert recording is not None
    recording.log.write_bytes(b"log of " + key.encode())
    recording.captures.mkdir()
    (recording.captures / shadow.CAPTURE_FILE).write_bytes(
        b"capture of " + key.encode()
    )
    recording.summary_path.write_text(json.dumps(_summary(**summary)), "utf-8")
    _stored(key)
    return recording, deps


def _load_dodo() -> Any:
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# The switch
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, shadow.ReplayMode.REUSE),
        ("", shadow.ReplayMode.REUSE),
        ("off", shadow.ReplayMode.OFF),
        ("record", shadow.ReplayMode.RECORD),
        (" Shadow ", shadow.ReplayMode.SHADOW),
        ("reuse", shadow.ReplayMode.REUSE),
    ],
)
def test_mode_is_one_variable_defaulting_to_reuse(monkeypatch, logged, value, expected):
    if value is None:
        monkeypatch.delenv(shadow.MODE_ENV, raising=False)
    else:
        monkeypatch.setenv(shadow.MODE_ENV, value)
    assert shadow.mode() is expected
    assert logged["warn"] == []


def test_an_unknown_mode_is_off_and_warns_once(monkeypatch, logged):
    monkeypatch.setattr(shadow, "_UNKNOWN_MODES", set())
    monkeypatch.setenv(shadow.MODE_ENV, "on")
    assert [shadow.mode() for _ in range(3)] == [shadow.ReplayMode.OFF] * 3
    assert len(logged["warn"]) == 1 and "'on'" in logged["warn"][0]


def test_the_restated_engine_facts_are_the_engines(tmp_path):
    assert shadow.EXIT_RECORD_FAULT == conv.EXIT_RECORD_FAULT
    assert shadow.CAPTURE_NAME == conv.capture_dir_of(Path(shadow.LOG_NAME)).name
    assert {r.value for r in shadow.Recovery} == {r.value for r in conv.Recovery}
    # The path budget's capture name is every capture name's width.
    assert shadow.CAPTURE_FILE == conv.capture_name(0)
    assert len(conv.capture_name(999_999)) == len(shadow.CAPTURE_FILE)
    # And its work-directory name is mkdtemp's.
    work = Path(tempfile.mkdtemp(prefix="", dir=tmp_path))
    assert len(work.name) == shadow.SCRATCH_NAME_CHARS


def test_dodos_side_never_imports_the_engine():
    code = (
        "import os, sys\n"
        f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
        "from pathlib import Path\n"
        "import _replay_shadow as shadow\n"
        "os.environ[shadow.MODE_ENV] = 'off'\n"
        "assert shadow.plan('x', Path('build_x.py'), 'k') is None\n"
        "shadow.after_build(None, [], str)\n"
        "loaded = sorted(m for m in ('_com_conversation', 'com_replay', 'pythoncom', '_session') if m in sys.modules)\n"
        "assert not loaded, loaded\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --------------------------------------------------------------------------- #
# The part action: off is the old command; recording wraps it, observes after
# --------------------------------------------------------------------------- #
def _part_action(dodo: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    script = tmp_path / f"build_{_STEM}.py"
    script.write_text("", encoding="utf-8")
    deps = [str(script)]
    order: list[str] = []
    runs: list[tuple[list[str], Any]] = []
    observed: list[tuple[Any, list[str], Any]] = []
    outcomes = iter((False, False))  # probe MISS, re-probe under the seat MISS
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: deps)
    monkeypatch.setattr(
        dodo, "_part_cache_outputs", lambda _stem: [tmp_path / "sh-widget.SLDPRT"]
    )
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_a: next(outcomes))
    monkeypatch.setattr(
        dodo._cache, "store", lambda *_a: (order.append("store"), "stored")[1]
    )
    monkeypatch.setattr(dodo, "_stamp_part_execution", lambda _stem: None)
    monkeypatch.setattr(dodo, "_validate_part_configuration_outputs", lambda *_a: None)
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)

    @contextlib.contextmanager
    def seat(_label: str):
        order.append("seat")
        yield 0.0
        order.append("seat released")

    def exec_com(cmd, label, log_stem=None, **options):
        order.append("build")
        runs.append((cmd, options.get("recording")))

    real_after = dodo._replay_shadow.after_build

    def after_build(recording, file_deps, digest):
        order.append("observe")
        observed.append((recording, file_deps, digest))
        real_after(None, file_deps, digest)

    monkeypatch.setattr(dodo, "_com_seat", seat)
    monkeypatch.setattr(dodo, "_exec_com", exec_com)
    monkeypatch.setattr(dodo._replay_shadow, "after_build", after_build)
    dodo._cached_part_action(_STEM, script)
    return script, deps, order, runs, observed


@pytest.mark.parametrize(
    ("replay_mode", "cache_mode"),
    [("off", "rw"), ("shadow", "ro")],
    ids=["replay-off", "cache-read-only"],
)
def test_off_builds_with_the_unrecorded_command_and_records_nothing(
    blob, tmp_path, monkeypatch, replay_mode, cache_mode
):
    dodo = _load_dodo()
    monkeypatch.setenv(shadow.MODE_ENV, replay_mode)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", cache_mode)
    script, deps, order, runs, observed = _part_action(dodo, monkeypatch, tmp_path)
    assert runs == [([sys.executable, str(script)], None)]
    assert observed == [(None, deps, dodo.ContentChecker._digest)]
    assert order == ["seat", "build", "seat released", "store", "observe"]
    assert not shadow.RECORDINGS.exists()


def test_shadow_builds_under_the_driver_and_observes_off_the_seat(
    blob, tmp_path, monkeypatch
):
    dodo = _load_dodo()
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    script, deps, order, runs, observed = _part_action(dodo, monkeypatch, tmp_path)
    [(command, recording)] = runs
    assert recording.mode is shadow.ReplayMode.SHADOW
    assert (recording.stem, recording.script, recording.key) == (
        _STEM,
        script,
        "k" * 64,
    )
    assert command == recording.command
    assert command[:4] == [sys.executable, str(shadow.DRIVER), "record", str(script)]
    assert recording.unrecorded == [sys.executable, str(script)]
    assert recording.directory == shadow.RECORDINGS / _STEM
    # Observation runs after the seat is released and the part is published,
    # with the very file_deps the key was computed from.
    assert order == ["seat", "build", "seat released", "store", "observe"]
    assert observed == [(recording, deps, dodo.ContentChecker._digest)]


class _Failed(Exception):
    pass


def _exec_com_runs(
    dodo: Any,
    monkeypatch: pytest.MonkeyPatch,
    recording: shadow.Recording | None,
    autostart: bool,
    codes: tuple[int, ...],
    degraded: bool = False,
) -> list[str]:
    """``dodo._exec_com`` with each subprocess answering the next exit code;
    the driver's summary names a ``rerun`` fault for exit 92 and (with
    ``degraded``) a ``degraded`` one for any other exit code."""
    runs: list[str] = []
    answers = iter(codes)

    def run_subprocess(cmd, label, log_stem=None, *, task=None, env_pins=None):
        driver = recording is not None and cmd == recording.command
        runs.append("driver" if driver else "unrecorded")
        # The driver, its unrecorded re-run and a plain build: one hash seed.
        assert env_pins == {"PYTHONHASHSEED": "0"}
        rc = next(answers)
        rerun = rc == shadow.EXIT_RECORD_FAULT
        if driver and (rerun or degraded):
            fault = {
                "where": "Recorder.call" if rerun else "Recorder.capture",
                "recovery": "rerun" if rerun else "degraded",
                "type": "OSError" if rerun else "FileNotFoundError",
                "message": "injected",
                "traceback": "Traceback ...\nOSError: injected",
            }
            recording.summary_path.write_text(
                json.dumps(_summary(exit_code=rc, complete=False, faults=[fault])),
                "utf-8",
            )
        return rc

    def fail_task(label, rc, **_kw):
        raise _Failed(rc)

    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: autostart)
    monkeypatch.setattr(dodo, "_com_retry_backoff", lambda: (0,))
    monkeypatch.setattr(dodo, "_run_subprocess", run_subprocess)
    monkeypatch.setattr(dodo, "_fail_task", fail_task)
    monkeypatch.setattr(dodo._sw_lifecycle, "is_connected", lambda: True)
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "force_recover",
        lambda: pytest.fail("a recorder fault recovered SolidWorks"),
    )
    command = recording.command if recording is not None else ["python", "build_x.py"]
    try:
        dodo._exec_com(
            command, f"part:{_STEM}", log_stem=f"part-{_STEM}", recording=recording
        )
    except _Failed as failed:
        runs.append(f"fail {failed.args[0]}")
    return runs


@pytest.mark.parametrize("autostart", [False, True], ids=["farm-leaf", "autostart"])
@pytest.mark.parametrize(
    ("codes", "degraded", "expected", "recovery"),
    [
        ((92, 0), False, ["driver", "unrecorded"], "rerun"),
        ((92, 1), False, ["driver", "unrecorded", "fail 1"], "rerun"),
        ((0,), True, ["driver"], "degraded"),
        ((1,), True, ["driver", "fail 1"], "degraded"),
        ((1,), False, ["driver", "fail 1"], None),
        ((0,), False, ["driver"], None),
    ],
    ids=[
        "rerun-then-clean",
        "rerun-then-script-failure",
        "degraded",
        "degraded-script-failure",
        "script-failure",
        "clean",
    ],
)
def test_only_a_rerun_fault_reruns_the_build_once_unrecorded(
    blob,
    tmp_path,
    monkeypatch,
    spans,
    logged,
    autostart,
    codes,
    degraded,
    expected,
    recovery,
):
    dodo = _load_dodo()
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    recording = shadow.plan(_STEM, tmp_path / f"build_{_STEM}.py", "k" * 64)
    runs = _exec_com_runs(dodo, monkeypatch, recording, autostart, codes, degraded)
    assert runs == expected
    assert recording.recovery == recovery and recording.faulted is bool(recovery)
    faults = [event for event in spans.events if event["name"] == "replay.record_fault"]
    records = _events(tmp_path, "replay_record_fault")
    if recovery is None:
        assert faults == [] and records == [] and logged["warn"] == []
        return
    where = "Recorder.call" if recovery == "rerun" else "Recorder.capture"
    assert [(f["where"], f["exit_code"], f["recovery"]) for f in faults] == [
        (where, codes[0], recovery)
    ]
    assert [(r["label"], r["where"], r["mode"], r["recovery"]) for r in records] == [
        (f"part:{_STEM}", where, "shadow", recovery)
    ]
    [warning] = logged["warn"]
    if recovery == "rerun":
        assert "re-running the build once unrecorded" in warning
    else:
        assert "nothing of this recording is published" in warning
    # A faulted recording is never published or evaluated; its one record
    # and INFO line say why.
    shadow.after_build(recording, [], _digest)
    [record] = _events(tmp_path, "replay_shadow")
    assert (record["outcome"], record["recovery"], record["where"]) == (
        "record_fault",
        recovery,
        where,
    )
    assert blob.committed == {}
    [line] = logged["info"]
    assert line.startswith(
        f"[com-replay] part:{_STEM}: record_fault ({recovery} in {where}): "
        "nothing published | publish=- bytes=-"
    )


def test_exit_92_without_a_recording_is_an_ordinary_failure(blob, monkeypatch):
    dodo = _load_dodo()
    assert _exec_com_runs(dodo, monkeypatch, None, False, (92,)) == [
        "unrecorded",
        "fail 92",
    ]


# --------------------------------------------------------------------------- #
# Publication: two create-only sidecars named from the part key
# --------------------------------------------------------------------------- #
def _blob_of(name: str) -> str:
    """The container blob behind sidecar ``name``: epoch after the prefix."""
    return name.replace("com-replay/", f"com-replay/epoch-{cache._CACHE_EPOCH}/", 1)


def test_a_recording_publishes_beside_the_part_archive(
    blob, tmp_path, monkeypatch, spans, logged
):
    monkeypatch.setenv(shadow.MODE_ENV, "record")
    recording, deps = _built(tmp_path, "size: 1\n")
    shadow.after_build(recording, deps, _digest)
    root = f"com-replay/{_ENGINE[:16]}/{_STEM}"
    tar_name, manifest_name = (
        f"{root}/bundle/{recording.key}.tar",
        f"{root}/manifest/{recording.key}.json",
    )
    assert shadow.blob_names(_ENGINE, _STEM, recording.key) == (
        tar_name,
        manifest_name,
    )
    tar_blob, manifest_blob = _blob_of(tar_name), _blob_of(manifest_name)
    assert sorted(blob.committed) == [tar_blob, manifest_blob]
    uploads = [call for call in blob.calls if call[0] == "upload"]
    assert [(name, options["overwrite"]) for _, name, options, _ in uploads] == [
        (tar_blob, False),
        (manifest_blob, False),
    ]
    published = json.loads(blob.content(manifest_blob))
    _, pairs = cache.key_inputs(deps, _digest)
    assert (published["stem"], published["key"], published["engine"]) == (
        _STEM,
        recording.key,
        _ENGINE,
    )
    assert published["inputs"] == dict(pairs) and published["recipe_requests"] == 100
    settings = cache.config_summary()
    assert (published["salt"], published["epoch"]) == (
        settings["salt"],
        settings["epoch"],
    )
    assert published["schema"] == shadow.MANIFEST_SCHEMA
    data = blob.content(tar_blob)
    assert published["bundle"] == {
        "name": tar_name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }
    shadow.unbundle(data, tmp_path / "restored")
    assert (
        tmp_path / "restored" / shadow.LOG_NAME
    ).read_bytes() == recording.log.read_bytes()
    capture = Path(shadow.CAPTURE_NAME) / shadow.CAPTURE_FILE
    assert (tmp_path / "restored" / capture).read_bytes() == (
        recording.directory / capture
    ).read_bytes()
    [record] = _events(tmp_path, "replay_shadow")
    assert (record["outcome"], record["publish"], record["mode"]) == (
        "recorded",
        "stored",
        "record",
    )
    assert record["bundle_bytes"] == len(data)
    assert record["overhead"]["overhead_pct"] == pytest.approx(
        100 * 1.53 / (100 - 1.53), abs=1e-3
    )
    assert logged["info"] == [
        f"[com-replay] part:{_STEM}: recorded | publish=stored bytes={len(data)} "
        "| lookup=- base=- differing=- listed=- read=- - | shadow=- served=-/- - "
        "| truth=- | outcome=- cause=-"
    ]
    published_spans = spans.named("replay.")
    assert [entry["name"] for entry in published_spans] == [
        f"replay.after_build part:{_STEM}",
        f"replay.record_overhead part:{_STEM}",
        f"replay.publish part:{_STEM}",
    ]
    assert published_spans[0]["replay.outcome"] == "recorded"
    assert {entry["service"] for entry in published_spans} == {
        _telemetry.BUILD_INFRA_SERVICE
    }
    # Sidecar transfers have their own spans, never the archives' cache.upload.
    assert [(e["name"], e["bytes"]) for e in spans.named("cache.")] == [
        ("cache.sidecar.upload", len(data)),
        ("cache.sidecar.upload", len(blob.content(manifest_blob))),
    ]
    # A second writer of the same key: create-only, the first bytes stand, and
    # its manifest (which describes ITS bytes) is never written.
    manifest_bytes = blob.content(manifest_blob)
    again, deps = _built(tmp_path, "size: 1\n")
    again.log.write_bytes(b"another writer's log")
    shadow.after_build(again, deps, _digest)
    assert _events(tmp_path, "replay_shadow")[-1]["publish"] == "exists"
    assert blob.content(tar_blob) == data
    assert blob.content(manifest_blob) == manifest_bytes
    assert [c[1] for c in blob.calls if c[0] == "upload"][2:] == [tar_blob]


def test_a_bundle_another_writer_stored_gets_no_manifest_of_ours(
    blob, tmp_path, monkeypatch
):
    # The other writer stored its bundle and stopped before its manifest: a
    # manifest now would name our digest over its bytes.
    monkeypatch.setenv(shadow.MODE_ENV, "record")
    recording, deps = _built(tmp_path, "size: 1\n")
    tar_name, manifest_name = shadow.blob_names(_ENGINE, _STEM, recording.key)
    assert cache.publish_sidecar(tar_name, b"their bundle") == "stored"
    shadow.after_build(recording, deps, _digest)
    assert _events(tmp_path, "replay_shadow")[-1]["publish"] == "exists"
    assert sorted(blob.committed) == [_blob_of(tar_name)]
    assert cache.list_sidecars(shadow.blob_prefix(_ENGINE, _STEM)) == []


@pytest.mark.parametrize(("cache_mode", "outcome"), [("ro", "skip"), ("off", "off")])
def test_only_a_cache_that_can_publish_records(
    blob, tmp_path, monkeypatch, cache_mode, outcome
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", cache_mode)
    # Nothing could be published, so nothing is recorded: the build runs
    # exactly as unrecorded and pays no recording or shadow time.
    assert shadow.plan(_STEM, tmp_path / f"build_{_STEM}.py", "k" * 64) is None
    assert not shadow.RECORDINGS.exists()
    # The sidecar layer itself publishes only in rw.
    _, manifest_name = shadow.blob_names(_ENGINE, _STEM, "a" * 64)
    assert cache.publish_sidecar(manifest_name, b"{}") == outcome
    assert blob.committed == {}


def test_a_publication_failure_is_soft(blob, tmp_path, monkeypatch, logged):
    monkeypatch.setenv(shadow.MODE_ENV, "record")
    recording, deps = _built(tmp_path, "size: 1\n")
    blob.fail_uploads = True
    shadow.after_build(recording, deps, _digest)  # does not raise
    [record] = _events(tmp_path, "replay_shadow")
    assert (record["outcome"], record["publish"]) == ("recorded", "error")
    assert blob.committed == {}
    assert any("not published" in message for message in logged["warn"])


def test_sidecars_cannot_name_an_archive(blob):
    for name in ("ab/" + "c" * 64 + ".tar.gz", "com-replay/../x", "com-replay\\x"):
        assert cache.publish_sidecar(name, b"x") == "error"
        assert cache.fetch_sidecar(name) is None
    assert blob.calls == []


def test_a_sidecar_is_served_only_as_published(blob, spans):
    name = f"{shadow.blob_prefix(_ENGINE, _STEM)}{'a' * 64}.json"
    assert cache.fetch_sidecar(name) is None  # absent
    assert cache.publish_sidecar(name, b'{"schema": 1}') == "stored"
    assert cache.fetch_sidecar(name) == b'{"schema": 1}'
    assert [(e["name"], e["bytes"]) for e in spans.named("cache.sidecar.")] == [
        ("cache.sidecar.download", 0),
        ("cache.sidecar.upload", 13),
        ("cache.sidecar.download", 13),
    ]
    # Bytes that are not the ones committed with the metadata: not served.
    blob.committed[_blob_of(name)] = [("single", b'{"schema": 2}')]
    assert cache.fetch_sidecar(name) is None


def test_an_epoch_bump_lists_and_fetches_no_older_sidecar(blob, logged, monkeypatch):
    prefix = shadow.blob_prefix(_ENGINE, _STEM)
    name = f"{prefix}{'a' * 64}.json"
    assert cache.publish_sidecar(name, b"{}") == "stored"
    before = _blob_of(prefix)
    assert (
        before
        == f"com-replay/epoch-{cache._CACHE_EPOCH}/{_ENGINE[:16]}/{_STEM}/manifest/"
    )
    assert sorted(blob.committed) == [_blob_of(name)]
    assert [listed for listed, _ in cache.list_sidecars(prefix)] == [name]
    monkeypatch.setattr(cache, "_CACHE_EPOCH", f"{cache._CACHE_EPOCH}-next")
    assert cache.list_sidecars(prefix) == []
    assert cache.fetch_sidecar(name) is None
    # Never listed and never read, so no integrity warning and no lookup
    # budget spent on the older epoch's sidecars.
    assert logged["warn"] == []
    lists = [call[1] for call in blob.calls if call[0] == "list"]
    assert lists == [before, _blob_of(prefix)] and before != _blob_of(prefix)


@pytest.mark.parametrize(
    ("summary", "outcome"),
    [
        ({"complete": False}, "no_recording"),
        ({"exit_code": 1}, "no_recording"),
    ],
)
def test_an_incomplete_recording_is_neither_published_nor_evaluated(
    blob, tmp_path, monkeypatch, summary, outcome
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    recording, deps = _built(tmp_path, "size: 1\n", **summary)
    shadow.after_build(recording, deps, _digest)
    assert blob.committed == {}
    assert [r["outcome"] for r in _events(tmp_path, "replay_shadow")] == [outcome]


def test_inputs_that_moved_during_the_build_publish_nothing(
    blob, tmp_path, monkeypatch
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    recording, deps = _built(tmp_path, "size: 1\n")
    Path(deps[1]).write_text("size: 9\n", encoding="utf-8")
    shadow.after_build(recording, deps, _digest)
    assert blob.committed == {}
    assert [r["outcome"] for r in _events(tmp_path, "replay_shadow")] == [
        "inputs_moved"
    ]


# --------------------------------------------------------------------------- #
# Base selection
# --------------------------------------------------------------------------- #
_SALT = "test-salt"


def _manifest(
    inputs: dict[str, str],
    recording_id: str,
    schema: int = shadow.MANIFEST_SCHEMA,
    salt: str = _SALT,
) -> dict:
    return {
        "schema": schema,
        "recording_id": recording_id,
        "inputs": inputs,
        "salt": salt,
        "key": recording_id,
    }


def test_the_nearest_base_differs_least_then_is_newest():
    now = {"a": "1", "b": "1", "c": "1"}
    candidates = [
        (_manifest({"a": "2", "b": "2", "c": "1"}, "newest-two-off"), 40.0),
        (_manifest({"a": "2", "b": "1", "c": "1"}, "old-one-off"), 10.0),
        (_manifest({"a": "1", "b": "2", "c": "1"}, "newer-one-off"), 20.0),
        # The exact inputs, but a bundle of the old format (captures mirrored
        # under their output paths): never a base.
        (_manifest(now, "same-but-old-format", schema=1), 50.0),
        (_manifest(now, "this-recording"), 60.0),
    ]
    base = shadow.nearest(candidates, now, "this-recording", _SALT)
    assert base is not None and base.manifest["recording_id"] == "newer-one-off"
    assert base.differing == ("b",)
    assert shadow.nearest([], now, None, _SALT) is None
    assert shadow.differing_inputs({"a": "1", "x": "1"}, {"a": "2", "y": "1"}) == (
        "a",
        "x",
        "y",
    )


def test_another_cache_salt_is_one_differing_input_never_a_filter():
    # Two throwaway salts (a native proof's two passes): the second still
    # finds the first's recordings, one input away.
    now = {"a": "1", "b": "1"}
    first = (_manifest(now, "pass-1", salt="throwaway-1"), 10.0)
    base = shadow.nearest([first], now, None, "throwaway-2")
    assert base is not None and base.differing == (shadow.SALT_INPUT,)
    assert base.classes == {"salt": 1}
    # The salt counts like any one file: a tie goes to the newer.
    one_file = (_manifest({"a": "2", "b": "1"}, "one-file", salt="throwaway-2"), 5.0)
    base = shadow.nearest([first, one_file], now, None, "throwaway-2")
    assert base is not None and base.manifest["recording_id"] == "pass-1"
    exact = (_manifest(now, "exact", salt="throwaway-2"), 1.0)
    base = shadow.nearest([first, one_file, exact], now, None, "throwaway-2")
    assert base is not None and base.differing == ()


def test_input_classes():
    assert {
        tag: shadow.input_class(tag).value
        for tag in (
            "cad/scripts/build_sh_widget.py",
            "cad/scripts/_session.py",
            "cad/config/release.yaml",
            "cad/config/fasteners.yaml",
            "cad/templates/part.prtdot",
            "cad/out/reports/.solidworks-mcp-submodule-part.digest",
            shadow.SALT_INPUT,
            "uv.lock",
        )
    } == {
        "cad/scripts/build_sh_widget.py": "script",
        "cad/scripts/_session.py": "helper",
        "cad/config/release.yaml": "release",
        "cad/config/fasteners.yaml": "config",
        "cad/templates/part.prtdot": "template",
        "cad/out/reports/.solidworks-mcp-submodule-part.digest": "adapter",
        shadow.SALT_INPUT: "salt",
        "uv.lock": "other",
    }


def _publish_manifests(count: int, best_at: int) -> str:
    """``count`` recordings, published oldest first under names that sort
    newest first (listing order is never recency order)."""
    prefix = shadow.blob_prefix(_ENGINE, _STEM)
    for index in range(count):
        inputs = {"a": "now" if index == best_at else f"old{index}"}
        bundle_name, manifest_name = shadow.blob_names(
            _ENGINE, _STEM, f"{count - index:064x}"
        )
        record = _manifest(inputs, f"id{index}")
        assert cache.publish_sidecar(bundle_name, b"bundle") == "stored"
        assert (
            cache.publish_sidecar(manifest_name, json.dumps(record).encode())
            == "stored"
        )
    return prefix


def test_the_lookup_reads_only_the_newest_manifests(blob):
    prefix = _publish_manifests(10, best_at=0)  # the exact match is the oldest
    found = shadow.find_base(prefix, {"a": "now"}, None, _SALT, limit=8)
    # The listing holds the manifests only (bundles live beside them).
    assert (found.outcome, found.listed, found.read) == (shadow.Lookup.FOUND, 10, 8)
    assert found.base is not None and found.base.manifest["recording_id"] == "id9"
    found = shadow.find_base(prefix, {"a": "now"}, None, _SALT, limit=10)
    assert found.base is not None and found.base.manifest["recording_id"] == "id0"
    assert [c for c in blob.calls if c[0] == "list"] == [("list", _blob_of(prefix))] * 2


def test_the_lookup_lists_every_name_before_it_takes_the_newest(blob):
    # A thousand older manifests whose names sort first: a listing cut in
    # name order would never see the newest one.
    prefix = shadow.blob_prefix(_ENGINE, _STEM)
    for index in range(1000):
        name = _blob_of(f"{prefix}{index:064x}.json")
        blob.committed[name] = [("single", b"{}")]
        blob.modified[name] = datetime.datetime.fromtimestamp(
            1_700_000_000 + index, datetime.UTC
        )
    newest = _manifest({"a": "now"}, "newest")
    _, manifest_name = shadow.blob_names(_ENGINE, _STEM, "f" * 64)
    assert cache.publish_sidecar(manifest_name, json.dumps(newest).encode()) == "stored"
    found = shadow.find_base(prefix, {"a": "now"}, None, _SALT, limit=1)
    assert (found.listed, found.read) == (1001, 1)
    assert found.base is not None and found.base.manifest["recording_id"] == "newest"


def test_the_lookup_gives_up_past_its_budget(blob):
    prefix = shadow.blob_prefix(_ENGINE, _STEM)
    blob.list_delay = 1.0
    started = time.monotonic()
    found = shadow.find_base(prefix, {"a": "now"}, None, _SALT, budget=0.2)
    assert found.outcome is shadow.Lookup.BUDGET and found.base is None
    assert time.monotonic() - started < 0.8  # never waits out the listing


def test_no_lookup_with_the_cache_off(blob, monkeypatch):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    found = shadow.find_base("com-replay/x/", {}, None, _SALT)
    assert found.outcome is shadow.Lookup.OFF
    assert blob.calls == []


# --------------------------------------------------------------------------- #
# Shadow verdicts: telemetry only, the alarm included
# --------------------------------------------------------------------------- #
_NOOP = {"verdict": "noop", "recorded": 10, "served": 10, "inert": {"recorded": 2}}
_DIVERGED = {
    "verdict": "diverged",
    "recorded": 10,
    "served": 4,
    "divergence": {"field": "member", "member_actual": "IApp.Add"},
}
_SAME = {"request_divergence": None, "truth_cause": None, "outcome": "same"}
_DIFFERENT = {
    "request_divergence": {"index": 4, "field": "args"},
    "truth_cause": "request",
    "outcome": "different",
}
# The fleet's first alarm (2026-11-11): one body's faces listed in another
# order, the same part.
_REORDERED = {
    "request_divergence": {"index": 1501, "field": "handle"},
    "truth_cause": "response:IFace2.Normal",
    "outcome": "same",
}
_UNMEASURED = {"request_divergence": None, "truth_cause": None, "outcome": "unknown"}
# The base's exact requests, another part: the seat changed the geometry.
_RESHAPED = {"request_divergence": None, "truth_cause": None, "outcome": "different"}
# The base's part, but requests that diverged with every earlier answer alike:
# neither the source (a noop) nor SolidWorks explains it.
_UNEXPLAINED = {
    "request_divergence": {"index": 9, "field": "args"},
    "truth_cause": "request",
    "outcome": "same",
}
# The same, but judging the divergence's cause raised: nothing establishes
# that every earlier answer was alike.
_UNJUDGED = {
    "request_divergence": {"index": 9, "field": "args"},
    "truth_cause": "error:RuntimeError",
    "outcome": "same",
    "judge_faults": [{"step": "truth_cause", "error": "RuntimeError: x"}],
}
# Diverged requests whose STL judgement raised: unknown, and a judge fault
# whatever the verdict (an STL neither build wrote is no fault: _UNMEASURED).
_FAULTED = {
    "request_divergence": {"index": 9, "field": "args"},
    "truth_cause": "request",
    "outcome": "unknown",
    "judge_faults": [{"step": "stl", "error": "KeyError: 'file'"}],
}
# 2026-11-12, mg_magnifying_wheel: an edge SelectByID2 answered False and the
# vendored geometric fallback selected the edge itself (173 more requests,
# reads and selections), the base's mass properties and STL.
_DETOURED = {
    "request_divergence": {"index": 7285, "field": "member"},
    "truth_cause": "response:IModelDocExtension.SelectByID2",
    "outcome": "different",
    "outcome_signals": {
        "mass": "same",
        "requests": "different",
        "answers": "different",
        "stl": "same",
    },
    "seat_path": {
        "path": "detour",
        "count": 1,
        "blocks": [
            {
                "base": [7285, 7285],
                "new": [7285, 7458],
                "steered_by": "IModelDocExtension.SelectByID2",
            }
        ],
    },
}
# A detour that put a property or kept its selection, or another solid: an
# alarm, whatever else held.
_DETOURED_PUT = {
    **_DETOURED,
    "seat_path": {"path": "not_read", "detail": "IFeature.Name (put) in the block"},
}
_DETOURED_SELECTING = {
    **_DETOURED,
    "seat_path": {
        "path": "selection_kept",
        "detail": "new called IFeatureManager.FeatureFillet3 before "
        "IModelDoc2.ClearSelection2 after the block at base 7285 new 7285",
    },
}
_DETOURED_RESHAPED = {
    **_DETOURED,
    "outcome_signals": {**_DETOURED["outcome_signals"], "stl": "different"},
}


def _verdict(name: str) -> dict[str, Any]:
    return {"verdict": name, "recorded": 10, "served": 4}


@pytest.mark.parametrize(
    ("replay_rc", "replay", "diff", "verdict", "truth", "kind", "flags"),
    [
        (0, _NOOP, _SAME, "noop", "same", "noop", ""),
        (0, _NOOP, _DIFFERENT, "noop", "diverged", "noop", "alarm"),
        (0, _NOOP, _RESHAPED, "noop", "same", "noop", "alarm"),
        (0, _NOOP, _REORDERED, "noop", "diverged", "noop", "seat"),
        (0, _NOOP, _UNMEASURED, "noop", "same", "noop", "unknown"),
        (0, _NOOP, _UNEXPLAINED, "noop", "diverged", "noop", "unexplained"),
        (0, _NOOP, _UNJUDGED, "noop", "diverged", "noop", "unknown judge"),
        (0, _NOOP, _FAULTED, "noop", "diverged", "noop", "unknown judge"),
        (0, _NOOP, _DETOURED, "noop", "diverged", "noop", "path"),
        (0, _NOOP, _DETOURED_PUT, "noop", "diverged", "noop", "alarm"),
        (0, _NOOP, _DETOURED_SELECTING, "noop", "diverged", "noop", "alarm"),
        (0, _NOOP, _DETOURED_RESHAPED, "noop", "diverged", "noop", "alarm"),
        # The judge's conditions, checked again: a request cause, or another
        # mass, is no detour SolidWorks steered.
        (
            0,
            _NOOP,
            {**_DETOURED, "truth_cause": "request"},
            "noop",
            "diverged",
            "noop",
            "alarm",
        ),
        (
            0,
            _NOOP,
            {
                **_DETOURED,
                "outcome_signals": {
                    **_DETOURED["outcome_signals"],
                    "mass": "different",
                },
            },
            "noop",
            "diverged",
            "noop",
            "alarm",
        ),
        # No comparison at all: a noop nothing confirms.
        (0, _NOOP, None, "noop", "unknown", "noop", "unknown"),
        (91, _DIVERGED, _UNEXPLAINED, "diverged", "diverged", "divergence", ""),
        (91, _DIVERGED, _DIFFERENT, "diverged", "diverged", "divergence", ""),
        (91, _DIVERGED, _REORDERED, "diverged", "diverged", "divergence", ""),
        (91, _DIVERGED, _FAULTED, "diverged", "diverged", "divergence", "judge"),
        (91, _DIVERGED, _DETOURED, "diverged", "diverged", "divergence", ""),
        (91, _DIVERGED, _SAME, "diverged", "same", "divergence", "false"),
        (91, _verdict("exhausted"), _SAME, "exhausted", "same", "divergence", "false"),
        (
            91,
            _verdict("unconsumed"),
            _SAME,
            "unconsumed",
            "same",
            "divergence",
            "false",
        ),
        # A refusal or a failure of the machinery is no judgement: never a
        # false divergence, whatever the ground truth.
        (
            91,
            _verdict("input_mismatch"),
            _SAME,
            "input_mismatch",
            "same",
            "refusal",
            "",
        ),
        (91, _verdict("sandbox"), _SAME, "sandbox", "same", "refusal", ""),
        (91, _verdict("error"), _SAME, "error", "same", "infrastructure", ""),
        (None, None, _SAME, "timeout", "same", "infrastructure", ""),
        (3, None, None, "error", "unknown", "infrastructure", ""),
    ],
)
def test_a_shadow_folds_replay_ground_truth_and_outcome(
    replay_rc, replay, diff, verdict, truth, kind, flags
):
    result = shadow.shadow_of(replay_rc, replay, 0 if diff else None, diff)
    assert (result.verdict, result.ground_truth) == (verdict, truth)
    assert result.verdict_class is shadow.VerdictClass(kind)
    assert result.outcome == (diff or {}).get("outcome", "unknown")
    assert result.truth_cause == (diff or {}).get("truth_cause")
    flags_of = {
        "alarm": result.soundness_alarm,
        "seat": result.seat_nondeterminism,
        "path": result.seat_path_divergence,
        "unexplained": result.noop_unexplained_divergence,
        "unknown": result.noop_outcome_unknown,
        "false": result.false_divergence,
        "judge": result.judge_fault,
    }
    assert flags_of == {name: name in flags.split() for name in flags_of}


_NOOP_MARKERS = {
    shadow.NoopJudgement.SOUNDNESS_ALARM: "soundness_alarm",
    shadow.NoopJudgement.SEAT_NONDETERMINISM: "seat_nondeterminism",
    shadow.NoopJudgement.SEAT_PATH_DIVERGENCE: "seat_path_divergence",
    shadow.NoopJudgement.UNEXPLAINED_DIVERGENCE: "noop_unexplained_divergence",
    shadow.NoopJudgement.OUTCOME_UNKNOWN: "noop_outcome_unknown",
}


def test_every_noop_is_judged_exactly_once():
    # Every verdict x ground truth x cause x outcome x geometry x seat path: a
    # noop has exactly one judgement, each but CONFIRMED with exactly its own
    # marker; any other verdict has none.
    judged = set()
    for verdict, truth, cause, outcome, geometry, path in itertools.product(
        [*shadow.VERDICT_CLASSES, "garbled"],
        ("same", "diverged", "unknown"),
        (None, "request", "response:IFace2.Normal", "error:RuntimeError"),
        ("same", "different", "unknown"),
        ("same", "different"),
        (None, {"path": "detour"}, {"path": "not_read"}),
    ):
        found = shadow.Shadow(
            verdict,
            ground_truth=truth,
            truth_cause=cause,
            outcome=outcome,
            outcome_signals={"mass": "same", "stl": geometry},
            seat_path=path,
        )
        markers = {name for name in _NOOP_MARKERS.values() if getattr(found, name)}
        judgement = found.noop_judgement
        if verdict != "noop":
            assert judgement is None and markers == set()
            continue
        judged.add(judgement)
        expected = {_NOOP_MARKERS[judgement]} if judgement in _NOOP_MARKERS else set()
        assert markers == expected, (truth, cause, outcome, geometry, path)
    assert judged == set(shadow.NoopJudgement)
    judgement = shadow.Shadow(
        "noop", ground_truth="diverged", truth_cause="request", outcome="same"
    ).noop_judgement
    assert judgement is shadow.NoopJudgement.UNEXPLAINED_DIVERGENCE
    # A fault judging the cause establishes nothing about earlier answers.
    judgement = shadow.Shadow(
        "noop",
        ground_truth="diverged",
        truth_cause="error:RuntimeError",
        outcome="same",
    ).noop_judgement
    assert judgement is shadow.NoopJudgement.OUTCOME_UNKNOWN


def test_a_seat_path_detour_is_the_judges_own_verdict():
    assert shadow.SEAT_PATH_DETOUR == _com_outcome.SeatPath.DETOUR.value
    found = shadow.shadow_of(0, _NOOP, 91, _DETOURED)
    assert found.noop_judgement is shadow.NoopJudgement.SEAT_PATH_DIVERGENCE
    assert found.seat_path == _DETOURED["seat_path"] and not found.soundness_alarm


def test_a_title_counter_echo_is_seat_nondeterminism():
    # 2026-11-12, ms_stick: a dimension's full name, which carries the seat's
    # document counter, written into an equation.
    found = shadow.Shadow(
        "noop",
        ground_truth="diverged",
        truth_cause=_com_outcome.TITLE_COUNTER_CAUSE,
        outcome="same",
    )
    assert found.noop_judgement is shadow.NoopJudgement.SEAT_NONDETERMINISM
    assert found.seat_nondeterminism and not found.noop_unexplained_divergence


def test_every_verdict_has_a_class():
    assert {v.value for v in conv.Verdict} | {"timeout", "unavailable"} == set(
        shadow.VERDICT_CLASSES
    )
    assert shadow.Shadow("garbled").verdict_class is shadow.VerdictClass.INFRASTRUCTURE


def _two_builds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> shadow.Recording:
    """A published base recording, then a shadow build one input away."""
    monkeypatch.setenv(shadow.MODE_ENV, "record")
    base, deps = _built(tmp_path, "size: 1\n")
    shadow.after_build(base, deps, _digest)
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    current, deps = _built(tmp_path, "size: 2\n")
    shadow.after_build(current, deps, _digest)
    return base


def test_a_soundness_alarm_is_an_error_and_never_fails_the_build(
    blob, tmp_path, monkeypatch, spans, logged
):
    divergence = {"index": 7, "field": "args", "context": ["x" * 10_000]}

    def evaluate(recording, base, summary):
        return shadow.Shadow(
            "noop",
            recorded=10,
            served=10,
            substitutions=0,
            ground_truth="diverged",
            request_divergence=divergence,
            truth_cause="request",
            outcome="different",
            outcome_signals={"mass": "different", "stl": "same"},
            outcome_details={"answers": {"x" * 10_000: [1, 1]}},
        )

    monkeypatch.setattr(shadow, "evaluate", evaluate)
    base = _two_builds(tmp_path, monkeypatch)
    [message] = logged["error"]
    assert "SOUNDNESS ALARM" in message and base.key[:12] in message
    record = _events(tmp_path, "replay_shadow")[-1]
    assert (record["outcome"], record["verdict"], record["soundness_alarm"]) == (
        "evaluated",
        "noop",
        True,
    )
    assert record["noop_judgement"] == "soundness_alarm"
    assert record["base_key"] == base.key and record["differing_count"] == 1
    assert record["differing_classes"] == {"other": 1}
    # Oversized details and context are clipped; the short fields survive.
    evidence = record["alarm_evidence"]
    assert len(evidence) == shadow.EVIDENCE_CHARS and evidence in message
    for field in (
        '"served": 10',
        '"truth_cause": "request"',
        '"outcome_signals": {"mass": "different", "stl": "same"}',
        '"request_divergence": {"index": 7, "field": "args"',
        '"outcome_details": "{\\"answers\\": {\\"xxx',
    ):
        assert field in evidence, field
    assert "context" not in evidence
    [span] = spans.named("replay.shadow ")
    assert span["replay.verdict"] == "noop" and span["replay.soundness_alarm"] is True
    assert span["replay.artefact_outcome"] == record["artefact_outcome"] == "different"
    assert span["replay.outcome_signals"] == "mass:different,stl:same"
    assert span["replay.base_key"] == base.key[:12]
    assert span["replay.verdict_class"] == record["verdict_class"] == "noop"
    # One INFO line per recorded build; the evaluated one carries every step.
    assert len(logged["info"]) == 2
    line = logged["info"][-1]
    assert "\n" not in line
    assert line.startswith(
        f"[com-replay] part:{_STEM}: evaluated | publish=stored bytes="
        f"{record['bundle_bytes']} | lookup=found base={base.key[:12]} differing=1 "
        "listed=2 read=2 "
    )
    assert "| shadow=noop served=10/10 " in line
    assert line.endswith(
        "| truth=diverged | outcome=different cause=request | SOUNDNESS ALARM"
    )
    assert span["service"] == _telemetry.BUILD_INFRA_SERVICE
    assert [entry["name"].split()[0] for entry in spans.named("replay.")] == [
        "replay.after_build",
        "replay.record_overhead",
        "replay.publish",
        "replay.after_build",
        "replay.record_overhead",
        "replay.publish",
        "replay.base_lookup",
        "replay.shadow",
    ]


@pytest.mark.parametrize(
    ("found", "marker", "line_end"),
    [
        (
            {
                "ground_truth": "diverged",
                "truth_cause": "response:IFace2.Normal",
                "outcome": "same",
            },
            "seat_nondeterminism",
            "| truth=diverged | outcome=same cause=response:IFace2.Normal "
            "| seat_nondeterminism",
        ),
        (
            {"ground_truth": "diverged", "truth_cause": "request", "outcome": "same"},
            "noop_unexplained_divergence",
            "| truth=diverged | outcome=same cause=request "
            "| noop_unexplained_divergence",
        ),
        (
            # No STL captured: the signal is absent, and no judge fault.
            {
                "ground_truth": "same",
                "outcome": "unknown",
                "outcome_signals": {"mass": "same", "stl": "absent"},
            },
            "noop_outcome_unknown",
            "| truth=same | outcome=unknown cause=- | noop_outcome_unknown",
        ),
        (
            {
                "ground_truth": "diverged",
                "truth_cause": _DETOURED["truth_cause"],
                "outcome": "different",
                "outcome_signals": _DETOURED["outcome_signals"],
                "seat_path": _DETOURED["seat_path"],
            },
            "seat_path_divergence",
            "| outcome=different cause=response:IModelDocExtension.SelectByID2 "
            "| seat_path_divergence",
        ),
    ],
)
def test_a_noop_the_outcome_does_not_contradict_is_counted_never_an_alarm(
    blob, tmp_path, monkeypatch, spans, logged, found, marker, line_end
):
    def evaluate(recording, base, summary):
        return shadow.Shadow("noop", recorded=10, served=10, **found)

    monkeypatch.setattr(shadow, "evaluate", evaluate)
    base = _two_builds(tmp_path, monkeypatch)
    assert logged["error"] == []
    # Only an unexplained divergence warns: it contradicts the premise that a
    # noop's live divergence can only come from SolidWorks.
    warned = [m for m in logged["warn"] if "noop_unexplained_divergence" in m]
    assert len(warned) == (marker == "noop_unexplained_divergence")
    assert all(base.key[:12] in m and '"truth_cause": "request"' in m for m in warned)
    record = _events(tmp_path, "replay_shadow")[-1]
    flags = tuple(_NOOP_MARKERS.values())
    assert {name: record[name] for name in flags} == {
        name: name == marker for name in flags
    }
    assert record["noop_judgement"] == marker
    [span] = spans.named("replay.shadow ")
    assert span[f"replay.{marker}"] is True and span["replay.soundness_alarm"] is False
    assert span["replay.noop_judgement"] == marker
    assert logged["info"][-1].endswith(line_end)
    assert record["judge_fault"] is False and span["replay.judge_fault"] is False
    # Never revoked: only an alarm revokes the base.
    assert "revoked" not in record and "alarm_evidence" not in record
    assert record["seat_path"] == (found.get("seat_path") or {}).get("path")
    assert "replay.judge_faults" not in span
    assert not [m for m in logged["warn"] if m.startswith("[com-replay] judge_fault ")]


@pytest.mark.parametrize(
    ("verdict", "found", "steps", "line_end"),
    [
        (
            "diverged",
            {
                "ground_truth": "diverged",
                "truth_cause": "request",
                "outcome": "unknown",
                "outcome_signals": {"mass": "same", "stl": "absent"},
                "outcome_details": {"stl": {"error": "KeyError: 'file'"}},
                "judge_faults": [{"step": "stl", "error": "KeyError: 'file'"}],
            },
            "stl",
            "| truth=diverged | outcome=unknown cause=request | judge_fault",
        ),
        (
            "noop",
            {
                "ground_truth": "diverged",
                "truth_cause": "error:RuntimeError",
                "outcome": "same",
                "judge_faults": [
                    {"step": "truth_cause", "error": "RuntimeError: injected"}
                ],
            },
            "truth_cause",
            "| truth=diverged | outcome=same cause=error:RuntimeError "
            "| noop_outcome_unknown | judge_fault",
        ),
    ],
)
def test_a_judge_fault_is_counted_and_warned_whatever_the_verdict(
    blob, tmp_path, monkeypatch, spans, logged, verdict, found, steps, line_end
):
    def evaluate(recording, base, summary):
        return shadow.Shadow(verdict, recorded=10, served=10, **found)

    monkeypatch.setattr(shadow, "evaluate", evaluate)
    base = _two_builds(tmp_path, monkeypatch)
    assert logged["error"] == []
    [warned] = [m for m in logged["warn"] if m.startswith("[com-replay] judge_fault ")]
    fault = found["judge_faults"][0]
    assert base.key[:12] in warned
    assert f'"judge_faults": [{{"step": "{steps}", "error": ' in warned
    assert json.dumps(fault["error"]) in warned
    record = _events(tmp_path, "replay_shadow")[-1]
    assert (record["judge_fault"], record["judge_faults"]) == (True, steps)
    [span] = spans.named("replay.shadow ")
    assert (span["replay.judge_fault"], span["replay.judge_faults"]) == (True, steps)
    assert span["replay.soundness_alarm"] is False
    assert logged["info"][-1].endswith(line_end)


def test_a_failed_evaluation_is_a_verdict_not_a_failure(
    blob, tmp_path, monkeypatch, logged
):
    def evaluate(recording, base, summary):
        raise RuntimeError("the replay could not start")

    monkeypatch.setattr(shadow, "evaluate", evaluate)
    _two_builds(tmp_path, monkeypatch)
    record = _events(tmp_path, "replay_shadow")[-1]
    assert (record["outcome"], record["verdict"]) == ("evaluated", "error")
    assert "could not start" in record["reason"] and logged["error"] == []


def test_a_failed_shadow_step_is_one_record_and_one_line(
    blob, tmp_path, monkeypatch, logged
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    recording, deps = _built(tmp_path, "size: 1\n")

    def bundle(_recording):
        raise OSError("injected:\nthe recording vanished")

    monkeypatch.setattr(shadow, "bundle", bundle)
    shadow.after_build(recording, deps, _digest)  # does not raise
    [record] = _events(tmp_path, "replay_shadow")
    assert record["outcome"] == "error" and "vanished" in record["error"]
    assert blob.committed == {}
    [line] = logged["info"]
    assert line.startswith(
        f"[com-replay] part:{_STEM}: error (OSError('injected:\\nthe recording "
        "vanished')) | publish=- bytes=-"
    )
    assert "\n" not in line


# --------------------------------------------------------------------------- #
# End to end: driver recordings, publication, lookup, sandboxed replay, diff
# --------------------------------------------------------------------------- #
_E2E_SCRIPT = (
    "import sys\n"
    "from _session import run_build\n"
    "from test_com_conversation import scenario\n"
    "async def build(adapter):\n"
    "    await scenario(adapter)\n"
    "    return {}\n"
    "if __name__ == '__main__':\n"
    "    sys.exit(run_build(build))\n"
)


def _outputs(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_a_shadow_replay_end_to_end(blob, tmp_path, monkeypatch, spans):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    source = tmp_path / "src"
    source.mkdir()
    script = source / f"build_{_STEM}.py"
    script.write_text(_E2E_SCRIPT, encoding="utf-8")
    config = source / "widget.yaml"
    deps = [str(script), str(config)]

    def build(text: str, fault: str = "") -> shadow.Recording:
        config.write_text(text, encoding="utf-8")
        recording = shadow.plan(_STEM, script, cache.key_inputs(deps, _digest)[0])
        assert recording is not None
        # The driver with a fake application for the seat (test_com_conversation).
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                _RECORD_DRIVER,
                *recording.command[2:],
                "--out-root",
                str(shadow.OUT_ROOT),
            ],
            cwd=SCRIPTS,
            env=dict(
                os.environ, OTEL_EXPORTER_OTLP_ENDPOINT="", COM_REPLAY_TEST_FAULT=fault
            ),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        # What dodo._exec_com does with the driver's exit: never a re-run here.
        assert not recording.exited(proc.returncode)
        built = _outputs(shadow.OUT_ROOT)
        _stored(recording.key)
        shadow.after_build(recording, deps, _digest)
        # Observation reads the outputs; it never writes one (and its scratch
        # under the output root is gone).
        assert _outputs(shadow.OUT_ROOT) == built
        return recording

    first = build("size: 1\n")
    second = build("size: 2\n")
    summary = json.loads(second.summary_path.read_text("utf-8"))
    assert summary["exit_code"] == 0 and summary["complete"] and summary["faults"] == []
    assert summary["recipe_requests"] == summary["calls"] - summary["inert_calls"] > 20
    assert summary["engine"] == conv.sha256_file(conv.ENGINE_FILE)
    assert summary["sw_revision"] == "34.3.0"
    assert set(summary["environment"]) == set(conv.ENVIRONMENT_KEYS)
    trailer = conv.load(second.log).trailer
    assert trailer["status"] == "complete" and trailer["faults"] == []
    first_record, second_record = _events(tmp_path, "replay_shadow")
    assert (first_record["outcome"], first_record["lookup"]) == ("no_base", "none")
    assert second_record["outcome"] == "evaluated", second_record
    assert (second_record["verdict"], second_record["ground_truth"]) == (
        "noop",
        "same",
    ), second_record
    assert second_record["base_key"] == first.key
    assert second_record["recorded"] == second_record["served"] > 20
    assert (
        not second_record["soundness_alarm"] and not second_record["false_divergence"]
    )
    # The fake build measures nothing and exports no STL: a noop the outcome
    # can neither confirm nor contradict.
    assert (second_record["artefact_outcome"], second_record["truth_cause"]) == (
        "unknown",
        None,
    )
    assert second_record["noop_outcome_unknown"]
    assert not second_record["seat_nondeterminism"]
    assert second_record["differing"] == [cache._rel(config)]
    # The replay's scratch is gone; its logs and the local verdict remain.
    assert list(shadow.SCRATCH.iterdir()) == []
    assert (second.directory / shadow.REPLAY_LOG_NAME).is_file()
    assert (
        json.loads((second.directory / shadow.SHADOW_NAME).read_text("utf-8"))[
            "verdict"
        ]
        == "noop"
    )
    [span] = spans.named("replay.shadow ")
    assert span["replay.verdict"] == "noop" and span["replay.ground_truth"] == "same"
    assert span["replay.verdict_class"] == second_record["verdict_class"] == "noop"
    # A recorder fault once the build had its result (keeping SaveTo's file,
    # as on the farm on 2026-11-10): the build exits 0 and nothing of its
    # recording is published or evaluated.
    published = dict(blob.committed)
    third = build("size: 3\n", fault="capture")
    assert third.recovery == shadow.Recovery.DEGRADED
    assert blob.committed == published
    third_record = _events(tmp_path, "replay_shadow")[-1]
    assert (third_record["outcome"], third_record["where"]) == (
        "record_fault",
        "Recorder.capture",
    )


# --------------------------------------------------------------------------- #
# The str hash seed: dodo._exec_com pins it for every COM subprocess
# --------------------------------------------------------------------------- #
# A build ordering its COM requests by iterating a set of str, as
# _drawing_precision._named_dimensions did before #2514.
_SET_ORDER_SCRIPT = (
    "import sys\n"
    "from _session import run_build\n"
    "import test_com_conversation  # noqa: F401 -- the fake seat's interfaces\n"
    "PARTS = {'plate', 'arm', 'hub', 'pin', 'rib', 'web', 'boss', 'slot'}\n"
    "async def build(adapter):\n"
    "    for name in PARTS:\n"
    "        adapter.swApp.GetPart(name).Volume\n"
    "    return {}\n"
    "if __name__ == '__main__':\n"
    "    sys.exit(run_build(build))\n"
)
_ON_PATH = f"import os, sys\nsys.path.insert(0, {str(SCRIPTS)!r})\n"
# A process as before the pin: a hash key of its own (the seed it started
# with, fixed here so the control is deterministic) and no PYTHONHASHSEED in
# its environment, so its recording names none.
_UNPINNED = _ON_PATH + "os.environ.pop('PYTHONHASHSEED')\n"
_REPLAY_DRIVER = "import com_replay\nsys.exit(com_replay.main(sys.argv[1:]))\n"


def test_com_subprocesses_issue_set_ordered_requests_in_one_order(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    # Inherited from dodo's own environment: the pin still wins.
    monkeypatch.setenv("PYTHONHASHSEED", "7")
    dodo = _load_dodo()
    launched: list[dict[str, str]] = []

    def run(command: list[str], **options: Any) -> subprocess.CompletedProcess:
        # dodo's command, working directory and environment, on the fake seat.
        launched.append(options["env"])
        return subprocess.run(command, **options)

    runner = types.SimpleNamespace(**{**vars(subprocess), "run": run})
    monkeypatch.setattr(dodo, "subprocess", runner)
    script = tmp_path / "build_fake_sets.py"
    script.write_text(_SET_ORDER_SCRIPT, encoding="utf-8")

    def run_dir(name: str) -> Path:
        (tmp_path / name).mkdir()
        return tmp_path / name

    def log(name: str) -> Path:
        return tmp_path / name / "L.jsonl.gz"

    def summary(name: str) -> dict[str, Any]:
        return json.loads((tmp_path / name / "summary.json").read_text("utf-8"))

    def record(name: str) -> list[str]:
        run = run_dir(name)
        return [
            "record",
            str(script),
            "--log",
            str(log(name)),
            "--summary",
            str(run / "summary.json"),
            "--out-root",
            str(run / "out"),
        ]

    def spawn(command: list[str], env: dict[str, str]) -> subprocess.Popen[str]:
        return subprocess.Popen(
            [sys.executable, "-c", *command],
            cwd=SCRIPTS,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    # Control: two fresh unpinned processes, as part builds ran until now.
    unpinned = [
        spawn(
            [_UNPINNED + _RECORD_DRIVER, *record(f"unpinned-{seed}")],
            dict(os.environ, PYTHONHASHSEED=seed),
        )
        for seed in ("1", "2")
    ]
    # Two fresh processes through the COM chokepoint.
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        recorded = [
            pool.submit(
                dodo._exec_com,
                [sys.executable, "-c", _ON_PATH + _RECORD_DRIVER, *record(name)],
                f"verify:{name}",
            )
            for name in ("pinned-1", "pinned-2")
        ]
    for future in recorded:
        future.result()  # _exec_com raises on a failed build
    assert [env["PYTHONHASHSEED"] for env in launched] == ["0", "0"]
    for proc in unpinned:
        output, _ = proc.communicate(timeout=120)
        assert proc.returncode == 0, output
    assert [
        summary(name)["environment"]["PYTHONHASHSEED"]
        for name in ("pinned-1", "pinned-2", "unpinned-1", "unpinned-2")
    ] == ["0", "0", None, None]
    pinned = conv.compare_conversations(log("pinned-1"), log("pinned-2"))
    calls = pinned["recipe_calls"][0]
    assert pinned["recipe_calls"] == [calls, calls] and calls >= 16
    assert pinned["request_divergence"] is None
    control = conv.compare_conversations(log("unpinned-1"), log("unpinned-2"))
    assert control["request_divergence"] is not None

    def replay(name: str, base: str, seat: str, seed: str | None = None):
        run = run_dir(name)
        (run / "tmp").mkdir()
        # What _replay_shadow.evaluate gives a replay: the environment of
        # the fresh recording (here the seat's).
        env = shadow._child_env(summary(seat), run / "tmp")
        driver = _ON_PATH
        if seed is not None:
            env["PYTHONHASHSEED"], driver = seed, _UNPINNED
        logs = ["--log", str(log(base)), "--seat-log", str(log(seat))]
        outputs = ["--scratch", str(run / "scratch"), "--result", str(run / "r.json")]
        return spawn(
            [driver + _REPLAY_DRIVER, "replay", str(script), *logs, *outputs], env
        )

    replays = {
        "pinned": replay("pinned", "pinned-1", "pinned-2"),
        "unpinned": replay("unpinned", "unpinned-1", "unpinned-2", seed="2"),
        "unpinned base": replay("unpinned base", "unpinned-1", "pinned-2"),
        "unpinned replay": replay("unpinned replay", "pinned-1", "unpinned-2", "2"),
    }
    results = {}
    for name, proc in replays.items():
        output, _ = proc.communicate(timeout=120)
        result = tmp_path / name / "r.json"
        assert result.is_file(), output
        results[name] = json.loads(result.read_text("utf-8"))
    assert results["pinned"]["verdict"] == "noop", results["pinned"]
    assert results["pinned"]["served"] == results["pinned"]["recorded"] == calls
    assert results["unpinned"]["verdict"] == "diverged", results["unpinned"]
    # One recording pinned and the other not: a refusal, never a divergence.
    for name in ("unpinned base", "unpinned replay"):
        verdict = results[name]["verdict"]
        assert shadow.VERDICT_CLASSES[verdict] is shadow.VerdictClass.REFUSAL
        assert verdict == "input_mismatch", results[name]
        assert [m["input"] for m in results[name]["input_mismatches"]] == [
            "env:PYTHONHASHSEED"
        ]


# --------------------------------------------------------------------------- #
# Isolation: the recording is no part of any task's inputs or outputs
# --------------------------------------------------------------------------- #
def test_recordings_are_no_task_input_or_output(monkeypatch):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    dodo = _load_dodo()
    modules = {
        "_com_conversation.py",
        "_com_outcome.py",
        "com_replay.py",
        "_replay_shadow.py",
    }
    owned = (shadow.RECORDINGS.resolve(), shadow.SCRATCH.resolve())
    # One real part task (every part task is built by the same _part_task; the
    # closure test covers every recipe's module closure).
    stem = _buildgraph.part_scripts()[0].stem.removeprefix("build_")
    task = dodo._part_task(stem)
    paths = [*task["file_dep"], *task["targets"]]
    assert paths
    assert not [
        path
        for path in paths
        if Path(path).name in modules
        or any(Path(path).resolve().is_relative_to(root) for root in owned)
    ]


# --------------------------------------------------------------------------- #
# Windows path budget: no long-path support on the workers (or in SolidWorks)
# --------------------------------------------------------------------------- #
# A farm leaf's checkout: C:\harmonic\work\sources\<commit 12 hex>-<16 hex>\
# workspace (solidworks-pool workers, 2026-11-10).
_FARM_REPO = (
    PureWindowsPath("C:/harmonic/work/sources") / f"{'f' * 12}-{'f' * 16}" / "workspace"
)
# Characters every path must keep in hand on the farm, for names this model
# does not know (a temporary file SolidWorks or pywin32 derives from an
# output, a longer member suffix). The tightest today: 41, a member PNG's
# SaveBMP intermediate replayed under rs/<8>/o (2026-11-10).
_FARM_HEADROOM = 32


def _part_outputs(dodo: Any, stem: str) -> list[str]:
    """Every file a part build writes under the output root, relative to it:
    its cache outputs, member exports, each routine view in its PNG directory,
    and SaveBMP's intermediate beside every PNG (the adapter's
    ``<png>.capture.bmp``, captured by the recorder)."""
    from _part_save import _ROUTINE_PART_VIEWS

    out = Path(dodo.CAD_OUT)
    png_dir = Path(dodo._png_dir(stem))
    files: set[Path] = set()
    for path in map(
        Path, [*dodo._part_cache_outputs(stem), *dodo._part_configuration_outputs(stem)]
    ):
        if path == png_dir:
            files.update(
                png_dir / f"{png_dir.name}_{v}.png" for v in _ROUTINE_PART_VIEWS
            )
            continue
        files.add(path)
    files.update(
        path.with_name(path.name + ".capture.bmp")
        for path in list(files)
        if path.suffix == ".png"
    )
    return sorted(path.relative_to(out).as_posix() for path in files)


def test_every_part_recording_fits_the_windows_path_limit(monkeypatch):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    dodo = _load_dodo()
    checkout = PureWindowsPath(shadow.REPO_ROOT)
    repo = max(_FARM_REPO, checkout, key=lambda root: len(str(root)))

    def under(path: Path) -> PureWindowsPath:
        return repo / PureWindowsPath(path.relative_to(shadow.REPO_ROOT))

    tightest: list[tuple[int, str, str]] = []
    stems = [s.stem.removeprefix("build_") for s in _buildgraph.part_scripts()]
    assert len(stems) > 100
    for stem in stems:
        outputs = _part_outputs(dodo, stem)
        needs = shadow.path_needs(
            stem, under(shadow.RECORDINGS), under(shadow.SCRATCH), outputs
        )
        # The recording's own files, the work directory and the base bundle,
        # and every output's replay copy are all budgeted.
        purposes = {need.purpose for need in needs}
        assert {
            shadow.LOG_NAME,
            shadow.SUMMARY_NAME,
            shadow.REPLAY_LOG_NAME,
            "capture",
            "work tmp",
            "base capture",
        } <= purposes
        assert {f"replay output {output}" for output in outputs} <= purposes
        need = min(needs, key=lambda n: n.headroom)
        tightest.append((need.headroom, stem, need.path))
    headroom, stem, path = min(tightest)
    assert headroom >= _FARM_HEADROOM, (stem, len(path), path)


def test_a_replayed_output_path_is_the_builds_own_plus_14_characters():
    out = PureWindowsPath("C:/w/cad/out")
    output = "sldprt/sh_widget.SLDPRT"
    assert shadow.SCRATCH == shadow.OUT_ROOT / "rs"
    needs = shadow.path_needs(_STEM, out / "replay", out / "rs", [output])
    [need] = [n for n in needs if n.purpose == f"replay output {output}"]
    assert len(need.path) - len(str(out / output)) == 14  # \rs\<8>\o


def test_a_checkout_too_deep_for_the_recording_builds_unrecorded(
    blob, tmp_path, monkeypatch, logged
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    monkeypatch.setattr(shadow, "RECORDINGS", tmp_path / ("d" * 240))
    assert shadow.plan(_STEM, tmp_path / f"build_{_STEM}.py", "k" * 64) is None
    [warning] = logged["warn"]
    assert "past the Windows limit; building unrecorded" in warning
    assert not (tmp_path / ("d" * 240)).exists()


# --------------------------------------------------------------------------- #
# Reuse: before the seat, a bound base's archive as this key's outputs
# --------------------------------------------------------------------------- #
_LABEL = f"part:{_STEM}"
_SEAT_BUILD = "34.3.0.17"
# What dodo._com_process_inputs gives a part build with no read guards.
_PINS: dict[str, str | None] = {
    "PYTHONHASHSEED": "0",
    "HARMONIC_FASTENER_ROWS": None,
    "HARMONIC_FIT_GROUPS": None,
}
_NATIVE = b"the base's native part"
_PY = b'{"written": "by Python"}\n'


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _drop(service: _ListingService, name: str) -> None:
    for blobs in (service.committed, service.metadata, service.etags):
        blobs.pop(name, None)


class _Shop:
    """A checkout under ``tmp_path`` for ``blob``'s cache, which is rooted at
    its output root: the end-to-end part script (which a replay executes) and
    a config it does not read (``script`` may), built on the fake seat; the
    replay driver resolves the inputs a replay executed or read against this
    checkout."""

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        digest: Any = _digest,
        script: str = _E2E_SCRIPT,
    ) -> None:
        self.digest = digest
        self.root = tmp_path.resolve()
        source = self.root / "src"
        source.mkdir()
        self.script = source / f"build_{_STEM}.py"
        self.config = source / "widget.yaml"
        self.script.write_text(script, "utf-8")
        self.config.write_text("size: 1\n", "utf-8")
        self.deps = [str(self.script), str(self.config)]
        self.out = self.root / "out"
        self.native = self.out / "sldprt" / "fake.SLDPRT"
        self.python_output = self.out / "py-output.json"
        self.outputs = [self.native, self.python_output]
        self.token = self.root / "token"
        driver = self.root / "replay_driver.py"
        driver.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "from pathlib import Path\n"
            "import com_replay\n"
            f"com_replay.REPO_ROOT = Path({str(self.root)!r})\n"
            "sys.exit(com_replay.main(sys.argv[1:]))\n",
            "utf-8",
        )
        for module, name, value in (
            (shadow, "OUT_ROOT", self.out),
            (shadow, "SCRATCH", self.out / "rs"),
            (shadow, "RECORDINGS", self.root / "replay"),
            (shadow, "DRIVER", driver),
            (shadow, "seat_build", lambda: _SEAT_BUILD),
            (cache, "REPO_ROOT", self.root),
            (cache, "_CACHE_OUTPUT_ROOT", self.out),
            (cache, "_PUBLISHED", {}),
        ):
            monkeypatch.setattr(module, name, value)
        monkeypatch.setenv(shadow.MODE_ENV, "reuse")
        # The driver commands run, by command ("replay", "diff").
        self.ran: list[str] = []
        run = shadow._run

        def counted(command, env, deadline, log):
            self.ran.append(command[2])
            return run(command, env, deadline, log)

        monkeypatch.setattr(shadow, "_run", counted)

    def key(self) -> str:
        return cache.cache_key(self.deps, self.digest, _LABEL)

    def edit(self, *, audited: bool, path: Path | None = None) -> str:
        """An inert edit (one more comment in the script, or in ``path``) to
        a key the audit does, or does not, sample."""
        path = path or self.script
        text = path.read_text("utf-8")
        for n in itertools.count():
            path.write_text(f"{text}# edit {n}\n", "utf-8")
            if shadow.audited(cache.key_inputs(self.deps, self.digest)[0]) is audited:
                return self.key()
        raise AssertionError("unreachable")

    def write(self, native: bytes = _NATIVE, python: bytes = _PY) -> None:
        self.native.parent.mkdir(parents=True, exist_ok=True)
        self.native.write_bytes(native)
        self.python_output.write_bytes(python)

    def clear(self) -> None:
        """A fresh worker: no output on disk."""
        shutil.rmtree(self.out, ignore_errors=True)

    def outputs_now(self) -> dict[str, bytes]:
        return {path.name: path.read_bytes() for path in self.outputs}

    def build(self, reuse: shadow.Reuse | None = None) -> shadow.Recording:
        """The current source built on the fake seat as dodo's part action
        builds a miss: under the recorder, stored, then observed."""
        key = self.key()
        recording = shadow.plan(_STEM, self.script, key, reuse=reuse)
        assert recording is not None
        env = {k: v for k, v in os.environ.items() if k not in _PINS}
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                _RECORD_DRIVER,
                *recording.command[2:],
                "--out-root",
                str(self.out),
            ],
            cwd=SCRIPTS,
            env={**env, "OTEL_EXPORTER_OTLP_ENDPOINT": "", "PYTHONHASHSEED": "0"},
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert cache.store(key, self.outputs, _LABEL) == "stored"
        shadow.after_build(recording, self.deps, self.digest)
        return recording

    def base(self, *, store: bool = True, native: bytes = _NATIVE) -> str:
        """A base as a recorded build leaves one, without running it: its
        outputs stored under its key, its recording published and bound to
        that archive (``store`` False: unbound). Its replay is _replay_as's."""
        key = self.key()
        self.write(native)
        if store:
            assert cache.store(key, self.outputs, _LABEL) == "stored"
        os.environ[shadow.MODE_ENV] = "record"
        recording = shadow.plan(_STEM, self.script, key)
        assert recording is not None
        recording.log.write_bytes(b"log of " + key.encode())
        recording.summary_path.write_text(json.dumps(_summary()), "utf-8")
        shadow.after_build(recording, self.deps, self.digest)
        os.environ[shadow.MODE_ENV] = "reuse"
        return key

    def part(
        self,
        *,
        key: str | None = None,
        outputs: list[Path] | None = None,
        environment: Any = None,
    ) -> shadow.PartBuild:
        return shadow.PartBuild(
            _STEM,
            self.script,
            key or self.key(),
            list(self.deps),
            self.digest,
            list(outputs or self.outputs),
            self.native,
            environment or (lambda: dict(_PINS)),
        )

    def attempt(self, **options: Any) -> shadow.Reuse:
        """dodo's reuse path for the current source (_cached_part_action,
        _reuse_part): the attempt, then for a reuse install, re-stamp, check
        the token, mark, and store under the key."""
        part = self.part(**options)
        with shadow.reuse_attempt(part) as reuse:
            if reuse.decision is shadow.ReuseDecision.REUSED:
                reuse.install(part.outputs)
                self.token.write_text(_sha(self.native.read_bytes()) + "\n", "utf-8")
                reuse.check_token(self.token)
                reuse.mark()
                reuse.finish(cache.store(part.key, part.outputs, _LABEL))
        return reuse

    def manifest(self, key: str, engine: str | None = None) -> dict[str, Any] | None:
        engine = engine or conv.sha256_file(conv.ENGINE_FILE)
        _, name = shadow.blob_names(engine, _STEM, key)
        data = cache.fetch_sidecar(name)
        return None if data is None else json.loads(data)

    def marker(self, key: str, engine: str | None = None) -> dict[str, Any] | None:
        engine = engine or conv.sha256_file(conv.ENGINE_FILE)
        data = cache.fetch_sidecar(shadow.reused_name(engine, _STEM, key))
        return None if data is None else json.loads(data)


def _replay_as(
    monkeypatch: pytest.MonkeyPatch,
    shop: _Shop,
    *,
    rc: int | None | str = "auto",
    absent: bool = False,
    **result: Any,
) -> list[str]:
    """The pre-build replay replaced by its result (a synthetic base has no
    real log): by default a clean no-op that executed the script and wrote
    the synthetic base's outputs. Returns the keys it replayed."""
    monkeypatch.setattr(shadow, "engine_digest", lambda: _ENGINE)
    replay = {
        "verdict": "noop",
        "recorded": 10,
        "served": 10,
        "python_files": [cache._rel(shop.script)],
        "solidworks_inputs": [],
        "solidworks_out_inputs": [],
        "title_echoes": {"count": 0, "first": []},
        "com_outputs": {"sldprt/fake.SLDPRT": _sha(_NATIVE)},
        "py_outputs": {"py-output.json": _sha(_PY)},
        **result,
    }
    replayed: list[str] = []

    def replay_before(part, reuse, deadline):
        replayed.append(part.key)
        assert part.environment() == _PINS
        reuse.replay_rc = (
            (0 if replay["verdict"] == "noop" else 3) if rc == "auto" else rc
        )
        reuse.replay = None if absent else replay
        reuse.replayed = True
        reuse.replay_log = "replayed\n"

    monkeypatch.setattr(shadow, "_replay_before", replay_before)
    return replayed


def _edited(shop: _Shop, **base: Any) -> str:
    key = shop.base(**base)
    shop.edit(audited=False)
    return key


def _differing(shop: _Shop, relative: str) -> None:
    """A key input at ``relative`` differing between the base and now."""
    path = shop.root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"as the base was built")
    shop.deps.append(str(path))
    shop.base()
    path.write_bytes(b"changed since")


def _case_edited(shop, monkeypatch, blob):
    _edited(shop)


def _case_forced_refresh(shop, monkeypatch, blob):
    _edited(shop)
    monkeypatch.setattr(cache, "forced_refresh", lambda label: "an intended rebuild")


def _case_inputs_moved(shop, monkeypatch, blob):
    _edited(shop)
    return {"key": "k" * 64}


def _rewrite_manifest(blob, key: str, rewrite: Any) -> None:
    """Replace base ``key``'s published manifest with ``rewrite(manifest)``."""
    _, name = shadow.blob_names(_ENGINE, _STEM, key)
    record = rewrite(json.loads(cache.fetch_sidecar(name)))
    _drop(blob, cache._sidecar_blob(name))
    assert cache.publish_sidecar(name, json.dumps(record).encode()) == "stored"


def _case_no_bound_base(shop, monkeypatch, blob):
    # The only recording was made under another cache salt: no base.
    key = _edited(shop)
    _rewrite_manifest(blob, key, lambda m: {**m, "salt": "a-throwaway-proof-salt"})


def _case_legacy_unbound(shop, monkeypatch, blob):
    # Published before manifests were bound to their archive.
    key = _edited(shop)
    _rewrite_manifest(blob, key, lambda m: {**m, "archive": None})


def _case_revoked(shop, monkeypatch, blob):
    key = _edited(shop)
    assert shadow.revoke(_ENGINE, _STEM, key, "a test") == "stored"


def _case_archive_replaced(shop, monkeypatch, blob):
    key = shop.base()
    _drop(blob, cache._BACKEND._name(key))
    shop.write(native=b"another build's part")
    assert cache.store(key, shop.outputs, _LABEL) == "stored"
    shop.edit(audited=False)


def _case_seat_differs(shop, monkeypatch, blob):
    _edited(shop)
    monkeypatch.setattr(shadow, "seat_build", lambda: "35.1.0.4")


def _case_seat_unknown(shop, monkeypatch, blob):
    _edited(shop)
    monkeypatch.setattr(shadow, "seat_build", lambda: None)


def _case_bundle_missing(shop, monkeypatch, blob):
    key = _edited(shop)
    bundle_name, _ = shadow.blob_names(_ENGINE, _STEM, key)
    _drop(blob, cache._sidecar_blob(bundle_name))


def _case_archive_missing(shop, monkeypatch, blob):
    _drop(blob, cache._BACKEND._name(_edited(shop)))


def _case_lookup_budget(shop, monkeypatch, blob):
    _edited(shop)
    monkeypatch.setattr(shadow, "LOOKUP_SECONDS", 0.05)
    blob.list_delay = 0.5


def _case_config(shop, monkeypatch, blob):
    shop.base()
    shop.config.write_text("size: 2\n", "utf-8")


def _case_outside_declared(shop, monkeypatch, blob):
    _edited(shop)
    return {"outputs": [shop.native]}


def _seat_session(shop: _Shop, monkeypatch: pytest.MonkeyPatch, changed: str) -> None:
    """The shop's own seat session, ``_session.py`` importing ``_paths.py``,
    as SESSION_MODULE (its closure derived by _buildgraph from the shop's
    scripts), with ``changed`` (one of them) edited since the base. The
    caller clears _buildgraph's import caches afterwards."""
    scripts = shop.root / "cad" / "scripts"
    scripts.mkdir(parents=True)
    session, paths = scripts / "_session.py", scripts / "_paths.py"
    session.write_text("import _paths\n", "utf-8")
    paths.write_text("PART_TEMPLATE = 'a.PRTDOT'\n", "utf-8")
    shop.deps += [str(session), str(paths)]
    monkeypatch.setattr(shadow, "SESSION_MODULE", session)
    monkeypatch.setattr(_buildgraph, "SCRIPTS_DIR", scripts)
    _buildgraph.clear_import_caches()
    shop.base()
    edited = scripts / changed
    edited.write_text(edited.read_text("utf-8") + "# changed\n", "utf-8")


def _case_seat_session(shop, monkeypatch, blob):
    _seat_session(shop, monkeypatch, "_session.py")


def _case_seat_session_import(shop, monkeypatch, blob):
    # Also when the recipe executes it inside the window (_REPLAYS).
    _seat_session(shop, monkeypatch, "_paths.py")


_PATH_CASES = {
    "template": "cad/templates/harmonic-analyzer.PRTDOT",
    "step_read_by_python": "cad/references/plate.STEP",
    "dxf_read_and_named": "cad/references/plate.dxf",
    "named_by_com": "cad/references/profile.csv",
    "named_and_refused": "cad/references/profile.csv",
}
_REPLAYS: dict[str, dict[str, Any]] = {
    # Python reads each of these, so only the rules under test decline them.
    "step_read_by_python": {"python_files": ["cad/references/plate.STEP"]},
    "seat_session_import": {"python_files": ["cad/scripts/_paths.py"]},
    "dxf_read_and_named": {
        "python_files": ["cad/references/plate.dxf"],
        "solidworks_inputs": ["cad/references/plate.dxf"],
    },
    "named_by_com": {
        "python_files": ["cad/references/profile.csv"],
        "solidworks_inputs": ["cad/references/profile.csv"],
    },
    # Its pinned digest refuses the replay, but the decline says why.
    "named_and_refused": {
        "verdict": "input_mismatch",
        "python_files": ["cad/references/profile.csv"],
        "solidworks_inputs": ["cad/references/profile.csv"],
    },
    "reads_output_root": {"solidworks_out_inputs": ["sldprt/other.SLDPRT"]},
    "seat_state_echo": {
        "title_echoes": {
            "count": 2,
            "first": ["18627 IEquationMgr.Add3", "18628 IEquationMgr.Add2"],
        }
    },
    "echoes_unreported": {"title_echoes": None},
    "diverged": {"verdict": "diverged"},
    "exhausted": {"verdict": "exhausted"},
    "sandbox": {"verdict": "sandbox"},
    "input_mismatch": {"verdict": "input_mismatch"},
    "replay_error": {"rc": 1, "absent": True},
    "replay_timeout": {"rc": None, "absent": True},
    "output_set_differs": {
        "com_outputs": {
            "sldprt/fake.SLDPRT": _sha(_NATIVE),
            "sldprt/extra.SLDPRT": _sha(b"x"),
        }
    },
    "python_output_differs": {"py_outputs": {"py-output.json": _sha(b"other")}},
}
_D = shadow.Decline
_DECLINES = [
    # (case, reason, replays run)
    ("forced_refresh", _D.FORCED_REFRESH, 0),
    ("inputs_moved", _D.INPUTS_MOVED, 0),
    ("no_base", _D.NO_BASE, 0),
    ("no_bound_base", _D.NO_BOUND_BASE, 0),
    ("legacy_unbound", _D.NO_BOUND_BASE, 0),
    ("revoked", _D.REVOKED_BASE, 0),
    ("archive_replaced", _D.UNBOUND_BASE, 1),
    ("seat_differs", _D.SEAT_DIFFERS, 0),
    ("seat_unknown", _D.SEAT_DIFFERS, 0),
    ("lookup_budget", _D.TIME_CAP, 0),
    ("bundle_missing", _D.BASE_BUNDLE_MISSING, 0),
    ("template", _D.UNJUDGED_INPUT, 0),
    ("seat_session", _D.UNJUDGED_INPUT, 0),
    ("seat_session_import", _D.UNJUDGED_INPUT, 0),
    ("step_read_by_python", _D.UNJUDGED_INPUT, 0),
    ("dxf_read_and_named", _D.UNJUDGED_INPUT, 0),
    ("named_by_com", _D.UNJUDGED_INPUT, 1),
    ("named_and_refused", _D.UNJUDGED_INPUT, 1),
    ("config", _D.UNJUDGED_INPUT, 1),
    ("reads_output_root", _D.UNJUDGED_INPUT, 1),
    ("seat_state_echo", _D.SEAT_STATE_ECHO, 1),
    ("echoes_unreported", _D.SEAT_STATE_ECHO, 1),
    ("diverged", _D.DIVERGED, 1),
    ("exhausted", _D.DIVERGED, 1),
    ("sandbox", _D.SANDBOX, 1),
    ("input_mismatch", _D.INPUT_MISMATCH, 1),
    ("replay_error", _D.REPLAY_ERROR, 1),
    ("replay_timeout", _D.TIME_CAP, 1),
    ("archive_missing", _D.BASE_ARCHIVE_MISSING, 1),
    ("output_set_differs", _D.OUTPUT_SET_DIFFERS, 1),
    ("outside_declared", _D.OUTPUT_SET_DIFFERS, 1),
    ("python_output_differs", _D.PYTHON_OUTPUT_DIFFERS, 1),
]


@pytest.mark.parametrize(
    ("case", "reason", "replays"), _DECLINES, ids=[c[0] for c in _DECLINES]
)
def test_every_failed_check_declines_and_says_why(
    blob, tmp_path, monkeypatch, spans, logged, request, case, reason, replays
):
    request.addfinalizer(_buildgraph.clear_import_caches)  # _seat_session's
    shop = _Shop(tmp_path, monkeypatch)
    replayed = _replay_as(monkeypatch, shop, **_REPLAYS.get(case, {}))
    options: dict[str, Any] | None = None
    if case in _PATH_CASES:
        _differing(shop, _PATH_CASES[case])
    elif case != "no_base":
        setup = globals().get(f"_case_{case}", _case_edited)
        options = setup(shop, monkeypatch, blob)
    published = dict(blob.committed)
    reuse = shop.attempt(**(options or {}))
    assert reuse.value == f"declined:{reason.value}", reuse.detail
    assert reuse.detail
    assert len(replayed) == replays
    assert reuse.archive is None
    # Nothing stored or published: the build runs on the seat.
    assert blob.committed == published
    assert not [m for m in logged["warn"] if "building on the seat" in m]
    [record] = _events(tmp_path, "replay_reuse")
    assert record["reuse_decision"] == reuse.value
    assert (record["decline"], record["store"], record["marker"]) == (
        reason.value,
        None,
        None,
    )
    [span] = spans.named("replay.reuse ")
    assert span["replay.reuse_decision"] == reuse.value
    assert span["service"] == _telemetry.BUILD_INFRA_SERVICE
    [line] = [
        m for m in logged["info"] if m.startswith(f"[com-replay] {_LABEL}: reuse=")
    ]
    assert line.startswith(f"[com-replay] {_LABEL}: reuse=declined:{reason.value} |")
    assert "\n" not in line


def test_inert_edits_reuse_the_one_real_build_until_a_refresh_revokes_it(
    blob, tmp_path, monkeypatch, spans, logged
):
    shop = _Shop(tmp_path, monkeypatch)
    base = shop.build()
    built = shop.outputs_now()
    stored = cache.publication(base.key)
    assert stored is not None and stored[0] == "stored"
    origin = shop.manifest(base.key)
    assert origin["archive"] == {"sha256": stored[1][0], "size": stored[1][1]}
    assert origin["sw_build"] == _SEAT_BUILD
    shop.clear()
    key = shop.edit(audited=False)
    reuse = shop.attempt()
    assert reuse.value == "reused", reuse.detail
    # The base's outputs, byte for byte, re-stamped to the base's token.
    assert shop.outputs_now() == built
    assert reuse.token == _sha(built["fake.SLDPRT"])
    assert shop.token.read_text("utf-8").strip() == reuse.token
    # Stored under the new key through the create-only store, and a restore
    # of the new key is the base's outputs.
    assert cache.publication(key)[0] == "stored"
    shop.clear()
    assert cache.restore(key, shop.outputs, _LABEL)
    assert shop.outputs_now() == built
    # No recording of the reused key (only real builds are bases), only the
    # marker naming the build and the archive it came from.
    engine = conv.sha256_file(conv.ENGINE_FILE)
    bundle_name, _ = shadow.blob_names(engine, _STEM, key)
    assert shop.manifest(key) is None and cache.fetch_sidecar(bundle_name) is None
    marker = shop.marker(key)
    assert (marker["key"], marker["origin_key"]) == (key, base.key)
    assert (
        marker["archive"]
        == origin["archive"]
        == {
            "sha256": stored[1][0],
            "size": stored[1][1],
        }
    )
    assert marker["commit"] and marker["marked_utc"]
    assert shop.ran == ["replay"]
    [record] = _events(tmp_path, "replay_reuse")
    assert (record["base_key"], record["differing"]) == (
        base.key,
        ["src/" + shop.script.name],
    )
    assert (record["store"], record["marker"]) == ("stored", "stored")
    assert record["verdict"] == "noop" and record["served"] == record["recorded"] > 20
    assert list(record["seconds"]) == list(shadow._REUSE_PHASES)
    assert record["archive_bytes"] == stored[1][1]
    [span] = spans.named("replay.reuse ")
    assert span["replay.reuse_decision"] == "reused"
    assert span["replay.base_key"] == base.key[:12]
    assert {f"replay.{p}_s" for p in shadow._REUSE_PHASES} <= set(span)
    line = [m for m in logged["info"] if m.startswith("[com-replay] part:")][-1]
    assert line.startswith(
        f"[com-replay] {_LABEL}: reuse=reused | base={base.key[:12]} differing=1 "
        f"| shadow=noop served={record['served']}/{record['recorded']} | lookup="
    )
    assert "| store=stored marker=stored" in line
    # The local record of the reuse.
    kept = json.loads((shadow.RECORDINGS / _STEM / shadow.REUSE_NAME).read_text())
    assert kept["reuse_decision"] == "reused"
    # A second generation reuses from the same real build.
    shop.clear()
    third = shop.edit(audited=False)
    again = shop.attempt()
    assert again.value == "reused", again.detail
    assert again.base.manifest["key"] == base.key
    assert shop.marker(third)["origin_key"] == base.key
    assert shop.outputs_now() == built
    assert shop.ran == ["replay", "replay"]
    # A forced refresh of a reused key revokes the build it came from, and no
    # key reuses it again.
    monkeypatch.setattr(cache, "forced_refresh", lambda label: "suspect")
    assert shop.attempt(key=third).value == "declined:forced_refresh"
    assert shadow.revoked(engine, _STEM, base.key)
    assert not shadow.revoked(engine, _STEM, third)
    monkeypatch.setattr(cache, "forced_refresh", lambda label: None)
    shop.edit(audited=False)
    revoked = shop.attempt()
    assert revoked.value == "declined:revoked_base", revoked.detail
    assert shop.ran == ["replay", "replay"]
    assert any(f"base {base.key[:12]} revoked" in m for m in logged["warn"])


def test_a_build_that_is_not_reused_is_judged_with_the_replay_before_it(
    blob, tmp_path, monkeypatch, spans, logged
):
    shop = _Shop(tmp_path, monkeypatch)
    base = shop.build()
    # An audited would-be reuse builds on the seat (as dodo then does),
    # recorded, and is judged with the replay the attempt already ran: a
    # build whose conversation contradicts the no-op raises the alarm.
    shop.edit(audited=True)
    reuse = shop.attempt()
    assert reuse.value == "audited", reuse.detail
    assert reuse.archive is None and reuse.store is None
    diff = shadow._diff
    monkeypatch.setattr(
        shadow,
        "_diff",
        lambda *_a: (
            3,
            {
                "request_divergence": {"index": 3, "field": "args"},
                "truth_cause": "request",
                "outcome": "different",
            },
        ),
    )
    audited = shop.build(reuse=reuse)
    assert shop.ran == ["replay"]
    record = _events(tmp_path, "replay_shadow")[-1]
    assert (record["reuse_decision"], record["outcome"]) == ("audited", "evaluated")
    assert (record["verdict"], record["soundness_alarm"]) == ("noop", True)
    assert record["base_key"] == base.key
    assert (audited.directory / shadow.REPLAY_LOG_NAME).is_file()
    [message] = logged["error"]
    assert "SOUNDNESS ALARM" in message
    assert "| reuse=audited |" in logged["info"][-1]
    # The alarmed base is revoked: no reuse installs its archive again.
    assert record["revoked"] == "stored"
    assert shadow.revoked(conv.sha256_file(conv.ENGINE_FILE), _STEM, base.key)
    # A diverging edit builds, and after the build only the comparison runs.
    monkeypatch.setattr(shadow, "_diff", diff)
    shop.script.write_text(
        _E2E_SCRIPT.replace("scenario(adapter)", "scenario(adapter, variant='extra')"),
        "utf-8",
    )
    declined = shop.attempt()
    assert declined.value == "declined:diverged", declined.detail
    current = shop.build(reuse=declined)
    assert shop.ran == ["replay", "replay", "diff"]
    record = _events(tmp_path, "replay_shadow")[-1]
    assert record["reuse_decision"] == "declined:diverged"
    assert (record["verdict"], record["ground_truth"]) == ("diverged", "diverged")
    assert record["base_key"] == audited.key and not record["soundness_alarm"]
    assert current.reuse is declined


def test_an_audited_build_that_took_a_seat_path_detour_revokes_nothing(
    blob, tmp_path, monkeypatch, spans, logged
):
    shop = _Shop(tmp_path, monkeypatch)
    base = shop.build()
    shop.edit(audited=True)
    reuse = shop.attempt()
    assert reuse.value == "audited", reuse.detail
    # The audited build on the seat detoured (mg_magnifying_wheel's shape):
    # counted, and the base stays reusable.
    monkeypatch.setattr(shadow, "_diff", lambda *_a: (91, _DETOURED))
    shop.build(reuse=reuse)
    record = _events(tmp_path, "replay_shadow")[-1]
    assert (record["reuse_decision"], record["verdict"]) == ("audited", "noop")
    assert record["noop_judgement"] == "seat_path_divergence"
    assert record["seat_path_divergence"] and not record["soundness_alarm"]
    assert "revoked" not in record and logged["error"] == []
    assert logged["info"][-1].endswith("| seat_path_divergence")
    assert not shadow.revoked(conv.sha256_file(conv.ENGINE_FILE), _STEM, base.key)
    shop.edit(audited=False)
    again = shop.attempt()
    assert again.value == "reused", again.detail


def test_a_build_on_another_solidworks_revision_is_not_judged_by_the_replay(
    blob, tmp_path, monkeypatch
):
    # A replay stands for the base's seat; the build ran on another revision.
    shop = _Shop(tmp_path, monkeypatch)
    replay = {"verdict": "noop", "recorded": 10, "served": 10}
    base = shadow.Base({"key": "b" * 64, "sw_revision": "34.2.0"}, ("x",), 0.0)
    reuse = shadow.Reuse(
        shop.part(), base=base, bundle=b"", replayed=True, replay_rc=0, replay=replay
    )
    monkeypatch.setattr(shadow, "unbundle", lambda data, target: None)
    monkeypatch.setattr(shadow, "_diff", lambda *_a: (0, None))
    recording = types.SimpleNamespace(directory=tmp_path)
    judged = shadow.judge_replayed(recording, reuse, {"sw_revision": "34.3.0"})
    assert judged.verdict == "input_mismatch" and "sw_revision" in judged.reason


def test_a_lost_publication_publishes_no_recording(blob, tmp_path, monkeypatch):
    shop = _Shop(tmp_path, monkeypatch)
    monkeypatch.setenv(shadow.MODE_ENV, "record")
    key = shop.key()
    shop.write(native=b"the winner's part")
    assert cache.store(key, shop.outputs, _LABEL) == "stored"
    cache._PUBLISHED.clear()  # the winner was another process
    recording = shadow.plan(_STEM, shop.script, key)
    recording.log.write_bytes(b"log")
    recording.summary_path.write_text(json.dumps(_summary()), "utf-8")
    shop.write(native=b"the loser's part")
    assert cache.store(key, shop.outputs, _LABEL) == "lost"
    before = dict(blob.committed)
    shadow.after_build(recording, shop.deps, _digest)
    assert blob.committed == before
    [record] = _events(tmp_path, "replay_shadow")
    assert (record["publish"], record["bound"], record["outcome"]) == (
        "lost",
        False,
        "recorded",
    )


def test_only_a_build_that_stored_its_archive_publishes_a_recording(
    blob, tmp_path, monkeypatch
):
    shop = _Shop(tmp_path, monkeypatch)
    monkeypatch.setattr(shadow, "engine_digest", lambda: _ENGINE)
    key = shop.base(store=False)
    assert blob.committed == {}
    assert shop.manifest(key, _ENGINE) is None
    [record] = _events(tmp_path, "replay_shadow")
    assert (record["publish"], record["bound"]) == ("unstored", False)
    # Manifests published before binding, or bound to a malformed digest,
    # are unbound.
    assert shadow.bound_archive({"key": key}) is None
    assert shadow.bound_archive({"archive": None}) is None
    assert shadow.bound_archive({"archive": {"sha256": "x" * 64}}) is None
    assert shadow.bound_archive({"archive": {"sha256": "a" * 64}}) == "a" * 64


def test_the_audit_samples_one_key_in_eight():
    sampled = sum(shadow.audited(f"{i:064x}") for i in range(8000))
    assert 850 < sampled < 1150
    assert shadow.AUDIT_ONE_IN == 8


def test_the_seat_build_is_the_registered_servers_file_version(monkeypatch):
    if sys.platform != "win32":
        assert shadow.seat_build.__wrapped__() is None
        return
    import winreg

    # SolidWorks registered as this Python (a file with a version resource),
    # read without starting it; every other registry read is the real one.
    executable = sys._base_executable
    server = {
        r"SldWorks.Application\CLSID": "{5F0B1F4E}",
        r"CLSID\{5F0B1F4E}\LocalServer32": f'"{executable}" /automation',
    }
    open_key, query_value = winreg.OpenKey, winreg.QueryValue

    def opened(root: Any, path: str, *rest: Any) -> Any:
        if path in server:
            return contextlib.nullcontext(path)
        if path.startswith(("SldWorks", "CLSID\\")):
            raise OSError(path)
        return open_key(root, path, *rest)

    def queried(handle: Any, name: Any) -> Any:
        return server[handle] if isinstance(handle, str) else query_value(handle, name)

    monkeypatch.setattr(winreg, "OpenKey", opened)
    monkeypatch.setattr(winreg, "QueryValue", queried)
    found = shadow.seat_build.__wrapped__()
    major, minor, *_ = sys.version_info
    assert found is not None and found.startswith(f"{major}.{minor}.")
    assert len(found.split(".")) == 4 and all(p.isdigit() for p in found.split("."))
    # An unquoted server command line names the same executable.
    server[r"CLSID\{5F0B1F4E}\LocalServer32"] = f"{executable} -Embedding"
    assert shadow.seat_build.__wrapped__() == found
    # No SolidWorks registered: unknown.
    del server[r"SldWorks.Application\CLSID"]
    assert shadow.seat_build.__wrapped__() is None


def test_solidworks_inputs_are_the_logs_repository_and_uncaptured_output_paths():
    import com_replay

    trailer = {
        "external": {
            "<REPO>\\cad\\references\\plate.dxf": "d" * 64,
            "<REPO/>cad/references/plate.STEP": "s" * 64,
            "C:\\ProgramData\\SOLIDWORKS\\font.ttf": "f" * 64,
        },
        "internal_paths": ["<OUT>\\sldprt\\a.SLDPRT", "<OUT>\\sldprt\\b.SLDPRT"],
        "captured": {"7": {"sldprt/a.SLDPRT": {"file": "000000.gz"}}},
    }
    named, inside = com_replay._solidworks_inputs(
        types.SimpleNamespace(trailer=trailer)
    )
    assert named == ["cad/references/plate.STEP", "cad/references/plate.dxf"]
    assert inside == ["sldprt/b.SLDPRT"]


def test_the_outside_window_inputs_are_the_seat_sessions_keyed_closure():
    outside = shadow.outside_window_inputs()
    assert {
        "cad/scripts/_session.py",
        "cad/scripts/_paths.py",
        "cad/scripts/_com.py",
    } <= outside
    # Only key inputs: _buildgraph leaves out what never keys a part.
    assert "cad/scripts/_telemetry.py" not in outside
    assert "cad/scripts/_watchdog.py" not in outside


def test_dodo_keys_the_template_the_session_pins():
    import _paths

    assert _load_dodo().PART_TEMPLATE.resolve() == _paths.PART_TEMPLATE.resolve()


# The fake seat's run_build with what a real _session.run_build also has: seat
# state set BEFORE the recorded window from a repository module (as
# _pin_default_part_template reads _paths.PART_TEMPLATE). The fake server's
# Volume answers scale with it.
_SEAT_CONFIG_DRIVER = """
import asyncio, os, sys
import _session
import test_com_conversation as fixture
sys.path.insert(0, os.environ["SEAT_CONFIG_SRC"])
def run_build(build):
    import seatcfg
    adapter = fixture.FakeAdapter(fixture.FakeServer(volume_scale=seatcfg.SCALE))
    try:
        asyncio.run(build(adapter))
    except Exception:
        return 1
    return 0
_session.run_build = run_build
import com_replay
sys.exit(com_replay.main(sys.argv[1:]))
"""


def test_seat_state_set_outside_the_window_is_never_reused(
    blob, tmp_path, monkeypatch, request
):
    # The adversarial review's demonstration (2026-11-12): the session sets
    # seat state outside the recorded window from a module the recipe also
    # imports. A replay serves the base's answers, so it cannot see a change.
    request.addfinalizer(_buildgraph.clear_import_caches)
    shop = _Shop(tmp_path, monkeypatch, script="import seatcfg\n" + _E2E_SCRIPT)
    source = shop.script.parent
    seatcfg, session = source / "seatcfg.py", source / "seat_session.py"
    seatcfg.write_text("SCALE = 1.0\n", "utf-8")
    session.write_text("import seatcfg\n", "utf-8")
    shop.deps += [str(seatcfg), str(session)]
    monkeypatch.setattr(shadow, "SESSION_MODULE", session)
    monkeypatch.setattr(_buildgraph, "SCRIPTS_DIR", source)
    _buildgraph.clear_import_caches()
    key = shop.key()
    recording = shadow.plan(_STEM, shop.script, key)
    assert recording is not None
    env = {k: v for k, v in os.environ.items() if k not in _PINS}
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            _SEAT_CONFIG_DRIVER,
            *recording.command[2:],
            "--out-root",
            str(shop.out),
        ],
        cwd=SCRIPTS,
        env={
            **env,
            "OTEL_EXPORTER_OTLP_ENDPOINT": "",
            "PYTHONHASHSEED": "0",
            "SEAT_CONFIG_SRC": str(source),
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert cache.store(key, shop.outputs, _LABEL) == "stored"
    shadow.after_build(recording, shop.deps, shop.digest)
    built = shop.outputs_now()
    # Only the seat state changes: a build now answers Volume twice as large.
    shop.clear()
    seatcfg.write_text("SCALE = 2.0\n", "utf-8")
    shop.edit(audited=False, path=seatcfg)
    reuse = shop.attempt()
    assert reuse.value == "declined:unjudged_input", reuse.detail
    assert "src/seatcfg.py" in reuse.detail
    assert shop.ran == [] and not shop.native.exists()
    # The control: a session whose closure leaves it out, and the same attempt
    # replays clean and reuses the base's part, built at the old scale.
    other = source / "other_session.py"
    other.write_text("SEAT = None\n", "utf-8")
    monkeypatch.setattr(shadow, "SESSION_MODULE", other)
    stale = shop.attempt()
    assert stale.value == "reused", stale.detail
    assert "src/seatcfg.py" in stale.replay["python_files"]
    assert shop.outputs_now() == built


# The end-to-end script, reading the config it never uses.
_READS_CONFIG_SCRIPT = _E2E_SCRIPT.replace(
    "async def build(adapter):\n",
    "from pathlib import Path\n"
    "async def build(adapter):\n"
    "    Path(__file__).with_name('widget.yaml').read_text()\n",
)


def test_a_replay_judges_what_the_recipe_reads_and_nothing_else(
    blob, tmp_path, monkeypatch
):
    shop = _Shop(tmp_path, monkeypatch, script=_READS_CONFIG_SCRIPT)
    notes = shop.script.parent / "notes.txt"
    notes.write_text("never read\n", "utf-8")
    shop.deps.append(str(notes))
    shop.build()
    built = shop.outputs_now()
    shop.clear()
    # A differing file the recipe reads (and does not use): judged, reused.
    shop.edit(audited=False, path=shop.config)
    reuse = shop.attempt()
    assert reuse.value == "reused", reuse.detail
    assert shop.outputs_now() == built
    # The recipe's own reads and imports, never the engine's: not the base
    # log it served, the inputs it digested, or the modules it loaded.
    assert reuse.replay["python_files"] == ["src/build_sh_widget.py", "src/widget.yaml"]
    # A differing file nothing reads: unjudged.
    shop.clear()
    shop.edit(audited=False, path=notes)
    declined = shop.attempt()
    assert declined.value == "declined:unjudged_input", declined.detail
    assert "src/notes.txt" in declined.detail
    assert shop.ran == ["replay", "replay"]


# --------------------------------------------------------------------------- #
# Reuse in dodo's part action
# --------------------------------------------------------------------------- #
def _reuse_action(
    dodo: Any, shop: _Shop, monkeypatch: pytest.MonkeyPatch
) -> tuple[list[str], list[Any]]:
    """``_cached_part_action`` on a cache miss: the seat, connect and build
    faked (the build writes its own outputs), the cache and reuse real."""
    order: list[str] = []
    recordings: list[Any] = []
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: list(shop.deps))
    monkeypatch.setattr(dodo, "_part_cache_outputs", lambda _stem: list(shop.outputs))
    monkeypatch.setattr(dodo, "_probe_cache", lambda *_a: "miss")
    monkeypatch.setattr(dodo, "_reprobe_under_seat", lambda *_a: False)
    monkeypatch.setattr(dodo, "_sldprt", lambda _stem: str(shop.native))
    monkeypatch.setattr(dodo, "_part_execution_token", lambda _stem: str(shop.token))
    monkeypatch.setattr(dodo, "_validate_part_configuration_outputs", lambda *_a: None)
    monkeypatch.setattr(dodo, "_com_process_inputs", lambda _task: dict(_PINS))
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: order.append("sw.connect"))

    @contextlib.contextmanager
    def seat(_label: str):
        order.append("seat")
        yield 0.0

    def exec_com(cmd, label, log_stem=None, **options):
        order.append("build")
        shop.write(native=b"built on the seat")
        recordings.append(options.get("recording"))

    store = cache.store

    def counted_store(key, outputs, label, **options):
        order.append("store")
        return store(key, outputs, label, **options)

    monkeypatch.setattr(dodo, "_com_seat", seat)
    monkeypatch.setattr(dodo, "_exec_com", exec_com)
    monkeypatch.setattr(cache, "store", counted_store)
    monkeypatch.setattr(
        dodo._replay_shadow,
        "after_build",
        lambda recording, deps, digest: order.append("observe"),
    )
    dodo._cached_part_action(_STEM, shop.script)
    return order, recordings


def test_a_reused_part_leaf_runs_no_com(blob, tmp_path, monkeypatch, spans, logged):
    dodo = _load_dodo()
    shop = _Shop(tmp_path, monkeypatch, digest=dodo.ContentChecker._digest)
    replayed = _replay_as(monkeypatch, shop)
    base = _edited(shop)
    shop.clear()
    order, recordings = _reuse_action(dodo, shop, monkeypatch)
    assert order == ["store"] and recordings == []
    assert shop.outputs_now() == {"fake.SLDPRT": _NATIVE, "py-output.json": _PY}
    assert shop.token.read_text("utf-8").strip() == _sha(_NATIVE)
    [task] = spans.named("task ")
    assert (task["cache"], task["com"]) == ("reuse", "none")
    assert not spans.named("sw.") and len(replayed) == 1
    [record] = _events(tmp_path, "replay_reuse")
    assert (record["reuse_decision"], record["base_key"]) == ("reused", base)
    assert (record["store"], record["marker"]) == ("stored", "stored")
    assert shop.manifest(shop.key(), _ENGINE) is None
    assert shop.marker(shop.key(), _ENGINE)["origin_key"] == base


def test_a_token_that_is_not_the_bases_falls_through_to_the_seat(
    blob, tmp_path, monkeypatch, spans, logged
):
    dodo = _load_dodo()
    shop = _Shop(tmp_path, monkeypatch, digest=dodo.ContentChecker._digest)
    _replay_as(monkeypatch, shop)
    _edited(shop)
    monkeypatch.setattr(
        dodo, "_stamp_part_execution", lambda _stem: shop.token.write_text("f" * 64)
    )
    order, [recording] = _reuse_action(dodo, shop, monkeypatch)
    assert order == ["seat", "sw.connect", "build", "store", "observe"]
    assert recording.reuse.value == "declined:token_mismatch"
    [warning] = [m for m in logged["warn"] if "building on the seat" in m]
    assert "reuse declined:token_mismatch in install" in warning
    [record] = _events(tmp_path, "replay_reuse")
    assert record["reuse_decision"] == "declined:token_mismatch"
    assert [task["cache"] for task in spans.named("task ")] == ["reuse_failed", "miss"]


# phase: (what faults, the phase the decline names)
_FAULTS = {
    "lookup": ((shadow, "find_base"), "lookup"),
    "revocation": ((cache, "read_sidecar"), "lookup"),
    "bundle": ((shadow, "_bundle_of"), "bundle"),
    "replay": ((shadow, "_replay_before"), "replay"),
    "archive": ((shadow, "_fetch_base_archive"), "archive"),
    "verify": ((shadow, "_verify_outputs"), "verify"),
    "install": ((cache, "install_archive"), "install"),
    "mark": ((cache, "publish_sidecar"), "mark"),
}


@pytest.mark.parametrize("phase", list(_FAULTS))
def test_a_fault_in_any_phase_never_costs_the_build(
    blob, tmp_path, monkeypatch, spans, logged, phase
):
    dodo = _load_dodo()
    shop = _Shop(tmp_path, monkeypatch, digest=dodo.ContentChecker._digest)
    _replay_as(monkeypatch, shop)
    _edited(shop)

    def fault(*_a, **_k):
        raise RuntimeError(f"injected {phase} fault")

    target, named = _FAULTS[phase]
    monkeypatch.setattr(*target, fault)
    order, recordings = _reuse_action(dodo, shop, monkeypatch)
    [record] = _events(tmp_path, "replay_reuse")
    # Nothing stored under the key but the seat's build, no marker.
    assert order == ["seat", "sw.connect", "build", "store", "observe"]
    assert shop.outputs_now()["fake.SLDPRT"] == b"built on the seat"
    assert shop.marker(shop.key(), _ENGINE) is None
    [recording] = recordings
    assert recording.reuse.value == "declined:fault"
    assert (record["reuse_decision"], record["phase"]) == ("declined:fault", named)
    [warning] = [m for m in logged["warn"] if "building on the seat" in m]
    assert f"reuse declined:fault in {named}" in warning
    assert f"injected {phase} fault" in warning


def test_a_marker_naming_another_base_falls_through_to_the_seat(
    blob, tmp_path, monkeypatch, logged
):
    dodo = _load_dodo()
    shop = _Shop(tmp_path, monkeypatch, digest=dodo.ContentChecker._digest)
    _replay_as(monkeypatch, shop)
    _edited(shop)
    other = json.dumps({"origin_key": "0" * 64}).encode()
    assert (
        cache.publish_sidecar(shadow.reused_name(_ENGINE, _STEM, shop.key()), other)
        == "stored"
    )
    order, [recording] = _reuse_action(dodo, shop, monkeypatch)
    assert order == ["seat", "sw.connect", "build", "store", "observe"]
    assert recording.reuse.value == "declined:fault"
    [warning] = [m for m in logged["warn"] if "building on the seat" in m]
    assert "in mark" in warning and "0" * 64 in warning


def test_a_local_record_that_fails_never_fails_a_stored_reuse(
    blob, tmp_path, monkeypatch, logged
):
    dodo = _load_dodo()
    shop = _Shop(tmp_path, monkeypatch, digest=dodo.ContentChecker._digest)
    _replay_as(monkeypatch, shop)
    _edited(shop)
    shop.clear()

    def broken(*_a):
        raise ValueError("injected local record fault")

    monkeypatch.setattr(shadow, "_fresh_directory", broken)
    order, recordings = _reuse_action(dodo, shop, monkeypatch)
    assert order == ["store"] and recordings == []
    assert cache.publication(shop.key())[0] == "stored"
    [record] = _events(tmp_path, "replay_reuse")
    assert (record["reuse_decision"], record["store"]) == ("reused", "stored")
    assert any("local reuse record not kept" in m for m in logged["warn"])


@pytest.mark.parametrize("mode", ["reuse", "shadow", "record"])
def test_a_forced_refresh_of_a_base_revokes_it(
    blob, tmp_path, monkeypatch, logged, mode
):
    shop = _Shop(tmp_path, monkeypatch)
    replayed = _replay_as(monkeypatch, shop)
    key = shop.base()
    monkeypatch.setenv(shadow.MODE_ENV, mode)
    monkeypatch.setattr(cache, "forced_refresh", lambda label: "an intended rebuild")
    reuse = shop.attempt(key=key)
    expected = "declined:forced_refresh" if mode == "reuse" else None
    assert reuse.value == expected, reuse.detail
    assert shadow.revoked(_ENGINE, _STEM, key) and replayed == []
    assert any(f"base {key[:12]} revoked" in m for m in logged["warn"])


@pytest.mark.parametrize("fault", ["write", "read"])
def test_a_revocation_that_fails_never_costs_the_build(
    blob, tmp_path, monkeypatch, logged, fault
):
    shop = _Shop(tmp_path, monkeypatch)
    _replay_as(monkeypatch, shop)
    key = shop.base()

    def unreadable(*_a):
        raise OSError("injected read fault")

    if fault == "write":
        monkeypatch.setattr(cache, "publish_sidecar", lambda *_a: "error")
    else:
        monkeypatch.setattr(cache, "read_sidecar", unreadable)
    # A forced refresh still builds on the seat.
    monkeypatch.setattr(cache, "forced_refresh", lambda label: "an intended rebuild")
    assert shop.attempt(key=key).value == "declined:forced_refresh"
    assert any("revocation failed" in m for m in logged["warn"])
    # A soundness alarm is still raised and recorded.
    assert shadow._revoke_alarmed(_ENGINE, _STEM, {"key": key}) == (
        "error" if fault == "write" else "stored"
    )
    revocation = cache._sidecar_blob(shadow.revoked_name(_ENGINE, _STEM, key))
    assert (revocation in blob.committed) is (fault == "read")


@pytest.mark.parametrize("mode", ["shadow", "record", "off"])
def test_other_modes_make_no_attempt(blob, tmp_path, monkeypatch, spans, mode):
    dodo = _load_dodo()
    shop = _Shop(tmp_path, monkeypatch, digest=dodo.ContentChecker._digest)
    replayed = _replay_as(monkeypatch, shop)
    _edited(shop)
    monkeypatch.setenv(shadow.MODE_ENV, mode)
    order, [recording] = _reuse_action(dodo, shop, monkeypatch)
    assert order == ["seat", "sw.connect", "build", "store", "observe"]
    assert replayed == [] and not spans.named("replay.reuse ")
    assert _events(tmp_path, "replay_reuse") == []
    if mode == "off":
        assert recording is None
        return
    assert recording.mode.value == mode and recording.reuse.decision is None


def test_an_audited_key_builds_on_the_seat(blob, tmp_path, monkeypatch, spans):
    dodo = _load_dodo()
    shop = _Shop(tmp_path, monkeypatch, digest=dodo.ContentChecker._digest)
    _replay_as(monkeypatch, shop)
    shop.base()
    shop.edit(audited=True)
    order, [recording] = _reuse_action(dodo, shop, monkeypatch)
    assert order == ["seat", "sw.connect", "build", "store", "observe"]
    assert recording.reuse.value == "audited" and recording.reuse.replayed
    assert [task["cache"] for task in spans.named("task ")] == ["miss"]


# --------------------------------------------------------------------------- #
# Assemblies and drawings: recorded, judged against the nearest earlier
# recording made on the same children, never reused
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ("reuse", "shadow", "shadow")),
        ("reuse", ("reuse", "shadow", "shadow")),
        ("record", ("record", "record", "record")),
        ("off", ("off", "off", "off")),
        ("shadow,drawing=off", ("shadow", "shadow", "off")),
        ("assembly=record", ("reuse", "record", "shadow")),
        ("drawing=reuse", ("reuse", "shadow", "shadow")),
        (" Drawing = Record , part=off ", ("off", "shadow", "record")),
        ("off,assembly=shadow", ("off", "shadow", "off")),
    ],
)
def test_each_kind_has_its_mode_and_dependents_never_reuse(
    monkeypatch, logged, value, expected
):
    if value is None:
        monkeypatch.delenv(shadow.MODE_ENV, raising=False)
    else:
        monkeypatch.setenv(shadow.MODE_ENV, value)
    assert tuple(shadow.mode(kind).value for kind in shadow.BuildKind) == expected
    assert logged["warn"] == []


@pytest.mark.parametrize(
    "value", ["drawing=on", "gear=shadow", "drawing=", "shadow,=off"]
)
def test_an_unknown_kind_or_mode_is_off_for_every_kind(monkeypatch, logged, value):
    monkeypatch.setattr(shadow, "_UNKNOWN_MODES", set())
    monkeypatch.setenv(shadow.MODE_ENV, value)
    modes = {shadow.mode(kind) for kind in shadow.BuildKind for _ in range(2)}
    assert modes == {shadow.ReplayMode.OFF}
    assert len(logged["warn"]) == 1 and repr(value) in logged["warn"][0]


_CHILD = "cad/out/sldprt/.sh-widget.execution"


def _drawing(script: Path, token: str = "a" * 64) -> shadow.Dependent:
    return shadow.Dependent(
        shadow.BuildKind.DRAWING, _STEM, script, (_STEM,), {_CHILD: token}
    )


def _planned(dependent: shadow.Dependent, key: str) -> shadow.Recording | None:
    return shadow.plan_dependent(dependent.kind, lambda: dependent, key)


def test_a_drawing_recording_keeps_its_argument_and_a_name_of_its_own(
    blob, tmp_path, monkeypatch, logged
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    script = tmp_path / f"draw_{_STEM}.py"
    recording = _planned(_drawing(script), "k" * 64)
    assert recording is not None and recording.mode is shadow.ReplayMode.SHADOW
    assert (recording.label, recording.name) == (f"drawing:{_STEM}", f"drawing-{_STEM}")
    assert recording.directory == shadow.RECORDINGS / f"drawing-{_STEM}"
    assert recording.command[:4] == [
        sys.executable,
        str(shadow.DRIVER),
        "record",
        str(script),
    ]
    assert recording.command[-2:] == ["--", _STEM]
    assert recording.unrecorded == [sys.executable, str(script), _STEM]
    # The part of the same stem keeps its recordings, locally and published.
    part = shadow.plan(_STEM, tmp_path / f"build_{_STEM}.py", "k" * 64)
    assert part.directory == shadow.RECORDINGS / _STEM and "--" not in part.command
    assert shadow.blob_prefix(_ENGINE, recording.name) != shadow.blob_prefix(
        _ENGINE, part.name
    )

    # Off for its kind, or a cache that cannot publish: run as ever, without
    # describing the build.
    def undescribable() -> shadow.Dependent:
        raise AssertionError("described")

    monkeypatch.setenv(shadow.MODE_ENV, "drawing=off")
    assert shadow.plan_dependent(shadow.BuildKind.DRAWING, undescribable, "k") is None
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "ro")
    assert shadow.plan_dependent(shadow.BuildKind.DRAWING, undescribable, "k") is None
    assert logged["warn"] == []
    # A build its recording cannot describe builds unrecorded.
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    assert shadow.plan_dependent(shadow.BuildKind.DRAWING, undescribable, "k") is None
    assert len(logged["warn"]) == 1 and "building unrecorded" in logged["warn"][0]


def test_a_drawing_rerun_after_a_recorder_fault_keeps_its_argument(
    blob, tmp_path, monkeypatch, logged
):
    dodo = _load_dodo()
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    script = tmp_path / f"draw_{_STEM}.py"
    recording = _planned(_drawing(script), "k" * 64)
    commands: list[list[str]] = []

    def run_subprocess(cmd, label, log_stem=None, *, task=None, env_pins=None):
        commands.append(cmd)
        if len(commands) > 1:
            return 0
        fault = {"where": "Recorder.call", "recovery": "rerun", "type": "OSError"}
        recording.summary_path.write_text(
            json.dumps(_summary(exit_code=92, complete=False, faults=[fault])), "utf-8"
        )
        return shadow.EXIT_RECORD_FAULT

    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: False)
    monkeypatch.setattr(dodo, "_run_subprocess", run_subprocess)
    dodo._exec_com(
        recording.command, f"drawing:{_STEM}", f"drawing-{_STEM}", recording=recording
    )
    assert commands == [recording.command, [sys.executable, str(script), _STEM]]
    assert recording.recovery is shadow.Recovery.RERUN


def test_sidecars_are_kept_as_the_build_wrote_them(blob, tmp_path, monkeypatch):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    proof = tmp_path / "out" / "sldasm" / ".sh-widget.massprops.sha"
    proof.parent.mkdir(parents=True)
    proof.write_text("built\n", encoding="utf-8")
    dof = proof.with_name(".sh-widget.dof.json")  # this assembly frees no DOF
    dependent = shadow.Dependent(
        shadow.BuildKind.ASSEMBLY,
        _STEM,
        tmp_path / f"build_{_STEM}_assembly.py",
        (),
        {_CHILD: "a" * 64},
        (proof, dof),
    )
    recording = _planned(dependent, "k" * 64)
    recording.summary_path.write_text(json.dumps(_summary()), "utf-8")
    assert not recording.exited(1)  # the build failed: nothing kept
    assert not recording.sidecar_copies.exists()
    assert not recording.exited(0)
    proof.write_text("adopted from the store's winner\n", encoding="utf-8")
    copies = {p.name: p.read_text("utf-8") for p in recording.sidecar_copies.iterdir()}
    assert copies == {proof.name: "built\n"}


def test_children_are_every_model_opened_transitively_by_token(monkeypatch, tmp_path):
    dodo = _load_dodo()
    graph = {"top": ["sub", "p1"], "sub": ["p1", "p2", "p3", "p4"]}
    monkeypatch.setattr(dodo, "ASSEMBLY_ORDER", ["sub", "top"])
    monkeypatch.setattr(dodo, "references_of", lambda stem: graph[stem])
    monkeypatch.setattr(
        dodo, "_part_execution_token", lambda s: str(tmp_path / f".{s}.part")
    )
    monkeypatch.setattr(
        dodo, "_assembly_execution_token", lambda s: str(tmp_path / f".{s}.asm")
    )
    (tmp_path / ".sub.asm").write_text("a" * 64 + "\n", encoding="utf-8")
    (tmp_path / ".p1.part").write_text("b" * 64 + "\n", encoding="utf-8")
    (tmp_path / ".p2.part").write_text("not a digest\n", encoding="utf-8")
    (tmp_path / ".p4.part").mkdir()  # a token that cannot be read
    found = dodo._child_identities(graph["top"])
    assert found.pop(".p4.part").startswith("unreadable: ")
    assert found == {
        ".sub.asm": "a" * 64,
        ".p1.part": "b" * 64,
        ".p2.part": "malformed: 'not a digest'",
        ".p3.part": "missing",  # no token at all
    }


def test_a_drawing_dependent_names_its_script_argument_and_model(monkeypatch, tmp_path):
    dodo = _load_dodo()
    monkeypatch.setattr(
        dodo, "_part_execution_token", lambda s: str(tmp_path / f".{s}.part")
    )
    monkeypatch.setattr(
        dodo, "_assembly_execution_token", lambda s: str(tmp_path / f".{s}.asm")
    )
    specs = {
        spec.source_kind: (name, spec) for name, spec in dodo.DRAWINGS_BY_NAME.items()
    }
    for kind in ("part", "assembly"):
        name, spec = specs[kind]
        dependent = dodo._drawing_dependent(name)
        assert (dependent.kind, dependent.stem, dependent.script, dependent.argv) == (
            shadow.BuildKind.DRAWING,
            name,
            spec.script.resolve(),
            (spec.artifact_stem,),
        )
        if kind == "part":
            assert dependent.children == {f".{spec.part}.part": "missing"}
        else:
            assert dependent.children == dodo._child_identities([spec.part])
            assert f".{spec.part}.asm" in dependent.children
            assert len(dependent.children) > 1


def _com_action_runs(dodo: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """``_cached_com_action`` on a miss for a drawing: seat and build faked."""
    script = tmp_path / f"draw_{_STEM}.py"
    deps = [str(script)]
    order: list[str] = []
    runs: list[tuple[list[str], Any]] = []
    observed: list[tuple[Any, list[str]]] = []
    outcomes = iter((False, False))  # probe MISS, re-probe under the seat MISS
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_a: next(outcomes))
    monkeypatch.setattr(
        dodo._cache, "store", lambda *_a: (order.append("store"), "stored")[1]
    )
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)

    @contextlib.contextmanager
    def seat(_label: str):
        order.append("seat")
        yield 0.0
        order.append("seat released")

    def exec_com(cmd, label, log_stem=None, **options):
        order.append("build")
        runs.append((cmd, options.get("recording")))

    def after_build(recording, file_deps, digest):
        order.append("observe")
        observed.append((recording, file_deps))

    monkeypatch.setattr(dodo, "_com_seat", seat)
    monkeypatch.setattr(dodo, "_exec_com", exec_com)
    monkeypatch.setattr(dodo._replay_shadow, "after_build", after_build)
    dodo._cached_com_action(
        f"drawing:{_STEM}",
        [sys.executable, str(script), _STEM],
        deps,
        [tmp_path / f"{_STEM}.SLDDRW"],
        log_stem=f"drawing-{_STEM}",
        recorded=lambda key: _planned(_drawing(script), key),
    )
    return script, deps, order, runs, observed


@pytest.mark.parametrize("value", ["shadow", "drawing=off"])
def test_a_drawing_builds_under_the_driver_and_is_observed_off_the_seat(
    blob, tmp_path, monkeypatch, value
):
    dodo = _load_dodo()
    monkeypatch.setenv(shadow.MODE_ENV, value)
    script, deps, order, runs, observed = _com_action_runs(dodo, monkeypatch, tmp_path)
    assert order == ["seat", "build", "seat released", "store", "observe"]
    [(command, recording)] = runs
    assert observed == [(recording, deps)]
    if value == "drawing=off":
        assert (command, recording) == ([sys.executable, str(script), _STEM], None)
        return
    assert recording.kind is shadow.BuildKind.DRAWING and recording.key == "k" * 64
    assert command == recording.command and command[-2:] == ["--", _STEM]


@pytest.mark.parametrize("tier", ["full", "refresh"])
def test_only_a_full_assembly_build_is_recorded(blob, tmp_path, monkeypatch, tier):
    dodo = _load_dodo()
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    stem = "ms_measuring_stick"
    target = tmp_path / f"{stem}.SLDASM"
    ledger = tmp_path / f".{stem}.inputs.json"
    proof = tmp_path / f".{stem}.massprops.sha"
    # The recipe's content is no concern here: its script alone, so the test
    # never walks the helper closure.
    deps = [str(dodo.SCRIPTS_DIR / f"build_{stem}_assembly.py")]
    if tier == "refresh":
        # Built from exactly the current recipe: only a reference could differ.
        target.write_bytes(b"asm")
        dodo._write_input_ledger(ledger, dodo._ledger_inputs(deps))
    order: list[str] = []
    runs: list[tuple[list[str], Any]] = []
    observed: list[tuple[Any, list[str]]] = []

    @contextlib.contextmanager
    def seat(_label: str):
        order.append("seat")
        yield 0.0
        order.append("seat released")

    def exec_com(cmd, label, log_stem=None, **options):
        order.append("build")
        runs.append((cmd, options.get("recording")))

    def after_build(recording, file_deps, digest):
        order.append("observe")
        observed.append((recording, file_deps))

    monkeypatch.setattr(dodo, "_recipe_files", lambda _stem: deps)
    monkeypatch.setattr(dodo, "_assembly_file_deps", lambda _stem: deps)
    monkeypatch.setattr(dodo, "POST_ASSEMBLY", {})
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_a: False)
    monkeypatch.setattr(
        dodo._cache, "store", lambda *_a, **_kw: (order.append("store"), "stored")[1]
    )
    monkeypatch.setattr(dodo._farm, "enabled", lambda: False)
    monkeypatch.setattr(dodo, "_com_seat", seat)
    monkeypatch.setattr(dodo, "_reprobe_under_seat", lambda *_a: False)
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(dodo, "_input_ledger", lambda _stem: ledger)
    monkeypatch.setattr(dodo, "_assembly_cache_outputs", lambda _stem: [target, proof])
    monkeypatch.setattr(dodo, "_stamp_assembly_execution", lambda _stem: None)
    monkeypatch.setattr(dodo, "_exec_com", exec_com)
    monkeypatch.setattr(dodo._replay_shadow, "after_build", after_build)
    dodo.build_or_refresh(stem, [], [], [str(target)])
    assert order == ["seat", "build", "seat released", "store", "observe"]
    [(command, recording)] = runs
    assert observed == [(recording, deps)]
    if tier == "refresh":
        assert recording is None and Path(command[1]).name == "refresh_assembly.py"
        return
    assert command == recording.command
    assert (recording.kind, recording.stem, recording.argv) == (
        shadow.BuildKind.ASSEMBLY,
        stem,
        (),
    )
    assert recording.unrecorded == [
        sys.executable,
        str(dodo.SCRIPTS_DIR / f"build_{stem}_assembly.py"),
    ]
    assert recording.sidecars == (proof,)
    assert recording.children == dodo._child_identities(dodo.references_of(stem))
    assert recording.children


def test_every_dependent_recording_has_a_name_of_its_own_within_the_path_limit(
    monkeypatch,
):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    dodo = _load_dodo()
    parts = [s.stem.removeprefix("build_") for s in _buildgraph.part_scripts()]
    dependents = [
        *(
            (shadow.BuildKind.ASSEMBLY, stem, dodo._assembly_judged_sidecars(stem))
            for stem in _buildgraph.ASSEMBLY_ORDER
        ),
        *((shadow.BuildKind.DRAWING, stem, ()) for stem in dodo.DRAWINGS_BY_NAME),
    ]
    assert len(dependents) > 100
    # Stems hold no "-", so no recording name is another's.
    stems = [*parts, *(stem for _kind, stem, _sidecars in dependents)]
    assert not [stem for stem in stems if "-" in stem]
    names = [
        *parts,
        *(shadow.recording_name(kind, stem) for kind, stem, _ in dependents),
    ]
    assert len(names) == len(set(names))
    checkout = PureWindowsPath(shadow.REPO_ROOT)
    repo = max(_FARM_REPO, checkout, key=lambda root: len(str(root)))

    def under(path: Path) -> PureWindowsPath:
        return repo / PureWindowsPath(path.relative_to(shadow.REPO_ROOT))

    tightest: list[tuple[int, str, str]] = []
    for kind, stem, sidecars in dependents:
        files = [path.name for path in sidecars]
        needs = shadow.path_needs(
            shadow.recording_name(kind, stem),
            under(shadow.RECORDINGS),
            under(shadow.SCRATCH),
            sidecars=files,
        )
        assert {f"sidecar {file}" for file in files} <= {n.purpose for n in needs}
        need = min(needs, key=lambda n: n.headroom)
        tightest.append((need.headroom, stem, need.path))
    assert any(
        sidecars for kind, _stem, sidecars in dependents if kind.value == "assembly"
    )
    headroom, stem, path = min(tightest)
    assert headroom >= _FARM_HEADROOM, (stem, len(path), path)


def test_an_oversize_dependent_bundle_is_not_published(blob, tmp_path, monkeypatch):
    monkeypatch.setenv(shadow.MODE_ENV, "record")
    monkeypatch.setattr(shadow, "BUNDLE_LIMIT", 16)
    script = tmp_path / f"draw_{_STEM}.py"
    script.write_text("# the drawing\n", encoding="utf-8")
    deps = [str(script)]
    key, _ = cache.key_inputs(deps, _digest)
    recording = _planned(_drawing(script), key)
    recording.log.write_bytes(b"log of " + key.encode())
    recording.summary_path.write_text(json.dumps(_summary()), "utf-8")
    _stored(key)
    shadow.after_build(recording, deps, _digest)
    [record] = _events(tmp_path, "replay_shadow")
    assert (record["outcome"], record["publish"]) == ("recorded", "oversize")
    assert blob.committed == {}


def test_a_dependent_comparison_past_a_bound_is_no_judgement(
    blob, tmp_path, monkeypatch
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    recording = _planned(_drawing(tmp_path / "draw.py"), "k" * 64)
    big = shadow.Base({"calls": shadow.DIFF_CALLS_LIMIT + 1}, (), 0.0)
    found = shadow._compare_dependent(recording, big, {"calls": 10})
    assert (found.verdict, found.verdict_class) == (
        "oversize",
        shadow.VerdictClass.INFRASTRUCTURE,
    )
    base = shadow.Base({"calls": 10}, (), 0.0)
    monkeypatch.setattr(shadow, "_bundle_of", lambda *_a: (None, "timeout"))
    assert (
        shadow._compare_dependent(recording, base, {"calls": 10}).verdict == "timeout"
    )
    monkeypatch.setattr(
        shadow, "_bundle_of", lambda *_a: (shadow.bundle(recording), None)
    )
    recording.log.write_bytes(b"log")
    monkeypatch.setattr(shadow, "_diff", lambda *_a: (None, None))
    found = shadow._compare_dependent(recording, base, {"calls": 10})
    assert (found.verdict, found.reason) == ("timeout", "diff exceeded the budget")
    assert list(shadow.SCRATCH.iterdir()) == []


_SELECTED = "response:IModelDocExtension.SelectByID2"


def test_a_dependent_detour_the_seat_steered_keeps_its_own_geometry(
    blob, tmp_path, monkeypatch
):
    assert {
        kind.value: names for kind, names in shadow.GEOMETRY_SIGNALS.items()
    } == _com_outcome.GEOMETRY
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    recording = _planned(_drawing(tmp_path / "draw.py"), "k" * 64)
    recording.log.write_bytes(b"log")
    base = shadow.Base({"calls": 10}, (), 0.0)
    monkeypatch.setattr(
        shadow, "_bundle_of", lambda *_a: (shadow.bundle(recording), None)
    )
    budgets: list[float] = []

    def diff(pdf: str):
        def run(_work, _recording, _env, deadline):
            budgets.append(deadline - time.monotonic())
            return 0, {
                "request_divergence": {"index": 4},
                "truth_cause": _SELECTED,
                "outcome": "different",
                "outcome_signals": {
                    "requests": "different",
                    "answers": "different",
                    "pdf": pdf,
                },
                "seat_path": {"path": shadow.SEAT_PATH_DETOUR},
                "judge_faults": [],
            }

        return run

    monkeypatch.setattr(shadow, "_diff", diff("same"))
    found = shadow._compare_dependent(recording, base, {"calls": 10})
    assert (found.verdict, found.kind) == ("diverged", shadow.BuildKind.DRAWING)
    assert found.seat_path_detour and found.noop_judgement is None
    monkeypatch.setattr(shadow, "_diff", diff("different"))
    assert not shadow._compare_dependent(
        recording, base, {"calls": 10}
    ).seat_path_detour
    # The comparison holds a farm leaf's slot with the seat idle: a minute.
    assert all(0 < budget <= 60.0 for budget in budgets)
    # An assembly's geometry is its mass and sidecars, never a part's STL.
    assembly = shadow.Shadow(
        "diverged",
        ground_truth="diverged",
        truth_cause=_SELECTED,
        outcome="different",
        outcome_signals={"mass": "same", "stl": "same", "sidecars": "different"},
        seat_path={"path": shadow.SEAT_PATH_DETOUR},
        kind=shadow.BuildKind.ASSEMBLY,
    )
    assert not assembly.seat_path_detour


def test_a_dependent_record_names_its_seat_path_and_unreadable_children(
    blob, tmp_path, monkeypatch, logged
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    published = {"salt": "s", "recording_id": "fresh"}
    other = {"schema": shadow.MANIFEST_SCHEMA, "salt": "s", "kind": "drawing"}
    base = shadow.Base(
        {**other, "key": "b" * 64, "children": {_CHILD: "a" * 64}}, (), 0
    )

    def lookup(*_args: Any, usable: Any, **_kwargs: Any) -> shadow.LookupResult:
        found = base if usable({**base.manifest, "recording_id": "old"}) else None
        return shadow.LookupResult(shadow.Lookup.FOUND, found, 1, 1)

    detour = shadow.Shadow(
        "diverged",
        ground_truth="diverged",
        truth_cause=_SELECTED,
        outcome="different",
        outcome_signals={
            "requests": "different",
            "answers": "different",
            "pdf": "same",
        },
        seat_path={"path": shadow.SEAT_PATH_DETOUR},
        kind=shadow.BuildKind.DRAWING,
    )
    monkeypatch.setattr(shadow, "find_base", lookup)
    monkeypatch.setattr(shadow, "_compare_dependent", lambda *_a: detour)

    def judged(token: str) -> dict[str, Any]:
        recording = _planned(_drawing(tmp_path / "draw.py", token), "k" * 64)
        record: dict[str, Any] = {}
        shadow._judge_dependent(recording, {"engine": _ENGINE}, {}, published, record)
        return record

    record = judged("a" * 64)
    assert (record["split"], record["seat_path"]) == ("diverged", "detour")
    assert record["seat_path_divergence"] and not record["seat_nondeterminism"]
    assert record["children_unreadable"] is None and logged["warn"] == []
    assert shadow.report_line(f"drawing:{_STEM}", record).endswith(
        "| seat_path_divergence"
    )
    # A token the worker lacks: which child, and why, before anything else.
    record = judged("missing")
    assert (record["split"], record["same_children"]) == ("children_unknown", 0)
    assert record["children_unreadable"] == f"{_CHILD}: missing"
    assert len(logged["warn"]) == 1 and f"{_CHILD}: missing" in logged["warn"][0]
    assert shadow.report_line(f"drawing:{_STEM}", record).endswith(
        "| children_unreadable"
    )


def _run_dependent(recording: shadow.Recording, deps: list[str]) -> None:
    """The driver on the fake seat for this assembly or drawing recording (its
    outputs under the output root), then dodo's side: the exit, the store,
    the observation, which never writes an output."""
    command = recording.command[2:]
    at = command.index("--") if "--" in command else len(command)
    command[at:at] = ["--out-root", str(shadow.OUT_ROOT)]
    proc = subprocess.run(
        [sys.executable, "-c", DEPENDENT_DRIVER, *command],
        cwd=SCRIPTS,
        env=dict(os.environ, OTEL_EXPORTER_OTLP_ENDPOINT=""),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not recording.exited(proc.returncode)
    built = _outputs(shadow.OUT_ROOT)
    _stored(recording.key)
    shadow.after_build(recording, deps, _digest)
    assert _outputs(shadow.OUT_ROOT) == built


def test_a_drawing_is_judged_against_the_nearest_base_on_its_children(
    blob, tmp_path, monkeypatch, spans, logged
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    source = tmp_path / "src"
    source.mkdir()
    script = source / f"draw_{_STEM}.py"
    script.write_text(DRAWING_SCRIPT, encoding="utf-8")
    settings = source / "drawing.json"
    token = source / ".sh-widget.execution"  # the drawn model's identity
    deps = [str(script), str(settings), str(token)]
    drawing_outputs(shadow.OUT_ROOT)

    def build(line: int, note: str, identity: str) -> tuple[Any, dict[str, Any]]:
        settings.write_text(json.dumps({"line": line, "note": note}), "utf-8")
        token.write_text(identity + "\n", encoding="utf-8")
        dependent = shadow.Dependent(
            shadow.BuildKind.DRAWING,
            _STEM,
            script,
            (_STEM,),
            {cache._rel(token): identity},
        )
        recording = _planned(dependent, cache.key_inputs(deps, _digest)[0])
        _run_dependent(recording, deps)
        return recording, _events(tmp_path, "replay_shadow")[-1]

    first, record = build(100, "a", "a" * 64)
    assert (record["outcome"], record["lookup"], record["candidates"]) == (
        "no_base",
        "none",
        0,
    )
    # An own-source change SolidWorks never sees: a no-op on the same model,
    # the same sheet although the PDF's bytes differ.
    second, record = build(100, "b", "a" * 64)
    assert record["outcome"] == "evaluated", record
    assert (record["split"], record["ground_truth"], record["artefact_outcome"]) == (
        "noop",
        "same",
        "same",
    ), record
    assert record["outcome_signals"] == "answers:same,pdf:same,requests:same"
    assert (record["candidates"], record["same_children"]) == (1, 1)
    assert record["base_key"] == first.key
    assert (
        record["differing"] == [cache._rel(settings)] and record["own_differing"] == 1
    )
    assert record["noop_judgement"] == "confirmed" and not record["soundness_alarm"]
    line = [m for m in logged["info"] if m.startswith(f"[com-replay] {second.label}")][
        -1
    ]
    assert " | split=noop same_children=1/1 " in line and " | record=+" in line
    assert " | truth=same | outcome=same cause=- | " in line and "\n" not in line
    engine = json.loads(second.summary_path.read_text("utf-8"))["engine"]
    _, manifest_name = shadow.blob_names(engine, second.name, second.key)
    published = json.loads(cache.fetch_sidecar(manifest_name))
    assert (published["kind"], published["argv"]) == ("drawing", [_STEM])
    assert published["children"] == {cache._rel(token): "a" * 64}
    assert published["replay_gaps"]["out_inputs"]["first"] == [
        "sldprt/sh-widget.SLDPRT"
    ]
    # A change SolidWorks sees: the source asked something else, another sheet.
    third, record = build(120, "b", "a" * 64)
    assert (record["split"], record["truth_cause"], record["artefact_outcome"]) == (
        "diverged",
        "request",
        "different",
    ), record
    assert "pdf:different" in record["outcome_signals"]
    assert (record["candidates"], record["same_children"]) == (2, 2)
    assert record["base_key"] == second.key and not record["seat_nondeterminism"]
    # Another model: no earlier recording was made on it.
    _, record = build(120, "b", "c" * 64)
    assert (record["split"], record["candidates"], record["same_children"]) == (
        "children_changed",
        3,
        0,
    )
    assert "base_key" not in record and record["outcome"] == "evaluated"
    assert [s["replay.split"] for s in spans.named("replay.split ")] == [
        "noop",
        "diverged",
        "children_changed",
    ]
    assert list(shadow.SCRATCH.iterdir()) == []
    assert logged["error"] == []


_ASSEMBLY_SCRIPT = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "import _paths\n"
    "from _session import run_build\n"
    "import test_com_conversation  # noqa: F401 -- the fake seat's interfaces\n"
    "async def build(adapter):\n"
    "    out = _paths.OUT_SLDPRT.parent\n"
    "    settings = json.loads((Path(__file__).parent / 'assembly.json').read_text())\n"
    "    app = adapter.swApp\n"
    "    if not app.Open(str(out / 'sldprt' / 'sh-widget.SLDPRT')):\n"
    "        raise RuntimeError('the part is missing')\n"
    "    total = app.Add(1.5, 2.25)\n"
    "    app.SaveTo(str(out / 'sldasm' / 'sh-widget.SLDASM'))\n"
    "    proof = out / 'sldasm' / '.sh-widget.massprops.sha'\n"
    "    proof.write_text(f\"{total.hex()} {settings['proof']}\\n\", encoding='utf-8')\n"
    "    return {}\n"
    "if __name__ == '__main__':\n"
    "    sys.exit(run_build(build))\n"
)


def test_an_assembly_noop_whose_sidecar_differs_is_a_soundness_alarm(
    blob, tmp_path, monkeypatch, spans, logged
):
    monkeypatch.setenv(shadow.MODE_ENV, "shadow")
    source = tmp_path / "src"
    source.mkdir()
    script = source / f"build_{_STEM}_assembly.py"
    script.write_text(_ASSEMBLY_SCRIPT, encoding="utf-8")
    settings = source / "assembly.json"
    deps = [str(script), str(settings)]
    drawing_outputs(shadow.OUT_ROOT)
    proof = shadow.OUT_ROOT / "sldasm" / ".sh-widget.massprops.sha"

    def build(written: str, note: str) -> dict[str, Any]:
        settings.write_text(json.dumps({"proof": written, "note": note}), "utf-8")
        dependent = shadow.Dependent(
            shadow.BuildKind.ASSEMBLY, _STEM, script, (), {_CHILD: "a" * 64}, (proof,)
        )
        recording = _planned(dependent, cache.key_inputs(deps, _digest)[0])
        _run_dependent(recording, deps)
        return _events(tmp_path, "replay_shadow")[-1]

    assert build("x", "a")["outcome"] == "no_base"
    record = build("x", "b")
    # The fake measures no mass property: a no-op it can neither confirm nor
    # contradict, its proof the same.
    assert (record["split"], record["artefact_outcome"]) == ("noop", "unknown"), record
    assert record["outcome_signals"] == (
        "answers:same,mass:absent,requests:same,sidecars:same"
    )
    assert record["noop_outcome_unknown"] and logged["error"] == []
    # The same requests, a proof Python wrote differently: another assembly.
    record = build("y", "b")
    assert (record["split"], record["artefact_outcome"]) == ("noop", "different")
    assert "sidecars:different" in record["outcome_signals"]
    assert record["soundness_alarm"] and record["outcome"] == "evaluated"
    [alarm] = logged["error"]
    assert alarm.startswith(f"[com-replay] SOUNDNESS ALARM assembly:{_STEM}: ")
    # Nothing of it is ever reused, so nothing is revoked.
    assert not [name for name in blob.committed if "/revoked/" in name]
