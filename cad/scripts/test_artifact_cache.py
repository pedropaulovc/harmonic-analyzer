r"""Tests for the artefact-cache provenance/observability surface (issue #73).

Pure python, NO SolidWorks and NO Azure -- the backend is faked in-memory and the
on-disk sinks (cache.jsonl, the per-label key sidecar) are redirected to a tmp dir.

    python cad/scripts/test_artifact_cache.py     # or: pytest cad/scripts/test_artifact_cache.py
"""

from __future__ import annotations

import json
import logging
import subprocess
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

    assert cache.restore(key, [out], "part:x") == cache.RestoreOutcome.HIT
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
    assert cache.restore(key, [], "part:x") == cache.RestoreOutcome.MISS
    assert records == [("debug", f"[cache] miss  part:x ({key[:12]}) -> building locally")]
    events = _events(tmp_path)
    assert [e["event"] for e in events] == ["restore_miss"]
    assert events[0]["inputs"] == [{"path": "input.py", "digest": "VALUE = 1\n"}]


def _held_by_unpack(monkeypatch, *errors):
    """``_unpack`` raising ``errors`` in turn, then succeeding; returns the call log."""
    pending = iter(errors)
    calls: list[int] = []

    def unpack(_blob):
        calls.append(1)
        error = next(pending, None)
        if error is not None:
            raise error

    monkeypatch.setattr(cache, "_unpack", unpack)
    monkeypatch.setattr(cache, "_HELD_RETRY_DELAYS_S", (0.0, 0.0, 0.0))
    return calls


def _mapped(filename):
    """The stud-6 error: the CRT's EINVAL for ERROR_USER_MAPPED_FILE."""
    return OSError(22, "Invalid argument", filename)


def test_restore_hit_over_a_share_locked_output_raises_instead_of_falling_through(
    tmp_path, fake, monkeypatch
):
    """The one restore failure that must not become "building locally": a cached
    build exists but SolidWorks still holds the output (Windows share lock), and
    a local rebuild would mint a token the fleet cannot reproduce."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    fake.blobs[key] = b"payload"
    locked = PermissionError(13, "Permission denied", "cad/out/sldprt/x.SLDPRT")
    calls = _held_by_unpack(monkeypatch, *[locked] * 4)

    with pytest.raises(cache.RestoreLocked, match="held by another process") as info:
        cache.restore(key, [], "part:x")

    assert info.value.key == key
    assert len(calls) == 4  # the first attempt plus one per configured delay
    assert [e["event"] for e in _events(tmp_path)] == ["restore_locked"]


def test_restore_over_a_mapped_output_retries_then_raises_locked(
    tmp_path, fake, monkeypatch
):
    """EINVAL naming a cad/out file is a held destination, not a generic error:
    it is waited out, and a hold that outlasts the wait is RestoreLocked -- never
    the "building locally" fall-through that stud-6 took."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="drawing:x")
    fake.blobs[key] = b"payload"
    held = str(cache._CACHE_OUTPUT_ROOT / "png" / "drawing-x.png")
    calls = _held_by_unpack(monkeypatch, *[_mapped(held)] * 4)

    with pytest.raises(cache.RestoreLocked, match="errno 22"):
        cache.restore(key, [], "drawing:x")

    assert len(calls) == 4
    (event,) = _events(tmp_path)
    assert event["event"] == "restore_locked"
    assert event["errno"] == 22
    assert event["filename"] == held


def test_restore_over_a_briefly_mapped_output_is_a_hit(tmp_path, fake, monkeypatch):
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="drawing:x")
    fake.blobs[key] = b"payload"
    held = str(cache._CACHE_OUTPUT_ROOT / "png" / "drawing-x.png")
    calls = _held_by_unpack(monkeypatch, _mapped(held), _mapped(held))

    assert cache.restore(key, [], "drawing:x") == cache.RestoreOutcome.HIT
    assert len(calls) == 3
    assert [e["event"] for e in _events(tmp_path)] == ["restore_hit"]


def test_restore_einval_outside_cad_out_is_an_error_without_retry(
    tmp_path, fake, monkeypatch
):
    """The classification stays narrow: an EINVAL with no cad/out filename is an
    ordinary restore error, reported as ERROR (not a miss) with its OS detail."""
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    fake.blobs[key] = b"payload"
    calls = _held_by_unpack(monkeypatch, _mapped(str(tmp_path / "elsewhere.bin")))

    assert cache.restore(key, [], "part:x") == cache.RestoreOutcome.ERROR
    assert len(calls) == 1
    (event,) = _events(tmp_path)
    assert event["event"] == "restore_error"
    assert event["errno"] == 22
    assert event["filename"] == str(tmp_path / "elsewhere.bin")


def test_restore_other_unpack_errors_are_errors_not_misses(
    tmp_path, fake, monkeypatch
):
    dep = _make_dep(tmp_path, "input.py", "VALUE = 1\n")
    key = cache.cache_key([dep], _digest_one, label="part:x")
    fake.blobs[key] = b"payload"
    monkeypatch.setattr(
        cache, "_unpack", lambda _blob: (_ for _ in ()).throw(OSError("disk full"))
    )

    assert cache.restore(key, [], "part:x") == cache.RestoreOutcome.ERROR
    assert [e["event"] for e in _events(tmp_path)] == ["restore_error"]


def test_unpack_names_the_member_it_failed_to_write(tmp_path, monkeypatch):
    """The telemetry must say which output failed even when the OS error is
    path-less; the archive member rides the exception."""
    monkeypatch.setattr(cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", tmp_path / "cad" / "out")
    output = tmp_path / "cad" / "out" / "png" / "drawing-x.png"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"new")
    blob = cache._pack([output])
    monkeypatch.setattr(
        cache.tarfile.TarFile,
        "extract",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError(22, "Invalid argument")),
    )

    with pytest.raises(OSError) as info:
        cache._unpack(blob)

    fields = cache._error_fields(info.value)
    assert fields["member"] == "cad/out/png/drawing-x.png"
    assert fields["errno"] == 22
    assert "filename" not in fields


# --------------------------------------------------------------------------- #
# The real Windows mechanism: another process holding a mapped view of the
# destination makes open(dest, "wb") fail with OSError(22) (stud-6, 2026-09-22;
# the repro this ports is C:/src/dt-logs/flakes/repro_restore_einval.py).
# --------------------------------------------------------------------------- #
_MAP_AND_HOLD = """
import mmap, sys, time
f = open(sys.argv[1], "rb")
view = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
print("READY", flush=True)
time.sleep(float(sys.argv[2]))
"""


@pytest.fixture
def real_tree(tmp_path, monkeypatch):
    """A cache HIT whose archive rewrites one existing cad/out PNG, extracted by
    the REAL ``_unpack`` into a tmp repo root. Returns (key, png path)."""
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.setattr(cache, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", tmp_path / "cad" / "out")
    monkeypatch.setattr(cache, "_REPORTS", tmp_path / "reports")
    monkeypatch.setattr(cache, "_EVENTS_LOG", tmp_path / "reports" / "cache.jsonl")
    monkeypatch.setattr(cache, "_KEYDIR", tmp_path / "reports" / "cache-keys")
    backend = _FakeBackend()
    monkeypatch.setattr(cache, "_BACKEND", backend)
    png = tmp_path / "cad" / "out" / "png" / "drawing-x.png"
    png.parent.mkdir(parents=True)
    png.write_bytes(b"NEW" + bytes(4096))
    key = "m" * 64
    backend.blobs[key] = cache._pack([png])
    png.write_bytes(b"OLD" + bytes(4096))
    return key, png


def _hold_mapped(path: Path, seconds: float):
    child = subprocess.Popen(
        [sys.executable, "-c", _MAP_AND_HOLD, str(path), str(seconds)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdout is not None
    assert child.stdout.readline().startswith("READY")
    return child


@pytest.mark.skipif(sys.platform != "win32", reason="Windows mapped-file semantics")
def test_restore_over_a_file_mapped_by_another_process_raises_locked(
    real_tree, monkeypatch
):
    key, png = real_tree
    monkeypatch.setattr(cache, "_HELD_RETRY_DELAYS_S", (0.05, 0.05))
    holder = _hold_mapped(png, 30)
    try:
        with pytest.raises(cache.RestoreLocked) as info:
            cache.restore(key, [png], "drawing:x")
    finally:
        holder.kill()
        holder.wait()

    assert info.value.cause.errno == 22
    assert Path(info.value.cause.filename).resolve() == png.resolve()
    (event,) = _events(cache._REPORTS)
    assert event["event"] == "restore_locked"
    assert event["member"] == "cad/out/png/drawing-x.png"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows mapped-file semantics")
def test_restore_waits_out_a_mapping_released_after_a_second(real_tree, monkeypatch):
    key, png = real_tree
    monkeypatch.setattr(cache, "_HELD_RETRY_DELAYS_S", (0.5, 1.0, 2.0, 4.0))
    holder = _hold_mapped(png, 1.0)
    try:
        assert cache.restore(key, [png], "drawing:x") == cache.RestoreOutcome.HIT
    finally:
        holder.kill()
        holder.wait()

    assert png.read_bytes()[:3] == b"NEW"


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
    assert cache.restore(new_key, [], "part:x") == cache.RestoreOutcome.MISS
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
        assert cache.restore(k_new, [out], "part:x") == cache.RestoreOutcome.HIT
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
        assert cache.restore(k_new, [out], "part:x") == cache.RestoreOutcome.HIT
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
        assert cache.restore(k_new, [out], "part:x") == cache.RestoreOutcome.HIT
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

    assert cache.restore(k_new, [out], "part:x") == cache.RestoreOutcome.HIT
    assert "restore_error" not in [e["event"] for e in _events(tmp_path)]


def test_hit_under_same_key_is_not_drift(tmp_path, fake):
    out = tmp_path / "out.bin"
    out.write_text("v0", encoding="utf-8")
    key = "3" * 64
    cache.store(key, [out], "part:x")
    assert cache.restore(key, [out], "part:x") == cache.RestoreOutcome.HIT
    assert [e["event"] for e in _events(tmp_path)][-1] == "restore_hit"


# --------------------------------------------------------------------------- #
# Mode gating: off writes nothing; ro pulls but records a publish-skip
# --------------------------------------------------------------------------- #
def test_mode_off_is_silent(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    assert cache.restore("k" * 64, [], "part:x") == cache.RestoreOutcome.MISS
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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
