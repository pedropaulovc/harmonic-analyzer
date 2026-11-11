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
import json
import os
import re
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
import _replay_shadow as shadow  # noqa: E402
import _telemetry  # noqa: E402
from test_artifact_cache import _BlockBlobService  # noqa: E402
from test_com_conversation import _RECORD_DRIVER  # noqa: E402

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
    """A part build that ran under the driver: its recording directory holds
    a log, a capture and the summary (``plan`` under the current mode)."""
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
        (None, shadow.ReplayMode.SHADOW),
        ("", shadow.ReplayMode.SHADOW),
        ("off", shadow.ReplayMode.OFF),
        ("record", shadow.ReplayMode.RECORD),
        (" Shadow ", shadow.ReplayMode.SHADOW),
    ],
)
def test_mode_is_one_variable_defaulting_to_shadow(
    monkeypatch, logged, value, expected
):
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
        # No comparison at all: a noop nothing confirms.
        (0, _NOOP, None, "noop", "unknown", "noop", "unknown"),
        (91, _DIVERGED, _DIFFERENT, "diverged", "diverged", "divergence", ""),
        (91, _DIVERGED, _REORDERED, "diverged", "diverged", "divergence", ""),
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
    assert {
        "alarm": result.soundness_alarm,
        "seat": result.seat_nondeterminism,
        "unknown": result.noop_outcome_unknown,
        "false": result.false_divergence,
    } == {name: name == flags for name in ("alarm", "seat", "unknown", "false")}


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
    divergence = {"index": 7, "field": "args", "detail": "x" * 10_000}

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
    assert record["base_key"] == base.key and record["differing_count"] == 1
    assert record["differing_classes"] == {"other": 1}
    assert len(record["alarm_evidence"]) == shadow.EVIDENCE_CHARS
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


# The hourly fleet report's parser of the INFO line.
_REPORT_LINE = re.compile(r"shadow=(\S+) served=(\S+).*?truth=(\S+)")


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
            {"ground_truth": "same", "outcome": "unknown"},
            "noop_outcome_unknown",
            "| truth=same | outcome=unknown cause=- | noop_outcome_unknown",
        ),
    ],
)
def test_a_noop_the_outcome_does_not_contradict_is_counted_never_an_alarm(
    blob, tmp_path, monkeypatch, spans, logged, found, marker, line_end
):
    def evaluate(recording, base, summary):
        return shadow.Shadow("noop", recorded=10, served=10, **found)

    monkeypatch.setattr(shadow, "evaluate", evaluate)
    _two_builds(tmp_path, monkeypatch)
    assert logged["error"] == []
    record = _events(tmp_path, "replay_shadow")[-1]
    flags = ("soundness_alarm", "seat_nondeterminism", "noop_outcome_unknown")
    assert {name: record[name] for name in flags} == {
        name: name == marker for name in flags
    }
    [span] = spans.named("replay.shadow ")
    assert span[f"replay.{marker}"] is True and span["replay.soundness_alarm"] is False
    line = logged["info"][-1]
    assert line.endswith(line_end)
    assert _REPORT_LINE.search(line).groups() == (
        "noop",
        "10/10",
        found["ground_truth"],
    )


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
# _drawing_precision._named_dimensions and
# _supplier_spring_reference.add_supplier_reference_configurations do.
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
