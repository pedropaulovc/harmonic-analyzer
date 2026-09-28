r"""Tests for the artefact-cache provenance/observability surface (issue #73).

Pure python, NO SolidWorks and NO Azure -- the backend is faked in-memory and the
on-disk sinks (cache.jsonl, the per-label key sidecar) are redirected to a tmp dir.

    python cad/scripts/test_artifact_cache.py     # or: pytest cad/scripts/test_artifact_cache.py
"""

from __future__ import annotations

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
def fake(tmp_path, monkeypatch):
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


def test_prewarm_opens_the_connection_once_and_the_probe_reuses_it(monkeypatch):
    """A farm leaf warms the cache connection while its graph loads. A probe that
    arrives mid-warm must wait for that one client, never build a second (a
    second SDK import + TLS handshake is the cost the warm-up exists to hide), and
    the warm-up must have touched the service so the connection is really open."""
    import threading
    import time

    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setattr(cache, "_BACKEND", cache._UNSET)
    backend = _FakeBackend()
    touched: list[str] = []
    backend.exists = lambda key: touched.append(key) or False
    built: list[int] = []
    constructing = threading.Event()

    def slow_make_backend():
        constructing.set()
        time.sleep(0.2)
        built.append(1)
        return backend

    monkeypatch.setattr(cache, "_make_backend", slow_make_backend)
    warm = cache.prewarm()
    assert warm is not None
    assert constructing.wait(5)
    assert cache._backend() is backend  # arrives mid-construction
    warm.join(5)
    assert built == [1]
    assert touched == ["prewarm"]


@pytest.mark.parametrize("mode", ["ro", "off"])
def test_prewarm_is_a_no_op_for_a_process_that_does_not_publish(monkeypatch, mode):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", mode)
    monkeypatch.setattr(cache, "_BACKEND", cache._UNSET)
    monkeypatch.setattr(
        cache, "_make_backend", lambda: pytest.fail("a non-publishing process connected")
    )
    assert cache.prewarm() is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
