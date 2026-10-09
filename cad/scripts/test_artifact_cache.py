r"""Tests for the artefact-cache provenance/observability surface (issue #73).

Pure python, NO SolidWorks and NO Azure -- the backend is faked in-memory and the
on-disk sinks (cache.jsonl, the per-label key sidecar) are redirected to a tmp dir.

    python cad/scripts/test_artifact_cache.py     # or: pytest cad/scripts/test_artifact_cache.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _artifact_cache as cache  # noqa: E402
import _telemetry  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures: a fake backend + tmp-redirected sinks, so nothing touches Azure or
# the real cad/out/reports/.
# --------------------------------------------------------------------------- #
class _FakeBackend:
    """In-memory stand-in for _BlobBackend: key -> packed bytes."""

    def __init__(self):
        self.blobs: dict[str, bytes] = {}

    def get(self, key):
        return self.blobs.get(key)

    def put(self, key, blob):
        self.blobs[key] = blob

    def exists(self, key):
        return key in self.blobs


@pytest.fixture
def real_unpack():
    return cache._unpack


@pytest.fixture
def fake(tmp_path, monkeypatch, real_unpack):
    """rw cache on a LOCAL-executor seat, wired to an in-memory backend with all
    sinks under tmp_path -- i.e. the role that both builds and publishes, so a HIT
    under an unpublished key is real drift. _unpack is a no-op (we test
    event/drift bookkeeping, not tar extraction)."""
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.delenv("HARMONIC_CACHE_DEBUG", raising=False)
    monkeypatch.setattr(cache, "_REPORTS", tmp_path)
    monkeypatch.setattr(cache, "_EVENTS_LOG", tmp_path / "cache.jsonl")
    monkeypatch.setattr(cache, "_KEYDIR", tmp_path / "cache-keys")
    monkeypatch.setattr(cache, "_unpack", lambda blob: None)
    monkeypatch.setattr(cache, "_KEY_INPUTS", {})
    monkeypatch.setattr(cache, "_KEY_CONTEXT", {})
    backend = _FakeBackend()
    monkeypatch.setattr(cache, "_BACKEND", backend)
    return backend


def _digest_one(path):
    """Stand-in for ContentChecker._digest: hash the file's text; missing -> OSError
    (exactly the contract cache_key/key_inputs rely on to mark a dep <missing>)."""
    return Path(path).read_text(encoding="utf-8")


def _events(tmp):
    log = tmp / "cache.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def _make_dep(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# --------------------------------------------------------------------------- #
# Key derivation + provenance
# --------------------------------------------------------------------------- #
def test_cache_key_is_deterministic_and_label_inert(tmp_path):
    a = _make_dep(tmp_path, "a.txt", "alpha")
    b = _make_dep(tmp_path, "b.txt", "beta")
    k1 = cache.cache_key([a, b], _digest_one)
    k2 = cache.cache_key([b, a], _digest_one, label="part:x")  # order + label irrelevant
    assert k1 == k2
    # A content change must move the key.
    Path(a).write_text("ALPHA", encoding="utf-8")
    assert cache.cache_key([a, b], _digest_one) != k1


def test_key_inputs_sorted_with_missing_marker(tmp_path):
    present = _make_dep(tmp_path, "z.txt", "z")
    missing = str(tmp_path / "gone.txt")
    key, inputs = cache.key_inputs([present, missing], _digest_one)
    rels = [rel for rel, _ in inputs]
    assert rels == sorted(rels)
    digests = dict(inputs)
    assert digests["gone.txt"] == "<missing>"
    assert key == cache.cache_key([present, missing], _digest_one)


def test_debug_logs_provenance_without_changing_key(tmp_path, monkeypatch):
    records: list[str] = []
    monkeypatch.setattr(_telemetry, "info", lambda message, **_: records.append(message))
    monkeypatch.setenv("HARMONIC_CACHE_DEBUG", "1")
    a = _make_dep(tmp_path, "a.txt", "alpha")
    key = cache.cache_key([a], _digest_one, label="part:x")
    logged = "\n".join(records)
    assert "key provenance part:x" in logged
    assert "a.txt" in logged and key in logged
    # Same inputs, debug off -> identical key (logging is side-effect only).
    monkeypatch.delenv("HARMONIC_CACHE_DEBUG")
    assert cache.cache_key([a], _digest_one) == key


# --------------------------------------------------------------------------- #
# Event log + store/restore round-trip
# --------------------------------------------------------------------------- #
def test_store_then_restore_logs_events_and_stamps_key(tmp_path, fake):
    out = tmp_path / "out.bin"
    out.write_text("payload", encoding="utf-8")
    key = "k" * 64

    cache.store(key, [out], "part:x")
    assert key in fake.blobs                                  # published
    assert cache.last_stored_key("part:x") == key            # sidecar stamped

    assert cache.restore(key, [out], "part:x") is True        # HIT
    events = [e["event"] for e in _events(tmp_path)]
    assert events == ["store", "restore_hit"]
    assert all(e["key"] == key for e in _events(tmp_path))


def test_store_retains_last_published_input_provenance(tmp_path, fake):
    """Issue #255: after the working tree moves to a new key, the old per-dep
    digests must remain available beside the last published key for a readable
    historical diff."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    out = tmp_path / "out.bin"
    out.write_text("payload", encoding="utf-8")
    cache.store(key, [out], "part:x")

    assert cache.last_stored_key("part:x") == key
    assert cache.last_stored_inputs("part:x") == [("input.py", "VALUE = 1\n")]

    Path(dep).write_text("VALUE = 2\n", encoding="utf-8")
    cache.cache_key([dep], _digest_one, label="part:x")
    assert cache.last_stored_inputs("part:x") == [("input.py", "VALUE = 1\n")]


def test_restore_miss_logs_event_at_debug(tmp_path, fake, monkeypatch):
    records: list[tuple[str, str]] = []
    monkeypatch.setattr(
        _telemetry, "debug", lambda message, **_: records.append(("debug", message))
    )
    monkeypatch.setattr(
        _telemetry, "warn", lambda message, **_: records.append(("warning", message))
    )
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    assert cache.restore(key, [], "part:x") is False
    assert records == [("debug", f"[cache] miss  part:x ({key[:12]}) -> building locally")]
    events = _events(tmp_path)
    assert [e["event"] for e in events] == ["restore_miss"]
    assert events[0]["inputs"] == [{"path": "input.py", "digest": "VALUE = 1\n"}]


def test_restore_hit_over_a_share_locked_output_raises_instead_of_falling_through(
    tmp_path, fake, monkeypatch
):
    """The one restore failure that must not become "building locally": a cached
    build exists but SolidWorks still holds the output (Windows share lock), and
    a local rebuild would mint a token the fleet cannot reproduce."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    fake.blobs[key] = b"payload"

    def refuse(_blob):
        raise PermissionError(13, "Permission denied", "cad/out/sldprt/x.SLDPRT")

    monkeypatch.setattr(cache, "_unpack", refuse)

    with pytest.raises(cache.RestoreLocked, match="share-locked") as info:
        cache.restore(key, [], "part:x")

    assert info.value.key == key
    assert [e["event"] for e in _events(tmp_path)] == ["restore_locked"]


def test_restore_other_unpack_errors_still_fall_through(tmp_path, fake, monkeypatch):
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    fake.blobs[key] = b"payload"
    monkeypatch.setattr(
        cache, "_unpack", lambda _blob: (_ for _ in ()).throw(OSError("disk full"))
    )

    assert cache.restore(key, [], "part:x") is False
    assert [e["event"] for e in _events(tmp_path)] == ["restore_error"]


def test_miss_retains_previous_and_current_inputs(tmp_path, fake):
    """Once a rebuild publishes the new key, its sidecar advances; the miss event
    must therefore preserve both sides of the drift for later diagnosis."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    old_key = cache.cache_key([dep], _digest_one, label="part:x")
    out = tmp_path / "out.bin"
    out.write_text("payload", encoding="utf-8")
    cache.store(old_key, [out], "part:x")

    Path(dep).write_text("VALUE = 2\n", encoding="utf-8")
    new_key = cache.cache_key([dep], _digest_one, label="part:x")
    assert cache.restore(new_key, [], "part:x") is False
    event = _events(tmp_path)[-1]
    assert event["previous_key"] == old_key
    assert event["previous_inputs"] == [{"path": "input.py", "digest": "VALUE = 1\n"}]
    assert event["inputs"] == [{"path": "input.py", "digest": "VALUE = 2\n"}]


def test_store_nothing_on_disk_logs_empty(tmp_path, fake):
    cache.store("k" * 64, [tmp_path / "absent.bin"], "part:x")
    assert [e["event"] for e in _events(tmp_path)] == ["store_empty"]
    assert cache.last_stored_key("part:x") is None            # nothing published


def _telemetry_logger(caplog, monkeypatch):
    """The telemetry logger, wired so caplog sees its records."""
    logger = _telemetry.get_logger()
    monkeypatch.setattr(logger, "propagate", True)
    caplog.clear()
    return logger


def _records(caplog, logger, level):
    return [r.getMessage() for r in caplog.records
            if r.name == logger.name and r.levelno == level]


# --------------------------------------------------------------------------- #
# THE issue-#73 case: store-skip-on-hit drift is surfaced on a HIT -- loudly for
# a seat that publishes what it builds, quietly (but still recorded) for one that
# structurally cannot have published the key it hit.
# --------------------------------------------------------------------------- #
def test_hit_under_new_key_warns_drift(tmp_path, fake, caplog, monkeypatch):
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    k_old = "1" * 64
    k_new = "2" * 64

    cache.store(k_old, [out], "part:x")          # this seat publishes k_old
    fake.blobs[k_new] = b"built-elsewhere"        # another seat publishes k_new
    logger = _telemetry_logger(caplog, monkeypatch)

    with caplog.at_level(logging.WARNING, logger=logger.name):
        assert cache.restore(k_new, [out], "part:x") is True
    assert _records(caplog, logger, logging.WARNING)
    event = _events(tmp_path)[-1]
    assert event["event"] == "restore_hit_drift"
    assert event["label"] == "part:x"
    assert event["key"] == k_new
    assert event["previous_key"] == k_old
    assert event["drift_expected"] is False
    # A HIT does NOT re-stamp the sidecar -- the seat still only ever published k_old.
    assert cache.last_stored_key("part:x") == k_old


def test_farm_submitter_hit_on_worker_published_key_does_not_warn(
    tmp_path, fake, caplog, monkeypatch
):
    """Under ``--executor farm`` the submitter dispatches every cache-missing leaf
    and never reaches ``store``, so EVERY hit is under a key the worker published.
    Warning there fires on the correct path and trains the operator to ignore the
    signal -- it must stay off the console while cache.jsonl keeps the event."""
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    k_old = "1" * 64
    k_new = "2" * 64

    cache.store(k_old, [out], "part:x")          # published back when it built locally
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    fake.blobs[k_new] = b"built-by-a-worker"
    logger = _telemetry_logger(caplog, monkeypatch)

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        assert cache.restore(k_new, [out], "part:x") is True
    assert _records(caplog, logger, logging.WARNING) == []
    assert any("expected" in msg for msg in _records(caplog, logger, logging.DEBUG))
    event = _events(tmp_path)[-1]
    assert event["event"] == "restore_hit_drift"      # the record stays complete
    assert event["previous_key"] == k_old
    assert event["drift_expected"] is True
    assert event["drift_reason"] == "executor=farm"


def test_read_only_seat_hit_on_foreign_key_does_not_warn(
    tmp_path, fake, caplog, monkeypatch
):
    """Same reasoning by role rather than executor: a ``ro`` seat declines to
    publish, so it cannot have stored the key it hits."""
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    k_old = "1" * 64
    k_new = "2" * 64

    cache.store(k_old, [out], "part:x")          # published while still rw
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "ro")
    fake.blobs[k_new] = b"built-elsewhere"
    logger = _telemetry_logger(caplog, monkeypatch)

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        assert cache.restore(k_new, [out], "part:x") is True
    assert _records(caplog, logger, logging.WARNING) == []
    event = _events(tmp_path)[-1]
    assert event["drift_expected"] is True
    assert event["drift_reason"] == "cache_mode=ro"


def test_drift_bookkeeping_failure_cannot_demote_a_hit(tmp_path, fake, monkeypatch):
    """The severity decision runs AFTER the outputs are on disk (it reads the
    sidecar and imports `_farm`). If it raises, the HIT must still stand: falling
    through to "building locally" would mint a fresh .execution token and fork
    every dependent's cache key off the fleet's."""
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    k_old = "1" * 64
    k_new = "2" * 64

    cache.store(k_old, [out], "part:x")
    fake.blobs[k_new] = b"built-elsewhere"

    def boom():
        raise ModuleNotFoundError("No module named '_farm'")

    monkeypatch.setattr(cache, "_cannot_publish_reason", boom)

    assert cache.restore(k_new, [out], "part:x") is True
    assert "restore_error" not in [e["event"] for e in _events(tmp_path)]


def test_hit_under_same_key_is_not_drift(tmp_path, fake):
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    key = "3" * 64
    cache.store(key, [out], "part:x")
    assert cache.restore(key, [out], "part:x") is True
    assert [e["event"] for e in _events(tmp_path)][-1] == "restore_hit"


# --------------------------------------------------------------------------- #
# Mode gating: off writes nothing; ro pulls but records a publish-skip
# --------------------------------------------------------------------------- #
def test_mode_off_is_silent(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    assert cache.restore("k" * 64, [], "part:x") is False
    cache.store("k" * 64, [tmp_path / "out.bin"], "part:x")
    assert _events(tmp_path) == []                            # no jsonl on a disabled seat


def test_mode_ro_records_store_skip(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "ro")
    cache.store("k" * 64, [tmp_path / "out.bin"], "part:x")
    assert [e["event"] for e in _events(tmp_path)] == ["store_skip"]


def test_probe_presence_and_disabled(tmp_path, fake, monkeypatch):
    key = "p" * 64
    fake.blobs[key] = b"x"
    assert cache.probe(key) is True
    assert cache.probe("q" * 64) is False
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    assert cache.probe(key) is None                          # disabled -> unknown


# --------------------------------------------------------------------------- #
# Publish atomicity -- the blob backend against Azure block-blob semantics
# --------------------------------------------------------------------------- #
class _BlockBlobService:
    """One container's block blobs, with the service rules a chunked publish
    relies on: staged blocks are private to the blob until a commit; a commit
    resolves each listed ID to its uncommitted block, else its committed one
    (the SDK's ``latest``); and a commit garbage-collects every uncommitted
    block it did not list."""

    def __init__(self):
        self.committed: dict[str, list[tuple[str, bytes]]] = {}
        self.uncommitted: dict[str, dict[str, bytes]] = {}
        self.on_stage = None

    def get_blob_client(self, name):
        service = self

        class _Client:
            def upload_blob(self, data, overwrite):
                assert overwrite
                service.committed[name] = [("single", bytes(data))]
                service.uncommitted.pop(name, None)

            def stage_block(self, block_id, data):
                service.uncommitted.setdefault(name, {})[block_id] = bytes(data)
                if service.on_stage is not None:
                    service.on_stage()

            def commit_block_list(self, blocks):
                staged = service.uncommitted.get(name, {})
                old = dict(service.committed.get(name, []))
                resolved = []
                for block in blocks:
                    if block.id in staged:
                        resolved.append((block.id, staged[block.id]))
                    elif block.id in old:
                        resolved.append((block.id, old[block.id]))
                    else:
                        raise RuntimeError(f"InvalidBlockList: {block.id}")
                service.committed[name] = resolved
                service.uncommitted.pop(name, None)

        return _Client()

    def content(self, name):
        return b"".join(data for _, data in self.committed[name])


def test_interleaved_chunked_publishes_never_commit_a_torn_archive(monkeypatch):
    """Two writers of one key upload different bytes (tar mtimes, gzip level).
    If writer B publishes while writer A is between its first and second staged
    block, the stored entry must be one writer's archive whole -- never B's
    first block followed by A's tail (a CRC failure on every later restore)."""
    monkeypatch.setattr(cache, "_SINGLE_PUT_MAX", 8)
    monkeypatch.setattr(cache, "_BLOCK_SIZE", 4)
    monkeypatch.setattr(cache, "_TRANSFER_CONCURRENCY", 1)  # deterministic order
    service = _BlockBlobService()
    backend = cache._BlobBackend(service)
    key = "c" * 64
    first, second = b"A" * 16, b"B" * 16

    def competing_publish():
        service.on_stage = None
        backend.put(key, second)

    service.on_stage = competing_publish
    try:
        backend.put(key, first)
    except RuntimeError:
        pass  # losing the race is a store_error, which store() swallows

    assert service.content(backend._name(key)) in (first, second)


_LEAF_RESOURCE = "microsoft.applicationId=app,farm.worker=w@1,farm.execution=wf/run/1"


@pytest.fixture
def leaf(monkeypatch):
    """A farm leaf execution in rw mode, with prewarm state isolated per test and
    its exit hook captured instead of registered with the interpreter."""
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", _LEAF_RESOURCE)
    monkeypatch.setattr(cache, "_BACKEND", cache._UNSET)
    monkeypatch.setattr(cache, "_PREWARMED", None)
    exits: list[tuple] = []
    monkeypatch.setattr(cache.atexit, "register", lambda *args: exits.append(args))
    return exits


def _gated_backend():
    """A fake whose prewarm HEAD blocks until released, recording the order."""
    import threading

    backend = _FakeBackend()
    order: list[str] = []
    release = threading.Event()

    def head(key):
        order.append(f"head {key}")
        release.wait(5)
        order.append("head done")
        return False

    backend.exists = head
    return backend, order, release


def test_prewarm_opens_the_connection_once_and_the_probe_reuses_it(leaf, monkeypatch):
    """A probe that arrives while the prewarm's HEAD is still in flight waits for
    that request, so it reuses the connection it opens -- rather than racing it
    with a second cold TLS handshake -- and the client is built exactly once."""
    import threading

    backend, order, release = _gated_backend()
    built: list[int] = []
    monkeypatch.setattr(cache, "_make_backend", lambda: built.append(1) or backend)
    warm = cache.prewarm()
    assert warm is not None
    while "head prewarm" not in order:  # client built, HEAD in flight
        threading.Event().wait(0.01)

    threading.Timer(0.2, release.set).start()
    assert cache._backend() is backend
    order.append("probe")
    warm.join(5)
    assert order == ["head prewarm", "head done", "probe"]
    assert built == [1]
    assert [args[0] for args in leaf] == [cache._join_prewarm]


def test_a_stalled_prewarm_delays_the_probe_only_by_its_bound(leaf, monkeypatch):
    """The cache verdict never depends on the prewarm: a HEAD that hangs costs the
    first real call at most ``_PREWARM_WAIT_S``, after which it proceeds."""
    import time

    backend, order, release = _gated_backend()
    monkeypatch.setattr(cache, "_make_backend", lambda: backend)
    monkeypatch.setattr(cache, "_PREWARM_WAIT_S", 0.2)
    warm = cache.prewarm()
    try:
        while "head prewarm" not in order:
            time.sleep(0.01)
        started = time.monotonic()
        assert cache._backend() is backend
        assert time.monotonic() - started < 2
        assert "head done" not in order
    finally:
        release.set()
        warm.join(5)


def test_a_stalled_prewarm_holds_interpreter_exit_only_by_its_bound(leaf, monkeypatch):
    """The exit hook joins so the prewarm's spans end before telemetry closes its
    exporters -- but a hung prewarm must not hold the leaf's exit hostage."""
    import time

    backend, order, release = _gated_backend()
    monkeypatch.setattr(cache, "_make_backend", lambda: backend)
    monkeypatch.setattr(cache, "_PREWARM_JOIN_S", 0.2)
    warm = cache.prewarm()
    try:
        (hook, thread), = leaf
        started = time.monotonic()
        hook(thread)
        assert time.monotonic() - started < 2
        assert warm.is_alive()
    finally:
        release.set()
        warm.join(5)


@pytest.mark.parametrize("failure", ["none", "raises"])
def test_a_failed_prewarm_never_turns_the_cache_off(leaf, monkeypatch, failure):
    """Only the real call may memoize 'no backend': a prewarm whose client cannot
    be built leaves the backend unset, so the probe builds (and reports) its own."""
    attempts: list[str] = []

    def speculative_failure():
        attempts.append("prewarm")
        if failure == "raises":
            raise RuntimeError("constructor failed")
        return None

    monkeypatch.setattr(cache, "_make_backend", speculative_failure)
    cache.prewarm().join(5)
    assert isinstance(cache._BACKEND, cache._Unset)

    backend = _FakeBackend()
    monkeypatch.setattr(cache, "_make_backend", lambda: attempts.append("probe") or backend)
    assert cache._backend() is backend
    assert attempts == ["prewarm", "probe"]


@pytest.mark.parametrize(
    ("mode", "resource"),
    [
        ("rw", "microsoft.applicationId=app"),  # a developer seat / check gate
        ("rw", "farm.executionx=1,farm.execution.id=2"),  # exact key only
        ("rw", "farm.execution="),  # declared but empty
        ("ro", _LEAF_RESOURCE),  # an export-role helper: never publishes
        ("off", _LEAF_RESOURCE),
    ],
)
def test_prewarm_runs_only_in_a_publishing_farm_leaf(leaf, monkeypatch, mode, resource):
    """Every other graph load -- ``doit list``, ``check:*``, the submitter, tests
    that load dodo -- must stay off Azure."""
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", mode)
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", resource)
    monkeypatch.setattr(
        cache, "_make_backend", lambda: pytest.fail("a non-leaf process connected")
    )
    assert cache.prewarm() is None
    assert cache._PREWARMED is None
    assert leaf == []


def test_a_thread_that_cannot_start_is_no_prewarm(leaf, monkeypatch):
    """``Thread.start`` runs at dodo import: its RuntimeError must not abort doit,
    and must not leave the first probe waiting on a warm-up that never began."""
    import threading

    def refuse(self):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(threading.Thread, "start", refuse)
    monkeypatch.setattr(cache, "_PREWARM_WAIT_S", 30)
    assert cache.prewarm() is None
    assert cache._PREWARMED.is_set()
    assert leaf == []


@pytest.fixture
def exported_cache_spans(monkeypatch):
    """Real SDK + in-memory exporter, not a mocked telemetry event echo."""
    from opentelemetry.sdk.trace import SpanLimits, TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    providers = []

    def make(**limits):
        if "max_attribute_length" in limits:
            monkeypatch.setenv("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT", str(limits["max_attribute_length"]))
        exporter = InMemorySpanExporter()
        provider = TracerProvider(
            span_limits=SpanLimits(**limits), shutdown_on_exit=False
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        providers.append(provider)
        tracer = provider.get_tracer("cache-test")
        monkeypatch.setattr(_telemetry, "get_tracer", lambda **kwargs: tracer)
        log_exporter = InMemoryLogRecordExporter()
        log_provider = LoggerProvider(
            resource=Resource.create({"service.name": _telemetry.BUILD_INFRA_SERVICE}),
            shutdown_on_exit=False,
        )
        log_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
        providers.append(log_provider)
        logger = logging.Logger("cache-test", level=logging.DEBUG)
        logger.addHandler(_telemetry._ResourceRoutedLoggingHandler(logger_provider=log_provider))
        monkeypatch.setattr(_telemetry, "get_logger", lambda: logger)
        monkeypatch.setattr(_telemetry, "_logger_provider_for_service", lambda service: log_provider)
        exporter.cache_logs = log_exporter
        return tracer, exporter

    yield make
    for provider in providers:
        provider.shutdown()


def _wire_events(exporter):
    """Read consumer-visible attributes after actual OTLP protobuf roundtrip."""
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    from opentelemetry.exporter.otlp.proto.common._log_encoder import encode_logs

    request = encode_spans(exporter.get_finished_spans())
    received = type(request).FromString(request.SerializeToString())
    events = [
        (event.name, {
            item.key: getattr(item.value, item.value.WhichOneof("value"))
            for item in event.attributes
        })
        for resource in received.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
        for event in span.events
    ]
    request = encode_logs(exporter.cache_logs.get_finished_logs())
    received = type(request).FromString(request.SerializeToString())
    events.extend(
        (record.body.string_value, {
            item.key: getattr(item.value, item.value.WhichOneof("value"))
            for item in record.attributes
        })
        for resource in received.resource_logs
        for scope in resource.scope_logs
        for record in scope.log_records
    )
    return events


def _received_recipe(events, outcome):
    """Independent consumer: fail closed on omission, truncation or unknown recipe."""
    decisions = [attrs for name, attrs in events if name == outcome]
    if len(decisions) != 1:
        return None
    decision = decisions[0]
    if not decision.get("manifest_complete"):
        return None
    chunks = {}
    for name, attrs in events:
        if name == "cache.provenance" and attrs.get("manifest_id") == decision["manifest_id"]:
            index, fragment = attrs["chunk_index"], attrs["chunk"]
            if index in chunks and chunks[index] != fragment:
                return None
            chunks[index] = fragment
    count = decision["manifest_chunk_count"]
    if set(chunks) != set(range(count)) or decision["manifest_emitted_chunks"] != count:
        return None
    payload = "".join(chunks[index] for index in range(count))
    if len(payload) != decision["manifest_chars"]:
        return None
    if hashlib.sha256(payload.encode("ascii")).hexdigest() != decision["manifest_id"]:
        return None
    recipe = json.loads(payload)
    if not recipe["recipe_known"]:
        return None
    if len(recipe["inputs"]) != recipe["input_count"] or recipe["input_count"] != decision["manifest_input_count"]:
        return None
    return recipe


@pytest.mark.parametrize("outcome", ["cache.miss", "cache.store", "cache.hit"])
def test_remote_recipe_survives_disposable_seat_without_sidecars(
    tmp_path, fake, monkeypatch, exported_cache_spans, outcome
):
    dep = _make_dep(tmp_path, "entrée.py", "source digest")
    monkeypatch.setenv("HARMONIC_CACHE_SALT", "salt-at-key-time")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    # Salt is recipe provenance, not the later environment at restore/store time.
    monkeypatch.setenv("HARMONIC_CACHE_SALT", "later-salt")
    out = tmp_path / "out.bin"
    out.write_bytes(b"payload")
    if outcome == "cache.hit":
        fake.blobs[key] = b"built-on-another-seat"
    tracer, exporter = exported_cache_spans(max_attribute_length=8192)
    with tracer.start_as_current_span("disposable-build"):
        if outcome == "cache.store":
            assert cache.store(key, [out], "part:x") == "stored"
        else:
            assert cache.restore(key, [out], "part:x") is (outcome == "cache.hit")

    events = _wire_events(exporter)
    recipe = _received_recipe(events, outcome)
    assert recipe == {
        "schema": 1, "key": key, "epoch": cache._CACHE_EPOCH,
        "salt": "salt-at-key-time", "recipe_known": True, "input_count": 1,
        "inputs": [{"path": "entrée.py", "digest": "source digest"}],
    }
    decision = next(attrs for name, attrs in events if name == outcome)
    assert decision["key"] == key[:12] and decision["key_full"] == key
    local = _events(tmp_path)[-1]
    assert {field: local[field] for field in recipe} == recipe
    assert local["manifest_id"] == decision["manifest_id"]
    # An independent re-derivation from the wire recipe verifies actual full key.
    h = hashlib.sha256()
    h.update(f"epoch={recipe['epoch']}\0salt={recipe['salt']}\0".encode())
    for item in recipe["inputs"]:
        h.update(f"{item['path']}\0{item['digest']}\0".encode())
    assert h.hexdigest() == recipe["key"]


@pytest.mark.parametrize("payload_chars", [5999, 6000, 6001, 12000, 12001])
def test_remote_manifest_exact_chunk_boundaries(
    tmp_path, fake, monkeypatch, exported_cache_spans, payload_chars
):
    # An empty dependency set is known, unlike an arbitrary key with no recipe.
    expected = {
        "schema": 1, "key": "0" * 64, "epoch": cache._CACHE_EPOCH, "salt": "",
        "recipe_known": True, "input_count": 0, "inputs": [],
    }
    overhead = len(json.dumps(expected, sort_keys=True, separators=(",", ":")))
    salt = "s" * (payload_chars - overhead)
    monkeypatch.setenv("HARMONIC_CACHE_SALT", salt)
    key = cache.cache_key([], _digest_one, label="part:boundary")
    expected.update(key=key, salt=salt)
    tracer, exporter = exported_cache_spans(max_attribute_length=8192)
    with tracer.start_as_current_span("boundary"):
        assert cache.restore(key, [], "part:boundary") is False
    events = _wire_events(exporter)
    assert _received_recipe(events, "cache.miss") == expected
    chunks = [attrs for name, attrs in events if name == "cache.provenance"]
    assert len(chunks) == (payload_chars + 5999) // 6000
    assert sum(len(attrs["chunk"]) for attrs in chunks) == payload_chars
    assert all(len(attrs["chunk"].encode("ascii")) <= 6000 for attrs in chunks)
    assert len(exporter.get_finished_spans()) == 3  # task, download, record; no dep spans


def test_remote_manifest_many_inputs_roundtrip(
    tmp_path, fake, exported_cache_spans
):
    deps = [
        _make_dep(tmp_path, f"recipe-{index:04d}.py", hashlib.md5(str(index).encode()).hexdigest())
        for index in range(250)
    ]
    key = cache.cache_key(deps, _digest_one, label="assembly:many")
    tracer, exporter = exported_cache_spans(max_attribute_length=8192)
    with tracer.start_as_current_span("many"):
        assert cache.restore(key, [], "assembly:many") is False
    events = _wire_events(exporter)
    recipe = _received_recipe(events, "cache.miss")
    assert recipe["input_count"] == 250
    assert recipe["inputs"] == _events(tmp_path)[-1]["inputs"]
    assert 1 < sum(name == "cache.provenance" for name, _ in events) < 32


@pytest.mark.parametrize("limits", [
    {"max_attribute_length": 64},
    {"max_event_attributes": 2},
])
def test_sdk_truncation_or_event_loss_cannot_appear_complete(
    tmp_path, fake, exported_cache_spans, limits
):
    dep = _make_dep(tmp_path, "long.py", "d" * 7000)
    key = cache.cache_key([dep], _digest_one, label="part:loss")
    tracer, exporter = exported_cache_spans(**limits)
    with tracer.start_as_current_span("limited"):
        assert cache.restore(key, [], "part:loss") is False
    assert _received_recipe(_wire_events(exporter), "cache.miss") is None


def test_unknown_recipe_is_explicitly_incomplete(tmp_path, fake, exported_cache_spans):
    tracer, exporter = exported_cache_spans()
    with tracer.start_as_current_span("unknown"):
        assert cache.restore("a" * 64, [], "part:unknown") is False
    events = _wire_events(exporter)
    decision = next(attrs for name, attrs in events if name == "cache.miss")
    assert decision["manifest_input_count"] == -1
    assert decision["manifest_complete"] is False
    assert _received_recipe(events, "cache.miss") is None
    assert _events(tmp_path)[-1]["recipe_known"] is False


def test_large_manifest_emits_every_input_without_span_event_flood(
    tmp_path, fake, exported_cache_spans
):
    dep = _make_dep(tmp_path, "huge.py", "d" * (6000 * 32))
    key = cache.cache_key([dep], _digest_one, label="part:huge")
    tracer, exporter = exported_cache_spans(max_attribute_length=8192)
    with tracer.start_as_current_span("huge"):
        assert cache.restore(key, [], "part:huge") is False
    events = _wire_events(exporter)
    decision = next(attrs for name, attrs in events if name == "cache.miss")
    assert decision["manifest_chunk_count"] == 33
    assert decision["manifest_emitted_chunks"] == 33
    assert decision["manifest_complete"] is True
    assert decision["manifest_transport"] == "logs"
    assert sum(name == "cache.provenance" for name, _ in events) == 33
    assert _received_recipe(events, "cache.miss")["inputs"][0]["digest"] == "d" * (6000 * 32)
    assert not any(
        event.name == "cache.provenance"
        for span in exporter.get_finished_spans() for event in span.events
    )
    assert _events(tmp_path)[-1]["inputs"][0]["digest"] == "d" * (6000 * 32)


@pytest.mark.parametrize("failure_at", ["outcome", "chunk", "logging"])
def test_telemetry_sink_failure_preserves_successful_cache_behavior(
    tmp_path, fake, real_unpack, monkeypatch, exported_cache_spans, failure_at
):
    monkeypatch.setattr(cache, "REPO_ROOT", tmp_path)
    output_root = tmp_path / "cad" / "out"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", output_root)
    monkeypatch.setattr(cache, "_unpack", real_unpack)
    dep = _make_dep(tmp_path, "input.py", "digest")
    key = cache.cache_key([dep], _digest_one, label="part:sink-failure")
    out = output_root / "out.bin"
    out.write_bytes(b"real packed payload")
    original_event = _telemetry.event
    original_debug = _telemetry.debug

    def event(name, **attributes):
        if failure_at == "outcome":
            raise RuntimeError("telemetry sink failed")
        original_event(name, **attributes)

    def debug(message, **attributes):
        if failure_at == "chunk" and message == "cache.provenance":
            raise RuntimeError("chunk sink failed")
        original_debug(message, **attributes)

    def broken_log(*args, **kwargs):
        raise RuntimeError("logging sink failed")

    monkeypatch.setattr(_telemetry, "event", event)
    monkeypatch.setattr(_telemetry, "debug", debug)
    if failure_at == "logging":
        for name in ("info", "debug", "warn"):
            monkeypatch.setattr(_telemetry, name, broken_log)
    tracer, exporter = exported_cache_spans()
    with tracer.start_as_current_span("failing-sink"):
        assert cache.restore(key, [], "part:sink-failure") is False
        assert cache.store(key, [out], "part:sink-failure") == "stored"
        assert fake.blobs[key].startswith(b"\x1f\x8b")  # real gzip packing/upload
        assert cache.last_stored_key("part:sink-failure") == key
        out.unlink()
        assert cache.restore(key, [out], "part:sink-failure") is True
        assert out.read_bytes() == b"real packed payload"
    assert _received_recipe(_wire_events(exporter), "cache.store") is None
    assert [item["event"] for item in _events(tmp_path)] == [
        "restore_miss", "store", "restore_hit",
    ]


def test_manifest_logs_do_not_consume_span_event_budget(
    tmp_path, fake, exported_cache_spans
):
    dep = _make_dep(tmp_path, "many-fragments.py", "d" * 18000)
    key = cache.cache_key([dep], _digest_one, label="part:budget")
    tracer, exporter = exported_cache_spans(max_events=1)
    with tracer.start_as_current_span("single-event-budget") as task_span:
        assert cache.restore(key, [], "part:budget") is False
        trace_id = task_span.get_span_context().trace_id
        span_id = task_span.get_span_context().span_id
    events = _wire_events(exporter)
    assert _received_recipe(events, "cache.miss")["inputs"][0]["digest"] == "d" * 18000
    chunks = [
        record for record in exporter.cache_logs.get_finished_logs()
        if record.log_record.body == "cache.provenance"
    ]
    assert len(chunks) == 4
    assert all(record.log_record.trace_id == trace_id for record in chunks)
    assert all(record.log_record.span_id == span_id for record in chunks)
    assert all(
        record.resource.attributes["service.name"] == _telemetry.BUILD_INFRA_SERVICE
        for record in chunks
    )
    # Real exported evidence with one ingested fragment lost must fail closed.
    missing_one = []
    for name, attrs in events:
        if name == "cache.provenance" and attrs["chunk_index"] == 1:
            continue
        missing_one.append((name, attrs))
    assert _received_recipe(missing_one, "cache.miss") is None
    # An equal-length alteration is detected by checksum, not just counts.
    damaged = [
        (name, {**attrs, "chunk": "x" + attrs["chunk"][1:]})
        if name == "cache.provenance" and attrs["chunk_index"] == 1
        else (name, attrs)
        for name, attrs in events
    ]
    assert _received_recipe(damaged, "cache.miss") is None


@pytest.mark.parametrize("baseline", ["cache.store", "cache.hit"])
def test_remote_baseline_identifies_changed_dependency_across_disposable_seats(
    tmp_path, fake, monkeypatch, exported_cache_spans, baseline
):
    recipe_dep = _make_dep(tmp_path, "_stock_fastener.py", "old recipe digest")
    config_dep = _make_dep(tmp_path, "spring.yaml", "unchanged config digest")
    label = "part:vn_counter_spring"
    old_key = cache.cache_key([recipe_dep, config_dep], _digest_one, label=label)
    out = tmp_path / "out.bin"
    out.write_bytes(b"payload")
    tracer, exporter = exported_cache_spans()
    with tracer.start_as_current_span("previous-disposable-seat"):
        if baseline == "cache.store":
            assert cache.store(old_key, [out], label) == "stored"
        else:
            fake.blobs[old_key] = b"built-on-another-seat"
            assert cache.restore(old_key, [out], label) is True
    # New seat has neither process provenance nor the old local key sidecar.
    monkeypatch.setattr(cache, "_KEY_INPUTS", {})
    monkeypatch.setattr(cache, "_KEY_CONTEXT", {})
    monkeypatch.setattr(cache, "_KEYDIR", tmp_path / "new-seat" / "cache-keys")
    Path(recipe_dep).write_text("new recipe digest", encoding="utf-8")
    new_key = cache.cache_key([recipe_dep, config_dep], _digest_one, label=label)
    with tracer.start_as_current_span("current-disposable-seat"):
        assert cache.restore(new_key, [], label) is False
    assert cache.last_stored_key(label) is None
    evidence = _wire_events(exporter)
    previous = _received_recipe(evidence, baseline)
    current = _received_recipe(evidence, "cache.miss")
    assert previous["key"] == old_key and current["key"] == new_key
    assert previous["epoch"] == current["epoch"]
    assert previous["salt"] == current["salt"]
    old_inputs = {item["path"]: item["digest"] for item in previous["inputs"]}
    new_inputs = {item["path"]: item["digest"] for item in current["inputs"]}
    changed = {
        path for path in old_inputs.keys() | new_inputs.keys()
        if old_inputs.get(path) != new_inputs.get(path)
    }
    assert changed == {"_stock_fastener.py"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
